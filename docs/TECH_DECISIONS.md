# BenefitScan — Technical Decision Log

Every meaningful architectural or technology decision is documented here.
Format: context → decision → rationale → consequences.

---

### Decision 1: pdfplumber over PyPDF2 or Tesseract OCR
**Date:** 2025-Q1
**Context:** SBCs are table-heavy PDFs. We need the table structure (row → cell → value)
preserved when we extract text — otherwise Claude sees a wall of text with no layout cues
and must guess which value belongs to which field.
**Decision:** pdfplumber as primary parser, PyMuPDF (fitz) as fallback.
**Rationale:**
- pdfplumber was purpose-built for table extraction. It returns `extract_tables()` which
  gives you a list of lists: `[row][col] = cell_value`. This matches how SBC data is laid out.
- PyPDF2 extracts raw text only — loses all table structure (like shredding a spreadsheet
  and trying to reconstruct it from confetti).
- Tesseract is OCR — for scanning images of paper documents. The vast majority of SBCs are
  digitally generated PDFs with native text embedded. Using OCR on them is wasteful and slower.
**Consequences:** We get better extraction accuracy from structured SBCs. Very old or
  scanned SBCs may still fail (future V2: add Tesseract as a third fallback with a warning).

---

### Decision 2: Claude API over GPT-4 or local LLMs
**Date:** 2025-Q1
**Context:** We need a language model that reliably follows a 30-field JSON schema and handles
  the semi-structured, table-extracted text output of SBC documents.
**Decision:** Anthropic Claude API (`claude-opus-4-5`)
**Rationale:**
- Claude was mandated by the product requirements (broker relationship with Anthropic ecosystem).
- Claude Opus performs exceptionally on structured extraction tasks with complex schemas.
- Local LLMs (Ollama, LLaMA 3) cannot reliably follow a 30-field JSON schema on consumer
  hardware. Error rates would require more human correction than the manual process they replace.
- GPT-4: not in scope per requirements.
**Consequences:** Per-extraction cost (~$0.05–0.15/SBC at Opus pricing). At 120 SBCs/broker
  per renewal season, this is $6–18/broker — trivial compared to the 60–90 hours of manual
  labor eliminated.

---

### Decision 3: FastAPI over Flask or Django
**Date:** 2025-Q1
**Context:** We need a Python web framework for the API backend.
**Decision:** FastAPI
**Rationale:**
- FastAPI generates interactive API docs (Swagger UI at /docs) automatically — invaluable
  for a builder learning the codebase. You can test every endpoint in a browser.
- Built-in request validation via Pydantic. Flask requires extra libraries (marshmallow,
  webargs) for the same thing.
- Type hints are first-class. Code is self-documenting.
- Django is designed for content sites with ORM-first templates. We're building a JSON API
  service — Django brings enormous complexity that doesn't apply here.
**Consequences:** More structured code from the start. Slightly steeper learning curve than
  Flask for the first 30 minutes, then significantly easier.

---

### Decision 4: SQLite over PostgreSQL for V1
**Date:** 2025-Q1
**Context:** We need to persist extraction results across page refreshes and server restarts.
**Decision:** SQLite via SQLAlchemy ORM
**Rationale:**
- SQLite is a file (benefitscan.db). Zero setup — no server, no user accounts, no config.
- SQLAlchemy is database-agnostic. Switching to PostgreSQL in V2 is a one-line config change
  (change the DATABASE_URL env var). The application code doesn't change.
- For a single-user local tool with ~200 plans max, SQLite performance is irrelevant.
  PostgreSQL's advantages (concurrent writes, JSON indexing) only matter at scale.
**Consequences:** V2 migration path: add `DATABASE_URL=postgresql://...` to env vars, remove
  `connect_args={"check_same_thread": False}` from the engine config. Nothing else changes.

---

### Decision 5: Vanilla JS frontend over React/Vue
**Date:** 2025-Q1
**Context:** We need a review UI with an editable table, file upload, and progress states.
**Decision:** Single `index.html` with vanilla JavaScript
**Rationale:**
- No build tooling: no npm, no webpack, no node_modules. The broker opens a browser and it works.
- For a table with editable cells and a file upload form, React would add complexity without
  adding capability. We don't have component reuse scenarios, complex state trees, or routing.
- Easier for a first-time builder to read, debug, and modify.
- V2 consideration: if the UI grows to need routing, real-time updates, or complex state
  management, migrate to a lightweight framework (Svelte or Vite+React).
**Consequences:** The frontend is a single maintainable file. No build step means no build
  failures, no version conflicts in package.json.

---

### Decision 6: Local-first deployment over cloud-first
**Date:** 2025-Q1
**Context:** V1 needs to be usable before we build cloud infrastructure.
**Decision:** Run locally at http://localhost:5000
**Rationale:**
- Cloud deployment (Railway, Render, Heroku) requires CI/CD config, environment variable
  management, domain names, TLS — all irrelevant complexity until we have validated users.
- Local deployment means: `python app/main.py` → open browser → it works. Zero DevOps.
- Data privacy: broker client documents (SBCs) stay on the broker's machine. No compliance
  questions about cloud storage of PII.
- V2 path: FastAPI apps deploy to Railway/Render with zero code changes. The only V2 work
  is adding a Procfile (one line) and configuring environment variables.
**Consequences:** V1 cannot be shared with multiple users or accessed remotely. Acceptable
  for a single-user validation product.

---

### Decision 7: Human-in-the-loop review step (not fully autonomous)
**Date:** 2025-Q1
**Context:** Should we auto-export to Excel without human review, or require the broker
  to review extracted data before exporting?
**Decision:** Require review — all extracted data is shown in an editable table before export.
**Rationale:**
- AI extraction accuracy is ~92–97% on standard SBCs. That means 1–2 errors per plan.
- A plan comparison spreadsheet that goes to a client employer is a high-stakes document.
  A $50 copay transcribed as $500 could cause a broker to lose the client relationship.
- The review step also serves as a trust-building mechanism during early adoption. Brokers
  need to see what the AI extracted and verify it matches the source document before they
  trust the tool enough to use it in production.
- The validation flagging (yellow/red cells) directs attention to the likely-wrong fields,
  so review takes 2–3 minutes per plan rather than 30–45 minutes.
**Consequences:** Export is not one-click from upload. This is intentional. V3 may add a
  "high-confidence auto-export" mode after we've validated accuracy on 1,000+ real SBCs.

---

### Decision 8: openpyxl over xlsxwriter for Excel export
**Date:** 2025-Q1
**Context:** We need to generate formatted .xlsx files with frozen panes, color fills,
  and auto-sized columns.
**Decision:** openpyxl
**Rationale:**
- openpyxl can both read and write .xlsx files. xlsxwriter is write-only.
- openpyxl's API maps intuitively to Excel concepts: `ws["A1"].value = "hello"`.
- Better Stack Overflow coverage for formatting questions.
- V2 consideration: if we add "update a previously exported spreadsheet" functionality,
  openpyxl will handle it; xlsxwriter cannot.
**Consequences:** openpyxl is slightly slower than xlsxwriter on very large files (10,000+
  rows), but for plan comparison files (~20 rows), this is completely irrelevant.
