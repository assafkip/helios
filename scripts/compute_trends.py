#!/usr/bin/env python3
"""
Compute deterministic trend analytics for FundVision.

Reads every signals-<vertical>.json plus verticals.json and writes trends.json —
no LLM, pure counting. The dashboard's Trends view renders this file.

Metrics per vertical:
- weekly sparkline (four 7-day buckets) + momentum % (last 7 days vs prior 7)
- deal heat (hard-signal count and ratio)
- whitespace score (talk vs money: soft/commentary/pain over funding)
- rising topics (n-gram frequency delta, recent 14 days vs prior 14)
- top movers (most active person/firm)

Cross-vertical:
- markets ranked by momentum (the "what's hot" lead)
- rising topics across every vertical

Usage: python3 scripts/compute_trends.py
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent
VERTICALS_PATH = PROJECT_ROOT / "verticals.json"
TRENDS_OUTPUT_PATH = PROJECT_ROOT / "trends.json"
HISTORY_PATH = PROJECT_ROOT / "trends-history.json"

HARD_CATEGORIES = {
    "new_investment", "new_fund_raised", "new_security_investment",
    "actively_looking", "new_thesis", "new_thesis_statement",
}
# Exit events (M&A / IPO) mined from the same feeds. An exit in a sector reads as
# VC appetite, tracked separately from deal heat (an exit is not an investment).
EXIT_CATEGORIES = {"exit_signal"}
TALK_CATEGORIES = {
    "market_commentary", "sector_pain", "deep_dive",
    "security_trend_commentary", "problem_post_soc_pain",
    "problem_post_detection_gaps", "threat_intelligence", "detection_engineering",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "up", "as", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "these", "those", "he", "she", "they", "we",
    "you", "his", "her", "their", "our", "your", "has", "have", "had", "will",
    "would", "can", "could", "may", "might", "not", "no", "new", "now", "how",
    "why", "what", "who", "when", "where", "which", "into", "out", "over", "more",
    "most", "all", "some", "just", "about", "after", "before", "than", "then",
    "them", "there", "here", "one", "two", "get", "got", "make", "made", "also",
    "says", "said", "say", "report", "reports", "week", "weekly", "day", "year",
    "via", "per", "amp", "inc", "llc", "com", "using", "use", "used", "top",
    "first", "next", "last", "back", "way", "big", "set", "off", "own", "many",
    # months + RSS boilerplate (kills feed-footer noise in rising topics)
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "post", "appeared", "read", "reading", "continue", "comments", "comment",
    "share", "subscribe", "subscriber", "newsletter", "episode", "source",
    "according", "told", "href", "http", "https", "www", "image", "photo",
    "like", "ago", "today", "yesterday", "company", "companies", "startups",
}


def strip_boilerplate(text):
    """Remove RSS footers that otherwise dominate the n-gram counts."""
    text = re.sub(r"the post .*? appeared first on.*", " ", text or "", flags=re.I | re.S)
    text = re.sub(r"(continue reading|read more|click here|the article).*", " ", text, flags=re.I | re.S)
    return text


def load_signals(vertical):
    path = PROJECT_ROOT / f"signals-{vertical}.json"
    if not path.exists():
        return []
    try:
        data = json.load(open(path))
    except Exception:
        return []
    return data if isinstance(data, list) else data.get("signals", [])


def days_ago(date_str, today):
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    delta = (today - d).days
    return max(0, delta)  # clamp future-dated feeds to "today"


def sparkline_and_momentum(signals, today):
    """Four 7-day buckets (oldest to newest) + last-7 vs prior-7 percent."""
    buckets = [0, 0, 0, 0]  # index 0 = oldest (21-27d), index 3 = newest (0-6d)
    for s in signals:
        da = days_ago(s.get("source_date"), today)
        if da is None or da > 27:
            continue
        buckets[3 - (da // 7)] += 1
    last7, prior7 = buckets[3], buckets[2]
    if prior7 == 0:
        momentum = 100 if last7 > 0 else 0
    else:
        momentum = round((last7 - prior7) / prior7 * 100)
    return buckets, momentum


def tokenize(text):
    text = re.sub(r"[^a-z0-9 ]", " ", strip_boilerplate(text).lower())
    return [t for t in text.split() if len(t) >= 3 and not t.isdigit() and t not in STOPWORDS]


def ngrams(signals, today, lo, hi):
    """Count unigrams + bigrams for signals dated [lo, hi] days ago."""
    counts = Counter()
    for s in signals:
        da = days_ago(s.get("source_date"), today)
        if da is None or da < lo or da > hi:
            continue
        toks = tokenize(f"{s.get('summary','')} {s.get('excerpt','')}")
        counts.update(toks)
        for a, b in zip(toks, toks[1:]):
            counts[f"{a} {b}"] += 1
    return counts


def rising_topics(signals, today, limit=8):
    recent = ngrams(signals, today, 0, 13)
    prior = ngrams(signals, today, 14, 29)
    scored = []
    for term, rc in recent.items():
        if rc < 2:
            continue
        # a bigram containing only its own unigrams is fine; dedupe substrings later
        delta = rc - prior.get(term, 0)
        scored.append({"term": term, "count": rc, "delta": delta})
    # prefer genuine risers (delta), then raw frequency
    scored.sort(key=lambda x: (x["delta"], x["count"]), reverse=True)
    # drop unigrams already covered by a higher-ranked bigram
    kept, seen_bigram_words = [], set()
    for item in scored:
        if " " in item["term"]:
            seen_bigram_words.update(item["term"].split())
            kept.append(item)
        elif item["term"] not in seen_bigram_words:
            kept.append(item)
        if len(kept) >= limit:
            break
    return kept


def top_movers(signals, today, limit=6):
    """Most active NAMED voices (investors/analysts), not wire-service outlets."""
    counts = Counter()
    labels = {}
    for s in signals:
        da = days_ago(s.get("source_date"), today)
        if da is None or da > 13:
            continue
        firm = s.get("firm") or ""
        if firm.lower() in ("news", "press", ""):
            continue
        name = s.get("person_name") or "Unknown"
        key = (name, firm)
        counts[key] += 1
        labels[key] = {"name": name, "firm": firm}
    return [{**labels[k], "count": c} for k, c in counts.most_common(limit)]


def compute_vertical(signals, today):
    total = len(signals)
    buckets, momentum = sparkline_and_momentum(signals, today)
    hard = sum(1 for s in signals if s.get("signal_category") in HARD_CATEGORIES)
    talk = sum(1 for s in signals if s.get("signal_category") in TALK_CATEGORIES)
    exits = sum(1 for s in signals if s.get("signal_category") in EXIT_CATEGORIES)
    hard_ratio = round(hard / total, 3) if total else 0
    whitespace = round(talk / hard, 1) if hard else float(talk)
    return {
        "total": total,
        "recent7": buckets[3],
        "sparkline": buckets,
        "momentum_pct": momentum,
        "momentum_basis": "window",
        "hard_count": hard,
        "hard_ratio": hard_ratio,
        "exit_count": exits,
        "talk_count": talk,
        "whitespace_score": whitespace,
        "rising": rising_topics(signals, today),
        "movers": top_movers(signals, today),
    }


def main():
    today = datetime.now(timezone.utc).date()
    verticals = json.load(open(VERTICALS_PATH)).get("verticals", [])

    per_vertical = {}
    all_signals = []
    highlights = []  # "who's investing today" — hard signals across every market
    for v in verticals:
        vid = v["id"]
        label = v.get("label", vid)
        signals = load_signals(vid)
        all_signals.extend(signals)
        per_vertical[vid] = {"label": label, **compute_vertical(signals, today)}
        for s in signals:
            # "who's investing today" = actual tracked investors (vc source), deal-first
            if s.get("source_kind") == "vc":
                highlights.append({
                    "person": s.get("person_name"), "firm": s.get("firm"),
                    "summary": s.get("summary"), "category": s.get("signal_category"),
                    "url": s.get("source_url"), "date": s.get("source_date"),
                    "vertical": label, "vid": vid,
                    "days": days_ago(s.get("source_date"), today) or 0,
                    "hard": 1 if s.get("signal_type") == "hard" else 0,
                })
    # freshest first, real deals first; one row per investor
    highlights.sort(key=lambda h: (h["days"], -h["hard"]))
    seen, dedup = set(), []
    for h in highlights:
        k = (h["person"] or h["firm"] or "").lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(h)
    highlights = dedup[:10]

    # Heartbeat: append a dated snapshot so week-over-week momentum becomes real
    # over time (RSS front-loads recent items, so single-snapshot momentum is noise).
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.load(open(HISTORY_PATH))
        except Exception:
            history = []
    today_str = today.strftime("%Y-%m-%d")
    history = [h for h in history if h.get("date") != today_str]  # one row per day
    history.append({"date": today_str, "totals": {vid: d["total"] for vid, d in per_vertical.items()}})
    history = sorted(history, key=lambda h: h["date"])[-90:]
    json.dump(history, open(HISTORY_PATH, "w"), indent=2)

    # Momentum vs the snapshot closest to 7 days ago, once that history exists.
    target = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    past = [h for h in history if h["date"] <= target]
    for vid, d in per_vertical.items():
        base = past[-1]["totals"].get(vid) if past else None
        if base:
            d["momentum_pct"] = round((d["total"] - base) / base * 100)
            d["momentum_basis"] = "7d"

    # cross-vertical: markets ranked by activity this week (the honest "what's hot" lead)
    momentum_ranked = sorted(
        (
            {
                "id": vid,
                "label": d["label"],
                "recent7": d["recent7"],
                "momentum_pct": d["momentum_pct"],
                "momentum_basis": d["momentum_basis"],
                "total": d["total"],
                "sparkline": d["sparkline"],
                "hard_ratio": d["hard_ratio"],
                "whitespace_score": d["whitespace_score"],
            }
            for vid, d in per_vertical.items()
        ),
        key=lambda x: (x["recent7"], x["total"]),
        reverse=True,
    )

    output = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verticals": per_vertical,
        "overall": {
            "momentum_ranked": momentum_ranked,
            "rising": rising_topics(all_signals, today, limit=10),
            "highlights": highlights,
            "total_signals": len(all_signals),
        },
    }
    json.dump(output, open(TRENDS_OUTPUT_PATH, "w"), indent=2)
    print(f"Wrote {TRENDS_OUTPUT_PATH} — {len(all_signals)} signals across {len(verticals)} verticals")
    print("Most active this week:", ", ".join(f"{m['label']} ({m['recent7']})" for m in momentum_ranked[:3]))


if __name__ == "__main__":
    main()
