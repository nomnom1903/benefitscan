"""
app/routes/extract.py — Extraction, plan management, and review endpoints

POST /extract/{upload_id}     — run AI extraction pipeline on an uploaded PDF
GET  /plans                   — list all extracted plans
PATCH /plans/{plan_id}        — update a single field (human review corrections)
DELETE /plans/{plan_id}       — remove a plan
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sbc import SBCPlanDB, SBC_FIELD_KEYS, PlanFieldUpdate
from app.services.pdf_parser import parse_pdf
from app.services.extractor import extract_sbc_fields
from app.services.validator import validate_sbc_plan

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/extract/{upload_id}")
def run_extraction(upload_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Run the full AI extraction pipeline for an uploaded PDF.

    Pipeline stages:
      1. Load the plan record from the database (must have been uploaded first)
      2. Parse the PDF to text (pdfplumber → pymupdf fallback)
      3. Send text to Claude API → receive 30 structured fields
      4. Validate the extracted fields → produce field-level quality report
      5. Save everything to database → return the complete plan record

    This is a synchronous endpoint. It will take 5–20 seconds while Claude processes.
    The frontend shows a progress spinner during this time.
    """
    # --- Load the plan record ---
    plan = db.get(SBCPlanDB, upload_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"No upload found with ID: {upload_id}")

    if plan.status == "complete":
        logger.info(f"Plan {upload_id} already extracted, returning cached result")
        return plan.to_dict()

    # --- Mark as processing so the UI can show the right state ---
    plan.status = "processing"
    db.commit()

    try:
        # ── Stage 1: PDF → text ──────────────────────────────────────────────
        logger.info(f"[{upload_id}] Stage 1: Parsing PDF {plan.upload_filename}")
        pdf_text, pdf_metadata = parse_pdf(plan.upload_path)
        logger.info(
            f"[{upload_id}] PDF parsed: {pdf_metadata['page_count']} pages, "
            f"{len(pdf_text)} chars via {pdf_metadata['parser_used']}"
        )

        # ── Stage 2: Text → extracted fields (Claude API) ────────────────────
        logger.info(f"[{upload_id}] Stage 2: Calling Claude API")
        extracted_fields = extract_sbc_fields(pdf_text)

        # ── Stage 3: Validate extracted fields ───────────────────────────────
        logger.info(f"[{upload_id}] Stage 3: Validating fields")
        validation_report = validate_sbc_plan(extracted_fields)

        # ── Stage 4: Persist to database ─────────────────────────────────────
        for key in SBC_FIELD_KEYS:
            setattr(plan, key, extracted_fields.get(key))

        plan.validation_report = json.dumps(validation_report)
        plan.status = "complete"
        db.commit()

        logger.info(f"[{upload_id}] Extraction complete. Status: {validation_report['overall_status']}")
        return plan.to_dict()

    except Exception as e:
        # Log the full error, save a user-friendly message to the DB
        logger.exception(f"[{upload_id}] Extraction failed: {e}")
        plan.status = "failed"
        plan.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}. Check that the file is a valid SBC PDF.",
        )


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)) -> list[dict]:
    """
    Return all extracted plans, most recently extracted first.
    Used by the frontend to populate the review table on page load.
    """
    plans = db.query(SBCPlanDB).order_by(SBCPlanDB.extracted_at.desc()).all()
    return [plan.to_dict() for plan in plans]


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, db: Session = Depends(get_db)) -> dict:
    """Return a single plan by ID."""
    plan = db.get(SBCPlanDB, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")
    return plan.to_dict()


@router.patch("/plans/{plan_id}")
def update_plan_field(
    plan_id: str,
    update: PlanFieldUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Update a single field on a plan after human review.

    This is the "human-in-the-loop" correction endpoint. When a broker sees
    an incorrectly extracted value in the UI, they edit the cell directly and
    this endpoint saves the correction.

    Why not allow updating all fields at once: single-field updates are safer
    (a mistaken bulk update is harder to recover from) and make it easier to
    track which corrections were made and why in V2 audit logging.
    """
    plan = db.get(SBCPlanDB, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")

    # Validate that the field being updated is one of our known SBC fields
    allowed_fields = set(SBC_FIELD_KEYS)
    if update.field not in allowed_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown field: '{update.field}'. Must be one of the 30 SBC fields.",
        )

    # Apply the update
    old_value = getattr(plan, update.field)
    setattr(plan, update.field, update.value)

    logger.info(
        f"[{plan_id}] Field '{update.field}' updated: "
        f"'{old_value}' → '{update.value}' (human correction)"
    )

    db.commit()
    return plan.to_dict()


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: str, db: Session = Depends(get_db)) -> dict:
    """Remove a plan from the database (does not delete the uploaded PDF from disk)."""
    plan = db.get(SBCPlanDB, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")

    db.delete(plan)
    db.commit()
    logger.info(f"Plan {plan_id} ({plan.upload_filename}) deleted")
    return {"message": f"Plan '{plan.upload_filename}' deleted successfully"}
