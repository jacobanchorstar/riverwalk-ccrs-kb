from pathlib import Path

# Path to the Riverwalk CCRs / Bylaws PDF (relative to repo root)
PDF_PATH = Path("data/Riverwalk_CCRs.pdf")

# Where the generated JSON knowledge base will be written
OUTPUT_JSON = Path("output/riverwalk_ccrs_kb.json")

# Cache file for OCR'd page texts to avoid re-running Tesseract
OCR_CACHE_JSON = Path("output/riverwalk_ccrs_pages.json")

# PDF page (1-based) where the Bylaws section begins
# Adjust if you later refine the boundary.
BYLAWS_START_PAGE = 57
