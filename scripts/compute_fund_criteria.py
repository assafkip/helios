#!/usr/bin/env python3
"""
Rank fund criteria into "the top things funds want" per vertical.

Single writer of the root `fund-criteria.json` — the file the site panel reads.
Pure counting over the per-vertical `data/<v>/fund_criteria.json` produced by
derive_fund_criteria.py. Same shape of deterministic rollup as compute_trends.py
(no model call): count how many funds carry each tag, rank, keep the top N.

The `wants` ranking is the headline Daniel asked for: the most common things
investors in a sector look for, so a founder can tailor the deck to them.

Usage: python3 scripts/compute_fund_criteria.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fund_criteria_vocab import TAG_LABELS

PROJECT_ROOT = Path(__file__).parent.parent
VERTICALS_PATH = PROJECT_ROOT / "verticals.json"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_PATH = PROJECT_ROOT / "fund-criteria.json"

# Families we rank, and how many rows to keep in each. `wants` is the headline.
RANKED_FAMILIES = {"wants": 6, "sector": 5, "stage": 4, "geo": 4}


def load_criteria(vertical):
    path = DATA_DIR / vertical / "fund_criteria.json"
    if not path.exists():
        return None
    try:
        return json.load(open(path))
    except Exception:
        return None


def rank_family(funds, family, limit):
    """Count how many funds carry each tag in `family`, ranked, with the
    contributing fund names. Deterministic: ties break alphabetically by tag."""
    counts = Counter()
    carriers = defaultdict(list)
    for f in funds:
        name = f.get("fund") or f.get("person") or "Unknown"
        for tag in f.get("tags", {}).get(family, []):
            counts[tag] += 1
            if name not in carriers[tag]:
                carriers[tag].append(name)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "tag": tag,
            "label": TAG_LABELS.get(tag, tag),
            "count": count,
            "funds": carriers[tag],
        }
        for tag, count in ranked[:limit]
    ]


def compute_vertical(label, criteria):
    funds = criteria.get("funds", [])
    covered = [f for f in funds if f.get("covered")]
    out = {
        "label": label,
        "fund_count": criteria.get("fund_count", len(funds)),
        "covered_count": criteria.get("covered_count", len(covered)),
    }
    for family, limit in RANKED_FAMILIES.items():
        out[family] = rank_family(covered, family, limit)
    return out


def main():
    verticals = json.load(open(VERTICALS_PATH)).get("verticals", [])
    per_vertical = {}
    for v in verticals:
        vid = v["id"]
        criteria = load_criteria(vid)
        if not criteria:
            continue
        per_vertical[vid] = compute_vertical(v.get("label", vid), criteria)

    output = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verticals": per_vertical,
    }
    json.dump(output, open(OUTPUT_PATH, "w"), indent=2)

    total = len(per_vertical)
    print(f"Wrote {OUTPUT_PATH} — {total} verticals")
    for vid, d in per_vertical.items():
        top = ", ".join(f"{w['label']} ({w['count']})" for w in d["wants"][:3])
        print(f"  {vid}: {d['covered_count']}/{d['fund_count']} funds | top wants: {top}")


if __name__ == "__main__":
    main()
