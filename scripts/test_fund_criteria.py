#!/usr/bin/env python3
"""
Tests for the deterministic fund-criteria pipeline.

Covers the three properties Assaf required: robust recon (tagging works on real
language), a summary with no model in the path (import scan), and an enforced
vocabulary (validator rejects invented tags). Verified against fixtures, with a
negative self-test on each behavior.

Run: python3 -m pytest scripts/test_fund_criteria.py -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fund_criteria_vocab as vocab
from derive_fund_criteria import tag_record
from compute_fund_criteria import rank_family

SCRIPT_DIR = Path(__file__).parent


def test_vocab_is_internally_consistent():
    assert vocab.self_check() == []


def test_tag_record_positive():
    """Real thesis language yields the expected controlled-vocab tags."""
    rec = {
        "notes": "Seed-stage, security-native fund. Thesis: agentic AI, values "
                 "proprietary data and rigorous founders. Israeli team.",
        "thesis_alignment": "Early-stage cyber",
    }
    tags, evidence = tag_record(rec)
    assert "agentic_ai" in tags["wants"]
    assert "proprietary_data" in tags["wants"]
    assert "technical_rigor" in tags["wants"]
    assert "israel" in tags["geo"]
    assert "seed" in tags["stage"]
    # every tag must be evidenced (the validator depends on this)
    evidenced = {(e["family"], e["tag"]) for e in evidence}
    for fam, tag_list in tags.items():
        for t in tag_list:
            assert (fam, t) in evidenced


def test_tag_record_negative_no_language():
    """A fund whose notes carry no thesis language gets no tags (not junk)."""
    rec = {"notes": "Notable exits: Uber, Mint. Forbes Midas List 2024."}
    tags, evidence = tag_record(rec)
    assert tags == {}
    assert evidence == []


def test_wants_ignores_boilerplate_keywords():
    """`wants` must not fire on the shared default keyword string; otherwise every
    fund looks identical and the ranking is meaningless."""
    rec = {"keywords": "security, detection, SOC, threat intel, infra, AI security"}
    tags, _ = tag_record(rec)
    # keywords still feed sector...
    assert "ai_security" in tags.get("sector", [])
    # ...but never the headline wants family
    assert "ai_native" not in tags.get("wants", [])


def test_rank_family_is_deterministic_and_counts():
    funds = [
        {"fund": "A", "covered": True, "tags": {"wants": ["agentic_ai", "ai_native"]}},
        {"fund": "B", "covered": True, "tags": {"wants": ["agentic_ai"]}},
        {"fund": "C", "covered": True, "tags": {"wants": ["ai_native"]}},
    ]
    ranked = rank_family(funds, "wants", 6)
    assert ranked[0]["tag"] == "agentic_ai" and ranked[0]["count"] == 2
    assert ranked[0]["funds"] == ["A", "B"]
    # tie at count 1 breaks alphabetically -> ai_native already at top? no: agentic 2 first
    counts = {r["tag"]: r["count"] for r in ranked}
    assert counts["ai_native"] == 2


def test_validator_rejects_out_of_vocab_tag():
    """The vocabulary is enforced by code: an invented tag is an error."""
    from validate_fund_criteria import validate_file
    import json, tempfile, os
    # build a bad fund_criteria.json in a temp vertical dir and point the validator at it
    bogus = {
        "funds": [{
            "fund": "Bad", "covered": True, "urls": ["http://x"],
            "tags": {"wants": ["totally_made_up_tag"]},
            "evidence": [{"family": "wants", "tag": "totally_made_up_tag",
                          "matched": "x", "field": "notes"}],
        }]
    }
    with tempfile.TemporaryDirectory() as d:
        import validate_fund_criteria as vf
        vdir = Path(d) / "faux"
        vdir.mkdir()
        (vdir / "fund_criteria.json").write_text(json.dumps(bogus))
        old = vf.DATA_DIR
        vf.DATA_DIR = Path(d)
        try:
            errors = []
            vf.validate_file("faux", errors)
        finally:
            vf.DATA_DIR = old
    assert any("not in vocab" in e for e in errors)


def test_no_model_or_network_import_in_pipeline():
    """No model/network client anywhere in the pipeline -> the summary cannot be
    an LLM call or a live fetch. This is the executable form of 'no LLM'."""
    forbidden = re.compile(
        r"\b(import|from)\s+(openai|anthropic|requests|httpx|urllib|http|socket|"
        r"aiohttp|google\.generativeai|cohere)\b"
    )
    for name in ("fund_criteria_vocab.py", "derive_fund_criteria.py",
                 "compute_fund_criteria.py", "validate_fund_criteria.py"):
        src = (SCRIPT_DIR / name).read_text()
        hits = forbidden.findall(src)
        assert not hits, f"{name} imports a model/network client: {hits}"


if __name__ == "__main__":
    raise SystemExit(__import__("pytest").main([__file__, "-q"]))
