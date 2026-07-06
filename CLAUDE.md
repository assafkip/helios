# CLAUDE.md — The Signal (VC Investment Feed)

Standalone VC-signal feed. A Python monitor pulls RSS and writes `signals-data.json`;
`index.html` renders it. Pure RSS — no LinkedIn, X, or Apify. No backend.

## The one rule

`signals-data.json` has exactly one writer: `scripts/live_monitor.py`. Never
hand-edit it. To change what shows up, edit the `data/*.json` source lists and re-run.

## Do NOT reintroduce social scraping

This repo is intentionally pure RSS. Do not add LinkedIn/X scraping, Apify actors,
or browser automation. If a source is only reachable via a social platform, find its
RSS equivalent or leave it out.

## Common tasks

- **Add/remove a source** → edit `data/vc_watchlist.json`,
  `data/cyber_media_voices.json`, or `data/industry_sources.json`, then
  `python scripts/live_monitor.py --verbose`.
- **Dry run** → `--dry-run`.
- **Change hard/soft classification** → the keyword tables at the top of
  `scripts/live_monitor.py` (HARD_SIGNAL_KEYWORDS, SOFT_SIGNAL_KEYWORDS, PRIORITY_KEYWORDS).
- **Change the dashboard** → `index.html` is self-contained (inline CSS/JS).

## Data contract (index.html depends on these fields)

`person_name`, `firm`, `signal_type` (hard|soft), `signal_category`, `summary`,
`excerpt`, `source_url`, `source_type`, `source_date` (YYYY-MM-DD), `confidence`.
If you rename any of these in the engine, update `index.html` too.

## Known behavior

Industry sources (publications) fill `person_name` with the outlet name and `firm`
with the source type (e.g. "The Hacker News — news"). That is intentional — those
are outlet-attributed market signals, not a named partner. Filter by the "All firms"
dropdown to focus on named VC partners.

## Automation

`.github/workflows/monitor.yml` runs hourly and commits `signals-data.json` if it
changed. Deploy target is Vercel (static, redeploys on push). No secrets required.
