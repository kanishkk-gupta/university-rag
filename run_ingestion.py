"""
run_ingestion.py — CLI entry point for the ingestion pipeline.

Usage:
    python run_ingestion.py [--docs-dir PATH] [--report]

Options:
    --docs-dir PATH   Override the documents directory (default: ./documents)
    --report          Print a human-readable summary report after ingestion
    --sample          Print sample chunks from each document
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from ingestion.pipeline import run_pipeline
from config import DOCUMENTS_DIR, CHUNKS_DIR

logger = logging.getLogger(__name__)


def print_report(report: dict, print_samples: bool = False):
    """Print a human-readable summary report."""
    s = report.get("summary", {})
    docs = report.get("documents", [])

    print("\n" + "=" * 70)
    print("BMU UNIVERSITY RAG — INGESTION VALIDATION REPORT")
    print("=" * 70)

    print(f"\n{'─'*40}")
    print("SUMMARY")
    print(f"{'─'*40}")
    print(f"  Documents discovered:      {s.get('documents_discovered', 0)}")
    print(f"  Processed OK:              {s.get('documents_processed_ok', 0)}")
    print(f"  Failed:                    {s.get('documents_failed', 0)}")
    print(f"  OCR skipped (no tesseract):{s.get('documents_ocr_skipped', 0)}")
    print(f"  Total pages:               {s.get('total_pages', 0)}")
    print(f"    Native pages:            {s.get('native_pages', 0)}")
    print(f"    OCR pages:               {s.get('ocr_pages', 0)}")
    print(f"  Total extracted chars:     {s.get('total_extracted_chars', 0):,}")
    print(f"  Total chunks:              {s.get('total_chunks', 0):,}")
    print(f"  Tables detected:           {s.get('total_tables_detected', 0)}")
    conf = s.get('ocr_confidence_avg_across_docs')
    print(f"  Avg OCR confidence:        {f'{conf:.3f}' if conf else 'N/A'}")

    print(f"\n{'─'*40}")
    print("PER-DOCUMENT RESULTS")
    print(f"{'─'*40}")
    header = f"{'Filename':<48}  {'Method':<14}  {'Pages':>5}  {'Chars':>8}  {'Chunks':>6}  {'Tables':>6}  {'Status'}"
    print(header)
    print("─" * len(header))

    for doc in docs:
        fname = doc['filename'][:47]
        method = (doc.get('extraction_method') or 'skipped')[:13]
        pages = doc.get('page_count', 0)
        chars = doc.get('total_chars', 0)
        chunks = doc.get('total_chunks', 0)
        tables = doc.get('tables_detected', 0)
        status = doc.get('status', '?')
        print(f"{fname:<48}  {method:<14}  {pages:>5}  {chars:>8,}  {chunks:>6}  {tables:>6}  {status}")

    # Warnings
    all_warnings = []
    for doc in docs:
        for w in doc.get("warnings", []):
            all_warnings.append(f"  [{doc['filename'][:35]}] {w}")
    if all_warnings:
        print(f"\n{'─'*40}")
        print(f"WARNINGS ({len(all_warnings)} total)")
        print(f"{'─'*40}")
        for w in all_warnings[:30]:  # cap at 30
            print(w)
        if len(all_warnings) > 30:
            print(f"  ... and {len(all_warnings)-30} more (see ingestion_report.json)")

    # Errors
    failed = report.get("failed_documents", [])
    if failed:
        print(f"\n{'─'*40}")
        print("FAILED DOCUMENTS — REQUIRE MANUAL REVIEW")
        print(f"{'─'*40}")
        for f in failed:
            print(f"  ✗ {f}")

    ocr_skipped = report.get("ocr_skipped_documents", [])
    if ocr_skipped:
        print(f"\n{'─'*40}")
        print("OCR SKIPPED — Install tesseract-ocr to process these")
        print(f"{'─'*40}")
        for f in ocr_skipped:
            print(f"  ⚠ {f}")

    if print_samples:
        _print_sample_chunks()

    print("\n" + "=" * 70)


def _print_sample_chunks():
    """Print one representative chunk from each successfully processed document."""
    chunks_dir = CHUNKS_DIR
    print(f"\n{'─'*40}")
    print("SAMPLE CHUNKS")
    print(f"{'─'*40}")

    chunk_files = sorted(chunks_dir.glob("*_chunks.jsonl"))
    for chunk_file in chunk_files:
        try:
            with open(chunk_file, "r") as f:
                lines = f.readlines()
            if not lines:
                continue
            # Find a non-trivially-small, non-heading chunk for a good sample
            sample = None
            for line in lines:
                chunk = json.loads(line)
                if chunk.get("content_type") == "text" and chunk.get("char_count", 0) > 100:
                    sample = chunk
                    break
            if not sample:
                sample = json.loads(lines[0])

            print(f"\n[ {sample.get('document_name', chunk_file.stem)} ]")
            print(f"  chunk_id:    {sample.get('chunk_id')}")
            print(f"  page:        {sample.get('page_start')}")
            print(f"  type:        {sample.get('content_type')}")
            print(f"  section:     {sample.get('section')}")
            print(f"  heading:     {sample.get('heading')}")
            print(f"  ocr_used:    {sample.get('ocr_used')}")
            conf = sample.get('ocr_confidence')
            print(f"  confidence:  {f'{conf:.3f}' if conf else 'N/A'}")
            print(f"  has_table:   {sample.get('has_table')}")
            text_preview = (sample.get('text') or '')[:300].replace('\n', ' ')
            print(f"  text[:300]:  {text_preview!r}")
        except Exception as exc:
            print(f"  Error reading {chunk_file.name}: {exc}")


def main():
    parser = argparse.ArgumentParser(description="BMU RAG Ingestion Pipeline")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=DOCUMENTS_DIR,
        help="Path to documents directory",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print validation report after ingestion",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Print sample chunks from each document",
    )
    args = parser.parse_args()

    report = run_pipeline(documents_dir=args.docs_dir)

    if args.report or args.sample:
        print_report(report, print_samples=args.sample)
    else:
        # Always print a minimal summary
        s = report.get("summary", {})
        print(f"\nIngestion complete: "
              f"{s.get('documents_processed_ok', 0)} OK, "
              f"{s.get('documents_failed', 0)} failed, "
              f"{s.get('documents_ocr_skipped', 0)} skipped, "
              f"{s.get('total_chunks', 0)} chunks, "
              f"{s.get('total_tables_detected', 0)} tables")
        print(f"Report saved to: {CHUNKS_DIR / 'ingestion_report.json'}")


if __name__ == "__main__":
    main()
