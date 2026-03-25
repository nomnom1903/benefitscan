# BenefitScan — Product Roadmap

---

## V1 — Beachhead (Current)

**Goal:** Validate that AI extraction + human review + Excel export saves real time for real brokers.

- [x] SBC PDF upload (single and batch)
- [x] AI extraction of 30 Tier 1 fields via Claude API
- [x] Field-level validation with status flags (OK / Missing / Review / Non-Compliant)
- [x] Human review UI — editable table with color-coded cells
- [x] Excel export with formatting, frozen panes, validation highlighting
- [x] Local deployment (single-user, no cloud required)

**Success criteria:** A broker can go from 10 uploaded SBCs → reviewed → exported Excel in under 15 minutes.
Previously took 5–7.5 hours manually.

---

## V2 — Expand Document Types (After V1 validated with 3+ real brokers)

**Goal:** Handle the full document set a broker receives from carriers, not just SBCs.

### Document support
- [ ] Schedule of Benefits (SOB) — carrier-specific, less standardized than SBC
- [ ] Certificate of Coverage (COC/EOC) — 50–200 page documents, complex structure
- [ ] Dental SBC — separate field schema (different benefits, different structure)
- [ ] Vision SBC — separate field schema

### Intelligence upgrades
- [ ] Confidence scoring per field — Claude estimates how certain it is about each extraction
- [ ] Year-over-year comparison — upload current + prior year SBC, diff the changes
- [ ] Vector database for past extractions — use similar past plans as few-shot examples
- [ ] Multi-file batch upload with progress tracking

### UX improvements
- [ ] Saved comparison sessions — reload previous extractions without re-uploading
- [ ] Export templates — customizable column selection and ordering
- [ ] Notes column — broker can add free-text notes per plan

---

## V3 — Compliance & Intelligence Layer (After V2 stable, targeting SaaS launch)

**Goal:** Make BenefitScan the compliance-aware brain of the broker workflow.

### Compliance engine
- [ ] ACA compliance checklist per plan (annual OOP limits, waiting period rules, etc.)
- [ ] Mental Health Parity flagging — compare mental health benefits to medical equivalents
- [ ] SPD extraction + ERISA compliance checklist
- [ ] Automatic year-over-year change alerts ("deductible increased 15% YoY")

### Integrations
- [ ] Employee Navigator API — push extracted plan data directly to benefits admin platform
- [ ] Applied Epic integration — create/update plan records in agency management system
- [ ] DocuSign integration — broker signature on compliance checklists

### Platform
- [ ] Multi-user accounts with brokerage-level data isolation
- [ ] Client portal — employers can view their plan comparison without broker sharing a file
- [ ] Cloud deployment (Railway or Render) with managed PostgreSQL
- [ ] Role-based access (broker admin / analyst / read-only)
- [ ] Audit log — track every field change with timestamp and user

### Business
- [ ] Usage-based pricing — pay per extraction
- [ ] White-label option — brokerages can brand the tool for their clients
- [ ] API access — allow brokerage tech teams to integrate BenefitScan into their own workflows
