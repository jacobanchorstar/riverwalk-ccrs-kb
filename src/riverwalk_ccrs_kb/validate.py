from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SECTION_NUM_RE = re.compile(r"^\d+(\.\d+)+[a-z]?$")
FOOTER_RE = re.compile(r"\bPage\s*\|\s*\d+\b|\bBK\d{6,}\b", re.IGNORECASE)


@dataclass
class Issue:
    level: str  # "ERROR" or "WARN"
    code: str
    section_idx: int | None
    message: str


def _get(d: dict[str, Any], path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def validate_kb(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    kb = json.loads(path.read_text(encoding="utf-8"))

    meta = kb.get("metadata")
    if not isinstance(meta, dict):
        return [Issue("ERROR", "META_MISSING", None, "Top-level metadata missing or not an object.")]

    page_count = meta.get("page_count")
    if not isinstance(page_count, int) or page_count <= 0:
        issues.append(Issue("ERROR", "META_PAGECOUNT", None, f"metadata.page_count invalid: {page_count!r}"))

    sections = kb.get("sections")
    if not isinstance(sections, list) or not sections:
        issues.append(Issue("ERROR", "SECTIONS_MISSING", None, "Top-level sections missing or empty."))
        return issues

    seen = defaultdict(list)  # (doc_type, section_number) -> idxs

    for i, s in enumerate(sections):
        if not isinstance(s, dict):
            issues.append(Issue("ERROR", "SECTION_NOT_OBJ", i, "Section is not an object."))
            continue

        required = [
            "doc_type",
            "article_number",
            "section_number",
            "page_start",
            "page_end",
            "source.pdf_file",
            "text",
        ]
        for key in required:
            v = _get(s, key)
            if v is None:
                issues.append(Issue("ERROR", "MISSING_FIELD", i, f"Missing field: {key}"))

        doc_type = s.get("doc_type")
        article_number = s.get("article_number")
        section_number = s.get("section_number")
        page_start = s.get("page_start")
        page_end = s.get("page_end")
        text = s.get("text", "")

        if not isinstance(doc_type, str) or not doc_type.strip():
            issues.append(Issue("ERROR", "BAD_DOCTYPE", i, f"doc_type invalid: {doc_type!r}"))

        if not isinstance(article_number, int) or article_number <= 0:
            issues.append(Issue("ERROR", "BAD_ARTICLE_NUM", i, f"article_number invalid: {article_number!r}"))

        if not isinstance(section_number, str) or not SECTION_NUM_RE.match(section_number.strip()):
            issues.append(Issue("ERROR", "BAD_SECTION_NUM", i, f"section_number invalid: {section_number!r}"))

        if isinstance(page_start, int) and isinstance(page_end, int):
            if page_start < 1 or page_end < page_start:
                issues.append(Issue("ERROR", "BAD_PAGE_RANGE", i, f"Bad page range: {page_start}-{page_end}"))
            if isinstance(page_count, int) and page_end > page_count:
                issues.append(Issue("ERROR", "PAGE_OOB", i, f"page_end {page_end} > page_count {page_count}"))

        if isinstance(article_number, int) and isinstance(section_number, str) and SECTION_NUM_RE.match(section_number):
            major = int(section_number.split(".")[0])
            if major != article_number:
                issues.append(Issue("WARN", "ARTICLE_SECTION_MISMATCH", i, f"article_number={article_number} but section_number={section_number}"))

        if isinstance(text, str) and FOOTER_RE.search(text):
            issues.append(Issue("WARN", "FOOTER_NOISE", i, "Detected Page|BK footer/header noise in text."))

        if not isinstance(text, str) or len(text.strip()) < 20:
            issues.append(Issue("WARN", "TEXT_TOO_SHORT", i, f"text is very short ({len(text.strip()) if isinstance(text,str) else 0} chars)"))

        if isinstance(doc_type, str) and isinstance(section_number, str):
            seen[(doc_type, section_number)].append(i)

    for (doc_type, section_number), idxs in seen.items():
        if len(idxs) > 1:
            issues.append(Issue("WARN", "DUP_SECTION_NUMBER", None, f"Duplicate section_number {section_number!r} in doc_type={doc_type!r}: idxs={idxs}"))

    return issues


def main() -> None:
    p = argparse.ArgumentParser(prog="riverwalk-ccrs-validate")
    p.add_argument("kb_json", help="Path to KB json (e.g., output/riverwalk_ccrs_kb.json)")
    p.add_argument("--fail-on-warn", action="store_true")
    args = p.parse_args()

    issues = validate_kb(Path(args.kb_json))
    errors = [x for x in issues if x.level == "ERROR"]
    warns = [x for x in issues if x.level == "WARN"]

    for x in issues:
        loc = f"section[{x.section_idx}]" if x.section_idx is not None else "GLOBAL"
        print(f"{x.level} {x.code} {loc}: {x.message}")

    print(f"\nSummary: {len(errors)} errors, {len(warns)} warnings, {len(issues)} total issues.")
    if errors or (args.fail_on_warn and warns):
        sys.exit(1)


if __name__ == "__main__":
    main()
