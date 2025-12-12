from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pdf2image import convert_from_path
import pytesseract


def ocr_pdf(pdf_path: Path, dpi: int = 300) -> List[str]:
    """
    Convert an image-based PDF into OCR'd text, returning one string per page.

    Requirements:
      - poppler (for pdf2image)
      - tesseract (for pytesseract)

    :param pdf_path: Path to the PDF file.
    :param dpi: Rasterization DPI; 300 is a good default for OCR.
    :return: List of OCR text strings, one per PDF page (in order).
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at: {pdf_path}")

    pages = convert_from_path(str(pdf_path), dpi=dpi)

    page_texts: List[str] = []
    for i, page in enumerate(pages, start=1):
        print(f"[OCR] Page {i}/{len(pages)}…")
        text = pytesseract.image_to_string(page)
        page_texts.append(text)

    return page_texts


def save_ocr_cache(page_texts: List[str], cache_path: Path) -> None:
    """Persist OCR page texts as JSON for reuse."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(page_texts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OCR] Cached {len(page_texts)} pages to {cache_path}")


def load_ocr_cache(cache_path: Path) -> List[str] | None:
    """Load OCR page texts from cache if present, else return None."""
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            print(f"[OCR] Loaded cached OCR text from {cache_path}")
            return data
    except Exception as e:  # cache corruption or parse error
        print(f"[OCR] Failed to load cache {cache_path}: {e}")
    return None
