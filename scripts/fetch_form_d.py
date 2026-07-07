#!/usr/bin/env python3
"""
SEC EDGAR Form D -> "dry powder" signal (Phase 3b, new free gov source).

When a private investment fund files Form D, it just raised capital it now has to
deploy. That is a founder-useful demand signal: who has fresh money. This mines
EDGAR's free "latest filings" Atom feed (type=D), keeps ONLY pooled investment
funds (Item 3C / Section 3(c) markers), and emits signals-schema rows.

Free + ToS-clean: SEC EDGAR is public gov data; the only requirement is a
descriptive User-Agent with contact (set below). No API key.

{{NEEDS_PROOF}} — attribution limit: Form D names the FUND (the issuer), not the
portfolio companies it will back or its LPs. So dry_powder is a fund-FORMATION
signal, not per-deal attribution. It deliberately does NOT feed derive_fund_intent's
deals-per-fund rollup (that reads announced portfolio deals, which name the investor
in the article body).

Single writer of form-d-signals.json.

Usage: .venv/bin/python scripts/fetch_form_d.py            # fetch live -> form-d-signals.json
       .venv/bin/python scripts/fetch_form_d.py --count 200
Test:  .venv/bin/python scripts/test_fetch_form_d.py       # runs against a captured fixture
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = PROJECT_ROOT / "form-d-signals.json"

# SEC requires a descriptive UA with contact for automated access. Not a secret.
USER_AGENT = "FundVision research assafkip@gmail.com"
EDGAR_FEED = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=D"
    "&company=&dateb=&owner=include&count={count}&output=atom"
)

# The getcurrent feed leaks related forms (a filer's other current filings), so
# the form type is checked explicitly — only real Form D / amendments count.
FORM_D_TYPES = {"D", "D/A"}

# Item 3C / Section 3(c) exemptions mark a private investment fund (3(c)(1) or
# 3(c)(7)). Their presence is the discriminator between "a fund raised its fund"
# (dry powder) and "an operating company did a Reg D raise" (not dry powder).
POOLED_FUND_MARKERS = ("Section 3(c)", "Investment Company Act")

_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_LINK_RE = re.compile(r'<link[^>]*href="([^"]+)"', re.S)
_UPDATED_RE = re.compile(r"<updated>(\d{4}-\d{2}-\d{2})", re.S)
_ENTRY_RE = re.compile(r"<entry>.*?</entry>", re.S)
_FORMTYPE_RE = re.compile(r"^\s*([A-Z0-9/\-]+)\s+-\s")
_FILER_RE = re.compile(r"^\s*[A-Z0-9/\-]+\s+-\s+(.*?)\s+\(\d+\)\s+\(Filer\)\s*$")


def _entry_title(entry):
    m = _TITLE_RE.search(entry)
    return (m.group(1) if m else "").strip()


def form_type(title):
    """Form type from an entry title: 'D - Foo (123) (Filer)' -> 'D'."""
    m = _FORMTYPE_RE.match(title or "")
    return m.group(1) if m else ""


def filer_name(title):
    """Filer name from an entry title, stripping the form prefix + CIK + (Filer)."""
    m = _FILER_RE.match(title or "")
    return m.group(1).strip() if m else ""


def _is_pooled_fund(entry):
    return any(marker in entry for marker in POOLED_FUND_MARKERS)


def _filing_url(entry):
    m = _LINK_RE.search(entry)
    return (m.group(1) if m else "").strip()


def _filing_date(entry, today):
    m = _UPDATED_RE.search(entry)
    return m.group(1) if m else today


def parse_form_d_feed(xml, today=None):
    """Parse the EDGAR Atom feed -> list of dry_powder rows (pooled funds only).

    Pure: no network. today defaults to the UTC date, used only when an entry
    lacks a filing date.
    """
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []
    for entry in _ENTRY_RE.findall(xml or ""):
        title = _entry_title(entry)
        if form_type(title) not in FORM_D_TYPES:
            continue
        if not _is_pooled_fund(entry):
            continue
        name = filer_name(title)
        if not name:
            continue
        rows.append({
            "person_name": name,
            "firm": "SEC Form D",
            "signal_type": "hard",
            "signal_category": "dry_powder",
            "summary": f"{name} filed Form D — private fund raising capital (fresh dry powder to deploy)",
            "excerpt": "SEC Form D, Item 3C private-fund exemption. Names the fund, not its portfolio deals.",
            "source_url": _filing_url(entry),
            "source_type": "sec-form-d",
            "source_date": _filing_date(entry, today),
            "confidence": "high",
        })
    return rows


def _fetch_feed(count):
    import urllib.request
    url = EDGAR_FEED.format(count=count)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def main():
    parser = argparse.ArgumentParser(description="Mine SEC Form D dry-powder signals.")
    parser.add_argument("--count", type=int, default=100, help="how many recent filings to pull")
    args = parser.parse_args()

    try:
        xml = _fetch_feed(args.count)
    except Exception as exc:  # noqa: BLE001 - a down gov endpoint is not fatal
        print(f"EDGAR fetch failed ({type(exc).__name__}: {exc}); leaving {OUTPUT_PATH.name} unchanged")
        return

    rows = parse_form_d_feed(xml)
    output = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "SEC EDGAR Form D (getcurrent feed)",
        "count": len(rows),
        "signals": rows,
    }
    json.dump(output, open(OUTPUT_PATH, "w"), indent=2)
    print(f"Wrote {OUTPUT_PATH} — {len(rows)} private-fund Form D filings (dry powder)")
    for r in rows[:8]:
        print(f"  {r['source_date']}  {r['person_name']}")


if __name__ == "__main__":
    main()
