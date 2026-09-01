"""
ingestion/metadata.py — Metadata building utilities.

All metadata helpers live here so that every stage of the pipeline
produces metadata that is consistent and well-typed.
No metadata is fabricated: every field is either computed from the
document or explicitly set to None.
"""

import hashlib
import uuid
from typing import Optional


def make_chunk_id(document_id: str, page_start: int, chunk_index: int) -> str:
    """
    Generate a stable, reproducible chunk ID.

    Format: {document_id_prefix}_{page_start:04d}_{chunk_index:04d}
    """
    return f"{document_id[:8]}_p{page_start:04d}_c{chunk_index:04d}"


def make_page_id(document_id: str, page_number: int) -> str:
    """Generate a stable page ID."""
    return f"{document_id[:8]}_page_{page_number:04d}"


def make_table_id(document_id: str, page_number: int, table_index: int) -> str:
    """Generate a stable table ID."""
    return f"{document_id[:8]}_p{page_number:04d}_t{table_index:02d}"


def build_page_metadata(
    document_id: str,
    filename: str,
    source_path: str,
    page_number: int,        # 1-based
    raw_text: str,
    extraction_method: str,  # "native_pdf" | "ocr_tesseract"
    ocr_confidence: Optional[float] = None,  # None if not available
    ocr_engine: Optional[str] = None,
    warnings: Optional[list] = None,
) -> dict:
    """Build the metadata record for a single extracted page."""
    return {
        "page_id": make_page_id(document_id, page_number),
        "document_id": document_id,
        "filename": filename,
        "source_path": source_path,
        "page_number": page_number,
        "char_count": len(raw_text),
        "extraction_method": extraction_method,
        "ocr_engine": ocr_engine,
        "ocr_confidence": ocr_confidence,
        "warnings": warnings or [],
        "raw_text": raw_text,
    }


def build_chunk_metadata(
    chunk_id: str,
    document_id: str,
    document_name: str,
    source_path: str,
    page_start: int,
    page_end: int,
    section: Optional[str],
    subsection: Optional[str],
    heading: Optional[str],
    chunk_index: int,
    content_type: str,        # "text" | "heading" | "table" | "mixed"
    extraction_method: str,
    ocr_used: bool,
    ocr_confidence: Optional[float],
    has_table: bool,
    table_id: Optional[str],
    text: str,
) -> dict:
    """Build the complete chunk metadata record."""
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "document_name": document_name,
        "source_path": source_path,
        "page_start": page_start,
        "page_end": page_end,
        "section": section,
        "subsection": subsection,
        "heading": heading,
        "chunk_index": chunk_index,
        "content_type": content_type,
        "extraction_method": extraction_method,
        "ocr_used": ocr_used,
        "ocr_confidence": ocr_confidence,
        "has_table": has_table,
        "table_id": table_id,
        "char_count": len(text),
        "text": text,
    }
