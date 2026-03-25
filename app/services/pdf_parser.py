"""
app/services/pdf_parser.py — Stage 1: PDF to text conversion

Strategy: try pdfplumber first (best for table-heavy SBCs), fall back to
pymupdf/fitz if that fails. Both are tried before we give up.

Why this matters: SBCs are table-structured documents. pdfplumber preserves
table geometry (row → row, cell → cell). If we lose that structure, Claude
has a harder time knowing that "$1,500" belongs to "Individual Deductible"
rather than some adjacent cell. Better input = better extraction.
"""

from __future__ import annotations  # allows str | Path syntax on Python 3.9

import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def parse_pdf(file_path: str | Path) -> tuple[str, dict]:
    """
    Extract all text from a PDF file.

    Returns:
        tuple: (extracted_text, metadata)
            - extracted_text: full text content of the PDF as a single string
            - metadata: dict with keys: file_name, file_size_kb, page_count, parser_used

    Raises:
        ValueError: if the file doesn't exist or both parsers fail
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise ValueError(f"PDF file not found: {file_path}")

    metadata = {
        "file_name": file_path.name,
        "file_size_kb": round(file_path.stat().st_size / 1024, 1),
        "page_count": 0,
        "parser_used": None,
    }

    # --- Attempt 1: pdfplumber ---
    # Best choice for table-heavy documents like SBCs.
    # It reconstructs table structure from PDF geometry, giving us rows and cells.
    text, page_count = _try_pdfplumber(file_path)

    if text and len(text.strip()) > 100:  # 100 chars = sanity check, not a blank page
        metadata["parser_used"] = "pdfplumber"
        metadata["page_count"] = page_count
        logger.info(f"pdfplumber parsed {file_path.name}: {page_count} pages, {len(text)} chars")
        return text, metadata

    # --- Attempt 2: pymupdf (fitz) ---
    # More robust for edge cases: image-heavy PDFs, non-standard encoding,
    # password-protected-but-readable PDFs. Slower but handles more scenarios.
    logger.warning(
        f"pdfplumber returned minimal text for {file_path.name}, falling back to pymupdf"
    )
    text, page_count = _try_pymupdf(file_path)

    if text and len(text.strip()) > 100:
        metadata["parser_used"] = "pymupdf"
        metadata["page_count"] = page_count
        logger.info(f"pymupdf parsed {file_path.name}: {page_count} pages, {len(text)} chars")
        return text, metadata

    # --- Both failed ---
    raise ValueError(
        f"Could not extract text from {file_path.name}. "
        "The file may be a scanned image PDF that requires OCR, "
        "or may be corrupted. Please ensure the SBC is a digitally-generated PDF."
    )


def _try_pdfplumber(file_path: Path) -> tuple[Optional[str], int]:
    """
    Parse PDF with pdfplumber, preserving table structure.

    pdfplumber's key feature: extract_tables() returns a list of lists (rows × cols).
    We convert those tables to tab-separated text so Claude can read the structure.
    Plain text is extracted separately and combined.

    Returns: (text, page_count) or (None, 0) on failure
    """
    try:
        import pdfplumber

        all_text_parts: list[str] = []
        page_count = 0

        with pdfplumber.open(str(file_path)) as pdf:
            page_count = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                all_text_parts.append(f"\n--- Page {page_num} ---\n")

                # Extract raw text from this page
                page_text = page.extract_text()
                if page_text:
                    all_text_parts.append(page_text)

                # Extract tables from this page
                # tables is a list of tables; each table is a list of rows;
                # each row is a list of cell values (strings or None)
                tables = page.extract_tables()
                for table in tables:
                    all_text_parts.append("\n[TABLE]\n")
                    for row in table:
                        # Replace None cells with empty string, join with tab
                        row_text = "\t".join(cell or "" for cell in row)
                        all_text_parts.append(row_text)
                    all_text_parts.append("[/TABLE]\n")

        return "\n".join(all_text_parts), page_count

    except Exception as e:
        logger.warning(f"pdfplumber failed on {file_path.name}: {e}")
        return None, 0


def _try_pymupdf(file_path: Path) -> tuple[Optional[str], int]:
    """
    Parse PDF with pymupdf (imported as fitz).
    Fallback for when pdfplumber can't extract meaningful text.

    Returns: (text, page_count) or (None, 0) on failure
    """
    try:
        import fitz  # fitz is the import name for pymupdf

        all_text_parts: list[str] = []
        page_count = 0

        doc = fitz.open(str(file_path))
        page_count = len(doc)

        for page_num, page in enumerate(doc, start=1):
            all_text_parts.append(f"\n--- Page {page_num} ---\n")
            # get_text("text") extracts plain text preserving line breaks
            all_text_parts.append(page.get_text("text"))

        doc.close()
        return "\n".join(all_text_parts), page_count

    except Exception as e:
        logger.warning(f"pymupdf failed on {file_path.name}: {e}")
        return None, 0
