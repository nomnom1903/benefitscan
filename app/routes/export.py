"""
app/routes/export.py — GET /export

Queries all complete plans from the database, generates a formatted
Excel comparison spreadsheet, and returns it as a file download.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.sbc import SBCPlanDB
from app.services.exporter import export_to_excel

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/export")
def export_plans(db: Session = Depends(get_db)) -> FileResponse:
    """
    Generate and download the Excel plan comparison spreadsheet.

    Only includes plans with status="complete" (successfully extracted).
    Skips pending/processing/failed plans.

    Returns a .xlsx file download.
    """
    # Fetch only successfully extracted plans
    plans = (
        db.query(SBCPlanDB)
        .filter(SBCPlanDB.status == "complete")
        .order_by(SBCPlanDB.extracted_at.asc())  # oldest first = natural order
        .all()
    )

    if not plans:
        raise HTTPException(
            status_code=404,
            detail=(
                "No extracted plans found. "
                "Upload and extract at least one SBC before exporting."
            ),
        )

    # Convert ORM objects to plain dicts for the exporter service
    plan_dicts = [plan.to_dict() for plan in plans]

    # Ensure output directory exists
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    # Generate the Excel file
    try:
        output_path = export_to_excel(plan_dicts, settings.output_dir)
    except Exception as e:
        logger.exception(f"Excel export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    logger.info(f"Exporting {len(plans)} plans → {output_path.name}")

    # Return the file as a download attachment
    # FileResponse handles the Content-Disposition and Content-Type headers
    return FileResponse(
        path=str(output_path),
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
