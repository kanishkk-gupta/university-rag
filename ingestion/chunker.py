"""
ingestion/chunker.py — Structure-aware text chunking.

Chunking strategy (in priority order):
  1. Table chunks: each detected table becomes a single atomic chunk.
     Tables are NEVER split across chunk boundaries.
  2. Heading-based chunks: for native PDFs where heading structure was
     detected, split at heading boundaries while respecting max size.
  3. Paragraph-based chunks: split on blank lines (paragraphs).
  4. Sentence-boundary fallback: if a paragraph is too long, split
     at sentence boundaries (". " patterns).
  5. Hard character-limit split: absolute last resort.

All chunks carry the full metadata schema defined in metadata.py.
Chunk size and overlap are configurable via config.py.

Design rules:
  - Never cross document boundaries.
  - Never cross page boundaries unless the chunk is very small (<50 chars)
    and continuing across the page break is more useful than isolating it.
  - Overlap is applied at text level by repeating the tail of the previous chunk.
  - Metadata is never fabricated. Section/heading fields are null when unknown.
"""

import logging
import re
from typing import List, Optional, Tuple

from ingestion.metadata import build_chunk_metadata, make_chunk_id
from ingestion.table_extractor import make_table_chunk_text
from config import (
    CHUNK_SIZE_CHARS,
    CHUNK_OVERLAP_CHARS,
    CHUNK_MIN_CHARS,
    CHUNK_MAX_CHARS,
)

logger = logging.getLogger(__name__)


# ─── Section tracking ──────────────────────────────────────────────────────────

class SectionTracker:
    """Tracks current heading/section hierarchy as we scan through pages."""

    def __init__(self):
        self.h1: Optional[str] = None
        self.h2: Optional[str] = None
        self.h3: Optional[str] = None

    def update(self, heading_text: str, level: int):
        if level == 1:
            self.h1 = heading_text
            self.h2 = None
            self.h3 = None
        elif level == 2:
            self.h2 = heading_text
            self.h3 = None
        elif level == 3:
            self.h3 = heading_text

    @property
    def section(self) -> Optional[str]:
        return self.h1

    @property
    def subsection(self) -> Optional[str]:
        return self.h2

    @property
    def heading(self) -> Optional[str]:
        return self.h3 or self.h2 or self.h1


# ─── Text splitting helpers ────────────────────────────────────────────────────

def _split_into_paragraphs(text: str) -> List[str]:
    """Split text on blank lines to get paragraphs."""
    paras = re.split(r"\n{2,}", text)
    return [p.strip() for p in paras if p.strip()]


def _split_at_sentences(text: str) -> List[str]:
    """Split text at sentence boundaries as a fallback."""
    # Split at ". " followed by capital letter, or at "; " or ".\n"
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


def _chunk_text(
    text: str,
    max_size: int = CHUNK_SIZE_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> List[str]:
    """
    Split a text block into overlapping chunks respecting paragraph boundaries.

    Returns list of chunk text strings.
    """
    if len(text) <= max_size:
        return [text] if text.strip() else []

    paragraphs = _split_into_paragraphs(text)
    if not paragraphs:
        return [text[:max_size]]

    chunks = []
    current_chunk = ""
    overlap_tail = ""

    for para in paragraphs:
        # If the paragraph itself is too large, split at sentences
        if len(para) > max_size:
            sentences = _split_at_sentences(para)
            for sent in sentences:
                if len(current_chunk) + len(sent) + 2 > max_size and current_chunk:
                    chunks.append(current_chunk.strip())
                    overlap_tail = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                    current_chunk = overlap_tail + " " + sent
                else:
                    current_chunk = (current_chunk + "\n\n" + sent).strip() if current_chunk else sent
        else:
            if len(current_chunk) + len(para) + 2 > max_size and current_chunk:
                chunks.append(current_chunk.strip())
                overlap_tail = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = (overlap_tail + "\n\n" + para).strip()
            else:
                current_chunk = (current_chunk + "\n\n" + para).strip() if current_chunk else para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ─── Table chunk builder ───────────────────────────────────────────────────────

def _build_table_chunk(
    table: dict,
    chunk_index: int,
    document_id: str,
    document_name: str,
    source_path: str,
    extraction_method: str,
    ocr_used: bool,
    section_tracker: SectionTracker,
) -> dict:
    """Build a single chunk for a complete table."""
    page_number = table.get("page_number", 0)
    table_id = table.get("table_id", "")
    text = make_table_chunk_text(table)

    chunk_id = make_chunk_id(document_id, page_number, chunk_index)

    return build_chunk_metadata(
        chunk_id=chunk_id,
        document_id=document_id,
        document_name=document_name,
        source_path=source_path,
        page_start=page_number,
        page_end=page_number,
        section=section_tracker.section,
        subsection=section_tracker.subsection,
        heading=section_tracker.heading,
        chunk_index=chunk_index,
        content_type="table",
        extraction_method=extraction_method,
        ocr_used=ocr_used,
        ocr_confidence=None,
        has_table=True,
        table_id=table_id,
        text=text,
    )


# ─── Main chunking function ────────────────────────────────────────────────────

def chunk_document(
    document_id: str,
    document_name: str,
    source_path: str,
    pages: List[dict],
    tables: List[dict],
    extraction_method: str,
    ocr_used: bool,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> List[dict]:
    """
    Produce all chunks for a single document.

    Parameters
    ----------
    document_id : str
    document_name : str   Human-readable name (filename without extension)
    source_path : str
    pages : List[dict]    Cleaned page dicts from cleaner.clean_document_pages()
    tables : List[dict]   Table dicts from table_extractor
    extraction_method : str
    ocr_used : bool
    chunk_size, overlap : int  Configurable

    Returns
    -------
    List[dict]  — fully populated chunk metadata dicts
    """
    chunks: List[dict] = []
    chunk_counter = 0
    section_tracker = SectionTracker()

    # Build a page → tables mapping for O(1) lookup
    tables_by_page: dict = {}
    for table in tables:
        pn = table.get("page_number", 0)
        tables_by_page.setdefault(pn, []).append(table)

    # Track which table IDs have been emitted (avoid duplicates)
    emitted_table_ids: set = set()

    for page in pages:
        page_number = page.get("page_number", 0)
        cleaned_text = page.get("cleaned_text", "").strip()
        ocr_confidence = page.get("ocr_confidence")
        blocks = page.get("blocks", [])

        # ── Emit table chunks for this page first ──────────────────────────
        page_tables = tables_by_page.get(page_number, [])
        for table in page_tables:
            tid = table.get("table_id", "")
            if tid in emitted_table_ids:
                continue
            emitted_table_ids.add(tid)

            tbl_chunk = _build_table_chunk(
                table=table,
                chunk_index=chunk_counter,
                document_id=document_id,
                document_name=document_name,
                source_path=source_path,
                extraction_method=extraction_method,
                ocr_used=ocr_used,
                section_tracker=section_tracker,
            )
            tbl_chunk["ocr_confidence"] = ocr_confidence
            chunks.append(tbl_chunk)
            chunk_counter += 1

        if not cleaned_text:
            logger.debug("Page %d: empty cleaned text, skipping text chunks", page_number)
            continue

        # ── For native PDFs with detected blocks, use heading structure ────
        if blocks and any(b.get("is_heading") for b in blocks):
            # Collect segments: heading blocks start new sections,
            # body blocks accumulate until next heading or page end
            pending_text_parts = []

            def _flush_pending(flush_page: int):
                nonlocal chunk_counter
                if not pending_text_parts:
                    return
                combined = "\n\n".join(pending_text_parts)
                for sub_chunk_text in _chunk_text(combined, chunk_size, overlap):
                    if not sub_chunk_text.strip():
                        continue
                    chunk_id = make_chunk_id(document_id, flush_page, chunk_counter)
                    chunk = build_chunk_metadata(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        document_name=document_name,
                        source_path=source_path,
                        page_start=flush_page,
                        page_end=flush_page,
                        section=section_tracker.section,
                        subsection=section_tracker.subsection,
                        heading=section_tracker.heading,
                        chunk_index=chunk_counter,
                        content_type="text",
                        extraction_method=extraction_method,
                        ocr_used=ocr_used,
                        ocr_confidence=ocr_confidence,
                        has_table=False,
                        table_id=None,
                        text=sub_chunk_text,
                    )
                    chunks.append(chunk)
                    chunk_counter += 1
                pending_text_parts.clear()

            for block in blocks:
                if block.get("is_image"):
                    continue
                btext = block.get("text", "").strip()
                if not btext:
                    continue

                if block.get("is_heading"):
                    level = block.get("heading_level", 3)
                    _flush_pending(page_number)
                    section_tracker.update(btext, level)
                    # Emit heading as its own tiny chunk
                    chunk_id = make_chunk_id(document_id, page_number, chunk_counter)
                    chunk = build_chunk_metadata(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        document_name=document_name,
                        source_path=source_path,
                        page_start=page_number,
                        page_end=page_number,
                        section=section_tracker.section,
                        subsection=section_tracker.subsection,
                        heading=section_tracker.heading,
                        chunk_index=chunk_counter,
                        content_type="heading",
                        extraction_method=extraction_method,
                        ocr_used=ocr_used,
                        ocr_confidence=ocr_confidence,
                        has_table=False,
                        table_id=None,
                        text=btext,
                    )
                    chunks.append(chunk)
                    chunk_counter += 1
                else:
                    pending_text_parts.append(btext)

            _flush_pending(page_number)

        else:
            # ── Paragraph-based chunking (OCR pages / flat native pages) ──
            for sub_chunk_text in _chunk_text(cleaned_text, chunk_size, overlap):
                if not sub_chunk_text.strip():
                    continue
                chunk_id = make_chunk_id(document_id, page_number, chunk_counter)
                chunk = build_chunk_metadata(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    document_name=document_name,
                    source_path=source_path,
                    page_start=page_number,
                    page_end=page_number,
                    section=section_tracker.section,
                    subsection=section_tracker.subsection,
                    heading=section_tracker.heading,
                    chunk_index=chunk_counter,
                    content_type="text",
                    extraction_method=extraction_method,
                    ocr_used=ocr_used,
                    ocr_confidence=ocr_confidence,
                    has_table=False,
                    table_id=None,
                    text=sub_chunk_text,
                )
                chunks.append(chunk)
                chunk_counter += 1

    logger.info(
        "Chunking complete: %r → %d chunks (%d tables)",
        document_name,
        len(chunks),
        sum(1 for c in chunks if c["has_table"]),
    )
    return chunks


# ─── Validation helpers ────────────────────────────────────────────────────────

def validate_chunks(chunks: List[dict]) -> List[dict]:
    """
    Run sanity checks on produced chunks.

    Returns a list of warning dicts: {chunk_id, issue}.
    """
    issues = []
    seen_ids = set()

    for chunk in chunks:
        cid = chunk.get("chunk_id", "MISSING")
        text = chunk.get("text", "")
        char_count = len(text)

        if cid in seen_ids:
            issues.append({"chunk_id": cid, "issue": "duplicate chunk_id"})
        seen_ids.add(cid)

        if char_count < CHUNK_MIN_CHARS:
            issues.append({"chunk_id": cid, "issue": f"very small chunk ({char_count} chars)"})

        if char_count > CHUNK_MAX_CHARS:
            issues.append({"chunk_id": cid, "issue": f"very large chunk ({char_count} chars)"})

        if not chunk.get("document_id"):
            issues.append({"chunk_id": cid, "issue": "missing document_id"})

        if not text.strip():
            issues.append({"chunk_id": cid, "issue": "empty text"})

    return issues
