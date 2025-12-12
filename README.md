# Riverwalk CCRs Knowledge Base

This project converts the Riverwalk Townhomes HOA governing documents
(CCRs + Bylaws) from an image-based PDF into a structured JSON knowledge
base that can be searched, analyzed, or used with AI models (like GPT-4/5)
to answer HOA-related questions with accurate citations.

The tool performs:
- OCR on the image-based PDF (via Tesseract)
- Article + section detection
- Declaration vs. Bylaws separation
- Cleanup + normalization of text
- JSON output with page references

⚠️ **Important:**  
The Riverwalk CCRs/Bylaws PDF is **not included** in this repository.
You must download your own copy from the Wake County Register of Deeds
and place it locally in:

```
data/Riverwalk_CCRs.pdf
```

---

## 📁 Project Structure

```
src/riverwalk_ccrs_kb/      # Python package: OCR + parsing logic
data/                       # Place Riverwalk_CCRs.pdf here (not committed)
output/                     # JSON output is written here (git-ignored)
pyproject.toml              # Project + dependency configuration
README.md                   # You are reading this
LICENSE                     # MIT License
```

---

## 🛠 Requirements

### System Dependencies
Install these first (Codespaces or Linux):

```
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

macOS (Homebrew):

```
brew install tesseract poppler
```

### Python Dependencies

Install using the included pyproject:

```
pip install .
```

---

## 🚀 Usage

1. Place your CCRs PDF here:

```
data/Riverwalk_CCRs.pdf
```

2. Build the knowledge base:

```
riverwalk-ccrs-build
```

3. Output will appear in:

```
output/riverwalk_ccrs_kb.json
```

This file contains structured Articles, Sections, page numbers, and text
extracted from the PDF.

### OCR Cache
- First run performs full OCR and caches page text to `output/riverwalk_ccrs_pages.json`.
- Subsequent runs reuse the cache and skip OCR (much faster). Delete the cache file if you need to force a fresh OCR pass (e.g., after changing Tesseract config or DPI).

### Validation
Run the validator on the generated KB:

```
riverwalk-ccrs-validate output/riverwalk_ccrs_kb.json
```

Current known warnings: duplicate numbering in the definitions block (e.g., `1.20`, `1.21`, `1.22`, `1.37` appear twice in the Declaration).

### Manual QA helper
`scripts/preview_sections.py` pretty-prints sections to compare with the PDF:

```
python scripts/preview_sections.py output/riverwalk_ccrs_kb.json --pages 4-6 --section 1.
python scripts/preview_sections.py output/riverwalk_ccrs_kb.json --pages 35-37 --section 10.
```

---

## 📄 JSON Output Example

```jsonc
{
  "doc_type": "Declaration",
  "article_number": 10,
  "article_title": "USE RESTRICTIONS",
  "section_number": "10.4",
  "section_title": "Leasing",
  "page_start": 30,
  "page_end": 31,
  "text": "Short-term rentals of less than 180 days are prohibited..."
}
```

---

## 📜 License

This project is released under the MIT License.
See the `LICENSE` file for details.
