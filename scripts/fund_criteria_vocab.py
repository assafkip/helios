#!/usr/bin/env python3
"""
Controlled vocabulary + phrase dictionary for FundVision fund-criteria recon.

This module is the single source of the recon knowledge: the fixed set of tags a
fund can be labelled with, and the phrase->tag map that derives those tags from a
fund's curated notes/thesis text. It is pure data + regex (no model call).

The in-vocab guarantee is held by executable code, not by this comment:
- the validator script `validate_fund_criteria.py` fails on any out-of-vocab tag,
- the pytest test `test_fund_criteria.py` runs `self_check()` below and an
  import-scan that fails if any consumer imports a model/network client.

`derive_fund_criteria.py` uses PHRASE_MAP to tag funds; `compute_fund_criteria.py`
ranks the `wants` family into the "top things funds want".

To teach the system a new signal, add a (pattern, family, tag) row here and, if the
tag is new, add it to TAG_VOCAB. That is the whole extension surface.
"""

from __future__ import annotations

import re

# The fixed allowlist. A tag outside these sets is a bug and the validator blocks it.
TAG_VOCAB = {
    "stage": {"pre_seed", "seed", "early_stage", "series_a", "growth"},
    "geo": {"israel", "us", "europe", "mena"},
    "sector": {
        "soc_detection", "ai_security", "cloud_infra", "enterprise",
        "devops_observability", "data", "hardware_industrial",
    },
    # `wants` is the headline family: what a fund looks for in a company/founder.
    # This is the ranking Daniel asked for ("top 3 things investors want").
    "wants": {
        "agentic_ai", "ai_native", "autonomous_systems", "proprietary_data",
        "quantified_outcomes", "technical_rigor", "proactive_posture",
        "founder_first", "distributed_systems", "security_native_team",
        "social_impact_objective", "international_market_path",
        # fintech-specific
        "unit_economics", "embedded_finance", "regulated_market", "operator_dna",
        # ai-ml-specific
        "applied_ai", "domain_expertise",
        # healthtech / climate / edtech / marketing / space
        "clinical_evidence", "reimbursement_path", "cost_competitive",
        "hard_science", "decarbonization_impact", "efficacy_outcomes",
        "product_led_growth", "distribution_advantage", "dual_use_defense",
    },
}

# Human-readable labels for the site panel. Every tag that can rank must have one.
TAG_LABELS = {
    # wants
    "agentic_ai": "Agentic AI in the product",
    "ai_native": "AI-native, not a wrapper",
    "autonomous_systems": "Autonomous / self-running systems",
    "proprietary_data": "A proprietary data advantage",
    "quantified_outcomes": "Quantified outcomes (hard numbers)",
    "technical_rigor": "Rigorous, technical founders",
    "proactive_posture": "Proactive, not reactive, approach",
    "founder_first": "Founder they want to back early",
    "distributed_systems": "Distributed-systems depth",
    "security_native_team": "Security-native team / DNA",
    "social_impact_objective": "A measurable social-impact objective",
    "international_market_path": "A path to international markets",
    "unit_economics": "Unit economics from day one",
    "embedded_finance": "Embedded finance ('every company is fintech')",
    "regulated_market": "Comfort operating in regulated markets",
    "operator_dna": "Operator-built, hands-on company building",
    "applied_ai": "AI-first (AI is the product, not a feature)",
    "domain_expertise": "Deep domain expertise as the moat",
    "clinical_evidence": "Robust clinical evidence",
    "reimbursement_path": "A clear reimbursement path",
    "cost_competitive": "Cost-competitive without subsidies",
    "hard_science": "Deep science / hard-tech depth",
    "decarbonization_impact": "Measurable CO2 impact",
    "efficacy_outcomes": "Proven learning outcomes",
    "product_led_growth": "Product-led growth",
    "distribution_advantage": "Network effects / distribution advantage",
    "dual_use_defense": "Dual-use / defense demand",
    # sector
    "soc_detection": "Detection / SOC / threat intel",
    "ai_security": "AI security",
    "cloud_infra": "Cloud / infrastructure",
    "enterprise": "Enterprise buyers",
    "devops_observability": "DevOps / observability",
    "data": "Data platforms",
    "hardware_industrial": "Hardware / industrial",
    # stage
    "pre_seed": "Pre-seed",
    "seed": "Seed",
    "early_stage": "Early stage (seed / A)",
    "series_a": "Series A",
    "growth": "Growth",
    # geo
    "israel": "Israel",
    "us": "United States",
    "europe": "Europe",
    "mena": "MENA",
}

# (regex, family, tag). Patterns run case-insensitive against the joined recon text.
# Ordered roughly headline-first; every row's tag MUST exist in TAG_VOCAB.
_RAW_PHRASE_MAP = [
    # --- stage ---
    (r"\bseed\b", "stage", "seed"),
    (r"pre-?seed", "stage", "pre_seed"),
    (r"series a|seed\s*/\s*a|early[- ]stage|inception", "stage", "early_stage"),
    (r"\bgrowth\b", "stage", "growth"),
    # --- geo ---
    (r"israel|israeli|tel aviv|haifa", "geo", "israel"),
    (r"west bank|palestin|gaza", "geo", "mena"),
    (r"\buk\b|london|britain|united kingdom|europe", "geo", "europe"),
    # --- sector ---
    (r"detection|\bsoc\b|threat intel|alert fatigue", "sector", "soc_detection"),
    (r"ai security|ai-native|ai soc|agentic security|ai-for-enterprise|ai security", "sector", "ai_security"),
    (r"\bcloud\b|cnapp|infra\b|infrastructure", "sector", "cloud_infra"),
    (r"enterprise", "sector", "enterprise"),
    (r"devops|observability", "sector", "devops_observability"),
    (r"data infrastructure|data infra|data platform|data-driven", "sector", "data"),
    (r"hardware|manufacturing|industrial", "sector", "hardware_industrial"),
    # --- wants (the headline family) ---
    (r"agentic", "wants", "agentic_ai"),
    (r"ai-native|ai security|ai soc|ai relevance", "wants", "ai_native"),
    (r"autonomous", "wants", "autonomous_systems"),
    (r"proprietary data|proprietary|data flywheel|data moat", "wants", "proprietary_data"),
    (r"ai-first|ai eats software|application layer|ai-native workflow|essential (for|to) (the )?product|work outcome|sells outcome|services.{0,8}software", "wants", "applied_ai"),
    (r"domain expertise|vertical.{0,10}moat|domain-specific", "wants", "domain_expertise"),
    (r"clinical evidence|clinical robustness|clinical validation|clinical trial|rigorously demonstrat|evidence base", "wants", "clinical_evidence"),
    (r"reimbursement|payer|evidence pathway", "wants", "reimbursement_path"),
    (r"cost parity|economically viable|make real money|cost today|paying deployment|cost-competitive", "wants", "cost_competitive"),
    (r"deep-tech|deep tech|hardware-heavy|deep science|scientific expertise|hard science|hard tech", "wants", "hard_science"),
    (r"carbon removal|slashing.{0,12}emission|decarboniz|greenhouse gas|co2 impact|measurable co2", "wants", "decarbonization_impact"),
    (r"learning outcome|efficacy|return on education|improving learning|measurable.{0,15}learning", "wants", "efficacy_outcomes"),
    (r"product-led|product led growth|\bplg\b|self-serve", "wants", "product_led_growth"),
    (r"network effect|growth loop|virality|go-to-market|\bgtm\b|distribution advantage", "wants", "distribution_advantage"),
    (r"dual-use|dual use|defense|defence|national security", "wants", "dual_use_defense"),
    (r"quantified|false positive|95-99|reduction|outcomes", "wants", "quantified_outcomes"),
    (r"rigorous", "wants", "technical_rigor"),
    (r"proactive", "wants", "proactive_posture"),
    (r"seeking founders|help founders|advise|founder to advise|ideating|founder is the most|founder-first|bet on the founder", "wants", "founder_first"),
    (r"unit economic", "wants", "unit_economics"),
    (r"embedded finance|every company.{0,20}fintech|everything is fintech|vertical saas", "wants", "embedded_finance"),
    (r"regulated|compliance|licens", "wants", "regulated_market"),
    (r"operator|company-build|company build|build it themselves|hands-on", "wants", "operator_dna"),
    (r"distributed systems", "wants", "distributed_systems"),
    (r"security-native|security native|cyber-only|security-only|security specialist|security-focused|security-native|company builder", "wants", "security_native_team"),
    (r"social objective|social impact|revitaliz|creating jobs|coexistence|empowerment|empowering", "wants", "social_impact_objective"),
    (r"international market|access.{0,15}international|global market|accessing international", "wants", "international_market_path"),
]

# Compile once. Each entry: (compiled_regex, family, tag).
PHRASE_MAP = [(re.compile(pat, re.I), family, tag) for pat, family, tag in _RAW_PHRASE_MAP]


def all_tags():
    """Flat set of every valid tag across all families (for the validator)."""
    return {t for fam in TAG_VOCAB.values() for t in fam}


def self_check():
    """Fail loudly if a PHRASE_MAP row points at a tag not in TAG_VOCAB, or a
    rankable tag has no label. Called by the test and by --self-check."""
    problems = []
    for _, family, tag in PHRASE_MAP:
        if family not in TAG_VOCAB:
            problems.append(f"unknown family {family!r}")
        elif tag not in TAG_VOCAB[family]:
            problems.append(f"tag {tag!r} not in TAG_VOCAB[{family!r}]")
        if tag not in TAG_LABELS:
            problems.append(f"tag {tag!r} has no TAG_LABELS entry")
    return problems


if __name__ == "__main__":
    issues = self_check()
    if issues:
        for i in issues:
            print("VOCAB ERROR:", i)
        raise SystemExit(1)
    print(f"vocab OK: {len(PHRASE_MAP)} phrase rules, {len(all_tags())} tags")
