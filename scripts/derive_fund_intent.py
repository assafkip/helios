#!/usr/bin/env python3
"""
Derive each fund's REVEALED thesis (DO) from its announced deals in the feed.

This is the deals-per-fund rollup. It reads the live signals feed, attributes
each deal to an investor via extract_investors.py, and rolls those deals up per
fund by sector + recency. The pattern of where a fund's money actually goes IS
its thesis — revealed preference, not the hand-typed conclusions the old
"What funds want" panel derived from vc_watchlist.json notes.

The engine reads ONLY feed rows (signals-<vertical>.json). It never opens
vc_watchlist.json, so a fund with typed notes but zero announced deals produces
NO intent. That is the point: DO, not SAY.

Two filters live here (the plan's known-limit fix for regex title-case noise):
- min-recurrence: a firm must appear >= N times or it is dropped (one-off
  title-case garbage like "Ransomware Gang Partners" never becomes a fund).
- canonicalization: geo-prefixed aliases collapse ("London-Based Tapestry VC"
  -> "Tapestry VC") so one firm is one fund.

The derived one-line thesis is a TEMPLATE over the deterministic counts, never an
LLM paraphrase — the LLM does extraction only (extract_investors), or the panel
re-grows the hand-typed-conclusions smell it was built to kill.

Single writer of fund-intent.json (the trends.json <- compute_trends.py pattern).

Usage:
  .venv/bin/python scripts/derive_fund_intent.py            # all verticals -> fund-intent.json
  .venv/bin/python scripts/derive_fund_intent.py --min 3    # stricter recurrence
Test:
  .venv/bin/python scripts/test_derive_fund_intent.py
"""

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone, date
from pathlib import Path

from extract_investors import (
    extract_investors, normalize_firm, load_cache, save_cache,
    fetch_article_text, make_haiku_extractor,
)

PROJECT_ROOT = Path(__file__).parent.parent
VERTICALS_PATH = PROJECT_ROOT / "verticals.json"
INTENT_OUTPUT_PATH = PROJECT_ROOT / "fund-intent.json"

# The DEAL set — money actually moving. Tighter than compute_trends' HARD set:
# actively_looking / new_thesis are SAY, not DO, so they are excluded. The
# extract_investors gate tightens this further — a miscategorized blog post
# (e.g. a Google Security Blog row tagged new_security_investment) carries no
# investor firm name in its text, so it attributes to nobody and drops out.
DEAL_CATEGORIES = {"new_investment", "new_fund_raised", "new_security_investment"}

# Recency weighting for sector ranking: a fresh deal reveals current appetite
# more than a stale one. Buckets, not a continuous decay, to stay legible.
def recency_weight(days):
    if days is None:
        return 0.25
    if days <= 30:
        return 1.0
    if days <= 90:
        return 0.5
    return 0.25


# Canonicalization: strip a leading geo/descriptor prefix so "London-Based
# Tapestry VC" and "Tapestry VC" are one fund. Prefix = a "<Word>-Based" token
# or a bare country code, followed by the real name.
_GEO_PREFIX_RE = re.compile(r"^(?:[A-Za-z][A-Za-z.]*-[Bb]ased|US|U\.S\.|UK|EU)\s+")


def canonicalize(name):
    """Collapse whitespace/punctuation and strip a leading geo prefix."""
    name = normalize_firm(name)
    prev = None
    while prev != name:  # strip repeated prefixes ("US London-Based X")
        prev = name
        name = _GEO_PREFIX_RE.sub("", name).strip()
    return name


def days_ago(date_str, today):
    if not date_str:
        return None
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    return max(0, (today - d).days)  # clamp future-dated feeds to today


def collect_deals(rows_by_sector, today, cache=None, fetcher=None, llm=None):
    """
    Walk every DEAL-category row, attribute investors, and emit one deal record
    per (fund, row). Returns a dict: canonical_fund -> list of deal records.
    fetcher + llm are the wired body-fetch + Haiku fallback (None -> regex-only).
    """
    deals_by_fund = defaultdict(list)
    seen = 0
    attributed = 0
    stats = {"fetch_attempts": 0, "fetch_ok": 0}
    for sector_label, rows in rows_by_sector.items():
        for row in rows:
            if row.get("signal_category") not in DEAL_CATEGORIES:
                continue
            seen += 1
            investors = extract_investors(
                row, fetcher=fetcher, llm=llm, cache=cache, stats=stats).get("investors", [])
            if investors:
                attributed += 1
            for firm in investors:
                fund = canonicalize(firm)
                if not fund:
                    continue
                deals_by_fund[fund].append({
                    "sector": sector_label,
                    "date": row.get("source_date"),
                    "days": days_ago(row.get("source_date"), today),
                    "summary": row.get("summary") or "",
                    "url": row.get("source_url") or "",
                })
    return deals_by_fund, seen, attributed, stats


def _sector_ranking(deals):
    """Sectors this fund deployed into, ranked by recency-weighted deal weight."""
    weight = defaultdict(float)
    count = defaultdict(int)
    for d in deals:
        weight[d["sector"]] += recency_weight(d["days"])
        count[d["sector"]] += 1
    ranked = sorted(count.keys(), key=lambda s: (weight[s], count[s]), reverse=True)
    return [{"label": s, "count": count[s], "weight": round(weight[s], 2)} for s in ranked]


def _cadence(deals):
    """Deal counts in recency windows so a burst reads as a burst."""
    recent30 = sum(1 for d in deals if d["days"] is not None and d["days"] <= 30)
    recent90 = sum(1 for d in deals if d["days"] is not None and d["days"] <= 90)
    prior30 = sum(1 for d in deals if d["days"] is not None and 30 < d["days"] <= 60)
    return recent30, recent90, prior30


def _thesis(fund, sectors, coverage, recent30):
    """
    Templated one-liner over the counts. NOT an LLM paraphrase — the numbers own
    the sentence, so it can never invent a conclusion the deals don't support.
    """
    top = [s["label"] for s in sectors[:2]]
    if len(top) == 1:
        focus = top[0]
    else:
        focus = f"{top[0]} and {top[1]}"
    recent_clause = f", {recent30} in the last 30d" if recent30 else ""
    return f"Revealed focus: {focus}. {coverage} attributed deal(s){recent_clause}."


def derive_intents(rows_by_sector, today, min_recurrence=2, cache=None,
                   fetcher=None, llm=None):
    """
    Pure rollup: feed rows in, fund-intent structure out. No file I/O, so the
    reproducer drives it with synthetic rows. Funds below min_recurrence are
    dropped (recurrence filter). Funds are ranked by coverage, then recency.
    """
    if isinstance(today, datetime):
        today = today.date()
    deals_by_fund, seen, attributed, stats = collect_deals(
        rows_by_sector, today, cache=cache, fetcher=fetcher, llm=llm)

    funds = []
    for fund, deals in deals_by_fund.items():
        if len(deals) < min_recurrence:
            continue
        sectors = _sector_ranking(deals)
        coverage = len(deals)
        recent30, recent90, prior30 = _cadence(deals)
        deal_days = [d["days"] for d in deals if d["days"] is not None]
        last_deal_days = min(deal_days) if deal_days else None
        deals_sorted = sorted(
            deals, key=lambda d: (d["days"] is None, d["days"] if d["days"] is not None else 1e9)
        )
        funds.append({
            "fund": fund,
            "thesis": _thesis(fund, sectors, coverage, recent30),
            "coverage": coverage,
            "sectors": sectors,
            "recent30": recent30,
            "recent90": recent90,
            "prior30": prior30,
            "last_deal_days": last_deal_days,
            "deals": [
                {"sector": d["sector"], "date": d["date"],
                 "summary": d["summary"], "url": d["url"]}
                for d in deals_sorted
            ],
        })

    funds.sort(key=lambda f: (f["coverage"], f["recent90"]), reverse=True)

    # Live fetchable rate — only meaningful when the fetch path actually ran.
    # None when regex-only (no fetch happened), so the UI omits it rather than
    # claiming a coverage number this run did not measure.
    attempts = stats.get("fetch_attempts", 0)
    fetchable_pct = round(stats["fetch_ok"] / attempts * 100) if attempts else None

    return {
        "min_recurrence": min_recurrence,
        "coverage": {
            "deal_rows_seen": seen,
            "deal_rows_attributed": attributed,
            "funds_tracked": len(funds),
            "fetch_attempts": attempts,
            "fetchable_pct": fetchable_pct,
            "update_cadence": "hourly",
        },
        "funds": funds,
    }


def _load_rows_by_sector():
    """Read every signals-<vertical>.json into {sector_label: [rows]}.

    Reads ONLY the feed. Never touches vc_watchlist.json — DO, not SAY.
    """
    verticals = json.load(open(VERTICALS_PATH)).get("verticals", [])
    rows_by_sector = {}
    for v in verticals:
        path = PROJECT_ROOT / f"signals-{v['id']}.json"
        if not path.exists():
            continue
        try:
            data = json.load(open(path))
        except (json.JSONDecodeError, OSError):
            continue
        rows = data if isinstance(data, list) else data.get("signals", [])
        rows_by_sector[v.get("label", v["id"])] = rows
    return rows_by_sector


def _index_by_vertical(result):
    """Group tracked funds under each sector they deployed into (for the panel)."""
    verticals = defaultdict(list)
    for fund in result["funds"]:
        for sector in fund["sectors"]:
            verticals[sector["label"]].append({
                "fund": fund["fund"],
                "thesis": fund["thesis"],
                "coverage": fund["coverage"],
                "sector_count": sector["count"],
                "recent30": fund["recent30"],
            })
    for label in verticals:
        verticals[label].sort(key=lambda f: (f["sector_count"], f["coverage"]), reverse=True)
    return dict(verticals)


def main():
    parser = argparse.ArgumentParser(description="Derive revealed fund intent from announced deals.")
    parser.add_argument("--min", type=int, default=2, help="min deals a firm must have to be tracked")
    parser.add_argument("--no-llm", action="store_true", help="regex-only, skip the Haiku body-fetch fallback")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).date()
    rows_by_sector = _load_rows_by_sector()
    cache = load_cache()

    # Wire the fallback if a key is present; otherwise stay regex-only (CI-safe).
    llm = None if args.no_llm else make_haiku_extractor()
    fetcher = fetch_article_text if llm else None
    print("fallback:", "Haiku body-extract wired" if llm else "regex-only (no ANTHROPIC_API_KEY or --no-llm)")

    result = derive_intents(rows_by_sector, today, min_recurrence=args.min,
                            cache=cache, fetcher=fetcher, llm=llm)
    save_cache(cache)

    output = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **result,
        "by_vertical": _index_by_vertical(result),
    }
    json.dump(output, open(INTENT_OUTPUT_PATH, "w"), indent=2)

    cov = result["coverage"]
    print(f"Wrote {INTENT_OUTPUT_PATH}")
    print(f"  deal rows seen: {cov['deal_rows_seen']}  attributed: {cov['deal_rows_attributed']}"
          f"  funds tracked (>= {args.min} deals): {cov['funds_tracked']}")
    for f in result["funds"][:8]:
        print(f"  {f['fund']:<28} {f['coverage']} deals  {f['thesis']}")


if __name__ == "__main__":
    main()
