"""
test_pipeline.py — Standalone CLI test for the BenefitScan extraction pipeline

Runs all 4 pipeline stages directly from the terminal without needing the browser UI.
Use this to verify each stage works before testing via the full web app.

Usage:
    python test_pipeline.py path/to/your_sbc.pdf

Example:
    python test_pipeline.py tests/sample_sbc.pdf

What it does:
    Stage 1 — Parse the PDF to text (pdfplumber → pymupdf fallback)
    Stage 2 — Send text to Claude API → get back 30 extracted fields
    Stage 3 — Validate the extracted fields → flag issues
    Stage 4 — Export a real .xlsx file to storage/outputs/

Each stage prints its result before moving to the next.
If a stage fails, the script stops and tells you exactly what went wrong.
"""

import sys
import json
import os
from pathlib import Path

# Add the project root to sys.path so imports work when running from any directory
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Color codes for terminal output (makes it easier to scan results) ────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"{GREEN}  ✓ {msg}{RESET}")
def warn(msg):  print(f"{YELLOW}  ⚠ {msg}{RESET}")
def fail(msg):  print(f"{RED}  ✗ {msg}{RESET}")
def info(msg):  print(f"{CYAN}  → {msg}{RESET}")
def header(msg):print(f"\n{BOLD}{msg}{RESET}")
def divider():  print("─" * 60)


def main():
    # ─── Check arguments ──────────────────────────────────────────────────────
    if len(sys.argv) < 2:
        print(f"\n{BOLD}Usage:{RESET}  python test_pipeline.py path/to/sbc.pdf\n")
        print("  Download a sample SBC from any insurance carrier's website,")
        print("  or search 'sample SBC PDF' to find a public example.\n")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        fail(f"File not found: {pdf_path}")
        sys.exit(1)
    if not pdf_path.suffix.lower() == ".pdf":
        fail(f"File must be a PDF: {pdf_path}")
        sys.exit(1)

    print(f"\n{BOLD}BenefitScan — Pipeline Test{RESET}")
    print(f"File: {pdf_path.name}  ({round(pdf_path.stat().st_size / 1024, 1)} KB)")
    divider()

    # ─── Stage 1: PDF Parsing ─────────────────────────────────────────────────
    header("Stage 1 — PDF Parsing (pdfplumber → pymupdf fallback)")

    try:
        from app.services.pdf_parser import parse_pdf
        pdf_text, metadata = parse_pdf(pdf_path)

        ok(f"Parser used:  {metadata['parser_used']}")
        ok(f"Pages found:  {metadata['page_count']}")
        ok(f"Text length:  {len(pdf_text):,} characters")

        if len(pdf_text) < 500:
            warn("Very little text extracted — this might be a scanned/image PDF")
            warn("BenefitScan requires digitally-generated PDFs with embedded text")

        # Print a preview of the first 800 characters so you can verify it looks right
        print(f"\n{BOLD}  Text preview (first 800 chars):{RESET}")
        print("  " + "─" * 56)
        for line in pdf_text[:800].split("\n"):
            if line.strip():
                print(f"  {line}")
        print("  " + "─" * 56)

    except Exception as e:
        fail(f"PDF parsing failed: {e}")
        print("\n  Possible causes:")
        print("  - File is corrupted")
        print("  - File is password-protected")
        print("  - File is a scanned image (requires OCR, not supported in V1)")
        sys.exit(1)

    # ─── Stage 2: AI Extraction ───────────────────────────────────────────────
    header("Stage 2 — AI Extraction (Claude API)")
    info(f"Sending {len(pdf_text):,} characters to Claude API...")
    info("This takes 10–30 seconds. Please wait...")

    try:
        from app.services.extractor import extract_sbc_fields
        extracted = extract_sbc_fields(pdf_text)

        populated = {k: v for k, v in extracted.items() if v is not None}
        missing   = {k: v for k, v in extracted.items() if v is None}

        ok(f"Fields extracted:  {len(populated)}/31")
        if missing:
            warn(f"Fields missing:    {len(missing)}/31")

        # Print all extracted fields in a readable table
        print(f"\n{BOLD}  Extracted fields:{RESET}")
        print("  " + "─" * 56)

        field_labels = {
            "plan_name": "Plan Name",
            "carrier_name": "Carrier",
            "plan_type": "Plan Type",
            "deductible_individual_in_network": "Deductible Ind. (In-Net)",
            "deductible_family_in_network": "Deductible Fam. (In-Net)",
            "deductible_individual_out_of_network": "Deductible Ind. (OON)",
            "deductible_family_out_of_network": "Deductible Fam. (OON)",
            "oop_max_individual_in_network": "OOP Max Ind. (In-Net)",
            "oop_max_family_in_network": "OOP Max Fam. (In-Net)",
            "copay_pcp": "PCP Copay",
            "copay_specialist": "Specialist Copay",
            "copay_emergency_room": "ER Copay",
            "copay_urgent_care": "Urgent Care Copay",
            "coinsurance_in_network": "Coinsurance (In-Net)",
            "rx_tier1_generic": "Rx Tier 1 (Generic)",
            "rx_tier2_preferred_brand": "Rx Tier 2 (Pref. Brand)",
            "rx_tier3_nonpreferred_brand": "Rx Tier 3 (Non-Pref.)",
            "rx_tier4_specialty": "Rx Tier 4 (Specialty)",
            "hsa_eligible": "HSA Eligible",
            "separate_drug_deductible": "Sep. Drug Deductible",
            "preventive_care": "Preventive Care",
            "inpatient_hospital": "Inpatient Hospital",
            "outpatient_surgery": "Outpatient Surgery",
            "mental_health_copay": "Mental Health Copay",
            "telehealth_copay": "Telehealth Copay",
            "premium_employee_only": "Premium Ee Only",
            "premium_employee_spouse": "Premium Ee+Spouse",
            "premium_employee_children": "Premium Ee+Children",
            "premium_family": "Premium Family",
            "effective_date": "Effective Date",
            "network_name": "Network Name",
        }

        for key, label in field_labels.items():
            value = extracted.get(key)
            if value:
                print(f"  {GREEN}✓{RESET}  {label:<28}  {value}")
            else:
                print(f"  {RED}✗{RESET}  {label:<28}  {YELLOW}(not found){RESET}")

        print("  " + "─" * 56)

    except Exception as e:
        fail(f"Extraction failed: {e}")
        print("\n  Possible causes:")
        print("  - ANTHROPIC_API_KEY not set or invalid in .env")
        print("  - No internet connection")
        print("  - Claude API rate limit (wait 30 seconds and retry)")
        sys.exit(1)

    # ─── Stage 3: Validation ──────────────────────────────────────────────────
    header("Stage 3 — Validation")

    try:
        from app.services.validator import validate_sbc_plan
        report = validate_sbc_plan(extracted)

        summary = report["summary"]
        overall = report["overall_status"]

        status_color = {
            "OK": GREEN,
            "WARNING": YELLOW,
            "CRITICAL": RED,
        }.get(overall, RESET)

        print(f"  Overall status:  {status_color}{BOLD}{overall}{RESET}")
        ok(f"OK fields:        {summary['ok_count']}")

        if summary["missing_count"]:
            warn(f"Missing fields:   {summary['missing_count']}")
        if summary["review_count"]:
            warn(f"Review flags:     {summary['review_count']}")
        if summary["non_compliant_count"]:
            fail(f"Non-compliant:    {summary['non_compliant_count']}")

        # Print only the flagged fields (OK fields are noise here)
        flagged = {
            k: v for k, v in report["field_results"].items()
            if v["status"] != "OK"
        }
        if flagged:
            print(f"\n{BOLD}  Flagged fields:{RESET}")
            for field, result in flagged.items():
                label = field_labels.get(field, field)
                status = result["status"]
                note = result["note"]
                color = YELLOW if status in ("Missing", "Review") else RED
                print(f"  {color}{status:<14}{RESET}  {label:<28}  {note}")

    except Exception as e:
        fail(f"Validation failed: {e}")
        sys.exit(1)

    # ─── Stage 4: Excel Export ────────────────────────────────────────────────
    header("Stage 4 — Excel Export")

    try:
        from app.services.exporter import export_to_excel
        from datetime import datetime

        output_dir = PROJECT_ROOT / "storage" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build a mock plan dict that matches what the DB would return
        plan_dict = {
            "id": "test-cli-run",
            "upload_filename": pdf_path.name,
            "upload_path": str(pdf_path),
            "extracted_at": datetime.utcnow().isoformat(),
            "status": "complete",
            "error_message": None,
            "validation_report": report,
            **extracted,
        }

        output_path = export_to_excel([plan_dict], output_dir)
        ok(f"Excel file created: {output_path.name}")
        ok(f"Full path: {output_path}")
        info("Open the file in Excel or Numbers to verify formatting.")

    except Exception as e:
        fail(f"Excel export failed: {e}")
        sys.exit(1)

    # ─── Summary ──────────────────────────────────────────────────────────────
    divider()
    print(f"\n{BOLD}{GREEN}All 4 stages completed successfully.{RESET}")
    print(f"\n  Next step: open the web UI and do a full end-to-end test.")
    print(f"  → python app/main.py")
    print(f"  → open http://localhost:8000\n")


if __name__ == "__main__":
    main()
