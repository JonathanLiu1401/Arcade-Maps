# Handoff: Arcade Maps overhaul (wip-overhaul branch)

Written 2026-07-28 ~07:25 JST for continuation in a remote Claude Code session.
Working branch: `wip-overhaul`. `main` still serves the last shipped v1 site on
GitHub Pages (safe). Merge to `main` ONLY after the remaining work below is done
and verified; Pages deploys from main root.

## State: what is DONE and verified on this branch

Data (all verified by adversarial audit agents):
- data/arcades.json: 13,681 arcades, 68 countries. Includes: romanization-aware
  cross-source dedupe (191 merges, e.g. ZIv "Amipara Kokojya" + official
  アミパラここじゃ店 = one entry, scrapers/name_match.py), geo_validate.py
  (source-aware bad-pin rejection: official=trust address, community=trust
  coords), China city-centroid approx placement (5,735 entries approx:true,
  jitter <=600m, scrapers/china_place.py + data/china_cities.json), counts_src
  honesty tags (bemanicn=true quantities; ziv kept only when any count>=2;
  placeholder all-1s dropped).
- data/enrichment.json (keyed by arcade id): transport text, hours, prices,
  game_prices/versions, image URLs, fav_count. bemanicn fields fully populate
  on the NEXT weekly crawl (parsers proven live; current file has partial).
- data/fx_rates.json: USD base, 17 currencies (frankfurter + open.er-api fill).
- mymaps/ rebuilt KMZ/CSV incl. game_counts column. Weekly Action
  (.github/workflows/update-data.yml) covers all sources + fx.

Frontend (modules js/: state, format, mapcore, markers, search, panel,
settings, nearby, app-init - LOAD-BEARING script order in index.html, markers.js
captures AM.format/AM.map at parse time, do NOT reorder):
- Done + e2e-verified by agents: smooth fractional zoom (SmoothWheelZoom
  vendored), place panel (Google-Maps-style IA, dark neon, mobile bottom
  sheet), settings modal (source toggles live-update, localStorage
  am_settings_v1), omnibox (games/arcades/places groups, CJK+romaji aliases),
  nearby+locate (haversine top-20), search halo highlight, hash deep links
  incl #arcade=, CJK tooltip nowrap fix, panel width 1.3x + drag-resize
  (280px..55vw, dblclick reset, persisted), cab-photo fallback chain
  (enrichment image -> assets/cabs/<game>.jpg + CC attribution overlay ->
  gradient), enrichment rows (transit w/ staleness caption, prices + 4-currency
  FX), counts-honesty chips (bemanicn "x9" / ziv "x7 listed" / plain chip +
  "counts unavailable" row), critical #arcade=% URIError boot fix +
  shareUrl encode, fitSheet resize listener, focus a11y fixes, mobile fixes
  (initial fitBounds view, collapsible footer, 44px targets, 320px overflow,
  anchored settings dialog, chips grid, empty-state hint).

Assets ready on disk:
- assets/markers/tier{1,2,3,4,5,U}.svg + marker-spec.md: 6 kawaii tier icons
  (SEGA-promo style, original art; T1 1-2 note, T2 3-9 pad, T3 10-19 star,
  T4 20-49 cat-ear chibi, T5 50+ crowned idol, TU unknown "?"; currentColor
  tints the disc, faces fixed-palette). Proof sheet verified at 20px.
- assets/cabs/: 17 CC-licensed cabinet photos + manifest.json + ATTRIBUTION.md
  (ongeki, drs missing on Commons - manifest records file:null; panel already
  handles). Attribution rendering is a LICENSE REQUIREMENT (CC BY/BY-SA).
- assets/favicon.svg + favicon.ico (root) + favicon-snippet.html: 8-dot ring
  favicon, hand-hinted 16px. SNIPPET NOT YET MERGED into index.html.

## REMAINING WORK (in order)

1. TIER ICON WIRING (the one unfinished feature; an agent thrashed on it, was
   killed; a fresh attempt was also stopped for shutdown - partial edits MAY
   exist in js/markers.js, git diff it first):
   - markers.js: tier from summed game_counts when counts_src trustworthy
     (bemanicn or ziv), else TU. Render: pre-rasterize 6 SVGs x 19 game colors
     to cached dataURLs via canvas at boot (string-replace currentColor with
     hex), L.icon markers (sizes/anchors per marker-spec.md). markerScaling
     false -> uniform TU-size. Spiderfy: spiderfyOnMaxZoom true + REMOVE
     disableClusteringAtZoom; verify lone-marker single-click still opens
     panel. Remap clusterHasBig to tier>=4 (currently keys on dead xl/xxl ids
     = silently broken). Legends (settings.js About + legend chip) must render
     the actual tier SVGs from an exported TIER_CLASSES, kill hard-coded size
     lists, keep gold-ring row + honesty caption.
   - Merge assets/favicon-snippet.html into index.html head (ico LAST rel=icon
     per snippet comment; REMOVE old inline data-URI icon line).
2. QA pass (desktop 1600x900 + mobile 390x844, Playwright, zero console):
   cold load, tier icons crisp at Tokyo z16, spiderfy stacked pair, panel photo
   chain 3 levels + attribution visible, FX row, counts chips, drag-resize,
   share round-trip, #arcade=% boots, omnibox groups, source toggles, locate,
   legend chip, tooltip GiGO神楽坂 horizontal, mobile sheet + footer.
3. README hero screenshot refresh (docs/screenshot.png) once icons live.
4. work-checker suite (user requested full run): code critics (XSS on scraped
   strings via innerHTML, listener leaks, hash codec, state-bus discipline)
   + data recompute + rasterized screenshot review. Fix confirmed, re-verify.
5. Housekeeping before merge: delete or gitignore .design-review/ (49
   screenshots, untracked), delete assets/cabs/_mgr_proof.png, check no stray
   test files at root.
6. Merge wip-overhaul -> main, push, verify live site + mobile viewport, run
   Actions smoke (workflow_dispatch) to confirm runner health.

## Known issues / decisions on record
- Design-review P2 polish items deliberately deferred (ragged chip wrap partly
  fixed, XXL legend swatch gap, etc. - see workflow reports in session).
- ongeki + drs cab photos unavailable under free licenses; gradient fallback.
- bemanicn coordinates are login-walled; user offered their login via their
  own Chrome earlier (never executed); China stays city-approx until then.
- ZIv x1 counts are placeholders, by policy never rendered as numbers.
- Owner style refs: SEGA otoge promo banners (markers), Google Maps place
  panel (IA only, original visuals), Claude desktop settings modal.
- NO EM DASHES anywhere (user hard rule; PS 5.1 ANSI decode breaks scripts).
- Mobile is P0: owner uses the site primarily on a phone.

## Environment notes for the remote session
- Site is plain static files, no build step; python -m http.server to serve.
- Scrapers stdlib-only Python 3.12+; run_all.py --skip-scrape re-merges
  without network; full crawl ~50 min (bemanicn 0.5s politeness).
- GitHub: repo JonathanLiu1401/Arcade-Maps, Pages from main root, gh CLI
  authed locally (remote session needs its own auth or the repo-local
  credential helper).
