# FundVision — Design System (canonical)

The approved look. Adhere to this; do not drift back to the earlier dark-SaaS /
neon version. Origin: a teardown of https://earcouture.jp (cinematic light +
couture serif), translated to a data tool.

## Direction
Couture editorial, cinematic, calm. A luxury magazine that happens to be a live
market tool. Cream serif display over a static jewel-toned light; data on clean
dark. Refined, never neon, never boxy.

## Type
- **Display / serif:** Fraunces (Google Fonts). Used for the hero headline,
  market names, area names, the logo wordmark, investor names. Weight 300–500,
  italic for emphasis (e.g. "leaves a *trace*").
- **Body / UI:** Inter (`--sans`). Labels, controls, excerpts.
- **Data / numerals:** monospace (`--mono`). Counts, dates, meta, sparkline axes.

## Palette (tokens in `:root`)
- `--bg` #08080c (near-black)
- `--cream` #f3ecdd — serif display ink
- `--ink` #f5f5f8 / `--ink-dim` / `--ink-faint` — body/meta
- `--accent` **#6f8fca** (muted dusty blue) — interactive, chips, sparklines,
  "buzz/attention" data, hover lines. NOT electric/neon blue.
- `--hard` **#c9a86a** (champagne gold) — money: hard signals, investor names,
  "Moving today", top-investor, live dot, "funding" bars. Gold = capital.
- No lime, no electric blue, no purple. That neon register is banned here.

## The light (signature)
- Static volumetric prism: layered soft radial blobs, `lighter` composite, one
  frozen frame (`t = 8`, no `requestAnimationFrame`). **Movement was removed on
  purpose — it hurt legibility.**
- Colors: deep jewel tones (sapphire / steel / teal + a soft gold), NOT neon.
- **Hero-only:** the canvas is `position: absolute`, ~54vh tall, masked with a
  `linear-gradient` fade so it dies before the content. Everything below the hero
  sits on solid dark → fully legible. Never run animated/bright light behind text.

## Structure (one page)
- Cinematic hero (Fraunces manifesto over the light) → scroll into the tool.
- **Moving today · investors active right now** — VC-sourced highlights, gold
  serif names, freshest first, one per investor. The hook.
- **Editorial market index** — full-width rows, NO boxes: index number, big serif
  name, sparkline flowing across, rising term, this-week count, and a `→` arrow
  (click affordance). Luminous hover line. Click a row → drill in.
- **Drill (area) view** — big serif area name + faint spine word, top-investor
  pill, pulse (rising chips / deal heat / movers), **collapsible filter bar**
  (search + "Filters ▾" with active-count badge), date-grouped feed.
- **Cross-market intelligence** — "Rising across every market" (bars) and
  "Where the gap is · buzz vs funding" (per-market blue-vs-gold bars, ranked by
  the gap). Borderless.

## Principles (do / don't)
- **Do:** editorial rows + hairline luminous separators; cream serif display +
  clean mono/sans data; gold for money/investors; static light in the hero only;
  visible click affordances; collapsible/compact controls.
- **Don't:** boxes/cards with borders behind everything; neon colors; animated
  light behind text; a Feed/Trends tab split (it's one page); filter bars that
  hog the screen.

## Data credibility
- "Moving today" and "top investor" pull only `source_kind == "vc"` signals
  (real tracked investors), never media/industry. Engine tags every signal with
  `source_kind` (vc | media | industry).

Everything is one self-contained `index.html` (inline CSS/JS, no build). Fonts via
Google Fonts. Deploys static on Vercel.
