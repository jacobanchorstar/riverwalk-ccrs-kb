from __future__ import annotations

from .config import OCR_CACHE_JSON, OUTPUT_JSON, PDF_PATH
from .ocr import load_ocr_cache, ocr_pdf, save_ocr_cache
from .parser import build_kb, write_kb_to_file


def main() -> None:
    print(f"[CLI] Building Riverwalk CCRs KB from {PDF_PATH}…")

    page_texts = load_ocr_cache(OCR_CACHE_JSON)
    if page_texts is None:
        page_texts = ocr_pdf(PDF_PATH)
        save_ocr_cache(page_texts, OCR_CACHE_JSON)

    kb = build_kb(page_texts)
    write_kb_to_file(kb, OUTPUT_JSON)

    print("[CLI] Done.")


if __name__ == "__main__":
    main()
