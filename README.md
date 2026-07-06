# The Signal — VC Investment Feed

A live read on who is funding, hiring, and talking in cybersecurity. Pulls VC-partner
and media RSS feeds every hour, classifies each item as a hard signal (fund/deal/
actively-looking) or a soft signal (thesis/commentary), and renders a light editorial
digest.

Self-contained. No backend, no database, no social scraping. A Python monitor writes
one JSON file; a static HTML page reads it. Deploys as a static site.

## What it does

- Fetches RSS from the VC watchlist, cyber media voices, and industry sources
  (`data/*.json`).
- Detects **hard signals** (new fund raised, new security investment, actively
  looking, new thesis) and **soft signals** (trend commentary, SOC pain, detection
  engineering, threat intel, portfolio wins).
- Attributes each signal to a person + firm, keeps a 30-day window, deduplicates.
- Writes everything to `signals-data.json` (the dashboard's only data source).

Pure RSS. There is no LinkedIn, X/Twitter, or Apify dependency — the feed is built
entirely from public RSS and Reddit archive endpoints.

## Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Pull feeds and write signals-data.json
.venv/bin/python scripts/live_monitor.py --verbose

# Preview the dashboard
python3 -m http.server 8000
# open http://localhost:8000
```

Dry run (fetch and print, write nothing):

```bash
.venv/bin/python scripts/live_monitor.py --dry-run
```

## How it stays fresh

`.github/workflows/monitor.yml` runs the monitor every hour on the hour
(cron `0 * * * *`), commits `signals-data.json` if it changed, and pushes. On
Vercel, that push triggers a redeploy. Also runnable by hand from the Actions tab.

## Deploy (Vercel)

1. Push this repo to GitHub.
2. Import it in Vercel as a static project (no build command, output = repo root).
3. Vercel serves `index.html` and redeploys on every hourly commit.

No environment variables are required.

## Layout

| Path | Purpose |
|------|---------|
| `scripts/live_monitor.py` | The engine. Fetches RSS, classifies signals, writes JSON. |
| `scripts/cleanup_old_signals.py` | Optional: prune signals past the window. |
| `scripts/test_reddit_collector.py` | Test for the Reddit-archive path. |
| `data/vc_watchlist.json` | VC partners + their feeds. |
| `data/cyber_media_voices.json` | Media voices + their feeds. |
| `data/industry_sources.json` | Publications, press, conferences, funding news. |
| `data/monitor_state.json` | Run state. Auto-written. |
| `signals-data.json` | The feed the dashboard reads. Auto-written. |
| `index.html` | The dashboard (self-contained). |
| `.github/workflows/monitor.yml` | Hourly automation. |

## Add or remove sources

Edit the relevant `data/*.json`. A watchlist entry:

```json
{
  "person_name": "Ed Sim",
  "firm": "Boldstart Ventures",
  "rss_feeds": ["https://example.com/feed.xml"]
}
```

The next run picks it up.

## Optional: pipeline contact matching

If a `data/outreach-tracker.json` exists (`{"contacts":[{"person_name","firm","status","tier"}]}`),
the monitor tags matching signals with those contacts so the data can flag which
signals touch a name you already track. Absent by default; the feature no-ops
without the file.

## Signal schema (what the dashboard reads)

`signals-data.json` is a flat array. Fields used by the dashboard:
`person_name`, `firm`, `signal_type` (hard|soft), `signal_category`, `summary`,
`excerpt`, `source_url`, `source_type`, `source_date`, `confidence`.
