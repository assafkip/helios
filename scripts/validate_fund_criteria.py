#!/usr/bin/env python3
"""
Validator for derived fund criteria. Exit non-zero blocks a bad commit / CI run.

Checks every `data/<vertical>/fund_criteria.json`:
  1. every tag is in TAG_VOCAB and in the right family (no invented tags),
  2. every tag has a TAG_LABELS entry (so the site never renders a raw slug),
  3. every covered fund carries at least one citation URL (grounding),
  4. every tag on a covered fund is backed by an evidence row.

This is the executable guarantee behind the vocabulary; the ranking is only as
trustworthy as this check passing.

Usage: python3 scripts/validate_fund_criteria.py    # exit 0 pass, 1 fail
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fund_criteria_vocab import TAG_VOCAB, TAG_LABELS

PROJECT_ROOT = Path(__file__).parent.parent
VERTICALS_PATH = PROJECT_ROOT / "verticals.json"
DATA_DIR = PROJECT_ROOT / "data"


def validate_file(vertical, errors):
    path = DATA_DIR / vertical / "fund_criteria.json"
    if not path.exists():
        return
    data = json.load(open(path))
    for f in data.get("funds", []):
        who = f.get("fund") or f.get("person") or "?"
        tags = f.get("tags", {})
        covered = f.get("covered")
        # evidence index for cross-check
        ev = {(e["family"], e["tag"]) for e in f.get("evidence", [])}
        for family, tag_list in tags.items():
            if family not in TAG_VOCAB:
                errors.append(f"{vertical}/{who}: unknown family {family!r}")
                continue
            for tag in tag_list:
                if tag not in TAG_VOCAB[family]:
                    errors.append(f"{vertical}/{who}: tag {tag!r} not in vocab family {family!r}")
                if tag not in TAG_LABELS:
                    errors.append(f"{vertical}/{who}: tag {tag!r} has no label")
                if (family, tag) not in ev:
                    errors.append(f"{vertical}/{who}: tag {tag!r} has no evidence row")
        if covered and not f.get("urls"):
            errors.append(f"{vertical}/{who}: covered fund has no citation URL")


def main():
    verticals = [v["id"] for v in json.load(open(VERTICALS_PATH)).get("verticals", [])]
    errors = []
    for vid in verticals:
        validate_file(vid, errors)
    if errors:
        for e in errors:
            print("FAIL:", e)
        print(f"\n{len(errors)} validation error(s)")
        return 1
    print("fund-criteria validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
