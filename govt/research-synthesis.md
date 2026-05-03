# Companion v1 → Research-Grade Platform: Consolidated Research Synthesis

_Output of 8 parallel research agents · 2026-04 · founder's reference document_

This file is the single canonical source of the research. Engineering roadmap is downstream of this. Do not delete.

---

## 1 · Sanskrit primary-source corpus

**Single-best source: SARIT TEI XML on GitHub** — https://github.com/sarit/SARIT-corpus, **CC-BY-SA 3.0**.

| Text | SARIT file | Verses | Quality |
|---|---|---|---|
| Caraka Saṃhitā | `carakasamhita.xml` (Yādavji Trikamji 1941 + Cakrapāṇi commentary, Hellwig/SARIT TEI) | ~9,000 | High — gold standard |
| Suśruta Saṃhitā | `susrutasamhita.xml` (Yamashita & Muroya from Y.T. Ācārya 1931/38) | ~7,000 | High — complete mūla |
| Aṣṭāṅga Hṛdaya | `astangahrdayasamhita.xml` (Das & Emmerick critical) | ~7,500 | **Highest structural quality** of Bṛhattrayī, pre-canonicalised verse IDs |
| Aṣṭāṅga Saṅgraha | `astangasangraha.xml` | — | Less proofed, spot-check |
| Bhāvaprakāśa Pūrvakhaṇḍa | GRETIL TEI `sa_bhAvamizra-bhAvaprakAza.htm` | partial | Madhya/Uttara not encoded |
| Mādhava Nidāna | None clean. Archive.org 1932 PDF only. | ~5,000 | Manual OCR project |
| Sahasrayoga / Yogaratnākara | None clean. Defer or commission. | — | — |

**Tooling:** `vidyut-lipi` (Rust crate, Python via `vidyut` package) is the production tool for IAST↔Devanagari↔SLP1 transliteration. Used by Ambuda. Install: `pip install vidyut`. Skip `indic-transliteration` (older, has IAST edge-case bugs).

**Schema (canonical JSONL per verse):**
```
text_id, sthana, chapter, verse_num, devanagari, iast, slp1, source_edition, license, commentary_refs[]
```

**Pipeline:** Parse SARIT TEI with lxml → walk `<div type="sthana">` → `<div type="chapter">` → `<lg>`/`<l>` → emit verse rows. Where `<lg>` missing in Suśruta, fall back to verse-number regex `||\s*\d+\s*||`.

**Minimum viable ingestion plan (1 week):** Pull 3 SARIT files → write 150-LOC TEI→JSONL parser → add Devanagari+SLP1 via vidyut → spot-check 30 verses against Trikamji print → load into `corpus_chunks`. Yields ~15,000-verse corpus. Aṣṭāṅga Hṛdaya alone yields ~7,500.

---

## 2 · English translations + licensing

**Punchline:** 4 of the 5 priority texts have NO complete public-domain English translation. K.R. Srikantha Murthy (Krishnadas Academy / Chaukhamba) is the dominant rights holder.

### Per-text translation map

| Text | Best scholarly | PD alternative | Strategy |
|---|---|---|---|
| Caraka | Sharma & Dash 7-vol (Chaukhamba, ©) or Priyavrat Sharma 4-vol | **A.C. Kaviratna 1890–1911 (Calcutta) — PD globally**, partial (Sūtra + part Nidāna) | Ship on PD Kaviratna where it covers; license Sharma-Dash for gaps |
| Suśruta | P.V. Sharma / K.R. Srikantha Murthy / G.D. Singhal | **K.K. Bhishagratna 1907–1916, 3 vols — PD globally, complete** | Ship on Bhishagratna |
| Aṣṭāṅga Hṛdaya | Murthy 3-vol (Krishnadas Academy ©) | None | License Murthy or commission clean-room |
| Bhāvaprakāśa | Murthy 2-vol (Krishnadas Academy ©) | None | License Murthy or commission |
| Mādhava Nidāna | Murthy (Chaukhamba ©) | None complete; Jolly 1901 fragments | License Murthy or commission |

### Licensing pathways

1. **Direct publisher:** Chaukhamba (publications@chaukhamba.com), Krishnadas Academy. Anecdotal INR 3-10L per title — **flag, unverified**. 6-12 months.
2. **CCRAS MoU:** likely no fee under research MoU; usage may be restricted to non-commercial. **Check whether it covers commercial chatbot**. 3-6 months.
3. **Clean-room commission** (vaidya-Sanskritists retranslate): INR 25-60L over 18-24 months. **You own the copyright**. Defensible.
4. **PD + modernise:** Bhishagratna + Kaviratna as base, light editorial pass. INR 5-10L. 3-6 months.

### Interim path (ship now, legally clean)

- Keep original paraphrases as primary user-facing English (your copyright).
- Pair each verse with Devanagari + IAST Sanskrit (Sanskrit text itself is PD; SARIT/GRETIL).
- Cite the print edition (Sharma-Dash, Murthy) so motivated users buy the book — citation is fair use.
- Where PD translation exists (Bhishagratna for Suśruta, Kaviratna for Caraka Sūtra), surface as "scholarly English (1907)" toggle. archive.org URLs are stable.

**Translator inconsistency materially affects retrieval:** *vāta* as "wind" / "Vata" / "vāyu" creates 4 different token clusters. Recommended chunk shape: `{sanskrit_devanagari, sanskrit_iast, english_gloss, key_terms_preserved}`. Multilingual embedding models (BGE-M3) handle IAST best.

### Quarter recommendation

1. **Weeks 1-4:** Original paraphrases + Sanskrit + IAST + PD toggle for Suśruta + Caraka. Zero legal risk.
2. **Weeks 4-8:** Open licensing correspondence with Chaukhamba + Krishnadas. Budget INR 15-30L contingency.
3. **Weeks 6-12:** CCRAS MoU explicitly scoping (i) access to translations and (ii) right to use commercially.
4. **Q2:** If both above stall, commission clean-room for AH + Bhāvaprakāśa + Mādhava only.

---

## 3 · Evaluation methodology + Ayurveda benchmarks

**Stack to standardise on: RAGAS (offline metrics) + DeepEval (CI) + Phoenix (production traces).**
- All three accept `(query, contexts, answer, ground_truth)` tuples — no retriever lock-in.
- Anthropic Claude works as judge via langchain_anthropic.
- DeepEval is pytest-native — fits existing test suite.

### Citation-specific metrics

- **ALCE benchmark methodology** (Liu et al. 2023, https://arxiv.org/abs/2305.14627, https://github.com/princeton-nlp/ALCE): citation_recall (does each statement have a supporting citation?) + citation_precision (does each citation actually support its statement?). Implemented via NLI entailment. **Adopt verbatim.**
- **ExpertQA** (Malaviya 2024, https://arxiv.org/abs/2309.07852): expert-curated QA with attribution; methodology directly transferable to pandit-curated Ayurveda Q&A.
- **AttributedQA** (Bohnet et al., https://arxiv.org/abs/2212.08037): AIS rubric — adopt for Sanskrit verse citations.

### Retrieval metrics

Recall@k, MRR@10, nDCG@10, **Hit@5** (most operationally meaningful — "did the right shloka appear in the top 5?"). Cross-lingual mirrors: Mr.TyDi, MIRACL, XOR-Retrieve. **None include Sanskrit** — we have to build our own probe set.

### Existing Ayurveda QA benchmarks

**Honest answer: none verified to exist.** AyurChat / AyurDC / AyurQA / Ayur-VQA names don't match anything findable. CCRAS has digitised corpora (NAMASTE) but no LLM QA benchmark. **NHA + IIT-Kanpur BODH (March 2026)** flagged as unverified — confirm directly with NHA, don't treat as established.

### Building a gold benchmark

- Annotators: 3-5 BAMS physicians + 2 Sanskrit pandits per question. Sources: CCRAS, BHU Ayurveda faculty, Jamnagar ITRA, Kerala Ayurveda Vaidya Sabha.
- Inter-annotator agreement: Cohen's κ ≥ 0.6 (substantial) is publishable threshold; aim for 0.7+.
- Taxonomy for 500 items: 25% diagnostic, 30% therapeutic, 15% formulation, 15% preventive, 10% philosophical, 5% safety.
- 100 items = development signal. 500-1000 = stable metrics with ±3% CI.

### 4-week proposal

1. **Standardise:** RAGAS + DeepEval + Phoenix.
2. **100-question seed (cheap):** 60 from textbook study questions in Charaka/Sushruta/AH translations + 20 CCRAS patient FAQs + 20 adversarial. Each item: `{question_en, question_hi, expected_verses[], expected_claims[], difficulty, category}`. Single BAMS reviewer. ~₹15-25k for reviewer time.
3. **Metrics on every CI run:** Hit@5, MRR@10, nDCG@10, ALCE citation precision/recall, RAGAS faithfulness, RAGAS answer_relevancy, refusal-correctness on a 10-item should-refuse set.
4. **Path to 500:** Months 2-4. Recruit pandit reviewers via CCRAS/BHU. Double-annotate. Publish κ. Release on HuggingFace under CC-BY-SA. arXiv preprint citing ALCE + ExpertQA methodology. Budget ₹2.5-4L for honoraria.

---

## 4 · State-of-the-art retrieval

### Engineering roadmap (priority order, expected lifts)

| # | Ship | Effort | Expected lift |
|---|---|---|---|
| 1 | **Citation allowlist + post-hoc validator** (regenerate on invalid cite) | 1-2 d | Hallucination ↓ majority. Highest ROI. **Ship first.** |
| 2 | **Chapter-context prefix in indexing** ("From Caraka Sūtra ch.5 (eating in proper measure): …") + reindex | 0.5 d | recall@6 +5-15%. Trivial. |
| 3 | **Swap embedding to bge-m3** (dense + sparse). Replace BM25 with bge-m3 sparse mode. | 2-3 d | recall@10 +10-20% Hindi/EN. **Single biggest model upgrade.** |
| 4 | **Add bge-reranker-v2-m3** as stage-2 (retrieve 40 → rerank 6) | 1-2 d | nDCG@6 +15-25%. Critical past ~1k verses. |
| 5 | **Index-time query-paraphrase expansion** (Anthropic Contextual Retrieval pattern — generate 3-5 hypothetical Qs per verse, embed alongside) | 2-3 d | recall +20-35%. |

### Detailed findings

- **bge-m3** (https://huggingface.co/BAAI/bge-m3): single 568M model that does dense + sparse + multi-vector ColBERT-style in one. 8K context. 100+ languages incl. Hindi/Sanskrit-adjacent. **Highest-impact embedding swap.**
- **bge-reranker-v2-m3** (https://huggingface.co/BAAI/bge-reranker-v2-m3): multilingual cross-encoder, 568M. Best free option for Indic/Sanskrit. Lift +15-25% nDCG@6.
- **Cohere Rerank 3.5** ($2/1k searches): API, ~100ms. Use only if latency-bound.
- **HyDE** (https://arxiv.org/abs/2212.10496): worth it for colloquial-EN→Sanskrit gap. +3-8% recall@10. Stacks with reranker.
- **Multi-query / RAG-Fusion**: 3-5 paraphrases + RRF. +5-10% recall.
- **Citation allowlist**: enforce that every citation the model emits is in the retrieved set. Cheap, deterministic. **The single best hallucination guard.**
- **Self-RAG / FActScore / FAVA** (https://arxiv.org/abs/2401.06855): atomic claim → NLI against citation. Use offline for eval; too slow online.
- **GraphRAG** (https://arxiv.org/abs/2404.16130, https://github.com/microsoft/graphrag): wins on global sense-making, loses on specific lookup. Defer until KG built.
- **Vector DB at our scale**: pgvector through ~1M vectors with HNSW is fine. **Qdrant** wins on payload filtering + multi-tenancy + sparse vectors (matters for bge-m3). Migrate when payload filters get hairy.

### Analogous-domain lessons

- **Legal RAG** (Casetext CoCounsel, vLex Vincent): citation-allowlist + reranker + atomic claim verification = industry standard. Stanford RegLab study shows even top legal RAGs hallucinate 17-33% — verification is non-negotiable.
- **Biblical RAG**: verse-prefix context + multi-translation embedding ensembling. Embed Sanskrit + transliteration + English gloss separately, fuse.
- **Medical** (OpenEvidence, Almanac): structured evidence cards + claim-level grounding. Each citation as a card with verse text visible.

---

## 5 · Ayurvedic ontology, NAMASTE, knowledge graph

### Data sources

- **NAMASTE portal** (https://namstp.ayush.gov.in) — National AYUSH Morbidity & Standardized Terminologies for EHR. ~4,500+ Ayurveda disease (vyādhi) codes. Hierarchical alpha-numeric. Includes Sanskrit term + English transliteration + dosha classification. Behind login; downloadable Excel/CSV. Likely Govt of India OGD license.
- **WHO ICD-11 TM2** (https://icd.who.int/browse11/l-m/en — chapter 26): ~400+ Ayurvedic disorder codes, designed for dual-coding alongside ICD-11 main. Free API: https://icd.who.int/icdapi. Token-based.
- **IMPPAT 2.0** (https://cb.imsc.res.in/imppat) — IMSc Chennai. **The single best open dataset.** ~4,000 Indian medicinal plants, ~17,000 phytochemicals, 1,100+ therapeutic uses. Free academic. Downloadable CSV/SDF. Documented in *Sci Rep* 2018 + 2023.
- **TKDL** (https://www.tkdl.res.in) — 250K+ AYUSH formulations. Originally for IP defence. Partial 2022 research opening; bulk access still constrained.
- **CCRAS publications**: Database on Medicinal Plants Used in Ayurveda (10 vols). Print + some PDFs. Source text, not structured DB.
- **NIIMH Hyderabad** (CCRAS unit, http://niimh.nic.in): Ayurveda Encyclopaedia incl. Bhāvaprakāśa, Caraka, Suśruta digital editions with structured tagging.
- **Wikidata SPARQL** (https://query.wikidata.org): moderate Ayurveda coverage. Useful as baseline scrape + entity-linking target.
- **PubChem** (https://pubchem.ncbi.nlm.nih.gov): full open API, cross-linked to IMPPAT.
- **ChEMBL** (https://www.ebi.ac.uk/chembl): bioactivity data, free, REST + dumps.

### MVP KG schema (Hetionet-style, ~8 node types, ~12 edge types)

```
Nodes: Dravya, Formulation, Vyadhi, Dosha, Rasa, Virya, Vipaka, Guna, Phytochemical
Edges: HAS_RASA, HAS_VIRYA, HAS_VIPAKA, PACIFIES_DOSHA, AGGRAVATES_DOSHA,
       INDICATED_FOR, CONTAINS_DRAVYA (Formulation→Dravya), CONTAINS_PHYTOCHEM,
       MENTIONED_IN_VERSE (→ existing verse store)
```

### 4-6 week bootstrap plan

- **Wk 1-2:** Wikidata SPARQL → top 200 dravyas. IMPPAT bulk dump → phytochemistry. NAMASTE codebook (register on portal) → top 100 vyādhi.
- **Wk 3:** Manually curate **rasa-vīrya-vipāka-doṣa-karma table** for top 100 dravyas from **Bhāvaprakāśa Nighaṇṭu** (already in verse corpus — extract via LLM-assisted structured extraction with human review). **Load-bearing step.**
- **Wk 4:** Top 50 formulations from AFI (Triphala, Chyavanaprash, Ashwagandharishta, etc.) — composition triples. Manual from PDFs.
- **Wk 5:** Indication edges (Dravya INDICATED_FOR Vyadhi) — extract from existing classical verse corpus using retrieval pipeline + LLM extraction with citation back to verse.
- **Wk 6:** Integrate into retrieval. Store in Neo4j or RDF/Oxigraph. ~8K-15K triples.

### Hybrid retrieval at query time

1. NER → map to KG nodes (Wikidata QIDs as canonical IDs).
2. Graph expansion: "insomnia" → `Vyadhi:nidrā-nāśa` → traverse `INDICATED_FOR⁻¹` → `{aśvagandha, brāhmī, jaṭāmāṃsī, tagara}` + `LIKELY_DOSHA → vāta`.
3. Pass expanded entity set as boost terms into existing verse retriever.
4. Return verses + structured KG facts (with provenance). LLM grounds answer in both, citing verses for assertions and KG edges for compositional reasoning.

**Critical:** every dravya-property triple must carry a source citation (verse ID or NAMASTE/IMPPAT row ID). Provenance is non-negotiable for clinical-adjacent.

---

## 6 · Real-world evidence integration

### Open data sources (all programmable)

- **PubMed E-utilities** (https://eutils.ncbi.nlm.nih.gov/entrez/eutils/) — `esearch.fcgi` + `efetch.fcgi`. 3 req/s without key, 10/s with API key. ~7-8K records under MeSH "Medicine, Ayurvedic"; ~30K when broadened. **Primary backbone.**
- **Europe PMC** (https://europepmc.org/RestfulWebService) — mirrors PubMed + full-text where OA. Cleaner JSON, no key.
- **ClinicalTrials.gov v2 REST** (https://clinicaltrials.gov/api/v2) — clean. Hundreds to ~1,000 trials per dravya.
- **CTRI** (http://ctri.nic.in) — ~5-7K Ayurveda-tagged trials. HTML/CSV only, no JSON API. Scrape-once + delta refresh.
- **DHARA / AYUSH Research Portal** — Indian Ayurveda journals not in PubMed (~25K articles). No API. Email CCRAS for partnership.
- **IMPPAT** (covered above) — bulk download CC-BY.
- **ChEMBL, PubChem, NPASS, LOTUS** (https://lotus.naturalproducts.net) — natural products databases. LOTUS is fully open (CC0).
- **Cochrane Library** — abstracts CC-BY, full reviews paywalled. Sparse direct Ayurveda coverage; pull broader systematic reviews from PubMed.

### Top dravyas with strong evidence (illustrative)

- **Ashwagandha:** strong for anxiety/stress (Pratte 2014 PMID:24330623; Lopresti 2019 PMID:31517876).
- **Turmeric:** dozens of RCTs; meta-analyses for OA pain (Daily 2016 PMID:27533649), depression, NAFLD.
- **Brahmi (Bacopa):** Kongkeaw 2014 PMID:24252493 — modest cognition effect.
- **Triphala:** Peterson 2017 PMID:28696777 — gut/anti-inflammatory, few high-quality RCTs.
- **Guduchi:** mostly preclinical; controversial post-2020 hepatotoxicity reports (Kulkarni 2022).

### Evidence-tier schema

```json
{
  "claim_id": "...",
  "classical": [{"text":"Caraka","ref":"Su.5.7","quote":"..."}],
  "modern": [{"pmid":"24330623","type":"meta-analysis",
              "n":491,"effect":"d=0.55","grade":"moderate"}],
  "evidence_tier": "A|B|C|traditional-only",
  "concordance": "supports|partial|diverges|silent",
  "last_refreshed": "2026-04-15"
}
```

Tier A = ≥1 SR/meta + classical concordance; B = ≥2 RCTs; C = preclinical only; traditional-only = no modern data. Use **GRADE** (simpler than AMSTAR-2 for runtime).

### 4-8 week bootstrap

- **Wk 1-2 ingestion:** IMPPAT bulk → Postgres. PubMed esearch+efetch per dravya (top-200 by relevance + all SR/meta). ClinicalTrials.gov v2 per dravya.
- **Wk 3-4 ranking + tiering:** SRs > RCTs > observational > preclinical. LLM-assisted abstract → structured `(intervention, comparator, outcome, effect, n)` extraction with 10% human spot-check.
- **Wk 5-6 integration:** New retrieval step after classical retrieval. Given resolved dravyas in planned response, fetch top-3 modern citations per (dravya, mapped indication). Prompt template adds `<evidence_modern>` block. Cite as `[PMID:xxxx]` only when tier A/B and concordance ≠ diverges-silently.
- **Wk 7-8 refresh + UX:** Weekly delta crawler (`reldate=7`). Frontend: classical citation chips (existing) + modern PMID chips with hover card (year, type, n, link to PubMed). 100-Q eval set; track citation precision.

### Comparable products

- **OpenEvidence** (openevidence.com) — inline PMID badges, recency tag, GRADE-like signal. **Adopt UX pattern.**
- **UpToDate** — graded recommendations (1A-2C) + explicit author panel.
- **Glass Health** — DDx + literature snippets w/ citations.

---

## 7 · Compliance + medical AI governance

### What's in force vs pending

| Obligation | Status | Action |
|---|---|---|
| **DPDP Act 2023** | Passed Aug 2023; Draft Rules Jan 2025 | Build layered consent UX; appoint DPO; cross-border register; right-to-erasure endpoint |
| **DMRA 1954** schedule (54 conditions where any "cure" advertisement is prohibited) | In force | Never recommend specific products tied to schedule conditions; route to "consult Vaidya" |
| **CDSCO Medical Device Rules 2017** (SaMD) | In force | Stay out of SaMD: market as "wellness/educational"; no diagnostic/therapeutic claims |
| **MeitY/IndiaAI Governance Guidelines (Nov 2025)** | Recently published | Publish model card + system card; designate grievance officer |
| **NCISM Act 2020** — Ayurvedic prescription requires registered Vaidya | In force | Vaidya-in-the-loop for individualised therapeutic recs; otherwise gate to "consult registered practitioner" |
| **EU AI Act Art. 50** (chatbot disclosure) | Active from Aug 2026 | Add "you are interacting with an AI" notice for EU users |
| **GDPR Art. 9** (special category — health) | In force | Explicit consent flow for EU; UK ICO registration if UK users; EU Art. 27 representative |
| **HIPAA** | US, conditional | BAA template ready; refuse CE-tenants without BAA |
| **FDA general-wellness exemption** (21st Century Cures Sec. 3060) | In force | Keep US claims wellness-only |

### 90-day compliance checklist

**Disclaimers — every consumer-facing surface:**
1. Persistent header: "AI-generated guidance based on classical Ayurvedic texts. Not medical advice. Not a substitute for a registered Vaidya or physician."
2. Pre-chat modal (one-time + on high-risk topic): "Do not use for emergencies, pregnancy, children under 12, cancer, or any condition listed under the DMRA 1954 schedule. Consult a registered practitioner."
3. Output footer on every response: "Educational. Verify with a NCISM-registered Vaidya before acting."
4. EU/UK: "You are interacting with an AI system (EU AI Act Art. 50)."

**Data retention/deletion:**
- Conversation logs: 90 days rolling, then hash-only.
- PII: purpose-limited, 12 months max, delete-on-request within 30 days.
- Right-to-erasure endpoint live before EU traffic.
- Cross-border transfer register.

**Tenant contract (non-negotiable):**
- DPA with controller/processor mapping + SCCs + Indian DPDP addendum.
- Tenant warrants no use for diagnosis/prescription; no scheduled-disease marketing.
- Companion is processor; tenant is Data Fiduciary for end-user data.
- Sub-processor list (Anthropic, hosting, embeddings) with change-notice.
- Audit rights (annual, on notice).
- Indemnity carve-outs.
- Liability cap 12 months fees; carve-outs for data breach, IP, confidentiality.

**Registrations before B2B sales:**
- DPDP grievance officer + DPO contact published.
- IndiaAI sandbox application (if cohort open).
- ISO 27001 in flight.
- EU Art. 27 rep if EU tenants.
- UK ICO registration if UK tenants.
- Insurance bound (tech-E&O + cyber + media liability).
- Model card + system card published.
- PvPI-AYUSH adverse-event SOP documented.

### High-risk gating

Hard-block: cancer, pregnancy/lactation, pediatric (<12), psychiatric, transplant, oncology drug-interactions → respond with referral-only.

### Insurance

Indian professional-indemnity for AI health guidance is nascent. ICICI Lombard, Tata AIG, HDFC Ergo write tech-E&O + cyber combined (~₹50L-2Cr cover, premiums 1-3% of limit). Standard exclusions include regulatory fines, intentional misrepresentation, bodily injury. Broker-led placement combining tech-E&O + cyber + media liability; disclose AI-health use case explicitly.

---

## 8 · Modern clinical evidence — dataset-level (returned)

### Top-evidence single dravyas — best RCTs and reviews

> **Confidence note:** PMIDs below should be re-verified via PubMed before ingestion. QA-pass required.

- **Ashwagandha (W. somnifera)** — strongest evidence. **Stress/anxiety** is the most-supported indication. RCTs: Chandrasekhar 2012 PMID 23439798 (N=64, KSM-66 300mg BID 60d, PSS effect size ~d=1.0); Salve 2019 PMID 32021735; Lopresti 2019 PMID 31517876. SR/MA: Pratte 2014 PMID 25405876; Speers 2021 PMID 33723635. Sleep: Langade 2019 PMID 31728244 (moderate). AEs: rare hepatotoxicity case reports (NIH LiverTox, 2020); thyroid stimulation — caution with hyperthyroid + immunosuppressants.
- **Turmeric/Curcumin** — Knee OA strongest: Kuptniratsaikul 2014 PMID 24672232 (N=367 vs ibuprofen, non-inferiority). Daily 2016 SR PMID 27533649. Depression: Lopresti 2014 PMID 25046624. AEs: rare hepatotoxicity (esp. with piperine); anticoagulant interaction.
- **Triphala** — Constipation: Mukherjee 2006; Peterson 2017 SR PMID 28147384 is canonical. Periodontal: Bajaj & Tandon 2011. Mostly low-N Indian trials; flag moderate.
- **Brahmi (B. monnieri)** — Cognition: Stough 2001 PMID 11498727; Calabrese 2008 PMID 18611150 (N=54). Meta-analysis: Kongkeaw 2014 PMID 24252493.
- **Tulsi** — Jamshidi & Cohen 2017 SR PMID 28400848. Moderate for stress/metabolic; weak otherwise.
- **Guggul** — Szapary 2003 *JAMA* PMID 12915429 — **negative trial** for hyperlipidemia in Western population. Ingest the negative evidence.
- **Boswellia serrata** — Knee OA: Kimmatkar 2003 PMID 12622457; Sengupta 2008 PMID 18667054 (5-Loxin). Yu 2020 SR.
- **Amla** — Akhtar 2011 (lipids); Usharani 2013 PMID 23901288.
- **Guduchi** — COVID-era surge; ICMR-AYUSH AYUSH-64 work covered Guduchi as component (Chopra 2021 PMID 33812744). **Hepatotoxicity signal** — Kulkarni 2022 J Clin Exp Hepatol — important AE alert.
- **Yashtimadhu** — peptic ulcer Cochrane-adjacent reviews; AE pseudohyperaldosteronism with chronic high-dose.
- **Arjuna** — Bharani 2002 (CHF); Dwivedi 2007 SR PMID 17804178.
- **Yogarāja/Kaiśora/Trayodaśāṅga Guggulu** — Chopra 2013 *Rheumatology* PMID 23934335 — **landmark trial, Ayurvedic formulations vs methotrexate in RA**.
- **AYUSH-64** (post-COVID) — Chopra 2021 PMID 33812744; CTRI/2020/05/025293.

### Open-access clinical research databases

| Database | Coverage | Access | License |
|---|---|---|---|
| **PubMed E-utilities** | 7-8K records under "Medicine, Ayurvedic"[MeSH]; ~30K broadened | REST `esearch.fcgi`+`efetch.fcgi`, 3 req/s (10 with key) | Free |
| **Europe PMC** | Mirrors PubMed + full-text where OA | RESTful (https://europepmc.org/RestfulWebService); OAI-PMH | Free |
| **CTRI** | ~60K trials, ~7-9K AYUSH | HTML/CSV only, no JSON API; scrape + delta refresh | Free |
| **DHARA** (CCRAS) | ~40K Ayurveda articles incl. PG theses | No API, no bulk dump publicly; partnership | CCRAS approval |
| **AYUSH Research Portal** | Ministry research DB | Search-only UI; no API | — |
| **WHO ICTRP** | Global aggregator; harvests CTRI | Weekly XML on request | Free |
| **Cochrane Library** | ~10-15 Ayurveda-specific reviews | Abstracts CC-BY-NC; full reviews paywalled | Mixed |
| **IMPPAT 2.0** | 17,967 phytochemicals, 4,010 plants, 1.1M plant-phytochemical edges | Bulk TSV/SDF/JSON download | CC-BY 4.0 |
| **LOTUS** (https://lotus.naturalproducts.net) | Natural products structural DB | Open API | CC0 |
| **PubChem PUG-REST** | Bioassay data for phytochemicals | REST API | Public domain |
| **ChEMBL** | Bioactivity, IC50/Ki | REST + RDF dump | CC-BY-SA |
| **NPASS 2.0** (https://bidd.group/NPASS/) | 96K NPs, 35K species; substantial Indian medicinal plant coverage | Bulk download | CC-BY-NC |
| **NCCIH "Herbs at a Glance"** | ~50 clinician-grade monographs | https://www.nccih.nih.gov/health/herbsataglance | US gov public domain |
| **MSKCC About Herbs** | ~70 monographs | https://www.mskcc.org/.../herbs | CC-BY-NC, no redistribute — link out |
| **AYUSH STGs** | Ministry STGs for ~50 conditions | https://main.ayush.gov.in/ PDFs | Govt — usage TBD |
| **Natural Medicines Comprehensive DB** | Best-curated commercial source for herb evidence + interactions | Paid (~$10K/yr institutional) | Commercial license |

### Quality grading

- **GRADE** (https://www.gradeworkinggroup.org/) — manual SR grading.
- **AMSTAR-2** (https://amstar.ca) — 16-item SR appraisal; partial LLM automation feasible.
- **Jadad scale** — quick RCT scoring (0-5); easy automation from abstract+methods.
- **Cochrane RoB 2** for newer trials.
- **Tooling:** Semantic Scholar API (free, citation count + influence), OpenAlex (https://openalex.org, fully open replacement for Microsoft Academic), Dimensions (free academic tier), Scite.ai (supporting/contradicting citations).

### Concrete 6-week ingestion plan

**Goal:** populate `modern_evidence` table linking 50 dravyas to evidence rows.

```
Schema:
dravya_id | latin_binomial | evidence_type[rct|sr|ma|case|preclinical] |
pmid | doi | ctri_id | year | journal | sample_size | indication |
quality_score[0-1] | effect_summary | adverse_events | full_text_oa[bool] |
imppat_phytochem_count | source_url
```

| Wk | Deliverable | Target count |
|---|---|---|
| 1 | PubMed E-utils harvester (50 dravyas × Latin + Sanskrit synonyms; RCT/SR/MA pubtype filters); Europe PMC fallback | ~3,000 PMIDs (top-10 per dravya curated, ~500) |
| 2 | CTRI scraper (50 dravyas); WHO ICTRP weekly XML cross-check | ~1,500 trial records |
| 3 | IMPPAT 2.0 bulk TSV ingest; map to dravya via Latin binomial; PubChem CID enrichment | ~17K phytochemicals; ~50K dravya-phytochem edges |
| 4 | NCCIH + MSKCC monographs (50) + AYUSH STG PDFs (~50) | ~100 monograph rows |
| 5 | Quality scoring: auto-Jadad from abstract via LLM; Semantic Scholar / OpenAlex citation enrichment; AMSTAR-2 prompt for SRs | quality_score on every row |
| 6 | Citation linker into existing classical-verse RAG; QA pass on 500 highest-traffic dravya–indication pairs; manual PMID re-verification (random 5%) | ready for staged rollout |

**Confirmed-public:** PubMed, Europe PMC, CTRI, WHO ICTRP, IMPPAT, PubChem, ChEMBL, NPASS, LOTUS, NCCIH, AYUSH STGs, *J Ayurveda Integr Med* (OA), OpenAlex, Semantic Scholar.

**Flagged:** DHARA bulk dump (no public API), AYUSH Research Portal (UI-only), TCMSP (intermittent uptime), MSKCC scrape ToS (re-read), Cochrane Wiley API (paid). **Commercial decision required:** Natural Medicines Comprehensive DB (~$10K/yr — strong recommend).

---

## 9 · Comprehensive materia medica (dravyaguṇa-vijñāna)

### Classical Nighaṇṭu sources

| Nighaṇṭu | Author / date | Dravya count | Vargas | License |
|---|---|---|---|---|
| **Bhāvaprakāśa Nighaṇṭu** | Bhāvamiśra, c. 1558 CE | ~470 | 23 (Harītakyādi → Miśraka) | Text PD; Chunekar commentary © Chaukhambha — **uncertain** for redistribution |
| **Dhanvantari Nighaṇṭu** | Anon. 10-13th c. | ~373 | 7 | MSS PD; Sharma ed. © |
| **Madanapāla Nighaṇṭu** | Madanapāla 1374 CE | ~600 unique | 13 | Text PD |
| **Rāja Nighaṇṭu** | Narahari Paṇḍita c. 17th c. | ~480 (~2000 synonyms) | 22 | Text PD |
| **Kaiyadeva Nighaṇṭu** | Kaiyadeva 1450 CE | ~2200 entries | 9 | Text PD |
| **Sodhala Nighaṇṭu** | Sodhala c. 1100-1200 | ~960 | 27 | Text PD |
| **Śāligrāma Nighaṇṭu Bhūṣaṇa** | Lala Śāligrāma 1896 | ~2400 | 8 khaṇḍas | Text PD |

**Aggregator: NIIMH-CCRAS eNighantu portal** — https://niimh.nic.in/ebooks/e-Nighantu/. **Single best digital starting point.** Hosts most major Nighaṇṭus. Govt-of-India open-access for research; redistribution terms uncertain — confirm with CCRAS as part of MoU.

### Modern pharmacopoeial sources

- **API (Ayurvedic Pharmacopoeia of India)** — Part I (single drugs) Vols I-IX, ~645 monographs; Part II (formulations) Vols I-IV. PDFs at https://www.pharmacopoeia.gov.in/publications.aspx. Govt publication, free download; commercial redistribution uncertain.
- **AFI (Ayurvedic Formulary of India)** — Parts I-III, ~1227 formulations.
- **Quality Standards of Indian Medicinal Plants** (ICMR) — 18 vols, 250+ plants. Print only; intermittent PDFs on archive.org. Copyrighted.
- **P.V. Sharma — Dravyaguṇa-Vijñāna** (5 vols) and **Classical Uses of Medicinal Plants** — Chaukhambha. Print-copyright.
- **P.K. Warrier — Indian Medicinal Plants: A Compendium of 500 Species** (Orient Longman / AVS Kottakkal), 5 vols. Copyrighted.
- **IMPPAT 2.0** (https://cb.imsc.res.in/imppat/) — open CC-BY-4.0. **Single best machine-readable.**
- **NMPB e-Charak** (https://echarak.in/) — Ministry of AYUSH species lookup. Free; redistribution uncertain.
- **TKDL** — CSIR; not public, prior-art DB. Inaccessible.

### Schema (proposed columns for ~500-row dravya table)

```
id, nama_sanskrit, nama_devanagari, latin_binomial, family,
hindi, english, regional_names[], varga_bhavaprakasha, varga_other[],
sthavara_jangama, rasa[], guna[], virya, vipaka, prabhava,
dosha_karma{vata,pitta,kapha}, karma[], prayoga[],
matra_value, matra_unit, anupana[], kala,
contraindications[], viruddha[], toxicity_notes,
pratinidhi_dravya[], part_used[],
phytochemicals[] (IMPPAT-linked), modern_pharmacology[],
clinical_evidence[] (PMID list), pregnancy_lactation_status,
api_monograph_ref, nighantu_refs[],
provenance{source,page,reviewer},
review_tier (vaidya|peer|llm-only)
```

**Controlled vocabularies:** rasa (6 — madhura, amla, lavaṇa, kaṭu, tikta, kaṣāya), guṇa (20 — Caraka Sūtra 25), vīrya (2 — uṣṇa/śīta), vipāka (3 — madhura/amla/kaṭu), karma (curated 40-term list seeded from Caraka Saṃśodhana-saṃśamana-adhyāya + Bhāvaprakāśa karma indices: dīpana, pācana, anulomana, sraṃsana, recana, śodhana, śamana, lekhana, bṛṃhaṇa, balya, varṇya, medhya, rasāyana, vājīkara, śothahara, raktastambhaka, śūlahara, jvarahara, etc.).

### Varga taxonomy (import as KG)

Use **Bhāvaprakāśa's 23 vargas as primary** (Harītakyādi, Karpūrādi, Guḍūcyādi, Puṣpa, Vaṭādi, Āmrādi, Dhānya, Śimbidhānya, Śāka, Mūla-phalādi, Kṛtānna, Hārīta-Hārītaka, Snehādi, Madya, Mūtra, Toya, Dugdha, Dadhi, Takra, Navanīta, Ghṛta, Kṣīra, Māṃsa-Jāṅgala-Anūpa). Overlay Rāja Nighaṇṭu's 22 + Kaiyadeva's 9 as alternative facets. Multi-label is fine.

### Beyond plants — the full dravya universe

- **Rasa-śāstra** seeds: *Rasatārangiṇī* (Sadānanda Śarmā, archive.org PD), *Rasaratna-samuccaya* (Vāgbhaṭa II), *Rasendra-sāra-saṅgraha*. Cover **mahārasa-8** (abhraka, vaikrānta, mākṣika, vimala, śilājatu, sasyaka, capala, rasaka), **uparasa-8** (gandhaka, gairika, kāsīsa, kāṅkṣī, hartāla, manaḥśilā, añjana, kaṅkuṣṭha), **sādhāraṇa-rasa**, **ratna-9**, **dhātu-lauha**, **viṣa-upaviṣa**.
- **Bhasma**: API Vol VII-IX has ~30 bhasma monographs with QC limits. Treat as `dravya_type=bhasma` with mandatory toxicology fields (heavy-metal content, Ayurvedic vs modern toxicology divergence flag).
- **Animal-origin**: madhu, ghṛta, gorocana, kastūrī, mukta, pravāḷa, śaṅkha — ~25 entries; many CITES-restricted today (flag legality).

### Toxicology + interaction sources

- **API monographs** ship safety + identity tests (primary).
- **PvPI-AYUSH** signal reports — bulk export uncertain, request via RTI/email.
- **NIH LiverTox** — public-domain entries on Ayurvedic & herbal hepatotoxicity. **Ingest directly.**
- **MSKCC About Herbs** — free, well-curated; ToS forbids redistribution → reference-link only.
- **Natural Medicines Comprehensive DB** — paid gold standard for interactions; license required.
- **LactMed (NIH)** — public-domain, ~80 herbs for pregnancy/lactation. Supplement with classical garbhiṇī-paricaryā contraindications from Caraka Śārīra 8.

### 6-week 500-row build plan

- **Wk 1:** Pull eNighantu PDFs (Bhāvaprakāśa, Kaiyadeva, Rāja, Madanapāla); OCR Skt+Devanāgarī (Tesseract+Sanskrit-OCR or Google DocAI). Pull all API Part-I PDFs. Pull IMPPAT 2.0 full TSV dump. Email CCRAS+PCIM-H clarifying redistribution rights. Lock schema + Postgres+Neo4j tables.
- **Wk 2:** Build authoritative 500-name list from Bhāvaprakāśa varga indices. Map each to API monograph # (where exists, ~330) and IMPPAT plant-id (where exists, ~420). Insert empty rows with provenance pointers.
- **Wk 3:** LLM-assisted extraction — Claude Opus + Sanskrit-tuned model for verse parsing, extract rasa/guṇa/vīrya/vipāka/karma/prayoga/mātrā per dravya from Bhāvaprakāśa verse + API monograph. Mandatory `provenance{source, page/verse, extracted_quote}` per field. Parallel: pull phytochem from IMPPAT, pharmacology PMIDs.
- **Wk 4:** Toxicology overlay — LiverTox + LactMed (PD). Cross-link API safety + classical viruddha. Flag the ~40 dravyas with notable modern interactions (ashwagandha-thyroid, guggul-statin, etc.).
- **Wk 5:** **Vaidya review (top 100)** — two-vaidya independent review; disagreements adjudicated by senior. Tag `review_tier=vaidya`. Tail 400 stays `review_tier=llm-only` with visible disclosure in UI.
- **Wk 6:** KG load to Neo4j (nodes: Dravya, Varga, Rasa, Guṇa, Karma, Roga, Yoga, Phytochemical; edges: BELONGS_TO_VARGA, HAS_RASA, INDICATED_IN, CONTAINS_PHYTOCHEM, INTERACTS_WITH). Build 200-query vaidya-written eval set; target recall@10 ≥ 0.85. Freeze v1.0; publish provenance + license manifest.

**Confirmed open:** IMPPAT (CC-BY-4.0), LiverTox/LactMed (US-Govt PD), Sanskrit primary texts on archive.org/GRETIL/muktabodha (PD), classical rasa-śāstra texts pre-1923.
**Uncertain license:** CCRAS eNighantu redistribution, API/AFI commercial redistribution, ICMR QSIMP, P.V. Sharma & P.K. Warrier volumes, MSK About-Herbs, PvPI-AYUSH bulk.

---

## 10 · Bhaiṣajya Kalpanā + practices + procedures

### Pañca-vidha kaṣāya kalpanā (5 base preparations — Sharangadhara Madhyama 1-6)

| Kalpanā | Method | Drug:Water | Sevana mātrā | Indication |
|---|---|---|---|---|
| **Svarasa** | Crush fresh herb, squeeze | — | 10-20 ml | Acute conditions, strongest potency |
| **Kalka** | Wet-grind | — | 5-10 g | Paste, anupāna base |
| **Kvātha/Kaṣāya** | Boil 1:16 (soft) / 1:8 (med) / 1:4 (hard); reduce to ¼ | varies | 48-96 ml | Most-prescribed liquid |
| **Hima** | Soak overnight cold 1:6 | — | 48-96 ml | Pitta, summer, śītala drugs |
| **Phāṇṭa** | Pour boiling water 1:4, steep | — | 48-96 ml | Aromatic/volatile drugs |

**Potency hierarchy:** Svarasa > Kalka > Kvātha > Hima > Phāṇṭa.

### Secondary kalpanās (upakalpanā)

- **Churṇa** — fine sieved powder; classical 2 mo / API 1-3 yr.
- **Vatī/Guṭikā** — 125 mg-2 g.
- **Avaleha/Lehya/Modaka** — 5-25 g (e.g. Cyavanaprāśa).
- **Ghṛta-kalpanā** — Sneha-pāka 4 stages (mṛdu-madhyama-khara-dagdha); shelf-life 16 mo (improves with age, "purāṇa-ghṛta" prized).
- **Taila-kalpanā** — same logic; 16 mo classical / 3 yr modern.
- **Āriṣṭa** (decoction-fermented) and **Āsava** (cold-water-fermented) — self-generated 5-10% alcohol; indefinite shelf life.
- **Sandhāna kalpanā** — fermentation method (dhātakī flowers + jaggery + herbs in earthen pot, 1 month).
- **Sneha kalpanā** — internal oleation-grade ghee/oil for snehapāna.
- **Rasa-śāstra** (Rasendra Sāra Saṅgraha, Rasa Tarangiṇī, Rasaratna Samuccaya): **bhasma** (śodhana → māraṇa → puṭa), **parpaṭī**, **kupīpakva** (e.g. Rasa Sindūra), **sattva**, **druti**, **kṣāra**.

### Top formulations (composition + reference)

**Herb groups:** Triphala (1:1:1 Harītakī/Vibhītakī/Āmalakī, 3-6 g HS warm water); Trikaṭu (Śuṇṭhī+Pippalī+Marica, 1-3 g); **Daśamūla** (5 bṛhat: Bilva/Agnimantha/Śyonāka/Pāṭalā/Gambhārī + 5 laghu: Śālaparṇī/Pṛśniparṇī/Bṛhatī/Kaṇṭakārī/Gokṣura); Pañcatikta, Pañcakola, Caturjāta.

**Ghṛta** (Aṣṭāṅga Hṛdaya Uttara, Caraka Cikitsā): Triphalā (AH Uttara 13, netra-roga, 5-10g); Brāhmī (Caraka Ci 10/BR Unmāda, psychiatric); Phala-Kalyāṇaka (Caraka Ci 30, infertility); Indukānta (Sahasra Yoga, chronic fevers/IBS); Mahā-pañcagavya (apasmāra/jaundice).

**Taila:** Mahānārāyaṇa (BR Vātavyādhi, 56 dravyas, arthritis/sciatica); Mahāmāṣa (facial palsy); Bhṛṅgarāja (alopecia); Sahacharādi (sciatica); Dhānwantara (neuro-musc); Bala-Aśvagandha (paediatric debility).

**Avaleha:** **Cyavanaprāśa** (Caraka Cikitsā 1.1.62-74, kuṭīpraveśika, 49+ herbs Āmalakī base, 10-20 g); Brahma rasāyana (Caraka Ci 1.1.41-57); Kuṣmāṇḍa (BR, chronic cough/raktapitta); Vāsāvaleha (phthisis); Agastya rasāyana.

**Vatī/Guggulu** (Yogaratnākara, BR): Triphalā guggulu (fistula, 500 mg-1 g BD); **Yogarāja** (āmavāta/RA); **Kaiśora** (gout/raktadoṣa/acne, 500 mg TDS); Mahā-yogarāja (severe RA, with bhasmas); **Kāñcanāra** (granthi/lymphadenopathy/thyroid nodules/PCOS); Trayodaśāṅga (sciatica); Khadirādi (oral/throat); Sūtaśekhara rasa (hyperacidity, with bhasmas); Sañjīvanī vatī (fevers/GI).

**Āsava-Āriṣṭa** (Sharangadhara Madhyama 10): **Aśvagandhāriṣṭa** (anxiety/debility, 15-30 ml); Drākṣāriṣṭa; Daśamūlāriṣṭa (post-partum/vāta); Lohāsava (anaemia); Kumāryāsava (menstrual/hepatic); Punarnavāsava (oedema/hepatic/renal); Pippalyāsava (IBS/cough); Sārasvatāriṣṭa (speech/memory).

**Bhasma** (API Vol VII-IX, ~30 monographs with QC limits): Abhraka, Lauha, Tāmra, Yaśada, Mukta, Pravāḷa, Svarṇa, Rajata. **Must come ROTA-tested + AYUSH-licensed**; serious heavy-metal contamination concerns when uncertified.

**Curṇa:** Avipattikara (3-6 g, hyperacidity/constipation); Hiṅgvāṣṭaka (flatulence); Sitopalādi/Tāḷiṣādi (3-6 g w/ honey, cough); Lavaṇa-bhāskara; **Sudarśana** (fevers, JE prophylaxis per AYUSH STG).

### Quality, safety, standardisation

- **API/AFI** = mandatory references for licensed manufacture.
- **PLIM Ghaziabad** (Pharmacopoeial Lab); **PCIM&H** (Pharmacopoeia Commission).
- **Heavy-metal contamination** — Saper *JAMA* 2008/2004 PMID 18728265: ~20% of US-market Ayurveda contained Pb/Hg/As above safety; bhasmas legitimately contain controlled metals. AYUSH GMP + WHO-GMP now mandate ICP-MS limits.
- **Shelf life** (Gazette 2009): Curṇa 2 yr · Vatī 3 yr · Āsava-Āriṣṭa 10 yr · Bhasma 10 yr · Taila 3 yr · Ghṛta 3 yr.

### Pañcakarma (Caraka Sūtra 2; AH Sūtra 18)

| Procedure | Used for | Method | AEs / CI |
|---|---|---|---|
| **Vamana** | Kapha (asthma, psoriasis, obesity) | 7d snehapāna → svedana → vamanopaga (Madanaphala+Yaṣṭimadhu+Saindhava+milk); 4-8 vegas | electrolyte loss, aspiration; pregnancy/cardiac/elderly debilitated |
| **Virecana** | Pitta (skin, hepatic, IBS) | Triphalā/Trivṛt/Eraṇḍa-bhṛṣṭa | Caraka prefers virecana for chronic disease |
| **Basti** | Vāta master-therapy | **Nirūha** (decoction) + **Anuvāsana** (oil); **Yoga** (8d), **Kāla** (16d), **Karma** (30d) bastis; also **Mātrā/Uttara/Picchā** | rectal trauma, vāta provocation if dose wrong |
| **Nasya** | Head/cervical/sensory | Pradhamana (powder, kapha), **Marśa** (oil 6-10 drops), **Pratimarśa** (daily 2 drops Aṇu taila), Navana, Avapīḍana, Dhūma | sinusitis acute |
| **Raktamokṣa** | Pitta-rakta vyādhi | Jalaukāvacaraṇa (leech), Sirāvyadha (venesection), Pracchāna, Ghaṭīyantra (cupping) | bleeding disorders |

### Pūrvakarma (preparatory)

- **Snehana** internal — **vardhamāna mātrā** (escalating: 30→60→120→240 ml ghee over 3-7 d until samyak-snigdha lakṣaṇa); external abhyaṅga.
- **Svedana** — Bāṣpa (steam), Nāḍī (tube), Avagāha (tub), **Piṇḍa** (bolus: Patra-piṇḍa leaves, Cūrṇa-piṇḍa powder, **Ṣaṣṭika-piṇḍa** rice).

### Paścāt-karma

- **Saṃsarjana krama** — graduated diet over 5-7 d post-vamana/virecana: peyā → vilepī → akṛta yūṣa → kṛta yūṣa → akṛta māṃsarasa → kṛta māṃsarasa → samānya āhāra. Restores agni.

### Kerala specialty (Sahasra Yoga, AH commentaries)

- **Śirodhārā** — 30-45 min oil/buttermilk/decoction stream; insomnia/anxiety/neuro.
- **Pizhichil** (sarvāṅga oil-pour with cloth); severe vāta, neuro-rehab.
- **Navarakizhi** (Ṣaṣṭika-piṇḍa-sveda) — milk-cooked rice bolus; muscular dystrophy, neuro.
- **Localised vasti**: Kaṭi (lumbar), Hṛd (sternum, IHD), Greevā (cervical), **Jānu** (knee OA) — dough-dam holding warm oil 30 min.
- **Udvartana/Ubṭana** — dry powder massage, kapha/obesity.
- **Abhyaṅga** — daily oil massage, dincharyā.
- **Distinctions:** Śirodhārā (stream) vs Śirovasti (oil pool in leather cap on head, 30-60 min) vs Śiropicchu (oil-soaked cotton on vertex).
- **Akṣi-tarpaṇa** (eye ghee-pool), **Karṇa-pūraṇa** (ear oil-fill).

### Kriyā Kalpa (5 eye procedures, Śālākya Tantra)

**Tarpaṇa** (medicated ghee retained in dough-ring over closed eye), **Puṭapāka** (concentrated juice instilled), **Seka** (irrigation), **Āścyotana** (drops), **Añjana** (collyrium — Sauvīra, Rasāñjana). AH Uttara 24, Suśruta Uttara.

### Caryā (regimens)

- **Dincharyā** (AH Sūtra 2): Brāhma muhūrta (~04:30); dantadhāvana (Khadira/Nimba twig); jihvā-nirlekhana; añjana; nasya; gaṇḍūṣa-kavala (oil pulling); abhyaṅga; vyāyāma to ardha-śakti; snāna; mitāhāra; early sleep.
- **Ṛtucharyā** (AH Sūtra 3): six ṛtu adjustments — śiśira (heating), vasanta (kapha-purgation, **vamana season**), grīṣma (cooling, hima), varṣā (vāta-pacifying, **basti season**), śarad (pitta, **virecana season**), hemanta (rasāyana, brmhaṇa).
- **Sadvṛtta** (Caraka Sūtra 8): moral conduct as preventive medicine.

### Rasāyana (Caraka Cikitsā 1.1-1.4)

- **Vātātapika** — outpatient (Triphalā, Cyavanaprāśa).
- **Kuṭīpraveśika** — sealed cabin, controlled diet, 21-90 d (Caraka Ci 1.1.16-24).
- **Specifics:** Triphalā, Cyavanaprāśa, Brahma, **Pippalī** (vardhamāna 1→10→1), Bhṛṅgarāja, Guḍūcī, Lauhādi.
- **Achāra rasāyana** (Ci 1.4.30-35): truthfulness, non-violence, spiritual practice as rejuvenation.

### Vājīkaraṇa (Caraka Cikitsā 2)

Vṛṣya yoga, Aśvagandhā-pāka, Cūrṇaka modaka, Maśa-pāka, Vajīkaraṇa ghṛta, Kāmeśvara modaka.

### Aṣṭāṅga Āyurveda (8 specialties)

Kāyacikitsā · Kaumārabhṛtya · Bhūta-vidyā · Śālākya · **Śalya** (Suśruta's 101 yantra + 20 śastra incl. aśmarī/cataract/rhinoplasty) · Agada · Rasāyana · Vājīkaraṇa.

### 6-week data-build roadmap

| Wk | Deliverable | Target |
|---|---|---|
| 1 | Schemas — `formulations`, `procedures`, `dravyas`. Pull AFI vols I-III + API vols. | Schema locked |
| 2 | Top 200 formulations Tier 1 (100): 30 curṇa + 25 vatī/guggulu + 20 āsava-āriṣṭa + 15 ghṛta + 10 taila from AFI; source verses from NIIMH e-Saṃhitā | 100 rows |
| 3 | Top 200 Tier 2 (100): 10 bhasmas (with mandatory licensing/heavy-metal disclaimer), 10 avalehas, 15 rasayogas, 65 regional (Sahasra Yoga). Cross-link AYUSH STGs (~40 conditions) | 200 rows |
| 4 | Pañcakarma + caryā + rasāyana protocol objects: indications, CI, pūrvakarma steps with day-wise vardhamāna doses, pradhāna karma vega/mātrā, paścāt saṃsarjana krama | Protocol library |
| 5 | Drug-interaction + contraindication tables (`interactions`: formulation × Western_drug × severity × mechanism × source) seeded from MSK About Herbs + Examine.com + NatMed + classical viruddha-āhāra (Caraka Sūtra 26) | Interactions matrix |
| 6 | Vaidya panel (3 BAMS+MD) reviews 30 random rows; target ≥95% agreement. Build hybrid retrieval (BM25 + embeddings) for RAG; enforce citation-required answers. | Released v1 |

**Uncertainty flags:** AYUSH STGs cover ~40 conditions only; Sahasra Yoga has multiple versions (pick AVS/AVP edition); dose ranges vary ±50% across texts (store *range* not point); bhasma compositions vary by manufacturer (don't auto-recommend without licensed-product link); rasayogas with mercurials/arsenicals are legal in India under Schedule E(1), restricted/illegal in US/EU/Canada/Australia — **jurisdiction-aware rendering required**.

---

## 11 · Classical diagnostic methods — parīkṣā

### Foundational frameworks

- **Trividha parīkṣā** (Charaka Vimāna 4.3-4): **Pratyakṣa** (direct sensory perception), **Anumāna** (inference — e.g. agni inferred from digestion), **Āptopadeśa** (testimony of authoritative texts/teachers). **Yukti** (synthesis) added by Sushruta. Epistemological scaffold.
- **Ṣaḍvidha parīkṣā** (6-fold sensory): Cakṣur, Sparśa, Śabda, Ghrāṇa, Rasa (rarely used now), **Praśna** (history-taking — functionally the modern clinical interview).
- **Aṣṭasthāna parīkṣā** (8-fold) — codified in **Yogaratnakara Pūrvārdha**: Nāḍī, Mūtra, Mala, Jihvā, Śabda, Sparśa, Dṛk, Ākṛti. **The operational examination protocol most BAMS clinics teach.**
- **Daśavidha parīkṣā** (Charaka Vimāna 8.94): examines the *patient*, not the disease — Prakṛti, Vikṛti, Sāra, Saṃhanana, Pramāṇa, Sātmya, Sattva, Āhāra-śakti, Vyāyāma-śakti, Vaya.

**Encoding verdict:** Trividha + Daśavidha = patient framework; Aṣṭasthāna = examination protocol; **Pañca-nidāna** = disease framework. All four must be encoded.

### Aṣṭasthāna methodology (per element)

- **Nāḍī parīkṣā** — three fingers radial artery (index=vāta, middle=pitta, ring=kapha). Right wrist males / left females (later commentary; Charaka doesn't specify). Examine post-dawn fasting post-evacuation. Pulse signatures: vāta=sarpa-gati (serpentine, irregular, thin); pitta=maṇḍūka-gati (frog-like, jumpy, hot, forceful); kapha=haṃsa-gati (swan-like, slow, deep, steady). Combinations: dvandvaja, sannipātaja. **Mumūrṣu nāḍī** (death pulse) — extremely thready/irregular/absent. **Modern correlate:** allopathic radial pulse (waterhammer in AR, pulsus bisferiens in HOCM/AR, pulsus alternans in CHF). Joshi et al. *J-AIM* photoplethysmography studies attempt objectification but **inter-rater reliability remains poor** — flag.
- **Mūtra parīkṣā** — Volume, frequency, varṇa (yellow=pitta, white/foamy=kapha, dry=vāta), gandha, sāndratā, foam. **Taila-bindu parīkṣā** (Yogaratnakara) — drop sesame oil onto still urine sample at brāhma-muhūrta. Spread = sādhya (curable); sinks = asādhya; spreads east = recovery, south = death (directional reading symbolic). Pattern shapes — fish/sieve/snake — mapped to doṣas. **Modern correlate:** loose mapping to bilirubinuria/proteinuria/UTI; taila-bindu studied as surface-tension assay (Ranade et al.) — **mechanism plausible, clinical validation thin**. Flag uncertain.
- **Mala parīkṣā** — Quantity, varṇa, consistency, gandha, sinking-vs-floating (sāma sinks, nirāma floats — āma indicator), undigested matter. **Modern correlate:** Bristol stool chart, steatorrhoea, occult blood. Solid overlap.
- **Jihvā parīkṣā** — Coating (sāma jihvā = thick white coat → āma); colour (pale=vāta/anaemia, red=pitta, white-thick=kapha); fissures (vāta), ulcers (pitta), tremor (vāta vitiation). Regional zones: tip=heart/lung, middle=stomach/spleen, root=intestines/kidneys. **Modern correlate:** glossitis, candidiasis, geographic tongue.
- **Śabda parīkṣā** — Voice (kṣīṇa=vāta, tīkṣṇa=pitta, snigdha-gambhīra=kapha), bowel/breath sounds, joint crepitus. **Modern correlate:** auscultation. Direct overlap.
- **Sparśa parīkṣā** — Skin: rūkṣa-cold=vāta, hot=pitta, cold-clammy=kapha. Organ palpation. **Modern correlate:** physical exam.
- **Dṛk parīkṣā** — Sclera (icterus=pitta), conjunctiva (pallor=rasa-kṣaya), pupil, movements, lacrimation. **Modern correlate:** eye exam — high overlap.
- **Ākṛti parīkṣā** — Build, posture, gait, facial affect, hair, nails. **Modern correlate:** general inspection.

### Daśavidha details

**Prakṛti** (Dehika V/P/K + 7 dvandvaja/sannipātaja, plus Mānasika sāttvika 7 / rājasika 6 / tāmasika 3 subtypes — Charaka Sharira 4). **CCRAS Ayur-Prakriti Web Portal** (validated 100+ item questionnaire) and **AyuSoft** (CDAC/CCRAS, https://www.cdac.in/index.aspx?id=hi_his_ayusoft). NIA Jaipur AyurPrakriti tool is research-grade. **Inter-tool concordance is moderate at best — flag.** **Vikṛti** (current imbalance). **Sāra** (7+1: rasa, rakta, māṃsa, meda, asthi, majjā, śukra, sattva). **Saṃhanana** (compactness). **Pramāṇa** (aṅgula-māna, Charaka Sharira 8). **Sātmya** (suitability). **Sattva** (mental endurance: pravara/madhyama/avara). **Āhāra-śakti** (abhyavaharaṇa + jaraṇa). **Vyāyāma-śakti** (typically half-strength). **Vaya** (bāla <16, madhya 16-60, vṛddha >60 per Charaka).

### Disease-cascade frameworks

- **Pañca-nidāna** (Mādhava Nidāna 1): Nidāna → Pūrvarūpa → Rūpa → Upaśaya → Saṃprāpti.
- **Ṣaṭ-kriyā-kāla** (Sushruta Sūtra 21): Saṃcaya → Prakopa → Prasara → Sthāna-saṃśraya → Vyakti → Bheda. Earlier stages reversible.
- **Doṣa-dūṣya-sammūrcchanā** (which doṣa colludes with which dhātu/srotas).
- **Adhiṣṭhāna** (site). **Mārga**: śākhā (peripheral) / madhyama (vital — heart/head/bladder) / marma-asthi-sandhi.
- **Sādhya-asādhya:** sukha-sādhya / kṛcchra-sādhya / yāpya / asādhya.

### Mānasika parīkṣā

Triguṇa (sattva/rajas/tamas). 16 mānasika prakṛti subtypes (Charaka Sharira 4): 7 sāttvika (Brāhma, Ārṣa, Aindra, Yāmya, Vāruṇa, Kaubera, Gāndharva) · 6 rājasika (Āsura, Sārpa, Śākuna, Rākṣasa, Paiśāca, Praita) · 3 tāmasika (Pāśava, Mātsya, Vānaspatya). Anxiety/depression/insomnia → cintā/śoka/anidrā.

### Worked roga-parīkṣā examples (Mādhava Nidāna)

- **Jvara** (8 types): vāta, pitta, kapha, vāta-pitta, vāta-kapha, pitta-kapha, sannipāta, āgantuja.
- **Atisāra** (6): vāta, pitta, kapha, sannipāta, śoka-ja, āma-ja.
- **Kāsa** (5): vāta, pitta, kapha, kṣataja, kṣayaja.
- **Śvāsa** (5): mahā, ūrdhva, chinna, **tamaka** (asthma), kṣudra.
- **Prameha** (20): 10 kapha + 6 pitta + 4 vāta — **madhumeha** is vātaja terminal stage ≈ T2DM.
- **Kuṣṭha** (18): 7 mahākuṣṭha + 11 kṣudra-kuṣṭha.
- Differential: sandhi-vāta (joint-localised, OA-like) vs āma-vāta (migratory + āma, RA-like) vs vāta-rakta (peripheral, gout-like).

### Encoding plan

- **Schema A — Parīkṣā Step Library:** `{parikṣa_id, framework, step_name_iast, step_name_en, classical_source: {text, chapter, verse, url}, procedure_steps[], observation_fields: [{field, type:enum|ordinal|free, values, dosha_mapping}], modern_correlate: {description, confidence: high|med|low|speculative, refs[]}, required_instruments, contraindications}`
- **Schema B — Doṣa-mapping:** every observation field maps to {V, P, K, sannipāta, āma} weights for downstream constitution/vikṛti scoring.
- **Schema C — Roga-vinishchaya Decision Tree:** disease nodes hold pañca-nidāna slots; each slot is a typed predicate (`has_symptom("jvara_vega")`, `relieved_by("ushna")`). Branches use weighted feature-matching. Sat-kriyā-kāla stage derived from feature-set maturity.
- **Schema D — Prakṛti Questionnaire:** ingest CCRAS instrument verbatim as item-bank `{item_id, dehika/mānasika, doṣa-loading vector, response_scale}`. Output triguṇa + tridoṣa vectors with confidence intervals; never collapse to a single label.
- **Schema E — Patient State Object:** Daśavidha attributes as ordinal fields (pravara/madhyama/avara) + free-text justification. Versioned per visit.
- **Schema F — Source-grounding:** every clinical assertion the LLM emits must cite `parikṣa_id + classical_source + (optional) modern_correlate`. Modern correlates with `confidence: low|speculative` must surface a disclaimer.
- **Schema G — Sādhya-asādhya classifier:** rule-set keyed on mārga + dhātu-involvement-depth + kriyā-kāla stage → prognosis label.

**Uncertainty flags to bake in:** taila-bindu mechanism, nāḍī inter-rater reliability, tongue regional mapping (Ayurvedic vs imported), prakṛti-tool concordance, all "modern correlate" claims. **Expose confidence levels as first-class metadata.**

---

## 12 · BAMS curriculum + integrated/hybrid diagnostics

### NCISM BAMS Regulations 2021

Operative document: **NCISM (Bachelor of Ayurvedic Medicine & Surgery Course) Regulations 2021** under NCISM Act 2020. Replaces older CCIM 2012. Source: https://ncismindia.org/ug-bams-regulations.php.

**Structure:** 4.5 yrs academic + **12-mo CRMI internship** = 5.5 yrs. ~5,400 total teaching hours.

**Subjects per professional year (NCISM 2021, AyUG- prefixed codes):**

- **First Prof (~1.5 yrs, ~1,150 hrs):** Padartha Vijnana evum Ayurveda Itihasa (PV); Sanskrit evum Ayurveda Samhita Adhyayana (SA); **Kriya Sharira** (KSh — Ayurvedic physiology + ~150 hrs modern physiology+biochem); **Rachana Sharira** (RSh — Ayurvedic anatomy + **~150 hrs cadaveric dissection** + modern gross anatomy).
- **Second Prof (~1.5 yrs):** Dravyaguna Vijnana (DG, ~300+ hrs); Rasashastra evum Bhaishajya Kalpana (RSBK); **Roga Nidana evum Vikriti Vijnana** (RN — pathology, fused with modern path/microbiology, ~150 hrs); Charaka Samhita Purvardha.
- **Third Prof (~1.5 yrs):** Agada Tantra + **Vyavahara Ayurveda evum Vidhi Vaidyaka** (toxicology + forensic + jurisprudence); **Prasuti Tantra evum Stri Roga** (OBG, including modern OBG); **Kaumarabhritya** (paediatrics + modern paeds + neonatology); Swasthavritta evum Yoga (preventive/social med + yoga + nutrition + community med + epidemiology).
- **Fourth Prof (~1 yr):** **Kayachikitsa** (largest clinical, includes modern medicine modules); Panchakarma; **Shalya Tantra** (surgery, fused with modern + anaesthesia basics); Shalakya Tantra (ENT+ophthal, classical+modern); Charaka Samhita Uttarardha; **Research Methodology + Medical Statistics** (newly elevated 2021).
- **Internship (12 mo):** rotations IPD Kayachikitsa, Panchakarma, Shalya/Shalakya OPD, Prasuti, Kaumarabhritya, **PHC posting (≥1 mo rural)**, **2 mo allopathic district-hospital posting**.

**Hours per subject:** KC ~600, PK ~250, ShT ~400, PT ~300, KB ~200, DG ~300, RSBK ~300, RN ~250, SV ~250, RSh ~250, KSh ~200, AT ~200, Samhita ~600 across years.

### Modern medicine integrated into BAMS

Allopathic content **embedded inside Ayurvedic subjects** (not separate departments):
- Modern anatomy + dissection: ~150 hrs (RSh).
- Modern physiology + biochem: ~150 hrs (KSh).
- Pathology, microbiology, clinical pathology: ~150 hrs (RN).
- Pharmacology of modern drugs: ~50-80 hrs across DG + KC. Common classes (antibiotics, NSAIDs, antihypertensives, antidiabetics, statins, anticoagulants, thyroid drugs, PPIs) for **interaction awareness + recognition, not full prescribing competency**.
- Modern medicine clinical: KC — DM, HTN, IHD, COPD, asthma, stroke, hepatitis, CKD, thyroid, anaemia, infections.
- Surgery + anaesthesia basics (ShT).
- OBG modern: antenatal, labour, common emergencies.
- Forensic + jurisprudence (~100 hrs).
- Emergency medicine: BLS/ACLS introduced internship.

**Diagnostics taught:** history + Aṣṭasthāna/Daśavidha; physical exam; **interpretation of CBC, LFT, KFT/RFT, lipid profile, FBS/PPBS/HbA1c, TFT, urinalysis, ECG basics, chest X-ray, USG abdomen/pelvis findings, basic CT/MRI report reading.** Trained to **read reports**, not always perform.

### Legal scope of practice (highly state-variable)

- **NCISM (Practice of Ayurveda) Regulations** under NCISM Act 2020 (operative; supersedes older CCIM rules).
- Registration via **State Boards of Indian Medicine** + Central Register at NCISM.
- **Modern drug prescribing:** **state-variable**. Maharashtra (1992 Act amendment + 2014 GR), Punjab, Tamil Nadu permit a defined modern-drug formulary if BAMS completed **CCIM-approved pharmacology bridge course**. Karnataka, Kerala restrict to ASU drugs. CCIM 2014 Notification listing permissible allopathic drugs has been challenged repeatedly. **Verify per state.**
- **Surgery:** **CCIM Notification 19 Nov 2020** permits **PG MS Ayurveda (Shalya/Shalakya)** holders to perform **58 surgical procedures** — 39 general (hydrocele, hernia, appendicectomy, haemorrhoidectomy, tracheostomy, amputation) + 19 ENT/ophthal/dental. Challenged by IMA; multiple writs pending. **Applies to MS Ayurveda PG, NOT undergraduate BAMS.**
- **BAMS vs MD/MS Ayurveda:** BAMS = generalist Vaidya. **MD/MS = 3-yr specialist.** MS holders gain operative scope under 2020 notification; MD specialists gain depth, not new drug rights.

### PG specialties (NCISM)

14 specialties recognised — Kayachikitsa, Panchakarma, Prasuti-Stri Roga, Kaumarabhritya, Shalya, Shalakya, Roga Nidana, Kriya Sharira, Rachana Sharira, Padartha Vijnana, Samhita-Sanskrit, Swasthavritta-Yoga, Dravyaguna, Rasashastra-Bhaishajya Kalpana, **Agada Tantra**. (Sometimes listed as 15 — Agada split.) 3-yr residency + thesis. PhD via universities, ICMR-AYUSH CARE, CCRAS.

### CME

NCISM rolling out credit-hour CME framework (similar to NMC 30 cr/5 yrs); rollout uncertain. Major venues: **World Ayurveda Congress** (biennial, AYUSH+VIBHA), Arogya Expo, Global Ayurveda Festival (Kerala), CME by AVS Kottakkal, Patanjali, **AIIA Delhi** (https://aiia.gov.in), **ITRA Jamnagar** (INI status, https://itra.edu.in), **NIA Jaipur** (https://nia.nic.in).

### Hybrid diagnosis in practice (modern OPD patterns)

| Condition | Modern adjunct labs/imaging |
|---|---|
| **Madhumeha** | FBS, PPBS, HbA1c, urine ketones, lipid profile |
| **Hridroga** | ECG, lipid profile, 2D-echo, BP charting |
| **Yakrit-vikara/Kamala** | LFT, USG abdomen, viral hepatitis serology |
| **Vatavyadhi (neuro)** | MRI brain/spine; classical Vata-subtype mapped |
| **Pakshaghata** | CT brain hyperacute → MRI; integrated with Snehana/Basti planning post-stable |
| **Amavata** | RA factor, anti-CCP, CRP, ESR, X-ray hands |
| **Vandhya** | FSH/LH/AMH/TSH/PRL, USG TVS, semen analysis, HSG |
| **Arbuda** | Biopsy + imaging; co-managed with oncology |

**Integrative case format at AIIA/ITRA:** (i) modern dx (ICD-11), (ii) Ayurvedic dx with Doṣa-Dūṣya-Srotas-Sāma/Nirāma-Avasthā, (iii) Prakṛti, (iv) modern + Ayurvedic Rx, (v) outcome measures (modern scales + classical lakṣaṇa scoring). Documented in **NAMASTE-coded EMRs**.

**Drug-interaction awareness** (taught ad-hoc): Ashwagandha + thyroxine (potentiation); Haridra/turmeric + warfarin (bleeding); Guggulu + statins; Yashtimadhu + diuretics (hypokalaemia); Pippali + CYP3A4 substrates; Triphala + iron absorption.

### AYUSH STGs + research

- **AYUSH STGs** for **80+ Ayurvedic conditions** (https://main.ayush.gov.in — "Standard Treatment Guidelines"). Each: classical Nidāna + modern dx + staged Rx + CI + outcome measures.
- **NCISM clinical practice guidelines** emerging.
- **CCRAS Methodology Manuals** — interventions specified by AFI/API; randomisation feasible; blinding hard for classical preparations (decoy-arm or active-comparator).
- **Whole-System Ayurveda (WSA)** methodology — Patwardhan/Furst/Witt — pragmatic-trial frame allowing individualised regimens.

### Digital decision-aids in current Vaidya practice

- **AyuSoft** (CCRAS, C-DAC Pune) — Prakriti, Nidana, Chikitsa modules.
- Sharangadhara desktop tools, Bhaishajya Ratnavali digitised.
- **NAMASTE Portal** (Ministry of AYUSH, codes mapped to ICD-11 TM2).
- **AyushEHR / e-Aushadhi / AHMIS** — hospital information systems for AYUSH facilities.
- Practitioner apps: Easy Ayurveda, Carakam, AYUSH Sanjivani.

### Encoding plan

**(a) BAMS Knowledge Surface — graph:**
```
Subject (NCISM code)
 ├── Year / Hours-theory / Hours-practical
 ├── ClassicalTopics[] (Sutra refs: CS/SS/AH chapter.verse)
 ├── ModernOverlapTopics[] (ICD-11 / MeSH ids)
 ├── ClinicalCompetencies[] (skill, level: Knows / Does)
 ├── DiagnosticsTaught[] (test → interpretation depth)
 └── Pharmacology[] (drug class → awareness vs prescribing)
```
Tag each node with **Taught / Legally-Permitted / Common-Practice** flags (these diverge frequently).

**(b) Hybrid Diagnostic Decision-Tree per high-prevalence condition:**
```
Condition
 ├── AyurvedicDx { Dosha, Dushya, Srotas, Sama/Nirama, Avastha, Sadhya/Asadhya }
 ├── ModernDx { ICD-11, criteria, red-flags-for-referral }
 ├── DiagnosticPanel { mandatory[], optional[], imaging[] }
 ├── TreatmentPlan { Shamana, Shodhana(Panchakarma), Pathya/Apathya, Yoga, ModernCoRx }
 ├── DrugInteractions[]
 ├── OutcomeMeasures { classicalLakshanaScore, modernScale (e.g. DAS28, HbA1c) }
 └── EvidenceRefs { CTRI, AYUSH-STG, CCRAS monograph }
```
Build initially for: Madhumeha, Sthaulya, Hridroga, Amavata, Sandhivata, Grahani, Kasa-Shvasa, Pakshaghata, Vandhya, Yakrit-vikara, Tamaka-shvasa, Pandu, Arsha, Vicharchika, Manasaroga (anxiety/depression).

**(c) Integrative Case Format (interpret + generate):**
```
Case
 ├── Demographics + Prakriti + Vikriti
 ├── History { modern HPI + Ashtavidha + Dashavidha pariksha }
 ├── Examination { systemic + Nadi/Jihva/Mutra/Mala/Shabda/Sparsha/Drik/Akriti }
 ├── Investigations { labs[], imaging[] with values + reference ranges }
 ├── Diagnosis { Ayurvedic Samprapti chain, Modern dx (ICD-11), Combined formulation }
 ├── Plan { Aushadha (with AFI/API code, dose, anupana, duration), 
            Panchakarma protocol, Pathya-Apathya, Yoga/Pranayama, 
            Modern-medicine continuation/taper }
 ├── Safety { contraindications, drug-herb interactions, red-flags }
 └── FollowUp { outcome metrics, classical + modern, intervals }
```
Use **NAMASTE codes** for Ayurvedic terms, **ICD-11 (incl. TM2)** for modern dx, **AFI/API** for formulations, **SNOMED/LOINC** for labs. Records exchangeable on **AYUSH Grid / ABDM**.

**Uncertainty flags:** exact 2024 NCISM revision details (incremental updates possible after research cutoff); final court status of 2020 surgery notification (likely still pending); state-by-state allopathic-prescribing rules; whether NCISM CME credit mandate is now binding nationally; total count of AYUSH STGs (range 50-100).

---

## Final cross-cutting engineering roadmap (after all 12 agents)

The full prioritised plan, integrating all research:

### Phase A — Core data + retrieval (3 weeks)
1. **Citation allowlist + post-hoc validator** (1-2 d) — deterministic hallucination guard.
2. **SARIT TEI corpus ingestion → ~15K verses** (1 wk) — Caraka + Suśruta + Aṣṭāṅga Hṛdaya complete mūla. CC-BY-SA 3.0.
3. **Chapter-context prefix in retrieval** (0.5 d) — +5-15% recall.
4. **Eval harness (RAGAS + DeepEval) + 100-Q seed benchmark** (1 wk).
5. **bge-m3 embedding swap** (2-3 d) — +10-20% recall on Hindi/EN.
6. **bge-reranker-v2-m3 stage-2** (1-2 d) — +15-25% nDCG@6.

### Phase B — Knowledge data layer (5 weeks)
7. **Materia medica DB: 500 dravyas** with full pharmaco-properties schema (6 wks parallel — vaidya-review for top 100, LLM-only for tail with disclosure).
8. **Formulations DB: 200+ classical formulations** with composition + indication + reference + AYUSH STG link.
9. **Procedures DB: pañcakarma + caryā + rasāyana protocol objects.**
10. **Knowledge Graph MVP** (NAMASTE + IMPPAT + 200 dravyas): Hetionet-style schema, ~8K-15K triples.

### Phase C — Evidence + diagnostic layers (8 weeks)
11. **Modern-evidence layer** (PubMed + IMPPAT + CTRI): 50 dravyas × top-10 PMIDs + SR + CT.gov + IMPPAT phytochem + quality scoring.
12. **Parīkṣā schema + decision-tree encoding** for top 15 conditions (Madhumeha, Sthaulya, Hridroga, Amavata, etc.).
13. **Prakṛti questionnaire ingest** (CCRAS instrument verbatim) with confidence-interval output.
14. **BAMS knowledge graph** — subjects → topics → competencies, Taught/Legally-Permitted/Common-Practice tags.
15. **Integrative case format** (interpret + generate).

### Phase D — Index-time + advanced retrieval (3 weeks)
16. **Index-time query-paraphrase expansion** (Anthropic Contextual Retrieval) — +20-35% recall.
17. **HyDE for colloquial-EN→Sanskrit gap** — +3-8% recall.
18. **Multi-query / RAG-Fusion** — +5-10% recall.
19. **Verse verification post-generation** (FActScore/FAVA-style atomic claim NLI for offline eval).

### Phase E — Compliance + production (concurrent throughout)
20. **Disclaimer system** (DPDP + DMRA + EU AI Act + FDA wellness).
21. **Data retention/deletion policies** (90-day rolling logs, right-to-erasure endpoint).
22. **Tenant DPA template + sub-processor list.**
23. **Model card + system card publication.**
24. **High-risk gating** (cancer, pregnancy, paediatric <12, psychiatric, transplant, oncology drug-interactions → referral-only).
25. **Insurance bound** (tech-E&O + cyber + media liability).
26. **PvPI-AYUSH adverse-event SOP.**

### Phase F — Strategic data (long-running)
27. **CCRAS MoU** signed → access to NIIMH e-Saṃhitā + e-Nighantu redistribution rights + scholarly translations.
28. **Multi-translation surfacing** (PD Bhishagratna for Suśruta, Kaviratna for Caraka).
29. **Translation licensing** with Chaukhamba/Krishnadas Academy for 4 texts where no PD exists.
30. **Vaidya panel onboarded** for top-100 dravya + 30-formulation review (~₹2.5-4L honoraria).

---

**Decision points the founder owes themselves:**
1. CCRAS MoU now or wait for licensing complete? **Recommend now** — it's the highest-asymmetry move.
2. Self-host LLM ever? **Not yet** — at current volumes Claude is cheaper.
3. Bhasma/rasayoga handling — surface or hide? **Hide for international, conditional surface for India** with mandatory licensed-product link.
4. Open-source the toolkit per CCRAS proposal? **Yes** — moat is corpus + heritage, not code.
5. Sanskrit-text licence with CCRAS — commercial use or research-only? **Push for commercial** — the platform is a B2B SaaS.

---

## Cross-cutting engineering roadmap (priority-ordered, after all 8 agents)

This is the synthesis. **Order matters:**

1. **Citation allowlist + post-hoc validator** — 1-2 days. Single highest ROI. Deterministic hallucination guard. Ship before anything else.
2. **SARIT TEI corpus ingestion → 15K verses** — 1 week. The fundamental data-driven move. Caraka + Suśruta + Aṣṭāṅga Hṛdaya, complete mūla.
3. **Chapter-context prefix in retrieval indexing** — 0.5 day. Trivial. +5-15% recall.
4. **Evaluation harness (RAGAS + DeepEval) + 100-Q seed benchmark** — 1 week. Measure everything that comes after.
5. **Embedding swap: paraphrase-multilingual-MiniLM → bge-m3** — 2-3 days. Single biggest model upgrade.
6. **Stage-2 reranker: bge-reranker-v2-m3** — 1-2 days. Critical past 1K verses.
7. **Index-time query-paraphrase expansion** (Anthropic Contextual Retrieval) — 2-3 days.
8. **Knowledge graph MVP (NAMASTE + IMPPAT + 200 dravyas)** — 4-6 weeks.
9. **Modern evidence layer (PubMed + IMPPAT + CT.gov)** — 4-8 weeks.
10. **Compliance hardening** — disclaimers, DPA template, model card, retention policy. Concurrent.
11. **Multi-translation surfacing** (PD Bhishagratna for Suśruta) — 1 week.

Steps 1-7 are technical-debt-light and ship in 2-3 weeks. Steps 8-11 are strategic and run on a separate track.

---

## Sources index

- SARIT corpus: https://github.com/sarit/SARIT-corpus
- vidyut: https://vidyut.readthedocs.io/
- GRETIL: https://gretil.sub.uni-goettingen.de/
- Internet Archive Caraka: https://archive.org/details/Caraka-sahit
- Internet Archive Bhishagratna Suśruta: https://archive.org/details/englishtranslati01susruoft
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- BGE Reranker: https://huggingface.co/BAAI/bge-reranker-v2-m3
- ALCE: https://github.com/princeton-nlp/ALCE
- RAGAS: https://docs.ragas.io
- DeepEval: https://github.com/confident-ai/deepeval
- Phoenix (Arize): https://github.com/Arize-ai/phoenix
- Anthropic Contextual Retrieval: https://www.anthropic.com/news/contextual-retrieval
- Microsoft GraphRAG: https://github.com/microsoft/graphrag
- IMPPAT: https://cb.imsc.res.in/imppat
- NAMASTE: https://namstp.ayush.gov.in
- ICD-11 TM2: https://icd.who.int/browse11/l-m/en
- LOTUS: https://lotus.naturalproducts.net
- PubMed E-utilities: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
- ClinicalTrials.gov API v2: https://clinicaltrials.gov/api/v2
- DPDP Act 2023: https://www.meity.gov.in/data-protection-framework
- EU AI Act: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
- ISO/IEC 42001:2023: https://www.iso.org/standard/81230.html
