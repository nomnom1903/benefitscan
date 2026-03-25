# BenefitScan

**AI-powered SBC extraction and plan comparison for insurance brokers.**

BenefitScan eliminates the most time-consuming part of the insurance broker's annual renewal workflow: manually copying data from carrier PDFs into Excel. Upload your SBC documents, let Claude extract the data, review in 2–3 minutes, and export a formatted comparison spreadsheet ready for your client.

Built with Python, FastAPI, and the Anthropic Claude API. Runs locally — no cloud account required, no client data leaves your machine.

---

## The Problem We're Solving

Every year, insurance brokers working on benefits renewals receive PDFs from 3–5 carriers, each with 2–4 plan options. For each plan, they manually read through a 4-page Summary of Benefits and Coverage (SBC) and transcribe 25–30 fields into an Excel spreadsheet. That spreadsheet — the plan comparison — is the broker's primary client deliverable.

The math: **30–45 minutes per plan × 12 plans per client × 10 clients in renewal season = 60–90 hours of manual data entry per broker per year.** Industry studies put the error rate at 3–5% — meaning at least one wrong number on every comparison spreadsheet.

SBCs are the ideal document to automate: mandated by the ACA since 2012, every SBC follows a standardized 4-page template with the same fields in roughly the same positions, regardless of carrier. BenefitScan exploits this standardization.

---

## Tech Stack

| Technology | Purpose | Why We Chose It |
|------------|---------|----------------|
| Python 3.11+ | Language | Best ecosystem for AI/data work; most beginner-accessible |
| FastAPI | Web framework | Auto-generates API docs; built-in type validation; simpler than Django |
| SQLite + SQLAlchemy | Database | Zero setup; file-based; ORM lets us switch to PostgreSQL later with one config change |
| pdfplumber | PDF parsing | Purpose-built for table extraction; preserves SBC table structure |
| PyMuPDF (fitz) | PDF fallback | Handles edge cases pdfplumber can't (image-heavy, non-standard encoding) |
| Claude API (Opus) | AI extraction | Most accurate model for structured JSON extraction from complex documents |
| openpyxl | Excel generation | Full .xlsx formatting support; can also read files (unlike xlsxwriter) |
| Vanilla JS | Frontend | No build tooling; no npm; works immediately in any browser |

---

## Architecture

```
PDF Upload
    │
    ▼
┌─────────────┐
│  pdf_parser  │  pdfplumber → text with table structure preserved
│  (Stage 1)  │  fallback: PyMuPDF if pdfplumber fails
└──────┬──────┘
       │ clean text string
       ▼
┌─────────────┐
│  extractor  │  Claude API (claude-opus-4-5)
│  (Stage 2)  │  30-field JSON extraction prompt
│             │  3x retry with exponential backoff
└──────┬──────┘
       │ {plan_name: "...", copay_pcp: "$30", ...}
       ▼
┌─────────────┐
│  validator  │  Field-level quality checks
│  (Stage 3)  │  Flags: Missing / Review / Non-Compliant
└──────┬──────┘
       │ plan data + validation_report
       ▼
┌─────────────┐
│  Review UI  │  Editable table in browser
│  (Stage 4)  │  Green/yellow/red cells by status
│             │  Human corrections via PATCH /plans/{id}
└──────┬──────┘
       │ approved data
       ▼
┌─────────────┐
│  exporter   │  openpyxl → formatted .xlsx
│  (Stage 5)  │  Frozen panes, color coding, auto-width columns
└─────────────┘
       │
       ▼
  Excel download
```

---

## Setup Instructions

Assumes Python 3.11+ is installed. Check with: `python --version`

**1. Clone or download the project**
```bash
cd ~/
# If using git:
git clone <repo-url> benefitscan
# Or just ensure the benefitscan/ folder is in your home directory
cd benefitscan
```

**2. Create a virtual environment**
```bash
python -m venv venv
```
A virtual environment keeps this project's dependencies separate from your system Python.
Think of it as a clean room for this project's packages.

**3. Activate the virtual environment**
```bash
# macOS / Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```
You'll see `(venv)` in your terminal prompt. Always activate before running the app.

**4. Install dependencies**
```bash
pip install -r requirements.txt
```
This installs FastAPI, the Anthropic SDK, pdfplumber, openpyxl, and everything else.
Takes 1–3 minutes.

**5. Set up your API key**
```bash
cp .env.example .env
```
Open `.env` in a text editor and replace `sk-ant-your-key-here` with your actual
Anthropic API key. Get one at [console.anthropic.com](https://console.anthropic.com).

Your `.env` file should look like:
```
ANTHROPIC_API_KEY=sk-ant-api03-...your-actual-key...
```

**6. Start the app**
```bash
python app/main.py
```

**7. Open in browser**

Navigate to: **http://localhost:8000**

You should see the BenefitScan upload interface.
The API docs are at: **http://localhost:8000/docs**

---

## How to Use

**Step 1 — Upload SBC PDFs**
Drag one or more SBC PDF files onto the upload zone, or click to browse.
You'll see each file appear in the queue with its filename and size.

**Step 2 — Extract**
Click "Extract All Plans". For each file:
- The PDF is uploaded to the server (~instant)
- The text is extracted and sent to Claude (~5–15 seconds per SBC)
- Fields are validated and the result appears in the table below

**Step 3 — Review**
The comparison table shows all extracted plans side by side:
- **Green cells**: extracted successfully, value looks correct
- **Yellow cells**: extracted but flagged for review (unusual value, ACA concern)
- **Red cells**: field not found in the document — needs manual entry
- **Hover** over a flagged cell to see the validation note explaining why it was flagged
- **Click any cell** to edit it. Press Enter or click away to save.

**Step 4 — Correct anything flagged**
Red and yellow cells need your attention. Either:
- Verify the value is correct (yellow) and leave it, or
- Type the correct value and click away to save

**Step 5 — Export**
Click "Export to Excel". A formatted `.xlsx` file downloads immediately.
- Sheet 1 "Plan Comparison": one row per plan, all fields, color-coded
- Sheet 2 "Extraction Summary": metadata about each extraction

---

## Product Decisions

**Why SBCs first (not SPDs or EOCs)?**
SBCs are the most standardized document in benefits. Mandated by the ACA, every SBC
follows a fixed 4-page template regardless of carrier. This makes AI extraction tractable.
SPDs are 50–200 pages with no standard structure — much harder, much less valuable for
the client-facing comparison deliverable. We start where success is achievable.

**Why human-in-the-loop review (not fully automated export)?**
AI extraction is ~93–97% accurate on standard SBCs. That sounds high, but 1–2 errors per
plan comparison spreadsheet that goes to an employer's HR team is unacceptable. The review
step directs broker attention to flagged cells only, keeping review to 2–3 minutes while
ensuring the output can be trusted. V3 will add auto-export mode after validating accuracy
on 1,000+ real SBCs.

**Why local-first deployment (not cloud-first)?**
SBC documents may contain sensitive employer and employee data. Keeping them on the broker's
machine eliminates cloud data privacy questions and removes DevOps complexity from V1. The
app deploys to cloud (Railway/Render) with zero code changes when needed in V2.

**Why Claude API (not GPT-4 or local models)?**
Claude Opus consistently follows complex JSON schemas with 30 fields and handles the
semi-structured table text that pdfplumber produces. Local LLMs (Ollama, LLaMA 3) cannot
reliably follow this schema on consumer hardware — error rates require more correction time
than the manual process they replace.

---

## Known Limitations (V1)

- **Single user only** — no authentication, no multi-user accounts
- **Local only** — not accessible from other machines without extra network config
- **Scanned PDFs not supported** — only digitally-generated PDFs with embedded text work
- **Premiums may be missing** — many carriers don't include premium rates in the SBC itself
- **No edit history** — corrections overwrite the original extracted value with no audit trail
- **No session persistence UI** — refreshing the page reloads all plans from the database,
  but there's no "load a previous session" concept in the UI

---

## Roadmap

See `docs/ROADMAP.md` for the full V1 → V2 → V3 plan.

**V1:** SBC extraction, review, Excel export (this release)
**V2:** Schedule of Benefits, COC/EOC support, dental/vision SBCs, confidence scoring
**V3:** SPD/ERISA compliance, integrations (Employee Navigator, Applied Epic), cloud/SaaS

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Tests cover the extraction JSON parsing, field normalization, and all validation rules.
They do not call the real Claude API (mocked to avoid cost and network dependency).

---

## Development Notes

- API docs: http://localhost:8000/docs (Swagger UI, only in development mode)
- Database: `benefitscan.db` in the project root (SQLite file, viewable with DB Browser for SQLite)
- Uploaded PDFs: `storage/uploads/` (UUID-named)
- Exported Excel files: `storage/outputs/`
- Logs: printed to console. Set `APP_ENV=production` in `.env` to reduce log verbosity.
