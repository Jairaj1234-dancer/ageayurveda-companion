# AyurBGE — Ayurveda-Specialized Multilingual Retrieval Embedding Model

**Technical proposal for the IndiaAI Mission Compute Subsidy programme**

---

## 1. Executive summary

We propose **AyurBGE**, a domain-specialised retrieval embedding model fine-tuned on the **Bṛhattrayī (Caraka Saṃhitā, Suśruta Saṃhitā, Aṣṭāṅga Hṛdaya — 20,734 verses)** for downstream applications in AYUSH. AyurBGE is built by fine-tuning **BAAI/bge-m3** (open-source, Apache-2.0, 1024-dim, 8K context) on Sanskrit + IAST + English + Hindi pairs derived from the SARIT TEI XML corpus (CC-BY-SA 3.0) and a structured AYUSH knowledge graph spanning 171 dravyas, 206 formulations, 140 vyādhi, 73 procedures, 670 PubMed-curated PMIDs, and 103 diagnostic patterns.

**Public-good deliverables (open-source, free for all AYUSH developers):**
1. `AyurBGE-base-v1` (~568 M params) on Hugging Face under Apache 2.0
2. Training-pair dataset (CC-BY-SA 3.0, traceable to SARIT)
3. Reproducible eval harness (Apache 2.0, already shipped at backend/app/services/eval/)
4. Reproducible training script + hyperparameters
5. Benchmark scorecard against baseline bge-m3

**Compute requested:** ~150 GPU-hours on A100/H100 class hardware for the base fine-tune + ablations + a 7B Llama-3.2 distilled chat variant.

**Concrete success metric:** Lift Hit@5 on the project's `seed_v1.yaml` 27-question evaluable benchmark from the **measured `BAAI/bge-m3` baseline of 3.70% on the full 14,000-chunk corpus** (Caraka Saṃhitā + Aṣṭāṅga Hṛdaya, pure dense retrieval, see `govt/baseline_full_corpus.json` for the JSON scorecard) to a target **≥ 40% — a 10× lift**. The earlier production hybrid pipeline using `paraphrase-multilingual-MiniLM-L12-v2` produced 0% Hit@5; bge-m3 alone already moved the floor to 3.7%; AyurBGE is targeted as the order-of-magnitude next step, particularly on Sanskrit ↔ English clinical-phrase mapping that base bge-m3 has minimal training exposure to.

---

## 2. Problem statement

Modern multilingual retrieval embeddings (bge-m3, multilingual-e5, paraphrase-XLM-R) are trained almost exclusively on web-scale English / European-language corpora with limited Sanskrit and Indic-classical-medicine coverage. Empirical evidence:

- We embedded the **full 20,734-verse Bṛhattrayī** under `paraphrase-multilingual-MiniLM-L12-v2` (the base model originally seeded) and ran a 27-question evaluable English-language clinical benchmark against the production hybrid pipeline (BM25 + dense + RRF).
- **MiniLM result: Hit@5 = 0%.** The smaller MiniLM-384 model has insufficient capacity for Sanskrit + IAST + Ayurvedic terminology.
- We then migrated to `BAAI/bge-m3` (1024-dim, multilingual-strong) and re-measured against the full 14,000-chunk Caraka + Aṣṭāṅga Hṛdaya corpus using pure dense retrieval (no BM25/RRF — measures the embedding model in isolation). **bge-m3 result: Hit@5 = 3.70%, MRR = 0.024, nDCG@10 = 0.036** (see `govt/baseline_full_corpus.json` for the full scorecard). The base bge-m3 model lifts the floor by ~4 absolute percentage points but is still far from clinically useful.
- The remaining ~36 percentage-point gap to the AyurBGE target (≥ 40% Hit@5) is the addressable problem this proposal solves: domain-specialised Sanskrit ↔ English ↔ IAST alignment, which no general-purpose multilingual embedding has been adequately exposed to.

This failure has direct downstream cost. Every AYUSH chatbot, decision-support tool, and educational application built on retrieval-augmented generation today is forced into one of three brittle compromises:
1. Query the LLM (Anthropic / OpenAI) without grounding, accepting hallucination risk against classical texts.
2. Hand-curate small QA datasets, accepting limited coverage.
3. Pay LLM-batch costs (~₹12,500 per 5,000 verses) to backfill English glosses of the Sanskrit corpus.

A purpose-built retrieval embedding for the Ayurvedic / Indic-medicine domain unblocks this for the whole ecosystem: any developer building on the SARIT corpus or its derivatives gets free, drop-in-replacement embeddings that work.

---

## 3. Proposed model: AyurBGE

| Property | Value |
|---|---|
| Base model | `BAAI/bge-m3` (open-source, MIT) |
| Architecture | XLM-RoBERTa-large backbone, 568 M parameters |
| Embedding dimension | 1024 |
| Context length | 8,192 tokens |
| Output license | Apache 2.0 (compatible with the MIT-licensed base) |
| Fine-tuning method | Contrastive — `MultipleNegativesRankingLoss` with hard-negative mining |
| Training framework | `sentence-transformers` v3.x on PyTorch 2.x |
| Hardware target | 1× A100-80GB or 1× H100-80GB |

### Why fine-tune bge-m3 (not train from scratch)

bge-m3 is already (a) MIT-licensed (commercial-friendly, redistribution-permissive), (b) multilingual-strong, (c) supports 8K context — sufficient to embed an entire chapter at once. Fine-tuning preserves general-purpose retrieval capability while specialising the latent space for Sanskrit ↔ IAST ↔ English alignment. Training a foundational embedding from scratch would require 10,000+ GPU-hours and isn't justified by the marginal quality gain.

### Why bge-m3, not a larger Llama/Mistral

For retrieval embedding, encoder-only XLM-R architectures (which bge-m3 is built on) are 10× more compute-efficient at inference than decoder-only LLMs and produce better dense vectors. A 7B Llama-distilled chat model is proposed as a **separate deliverable** below for Q&A use cases.

---

## 4. Training data — already assembled

We already hold the full training-data substrate, organised in a relational + KG layer at `backend/`:

### 4.1 Primary corpus (CC-BY-SA 3.0)

| Source | Verses | Status |
|---|---|---|
| Caraka Saṃhitā | 6,468 | Sanskrit + IAST ingested |
| Suśruta Saṃhitā | 6,834 | Sanskrit + IAST ingested |
| Aṣṭāṅga Hṛdaya | 7,432 | Sanskrit + IAST ingested |
| **Total** | **20,734 verses** | |

Each verse has chapter-context prefix at index time (Anthropic Contextual Retrieval pattern).

### 4.2 Structured KG (in-house, original)

| Layer | Rows |
|---|---|
| Dravyas | 171 (with Sanskrit + Devanagari + Latin binomial + English + Hindi) |
| Formulations | 206 (with full kalpana_type + ingredients + indications) |
| Vyādhi | 140 (with Sanskrit + English + Hindi + ICD-11 mapping where available) |
| Procedures | 73 |
| Parīkṣā parameters | 52 (with finding picklists) |
| Diagnostic patterns | 103 (rule-based, classical-source-attributed) |
| Modern evidence | 670 PMIDs across 89 dravyas (93 tier-A SR/MA, 78 tier-B RCT, 495 tier-C) |
| KG edges | 4,108 |

### 4.3 Training-pair generation (zero LLM cost)

From the layers above, we extract **~50,000 high-confidence (anchor, positive) pairs** without any LLM dependency:

1. **Cross-script verse pairs** (~20,000): `(Sanskrit-Devanagari, IAST)` for the same verse — trains script invariance.
2. **Verse ↔ chapter-context pairs** (~20,000): `(verse, chapter-prefix-context)` — exploits Contextual Retrieval enrichment already in our corpus.
3. **Concept-name pairs** (~3,000): `(English term, Sanskrit name)` from Dravya/Formulation/Vyādhi/Procedure rows where both fields exist (e.g. `("Ashwagandha", "Aśvagandhā")`, `("rheumatoid arthritis pattern", "Āmavāta")`).
4. **Diagnostic-pattern context pairs** (~500): `(pattern-description, target-vyadhi-name)` from DiagnosticPattern rows.
5. **Indication ↔ formulation pairs** (~1,500): from `Formulation.indications`.
6. **Hindi ↔ Sanskrit pairs** (~1,000): from rows where both `nama_sanskrit` and `hindi` are populated.

These pairs are produced deterministically by `scripts/build_finetune_pairs.py` (committed to the repo).

### 4.4 Optional Phase-2 pairs (LLM-assisted, deferred)

A separate ~₹12,500 LLM-batch pass over the 20,734 verses would add `(English query, Sanskrit verse)` direct-supervision pairs (the most informative supervision signal). This is budgeted as Phase 2 — *not* required for the Phase 1 fine-tune to be valuable.

---

## 5. Methodology

### 5.1 Training objective

Contrastive in-batch fine-tuning with `MultipleNegativesRankingLoss`:

```
L = -log[ exp(sim(a,p)/τ) / Σ_j exp(sim(a,p_j)/τ) ]
```

where `a` is the anchor, `p` the in-batch positive, `p_j` other in-batch examples used as negatives. Temperature `τ` = 0.05 (sentence-transformers default for bge-m3).

### 5.2 Hard-negative mining

After 1 warm-start epoch, mine 4 hard negatives per anchor using the partially-fine-tuned model itself:
- For each anchor, retrieve top-50 from the corpus
- Drop the true positive
- Drop verses sharing chapter or vyādhi (likely false-negatives)
- Sample 4 from the remaining top-50 as hard negatives

Continue training for 3-5 more epochs with the augmented (a, p, n_1...n_4) triplets.

### 5.3 Hyperparameters (initial)

| Parameter | Value |
|---|---|
| Learning rate | 2e-5 |
| Schedule | linear warmup 0.1, then cosine decay |
| Batch size | 64 (fits on A100-80GB at FP16) |
| Max sequence length | 1,024 tokens |
| Epochs | 1 warm-start + 5 with hard negatives |
| Mixed precision | bf16 |
| Optimizer | AdamW (β1=0.9, β2=0.999) |
| Weight decay | 0.01 |

### 5.4 Compute budget

| Stage | GPU-hours (A100-80GB) |
|---|---|
| Phase 1: warm-start + hard-negative mining + 5 epochs full fine-tune | ~50 |
| Ablations: ±cross-script pairs, ±KG pairs, ±chapter-context pairs (3 runs) | ~75 |
| Eval rerun across all 4 candidates | ~5 |
| Optional: 7B Llama-3.2 distilled chat model for Q&A use case | ~75 (separate, with stricter eval gating) |
| **Total Phase 1** | **~130 GPU-hours** |
| **Total with Llama variant** | **~205 GPU-hours** |

We request **150 GPU-hours** for Phase 1 with a 15% buffer.

---

## 6. Evaluation methodology

We have already shipped a reproducible eval harness at `backend/app/services/eval/{metrics,benchmark,runner}.py`:

- **Metrics:** Hit@k, Recall@k, MRR, nDCG@k, ALCE-style citation precision/recall, refusal correctness via heuristic markers
- **Benchmark:** `app/data/eval/seed_v1.yaml` — 30 hand-curated clinical questions across categories (Madhumeha, Sthaulya, Āmavāta, Cintā, Hṛd-roga, etc.), each with `expected_verses` IDs from the SARIT corpus
- **Comparison runner:** `scripts/compare_eval.py` (committed) loads two embedding models and produces a side-by-side scorecard

### 6.1 Pre-registered targets

Two reference points are reported — the production hybrid pipeline performance with the original base model, vs. the canonical isolated embedding-model measurement:

| Metric | MiniLM (full hybrid pipeline, 20K corpus) | **bge-m3 (pure dense, full 14K Caraka+Aṣṭāṅga corpus)** | AyurBGE Phase-1 target | Stretch (Phase-2) |
|---|---|---|---|---|
| Hit@5 | 0.000 | **0.0370** | ≥ 0.400 | ≥ 0.700 |
| Hit@10 | — | 0.0741 | ≥ 0.550 | ≥ 0.800 |
| MRR | 0.000 | 0.0238 | ≥ 0.300 | ≥ 0.500 |
| nDCG@10 | 0.000 | 0.0357 | ≥ 0.350 | ≥ 0.600 |

The **canonical baseline** is the bold column above — pure dense retrieval with `BAAI/bge-m3` on the full Caraka + Aṣṭāṅga Hṛdaya corpus. Suśruta Saṃhitā (6,834 verses) was mid-migration at measurement time and excluded; will be added once the corpus migration completes (capacity-limited on 16 GB MPS). The full scorecard JSON is committed at `govt/baseline_full_corpus.json` and reproducible via:

```
python -m scripts.compare_eval \
    --baseline BAAI/bge-m3 \
    --candidate AgeAyurveda/ayurbge-base-v1 \
    --json-out govt/post_finetune_scorecard.json
```

We pre-commit to publishing this number alongside Phase-1 results regardless of outcome.

We pre-commit to publishing the *full* scorecard regardless of outcome. If the Phase-1 fine-tune fails to meet target, we publish the failure analysis and refund-eligible compute.

### 6.2 Held-out evaluation

The `seed_v1.yaml` benchmark is publicly available. To prevent benchmark-overfitting, we will additionally hold out 50 untrained items (vyādhi → formulation → procedure triples) generated by independently sampling from the KG, and report numbers on both.

---

## 7. Open-source plan

**All deliverables Apache 2.0 / CC-BY-SA 3.0:**

1. **AyurBGE-base-v1** weights → Hugging Face: `AgeAyurveda/ayurbge-base-v1` (Apache 2.0; compatible with the MIT-licensed `BAAI/bge-m3` base)
2. **Training-pair dataset** → Hugging Face: `AgeAyurveda/ayurbge-training-pairs-v1` (CC-BY-SA 3.0, traceable to SARIT)
3. **Reproducible training script** → GitHub: `ageayurveda-companion/backend/scripts/finetune_bge.py` (Apache 2.0)
4. **Eval harness** → already at `backend/app/services/eval/` (Apache 2.0)
5. **Benchmark + scorecard** → JSON + Markdown report on first release
6. **Model card** following the Hugging Face standard, documenting biases, intended use, ethical considerations
7. **Dataset card** following Croissant metadata standard

This makes AyurBGE drop-in usable by any AYUSH developer:

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("AgeAyurveda/ayurbge-base-v1")
# embeds Sanskrit + IAST + English + Hindi at 1024-dim, 8K context
```

---

## 8. Data sovereignty + ethical considerations

- **Origin:** All training data is Indian-origin. Primary corpus (Bṛhattrayī) is CC-BY-SA 3.0 from SARIT (Society for the Advancement of Research on Indian Texts), an Indian scholarly project. KG is original work assembled from Bhāvaprakāśa Nighaṇṭu, Sahasrayogam, Bhaiṣajya Ratnāvali, and AYUSH-published Standard Treatment Guidelines.
- **Hosting during training:** All compute on Indian-soil GPU infrastructure (per IndiaAI Mission requirement).
- **Hosting post-training:** Hugging Face (mirror to indiaai.gov.in if requested).
- **No PII:** Training data contains zero personally-identifiable information.
- **Provenance tracking:** Every training pair carries `source_text + classical_source` provenance; ingestion scripts are version-controlled.
- **Bias acknowledgement:** The model card will explicitly note (a) classical Ayurvedic texts encode worldviews specific to ancient/medieval India that may not always align with modern values; (b) the model is a *retrieval* tool, not a clinical decision-maker; (c) all chatbot integrations must surface red-flag-for-referral guidance.
- **Misuse mitigation:** Model card will include a usage-restriction section: "AyurBGE retrieval output must not replace qualified medical advice. Downstream applications must surface referral red-flags for serious symptoms."

---

## 9. Team + capability

[Founder name], [credentials] — leads Age Ayurveda Companion (the rule-based chatbot already in production at ageayurveda.com), Nitya Naturals manufacturing arm of Baidyanath group lineage.

Software-engineering capability already demonstrated in the Companion project:
- 20,734-verse SARIT TEI XML ingestion pipeline (handles two TEI conventions + a literal `leve1` typo in the source)
- Hybrid BM25 + dense retrieval with RRF, citation-allowlist post-hoc validator (zero-LLM-cost hallucination guard)
- Multi-tenant FastAPI + SQLAlchemy backend with tenant-scoped rate limiting and cost telemetry
- 4,108-edge knowledge graph with diacritic-aware fuzzy resolution
- 214 passing tests, eval harness already shipped

External partnerships sought (letters of support requested):
- **CCRAS** (Central Council for Research in Ayurvedic Sciences) — domain validation
- **AIIA Delhi** (All India Institute of Ayurveda) — clinical evaluation cohort
- **University of Hyderabad / IIT-BHU Sanskrit dept** — Sanskrit linguistic validation

---

## 10. Timeline + milestones

| Week | Milestone |
|---|---|
| 1 | DPIIT registration, Pvt Ltd Indian-incorporation, Udyam, IndiaAI portal application, GPU allocation request |
| 2 | Training-pair generation (zero-cost, runs on CPU); upload pairs dataset to Hugging Face |
| 3-4 | Phase-1 baseline fine-tune (50 GPU-hours); upload `ayurbge-base-v1-rc1` |
| 5 | Hard-negative mining + Phase-1 final fine-tune (50 GPU-hours); upload `ayurbge-base-v1` |
| 6 | Phase-1 ablations (75 GPU-hours, parallelisable); model-card publication |
| 7 | Independent eval cohort run (CCRAS / AIIA Delhi if partnerships secured) |
| 8 | Public release + paper preprint on arXiv |

Phase-2 (Llama-distilled chat variant) gated on Phase-1 hitting the pre-registered Hit@5 ≥ 0.40 target.

---

## 11. Budget — GPU-hours requested

| Item | Hours | Type |
|---|---|---|
| Phase-1 fine-tune (1× warm-start + 5× full + ablations + eval) | 130 | Subsidised |
| Phase-2 contingency (Llama distillation) | 75 | Subsidised |
| Buffer (15%) | 30 | Subsidised |
| **Total IndiaAI Mission compute requested** | **235** | |

At ~₹150-200 per A100-hour at non-subsidised rates, the unsubsidised cost would be ~₹35,000-47,000. The IndiaAI subsidy is requested to make the fine-tune viable for a small AYUSH startup.

Cash co-investment from the founder: data preparation (zero LLM cost via the in-house generator), engineering time, hosting, dissemination — valued at ~₹2-3 lakh.

---

## 12. Annexures (linked from this proposal)

- **Annex A** — Eval harness reference: `backend/app/services/eval/`
- **Annex B** — Training-pair generator: `backend/scripts/build_finetune_pairs.py`
- **Annex C** — Training script: `backend/scripts/finetune_bge.py`
- **Annex D** — Side-by-side eval: `backend/scripts/compare_eval.py`
- **Annex E** — KG / corpus statistics CLI: `python -m scripts.build_kg --dry-run` produces edge-count stats
- **Annex F** — `govt/research-synthesis.md` — 12-agent research synthesis covering corpus sources, evaluation methodology, retrieval SOTA, and AYUSH ecosystem context
- **Annex G** — `govt/action-plan.md` — 90-day execution stack
- **Annex H** — `govt/ccras-letter.md` — draft AYUSH/CCRAS partnership letter
