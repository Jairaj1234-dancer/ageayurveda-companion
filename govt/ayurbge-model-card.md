---
language:
  - sa
  - en
  - hi
license: apache-2.0
library_name: sentence-transformers
tags:
  - sentence-transformers
  - feature-extraction
  - sentence-similarity
  - embeddings
  - retrieval
  - ayurveda
  - sanskrit
  - multilingual
  - indic
base_model: BAAI/bge-m3
datasets:
  - AgeAyurveda/ayurbge-training-pairs-v1
pipeline_tag: sentence-similarity
model-index:
  - name: ayurbge-base-v1
    results:
      - task:
          type: information-retrieval
          name: Information Retrieval
        dataset:
          type: AgeAyurveda/ayurveda-eval-seed-v1
          name: AgeAyurveda Seed-v1 Benchmark
          split: test
        metrics:
          - type: hit-at-5
            value: TBD  # filled post-training
          - type: mrr
            value: TBD
          - type: ndcg-at-10
            value: TBD
---

# AyurBGE-base-v1

> **Status: Pre-training. Numbers below are pre-registered targets, not measured results.** This card is published as part of the IndiaAI Mission compute proposal. Update with measured numbers once Phase-1 training completes.

AyurBGE is a domain-specialised retrieval embedding model for Ayurveda and classical Indian medicine, fine-tuned from `BAAI/bge-m3` on 44,360 (anchor, positive) pairs derived from the Bṛhattrayī (Caraka Saṃhitā, Suśruta Saṃhitā, Aṣṭāṅga Hṛdaya) and a structured AYUSH knowledge graph spanning 152 dravyas, 206 formulations, 140 vyādhi, 73 procedures, 670 PubMed-curated PMIDs, and 103 diagnostic patterns.

## Model details

| | |
|---|---|
| **Model name** | `AgeAyurveda/ayurbge-base-v1` |
| **Base model** | [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3) |
| **Architecture** | XLM-RoBERTa-large (encoder-only) |
| **Parameters** | ~568 M |
| **Embedding dimension** | 1024 |
| **Maximum sequence length** | 8,192 tokens |
| **Languages** | Sanskrit (Devanagari + IAST), English, Hindi |
| **License** | Apache 2.0 (compatible with the MIT-licensed `BAAI/bge-m3` base) |
| **Library** | `sentence-transformers` ≥ 3.0 |
| **Developed by** | Age Ayurveda Companion (Nitya Naturals) |
| **Training compute** | IndiaAI Mission GPU subsidy |
| **First release** | TBD |

## Intended use

### Primary intended uses

- **Retrieval-augmented generation (RAG) over classical Ayurvedic texts.** Embed query in any of {Sanskrit Devanagari, IAST, English, Hindi} and retrieve relevant verses or KG entities from the Bṛhattrayī, AYUSH formularies, or downstream applications.
- **Cross-language Sanskrit ↔ English retrieval** for Ayurvedic concepts (dravya names, vyādhi names, formulation names, indications, diagnostic patterns).
- **Semantic search** over Ayurvedic literature and scholarly Indian medical corpora.

### Out-of-scope uses

- **Clinical decision-making.** AyurBGE is a *retrieval* model. Output is text-passages, not diagnoses or treatments. Any clinical application must be supervised by a qualified Ayurvedic Vaidya (BAMS / MD-Ayurveda) and must surface red-flag-for-referral guidance.
- **Generation.** AyurBGE is encoder-only and does not generate text. Pair it with a separate LLM for RAG.
- **Non-Indic-medical domains.** The model is specialised; for general-purpose multilingual retrieval, use the base `BAAI/bge-m3`.
- **Diagnosing serious medical conditions** (cardiac events, sepsis, sannipāta-jvara, status epilepticus, acute abdomen, post-partum fever, glaucoma, etc.). All AYUSH-aligned downstream apps must enforce universal red-flag screening per AYUSH Standard Treatment Guidelines and refer to qualified allopathic care.

### Recommendations

For RAG applications, combine AyurBGE with:
- A citation-allowlist post-hoc validator to suppress hallucinated source attributions
- A red-flag screening layer that detects emergency presentations and prepends a referral notice
- A language-detection step to normalize the query encoding (Devanagari, IAST, English, Hindi)

## Training data

The model is fine-tuned on **44,360 (anchor, positive) pairs**, organised in seven sub-sources:

| Source | Pairs | Description |
|---|---|---|
| Cross-script verse pairs | 20,734 | (Sanskrit Devanagari, IAST) for the same verse — script invariance |
| Verse ↔ chapter-context pairs | 20,734 | (verse, chapter-context-prefix) — within-text coherence |
| Indication ↔ formulation | 881 | (vyādhi indication, formulation name) |
| Rūpa ↔ vyādhi | 337 | (clinical sign, disease name) |
| Formulation name pairs (en/hi) | 211 | (English/Hindi name, IAST name) |
| Dravya name pairs | 681 | (English/Hindi/Devanagari/Latin, Sanskrit IAST) |
| Vyādhi name pairs | 242 | (English/Hindi name, Sanskrit IAST) |
| Procedure name pairs | 219 | (English/Hindi name, Sanskrit IAST) |
| Diagnostic-pattern → target | 115 | (pattern description, target vyādhi name) |

**All pairs are produced deterministically by `scripts/build_finetune_pairs.py`** with no LLM dependency. The pair-extraction script is open-source (Apache 2.0) and reproducible from the source corpus + structured KG.

### Source corpus

The primary corpus is the **Bṛhattrayī (Three Greats) of classical Ayurveda**:

| Source | Verses | Composer (trad.) | Approx. era |
|---|---|---|---|
| Caraka Saṃhitā | 6,468 | Agniveśa, redacted by Caraka and Dṛḍhabala | ~2nd c. BCE – 4th c. CE |
| Suśruta Saṃhitā | 6,834 | Suśruta | ~6th c. BCE – 7th c. CE |
| Aṣṭāṅga Hṛdaya | 7,432 | Vāgbhaṭa | ~7th c. CE |
| **Total** | **20,734** | | |

Source XML obtained from the [SARIT (Society for the Advancement of Research on Indian Texts)](https://sarit.indology.info/) project, licensed CC-BY-SA 3.0. Each verse has Sanskrit (Devanagari), IAST transliteration, and chapter-context metadata.

### Structured AYUSH knowledge graph

In-house curated relational + graph layer (committed to the source repo):

| Layer | Rows | License |
|---|---|---|
| Dravya (substance) | 152 | Apache 2.0 |
| Formulation | 206 | Apache 2.0 |
| Vyādhi (disease) | 140 | Apache 2.0 |
| Procedure | 73 | Apache 2.0 |
| Parīkṣā parameter | 52 | Apache 2.0 |
| Diagnostic pattern | 103 | Apache 2.0 |
| Modern evidence (PubMed) | 670 | Public domain (US gov't) |
| Knowledge graph edges | ~4,100 | Apache 2.0 |

Each row is grounded in classical sources (Bhāvaprakāśa Nighaṇṭu, Sahasrayogam, Bhaiṣajya Ratnāvali, AYUSH STG) with `classical_source` attribution per row. All rows are marked `review_tier: llm-only` pending Vaidya validation.

## Training procedure

### Preprocessing

- All text segments are normalized to NFKD + lowercase for matching, but encoded as raw input to bge-m3's tokenizer (which preserves Devanagari + diacritics natively).
- Maximum input length capped at 1,024 tokens for training (bge-m3 supports 8,192; we use a smaller cap to fit batch_size=64 on A100-80GB).

### Training hyperparameters

| Parameter | Value |
|---|---|
| Loss | `MultipleNegativesRankingLoss` (in-batch negatives) + hard-negative mining at epoch 2 |
| Optimizer | AdamW (β₁=0.9, β₂=0.999) |
| Learning rate | 2e-5 |
| Schedule | Linear warmup 10%, then cosine decay |
| Weight decay | 0.01 |
| Batch size | 64 |
| Mixed precision | bf16 |
| Epochs | 1 warm-start + 5 with hard negatives |
| Hard negatives | k=4 per anchor, mined from top-50 most-similar (excluding true positive and same-chapter) |
| Temperature | 0.05 |

### Hardware

| Resource | Spec |
|---|---|
| Phase-1 training GPU | 1× A100-80GB (or 1× H100-80GB) |
| Approximate compute | 50 GPU-hours (warm-start + 5 epochs) |
| Phase-1 ablations | 75 additional GPU-hours |
| Total Phase-1 budget | 130 GPU-hours |

Training will be conducted on Indian-soil GPU infrastructure (IndiaAI Mission compute allocation) per data-sovereignty requirements.

## Evaluation

### Benchmark

`AgeAyurveda/ayurveda-eval-seed-v1` — 30 hand-curated clinical questions across categories (Madhumeha, Sthaulya, Āmavāta, Cintā, Hṛd-roga, etc.), 27 of which are evaluable retrieval items (the remaining 3 are safety-refusal items evaluated separately when generation is added).

Each item has `question_en` and `expected_verses` IDs traceable to the source corpus. Scoring is by Hit@5, Hit@10, MRR, and nDCG@10 using the citation methodology of [ALCE (Gao et al. 2023)](https://arxiv.org/abs/2305.14627).

### Pre-registered targets

| Metric | Baseline (`BAAI/bge-m3`, full 14K corpus, pure dense) | AyurBGE Phase-1 target | Stretch (Phase-2) |
|---|---|---|---|
| Hit@5 | **0.0370** | ≥ 0.400 | ≥ 0.700 |
| Hit@10 | 0.0741 | ≥ 0.550 | ≥ 0.800 |
| MRR | 0.0238 | ≥ 0.300 | ≥ 0.500 |
| nDCG@10 | 0.0357 | ≥ 0.350 | ≥ 0.600 |

The baseline scorecard JSON is available at [`govt/baseline_full_corpus.json`](https://github.com/Jairaj1234-dancer/ageayurveda-companion/blob/main/govt/baseline_full_corpus.json). The reproducible eval script is `scripts/compare_eval.py` in the source repo.

We pre-commit to publishing the full Phase-1 scorecard regardless of outcome, including failure analysis and root-cause if targets are missed.

### Held-out evaluation cohort

To prevent benchmark-overfitting, an additional 50 items will be sampled from the KG (vyādhi → formulation → procedure triples) and held out from any training-pair generation. Numbers will be reported on both `seed-v1` and the held-out cohort.

## Limitations

- **Training-data domain narrowness:** The pair set is limited to Ayurveda and adjacent Indic medicine. Out-of-domain queries may return less-relevant results than the base bge-m3.
- **Sanskrit-English supervision is weak:** Most pairs are cross-script (Sanskrit-Devanagari ↔ Sanskrit-IAST) or KG-derived. Direct (English query, Sanskrit verse) supervision is limited to the ~3,000 KG concept-name pairs. A Phase-2 batch generating English glosses for the 20,734 verses (~₹12,500 LLM cost) would substantially improve English-query retrieval.
- **Suśruta Saṃhitā coverage:** The training data uses verses from all three samhitas, but the baseline eval at proposal time was limited to the 14,000 verses of Caraka + Aṣṭāṅga Hṛdaya (the local laptop bge-m3 re-embed OOM'd on MPS at ~14K chunks; capacity-bound, not data-bound). Suśruta will be included in the production eval.
- **Variant-spelling residue:** Some classical-text spellings still resolve to multiple distinct entities (e.g. "Vāsā" vs "Vāsaka"). The training-pair extractor is diacritic-aware, but a small percentage of name variants may land in different anchor/positive spaces.

## Biases

- **Worldview encoded in classical Ayurvedic texts** (~2nd c. BCE – 7th c. CE) reflects ancient/medieval Indian ideas that may not always align with modern values regarding gender, caste, or social roles. The model surfaces text *as-is*; downstream applications should mediate. The KG explicitly excludes any prescriptive social hierarchy.
- **English mappings are translation artifacts.** Sanskrit medical terms have multiple acceptable English glosses (`Madhumeha` ≈ "diabetes mellitus type 2 analogue" vs the literal "honey-urine"). The training pairs use the curatorially-preferred gloss.
- **Modern-evidence bias toward English-language clinical research.** PubMed indexing is English-dominant; Ayurvedic clinical research published only in Hindi or regional Indian languages may be under-represented.

## Ethical considerations

- **No PII in training data.** All training data is published-text or original KG data with classical-source attribution. Personally identifiable data is not included.
- **Open-source commitment.** Weights, training pairs, and evaluation scripts are all permissively licensed. The model can be self-hosted by any AYUSH developer.
- **Misuse mitigation.** This card explicitly warns against clinical decision-making based on retrieval alone. Downstream apps must implement safeguards.
- **Patient safety.** Any clinical application built on AyurBGE must implement the universal red-flag-for-referral screen (per AYUSH STG). The KG includes 100+ explicit red-flag indicators across vyādhi entries.

## Citation

If you use AyurBGE in research, please cite:

```bibtex
@misc{ayurbge2026,
  author = {Sharma, Jairaj and {Age Ayurveda Companion Team}},
  title  = {AyurBGE: a multilingual retrieval embedding for classical Ayurveda},
  year   = {2026},
  publisher = {Hugging Face},
  url    = {https://huggingface.co/AgeAyurveda/ayurbge-base-v1}
}
```

And cite the base model and source corpus:

```bibtex
@misc{bge-m3-2024,
  title  = {BGE M3-Embedding},
  author = {Chen, Jianlv and others},
  year   = {2024},
  url    = {https://huggingface.co/BAAI/bge-m3}
}

@misc{sarit-2017,
  title  = {SARIT: Search and Retrieval of Indic Texts},
  url    = {https://sarit.indology.info/},
  note   = {CC-BY-SA 3.0; accessed via the AgeAyurveda Companion ingest pipeline}
}
```

## Contact

- Project: https://github.com/Jairaj1234-dancer/ageayurveda-companion
- HuggingFace: https://huggingface.co/AgeAyurveda
- Issues: https://github.com/Jairaj1234-dancer/ageayurveda-companion/issues

## Usage example

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("AgeAyurveda/ayurbge-base-v1")

queries = [
    "joint pain with morning stiffness",   # likely Āmavāta
    "frequent urination with sweet urine",  # likely Madhumeha
    "अश्वगन्धा",                              # Sanskrit query
    "ashwagandha for stress",
]

embeddings = model.encode(queries, normalize_embeddings=True)
# shape: (4, 1024)

# Use with sentence-transformers .similarity, FAISS, Qdrant, pgvector, etc.
```

For RAG over the full Ayurvedic corpus, see the production retrieval pipeline at the source repository.
