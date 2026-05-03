# IndiaAI Mission Compute Subsidy — Submission Checklist

A single-page actionable list of every form, certificate, and document the IndiaAI portal asks for, with status / where-to-apply / est. time / cost.

**Status legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[—]` not applicable

---

## A. Entity setup (must precede submission)

| # | Item | Status | Where to apply | Est. time | Cost |
|---|---|---|---|---|---|
| A1 | Pvt Ltd incorporation (sister entity to Nitya Naturals) | `[ ]` | MCA SPICe+ Part B (https://www.mca.gov.in) | 7-14 days | ₹5,000-15,000 (govt fees + DSCs + DIN) |
| A2 | PAN + TAN (auto-issued with SPICe+) | `[—]` auto | follows A1 | with A1 | included |
| A3 | Bank current account in Pvt Ltd name | `[ ]` | any commercial bank (preferred: HDFC / Axis / SBI) | 3-7 days post-A1 | ₹0-25,000 deposit |
| A4 | GST registration | `[ ]` | https://www.gst.gov.in | 3-7 days | free |
| A5 | Udyam (MSME) registration | `[ ]` | https://udyamregistration.gov.in | instant | free |
| A6 | DPIIT Startup India recognition | `[ ]` | https://www.startupindia.gov.in (Recognition tab) | 2-3 weeks | free |
| A7 | Digital signature certificates (DSC) for directors | `[~]` | any licensed CA (e.g. eMudhra, NSDL) | 1-3 days | ₹1,500-3,000 each |

**A6 DPIIT eligibility tests** (verify before applying):
- Entity ≤ 10 years old since incorporation
- Annual turnover ≤ ₹100 Cr in any year since incorporation
- Working towards innovation / development / improvement of products/services with high potential for employment generation or wealth creation
- AI/ML product fits clearly
- Letter of recommendation NOT mandatory; can self-declare

**A6 Documents needed:**
- Pvt Ltd Certificate of Incorporation (from A1)
- PAN (from A2)
- Brief project description (≤ 1,000 chars) — can adapt the proposal §1 executive summary
- Pitch deck OR ≤ 1-page concept note (we'll prep below)
- Founder/team profile

---

## B. Application materials (already drafted)

| # | Item | Status | Path |
|---|---|---|---|
| B1 | Technical proposal | `[x]` | `govt/ayurbge-proposal.md` |
| B2 | Model card | `[x]` | `govt/ayurbge-model-card.md` |
| B3 | Dataset card | `[x]` | `govt/ayurbge-dataset-card.md` |
| B4 | Baseline scorecard (JSON) | `[x]` | `govt/baseline_full_corpus.json` |
| B5 | Pair-generation script (reproducibility) | `[x]` | `backend/scripts/build_finetune_pairs.py` |
| B6 | Training script | `[x]` | `backend/scripts/finetune_bge.py` |
| B7 | Eval-comparison script | `[x]` | `backend/scripts/compare_eval.py` |
| B8 | Source corpus + KG (in-repo) | `[x]` | `backend/app/data/` (committed) |
| B9 | Existing project URL (production widget on ageayurveda.com) | `[ ]` confirm | https://ageayurveda.com |
| B10 | Github URL (public source repo) | **`[ ]` not pushed** | needs `git remote add origin` + `gh repo create --public --push`; cited URL is `https://github.com/Jairaj1234-dancer/ageayurveda-companion` |
| B11 | Reproducibility README | `[ ]` add | one-page README at `/README.md` pointing to all the above |

---

## C. Supporting letters / partnerships (boost the application)

| # | Item | Status | Path / how |
|---|---|---|---|
| C1 | AYUSH / CCRAS letter of support | `[~]` | `govt/ccras-letter.md` (drafted; needs sign-off) |
| C2 | AIIA Delhi clinical-evaluation cohort partnership letter | `[ ]` | Email Director's office: `aiia.dir@gov.in` |
| C3 | University of Hyderabad Sanskrit dept letter | `[ ]` | Contact via dept of Sanskrit Studies |
| C4 | IIT-BHU Indic Knowledge Systems centre letter | `[ ]` | Contact IKS centre Director |
| C5 | Optional: industry support letter from existing AYUSH manufacturer (Baidyanath group lineage) | `[ ]` | internal (Nitya Naturals) |

C1-C4 are not mandatory but **materially boost evaluation scoring** for AYUSH-priority sector applications. C5 is in-house and free.

---

## D. Compliance attestations (in proposal, may need separate forms)

| # | Item | Status | Where it appears in materials |
|---|---|---|---|
| D1 | Open-source commitment (Apache 2.0 / CC-BY-SA 3.0) | `[x]` | proposal §7, model card, dataset card |
| D2 | Indian-soil training compute commitment | `[x]` | proposal §8 |
| D3 | Indian-origin data declaration | `[x]` | proposal §8, dataset card |
| D4 | No PII in training data | `[x]` | model card, dataset card |
| D5 | Beneficial-use / public-benefit statement | `[x]` | proposal §1, §7 |
| D6 | Bias acknowledgement and mitigation plan | `[x]` | model card |
| D7 | Pre-registered evaluation targets | `[x]` | proposal §6.1, model card |
| D8 | Hugging Face account / org page | `[ ]` create | `https://huggingface.co/AgeAyurveda` (sign up) |

---

## E. Team materials

| # | Item | Status | Notes |
|---|---|---|---|
| E1 | Founder CV / LinkedIn profile | `[ ]` confirm up-to-date | include AI/ML credentials, Companion project history |
| E2 | Co-founder / CTO CV (if any) | `[—]` | only if applicable |
| E3 | Technical advisor list | `[ ]` | can include CCRAS / AIIA / academic advisors named in C1-C4 |
| E4 | Demonstrated capability proof | `[x]` | proposal §9 lists all built artifacts: 4,108-edge KG, 670 PMIDs ingested, 214 passing tests, hybrid retrieval pipeline, citation validator, eval harness |

---

## F. Submission flow on the IndiaAI portal

| # | Step | Notes |
|---|---|---|
| F1 | Sign up at https://indiaai.gov.in | Use Pvt Ltd email, DPIIT certificate # |
| F2 | Navigate to "Compute" / "GPU Subsidy" tab | Subsidy programmes are listed under Mission Pillars |
| F3 | Download application template (varies by call) | Match section structure to template; the proposal already follows the standard structure |
| F4 | Upload: proposal (PDF), model card, dataset card, baseline JSON, links to repos | Convert .md → PDF before upload |
| F5 | Attach: Pvt Ltd certificate, DPIIT certificate, PAN, GST, Udyam | All from section A |
| F6 | Attach: support letters (C1-C5) | as available |
| F7 | Submit + retain acknowledgement number | Submission can take 8-12 weeks for evaluation |

---

## G. Post-submission expected milestones

| Phase | Expected | Milestone |
|---|---|---|
| Submission + 4-6 wk | Initial screening | Eligibility + technical fit verification |
| Submission + 8-12 wk | Technical evaluation | Possibly an interview or panel review |
| Submission + 12-16 wk | Decision + GPU allocation | If approved: receive compute credits or direct allocation |
| Post-allocation 0-8 wk | Phase-1 training + ablations | Per proposal §10 timeline |
| Post-allocation 8-12 wk | Phase-1 publication | HuggingFace release of weights + cards + scorecard |
| Phase-2 (optional) | If Phase-1 hits target | Llama-distilled chat model, English-gloss enrichment |

---

## H. Pre-submission self-test (do this 24 hr before submitting)

| # | Test | Expected | Status |
|---|---|---|---|
| H1 | All B1-B11 files lint-clean and PDF-convert correctly | no broken refs | `[ ]` |
| H2 | `python -m scripts.build_finetune_pairs --max-per-source 100` | runs in < 30s, emits valid JSONL | `[ ]` |
| H3 | `python -m scripts.finetune_bge --dry-run` | passes with "Pipeline validated" | `[ ]` |
| H4 | `python -m scripts.compare_eval --baseline BAAI/bge-m3 --candidate BAAI/bge-m3 --corpus-limit 200` | identical metrics, delta=0 (sanity) | `[x]` (already verified 2026-05-03) |
| H5 | All links in proposal resolve (SARIT, base bge-m3, our github) | 200 OK | `[ ]` |
| H6 | DPIIT certificate visible in Startup India dashboard | "Recognized" status | `[ ]` |
| H7 | All .md files have ASCII-clean frontmatter + UTF-8 body | no encoding artifacts | `[ ]` |
| H8 | Existing widget loads at ageayurveda.com (proves built capability) | 200 OK | `[ ]` |

---

## I. Critical timeline (parallelisable items in **bold**)

```
Week 0  ── A7 DSCs ────► A1 Pvt Ltd ───► A2 PAN auto ───► A3 bank ─┐
                                                                   │
Week 1  ── **A4 GST**  + **A5 Udyam** + **A6 DPIIT** + **D8 HF** ──┤
                                                                   │
Week 2  ── **C1 CCRAS sign-off** + **C2/C3/C4 academic letters** ──┤
                                                                   │
Week 3  ── E1 CV refresh + H1-H8 self-test + final review ─────────┤
                                                                   │
Week 4  ── F1-F7 PORTAL SUBMISSION ◄───────────────────────────────┘
```

**Critical path: A1 → A6 → F1.** Everything else parallelises off these.

---

## J. Estimated total cost (pre-submission)

| Item | Cost |
|---|---|
| Pvt Ltd incorporation (A1) | ₹5,000-15,000 |
| 2 DSCs (A7) | ₹3,000-6,000 |
| PAN/TAN/GST/Udyam/DPIIT/HF | ₹0 (all free) |
| Bank account opening deposit | ₹0-25,000 (refundable) |
| Optional: legal review of incorporation docs | ₹5,000-15,000 |
| Pre-submission CA review | ₹5,000-10,000 |
| **Total** | **₹18,000 - ₹71,000** |

If approved, the IndiaAI Mission compute subsidy covers ~₹35,000-47,000 of GPU compute — net positive vs. self-paying.

---

## K. Failure modes to plan for

1. **DPIIT recognition rejected** — Most rejections are for inadequate "innovation" claim. Mitigation: emphasize the Sanskrit + multilingual + open-source angle and the public-good benefit to AYUSH ecosystem (not just commercial chatbot).

2. **IndiaAI Compute portal flagged for "no clear training workload"** — Mitigation: the proposal already has 130 GPU-hour budget breakdown in §5.4, which is a clear training workload. Reinforce in F4 cover note.

3. **AYUSH/CCRAS letter delayed** — Submit application without C1 if needed; C1 can be added as an addendum post-submission.

4. **Baseline numbers questioned** — Mitigation: the JSON scorecard is reproducible end-to-end via `scripts/compare_eval.py`. Open-source the eval cohort + script for verification.

5. **Reviewers ask for English-gloss enrichment** — Pre-prepared response: Phase-2 is budgeted for that (~₹12,500 LLM batch); Phase-1 is an honest measure-and-build with the data we have.

---

## L. Single line of action right now

**The blocker for everything is A1 (Pvt Ltd) → A6 (DPIIT).** Until those two are filed, nothing else moves the application forward. Engage a CA today; A1 is a 7-14 day clock; A6 starts the moment A1 issues.

**Two near-term action items independent of the critical path:**

1. **Push the source repo to GitHub** (currently no remote set). The proposal/cards cite `github.com/Jairaj1234-dancer/ageayurveda-companion` which is aspirational. Run:
   ```
   cd ~/Projects/ageayurveda-companion
   git add . && git commit -m "Initial commit: AgeAyurveda Companion + AyurBGE proposal"
   gh repo create Jairaj1234-dancer/ageayurveda-companion --public --source=. --push
   ```

2. **Create the HuggingFace org `AgeAyurveda`** at https://huggingface.co/organizations/new (free, no review needed). The model and dataset cards point to this org's namespace.
