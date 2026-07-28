# Status: Arcade Maps overhaul

Started 2026-07-28 as a continuation brief for a remote session. That
continuation is done, so this file is now a status record rather than a task
list. It is a working document, not project documentation: the durable
material lives in `README.md` and `docs/ARCHITECTURE.md`, so this can be
deleted before merging to `main` without losing anything.

Branch: `claude/arcade-maps-overhaul-handoff-vgbp2h` (contains everything that
was on `wip-overhaul`, plus the work below). `main` still serves the last
shipped v1 site on GitHub Pages. Pages deploys from main root.

## Done and verified

Data:
- `data/arcades.json`: 13,621 arcades, 68 countries. Romanization-aware
  cross-source dedupe (191 merges, `scrapers/name_match.py`), `geo_validate.py`
  source-aware bad-pin rejection, China city-centroid approx placement (5,735
  entries `approx: true`, `scrapers/china_place.py`), `counts_src` honesty tags.
- `data/enrichment.json`: 6,522 entries, four fields only - `hours_text`
  (5,212), `info_text` (4,208), `website` (4,092), `machine_prices` (2,414).
  Every row is ZIv-sourced. The BemaniCN parsers exist and are proven, but no
  BemaniCN row has landed in the shipped file yet, so transit prose, coin
  pricing, images, `fav_count`, `game_prices` and `game_versions` are NOT
  shipped data. Earlier revisions of this file and of the README claimed
  otherwise; that has been corrected.
- `data/fx_rates.json`: USD base, 17 currencies.
- `mymaps/` KMZ/CSV layers incl. game_counts. Weekly Action covers all sources.

Frontend (modules in `js/`, LOAD-BEARING script order in `index.html` - see the
load-order invariant in `docs/ARCHITECTURE.md` before touching it):
smooth fractional zoom, place panel, settings modal, omnibox, nearby + locate,
search halo, hash deep links incl. `#arcade=`, panel drag-resize, cab-photo
fallback chain with CC attribution, enrichment rows, counts-honesty chips,
mobile fixes.

Tier marker icons, wired this session:
- Six silhouettes by total cabinets: T1 1-2, T2 3-9, T3 10-19, T4 20-49,
  T5 50+, TU unknown, at 20/24/26/30/36px with TU 25px. Shape carries the tier;
  the size ramp only reinforces it, and the Display toggle flattens sizes to
  25px without changing shapes.
- A tier is computed only when `counts_src` is trusted (`bemanicn`, or `ziv`
  where the merge kept a real quantity). Everything else is TU.
- `L.marker` + `L.icon` over per-(tier, colour) SVG data URLs. Artwork is
  generated into `js/tier-icons.js` by `tools/build_tier_icons.py`; edit the
  SVGs under `assets/markers/` and re-run, never the generated file.
- Clustering at every zoom with the radius collapsing to 14px up close, plus
  `spiderfyOnMaxZoom`, so stores sharing a building are reachable.
- Both legends render the real artwork from the exported tier table.

Also fixed this session:
- Opening hours: ZIv's `["00:00","00:00",false]` "not recorded" default was
  being published as `Mon-Sun 00:00-00:00` on 1,742 arcades. Rejected at the
  source and re-checked in `enrich.py`; data regenerated.
- Hover tooltip collapsed to a one-word-wide vertical column (a Leaflet
  tooltip's containing block resolves to 0px, so `white-space: normal` fell
  back to min-content). Fixed with `width: max-content`.
- `util.safeUrl` on every scraped link that reaches an `href`.
- Four listener/timer defects: omnibox debounce reopening after a pick,
  `keepInView` arming a `moveend` that had already fired under reduced motion,
  an untracked chip-flash timer, and `applyingHash` without `try/finally`.

## Open items

- README hero screenshot (`docs/screenshot.png`) still shows the old circle
  markers. It could not be refreshed remotely: that environment's egress policy
  blocks `tile.openstreetmap.org`, so every screenshot taken there has a blank
  basemap. Needs one capture from a machine that can reach OSM tiles.
- Hover behaviour was verified by shimming `matchMedia`, because headless
  Chromium reports `(hover: none)`. Worth one look in a real desktop browser.
- BemaniCN coordinates remain login-walled, so China stays city-approx.
- `ongeki` and `drs` cabinet photos are unavailable under free licences; the
  panel falls back to a gradient.
- Two unmerged duplicate pairs survive, both ZIv-only and both understood:
  #1139/#6224 (same Beijing store, romaji vs hanzi, identical coordinates) and
  #11628/#11629 (both "Hollywood Bowl Ashford", 47.1 m apart, just outside
  `merge.py`'s 30 m same-source window). Left alone on purpose: loosening that
  window or the same-source name rule to catch two pairs risks over-merging
  genuinely distinct neighbours across 13,621 entries, and that needs a full
  re-run with a dedupe audit rather than a threshold nudge.
- `.design-review/` blobs remain in git history from the earlier checkpoint
  commit even though the directory is gone from the tree. Reclaiming the 26 MB
  needs a history rewrite, which is not worth doing to a shared branch.

## Decisions on record

- Counts honesty: never render a number the source did not actually publish.
  ZIv all-1s rows are placeholders and are dropped; unknown counts get their
  own marker at mid weight, never the smallest.
- Owner style refs: SEGA otoge promo banners (markers), Google Maps place panel
  (information architecture only, original visuals), Claude desktop settings
  modal.
- NO EM DASHES anywhere (hard rule: PowerShell 5.1 ANSI decode breaks scripts).
- Mobile is P0: the site is used primarily on a phone.

## Environment notes

- Plain static files, no build step. `python3 -m http.server` to serve.
- Scrapers are stdlib-only Python 3.12+. `run_all.py --skip-scrape` re-merges
  without network; a full crawl is about 50 minutes.
- GitHub Pages serves from main root, so asset paths must stay relative.
