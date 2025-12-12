from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path


def parse_page_range(raw: str | None) -> tuple[int | None, int | None]:
    if not raw:
        return None, None
    if "-" in raw:
        start, end = raw.split("-", 1)
        return (int(start) if start else None), (int(end) if end else None)
    val = int(raw)
    return val, val


def section_in_range(section: dict, start: int | None, end: int | None) -> bool:
    ps, pe = section.get("page_start"), section.get("page_end")
    if not isinstance(ps, int) or not isinstance(pe, int):
        return False
    if start is not None and pe < start:
        return False
    if end is not None and ps > end:
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Pretty-print KB sections for manual PDF comparison.")
    ap.add_argument("kb_json", type=Path, help="Path to output/riverwalk_ccrs_kb.json")
    ap.add_argument("--pages", help="Page filter (e.g., '4-6', '35', '-10', '50-').")
    ap.add_argument("--doc-type", help="Filter by doc_type (e.g., Declaration, Bylaws).")
    ap.add_argument("--section", help="Filter by section_number prefix (e.g., '1.', '10.2').")
    args = ap.parse_args()

    start, end = parse_page_range(args.pages)

    kb = json.loads(args.kb_json.read_text(encoding="utf-8"))
    sections = kb.get("sections", [])

    for s in sections:
        if args.doc_type and s.get("doc_type") != args.doc_type:
            continue
        if args.section and not str(s.get("section_number", "")).startswith(args.section):
            continue
        if not section_in_range(s, start, end):
            continue

        header = f"[p{s.get('page_start')}–{s.get('page_end')}] {s.get('doc_type')} Art {s.get('article_number')} Sec {s.get('section_number')} {s.get('section_title')}"
        print(header)
        print("-" * len(header))
        text = str(s.get("text", "")).strip()
        if text:
            wrapped = textwrap.fill(text, width=110)
            print(wrapped)
        else:
            print("(no text)")
        print()


if __name__ == "__main__":
    main()
