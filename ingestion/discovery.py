"""
ingestion/discovery.py — Recursive document discovery.

Scans the documents directory (and subdirectories) for supported file types.
Returns a list of DocumentRecord dicts — one per discovered file.
Never modifies source files.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

from config import DOCUMENTS_DIR, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


@dataclass
class DocumentRecord:
    """Metadata record for a discovered source document."""
    document_id: str          # SHA-1 of absolute path (stable, reproducible)
    filename: str             # e.g. "Anti Ragging Policy V 1.0.pdf"
    source_path: str          # Absolute path as string
    relative_path: str        # Path relative to documents directory
    file_type: str            # ".pdf"
    file_size_bytes: int
    page_count: int           # Actual page count from PDF; 0 if unreadable
    is_readable: bool         # Could PyMuPDF open it without error?
    error: str = ""           # Non-empty if there was a problem opening it

    def to_dict(self) -> dict:
        return asdict(self)


def _compute_document_id(path: Path) -> str:
    """Stable, reproducible document ID based on absolute path."""
    return hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:16]


def _get_page_count(path: Path) -> tuple[int, bool, str]:
    """
    Open the PDF with PyMuPDF and return (page_count, is_readable, error).
    Never modifies the file.
    """
    try:
        doc = fitz.open(str(path))
        count = doc.page_count
        doc.close()
        return count, True, ""
    except Exception as exc:
        return 0, False, str(exc)


def discover_documents(
    directory: Path = DOCUMENTS_DIR,
    supported_extensions: set = SUPPORTED_EXTENSIONS,
) -> List[DocumentRecord]:
    """
    Recursively discover all supported documents under ``directory``.

    Parameters
    ----------
    directory : Path
        Root directory to scan. Defaults to config.DOCUMENTS_DIR.
    supported_extensions : set
        Set of lowercase extensions to include (e.g. {".pdf"}).

    Returns
    -------
    List[DocumentRecord]
        Sorted by filename, one record per discovered file.
    """
    directory = Path(directory).resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Documents directory not found: {directory}")

    records: List[DocumentRecord] = []

    for root, dirs, files in os.walk(directory):
        # Sort for reproducible ordering
        dirs.sort()
        for fname in sorted(files):
            fpath = Path(root) / fname
            ext = fpath.suffix.lower()

            if ext not in supported_extensions:
                logger.debug("Skipping unsupported file: %s", fpath.name)
                continue

            size = fpath.stat().st_size
            page_count, is_readable, error = _get_page_count(fpath)
            doc_id = _compute_document_id(fpath)

            rel = fpath.relative_to(directory)

            record = DocumentRecord(
                document_id=doc_id,
                filename=fpath.name,
                source_path=str(fpath),
                relative_path=str(rel),
                file_type=ext,
                file_size_bytes=size,
                page_count=page_count,
                is_readable=is_readable,
                error=error,
            )
            records.append(record)

            if error:
                logger.warning("Problem opening %s: %s", fname, error)
            else:
                logger.info(
                    "Discovered: %s  [%d pages, %.1f KB]",
                    fname, page_count, size / 1024,
                )

    logger.info("Discovery complete: %d document(s) found.", len(records))
    return records
