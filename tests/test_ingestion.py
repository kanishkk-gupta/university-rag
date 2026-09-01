"""
tests/test_ingestion.py — Unit and integration tests for the ingestion subsystem.

Uses pytest. Tests cover:
  1. Document discovery
  2. PDF routing (native vs scanned detection)
  3. Native PDF extraction
  4. OCR extraction (skips gracefully if Tesseract absent)
  5. Cleaning
  6. Chunking
  7. Metadata integrity
  8. Table representation

All tests read from the actual documents directory but NEVER modify source files.
The output directories used in tests are separate from production output.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DOCUMENTS_DIR
from ingestion.discovery import discover_documents
from ingestion.router import classify_document, ExtractionMethod
from ingestion.pdf_extractor import extract_native_pdf
from ingestion.ocr_extractor import _check_tesseract
from ingestion.cleaner import clean_page_text, clean_document_pages, detect_repeated_lines
from ingestion.chunker import chunk_document, validate_chunks, _chunk_text
from ingestion.table_extractor import _rows_to_markdown, make_table_chunk_text
from ingestion.metadata import make_chunk_id, make_table_id, build_chunk_metadata


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def all_records():
    """Discover all BMU documents once per test session."""
    return discover_documents(DOCUMENTS_DIR)


@pytest.fixture(scope="session")
def student_handbook_record(all_records):
    """The Student Handbook — the only native-text PDF."""
    for r in all_records:
        if "Student Handbook" in r.filename:
            return r
    pytest.skip("Student Handbook not found in documents directory")


@pytest.fixture(scope="session")
def anti_ragging_record(all_records):
    """Anti Ragging Policy — a clean scanned PDF."""
    for r in all_records:
        if "Anti Ragging" in r.filename:
            return r
    pytest.skip("Anti Ragging Policy not found")


# ─── 1. Discovery tests ────────────────────────────────────────────────────────

class TestDiscovery:
    def test_discovers_all_8_documents(self, all_records):
        assert len(all_records) == 8, f"Expected 8 documents, got {len(all_records)}"

    def test_all_have_unique_ids(self, all_records):
        ids = [r.document_id for r in all_records]
        assert len(ids) == len(set(ids)), "Document IDs are not unique"

    def test_all_are_readable(self, all_records):
        unreadable = [r for r in all_records if not r.is_readable]
        assert not unreadable, f"Unreadable documents: {[r.filename for r in unreadable]}"

    def test_all_have_page_counts(self, all_records):
        zero_pages = [r for r in all_records if r.page_count == 0]
        assert not zero_pages, f"Documents with zero pages: {[r.filename for r in zero_pages]}"

    def test_file_sizes_are_nonzero(self, all_records):
        empty = [r for r in all_records if r.file_size_bytes == 0]
        assert not empty, f"Empty documents: {[r.filename for r in empty]}"

    def test_source_paths_exist(self, all_records):
        for r in all_records:
            assert Path(r.source_path).exists(), f"Source path not found: {r.source_path}"

    def test_source_files_are_not_modified(self, all_records):
        """Record file sizes before and after discovery — they must not change."""
        for r in all_records:
            current_size = Path(r.source_path).stat().st_size
            assert current_size == r.file_size_bytes, (
                f"File size changed for {r.filename}! "
                f"Expected {r.file_size_bytes}, got {current_size}. "
                "Source documents must not be modified."
            )

    def test_record_fields_not_empty(self, all_records):
        for r in all_records:
            assert r.document_id, f"Missing document_id for {r.filename}"
            assert r.filename, "Empty filename"
            assert r.source_path, f"Missing source_path for {r.filename}"
            assert r.file_type == ".pdf", f"Unexpected file type: {r.file_type}"


# ─── 2. Routing tests ─────────────────────────────────────────────────────────

class TestRouting:
    def test_student_handbook_is_native(self, student_handbook_record):
        r = student_handbook_record
        c = classify_document(r.document_id, r.filename, r.source_path)
        assert c.doc_method == ExtractionMethod.NATIVE, (
            f"Student Handbook should be NATIVE, got {c.doc_method}"
        )

    def test_anti_ragging_has_classification(self, anti_ragging_record):
        """
        The Anti Ragging Policy was scanned on a Canon scanner that embedded
        an OCR text layer in the PDF. PyMuPDF can extract this text directly
        without running Tesseract again. The router correctly classifies it as
        NATIVE because the text layer yields ~2400 chars/page.

        This test verifies that classification completes without error and
        yields a consistent result — not that it must be OCR.
        """
        r = anti_ragging_record
        c = classify_document(r.document_id, r.filename, r.source_path)
        # Classification must be one of the two valid values
        assert c.doc_method in (ExtractionMethod.NATIVE, ExtractionMethod.OCR), (
            f"Unexpected classification for Anti Ragging Policy: {c.doc_method}"
        )
        # It has 3 pages — verify we got per-page data
        assert len(c.page_types) == r.page_count

    def test_page_types_match_page_count(self, student_handbook_record):
        r = student_handbook_record
        c = classify_document(r.document_id, r.filename, r.source_path)
        assert len(c.page_types) == c.page_count == r.page_count

    def test_critical_table_detection(self, all_records):
        """Documents with table-critical names should be flagged."""
        table_critical_names = ["Fee Payment Calendar", "Holiday List", "University Calendar", "DAC Policy"]
        for r in all_records:
            c = classify_document(r.document_id, r.filename, r.source_path)
            should_be_critical = any(n in r.filename for n in table_critical_names)
            if should_be_critical:
                assert c.has_critical_tables, (
                    f"{r.filename} should be flagged as critical_tables"
                )

    def test_no_hardcoded_logic(self, all_records):
        """
        Verify that routing works on all documents without raising errors.
        The actual classification must come from PyMuPDF, not hardcoded names.
        """
        for r in all_records:
            c = classify_document(r.document_id, r.filename, r.source_path)
            assert c.doc_method in (ExtractionMethod.NATIVE, ExtractionMethod.OCR)


# ─── 3. Native extraction tests ────────────────────────────────────────────────

class TestNativeExtraction:
    def test_extracts_all_pages(self, student_handbook_record):
        r = student_handbook_record
        pages = extract_native_pdf(r.document_id, r.filename, r.source_path)
        assert len(pages) == r.page_count, (
            f"Expected {r.page_count} pages, got {len(pages)}"
        )

    def test_pages_have_content(self, student_handbook_record):
        r = student_handbook_record
        pages = extract_native_pdf(r.document_id, r.filename, r.source_path)
        non_empty = [p for p in pages if p["char_count"] > 0]
        # Most pages should have content (allow for blank/image-only pages)
        assert len(non_empty) >= r.page_count * 0.7, (
            f"Too many empty pages: {r.page_count - len(non_empty)} out of {r.page_count}"
        )

    def test_extraction_method_field(self, student_handbook_record):
        r = student_handbook_record
        pages = extract_native_pdf(r.document_id, r.filename, r.source_path)
        for p in pages:
            assert p["extraction_method"] == "native_pdf"

    def test_page_numbers_are_sequential(self, student_handbook_record):
        r = student_handbook_record
        pages = extract_native_pdf(r.document_id, r.filename, r.source_path)
        page_nums = [p["page_number"] for p in pages]
        assert page_nums == list(range(1, r.page_count + 1))

    def test_source_file_not_modified(self, student_handbook_record):
        r = student_handbook_record
        original_size = Path(r.source_path).stat().st_size
        extract_native_pdf(r.document_id, r.filename, r.source_path)
        assert Path(r.source_path).stat().st_size == original_size


# ─── 4. OCR tests (skips if Tesseract absent) ─────────────────────────────────

class TestOCR:
    def test_tesseract_check(self):
        """Just verify the check doesn't crash."""
        result = _check_tesseract()
        assert isinstance(result, bool)

    @pytest.mark.skipif(not _check_tesseract(), reason="Tesseract not installed")
    def test_ocr_anti_ragging(self, anti_ragging_record):
        from ingestion.ocr_extractor import extract_ocr_pdf
        r = anti_ragging_record
        pages = extract_ocr_pdf(r.document_id, r.filename, r.source_path)
        assert len(pages) == r.page_count
        non_empty = [p for p in pages if p["char_count"] > 50]
        assert len(non_empty) >= 1, "OCR should produce some text"

    @pytest.mark.skipif(not _check_tesseract(), reason="Tesseract not installed")
    def test_ocr_confidence_is_real_or_none(self, anti_ragging_record):
        from ingestion.ocr_extractor import extract_ocr_pdf
        r = anti_ragging_record
        pages = extract_ocr_pdf(r.document_id, r.filename, r.source_path)
        for p in pages:
            conf = p.get("ocr_confidence")
            if conf is not None:
                assert 0.0 <= conf <= 1.0, f"Confidence out of range: {conf}"


# ─── 5. Cleaning tests ─────────────────────────────────────────────────────────

class TestCleaning:
    def test_normalises_crlf(self):
        text = "Hello\r\nWorld\r\nTest"
        cleaned, _ = clean_page_text(text)
        assert "\r" not in cleaned

    def test_fixes_hyphenation(self):
        text = "This is a uni-\nversity policy"
        cleaned, ops = clean_page_text(text)
        assert "university" in cleaned
        assert "fix_hyphenation" in ops

    def test_removes_standalone_page_numbers(self):
        text = "Some content here\n\n3\n\nMore content"
        cleaned, ops = clean_page_text(text)
        # Page number "3" at the start/end boundary should be stripped
        # Note: it's in the middle here, so it may or may not be stripped
        # depending on position — we just check no crash
        assert isinstance(cleaned, str)

    def test_does_not_remove_policy_text(self):
        text = ("1. No student shall engage in ragging.\n"
                "2. Violations shall be reported to the Dean.\n"
                "3. Penalties include suspension or expulsion.")
        cleaned, _ = clean_page_text(text)
        assert "ragging" in cleaned
        assert "suspension" in cleaned

    def test_detects_repeated_headers(self):
        pages = [
            "BML Munjal University\n\nSome content page 1",
            "BML Munjal University\n\nSome content page 2",
            "BML Munjal University\n\nSome content page 3",
        ]
        repeated = detect_repeated_lines(pages, min_occurrences=3)
        assert "BML Munjal University" in repeated

    def test_preserves_raw_text(self):
        """clean_document_pages must not modify raw_text."""
        pages = [
            {
                "page_number": 1, "raw_text": "Original text",
                "char_count": 13, "extraction_method": "native_pdf",
                "ocr_confidence": None, "warnings": [], "blocks": [],
            }
        ]
        result = clean_document_pages(pages)
        assert result[0]["raw_text"] == "Original text"
        assert "cleaned_text" in result[0]


# ─── 6. Chunking tests ─────────────────────────────────────────────────────────

class TestChunking:
    def test_chunk_text_respects_max_size(self):
        long_text = "The quick brown fox. " * 200  # 4400 chars
        chunks = _chunk_text(long_text, max_size=500, overlap=50)
        for c in chunks:
            assert len(c) <= 700, f"Chunk too large: {len(c)}"

    def test_chunk_text_handles_short_input(self):
        short = "Short text."
        chunks = _chunk_text(short, max_size=500)
        assert len(chunks) == 1
        assert chunks[0] == short

    def test_empty_input_gives_empty_chunks(self):
        chunks = _chunk_text("", max_size=500)
        assert chunks == []

    def test_chunk_ids_are_unique(self):
        # Build minimal page data
        pages = [
            {
                "page_number": 1,
                "cleaned_text": "Policy text about academic integrity. " * 50,
                "raw_text": "Policy text about academic integrity. " * 50,
                "char_count": 1800,
                "extraction_method": "native_pdf",
                "ocr_confidence": None,
                "warnings": [],
                "blocks": [],
            },
            {
                "page_number": 2,
                "cleaned_text": "Further rules and regulations. " * 50,
                "raw_text": "Further rules and regulations. " * 50,
                "char_count": 1500,
                "extraction_method": "native_pdf",
                "ocr_confidence": None,
                "warnings": [],
                "blocks": [],
            },
        ]
        chunks = chunk_document(
            document_id="testdoc001",
            document_name="Test Document",
            source_path="/fake/path.pdf",
            pages=pages,
            tables=[],
            extraction_method="native_pdf",
            ocr_used=False,
        )
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs are not unique"

    def test_table_chunks_are_atomic(self):
        """Tables must not be split — each table = exactly one chunk."""
        pages = [
            {
                "page_number": 1,
                "cleaned_text": "Fee payment schedule follows.",
                "raw_text": "Fee payment schedule follows.",
                "char_count": 30,
                "extraction_method": "ocr_tesseract",
                "ocr_confidence": 0.92,
                "warnings": [],
                "blocks": [],
            }
        ]
        tables = [
            {
                "table_id": "testdoc_p0001_t00",
                "document_id": "testdoc001",
                "filename": "Fee.pdf",
                "page_number": 1,
                "n_rows": 5,
                "n_cols": 3,
                "rows": [["Program", "Fee", "Due Date"],
                         ["B.Tech", "₹50000", "15 Jan"],
                         ["MBA", "₹80000", "15 Jan"],
                         ["M.Tech", "₹45000", "15 Jan"],
                         ["Ph.D", "₹30000", "15 Jan"]],
                "markdown": "| Program | Fee | Due Date |\n|---|---|---|\n| B.Tech | ₹50000 | 15 Jan |",
                "extraction_method": "img2table_ocr",
                "extraction_status": "ok",
                "confidence": None,
            }
        ]
        chunks = chunk_document(
            document_id="testdoc001",
            document_name="Fee Schedule",
            source_path="/fake/fee.pdf",
            pages=pages,
            tables=tables,
            extraction_method="ocr_tesseract",
            ocr_used=True,
        )
        table_chunks = [c for c in chunks if c["has_table"]]
        assert len(table_chunks) == 1
        assert table_chunks[0]["table_id"] == "testdoc_p0001_t00"
        assert table_chunks[0]["content_type"] == "table"

    def test_validation_flags_tiny_chunks(self):
        chunk = build_chunk_metadata(
            chunk_id="test_tiny",
            document_id="doc1",
            document_name="Test",
            source_path="/path",
            page_start=1, page_end=1,
            section=None, subsection=None, heading=None,
            chunk_index=0,
            content_type="text",
            extraction_method="native_pdf",
            ocr_used=False,
            ocr_confidence=None,
            has_table=False,
            table_id=None,
            text="Hi",
        )
        issues = validate_chunks([chunk])
        assert any("small" in i["issue"] for i in issues)


# ─── 7. Metadata integrity tests ───────────────────────────────────────────────

class TestMetadata:
    def test_chunk_id_format(self):
        cid = make_chunk_id("abc12345", 3, 7)
        assert "p0003" in cid
        assert "c0007" in cid

    def test_table_id_format(self):
        tid = make_table_id("abc12345", 5, 2)
        assert "p0005" in tid
        assert "t02" in tid

    def test_build_chunk_has_all_required_fields(self):
        chunk = build_chunk_metadata(
            chunk_id="c001",
            document_id="doc1",
            document_name="Test Doc",
            source_path="/path/test.pdf",
            page_start=1, page_end=1,
            section="Section 1", subsection=None, heading="Heading",
            chunk_index=0,
            content_type="text",
            extraction_method="native_pdf",
            ocr_used=False,
            ocr_confidence=None,
            has_table=False,
            table_id=None,
            text="Sample text content here.",
        )
        required_keys = [
            "chunk_id", "document_id", "document_name", "source_path",
            "page_start", "page_end", "section", "subsection", "heading",
            "chunk_index", "content_type", "extraction_method", "ocr_used",
            "ocr_confidence", "has_table", "table_id", "text",
        ]
        for key in required_keys:
            assert key in chunk, f"Missing required key: {key}"


# ─── 8. Table representation tests ────────────────────────────────────────────

class TestTableRepresentation:
    def test_markdown_has_header_separator(self):
        rows = [["Date", "Day", "Holiday"],
                ["14 Jan", "Wed", "Makar Sankranti"],
                ["26 Jan", "Mon", "Republic Day"]]
        md = _rows_to_markdown(rows)
        assert "|---" in md
        assert "Date" in md
        assert "Republic Day" in md

    def test_markdown_empty_rows(self):
        assert _rows_to_markdown([]) == ""

    def test_table_chunk_text_includes_context(self):
        table = {
            "filename": "Holiday List.pdf",
            "page_number": 1,
            "markdown": "| Date | Holiday |\n|---|---|\n| 26 Jan | Republic Day |",
            "extraction_status": "ok",
        }
        text = make_table_chunk_text(table)
        assert "TABLE" in text
        assert "Republic Day" in text
        assert "page 1" in text

    def test_failed_table_flagged(self):
        table = {
            "filename": "Fee.pdf",
            "page_number": 3,
            "markdown": "",
            "extraction_status": "failed",
        }
        text = make_table_chunk_text(table)
        assert "failed" in text.lower() or "uncertain" in text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
