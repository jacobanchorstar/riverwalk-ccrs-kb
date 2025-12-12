from __future__ import annotations

import json
import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import BYLAWS_START_PAGE, OUTPUT_JSON, PDF_PATH

# Match article headers like: "ARTICLE 10: USE RESTRICTIONS"
ARTICLE_RE = re.compile(r"^\s*ARTICLE\s+(\d+)\s*[:\-]?\s*(.+)$", re.IGNORECASE)

# Match section headers like: "10.11. Animals" or "4.3. Enforcement"
SECTION_RE = re.compile(r"^\s*(\d+\.\d+)\.\s*(.+)$")

# Common footer/header noise from the OCR'd PDF (e.g., "Page | 33 BK123456 PG 789")
FOOTER_RE = re.compile(r"Page\s*\|\s*\d+|\bBK\d{6,}\b|\bPG\s*\d+\b", re.IGNORECASE)


def doc_type_for_page(page_num: int) -> str:
    """Return 'Declaration' or 'Bylaws' based on the PDF page number."""
    return "Bylaws" if page_num >= BYLAWS_START_PAGE else "Declaration"


def clean_article_title(raw: str | None) -> str:
    """
    Try to keep article titles clean by trimming anything that looks like
    OCR-run-on text. Titles should usually be short and uppercase.
    """
    if not raw:
        return ""
    text = raw.strip()

    # Truncate on first '.', ';', or newline to avoid swallowing body text.
    for cut in (".", ";", "\n"):
        idx = text.find(cut)
        if idx != -1:
            text = text[:idx]
            break

    return text.strip().upper()


def split_title_and_body(after_num: str) -> Tuple[str, str]:
    """
    Given the text after 'X.Y.' on the first line, split into:
      (section_title, first_body_piece)

    Heuristic:
      - If there's a colon, everything before it is title.
      - Else, if there's a period, treat first sentence fragment as title.
      - Else, whole line is title.
    """
    text = (after_num or "").strip()
    if not text:
        return "", ""

    colon_idx = text.find(":")
    if colon_idx != -1:
        title = text[:colon_idx].strip()
        rest = text[colon_idx + 1 :].lstrip()
        return title, rest

    dot_idx = text.find(".")
    if dot_idx != -1:
        title = text[: dot_idx + 1].strip()
        rest = text[dot_idx + 1 :].lstrip()
        return title, rest

    return text, ""


def build_sections(page_texts: List[str]) -> List[Dict[str, Any]]:
    """
    Parse per-page OCR text into structured sections.

    Strategy:
      - Track the most recent ARTICLE header.
      - Start a new section when a line matches 'X.Y.'.
      - Accumulate lines until the next section header.
      - Track page_start/page_end using the page loop directly.
    """
    sections: List[Dict[str, Any]] = []

    current_article_number: int | None = None
    current_article_title: str | None = None

    open_section: Dict[str, Any] | None = None

    for page_num, text in enumerate(page_texts, start=1):
        lines = text.splitlines()

        for line in lines:
            # Skip footer/header noise that can leak into OCR text
            if FOOTER_RE.search(line):
                continue

            # ARTICLE heading?
            art_match = ARTICLE_RE.match(line)
            if art_match:
                tail = art_match.group(2)
                # Ignore in-line references like "Article 9 of this Declaration" that start mid-body.
                if not tail.lower().startswith(("of this", "of the")):
                    current_article_number = int(art_match.group(1))
                    current_article_title = clean_article_title(tail)
                continue

            # SECTION heading?
            sec_match = SECTION_RE.match(line)
            if sec_match:
                sec_num = sec_match.group(1).strip()
                after_num = sec_match.group(2)
                major = int(sec_num.split(".")[0])

                # If we see the same section number while it's already open, treat it as inline text
                # (e.g., references like "Section 15.4. Notwithstanding ...") instead of starting anew.
                if open_section is not None and open_section.get("section_number") == sec_num:
                    if after_num.strip():
                        open_section["text_chunks"].append(after_num.strip())
                    continue

                # Close previous open section
                if open_section is not None:
                    sections.append(open_section)
                    open_section = None

                # If section number implies a new article, update trackers even if an ARTICLE heading was missed.
                if current_article_number != major:
                    current_article_number = major
                    current_article_title = None

                sec_title, first_body_piece = split_title_and_body(after_num)

                open_section = {
                    "doc_type": doc_type_for_page(page_num),
                    "article_number": current_article_number,
                    "article_title": current_article_title,
                    "section_number": sec_num,
                    "section_title": sec_title,
                    "page_start": page_num,
                    "page_end": page_num,
                    "text_chunks": [],
                    "source": {
                        "pdf_file": str(PDF_PATH),
                    },
                }

                if first_body_piece:
                    open_section["text_chunks"].append(first_body_piece)

                continue

            # Normal line: append to open section if we have one
            if open_section is not None:
                open_section["text_chunks"].append(line)

        # End of page: extend page_end for open section (if any)
        if open_section is not None:
            open_section["page_end"] = page_num

    # Close last section
    if open_section is not None:
        sections.append(open_section)

    # Final cleanup: join text_chunks into "text" and normalize whitespace
    for s in sections:
        raw_text = "\n".join(s.pop("text_chunks"))
        s["text"] = " ".join(raw_text.split())

    return sections


def build_kb(page_texts: List[str]) -> Dict[str, Any]:
    """Build the full JSON knowledge base structure."""
    sections = build_sections(page_texts)
    return {
        "metadata": {
            "source_file": str(PDF_PATH),
            "page_count": len(page_texts),
            "generated_at": datetime.now(UTC).isoformat(),
            "notes": "Built from OCR of Riverwalk CCRs/Bylaws PDF.",
        },
        "sections": sections,
    }


def write_kb_to_file(kb: Dict[str, Any], output_path: Path | None = None) -> None:
    """Write the KB JSON to disk."""
    out = output_path or OUTPUT_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[KB] Wrote {len(kb.get('sections', []))} sections to {out}")
