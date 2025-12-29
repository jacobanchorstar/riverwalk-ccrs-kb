from __future__ import annotations

import json
import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import BYLAWS_START_PAGE, OUTPUT_JSON, PDF_PATH

# Match article headers like: "ARTICLE 10: USE RESTRICTIONS"
ARTICLE_RE = re.compile(r"^\s*ARTICLE\s+(\d+)\s*[:\-]?\s*(.+)$", re.IGNORECASE)

# Match section numbers like "10.11" or "4.3" with optional trailing "."
SECTION_TOKEN_RE = re.compile(r"(?<!\w)(\d+\.\d+)(?:\.)?(?=\s)")

# Match collapsed OCR section numbers like "19." (should be "1.9.")
COLLAPSED_SECTION_TOKEN_RE = re.compile(r"(?<!\w)(\d{2,3})(?:\.)?(?=\s)")

# Common footer/header noise from the OCR'd PDF (e.g., "Page | 33 BK123456 PG 789")
FOOTER_RE = re.compile(
    r"Page\s*\|\s*\d+|\bBK\d{6,}PG\d+\b|\bBK\d{6,}\b|\bPG\s*\d+\b",
    re.IGNORECASE,
)
SIGNATURE_OR_EXHIBIT_RE = re.compile(
    r"\[?\s*Signature\s+Page\s+Follows\s*\]?"
    r"|^IN\s+WITNESS\s+WHEREOF\b"
    r"|^EXHIBIT\b"
    r"|^BYLAWS\s+OF\b",
    re.IGNORECASE,
)


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
        title = _clean_section_title(text[:colon_idx])
        rest = text[colon_idx + 1 :].lstrip()
        return title, rest

    dot_idx = text.find(".")
    if dot_idx != -1:
        title = _clean_section_title(text[: dot_idx + 1])
        rest = text[dot_idx + 1 :].lstrip()
        return title, rest

    return _clean_section_title(text), ""


def _clean_section_title(title: str) -> str:
    cleaned = title.strip().lstrip("|-:;").strip()
    if cleaned.startswith("|"):
        cleaned = cleaned[1:].strip()
    if cleaned.endswith("."):
        cleaned = cleaned[:-1].rstrip()
    return cleaned


def _normalize_line(line: str) -> str:
    cleaned = FOOTER_RE.sub(" ", line)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _is_all_caps_heading(line: str) -> bool:
    letters = re.findall(r"[A-Za-z]", line)
    if not letters:
        return False
    return all(ch.isupper() for ch in letters)


def _preceded_by_section_word(line: str, pos: int) -> bool:
    before = line[:pos].rstrip()
    if not before:
        return False
    match = re.search(r"([A-Za-z]+)$", before)
    return bool(match and match.group(1).lower() in {"section", "sections"})


def _looks_like_heading(after_text: str) -> bool:
    stripped = after_text.lstrip()
    if not stripped:
        return False
    cleaned = stripped.lstrip("|-:;").lstrip()
    if not cleaned:
        return False
    first = cleaned[0]
    return first.isupper() or first in {"\"", "'", "“", "("}


def _normalize_collapsed_section(raw: str, current_article_number: int | None) -> str | None:
    if current_article_number is None:
        return None
    article = str(current_article_number)
    if not raw.startswith(article):
        return None
    remainder = raw[len(article) :]
    if not remainder or remainder == "0":
        return None
    return f"{article}.{remainder}"


def _find_section_candidates(line: str, current_article_number: int | None) -> List[Tuple[int, int, str]]:
    candidates: List[Tuple[int, int, str]] = []

    for match in SECTION_TOKEN_RE.finditer(line):
        if _preceded_by_section_word(line, match.start()):
            continue
        if not _looks_like_heading(line[match.end() :]):
            continue
        candidates.append((match.start(), match.end(), match.group(1)))

    for match in COLLAPSED_SECTION_TOKEN_RE.finditer(line):
        normalized = _normalize_collapsed_section(match.group(1), current_article_number)
        if not normalized:
            continue
        if _preceded_by_section_word(line, match.start()):
            continue
        if not _looks_like_heading(line[match.end() :]):
            continue
        candidates.append((match.start(), match.end(), normalized))

    candidates.sort(key=lambda item: item[0])
    deduped: List[Tuple[int, int, str]] = []
    for start, end, sec_num in candidates:
        if deduped and start < deduped[-1][1]:
            continue
        deduped.append((start, end, sec_num))
    return deduped


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
    pending_article_title: bool = False

    open_section: Dict[str, Any] | None = None

    for page_num, text in enumerate(page_texts, start=1):
        lines = text.splitlines()

        for raw_line in lines:
            line = _normalize_line(raw_line)
            if not line:
                continue
            if re.fullmatch(r"\d{1,3}", line):
                continue
            if SIGNATURE_OR_EXHIBIT_RE.search(line):
                if open_section is not None:
                    sections.append(open_section)
                    open_section = None
                continue
            if pending_article_title:
                if _is_all_caps_heading(line) and not SECTION_TOKEN_RE.search(line):
                    if current_article_title:
                        current_article_title = f"{current_article_title} {line.strip()}"
                    else:
                        current_article_title = line.strip()
                    pending_article_title = False
                    continue
                pending_article_title = False

            # ARTICLE heading?
            art_match = ARTICLE_RE.match(line)
            if art_match:
                tail = art_match.group(2)
                if open_section is not None:
                    sections.append(open_section)
                    open_section = None
                # Ignore in-line references like "Article 9 of this Declaration" that start mid-body.
                if not tail.lower().startswith(("of this", "of the")):
                    current_article_number = int(art_match.group(1))
                    current_article_title = clean_article_title(tail)
                    pending_article_title = tail.rstrip().endswith((",", "-", "–"))
                continue

            candidates = _find_section_candidates(line, current_article_number)
            if candidates:
                prefix = line[: candidates[0][0]].strip()
                if prefix and open_section is not None:
                    open_section["text_chunks"].append(prefix)

                for idx, (start, end, sec_num) in enumerate(candidates):
                    next_start = candidates[idx + 1][0] if idx + 1 < len(candidates) else None
                    after_num = line[end:next_start].strip() if next_start is not None else line[end:].strip()
                    major = int(sec_num.split(".")[0])

                    if open_section is not None and open_section.get("section_number") == sec_num:
                        if after_num:
                            open_section["text_chunks"].append(after_num)
                        continue

                    if open_section is not None:
                        sections.append(open_section)
                        open_section = None

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
        cleaned = " ".join(raw_text.split())
        cleaned = cleaned.lstrip("| ").strip()
        s["text"] = cleaned

    _disambiguate_section_numbers(sections)
    return sections


def _disambiguate_section_numbers(sections: List[Dict[str, Any]]) -> None:
    counts: Dict[Tuple[str, str], int] = {}
    for s in sections:
        key = (s.get("doc_type", ""), s.get("section_number", ""))
        counts[key] = counts.get(key, 0) + 1

    suffixes: Dict[Tuple[str, str], int] = {}
    for s in sections:
        key = (s.get("doc_type", ""), s.get("section_number", ""))
        if counts.get(key, 0) <= 1:
            continue
        if "section_number_original" not in s:
            s["section_number_original"] = s["section_number"]
        idx = suffixes.get(key, 0)
        suffixes[key] = idx + 1
        letter = chr(ord("a") + idx)
        s["section_number"] = f"{s['section_number']}{letter}"


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
