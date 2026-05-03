"""Grounded chat tool-loop tests with mocked Anthropic client.

Locks down the agentic-loop behaviour: a tool_use response triggers the
product tool executor, results are fed back, the loop continues until
end_turn, and the final response surfaces text + products + retrievals.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models import CorpusChunk
import app.services.grounded_chat as gc


def _block(**kwargs):
    return SimpleNamespace(**kwargs)


def _msg(content, stop_reason, model="claude-opus-4-7", in_tokens=100, out_tokens=50):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


@pytest.fixture
def mock_client(monkeypatch):
    """Inject a mock Anthropic client into grounded_chat."""
    client = MagicMock()
    gc._client = client
    yield client
    gc._client = None


@pytest.fixture
async def seeded_db(db_session, stub_embedding):
    chunk = CorpusChunk(
        source="Ashtanga Hridaya",
        section="Sutrasthana",
        chapter="Ch.2 Dinacharya",
        verse_start="2.7",
        english="Daily abhyanga pacifies vata.",
        summary="abhyanga daily routine",
        embedding=stub_embedding("abhyanga daily routine"),
        embedding_model="stub",
    )
    db_session.add(chunk)
    await db_session.commit()
    return db_session


async def test_tool_loop_executes_product_tool_and_returns_text(seeded_db, mock_client):
    """tool_use → execute → tool_result → end_turn with final text."""
    tool_use_block = _block(
        type="tool_use",
        id="toolu_xyz",
        name="recommend_age_ayurveda_products",
        input={"concern": "sleep", "dosha": "vata"},
    )
    text_block = _block(type="text", text="Try Natural Sleep Aid daily.")

    call_log = []

    async def fake_create(**kwargs):
        call_log.append(kwargs)
        if len(call_log) == 1:
            return _msg([tool_use_block], stop_reason="tool_use")
        return _msg([text_block], stop_reason="end_turn")

    mock_client.messages.create = fake_create

    result = await gc.generate_grounded_response(
        seeded_db, "I cannot sleep, what do you recommend?", language="en"
    )

    assert "Natural Sleep Aid" in result["content"]
    assert len(result["tool_invocations"]) == 1
    assert result["tool_invocations"][0]["name"] == "recommend_age_ayurveda_products"
    assert len(result["products"]) > 0
    assert len(call_log) == 2  # tool_use round + final round


async def test_tool_loop_skips_tool_for_educational_query(seeded_db, mock_client):
    """When Claude returns end_turn directly (no tool_use), no tool fires."""
    text_block = _block(type="text", text="The three doshas are Vata, Pitta, and Kapha.")

    async def fake_create(**kwargs):
        return _msg([text_block], stop_reason="end_turn")

    mock_client.messages.create = fake_create

    result = await gc.generate_grounded_response(
        seeded_db, "What are the three doshas?", language="en"
    )

    assert result["tool_invocations"] == []
    assert result["products"] == []
    assert "doshas" in result["content"].lower()


async def test_tool_loop_terminates_at_max_iterations(seeded_db, mock_client):
    """If Claude keeps calling tools forever, the loop bails out cleanly."""
    tool_use_block = _block(
        type="tool_use",
        id="toolu_loop",
        name="recommend_age_ayurveda_products",
        input={"concern": "sleep", "dosha": "vata"},
    )

    async def fake_create(**kwargs):
        return _msg([tool_use_block], stop_reason="tool_use")

    mock_client.messages.create = fake_create

    result = await gc.generate_grounded_response(
        seeded_db, "loop forever", language="en"
    )

    # Should hit the iteration cap, not infinite-loop.
    assert len(result["tool_invocations"]) <= gc._TOOL_LOOP_MAX_ITERATIONS


async def test_response_includes_retrievals(seeded_db, mock_client):
    text_block = _block(type="text", text="Per [Ashtanga Hridaya, Sutrasthana, Ch.2 verse 7], abhyanga daily.")

    async def fake_create(**kwargs):
        return _msg([text_block], stop_reason="end_turn")

    mock_client.messages.create = fake_create

    result = await gc.generate_grounded_response(seeded_db, "what is abhyanga", language="en")

    assert len(result["retrievals"]) > 0
    assert "Ashtanga Hridaya" in result["retrievals"][0]["label"]


async def test_unknown_tool_returns_error_to_claude(seeded_db, mock_client):
    """If Claude calls a tool we don't recognise, the loop returns an error
    tool_result rather than crashing."""
    weird_tool_block = _block(
        type="tool_use",
        id="toolu_weird",
        name="some_unregistered_tool",
        input={},
    )
    text_block = _block(type="text", text="Sorry, that didn't work.")

    call_log = []

    async def fake_create(**kwargs):
        call_log.append(kwargs)
        if len(call_log) == 1:
            return _msg([weird_tool_block], stop_reason="tool_use")
        return _msg([text_block], stop_reason="end_turn")

    mock_client.messages.create = fake_create

    # Should not raise — unknown tool returns error in tool_result.
    result = await gc.generate_grounded_response(seeded_db, "whatever", language="en")
    assert result["content"]
