# Letter to CCRAS — research partnership proposal

**Use:** Print on the manufacturing entity's letterhead. Co-sign with founder of the AI platform. Send by registered post AND email.

**Address:**
> The Director General
> Central Council for Research in Ayurvedic Sciences (CCRAS)
> Ministry of AYUSH, Government of India
> 61–65 Institutional Area, Opposite D-Block
> Janakpuri, New Delhi – 110058
> Email: ccrasdg-ayush@gov.in (verify before sending)

---

**Subject:** Proposal for a research partnership on AI-augmented retrieval and provenance validation of classical Ayurvedic texts

Respected Sir / Madam,

We write from one of India's longest-standing classical Ayurvedic enterprises — established 1917 — which today operates a GMP-certified contract-manufacturing facility in Prayagraj and is associated with one of the most recognised heritage Ayurvedic brands in the country. Across three generations our group has carried forward an unbroken pandit lineage and an in-house formulary anchored in the *Charaka Saṃhitā*, *Suśruta Saṃhitā*, *Aṣṭāṅga Hṛdaya*, and *Bhāvaprakāśa*.

We are writing to propose a formal research partnership between CCRAS and our newly-incorporated digital-research arm, **Age Ayurveda Companion Pvt Ltd**, on a question we believe is squarely within the Council's mandate: **the digital preservation, provenance-traceable retrieval, and AI-assisted public dissemination of the classical Ayurvedic corpus.**

## What we have built

Over the past several months our team has built a working AI platform that retrieves verses from the classical Sanskrit corpus and presents them, with full citation, to a user asking a wellness question. Today the platform indexes:

- *Aṣṭāṅga Hṛdaya, Sūtrasthāna* — 20 representative verses
- *Charaka Saṃhitā, Sūtrasthāna* — 14 representative verses

Each verse is stored with its mūla pāṭha (Sanskrit), Roman transliteration, English paraphrase, and a structured metadata schema (chapter, verse-range, source). A retrieval layer combining semantic embeddings with keyword search returns the most relevant verses for any query — in English, Hindi, or Devanagari Sanskrit — and a language-model layer composes a cited answer that **never asserts a claim without pointing to a specific verse.** A separate audit interface records, for every answer, exactly which verses grounded it.

This is, to the best of our knowledge, the first production-grade implementation of *citation-disciplined, classical-text-grounded* AI for Ayurveda anywhere in the world.

## Why we are writing to CCRAS

We have noted with great interest the Council's recent partnerships:

- The **MoU with Berhampur University** (2025) for the digitisation of rare palm-leaf Ayurvedic manuscripts.
- The **MoU with Anuvadini AI** (2025) for the multilingual translation of Ayurveda texts across thirteen Indian languages.
- The **AI in AYUSH internship programme** including the OCR-of-classical-manuscripts track.

Our work sits in the same direction of travel. We believe a research partnership with CCRAS would meaningfully accelerate the Council's stated digital-preservation mandate, and would in turn give our platform the scientific rigour that only the Council can confer.

## What we propose

A non-financial Memorandum of Understanding spanning twelve months, with the following deliverables:

1. **Open-licensed digital corpus.** We will publish, under a permissive licence, structured XML versions of selected sthānas of *Aṣṭāṅga Hṛdaya*, *Charaka Saṃhitā*, *Suśruta Saṃhitā*, and *Bhāvaprakāśa* — each verse tagged with chapter, verse-range, semantic concept, and CCRAS-validated provenance. This becomes a public research artefact independent of our commercial product.

2. **Benchmark dataset for classical-text question-answering.** We will compile, with input from CCRAS scholars, a benchmark of 500 reference questions paired with verse-level ground-truth answers. This dataset will be the reference standard against which any future Ayurveda AI system can be measured — a public good comparable in spirit to the BODH benchmarking initiative recently launched by NHA and IIT-Kanpur.

3. **Provenance-validation tool, open-sourced.** We will publish, as open-source software, our citation-validation toolkit so that any researcher, brand, or clinic in the country can independently verify whether a claim is genuinely grounded in classical Ayurvedic texts.

4. **Joint scholarly outputs.** We propose two co-authored publications during the year — one technical, one Ayurvedic-scholarly — and joint authorship on any consequential dataset or tool release.

5. **Acknowledgement and review rights.** All public-facing outputs of the platform that draw on CCRAS-validated content will carry appropriate acknowledgement and will be subject to scholarly review by CCRAS-nominated reviewers prior to release.

## What we ask

The MoU itself — and, where appropriate, the engagement of CCRAS-nominated scholars to validate the verse selections, English paraphrases, and benchmark questions. We are not asking for financial support through this MoU; we are separately preparing an Extra-Mural Research grant proposal on a related question, which we will route through the standard ANUDAN portal channel and with academic co-investigators.

## Why now

Generic large language models are, today, demonstrably unreliable on Ayurvedic claims — they invent citations, conflate sources, and lack the provenance discipline that a five-thousand-year medical tradition deserves. The risk of misuse is real: a Shopify storefront with a generic chatbot can quote a fabricated Charaka verse to recommend a product that the original text never endorses. India's classical knowledge deserves better than that.

A CCRAS-anchored, provenance-traceable AI layer for Ayurveda is the answer. We are in a position to build it; we are reaching out because we believe the work is meaningfully better with the Council's authority behind it.

We would welcome the opportunity to present the working platform — including a live demonstration of citation-traceable retrieval — to you and your colleagues at a date convenient to the Council. A team from our research arm can travel to Delhi within two weeks of any scheduled meeting.

With deepest respect for the Council's work,

> *(signed)*
>
> **Founder & CEO**
> Age Ayurveda Companion Pvt Ltd
>
> *(co-signed, on heritage letterhead)*
>
> **For the Baidyanath group**

---

**Enclosures (suggested):**
- One-page platform brief (govt/pitch.html · printed at A4)
- Sample of the structured-XML corpus output (one *Aṣṭāṅga Hṛdaya* chapter)
- One screen-capture of a live grounded answer with verse-level citations
- Brief profile of the manufacturing-entity heritage and its classical-text scholarly resources

---

**Internal notes for the sender — do not include in the letter:**

- Send via Speed Post **and** email (simultaneously). Hard copy carries weight at AYUSH bodies; email gives a forwardable artefact.
- Follow up by phone after 10 working days if no response. Council switchboard: 011-28525852.
- If first contact is unanswered after 3 weeks, route via your existing AYUSH-ministry contacts — but do NOT skip the formal letter; the letter establishes precedence.
- Do not lead with the commercial product. The letter leads with public-research deliverables. The commercial path is downstream and gets its own conversation.
- "We are not asking for financial support through this MoU" is load-bearing — it removes the budget barrier that would otherwise slow approval. Money is asked for elsewhere (EMR, SAMRIDH).
