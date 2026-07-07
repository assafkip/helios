#!/usr/bin/env python3
"""
Reproducer for the exit_signal classifier (Phase 3 — VC appetite from exits).

An M&A or IPO in a sector is a VC-appetite signal, mined from feeds we already
read. It must be a distinct HARD category, not buried in the soft portfolio
catch-all, and it must not steal genuine investment headlines or fire on the
word "exit" used in a non-deal sense ("exit node").

Run: .venv/bin/python scripts/test_exit_classifier.py   (or: pytest -q)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import live_monitor
from live_monitor import (
    FeedMonitor, HARD_SIGNAL_KEYWORDS, SOFT_SIGNAL_KEYWORDS,
    GENERIC_HARD_KEYWORDS, GENERIC_SOFT_KEYWORDS,
)


def _classifier(hard, soft):
    """A FeedMonitor with only the keyword tables set — no file/network load."""
    m = FeedMonitor.__new__(FeedMonitor)
    m.hard_keywords = hard
    m.soft_keywords = soft
    return m


def test_ma_headline_is_exit_signal():
    m = _classifier(HARD_SIGNAL_KEYWORDS, SOFT_SIGNAL_KEYWORDS)
    t, c = m._detect_signal_type("CrowdStrike acquires Adaptive Shield for $300M")
    assert (t, c) == ("hard", "exit_signal"), (t, c)


def test_ipo_headline_is_exit_signal():
    m = _classifier(GENERIC_HARD_KEYWORDS, GENERIC_SOFT_KEYWORDS)
    t, c = m._detect_signal_type("Fintech startup Wiz files for IPO")
    assert (t, c) == ("hard", "exit_signal"), (t, c)


def test_exit_node_is_not_exit_signal():
    # "exit" in a non-deal sense must NOT trip the classifier.
    m = _classifier(HARD_SIGNAL_KEYWORDS, SOFT_SIGNAL_KEYWORDS)
    t, c = m._detect_signal_type("How to configure a Tor exit node safely")
    assert c != "exit_signal", (t, c)


def test_investment_headline_still_wins_over_exit():
    # A genuine raise must classify as an investment, not an exit.
    m = _classifier(GENERIC_HARD_KEYWORDS, GENERIC_SOFT_KEYWORDS)
    t, c = m._detect_signal_type("Sequoia backs Acme in a seed round")
    assert t == "hard" and c != "exit_signal", (t, c)


def test_exit_signal_excluded_from_deal_categories():
    # derive_fund_intent must not treat an exit as a fund making an investment.
    import derive_fund_intent
    assert "exit_signal" not in derive_fund_intent.DEAL_CATEGORIES


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
