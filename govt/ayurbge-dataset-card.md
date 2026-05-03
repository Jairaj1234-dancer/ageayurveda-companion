---
language:
  - sa
  - en
  - hi
license: cc-by-sa-3.0
size_categories:
  - 10K<n<100K
task_categories:
  - sentence-similarity
  - feature-extraction
task_ids:
  - text-retrieval
  - cross-lingual-retrieval
pretty_name: AyurBGE Training Pairs v1
tags:
  - ayurveda
  - sanskrit
  - indic
  - multilingual
  - retrieval
  - contrastive
configs:
  - config_name: default
    data_files: pairs_v1.jsonl
---

# AyurBGE Training Pairs v1

A deterministically-generated corpus of **44,360 (anchor, positive) training pairs** for fine-tuning multilingual retrieval embeddings on the Ayurveda / classical Indian medicine domain. Used to train [`AgeAyurveda/ayurbge-base-v1`](https://huggingface.co/AgeAyurveda/ayurbge-base-v1).

## Dataset summary

This dataset is purpose-built for contrastive fine-tuning (e.g. `MultipleNegativesRankingLoss`) of sentence-transformer models on the Sanskrit–English–Hindi medical-text retrieval task. Pairs are extracted from two complementary substrates:

1. **The Bṛhattrayī classical corpus** — 20,734 verses across the Caraka Saṃhitā, Suśruta Saṃhitā, and Aṣṭāṅga Hṛdaya, sourced from the [SARIT](https://sarit.indology.info/) TEI XML archive (CC-BY-SA 3.0).
2. **A structured AYUSH knowledge graph** — 152 dravyas, 206 formulations, 140 vyādhi, 73 procedures, 670 PubMed-curated PMIDs, and 103 diagnostic patterns, all classical-source-attributed.

Pair extraction is fully deterministic — produced by the open-source script `scripts/build_finetune_pairs.py` (Apache 2.0). No LLM was used in pair generation. This makes the dataset reproducible end-to-end from the source corpus + KG.

## Languages

- **Sanskrit** (Devanagari script and IAST transliteration)
- **English** (clinical glosses, modern terminology)
- **Hindi** (medical terminology, regional names)
- **Latin** (binomial nomenclature for botanicals)

## Dataset structure

### Format

JSON Lines (`.jsonl`) — one pair per line. UTF-8 encoded.

### Fields

| Field | Type | Description |
|---|---|---|
| `anchor` | string | The query / source-language text |
| `positive` | string | The semantically-paired target |
| `source` | string | Sub-source category (one of: `cross-script-verse`, `verse-context`, `dravya-en-sa`, `dravya-latin-sa`, `dravya-hi-sa`, `dravya-deva-iast`, `formulation-en-iast`, `formulation-hi-iast`, `indication-formulation`, `primary-ind-formulation`, `vyadhi-en-sa`, `vyadhi-hi-sa`, `rupa-vyadhi`, `procedure-en-iast`, `procedure-hi-iast`, `primary-ind-procedure`, `pattern-target`) |
| `lang_a` | string | Language of the anchor (one of: `sa-deva`, `sa-iast`, `en`, `hi`, `la`, `mixed`, `en-context`) |
| `lang_b` | string | Language of the positive |

### Splits

| Split | # rows | Notes |
|---|---|---|
| `train` | 44,360 | Single split; held-out eval is provided separately as `seed_v1.yaml` benchmark |

### Pair distribution by sub-source

| Sub-source | Count | Description |
|---|---|---|
| `cross-script-verse` | 20,734 | Sanskrit-Devanagari ↔ IAST for the same verse |
| `verse-context` | 20,734 | Verse ↔ chapter-context-prefix |
| `indication-formulation` | 881 | Vyādhi indication ↔ formulation IAST name |
| `rupa-vyadhi` | 337 | Clinical sign ↔ vyādhi Sanskrit name |
| `dravya-latin-sa` | 171 | Latin binomial ↔ Sanskrit IAST name |
| `dravya-hi-sa` | 171 | Hindi name ↔ Sanskrit IAST name |
| `dravya-deva-iast` | 171 | Sanskrit Devanagari ↔ Sanskrit IAST name |
| `dravya-en-sa` | 168 | English name ↔ Sanskrit IAST name |
| `formulation-en-iast` | 206 | English name ↔ formulation IAST name |
| `primary-ind-formulation` | 206 | Primary indication (English) ↔ formulation IAST name |
| `formulation-hi-iast` | 5 | Hindi name ↔ formulation IAST name |
| `vyadhi-en-sa` | 140 | English vyādhi name ↔ Sanskrit name |
| `vyadhi-hi-sa` | 102 | Hindi name ↔ Sanskrit name |
| `pattern-target` | 115 | Diagnostic-pattern description ↔ target vyādhi |
| `procedure-en-iast` | 73 | English procedure name ↔ IAST name |
| `procedure-hi-iast` | 73 | Hindi name ↔ IAST name |
| `primary-ind-procedure` | 73 | Primary indication (English) ↔ procedure IAST name |
| **Total** | **44,360** | |

### Data sample

```jsonl
{"anchor": "रागादि-रोगान् सततानुषक्तान् अ-शेष-काय-प्रसृतान् अ-शेषान् |", "positive": "rāgādi-rogān satatānuṣaktān a-śeṣa-kāya-prasṛtān a-śeṣān |", "source": "cross-script-verse", "lang_a": "sa-deva", "lang_b": "sa-iast"}
{"anchor": "Ashwagandha", "positive": "Aśvagandhā", "source": "dravya-en-sa", "lang_a": "en", "lang_b": "sa-iast"}
{"anchor": "rheumatoid arthritis pattern with active āma", "positive": "Āmavāta", "source": "rupa-vyadhi", "lang_a": "en", "lang_b": "sa-iast"}
{"anchor": "anxiety with insomnia and low sattva", "positive": "Cintā", "source": "pattern-target", "lang_a": "en", "lang_b": "sa-iast"}
```

## Source data

### Primary corpus

The Bṛhattrayī (Three Greats) of classical Ayurveda:

| Source | Verses | Author (trad.) | Era |
|---|---|---|---|
| Caraka Saṃhitā | 6,468 | Agniveśa, redacted by Caraka and Dṛḍhabala | ~2nd c. BCE – 4th c. CE |
| Suśruta Saṃhitā | 6,834 | Suśruta | ~6th c. BCE – 7th c. CE |
| Aṣṭāṅga Hṛdaya | 7,432 | Vāgbhaṭa | ~7th c. CE |

Source XML obtained from the [SARIT](https://sarit.indology.info/) project archive. Original digitisation is collaborative work by SARIT contributors; CC-BY-SA 3.0.

### Structured knowledge-graph layers

Original work, compiled from:
- **Bhāvaprakāśa Nighaṇṭu** (16th c. CE — Bhāvamiśra, materia medica reference)
- **Sahasrayogam** (Kerala tradition, formulations and procedures)
- **Bhaiṣajya Ratnāvali** (~17th c. CE — Govindadasa, formulations)
- **Rasa-tarangiṇī** (~19th c. CE — Sadananda Sharma, mineral preparations)
- **AYUSH Standard Treatment Guidelines** (Government of India)
- **API (Ayurvedic Pharmacopoeia of India), Vol I-III**
- **NAMASTE Ayurveda terminology codebook** (where ICD-11 TM2 mappings exist)

PubMed PMIDs were retrieved via NCBI E-utilities `esearch` + `efetch` with the query `<latin-binomial>[Title/Abstract] AND humans[Filter] AND (Randomized Controlled Trial[ptyp] OR Systematic Review[ptyp] OR Meta-Analysis[ptyp] OR Clinical Trial[ptyp] OR Review[ptyp])`, sorted by relevance. Each PMID is tiered (A=SR/MA, B=RCT, C=clinical/observational/review, D=other).

## Curation rationale

Generic multilingual retrieval embeddings (e.g. `paraphrase-multilingual-MiniLM-L12-v2`, `BAAI/bge-m3`) score 0–4% Hit@5 on Ayurvedic clinical questions due to insufficient Sanskrit + IAST + Ayurvedic-terminology training exposure. This dataset is the supervision signal needed to specialise a multilingual encoder for the AYUSH domain.

The pair-extraction methodology favours **explainable, classical-source-attributed signal** over LLM-generated synthetic data. Every pair traces to either:
- An identical verse in two different scripts (cross-script-verse)
- A verse and its containing-chapter context (verse-context)
- A KG row where two languages name the same entity (concept-name pairs)
- A diagnostic pattern's hand-curated description and target (pattern-target)

## Personal and sensitive information

**None.** All training data is either:
- Published classical-text material (>1,000 years old, no living-person attribution)
- Original KG data with classical-source citations (no patient data, no PII)
- Public-domain PubMed metadata (titles, authors, abstracts of published research papers — no patient data)

## Licensing

| Component | License | Rationale |
|---|---|---|
| `pairs_v1.jsonl` | **CC-BY-SA 3.0** | Inherited from SARIT corpus |
| Pair-extraction script | Apache 2.0 | Original code (in source repo) |
| Source SARIT corpus | CC-BY-SA 3.0 | Inherited |
| Structured KG | Apache 2.0 | Original work; data layer of `ageayurveda-companion` |
| PubMed metadata | Public domain | US government work |

CC-BY-SA 3.0 imposes share-alike on derivatives that include any portion of the SARIT-derived pairs. Models trained from this data may be released under any license compatible with CC-BY-SA 3.0 (we use Apache 2.0 for `AyurBGE-base-v1` weights, which is permissible since model weights are not direct copies of CC-BY-SA text).

## Citation

```bibtex
@dataset{ayurbge-pairs-v1-2026,
  author    = {Sharma, Jairaj and {Age Ayurveda Companion Team}},
  title     = {AyurBGE Training Pairs v1},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/AgeAyurveda/ayurbge-training-pairs-v1}
}
```

Cite the source SARIT corpus:

```bibtex
@misc{sarit-2017,
  title = {SARIT: Search and Retrieval of Indic Texts},
  url   = {https://sarit.indology.info/},
  note  = {CC-BY-SA 3.0; classical Ayurvedic samhita TEI XML}
}
```

## Limitations and biases

- **Domain narrowness.** Pairs cover Ayurveda and adjacent Indic medicine. Models trained only on this dataset will be sub-optimal for general-purpose retrieval; warm-start from a multilingual-strong base model (e.g. `BAAI/bge-m3`) is recommended.
- **Direct (English query, Sanskrit verse) supervision is sparse.** Only ~2,900 of 44,360 pairs are explicitly cross-language between Sanskrit and English/Hindi. The majority of pairs are intra-language (cross-script verse pairs and verse-context pairs). A Phase-2 batch generating English glosses for the 20,734 source verses (~₹12,500 LLM cost) would materially improve cross-language signal — pre-registered as Phase-2 of the AyurBGE roadmap.
- **Worldview embedded in classical Ayurvedic texts** reflects ancient/medieval Indian ideas. While the KG explicitly excludes prescriptive social hierarchy, the source verses are reproduced as-is for retrieval purposes. Downstream applications should mediate.
- **Suśruta Saṃhitā is included in training but was not in the proposal-time baseline measurement** (corpus-migration capacity-bound at proposal write time). Phase-1 training will include all 20,734 verses.
- **PMID metadata is not training-paired** in v1 — the modern-evidence layer is included as KG context but not yet as embedding-pair supervision. A Phase-3 enrichment could add (RCT abstract, target dravya / vyādhi) supervision.

## Reproducibility

The pairs file can be regenerated end-to-end:

```bash
git clone https://github.com/Jairaj1234-dancer/ageayurveda-companion
cd ageayurveda-companion/backend
pip install -r requirements.txt

# Ingest the source corpus from SARIT TEI XML
python -m scripts.ingest_sarit
python -m scripts.ingest_dravyas
python -m scripts.ingest_formulations
python -m scripts.ingest_vyadhi
python -m scripts.ingest_procedures
python -m scripts.ingest_pariksha

# Generate the pair file
python -m scripts.build_finetune_pairs
# Output: app/data/finetune/pairs_v1.jsonl
```

The script is deterministic; running it twice on the same DB state produces identical output (modulo dict ordering).

## Contact

- Project: https://github.com/Jairaj1234-dancer/ageayurveda-companion
- Issues: https://github.com/Jairaj1234-dancer/ageayurveda-companion/issues
- HuggingFace dataset: https://huggingface.co/datasets/AgeAyurveda/ayurbge-training-pairs-v1
