# Product Requirements Document — BenefitScan V1

**Product:** BenefitScan
**Author:** Om Waghela
**Status:** V1 Complete
**Last Updated:** March 2026

---

## 1. Problem Statement

Insurance brokers managing employee benefits renewals spend **30–45 minutes per plan** manually transcribing data from carrier PDFs into Excel spreadsheets. A broker with 10 clients in renewal season handles roughly 120 SBC documents — translating to **60–90 hours of pure data entry per year**, with an industry-observed error rate of **3–5%**.

The downstream impact is significant: a single transcription error on a plan comparison spreadsheet sent to an employer's HR team can cost a broker their client relationship.

This is a solved problem in adjacent industries (mortgage, legal, accounting all have document automation tooling) but remains largely manual in the employee benefits brokerage space, particularly at small-to-mid-size firms without enterprise software budgets.

---

## 2. The User

**Primary user:** Independent insurance brokers and benefits analysts at small-to-mid-size brokerages (2–50 employees).

**Profile:**
- Manages 10–30 employer clients, each with annual renewal cycles
- Proficient in Excel; not a technical user
- Works primarily in Windows, uses Outlook, receives PDFs by email from carriers
- Values accuracy over speed — a wrong number on a client deliverable is a trust-destroying event
- Budget-conscious; pays for tools out of their own book of business in many cases

**Secondary user (V2):** Benefits analysts at larger brokerages who process 200+ SBCs per renewal season and need batch automation.

---

## 3. The Opportunity

### Why now
The ACA mandated the SBC format in 2012. Every SBC since then has followed the same 4-page standardized template regardless of carrier. This standardization — combined with the maturation of large language models capable of reliable structured extraction — makes this problem automatable for the first time without carrier-specific integrations.

### Why this hasn't been built
- Enterprise benefits platforms (Employee Navigator, PlanSource, bswift) solve the *administration* problem, not the *comparison* problem. They don't help brokers build the pre-sale deliverable.
- Generic document AI tools (Textract, Document AI) require significant engineering to map to insurance-specific schemas. Brokers don't have engineering teams.
- The market is fragmented and broker-owned firms are underserved by software vendors who focus on large enterprise accounts.

---

## 4. Goals and Success Metrics

### V1 Goal
Prove that AI extraction + human review reduces SBC comparison time from 30–45 minutes per plan to under 5 minutes per plan, with broker-verified output accuracy.

### Success Metrics

| Metric | Baseline (manual) | V1 Target |
|--------|------------------|-----------|
| Time per SBC comparison | 30–45 min | < 5 min |
| Broker-reported output accuracy | ~95–97% | ≥ 95% (after review) |
| Fields extracted per SBC | 30 (manual) | ≥ 25/30 auto-extracted |
| Time to first export (new user) | N/A | < 15 min from install |

### Non-goals for V1
- Real-time carrier data feeds
- Automated email ingestion of SBCs
- Multi-user collaboration
- Cloud hosting or SaaS billing
- Mobile experience

---

## 5. Solution Overview

A locally-run web application that:

1. **Accepts PDF uploads** (single or batch) via drag-and-drop
2. **Extracts 30 standardized fields** from each SBC using the Anthropic Claude API
3. **Validates extracted data** against known rules (ACA OOP max limits, deductible sanity checks, missing field detection)
4. **Presents results** in an editable review table — color-coded by confidence
5. **Exports a formatted Excel file** (.xlsx) ready for client delivery

### Why local-first (not SaaS)
- SBC documents may contain employer PII — local processing avoids data privacy questions in V1
- Removes cloud infrastructure cost and complexity from the validation phase
- Brokers are accustomed to desktop tools; zero onboarding friction
- V2 migration path to cloud is a config change, not a rewrite (FastAPI + SQLite → FastAPI + PostgreSQL on Railway/Render)

---

## 6. Scope

### In scope (V1)
- SBC PDF upload: single file and batch (up to ~20 files)
- AI extraction of 30 Tier 1 fields (see `docs/DATA_FIELDS.md` for full list)
- Field-level validation with status flags: OK / Missing / Review / Non-Compliant
- ACA 2025 out-of-pocket maximum compliance check
- Editable review table — brokers can correct any AI-extracted value
- Excel export: formatted .xlsx with frozen panes, color-coded validation flags, auto-width columns
- Local deployment on macOS and Windows

### Out of scope (V1)
- Schedule of Benefits, COC/EOC, SPD documents
- Dental and vision SBCs (different schema)
- Premium data (not in SBC — requires separate rate sheet)
- Year-over-year comparison
- User authentication / multi-user
- Cloud deployment
- Carrier integrations

---

## 7. User Stories

**As a broker**, I want to upload multiple SBC PDFs at once so that I can process a full carrier's plan set in one session rather than one by one.

**As a broker**, I want AI to extract plan data automatically so that I spend my time reviewing and advising, not transcribing.

**As a broker**, I want flagged cells to tell me *why* they're flagged so that I know whether to verify with the carrier or simply fill in a missing field.

**As a broker**, I want to edit any extracted value directly in the table so that I can correct AI errors before the data reaches my client.

**As a broker**, I want to export a formatted Excel file so that I can send a professional-looking comparison to my client without reformatting in Excel.

**As a broker**, I want the tool to flag ACA non-compliance so that I catch carrier errors before my client does.

---

## 8. Key Product Decisions

### Decision: Human-in-the-loop review (not fully automated export)
AI extraction accuracy is approximately 93–97% on standard SBCs. The remaining 3–7% represents 1–2 errors per plan comparison — unacceptable for a client-facing document. The review step surfaces exactly those fields, keeping review time to 2–3 minutes while ensuring the broker can stand behind the output. Full automation is a V3 feature after accuracy is validated across 1,000+ real SBCs.

### Decision: SBCs before any other document type
SBCs are ACA-mandated and follow a fixed 4-page template. Every other benefits document (SPD, COC/EOC, Schedule of Benefits) is carrier-specific, longer, and less structured. Starting with SBCs maximizes extraction accuracy and minimizes prompt engineering complexity. The beachhead is the highest-volume, most standardized document in the broker's workflow.

### Decision: Claude API for extraction
Claude Opus was selected for its reliability in following complex JSON schemas with 30+ fields. Local LLMs tested on consumer hardware (Ollama + LLaMA 3) produced unacceptable schema adherence — approximately 15–20% of fields either hallucinated or omitted. The per-extraction cost (~$0.05–0.15 at Opus pricing) is negligible compared to the labor hours eliminated. A Gemini free-tier fallback is also supported for cost-free testing.

### Decision: All fields stored as strings
SBC values like "$1,500" and "20% after deductible" are broker-facing text, not numeric inputs to calculations. Parsing them to numeric types at storage time would require complex normalization logic that could introduce errors and would make human review harder. Fields are stored verbatim from the source document.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SBC format variation across carriers causes extraction failures | Medium | High | Validation layer flags missing fields; human review catches gaps |
| Scanned/image SBCs can't be parsed | Low | Medium | Error message directs broker to request a digital PDF from carrier |
| AI model returns hallucinated values | Low | High | Validation flags statistically improbable values for review |
| ACA OOP limits change annually | Certain | Medium | Limits stored in `validator.py` as named constants — one-line update each January |
| Broker edits a correct value accidentally | Low | Low | V2: add edit history / undo |

---

## 10. Roadmap Summary

| Version | Theme | Key Features |
|---------|-------|-------------|
| **V1** | Beachhead | SBC extraction, review UI, Excel export, local deployment |
| **V2** | Document breadth | SOB, COC/EOC, dental/vision SBCs, confidence scoring, YoY comparison |
| **V3** | Platform | SPD/ERISA compliance, carrier integrations, cloud/SaaS, multi-user |

Full roadmap: `docs/ROADMAP.md`

---

## 11. Open Questions (for V2 scoping)

1. What is the broker's tolerance for a cloud-hosted version — is data privacy a blocker or a preference?
2. Do brokers want to store past extractions for year-over-year comparison, or is each renewal season treated as a fresh start?
3. What percentage of SBCs received are scanned vs. digitally generated? (Determines whether OCR support is a V2 priority.)
4. Is the Excel format the right export target, or do brokers increasingly use Google Sheets?
5. Would brokers pay per extraction, per seat, or prefer a flat monthly fee?
