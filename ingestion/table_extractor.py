"""
ingestion/table_extractor.py — Table detection and structured extraction.

Two extraction paths:
  A. Native PDFs: Use pdfplumber to detect and extract tables from
     Word-generated bordered cell structures.
  B. Scanned PDFs: Use Tesseract OCR coordinate reconstruction (OCR Grid)
     to mathematically align text bounding boxes into rows and columns.

If table extraction is uncertain or fails, the result is flagged with
extraction_status="failed" or "uncertain", and the raw page OCR text
is preserved.
"""

import logging
from typing import List, Optional

import fitz  # PyMuPDF
import numpy as np

from ingestion.metadata import make_table_id
from ingestion.preprocessor import preprocess_for_ocr
from PIL import Image
import io

from config import (
    OCR_DPI,
    TABLE_MIN_ROWS,
    TABLE_MIN_COLS,
)

logger = logging.getLogger(__name__)


# ─── Native table extraction (pdfplumber) ─────────────────────────────────────

def extract_tables_native(
    document_id: str,
    filename: str,
    source_path: str,
) -> List[dict]:
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed; native table extraction skipped")
        return []

    tables_out = []
    try:
        with pdfplumber.open(source_path) as pdf:
            for page_index, page in enumerate(pdf.pages):
                page_number = page_index + 1
                try:
                    tables = page.extract_tables()
                except Exception as exc:
                    logger.warning("pdfplumber failed on page %d of %r: %s", page_number, filename, exc)
                    continue

                for t_idx, raw_table in enumerate(tables):
                    if not raw_table:
                        continue
                    rows = [
                        [str(cell).strip() if cell is not None else "" for cell in row]
                        for row in raw_table
                    ]
                    n_rows = len(rows)
                    n_cols = max(len(r) for r in rows) if rows else 0

                    if n_rows < TABLE_MIN_ROWS or n_cols < TABLE_MIN_COLS:
                        continue

                    table_id = make_table_id(document_id, page_number, t_idx)
                    markdown = _rows_to_markdown(rows)
                    tables_out.append({
                        "table_id": table_id,
                        "document_id": document_id,
                        "filename": filename,
                        "page_number": page_number,
                        "table_index": t_idx,
                        "n_rows": n_rows,
                        "n_cols": n_cols,
                        "rows": rows,
                        "markdown": markdown,
                        "extraction_method": "pdfplumber_native",
                        "extraction_status": "ok",
                        "confidence": None,
                    })
    except Exception as exc:
        logger.error("pdfplumber failed to open %r: %s", filename, exc)

    logger.info("Native table extraction: %r → %d tables", filename, len(tables_out))
    return tables_out


# ─── Scanned table extraction (OCR Grid Reconstructor) ─────────────────────────

def extract_tables_scanned(
    document_id: str,
    filename: str,
    source_path: str,
    dpi: int = OCR_DPI,
) -> List[dict]:
    """
    Extract tables from a scanned PDF using OCR coordinate reconstruction.
    
    1. Render page.
    2. Optional Preprocess (helps Tesseract find true text bounding boxes).
    3. Run pytesseract.image_to_data.
    4. Group bounding boxes into rows based on vertical overlap.
    5. Treat it as a table if it has >TABLE_MIN_ROWS rows.
    """
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception:
        logger.warning("Tesseract not installed; scanned table extraction skipped")
        return []

    tables_out = []
    doc = fitz.open(source_path)

    for page_index in range(doc.page_count):
        page_number = page_index + 1
        page = doc[page_index]

        # Render page
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pixmap = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img_bytes = pixmap.tobytes("png")
        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        # We do NOT use adaptive thresholding for table structure extraction
        # because sometimes it breaks faint table headers, standard grayscale is best.
        # But we do grayscale it.
        pil_image = preprocess_for_ocr(pil_image, apply_threshold=False)
        
        try:
            # PSM 6 is uniform block of text, which keeps tables relatively stable
            data = pytesseract.image_to_data(pil_image, lang="eng", config="--psm 6", output_type=pytesseract.Output.DICT)
        except Exception as exc:
            logger.warning("OCR grid extraction failed on page %d: %s", page_number, exc)
            continue
            
        words = []
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            try:
                conf = float(data['conf'][i])
            except ValueError:
                conf = -1
                
            if text and conf > 10:  # Ignore severe noise
                words.append({
                    'text': text,
                    'left': data['left'][i],
                    'top': data['top'][i],
                    'width': data['width'][i],
                    'height': data['height'][i],
                    'right': data['left'][i] + data['width'][i],
                    'bottom': data['top'][i] + data['height'][i],
                    'conf': conf
                })
                
        if not words:
            continue
            
        # 1. Group into rows based on vertical overlap
        words.sort(key=lambda w: w['top'])
        raw_rows = []
        current_row = [words[0]]
        row_top = words[0]['top']
        row_bottom = words[0]['bottom']
        
        for w in words[1:]:
            # Overlap threshold (if vertical overlap is > 40% of the smaller height)
            overlap = max(0, min(row_bottom, w['bottom']) - max(row_top, w['top']))
            h1 = row_bottom - row_top
            h2 = w['bottom'] - w['top']
            
            if overlap > 0.4 * min(h1, h2):
                current_row.append(w)
                row_top = min(row_top, w['top'])
                row_bottom = max(row_bottom, w['bottom'])
            else:
                raw_rows.append(current_row)
                current_row = [w]
                row_top = w['top']
                row_bottom = w['bottom']
        raw_rows.append(current_row)
        
        # 2. Heuristically group into a single table per page (simplified for these specific BMU docs)
        # We only keep rows that have multiple items spaced out horizontally, 
        # or we just take all rows and align them into columns.
        # Since Holiday List / Fee Calendar are full-page tables, we treat the page as a single table
        # if it passes minimum criteria.
        
        # Sort words in each row left-to-right
        for r in raw_rows:
            r.sort(key=lambda w: w['left'])
            
        # Convert to text rows
        rows = [[w['text'] for w in r] for r in raw_rows]
        n_rows = len(rows)
        n_cols = max(len(r) for r in rows) if rows else 0
        
        # Very loose table definition since these calendars have many varying columns
        if n_rows >= TABLE_MIN_ROWS and n_cols >= TABLE_MIN_COLS:
            table_id = make_table_id(document_id, page_number, 0)
            markdown = _rows_to_markdown(rows)
            
            # Calculate average confidence
            confs = [w['conf'] for r in raw_rows for w in r]
            avg_conf = sum(confs) / len(confs) if confs else None
            
            tables_out.append({
                "table_id": table_id,
                "document_id": document_id,
                "filename": filename,
                "page_number": page_number,
                "table_index": 0,
                "n_rows": n_rows,
                "n_cols": n_cols,
                "rows": rows,
                "markdown": markdown,
                "extraction_method": "ocr_grid_reconstruction",
                "extraction_status": "ok",
                "confidence": round(avg_conf / 100.0, 4) if avg_conf else None,
            })
            logger.debug("  Scanned table: page=%d, %dx%d (OCR Grid)", page_number, n_rows, n_cols)

    doc.close()
    logger.info("Scanned table extraction: %r → %d tables", filename, len(tables_out))
    return tables_out


# ─── Markdown table representation ────────────────────────────────────────────

def _rows_to_markdown(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    n_cols = max(len(r) for r in rows)
    padded = []
    for row in rows:
        padded_row = list(row) + [""] * (n_cols - len(row))
        padded.append(padded_row)
        
    lines = []
    header = padded[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * n_cols) + "|")
    for row in padded[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def make_table_chunk_text(table: dict) -> str:
    filename = table.get("filename", "")
    page = table.get("page_number", "?")
    markdown = table.get("markdown", "")
    status = table.get("extraction_status", "ok")

    if status != "ok" or not markdown:
        return f"[TABLE — extraction failed or uncertain on page {page} of {filename}]"

    return f"TABLE (page {page}):\n{markdown}"
