#!/usr/bin/env python3
"""
Investor attribution for FundVision DO (deals-per-fund) — the cheap-LLM unlock.

Regex-first, LLM-fallback, always verified. Pulls the investor(s) out of a deal
row so `derive_fund_intent.py` can roll deals up per fund.

Pipeline per row:
  1. extract_from_text  — deterministic regex on the summary/excerpt (FREE, no fetch)
  2. if regex finds nothing AND a fetcher+llm are wired — fetch the linked article
     body and Haiku-extract (recon proved investors live in the body)
  3. verify_against_source — drop any name not literally in the source text
     (LLM hallucination guard: recon leaked "Fenwick LLP" + individuals)
  4. filter_noise — drop law firms + person-name individuals

The LLM + fetcher are INJECTED (default None) so the deterministic core is fully
testable offline. Model tier for the fallback = Haiku (data extraction,
model-allocation.md). Cache by source_url so each row is extracted once.

Run over real data: .venv/bin/python scripts/extract_investors.py cyber
Test:               .venv/bin/python scripts/test_extract_investors.py
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CACHE_PATH = PROJECT_ROOT / "investor-cache.json"

# Investor-firm name suffixes. Kept tight on purpose: "Fund"/"Group" over-match
# generic prose ("Energy Fund"), so they are excluded from the v1 suffix set.
SUFFIX = r"(?:Ventures|Capital|Partners|Equity|VC)"
_WORD = r"[A-Z][A-Za-z0-9.&'’-]*"

# 1) Capitalized phrase ending in an investor suffix: "Khosla Ventures".
FIRM_RE = re.compile(rf"\b({_WORD}(?:\s+{_WORD}){{0,3}}\s+{SUFFIX})\b")
# 2) Entity named by an investing verb: "led by X", "backed by X", "investors include X".
# The trigger is case-insensitive via (?i:...) scoping ONLY — the captured entity
# keeps its strict [A-Z] anchor, so lowercase noun phrases ("the fossil fuel
# industry") no longer leak in.
LED_RE = re.compile(
    rf"(?i:led by|backed by|participation from|investors?\s+includ\w*)\s+({_WORD}(?:\s+{_WORD}){{0,3}})"
)
# 3) Suffix-less backer in a headline: "Google backs Proxima Fusion" -> "Google".
BACKS_RE = re.compile(rf"\b({_WORD}(?:\s+{_WORD}){{0,2}})\s+backs?\b")

# Law-firm / advisor markers — never investors, always dropped.
LAW_RE = re.compile(r"\b(LLP|L\.L\.P|Law|Attorneys)\b", re.I)

# Generic adjectives/nouns that precede an investor suffix in ordinary prose
# ("Fresh Capital", "Venture Capital", "Global Equity") — a name LED by one of
# these is a phrase, not a firm. Dropped when it is the leading word.
GENERIC_HEADS = {
    "Fresh", "Serious", "Venture", "Working", "Global", "Financial", "Private",
    "Public", "Human", "Social", "Total", "Growth", "Sovereign", "Real", "Open",
    "Know", "Need", "Save", "Restoring", "Confidence", "Financing", "More", "New",
}

# Suffix-less firms that look like person names ("First Last"). Seed set; extend
# as real feed data surfaces more. Without this, the person-name filter would
# wrongly drop eponymous funds.
KNOWN_FIRMS = {
    "Andreessen Horowitz", "Kleiner Perkins", "Founders Fund", "General Catalyst",
    "Bessemer Venture", "Google", "Microsoft", "Nvidia", "Salesforce", "Coatue",
    "Tiger Global", "Insight Partners", "Sequoia", "Benchmark", "Greylock",
}


def normalize_firm(name):
    """Collapse whitespace, strip trailing punctuation/whitespace."""
    return re.sub(r"\s+", " ", name or "").strip().strip(".").strip()


def _is_person_shaped(name):
    """Two capitalized words, no investor suffix — looks like 'Tony James'."""
    words = name.split()
    if len(words) != 2:
        return False
    if re.search(SUFFIX, name):
        return False
    return all(w[:1].isupper() for w in words)


def extract_from_text(text):
    """Deterministic investor extraction from deal text. Order-preserving, deduped."""
    if not text:
        return []
    found = []
    for regex in (FIRM_RE, LED_RE, BACKS_RE):
        for match in regex.finditer(text):
            found.append(normalize_firm(match.group(1)))
    seen, out = set(), []
    for name in found:
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def filter_noise(names):
    """Drop law firms, generic-head phrases, and person-name individuals."""
    kept = []
    for name in names:
        if LAW_RE.search(name):
            continue
        head = name.split()[0] if name.split() else ""
        if head in GENERIC_HEADS:
            continue
        if _is_person_shaped(name) and name not in KNOWN_FIRMS:
            continue
        kept.append(name)
    return kept


def verify_against_source(names, source):
    """Keep only names that appear literally in the source (LLM hallucination guard)."""
    low = (source or "").lower()
    return [n for n in names if n.lower() in low]


def load_cache():
    if CACHE_PATH.exists():
        try:
            return json.load(open(CACHE_PATH))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_cache(cache):
    json.dump(cache, open(CACHE_PATH, "w"), indent=2)


def extract_investors(row, fetcher=None, llm=None, cache=None, stats=None):
    """
    Resolve investors for one deal row. Regex-first (free); article fetch + LLM
    fallback only when regex is empty and both are wired. Returns
    {"investors": [...], "method": "regex|llm|cache|none"}.

    stats (optional mutable dict): counts fetch_attempts / fetch_ok so the caller
    can report a LIVE fetchable rate instead of a hardcoded claim. Only touched
    when the fetch path actually runs.
    """
    url = row.get("source_url") or ""
    if cache is not None and url in cache:
        return {"investors": cache[url], "method": "cache"}

    text = f"{row.get('summary', '')} {row.get('excerpt', '')}"
    names = filter_noise(extract_from_text(text))
    method = "regex" if names else "none"

    llm_ran = False
    if not names and fetcher and llm and url:
        body = fetcher(url)
        if stats is not None:
            stats["fetch_attempts"] = stats.get("fetch_attempts", 0) + 1
            if body:
                stats["fetch_ok"] = stats.get("fetch_ok", 0) + 1
        if body:
            llm_ran = True
            raw = [normalize_firm(n) for n in llm(body)]
            names = filter_noise(verify_against_source(raw, body))
            method = "llm" if names else "none"

    # Cache only DEFINITIVE answers: names found, or the LLM fallback actually
    # ran. A regex-miss with no LLM wired is NOT definitive — caching [] there
    # would block the LLM from ever reprocessing the row once it is wired.
    if cache is not None and url and (names or llm_ran):
        cache[url] = names
    return {"investors": names, "method": method}


# ---------------------------------------------------------------------------
# The wired fallback: fetch the article body + Haiku-extract investors.
#
# Both are built lazily and degrade to None when unavailable (no network, no
# ANTHROPIC_API_KEY). When they are None the extractor stays regex-only, so the
# repo's no-secrets automation and the offline tests keep working unchanged.
# Model tier = Haiku (data extraction, model-allocation.md).
# ---------------------------------------------------------------------------

HAIKU_MODEL = "claude-haiku-4-5"
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_HTML_RE = re.compile(r"<[^>]+>")


def fetch_article_text(url, timeout=15, max_chars=12000):
    """Fetch a public article and return its visible text (HTML stripped).

    Returns "" on any failure (403, timeout, non-HTML) — a blocked domain is a
    known, measured coverage gap (recon: ~94% fetchable), not an error to raise.
    """
    import urllib.request
    import urllib.error

    if not url:
        return ""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return ""
            raw = resp.read(2_000_000).decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = _HTML_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


_LLM_PROMPT = (
    "Extract ONLY the investor / venture-capital firm names that appear VERBATIM "
    "in the text below. Rules: include VC funds, corporate investors, and angel "
    "syndicates that are BACKING a deal. Exclude the company raising money, law "
    "firms, banks acting as advisors, and individual people's names. Return a "
    "JSON array of strings and nothing else. If none, return [].\n\nTEXT:\n"
)


def make_haiku_extractor():
    """Return an llm(body) -> [names] callable, or None if no API key is set.

    Uses the Anthropic Messages API over stdlib urllib — no SDK dependency. The
    caller pairs this with verify_against_source, so a hallucinated name is
    dropped even if the model invents one.
    """
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    import json as _json
    import urllib.request
    import urllib.error

    def llm(body):
        payload = _json.dumps({
            "model": HAIKU_MODEL,
            "max_tokens": 400,
            "messages": [{"role": "user", "content": _LLM_PROMPT + body}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.loads(resp.read().decode("utf-8", errors="ignore"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            return []
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        raw = "".join(parts).strip()
        match = re.search(r"\[.*\]", raw, re.S)  # tolerate prose around the array
        if not match:
            return []
        try:
            names = _json.loads(match.group(0))
        except _json.JSONDecodeError:
            return []
        return [n for n in names if isinstance(n, str)]

    return llm


def _run_over_vertical(vertical):
    """Offline regex-only pass over a real signals file — proves wiring + hit rate."""
    path = PROJECT_ROOT / f"signals-{vertical}.json"
    if not path.exists():
        print(f"no such file: {path}")
        return 1
    data = json.load(open(path))
    rows = data if isinstance(data, list) else data.get("signals", [])
    hits = 0
    for row in rows:
        result = extract_investors(row)
        if result["investors"]:
            hits += 1
            print(f"  {result['investors']}  <-  {row.get('summary', '')[:70]}")
    print(f"\n{hits}/{len(rows)} rows attributed by regex alone (no fetch) in '{vertical}'")
    return 0


if __name__ == "__main__":
    vertical = sys.argv[1] if len(sys.argv) > 1 else "cyber"
    sys.exit(_run_over_vertical(vertical))
