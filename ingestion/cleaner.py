"""
ingestion/cleaner.py — Post-extraction text cleaning.

Applied AFTER extraction (native or OCR). The cleaning is conservative:
  - We never remove text just because it looks repetitive unless we can
    confidently identify it as a header/footer artifact.
  - We never alter substantive policy language.
  - Cleaning is flagged: every step that modifies text is recorded.

Cleaning steps (in order):
  1. Normalise line endings (\r\n → \n)
  2. Collapse excessive blank lines (>2 consecutive → 2)
  3. Fix OCR hyphenation across lines (word-\nnext → wordnext)
  4. Strip page-number noise (standalone digit lines at page boundaries)
  5. Remove identified header/footer repeats across pages (conservative)
  6. Collapse multiple spaces in a line
  7. Strip leading/trailing whitespace per line

We do NOT:
  - Remove content that appears on <2 pages
  - Alter wording
  - Remove capitalized content
  - Silently swallow errors
"""

import logging
import re
from collections import Counter
from typing import List, Tuple

logger = logging.getLogger(__name__)


# ─── Single-page cleaning ──────────────────────────────────────────────────────

def clean_page_text(text: str) -> Tuple[str, List[str]]:
    """
    Clean a single page's extracted text.

    Returns (cleaned_text, list_of_applied_operations).
    The operations list is for audit/debugging.
    """
    if not text:
        return text, []

    ops = []
    original = text

    # 1. Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Fix OCR hyphenation: word-\nword → wordword (conservative: only clear cases)
    before = text
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    if text != before:
        ops.append("fix_hyphenation")

    # 3. Strip leading/trailing whitespace per line
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]

    # 4. Collapse excessive internal whitespace per line (but preserve indentation signals)
    cleaned_lines = []
    for line in lines:
        # Only collapse if 3+ spaces in the middle of a line
        line = re.sub(r"  +", " ", line)
        cleaned_lines.append(line)
    lines = cleaned_lines

    # 5. Remove lines that are ONLY page numbers (isolated digits, possibly with whitespace)
    before_count = len(lines)
    def is_page_number_line(line: str) -> bool:
        stripped = line.strip()
        # Pure number, possibly with "Page", "Pg", "- N -" patterns
        if re.fullmatch(r"\d{1,4}", stripped):
            return True
        if re.fullmatch(r"[-–]\s*\d{1,4}\s*[-–]", stripped):
            return True
        if re.fullmatch(r"(Page|Pg\.?)\s*\d{1,4}", stripped, re.IGNORECASE):
            return True
        return False

    filtered_lines = []
    for i, line in enumerate(lines):
        # Only strip page numbers if they appear at the very start or end of the page text
        # (within first 2 or last 2 lines) and are short isolated numbers
        near_edge = (i < 2 or i >= len(lines) - 2)
        if near_edge and is_page_number_line(line):
            ops.append(f"removed_page_number_line: {repr(line.strip())}")
            continue
        filtered_lines.append(line)
    lines = filtered_lines

    # 6. Collapse consecutive blank lines to maximum 2
    result_lines = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                result_lines.append(line)
        else:
            blank_count = 0
            result_lines.append(line)
    lines = result_lines

    text = "\n".join(lines).strip()

    if text != original.strip():
        if "fix_hyphenation" not in ops:
            ops.append("whitespace_normalization")

    return text, ops


# ─── Cross-page header/footer detection ───────────────────────────────────────

def detect_repeated_lines(pages_text: List[str], min_occurrences: int = 3) -> set:
    """
    Identify lines that appear verbatim on many pages — likely headers/footers.

    Conservative: a line must appear on at least `min_occurrences` pages
    to be considered repeated boilerplate. Short lines (<10 chars) are excluded
    to avoid stripping substantive short content.

    Returns a set of line strings to be considered for removal.
    """
    line_counter: Counter = Counter()

    for page_text in pages_text:
        page_lines = set(line.strip() for line in page_text.split("\n"))
        for line in page_lines:
            if len(line) >= 10:  # ignore very short lines
                line_counter[line] += 1

    repeated = {
        line for line, count in line_counter.items()
        if count >= min_occurrences
    }
    return repeated


def remove_repeated_lines(text: str, repeated_lines: set) -> Tuple[str, List[str]]:
    """
    Remove lines identified as repeated boilerplate from a page's text.

    Returns (cleaned_text, list_of_removed_lines).
    """
    if not repeated_lines:
        return text, []

    removed = []
    result = []
    for line in text.split("\n"):
        if line.strip() in repeated_lines:
            removed.append(line.strip())
        else:
            result.append(line)

    return "\n".join(result), removed


# ─── Document-level cleaning ───────────────────────────────────────────────────

def clean_document_pages(pages: List[dict], min_repeat: int = 3) -> List[dict]:
    """
    Clean all pages of a document.

    Steps:
      1. Per-page cleaning (normalisation, hyphenation, noise)
      2. Cross-page header/footer detection
      3. Header/footer removal

    Parameters
    ----------
    pages : List[dict]
        Page metadata dicts from pdf_extractor or ocr_extractor.
    min_repeat : int
        Minimum page count for a line to be considered repeated boilerplate.

    Returns
    -------
    List[dict]
        Pages with added 'cleaned_text' and 'cleaning_ops' fields.
        The original 'raw_text' field is preserved unchanged.
    """
    if not pages:
        return pages

    # Step 1: per-page cleaning
    for page in pages:
        raw = page.get("raw_text", "")
        cleaned, ops = clean_page_text(raw)
        page["cleaned_text"] = cleaned
        page["cleaning_ops"] = ops

    # Step 2: detect repeated lines across pages
    cleaned_texts = [p.get("cleaned_text", "") for p in pages]
    repeated = detect_repeated_lines(cleaned_texts, min_occurrences=min_repeat)

    if repeated:
        logger.info(
            "Detected %d repeated header/footer lines across %d pages",
            len(repeated), len(pages),
        )
        for line in sorted(repeated)[:5]:  # log a sample
            logger.debug("  Repeated line: %r", line[:80])

    # Step 3: remove repeated lines
    for page in pages:
        cleaned = page.get("cleaned_text", "")
        final, removed = remove_repeated_lines(cleaned, repeated)
        page["cleaned_text"] = final
        if removed:
            page["cleaning_ops"].extend([f"removed_repeated: {repr(r[:40])}" for r in removed])

    return pages
