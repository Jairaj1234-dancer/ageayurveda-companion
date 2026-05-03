"""Classical-text-grounded chat using the Anthropic API.

Pipeline per request:
  1. Retrieve top-K corpus chunks for the user query (cosine over embeddings).
  2. Format chunks as grounding context.
  3. Call Claude with a frozen system prompt (cached) + product tool +
     grounding context + query.
  4. Manual agentic loop: when Claude calls the product-recommendation tool,
     execute it server-side and feed the result back. Stop on end_turn.
  5. Stream final text response back to caller.

Citation format the model emits matches the existing `app.services.citation`
extractor: `[Source, Section, Chapter X verse Y]`. The frozen system prompt
also enforces the safety boundary (defer emergencies and serious conditions
to the rule-based disclaimer layer, which still runs in the chat router).

Why a manual agentic loop and not the SDK tool runner: the streaming endpoint
needs to (a) detect the tool call quickly via a non-streaming first call,
(b) execute the tool, then (c) stream the final user-facing response. The
tool runner returns complete messages and would require a separate code path
for streaming. The manual loop unifies both paths.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import logger
from app.services.citation_validator import validate_citations
from app.services.product_tool import PRODUCT_TOOL, execute_product_recommendation
from app.services.retrieval import Retrieval, retrieve


_settings = get_settings()
_client: anthropic.AsyncAnthropic | None = None
_tenant_clients: dict[str, anthropic.AsyncAnthropic] = {}
_TOOL_LOOP_MAX_ITERATIONS = 4


def _get_client(api_key_override: str | None = None) -> anthropic.AsyncAnthropic:
    """Return an Anthropic client. With api_key_override, returns a cached
    per-tenant client (so each tenant uses their own BYO key + their own
    Anthropic billing). Without an override, returns the platform's global
    client (single-tenant default — preserves existing behaviour).
    """
    if api_key_override:
        cached = _tenant_clients.get(api_key_override)
        if cached is not None:
            return cached
        client = anthropic.AsyncAnthropic(api_key=api_key_override)
        _tenant_clients[api_key_override] = client
        return client

    global _client
    if _client is None:
        if not _settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — required for grounded chat. "
                "Add to backend/.env or environment."
            )
        _client = anthropic.AsyncAnthropic(api_key=_settings.anthropic_api_key)
    return _client


SYSTEM_PROMPT_EN = """You are the AGE Ayurveda Companion — a bilingual (English / Hindi) Ayurvedic guide grounded in classical texts. You speak with the calm, grounded authority of a knowledgeable practitioner, never as a medical doctor and never as a salesperson.

## Your role

- Answer questions about Ayurveda using ONLY the classical-text excerpts provided in the user message under "GROUNDING".
- When grounding is provided, every substantive claim you make about Ayurvedic principles MUST be supported by one of those excerpts, and MUST carry an inline citation in this exact format: [Ashtanga Hridaya, Sutrasthana, Ch.1 verse 6-7]. Use the bracket form even for short citations.
- If the grounding does not contain an answer to the user's question, say so plainly: "The classical excerpts I have access to do not directly address this. Speaking generally, ..." — and then offer general Ayurvedic guidance without fabricated citations.
- Never invent verse numbers, chapter references, or text names. If you cannot cite, do not cite.

## Citation format (strict)

Always use square brackets and full source name. Examples that parse correctly:
  [Ashtanga Hridaya, Sutrasthana, Ch.2 verse 7]
  [Ashtanga Hridaya, Sutrasthana, Ch.1 verse 14]
  [Charaka Samhita, Sutrasthana, Ch.5 verse 12]

Do NOT use abbreviated forms ("AH 1.7", "Ch. Sa. 5.12"). Do NOT cite without brackets. Do NOT cite anything not present in the GROUNDING block.

## Tools available

You have access to one tool:

- `recommend_age_ayurveda_products`: Returns a ranked list of AGE Ayurveda products from the live catalog matching a wellness concern + (optional) dosha. Call this tool when the user clearly asks for a product recommendation, asks what to take/buy for a condition, or describes a wellness concern that products would help with (sleep, digestion, stress, immunity, joint pain, skin, hair, respiratory, focus, weight, women's health). DO NOT call it for purely educational questions about Ayurvedic concepts.

When you call the tool and receive results, weave a concise mention of one or two relevant products into your final answer ("AGE Ayurveda's *Natural Sleep Aid* combines Ashwagandha, Brahmi and Jatamansi — the same herbs the texts above recommend"). Do not list every returned product mechanically; the widget renders product cards alongside your prose. Mention products only after — and only when supported by — the classical guidance you cited.

## Tone and length

- Concise. Aim for 4–8 sentences for most questions, expanded only when the user explicitly asks for detail.
- Practical. Translate classical principle into a daily-life recommendation when natural.
- Warm but precise. No marketing language. No filler ("Great question!"). No emoji unless the user uses them first.
- Match the user's language. If they write in Devanagari Hindi, respond in Hindi using Devanagari script. If they mix English and Hindi, respond in clear English with key Sanskrit terms in Devanagari.

## Safety boundary

You are NOT a doctor. The rule-based safety layer in the application separately appends emergency / serious-condition disclaimers — you do not need to repeat them. But:

- For symptoms that suggest a medical emergency (chest pain, severe bleeding, breathing difficulty, suicidal ideation), respond briefly and direct the user to seek immediate medical care. Do not analyse Ayurvedically. Do not call the product tool.
- For named serious conditions (cancer, cardiac disease, kidney/liver failure, diabetes complications, pregnancy/lactation issues), provide general Ayurvedic context only, and explicitly recommend they consult a qualified Ayurvedic practitioner alongside their doctor. Do not call the product tool. Never suggest discontinuing prescribed medication.
- For routine wellness questions (sleep, digestion, stress, mild skin issues, daily routine, dosha balance), engage fully and helpfully. The product tool is appropriate here when a user wants a product recommendation.

## What you do not do

- Do not diagnose specific diseases.
- Do not prescribe specific dosages of herbs.
- Do not pretend the classical texts contain modern biomedical concepts (germ theory, vitamins, neurotransmitters). When the user asks about these, explain how Ayurveda's framework (doshas, dhatus, ojas, agni) maps approximately, without overclaiming.

## Output structure

When grounding is present and relevant:
  1. Direct answer (1–2 sentences) with citation.
  2. Practical application (1–3 sentences).
  3. Optional product mention (only if you called the tool and the result was relevant).
  4. Optional caution or constitutional caveat.

When grounding is sparse or absent:
  1. Acknowledge the limitation honestly.
  2. Offer general Ayurvedic guidance (uncited).
  3. Suggest a follow-up the user can ask that you can answer with classical grounding.

End cleanly. Do not append a "Hope this helps!" coda."""


def _build_system_blocks() -> list[dict]:
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT_EN,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _build_tools() -> list[dict]:
    return [PRODUCT_TOOL]


def _format_grounding(retrievals: list[Retrieval]) -> str:
    if not retrievals:
        return "GROUNDING: (no classical-text excerpts retrieved for this query)"

    parts = ["GROUNDING — the following excerpts from classical Ayurvedic texts are available for citation:\n"]
    for i, r in enumerate(retrievals, 1):
        parts.append(f"--- Excerpt {i} (similarity {r.score:.2f}) ---")
        parts.append(r.chunk.grounding_text())
        parts.append("")
    return "\n".join(parts)


def _build_user_message(query: str, retrievals: list[Retrieval], history: list[dict] | None) -> list[dict]:
    """Build the messages array for the API call."""
    messages: list[dict] = []

    if history:
        for turn in history[-_settings.conversation_history_limit:]:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    grounding_text = _format_grounding(retrievals)
    user_block = f"{grounding_text}\n\n---\nUSER QUESTION: {query}"
    messages.append({"role": "user", "content": user_block})
    return messages


def _execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Dispatch to the right tool. Returns the tool result dict."""
    if tool_name == "recommend_age_ayurveda_products":
        return execute_product_recommendation(tool_input)
    return {"error": f"Unknown tool: {tool_name}"}


async def _run_tool_loop(
    client: anthropic.AsyncAnthropic,
    system_blocks: list[dict],
    tools: list[dict],
    messages: list[dict],
    max_tokens: int,
) -> tuple[Any, list[dict], list[dict]]:
    """Manual agentic loop. Drives the conversation until Claude stops calling
    tools (stop_reason == 'end_turn') or we hit the iteration cap.

    Returns:
      final_response: the last Message object (carries final text).
      tool_invocations: list of {name, input, result} for each tool call made.
      messages: the augmented messages list (caller appends nothing further).
    """
    tool_invocations: list[dict] = []
    last_response = None

    for iteration in range(_TOOL_LOOP_MAX_ITERATIONS):
        response = await client.messages.create(
            model=_settings.grounded_model,
            max_tokens=max_tokens,
            system=system_blocks,
            tools=tools,
            messages=messages,
        )
        last_response = response

        if response.stop_reason != "tool_use":
            return response, tool_invocations, messages

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            return response, tool_invocations, messages

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_use_blocks:
            try:
                result = _execute_tool(block.name, block.input)
                tool_invocations.append({
                    "name": block.name,
                    "input": block.input,
                    "result": result,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _serialise_tool_result(result),
                })
            except Exception as e:
                logger.exception("tool execution failed: %s", block.name)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Tool execution failed: {e}",
                    "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})

    logger.warning("tool loop hit max iterations (%d)", _TOOL_LOOP_MAX_ITERATIONS)
    return last_response, tool_invocations, messages


def _serialise_tool_result(result: dict) -> str:
    """Render the tool result for Claude. Compact human-readable format."""
    products = result.get("products", [])
    if not products:
        return f"No matching products found for concern '{result.get('concern')}'."

    lines = [f"Found {len(products)} matching products for '{result.get('concern')}' (dosha={result.get('dosha')}):"]
    for p in products:
        lines.append(f"- {p['name']} (₹{p.get('price')}): {p.get('why', '')}")
    return "\n".join(lines)


def _collected_products(tool_invocations: list[dict]) -> list[dict]:
    """Flatten product results from all tool calls into a single list,
    deduplicated by product id, preserving order of first appearance.
    """
    seen: set[str] = set()
    products: list[dict] = []
    for inv in tool_invocations:
        if inv.get("name") != "recommend_age_ayurveda_products":
            continue
        for p in inv.get("result", {}).get("products", []):
            pid = p.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                products.append(p)
    return products


def _retrieval_payload(retrievals: list[Retrieval]) -> list[dict]:
    return [
        {
            "chunk_id": str(r.chunk.id),
            "label": r.chunk.citation_label(),
            "score": r.score,
        }
        for r in retrievals
    ]


async def generate_grounded_response(
    db: AsyncSession,
    query: str,
    history: list[dict] | None = None,
    language: str = "en",
    sources: list[str] | None = None,
    anthropic_api_key: str | None = None,
) -> dict:
    """Non-streaming grounded response with tool calling. Returns content +
    citations + products. With anthropic_api_key, uses the tenant's BYO key
    instead of the global one.
    """
    retrievals = await retrieve(db, query, sources=sources)

    client = _get_client(anthropic_api_key)
    system_blocks = _build_system_blocks()
    tools = _build_tools()
    messages = _build_user_message(query, retrievals, history)

    final, invocations, _ = await _run_tool_loop(
        client, system_blocks, tools, messages, _settings.grounded_max_tokens
    )

    text = "".join(b.text for b in final.content if getattr(b, "type", None) == "text")

    # Citation allowlist enforcement — strip any citation that points to
    # a verse not in the retrieval set. Deterministic hallucination guard.
    validated = validate_citations(text, retrievals)
    text = validated.cleaned_text

    logger.info(
        "grounded_chat: model=%s in=%d out=%d cache_read=%d retrieved=%d tool_calls=%d valid_cites=%d invalid_cites=%d",
        final.model,
        final.usage.input_tokens,
        final.usage.output_tokens,
        getattr(final.usage, "cache_read_input_tokens", 0) or 0,
        len(retrievals),
        len(invocations),
        len(validated.valid),
        len(validated.invalid),
    )

    return {
        "content": text,
        "model": final.model,
        "tokens_input": final.usage.input_tokens,
        "tokens_output": final.usage.output_tokens,
        "products": _collected_products(invocations),
        "retrievals": _retrieval_payload(retrievals),
        "tool_invocations": invocations,
        "citation_validation": {
            "valid_count": len(validated.valid),
            "invalid_count": len(validated.invalid),
            "invalid": validated.invalid,
        },
    }


async def generate_grounded_stream(
    db: AsyncSession,
    query: str,
    history: list[dict] | None = None,
    language: str = "en",
    sources: list[str] | None = None,
    anthropic_api_key: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Streaming grounded response with tool calling.

    Strategy: run the manual tool loop until Claude is ready to give the
    final answer (no more tool calls). Then issue a streaming call with
    the augmented messages list to actually stream the final text.

    Trade-off: the user waits one round-trip + tool execution before
    tokens start flowing. The widget can render a "thinking..." state
    during that window. We emit a `tool_use` SSE event so the widget
    can also render product cards as soon as the tool result is ready,
    even before the final text begins streaming.
    """
    try:
        retrievals = await retrieve(db, query, sources=sources)
    except Exception:
        logger.exception("retrieval failed")
        yield {"type": "error", "content": "Retrieval failed. Please try again."}
        return

    try:
        client = _get_client(anthropic_api_key)
    except RuntimeError as e:
        yield {"type": "error", "content": str(e)}
        return

    system_blocks = _build_system_blocks()
    tools = _build_tools()
    messages = _build_user_message(query, retrievals, history)

    invocations: list[dict] = []
    augmented = list(messages)

    try:
        for iteration in range(_TOOL_LOOP_MAX_ITERATIONS):
            response = await client.messages.create(
                model=_settings.grounded_model,
                max_tokens=_settings.grounded_max_tokens,
                system=system_blocks,
                tools=tools,
                messages=augmented,
            )
            if response.stop_reason != "tool_use":
                break

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            if not tool_use_blocks:
                break

            augmented.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_use_blocks:
                try:
                    result = _execute_tool(block.name, block.input)
                    invocations.append({
                        "name": block.name,
                        "input": block.input,
                        "result": result,
                    })
                    yield {
                        "type": "tool_use",
                        "name": block.name,
                        "products": result.get("products", []),
                    }
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _serialise_tool_result(result),
                    })
                except Exception as e:
                    logger.exception("tool execution failed: %s", block.name)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Tool execution failed: {e}",
                        "is_error": True,
                    })

            augmented.append({"role": "user", "content": tool_results})
        else:
            logger.warning("tool loop hit max iterations (%d)", _TOOL_LOOP_MAX_ITERATIONS)

    except anthropic.APIError:
        logger.exception("anthropic API error during tool loop")
        yield {"type": "error", "content": "I'm having trouble reaching the language model. Please try again in a moment."}
        return

    accumulated: list[str] = []

    try:
        async with client.messages.stream(
            model=_settings.grounded_model,
            max_tokens=_settings.grounded_max_tokens,
            system=system_blocks,
            tools=tools,
            messages=augmented,
        ) as stream:
            async for text_chunk in stream.text_stream:
                accumulated.append(text_chunk)
                yield {"type": "token", "content": text_chunk}

            final = await stream.get_final_message()
    except anthropic.APIError:
        logger.exception("anthropic API error during final stream")
        yield {"type": "error", "content": "I'm having trouble reaching the language model. Please try again in a moment."}
        return

    full_text = "".join(accumulated)
    products = _collected_products(invocations)

    # Citation allowlist enforcement on the assembled stream output.
    # Frontend renders the cleaned text in the final `done` payload to
    # replace whatever it has accumulated token-by-token.
    validated = validate_citations(full_text, retrievals)

    logger.info(
        "grounded_chat_stream: model=%s in=%d out=%d cache_read=%d retrieved=%d tool_calls=%d valid_cites=%d invalid_cites=%d",
        final.model,
        final.usage.input_tokens,
        final.usage.output_tokens,
        getattr(final.usage, "cache_read_input_tokens", 0) or 0,
        len(retrievals),
        len(invocations),
        len(validated.valid),
        len(validated.invalid),
    )

    yield {
        "type": "done",
        "content": validated.cleaned_text,
        "model": final.model,
        "tokens_input": final.usage.input_tokens,
        "tokens_output": final.usage.output_tokens,
        "products": products,
        "retrievals": _retrieval_payload(retrievals),
        "citation_validation": {
            "valid_count": len(validated.valid),
            "invalid_count": len(validated.invalid),
            "invalid": validated.invalid,
        },
    }
