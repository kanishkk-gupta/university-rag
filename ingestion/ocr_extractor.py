"""
ingestion/ocr_extractor.py — OCR extraction for scanned PDFs.

Strategy:
  1. Open the PDF with PyMuPDF (read-only).
  2. For each page, render the COMPLETE page to a raster image using
     page.get_pixmap(dpi=DPI). This automatically composites any
     image tiles (important for DAC Policy with 113 sub-images per page
     and Holiday List with 25 tiles).
  3. Pass the raster image to Tesseract via pytesseract.
  4. Extract OCR text AND per-word confidence data.
  5. Compute median confidence from Tesseract's data output.
     If confidence data is unavailable, set ocr_confidence=None.
     We never fabricate confidence values.

The page is the unit of OCR — we never treat embedded image tiles as
separate logical pages.

If Tesseract is not installed, the extractor raises a clear RuntimeError
with installation instructions rather than silently producing empty output.
"""

import logging
import statistics
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image
import io

from ingestion.metadata import build_page_metadata
from ingestion.preprocessor import preprocess_for_ocr
from config import OCR_DPI, OCR_LANG, OCR_PSM_DEFAULT, OCR_PSM_TABLE, OCR_TIMEOUT

logger = logging.getLogger(__name__)

# Lazy imports for optional OCR dependencies
_tesseract_available: Optional[bool] = None


def _check_tesseract() -> bool:
    """Check once whether Tesseract is installed and reachable."""
    global _tesseract_available
    if _tesseract_available is not None:
        return _tesseract_available
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        _tesseract_available = True
    except Exception:
        _tesseract_available = False
    return _tesseract_available


def _render_page_to_pil(page: fitz.Page, dpi: int) -> Image.Image:
    """
    Render a full PDF page to a PIL Image.

    PyMuPDF's get_pixmap composites all sub-images (tiles) automatically,
    so we always get a clean single-image representation of the page.
    """
    mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72 pts/inch baseline
    pixmap = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_bytes = pixmap.tobytes("png")
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def _ocr_page(
    pil_image: Image.Image,
    psm: int,
    lang: str,
    timeout: int,
) -> Tuple[str, Optional[float]]:
    """
    Run Tesseract on a PIL Image.

    Returns (text, median_confidence).
    median_confidence is None if Tesseract data output is unavailable.
    """
    import pytesseract

    config = f"--psm {psm} --oem 1"

    # Get both text and per-word data for confidence calculation
    try:
        data = pytesseract.image_to_data(
            pil_image,
            lang=lang,
            config=config,
            timeout=timeout,
            output_type=pytesseract.Output.DICT,
        )
        # Extract words and their confidences (Tesseract returns -1 for non-word rows)
        words = []
        confidences = []
        for i, conf in enumerate(data["conf"]):
            try:
                c = float(conf)
            except (ValueError, TypeError):
                continue
            if c >= 0 and data["text"][i].strip():
                words.append(data["text"][i])
                confidences.append(c / 100.0)  # normalise 0-100 → 0-1

        text = " ".join(words)
        # Re-build with line structure preserved
        # Use get_text after data to keep proper line breaks
        text_with_lines = pytesseract.image_to_string(
            pil_image,
            lang=lang,
            config=config,
            timeout=timeout,
        )

        median_conf = statistics.median(confidences) if confidences else None
        return text_with_lines, median_conf

    except Exception as exc:
        logger.warning("Tesseract data extraction failed (%s), falling back to image_to_string", exc)
        try:
            text = pytesseract.image_to_string(
                pil_image,
                lang=lang,
                config=config,
                timeout=timeout,
            )
            return text, None
        except Exception as exc2:
            raise RuntimeError(f"Tesseract OCR failed: {exc2}") from exc2


def extract_ocr_page(
    page: fitz.Page,
    page_number: int,  # 1-based
    document_id: str,
    filename: str,
    source_path: str,
    dpi: int = OCR_DPI,
    psm: int = OCR_PSM_DEFAULT,
    lang: str = OCR_LANG,
) -> dict:
    """
    OCR a single page and return a page metadata dict.

    Parameters
    ----------
    page         : fitz.Page
    page_number  : int  (1-based)
    dpi          : int  Render resolution
    psm          : int  Tesseract page segmentation mode

    Returns
    -------
    dict  — page metadata including raw_text, ocr_confidence, warnings
    """
    warnings = []

    if not _check_tesseract():
        raise RuntimeError(
            "Tesseract OCR is not installed. "
            "Please run: sudo apt install tesseract-ocr\n"
            "Then verify with: tesseract --version"
        )

    # Render full page composite (handles tiles automatically)
    try:
        pil_image = _render_page_to_pil(page, dpi)
        # Apply preprocessing (e.g. adaptive threshold) to drop faint watermarks
        pil_image = preprocess_for_ocr(pil_image, apply_threshold=True)
    except Exception as exc:
        warnings.append(f"Page render failed: {exc}")
        return build_page_metadata(
            document_id=document_id,
            filename=filename,
            source_path=source_path,
            page_number=page_number,
            raw_text="",
            extraction_method="ocr_tesseract",
            ocr_confidence=None,
            ocr_engine="tesseract",
            warnings=warnings,
        )

    # OCR
    try:
        text, conf = _ocr_page(pil_image, psm=psm, lang=lang, timeout=OCR_TIMEOUT)
    except RuntimeError as exc:
        warnings.append(f"OCR error: {exc}")
        text = ""
        conf = None

    if not text.strip():
        warnings.append("OCR produced empty text for this page")
        logger.warning("Page %d of %r: OCR produced empty text", page_number, filename)
    elif conf is not None and conf < 0.5:
        warnings.append(f"Low OCR confidence: {conf:.2f}")
        logger.warning(
            "Page %d of %r: low confidence %.2f", page_number, filename, conf
        )

    meta = build_page_metadata(
        document_id=document_id,
        filename=filename,
        source_path=source_path,
        page_number=page_number,
        raw_text=text,
        extraction_method="ocr_tesseract",
        ocr_confidence=round(conf, 4) if conf is not None else None,
        ocr_engine="tesseract",
        warnings=warnings,
    )
    meta["render_dpi"] = dpi
    meta["psm"] = psm
    return meta


def extract_ocr_pdf(
    document_id: str,
    filename: str,
    source_path: str,
    dpi: int = OCR_DPI,
    psm: int = OCR_PSM_DEFAULT,
    lang: str = OCR_LANG,
    has_critical_tables: bool = False,
) -> List[dict]:
    """
    OCR all pages of a scanned PDF.

    If has_critical_tables is True, uses PSM 6 (uniform block) which
    preserves table structure better than the default PSM 3.

    Parameters
    ----------
    document_id, filename, source_path : str
    dpi          : int   render DPI (default 300)
    psm          : int   Tesseract PSM override (default from config)
    has_critical_tables : bool  If True, switch to PSM 6 for table pages

    Returns
    -------
    List[dict] — one metadata dict per page
    """
    if not _check_tesseract():
        raise RuntimeError(
            "Tesseract OCR is not installed. Please run: sudo apt install tesseract-ocr"
        )

    effective_psm = OCR_PSM_TABLE if has_critical_tables else psm

    doc = fitz.open(source_path)
    pages_out = []

    logger.info(
        "OCR extraction: %r (%d pages, DPI=%d, PSM=%d, tables=%s)",
        filename, doc.page_count, dpi, effective_psm, has_critical_tables,
    )

    for page_index in range(doc.page_count):
        page = doc[page_index]
        page_number = page_index + 1
        logger.debug("  OCR page %d/%d ...", page_number, doc.page_count)

        page_data = extract_ocr_page(
            page=page,
            page_number=page_number,
            document_id=document_id,
            filename=filename,
            source_path=source_path,
            dpi=dpi,
            psm=effective_psm,
            lang=lang,
        )
        pages_out.append(page_data)

        conf_str = (
            f"{page_data['ocr_confidence']:.2f}"
            if page_data["ocr_confidence"] is not None
            else "N/A"
        )
        logger.debug(
            "  Page %d: %d chars, confidence=%s",
            page_number,
            page_data["char_count"],
            conf_str,
        )

    doc.close()
    total_chars = sum(p["char_count"] for p in pages_out)
    confidences = [
        p["ocr_confidence"]
        for p in pages_out
        if p["ocr_confidence"] is not None
    ]
    avg_conf = statistics.mean(confidences) if confidences else None
    logger.info(
        "OCR complete: %r → %d pages, %d chars, avg_confidence=%s",
        filename,
        len(pages_out),
        total_chars,
        f"{avg_conf:.2f}" if avg_conf is not None else "N/A",
    )
    return pages_out
