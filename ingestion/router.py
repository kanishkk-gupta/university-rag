"""
ingestion/router.py — Automatic PDF type detection.

Determines whether a PDF is native (has selectable text) or scanned (image-only)
by actually attempting text extraction with PyMuPDF on a sample of pages.

Rules:
  - Open the PDF with PyMuPDF (read-only)
  - For each page (up to a sample), call page.get_text("text").strip()
  - If enough pages yield more than NATIVE_TEXT_CHARS_THRESHOLD characters,
    the document is classified as NATIVE.
  - Otherwise it is SCANNED.
  - A per-page override is also supported: individual pages can differ.

We NEVER hardcode document names. The decision is made from the document itself.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

from config import (
    NATIVE_TEXT_CHARS_THRESHOLD,
    NATIVE_TEXT_PAGE_FRACTION,
    TABLE_CRITICAL_DOCS,
)

logger = logging.getLogger(__name__)


class ExtractionMethod(str, Enum):
    NATIVE = "native_pdf"        # PyMuPDF text extraction
    OCR = "ocr_tesseract"        # Rasterise → Tesseract


class PageType(str, Enum):
    NATIVE = "native"
    SCANNED = "scanned"


class DocumentClassification:
    """Result of routing analysis for a single document."""

    def __init__(
        self,
        document_id: str,
        filename: str,
        source_path: str,
        doc_method: ExtractionMethod,
        page_types: List[PageType],    # one entry per page
        has_critical_tables: bool,
        page_count: int,
    ):
        self.document_id = document_id
        self.filename = filename
        self.source_path = source_path
        self.doc_method = doc_method       # dominant method for the document
        self.page_types = page_types       # per-page classification
        self.has_critical_tables = has_critical_tables
        self.page_count = page_count

    @property
    def native_page_count(self) -> int:
        return sum(1 for p in self.page_types if p == PageType.NATIVE)

    @property
    def scanned_page_count(self) -> int:
        return sum(1 for p in self.page_types if p == PageType.SCANNED)

    def __repr__(self) -> str:
        return (
            f"<Classification {self.filename!r}: {self.doc_method.value}, "
            f"{self.native_page_count} native / {self.scanned_page_count} scanned pages>"
        )


def classify_document(
    document_id: str,
    filename: str,
    source_path: str,
    chars_threshold: int = NATIVE_TEXT_CHARS_THRESHOLD,
    page_fraction: float = NATIVE_TEXT_PAGE_FRACTION,
) -> DocumentClassification:
    """
    Classify a single PDF as native or scanned by inspecting its content.

    Parameters
    ----------
    document_id : str
    filename : str
    source_path : str   Absolute path to the PDF
    chars_threshold : int
        Minimum extracted characters per page to call it "native"
    page_fraction : float
        Fraction of pages that must be native for the doc to be classified NATIVE

    Returns
    -------
    DocumentClassification
    """
    path = Path(source_path)
    doc = fitz.open(str(path))
    page_count = doc.page_count
    page_types: List[PageType] = []

    for page_num in range(page_count):
        page = doc[page_num]
        text = page.get_text("text").strip()
        char_count = len(text)

        if char_count >= chars_threshold:
            page_types.append(PageType.NATIVE)
            logger.debug("  Page %d: NATIVE (%d chars)", page_num + 1, char_count)
        else:
            page_types.append(PageType.SCANNED)
            logger.debug("  Page %d: SCANNED (%d chars)", page_num + 1, char_count)

    doc.close()

    # Document-level classification: majority vote weighted by page_fraction
    native_count = sum(1 for p in page_types if p == PageType.NATIVE)
    native_ratio = native_count / page_count if page_count > 0 else 0.0

    if native_ratio >= page_fraction:
        doc_method = ExtractionMethod.NATIVE
    else:
        doc_method = ExtractionMethod.OCR

    # Check if this document requires critical table handling
    has_critical_tables = any(
        marker.lower() in filename.lower()
        for marker in TABLE_CRITICAL_DOCS
    )

    classification = DocumentClassification(
        document_id=document_id,
        filename=filename,
        source_path=source_path,
        doc_method=doc_method,
        page_types=page_types,
        has_critical_tables=has_critical_tables,
        page_count=page_count,
    )

    logger.info(
        "Classified %r → %s  "
        "(native_pages=%d/%d, critical_tables=%s)",
        filename,
        doc_method.value,
        native_count,
        page_count,
        has_critical_tables,
    )

    return classification
