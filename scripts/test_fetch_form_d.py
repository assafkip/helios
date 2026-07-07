#!/usr/bin/env python3
"""
Reproducer for fetch_form_d.py — SEC EDGAR Form D dry-powder signal (Phase 3b).

A private investment fund filing Form D just raised capital it now has to deploy
("who has money to deploy"). The parser mines EDGAR's free Form D feed and keeps
ONLY pooled investment funds (Item 3C / Section 3(c) markers), dropping operating
-company Reg D raises and non-Form-D forms that leak into the feed.

Runs against a REAL captured EDGAR fixture (scripts/fixtures/edgar_form_d_sample.xml,
2 funds + 1 operating company + 1 non-D form) — no network in the test.

Run: .venv/bin/python scripts/test_fetch_form_d.py   (or: pytest -q)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_form_d import parse_form_d_feed, filer_name, form_type

FIXTURE = Path(__file__).parent / "fixtures" / "edgar_form_d_sample.xml"


def _rows():
    return parse_form_d_feed(FIXTURE.read_text())


def test_only_pooled_funds_survive():
    rows = _rows()
    names = {r["person_name"] for r in rows}
    # the 2 private funds are kept
    assert "TSOF III GP Coinvestment, L.P." in names, names
    assert "Volantis I, LP" in names, names
    # the operating company Form D (no 3(c) marker) is dropped
    assert not any("Northstar Baseball" in n for n in names), names
    # the non-Form-D form (DEFA14A) is dropped
    assert not any("BLACKROCK" in n.upper() for n in names), names
    assert len(rows) == 2, len(rows)


def test_rows_match_signals_contract():
    r = _rows()[0]
    assert r["signal_category"] == "dry_powder", r
    assert r["signal_type"] == "hard", r
    assert r["firm"] == "SEC Form D", r
    assert r["source_type"] == "sec-form-d", r
    assert r["source_url"].startswith("https://www.sec.gov/"), r
    assert len(r["source_date"]) == 10 and r["source_date"][4] == "-", r
    assert r["confidence"] == "high", r


def test_filer_name_strips_form_and_cik():
    assert filer_name("D - Volantis I, LP (0002144231) (Filer)") == "Volantis I, LP"
    assert form_type("D - Volantis I, LP (0002144231) (Filer)") == "D"
    assert form_type("DEFA14A - BLACKROCK ... (0001053988) (Filer)") == "DEFA14A"


def test_dry_powder_excluded_from_deal_categories():
    # Form D names the FUND, not the portfolio company it will back. It is a
    # fund-formation signal, not per-deal attribution ({{NEEDS_PROOF}} on
    # outside-investor attribution). It must NOT feed the deals-per-fund rollup.
    import derive_fund_intent
    assert "dry_powder" not in derive_fund_intent.DEAL_CATEGORIES


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
