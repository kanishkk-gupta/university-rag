"""
ingestion/pdf_extractor.py — Native PDF text extraction.

Used for PDFs with selectable/embedded text (e.g. Student Handbook,
which was produced by Microsoft Word via Acrobat PDFMaker).

Uses PyMuPDF exclusively. Extracts text page-by-page in reading order,
preserving paragraph structure. Detects headings based on font size
comparison to the page median font size.

Absolutely no OCR is performed here.
No document contents are invented.
"""

import logging
import re
from typing import List, Optional, Dict, Any

import fitz  # PyMuPDF

from ingestion.metadata import build_page_metadata

logger = logging.getLogger(__name__)

# Font size multiplier above median to classify as heading
HEADING_FONT_SIZE_RATIO = 1.15


def _detect_heading_level(font_size: float, median_size: float) -> Optional[int]:
    """
    Classify a text span as a heading (H1/H2/H3) based on font size.
    Returns None if it's body text.
    """
    if median_size <= 0:
        return None
    ratio = font_size / median_size
    if ratio >= 1.6:
        return 1
    elif ratio >= 1.3:
        return 2
    elif ratio >= HEADING_FONT_SIZE_RATIO:
        return 3
    return None


def _get_median_font_size(page: fitz.Page) -> float:
    """Compute median font size across all text spans on a page."""
    sizes = []
    try:
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for block in blocks:
            if block.get("type") != 0:  # 0 = text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    s = span.get("size", 0)
                    if s > 0:
                        sizes.append(s)
    except Exception:
        pass

    if not sizes:
        return 12.0  # fallback
    sizes.sort()
    mid = len(sizes) // 2
    return sizes[mid]


def extract_page_native(
    page: fitz.Page,
    page_number: int,  # 1-based
    document_id: str,
    filename: str,
    source_path: str,
) -> dict:
    """
    Extract all text from a single native PDF page.

    Returns a page metadata dict including:
    - raw_text: full page text in reading order
    - blocks: list of {text, is_heading, heading_level, bbox}
    - warnings: any issues encountered
    """
    warnings = []
    blocks_out = []

    median_size = _get_median_font_size(page)

    try:
        raw_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    except Exception as exc:
        warnings.append(f"Failed to extract dict blocks: {exc}")
        # Fallback to plain text
        text = page.get_text("text").strip()
        meta = build_page_metadata(
            document_id=document_id,
            filename=filename,
            source_path=source_path,
            page_number=page_number,
            raw_text=text,
            extraction_method="native_pdf",
            warnings=warnings,
        )
        meta["blocks"] = []
        return meta

    raw_text_parts = []

    for block in raw_blocks:
        btype = block.get("type", -1)
        if btype == 1:
            # Image block — record but don't extract text
            blocks_out.append({
                "text": "",
                "is_heading": False,
                "heading_level": None,
                "is_image": True,
                "bbox": block.get("bbox"),
            })
            continue

        if btype != 0:
            continue  # skip other block types

        block_text_parts = []
        max_span_size = 0.0
        is_bold = False

        for line in block.get("lines", []):
            line_parts = []
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                span_size = span.get("size", 0)
                span_flags = span.get("flags", 0)
                is_bold = bool(span_flags & 2**4)  # bold flag in pymupdf

                if span_text.strip():
                    line_parts.append(span_text)
                    if span_size > max_span_size:
                        max_span_size = span_size

            if line_parts:
                block_text_parts.append(" ".join(line_parts))

        block_text = "\n".join(block_text_parts).strip()
        if not block_text:
            continue

        heading_level = _detect_heading_level(max_span_size, median_size) if max_span_size else None
        # Also treat short all-caps or bold lines as headings
        if heading_level is None and is_bold and len(block_text) < 120:
            heading_level = 3

        blocks_out.append({
            "text": block_text,
            "is_heading": heading_level is not None,
            "heading_level": heading_level,
            "is_image": False,
            "bbox": block.get("bbox"),
        })
        raw_text_parts.append(block_text)

    raw_text = "\n\n".join(raw_text_parts)

    if not raw_text.strip():
        warnings.append("Page yielded no text after native extraction")
        logger.warning("Page %d of %r: empty after native extraction", page_number, filename)

    meta = build_page_metadata(
        document_id=document_id,
        filename=filename,
        source_path=source_path,
        page_number=page_number,
        raw_text=raw_text,
        extraction_method="native_pdf",
        warnings=warnings,
    )
    meta["blocks"] = blocks_out
    meta["median_font_size"] = median_size
    return meta


def extract_native_pdf(
    document_id: str,
    filename: str,
    source_path: str,
) -> List[dict]:
    """
    Extract all pages from a native PDF.

    Parameters
    ----------
    document_id, filename, source_path : str

    Returns
    -------
    List[dict]
        One metadata dict per page (in page order).
    """
    pages_out = []
    doc = fitz.open(source_path)

    logger.info("Extracting native PDF: %r (%d pages)", filename, doc.page_count)

    for page_index in range(doc.page_count):
        page = doc[page_index]
        page_number = page_index + 1  # 1-based
        page_data = extract_page_native(
            page=page,
            page_number=page_number,
            document_id=document_id,
            filename=filename,
            source_path=source_path,
        )
        pages_out.append(page_data)
        logger.debug(
            "  Page %d: %d chars extracted",
            page_number,
            len(page_data["raw_text"]),
        )

    doc.close()
    total_chars = sum(p["char_count"] for p in pages_out)
    logger.info(
        "Native extraction complete: %r → %d pages, %d total chars",
        filename, len(pages_out), total_chars,
    )
    return pages_out
