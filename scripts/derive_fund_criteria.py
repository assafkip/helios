#!/usr/bin/env python3
"""
Derive structured fund criteria from each vertical's curated VC watchlist.

Single writer of `data/<vertical>/fund_criteria.json`. Reads the hand-curated
`vc_watchlist.json` (never mutates it) and applies the PHRASE_MAP from
fund_criteria_vocab.py to each fund's notes/thesis/keywords text, producing
controlled-vocab tags with the exact phrase that matched (evidence) and the
fund's own URL as citation. Pure regex over curated text, no model call.

This is the recon step. The counting/ranking lives in compute_fund_criteria.py.

Usage:
  python3 scripts/derive_fund_criteria.py            # all verticals
  python3 scripts/derive_fund_criteria.py cyber      # one vertical
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fund_criteria_vocab import PHRASE_MAP

PROJECT_ROOT = Path(__file__).parent.parent
VERTICALS_PATH = PROJECT_ROOT / "verticals.json"
DATA_DIR = PROJECT_ROOT / "data"

# Fields we read recon language from, in citation-priority order for evidence.
TEXT_FIELDS = ("thesis_alignment", "notes", "keywords", "role")
# The headline `wants` family reads ONLY the differentiated intel. The `keywords`
# field is a shared boilerplate default on most cyber funds ("security, detection,
# SOC, ... AI security"); counting it as a `want` would make every fund look
# identical and flatten the ranking. Sector/stage/geo may still read keywords.
WANTS_FIELDS = ("thesis_alignment", "notes")
# Fields we accept as the fund's citation URL, best first.
URL_FIELDS = ("website_or_blog_url", "linkedin_url", "x_url")


def load_watchlist(vertical):
    path = DATA_DIR / vertical / "vc_watchlist.json"
    if not path.exists():
        return []
    data = json.load(open(path))
    if isinstance(data, list):
        return data
    for key in ("watchlist", "vcs", "funds", "investors"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


def source_urls(record):
    urls = []
    for f in URL_FIELDS:
        v = (record.get(f) or "").strip()
        if v and v not in urls:
            urls.append(v)
    return urls


def tag_record(record):
    """Return (tags_by_family, evidence) for one fund. Deterministic."""
    tags = {}          # family -> set of tags
    evidence = []      # [{family, tag, matched, field}]
    seen = set()       # (family, tag) already evidenced
    for field in TEXT_FIELDS:
        text = record.get(field)
        if not isinstance(text, str) or not text:
            continue
        for rx, family, tag in PHRASE_MAP:
            # headline `wants` only from differentiated fields, never boilerplate keywords
            if family == "wants" and field not in WANTS_FIELDS:
                continue
            m = rx.search(text)
            if not m:
                continue
            tags.setdefault(family, set()).add(tag)
            if (family, tag) not in seen:
                seen.add((family, tag))
                evidence.append({
                    "family": family, "tag": tag,
                    "matched": m.group(0), "field": field,
                })
    tags_out = {fam: sorted(vals) for fam, vals in sorted(tags.items())}
    return tags_out, evidence


def derive_vertical(vertical):
    records = load_watchlist(vertical)
    funds = []
    for r in records:
        tags, evidence = tag_record(r)
        if not tags:
            # No recon language matched -> no criteria. Recorded as uncovered,
            # not silently dropped, so coverage is honest.
            funds.append({
                "fund": r.get("firm") or "",
                "person": r.get("person_name") or "",
                "urls": source_urls(r),
                "tags": {},
                "evidence": [],
                "covered": False,
            })
            continue
        funds.append({
            "fund": r.get("firm") or "",
            "person": r.get("person_name") or "",
            "urls": source_urls(r),
            "tags": tags,
            "evidence": evidence,
            "covered": True,
        })
    out = {
        "vertical": vertical,
        "fund_count": len(records),
        "covered_count": sum(1 for f in funds if f["covered"]),
        "funds": funds,
    }
    out_path = DATA_DIR / vertical / "fund_criteria.json"
    json.dump(out, open(out_path, "w"), indent=2)
    return out


def main():
    which = sys.argv[1:] if len(sys.argv) > 1 else None
    verticals = [v["id"] for v in json.load(open(VERTICALS_PATH)).get("verticals", [])]
    if which:
        verticals = [v for v in verticals if v in which]
    for vid in verticals:
        res = derive_vertical(vid)
        print(f"{vid}: tagged {res['covered_count']}/{res['fund_count']} funds "
              f"-> data/{vid}/fund_criteria.json")


if __name__ == "__main__":
    main()
