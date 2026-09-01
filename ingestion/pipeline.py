"""
ingestion/pipeline.py — End-to-end ingestion orchestration.

Runs the complete ingestion pipeline for all discovered documents:
  1. Discovery
  2. Classification (native vs scanned)
  3. Extraction (native PDF or OCR)
  4. Table extraction
  5. Cleaning
  6. Chunking
  7. Validation
  8. Output (JSONL files per document + combined chunks file)

Produces structured output in data/extracted/ and data/chunks/.
No embeddings, no vector store, no LLM — this is purely ingestion.

All exceptions are caught per-document: one failing document does not
abort the entire pipeline. Failures are recorded in the report.
"""

import json
import logging
import os
import statistics
import time
from pathlib import Path
from typing import List, Optional

from config import (
    DOCUMENTS_DIR,
    EXTRACTED_DIR,
    CHUNKS_DIR,
    EXTRACTED_PAGES_SUFFIX,
    CHUNKS_OUTPUT_FILE,
    OCR_DPI,
    OCR_PSM_DEFAULT,
)
from ingestion.discovery import discover_documents, DocumentRecord
from ingestion.router import classify_document, ExtractionMethod
from ingestion.pdf_extractor import extract_native_pdf
from ingestion.ocr_extractor import extract_ocr_pdf, _check_tesseract
from ingestion.table_extractor import extract_tables_native, extract_tables_scanned
from ingestion.cleaner import clean_document_pages
from ingestion.chunker import chunk_document, validate_chunks

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


# ─── JSONL I/O helpers ─────────────────────────────────────────────────────────

def _save_jsonl(records: list, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _load_jsonl(path: Path) -> list:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ─── Per-document pipeline ─────────────────────────────────────────────────────

def process_document(record: DocumentRecord) -> dict:
    """
    Run the full ingestion pipeline for a single document.

    Returns a report dict with statistics and any warnings/errors.
    """
    doc_report = {
        "document_id": record.document_id,
        "filename": record.filename,
        "source_path": record.source_path,
        "file_size_bytes": record.file_size_bytes,
        "page_count": record.page_count,
        "extraction_method": None,
        "native_pages": 0,
        "ocr_pages": 0,
        "total_chars": 0,
        "total_chunks": 0,
        "tables_detected": 0,
        "ocr_confidence_min": None,
        "ocr_confidence_max": None,
        "ocr_confidence_avg": None,
        "warnings": [],
        "errors": [],
        "status": "ok",
        "processing_time_s": 0.0,
    }

    start_time = time.time()

    # ── Step 1: Classify ───────────────────────────────────────────────────
    try:
        classification = classify_document(
            document_id=record.document_id,
            filename=record.filename,
            source_path=record.source_path,
        )
    except Exception as exc:
        msg = f"Classification failed: {exc}"
        logger.error("  %s: %s", record.filename, msg)
        doc_report["errors"].append(msg)
        doc_report["status"] = "failed"
        doc_report["processing_time_s"] = round(time.time() - start_time, 2)
        return doc_report

    doc_report["extraction_method"] = classification.doc_method.value
    doc_report["native_pages"] = classification.native_page_count
    doc_report["ocr_pages"] = classification.scanned_page_count

    # ── Step 2: Extract ────────────────────────────────────────────────────
    pages = []
    try:
        if classification.doc_method == ExtractionMethod.NATIVE:
            pages = extract_native_pdf(
                document_id=record.document_id,
                filename=record.filename,
                source_path=record.source_path,
            )
        else:
            # Check tesseract before attempting OCR
            if not _check_tesseract():
                msg = (
                    "Tesseract not installed — OCR skipped. "
                    "Run: sudo apt install tesseract-ocr"
                )
                logger.warning("  %s: %s", record.filename, msg)
                doc_report["warnings"].append(msg)
                doc_report["status"] = "ocr_skipped"
                doc_report["processing_time_s"] = round(time.time() - start_time, 2)
                return doc_report

            pages = extract_ocr_pdf(
                document_id=record.document_id,
                filename=record.filename,
                source_path=record.source_path,
                dpi=OCR_DPI,
                psm=OCR_PSM_DEFAULT,
                has_critical_tables=classification.has_critical_tables,
            )

    except Exception as exc:
        msg = f"Extraction failed: {exc}"
        logger.error("  %s: %s", record.filename, msg)
        doc_report["errors"].append(msg)
        doc_report["status"] = "failed"
        doc_report["processing_time_s"] = round(time.time() - start_time, 2)
        return doc_report

    # Collect warnings from individual pages
    for page in pages:
        for w in page.get("warnings", []):
            doc_report["warnings"].append(f"p{page['page_number']}: {w}")

    # ── Step 3: Extract tables ─────────────────────────────────────────────
    tables = []
    try:
        if classification.doc_method == ExtractionMethod.NATIVE:
            tables = extract_tables_native(
                document_id=record.document_id,
                filename=record.filename,
                source_path=record.source_path,
            )
        elif classification.has_critical_tables:
            tables = extract_tables_scanned(
                document_id=record.document_id,
                filename=record.filename,
                source_path=record.source_path,
                dpi=OCR_DPI,
            )
    except Exception as exc:
        msg = f"Table extraction warning: {exc}"
        logger.warning("  %s: %s", record.filename, msg)
        doc_report["warnings"].append(msg)

    doc_report["tables_detected"] = len(tables)

    # ── Step 4: Clean ──────────────────────────────────────────────────────
    try:
        pages = clean_document_pages(pages)
    except Exception as exc:
        msg = f"Cleaning warning: {exc}"
        logger.warning("  %s: %s", record.filename, msg)
        doc_report["warnings"].append(msg)
        # Fall back: add cleaned_text = raw_text
        for page in pages:
            if "cleaned_text" not in page:
                page["cleaned_text"] = page.get("raw_text", "")
                page["cleaning_ops"] = []

    # ── Step 5: Chunk ──────────────────────────────────────────────────────
    document_name = Path(record.filename).stem
    ocr_used = classification.doc_method == ExtractionMethod.OCR

    try:
        chunks = chunk_document(
            document_id=record.document_id,
            document_name=document_name,
            source_path=record.source_path,
            pages=pages,
            tables=tables,
            extraction_method=classification.doc_method.value,
            ocr_used=ocr_used,
        )
    except Exception as exc:
        msg = f"Chunking failed: {exc}"
        logger.error("  %s: %s", record.filename, msg)
        doc_report["errors"].append(msg)
        doc_report["status"] = "partial"
        chunks = []

    # ── Step 6: Validate ───────────────────────────────────────────────────
    issues = validate_chunks(chunks)
    for issue in issues:
        doc_report["warnings"].append(f"Chunk {issue['chunk_id']}: {issue['issue']}")

    # ── Step 7: Compute stats ──────────────────────────────────────────────
    doc_report["total_chars"] = sum(p.get("char_count", 0) for p in pages)
    doc_report["total_chunks"] = len(chunks)

    confidences = [
        p["ocr_confidence"]
        for p in pages
        if p.get("ocr_confidence") is not None
    ]
    if confidences:
        avg_conf = statistics.mean(confidences)
        doc_report["ocr_confidence_min"] = round(min(confidences), 4)
        doc_report["ocr_confidence_max"] = round(max(confidences), 4)
        doc_report["ocr_confidence_avg"] = round(avg_conf, 4)
        if avg_conf < 0.70:
            doc_report["warnings"].append(f"Document has unusually low median OCR confidence: {avg_conf:.2f}")

    # Check for critical tabular extraction failure
    if classification.has_critical_tables and doc_report["tables_detected"] == 0:
        doc_report["warnings"].append("Critical: Tabular document detected 0 tables. Extraction failed.")


    # ── Step 8: Save outputs ───────────────────────────────────────────────
    safe_name = record.filename.replace(" ", "_").replace("/", "_")

    # Save extracted pages
    pages_path = EXTRACTED_DIR / (safe_name + EXTRACTED_PAGES_SUFFIX)
    _save_jsonl(pages, pages_path)

    # Save tables
    if tables:
        tables_path = EXTRACTED_DIR / (safe_name + "_tables.jsonl")
        _save_jsonl(tables, tables_path)

    # Save chunks
    chunks_path = CHUNKS_DIR / (safe_name + "_chunks.jsonl")
    _save_jsonl(chunks, chunks_path)

    doc_report["processing_time_s"] = round(time.time() - start_time, 2)
    return doc_report, chunks


# ─── Full pipeline ──────────────────────────────────────────────────────────────

def run_pipeline(documents_dir: Path = DOCUMENTS_DIR) -> dict:
    """
    Run the complete ingestion pipeline for all documents.

    Returns a validation report dict suitable for human review.
    """
    logger.info("=" * 60)
    logger.info("BMU University RAG — Ingestion Pipeline")
    logger.info("=" * 60)

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Discover all documents ──────────────────────────────────────────
    records = discover_documents(documents_dir)
    if not records:
        logger.error("No documents found in %s", documents_dir)
        return {"error": "No documents found", "documents": []}

    logger.info("Discovered %d documents.", len(records))

    # ── 2. Process each document ───────────────────────────────────────────
    all_chunks = []
    doc_reports = []

    for i, record in enumerate(records, 1):
        logger.info("-" * 50)
        logger.info("[%d/%d] Processing: %s", i, len(records), record.filename)

        result = process_document(record)
        # process_document returns (report, chunks) or just report on early exit
        if isinstance(result, tuple):
            doc_report, doc_chunks = result
            all_chunks.extend(doc_chunks)
        else:
            doc_report = result
            doc_chunks = []

        doc_reports.append(doc_report)

        logger.info(
            "  → %s | %d pages | %d chars | %d chunks | %d tables | %s",
            doc_report["extraction_method"] or "skipped",
            doc_report["page_count"],
            doc_report["total_chars"],
            doc_report["total_chunks"],
            doc_report["tables_detected"],
            doc_report["status"],
        )
        if doc_report["warnings"]:
            logger.warning("  Warnings: %d", len(doc_report["warnings"]))
        if doc_report["errors"]:
            logger.error("  Errors: %s", doc_report["errors"])

    # ── 3. Save combined chunks ────────────────────────────────────────────
    _save_jsonl(all_chunks, CHUNKS_OUTPUT_FILE)
    logger.info("Saved %d total chunks to %s", len(all_chunks), CHUNKS_OUTPUT_FILE)

    # ── 4. Build validation report ─────────────────────────────────────────
    total_pages = sum(r["page_count"] for r in doc_reports)
    total_native = sum(r["native_pages"] for r in doc_reports)
    total_ocr = sum(r["ocr_pages"] for r in doc_reports)
    total_chars = sum(r["total_chars"] for r in doc_reports)
    total_chunks = sum(r["total_chunks"] for r in doc_reports)
    total_tables = sum(r["tables_detected"] for r in doc_reports)
    failed = [r for r in doc_reports if r["status"] == "failed"]
    ocr_skipped = [r for r in doc_reports if r["status"] == "ocr_skipped"]

    all_confs = [
        r["ocr_confidence_avg"]
        for r in doc_reports
        if r.get("ocr_confidence_avg") is not None
    ]

    report = {
        "summary": {
            "documents_discovered": len(records),
            "documents_processed_ok": len([r for r in doc_reports if r["status"] == "ok"]),
            "documents_failed": len(failed),
            "documents_ocr_skipped": len(ocr_skipped),
            "total_pages": total_pages,
            "native_pages": total_native,
            "ocr_pages": total_ocr,
            "total_extracted_chars": total_chars,
            "total_chunks": total_chunks,
            "total_tables_detected": total_tables,
            "ocr_confidence_avg_across_docs": round(statistics.mean(all_confs), 4) if all_confs else None,
        },
        "documents": doc_reports,
        "failed_documents": [r["filename"] for r in failed],
        "ocr_skipped_documents": [r["filename"] for r in ocr_skipped],
    }

    # Save report
    report_path = CHUNKS_DIR / "ingestion_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  Documents: %d", len(records))
    logger.info("  Pages: %d (%d native, %d OCR)", total_pages, total_native, total_ocr)
    logger.info("  Chars: %d", total_chars)
    logger.info("  Chunks: %d", total_chunks)
    logger.info("  Tables: %d", total_tables)
    logger.info("  Failed: %d", len(failed))
    logger.info("  OCR skipped: %d", len(ocr_skipped))
    logger.info("=" * 60)

    return report
