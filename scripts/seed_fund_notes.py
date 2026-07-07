#!/usr/bin/env python3
"""
One-shot recon seed: write cited thesis notes into the healthtech / climate /
edtech / marketing-ads / space-tech watchlists so derive_fund_criteria can tag
them. Idempotent — only sets thesis_alignment / notes / url / priority, preserves
rss_feeds and last_checked. Notes grounded in primary-source recon (2026-07-07);
market-voice entries are labelled as such and intentionally carry no thesis.

Run once: python3 scripts/seed_fund_notes.py
"""

import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"

# vertical -> person_name -> {url, priority, thesis, notes}
SEED = {
    "healthtech": {
        "Rock Health": {
            "url": "https://rockhealth.com/insights/assessing-the-clinical-robustness-of-digital-health-startups/",
            "priority": 1,
            "thesis": "Early-stage digital health with real clinical robustness.",
            "notes": "Digital-health research house and early-stage fund. Values robust clinical evidence: only ~20% of digital health carries real trials, and clinical claims are poorly correlated with evidence, so companies that rigorously demonstrate impact stand out. Tracks reimbursement and evidence pathways. Thesis that established distribution networks plus AI drive efficiency and scale.",
        },
        "Andreessen Horowitz (a16z / Future)": {
            "url": "https://a16z.com/bio-health/",
            "priority": 2,
            "thesis": "AI-enabled healthcare and bio, infrastructure to applications.",
            "notes": "Backs AI-enabled healthcare and bio across infrastructure and the application layer; AI-native clinical workflows.",
        },
        "Sequoia Capital": {
            "url": "https://sequoiacap.com/article/services-the-new-software/",
            "priority": 2,
            "thesis": "AI-native healthcare services, outcomes over software.",
            "notes": "Healthcare thesis follows its AI view: sell work outcomes, not software; values a proprietary data flywheel tied to a business metric and deep domain expertise.",
        },
        "Venrock": {
            "url": "https://www.venrock.com/",
            "priority": 1,
            "thesis": "Contrarian early-stage healthcare and biotech.",
            "notes": "Healthcare and biotech specialist. Backs companies with strong clinical evidence and a clear reimbursement path; contrarian, early-stage.",
        },
        "Christina Farr": {
            "url": "https://www.secondopinion.health/",
            "priority": 3,
            "thesis": "Digital-health writer and commentator, not a primary check-writer.",
            "notes": "Second Opinion. Digital-health market voice tracked for intelligence, not deal flow.",
        },
    },
    "climate": {
        "Lowercarbon Capital": {
            "url": "https://lowercarbon.com/",
            "priority": 1,
            "thesis": "Companies that make real money slashing and removing CO2.",
            "notes": "Chris and Crystal Sacca, ~$2.4B AUM. Backs companies that make real money slashing CO2 and removing carbon. Pragmatic: real-world unit economics, speed to deployment and measurable CO2 impact; wants cost today versus cost post-raise and the first paying deployments that stick. Leads deep-tech, hardware-heavy climate with in-house scientific expertise.",
        },
        "Jason Jacobs": {
            "url": "https://www.mcjcollective.com/",
            "priority": 2,
            "thesis": "Early-stage climate, community-driven, real deployment.",
            "notes": "MCJ Collective (My Climate Journey). Early-stage climate fund and community backing founders across climate; values real deployment and measurable decarbonization impact.",
        },
        "Sightline Climate (CTVC)": {
            "url": "https://sightlineclimate.com/",
            "priority": 3,
            "thesis": "Climate-tech research and intelligence, not a check-writer.",
            "notes": "CTVC. Climate-tech market intelligence voice tracked for signal, not deal flow.",
        },
        "Climate Drift": {
            "url": "https://www.climatedrift.com/",
            "priority": 3,
            "thesis": "Climate accelerator and community.",
            "notes": "Climate accelerator and community; early support and market voice.",
        },
        "Distilled": {
            "url": "https://www.distilledventures.com/",
            "priority": 3,
            "thesis": "Early-stage climate tech.",
            "notes": "Climate-tech, early-stage; light public thesis.",
        },
        "Climate Papa": {
            "url": "https://www.climatepapa.com/",
            "priority": 3,
            "thesis": "Climate media and community voice.",
            "notes": "Climate media and community voice tracked for signal, not deal flow.",
        },
    },
    "edtech": {
        "Reach Capital": {
            "url": "https://www.reachcapital.com/industries/learning/",
            "priority": 1,
            "thesis": "Early-stage learning, measurable learning outcomes.",
            "notes": "Early-stage edtech specialist (ClassDojo, Handshake). Moving beyond pure growth metrics to measurable learning outcomes; backs AI plus human creativity reshaping pedagogy, assessment and infrastructure, not tools that merely digitize the status quo.",
        },
        "GSV Ventures": {
            "url": "https://www.gsvventures.com/",
            "priority": 1,
            "thesis": "Pre-K to Gray lifelong learning, return on education.",
            "notes": "Edtech across K-12, higher ed and workforce. 'Pre-K to Gray' lifelong-learning thesis: scalable platforms, data-driven personalized learning and return on education (learning outcomes plus career readiness).",
        },
        "Alex Sarlin / Ben Kornell": {
            "url": "https://www.edtechinsiders.org/",
            "priority": 3,
            "thesis": "Edtech podcast and community, not a check-writer.",
            "notes": "Edtech Insiders. Market voice tracked for signal, not deal flow.",
        },
        "Michael B. Horn": {
            "url": "https://michaelbhorn.com/",
            "priority": 3,
            "thesis": "Education thinker (disruption / blended learning), adjacent.",
            "notes": "Education thinker on disruption and blended learning; adjacent voice, not a primary check-writer.",
        },
    },
    "marketing-ads": {
        "David Skok": {
            "url": "https://www.forentrepreneurs.com/saas-metrics-2/",
            "priority": 1,
            "thesis": "Metrics-driven, efficient SaaS growth.",
            "notes": "Matrix Partners / For Entrepreneurs. SaaS-metrics authority (CAC, LTV, unit economics). Values efficient, metrics-driven growth from the earliest stage.",
        },
        "Andrew Chen": {
            "url": "https://andrewchen.com/",
            "priority": 1,
            "thesis": "Network effects and product-led viral growth.",
            "notes": "a16z, author of The Cold Start Problem. Backs product-led, viral growth loops and network effects as the distribution advantage.",
        },
        "Lenny Rachitsky": {
            "url": "https://www.lennysnewsletter.com/",
            "priority": 2,
            "thesis": "Product-led growth, activation and retention.",
            "notes": "Lenny's Newsletter. Product and growth; values product-led growth and strong activation and retention metrics.",
        },
        "Andreessen Horowitz (a16z / Future)": {
            "url": "https://a16z.com/",
            "priority": 2,
            "thesis": "Consumer and growth; distribution and network effects.",
            "notes": "Backs consumer and growth companies built on distribution and network effects.",
        },
        "Rand Fishkin": {
            "url": "https://sparktoro.com/",
            "priority": 2,
            "thesis": "Audience-led organic distribution.",
            "notes": "SparkToro. Audience intelligence; values audience-led, organic distribution and is skeptical of paid-only growth.",
        },
        "Emily Kramer / Kathleen Estreich": {
            "url": "https://www.mkt1.co/",
            "priority": 2,
            "thesis": "Early-stage B2B, GTM- and marketing-led.",
            "notes": "MKT1. Early-stage B2B across AI, GTM tech and vertical software; backs an efficient, structured go-to-market as the edge.",
        },
        "Jason Lemkin": {
            "url": "https://www.saastr.com/",
            "priority": 2,
            "thesis": "SaaS metrics and product-led growth.",
            "notes": "SaaStr. Values product-led growth plus quantified revenue, retention and efficiency metrics.",
        },
        "Kyle Poyar": {
            "url": "https://www.growthunhinged.com/",
            "priority": 2,
            "thesis": "Product-led growth and monetization.",
            "notes": "Growth Unhinged / Tremont. Product-led-growth authority; backs PLG and pricing- and monetization-driven companies.",
        },
    },
    "space-tech": {
        "Space Capital": {
            "url": "https://www.spacecapital.com/",
            "priority": 1,
            "thesis": "Early-stage across the space value chain.",
            "notes": "Dedicated space-economy VC (Chad Anderson, $100M+). Early-stage across the space value chain: satellite infrastructure and space-enabled data platforms built on proprietary geospatial data.",
        },
        "Seraphim Space": {
            "url": "https://seraphim.vc/",
            "priority": 1,
            "thesis": "SpaceTech across defence, Earth observation and comms.",
            "notes": "London spacetech specialist. Targets defence and security, Earth observation, satellite communications, geospatial intelligence, orbital logistics and climate monitoring; spacetech as a dual-use capability. Deep-tech, hardware-heavy.",
        },
        "Founders Fund": {
            "url": "https://foundersfund.com/",
            "priority": 1,
            "thesis": "Launch systems, aerospace and defense space.",
            "notes": "Backs launch systems, aerospace engineering and defense space (SpaceX). Deep-tech, dual-use, ambitious technical founders.",
        },
        "Space Ambition": {
            "url": "https://www.spaceambition.org/",
            "priority": 3,
            "thesis": "Spacetech media and community voice.",
            "notes": "Spacetech media and community voice tracked for signal, not deal flow.",
        },
        "Ian Vorbach": {
            "url": "https://www.spacedotbiz.com/",
            "priority": 3,
            "thesis": "Space-economy analyst and newsletter.",
            "notes": "SpaceDotBiz. Space-economy analyst voice tracked for signal, not deal flow.",
        },
    },
}


def main():
    for vertical, funds in SEED.items():
        path = DATA / vertical / "vc_watchlist.json"
        data = json.load(open(path))
        records = data.get("watchlist") or data.get("vcs") or []
        by_name = {r.get("person_name"): r for r in records}
        touched = 0
        for name, fields in funds.items():
            r = by_name.get(name)
            if not r:
                print(f"  WARN {vertical}: no record named {name!r}")
                continue
            r["thesis_alignment"] = fields["thesis"]
            r["notes"] = fields["notes"]
            r["website_or_blog_url"] = fields["url"]
            r["priority"] = fields["priority"]
            touched += 1
        json.dump(data, open(path, "w"), indent=2)
        print(f"{vertical}: seeded {touched}/{len(records)} records")


if __name__ == "__main__":
    main()
