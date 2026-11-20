#!/usr/bin/env python3
"""Original 170-Protocol Manual Page-by-Page Verifier (Phase 2).

Cross-checks data/protocols_170.json against an owner-supplied source manual PDF or plain-text export.
NEVER fabricates missing page numbers and NEVER silently alters canonical protocol IDs, codes, or titles.
Upgrades `source_confidence` from `summary_verified_pending_full_manual_page_audit` to `page_verified`
ONLY for protocols whose ID/code and title match verbatim pages in the supplied source document.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "data" / "protocols_170.json"


def extract_pages(source_path: Path) -> list[tuple[int, str]]:
    """Extract (1-indexed page_number, page_text) tuples from a PDF or structured text/markdown file."""
    if not source_path.exists():
        raise FileNotFoundError(f"Source manual not found: {source_path}")

    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "PDF extraction requires 'pypdf' (install with `pip install pypdf` or export text with form-feed page breaks)."
            ) from exc
        reader = PdfReader(str(source_path))
        return [(idx + 1, page.extract_text() or "") for idx, page in enumerate(reader.pages)]

    text = source_path.read_text(encoding="utf-8", errors="replace")
    if "\f" in text:
        raw_pages = text.split("\f")
        return [(idx + 1, chunk) for idx, chunk in enumerate(raw_pages) if chunk.strip()]

    # Support explicit '--- Page N ---' or '=== Page N ===' markers
    marker_re = re.compile(r"(?im)^(?:---|===)\s*page\s+(\d+)\s*(?:---|===)\s*$")
    matches = list(marker_re.finditer(text))
    if matches:
        pages: list[tuple[int, str]] = []
        for idx, m in enumerate(matches):
            pnum = int(m.group(1))
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            pages.append((pnum, text[start:end]))
        return pages

    # Fallback: single-page document (honestly recorded as page 1)
    return [(1, text)]


def verify_manual_against_registry(
    *,
    source_path: Path,
    registry_path: Path = DEFAULT_REGISTRY,
    update_registry: bool = False,
) -> dict[str, Any]:
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    protocols: list[dict[str, Any]] = data.get("protocols", [])
    pages = extract_pages(source_path)

    verified: list[dict[str, Any]] = []
    title_discrepancies: list[dict[str, Any]] = []
    missing_ids: list[int] = []

    for proto in protocols:
        pid = int(proto["protocol_id"])
        pcode = str(proto["protocol_code"])
        title = str(proto["canonical_title"])

        # Match Protocol 001 / Protocol 1 / P001 / 001. Title / 1. Title
        id_patterns = [
            re.compile(rf"(?i)\bprotocol\s+0*{pid}\b(?:\s*[:.\-–—]\s*([^\n\r]+))?"),
            re.compile(rf"(?i)\b{re.escape(pcode)}\b(?:\s*[:.\-–—]\s*([^\n\r]+))?"),
            re.compile(rf"(?m)^\s*0*{pid}\.\s+([^\n\r]+)$"),
        ]
        found_page: int | None = None
        matched_heading: str | None = None

        for page_num, ptext in pages:
            for pat in id_patterns:
                m = pat.search(ptext)
                if m:
                    found_page = page_num
                    matched_heading = (m.group(1) or "").strip() if m.lastindex else ""
                    break
            if found_page is not None:
                break

        if found_page is None:
            missing_ids.append(pid)
            continue

        title_norm = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        heading_norm = re.sub(r"[^a-z0-9]+", " ", (matched_heading or "").lower()).strip()
        page_text_norm = re.sub(r"[^a-z0-9]+", " ", next(t for n, t in pages if n == found_page).lower())

        title_matched = bool(
            (heading_norm and (title_norm in heading_norm or heading_norm in title_norm))
            or (title_norm in page_text_norm)
        )
        if title_matched:
            verified.append({"protocol_id": pid, "protocol_code": pcode, "page": found_page, "canonical_title": title})
            if update_registry:
                proto["source_confidence"] = "page_verified"
                proto["source_manual_page"] = found_page
        else:
            title_discrepancies.append(
                {
                    "protocol_id": pid,
                    "protocol_code": pcode,
                    "page": found_page,
                    "registry_canonical_title": title,
                    "manual_heading_excerpt": matched_heading or "(title text not matched verbatim on page)",
                    "action": "preserved_canonical_title_requires_owner_review",
                }
            )

    if update_registry and verified:
        data["last_manual_page_audit"] = {
            "source_filename": source_path.name,
            "total_pages_scanned": len(pages),
            "verified_count": len(verified),
            "discrepancy_count": len(title_discrepancies),
            "missing_count": len(missing_ids),
        }
        registry_path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "source_path": str(source_path),
        "registry_path": str(registry_path),
        "total_pages_scanned": len(pages),
        "total_protocols": len(protocols),
        "verified_count": len(verified),
        "title_discrepancies_count": len(title_discrepancies),
        "missing_count": len(missing_ids),
        "coverage_pct": round((len(verified) / max(1, len(protocols))) * 100.0, 2),
        "registry_updated": bool(update_registry and verified),
        "title_discrepancies": title_discrepancies[:50],
        "missing_protocol_ids": missing_ids[:50],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify data/protocols_170.json page-by-page against the original 170-Protocol Manual PDF/text."
    )
    parser.add_argument("--source", required=True, help="Path to original 170-Protocol Manual (.pdf, .txt, or .md)")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Path to protocols_170.json")
    parser.add_argument(
        "--update-registry",
        action="store_true",
        default=False,
        help="Upgrade source_confidence to 'page_verified' and attach source_manual_page ONLY for matched protocols.",
    )
    args = parser.parse_args(argv)
    try:
        report = verify_manual_against_registry(
            source_path=Path(args.source),
            registry_path=Path(args.registry),
            update_registry=args.update_registry,
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["missing_count"] == 0 and report["title_discrepancies_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
