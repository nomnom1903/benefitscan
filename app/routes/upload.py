"""
app/routes/upload.py — POST /upload

Accepts a PDF file upload, saves it to disk with a UUID filename,
creates a database record for it, and returns the upload_id.

The upload and extraction steps are intentionally separate:
  POST /upload  → saves file, returns upload_id immediately
  POST /extract/{upload_id} → runs the (slow) AI extraction

This separation means the UI can show progress per-file, and a failed
extraction doesn't lose the uploaded file — the broker can retry extraction
without re-uploading the PDF.
"""

import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.sbc import SBCPlanDB

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """
    Upload a PDF file for extraction.

    Accepts: multipart/form-data with a single file field named "file"
    Returns: {"upload_id": "...", "filename": "...", "file_size_kb": 123}
    """
    # --- Validate the file type ---
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # --- Read file content ---
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # --- Generate a UUID filename to avoid collisions and sanitize user input ---
    # We never use the original filename as a path — it could contain path traversal attempts
    upload_id = str(uuid.uuid4())
    safe_filename = f"{upload_id}.pdf"
    save_path = settings.upload_dir / safe_filename

    # --- Ensure upload directory exists (created at startup, but defensive check) ---
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    # --- Save to disk ---
    with open(save_path, "wb") as f:
        f.write(content)

    file_size_kb = round(len(content) / 1024, 1)
    logger.info(f"Uploaded: {file.filename} → {safe_filename} ({file_size_kb} KB)")

    # --- Create a database record (status = pending, no extraction yet) ---
    plan = SBCPlanDB(
        id=upload_id,
        upload_filename=file.filename,  # store original name for display
        upload_path=str(save_path),
        status="pending",
    )
    db.add(plan)
    db.commit()

    return {
        "upload_id": upload_id,
        "filename": file.filename,
        "file_size_kb": file_size_kb,
        "status": "pending",
        "message": "File uploaded successfully. Call POST /extract/{upload_id} to extract fields.",
    }
