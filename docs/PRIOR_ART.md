# Arcade Maps - Prior Art Research Report

Date: 2026-07-27. Every claim below marked [verified] was confirmed by an actual fetch (curl, GitHub API via authenticated `gh`, raw.githubusercontent.com, or WebFetch) during this session. Anything not directly fetched is marked [unverified].

---

## 1. Existing scrapers

### 1.1 ALL.Net (location.am-all.net) scrapers

**A. bemusicscript/gcm-storefinder** - the closest single-repo prior art to our whole project. [verified]
- URL: https://github.com/bemusicscript/gcm-storefinder ; live site https://bemusicscript.github.io/gcm-storefinder/
- Language: Python (scraper) + static HTML/JS frontend. **License: NONE** (GitHub API spdx_id = null, no LICENSE file). Code cannot be legally reused, only studied.
- Activity: created 2021-09-22, **pushed 2026-07-26** (the day before this research), 10 stars, not archived. Actively maintained.
- What it parses (from `storemap.py`, fetched): requests `https://location.am-all.net/alm/location` with `gm=` game id (88 = Ongeki, 109/104 = CHUNITHM, 96/98 = maimai), `ct=`/`at=` region (0-46 = JP prefectures, 1000-1019 = countries), `lang=en` for non-JP. Parses with plain `re`: coordinates regexed out of the embedded `//maps.google.com/maps?q=...@lat,lng` links, addresses from `<span class="store_address">`. Hardcoded `UNKNOWN_LOCATION` override dict for ~10 stores with bad official coordinates. Writes `json/ongeki.json` etc. plus `json/duplicate.json` (stores present in multiple games). No rate limiting.
- Automation: `.github/workflows/crawler.yaml` (fetched) - weekly cron Sunday 17:00 UTC + workflow_dispatch, `permissions: contents: write`, concurrency guard, runs `storemap.py`, commits `json/` with bot credentials, skips commit when no changes.
- Frontend (index.html fetched): Leaflet 1.9.4 + Leaflet.markercluster 1.5.3 from unpkg, plus maplibre-gl 5.6.1 + @maplibre/maplibre-gl-leaflet 0.1.1 (vector basemap rendered under the Leaflet API), game layer toggles via dropdown.

**B. hker9527/otoge-locator** - closest prior art for the daily-cron + static-map architecture. [verified]
- URL: https://github.com/hker9527/otoge-locator
- Language: TypeScript on Bun; frontend is one static `index.html`. **License: NONE.** 2 stars.
- Description: "An interactive map with filtering to view all rhythm game cabinets' location in Japan, data update daily."
- Activity: pushed 2026-07-23; last 5 commits are all `github-actions[bot] "Update data"` daily (2026-07-19 through 2026-07-23) - the cron demonstrably works end to end.
- Scraper (`index.ts`, full source captured): fetches `https://location.am-all.net/alm/location?gm={88|96|109}&at={0..46}&ct=1000&lang=en`, parses with cheerio: name from `span.store_name`, address from `span.store_address`, lat/lng regexed (`/@([\d.]+),([\d.]+)/`) from the `onclick` of `button.store_bt_google_map_en`, stable store id from `sid=` in `button.bt_details_en` onclick. Writes `stores.json` (id-keyed) + `games.json` (per-game id arrays). Japan only; all requests fired concurrently via Promise.all (no rate limiting).
- Frontend (head fetched): Leaflet + Leaflet.markercluster + leaflet.locatecontrol + Leaflet.Icon.Glyph + Material Design Icons, all from jsdelivr, single `#map` full-screen page.
- Workflow (`.github/workflows/main.yml`, fetched verbatim - see section 5).

**C. djzmo/otoge-app** - the most complete multi-source scraper suite (the original otoge.app). [verified]
- URL: https://github.com/djzmo/otoge-app ; homepage https://otoge.app
- TypeScript monorepo (`packages/api`, `scripts`, `shared`, `web`). **License: NONE** (spdx none). Pushed 2025-08-11, 9 stars. Semi-dormant.
- `packages/scripts/src/FetchAllnet.ts` (fetched): base `https://location.am-all.net/alm/location` with `gm`, `lang=en`, `ct` (country), `at` (area). Game id mapping includes maimai DX (96), maimai DX International (98), CHUNITHM (58), CHUNITHM New (109), Ongeki (88), classic maimai (90). Handles 14 regions: JP, TW, HK, SG, MY, KR, TH, ID, MO, US, PH, VN, AU, MM, NZ (JP via `ct=1000` + per-area `at`; other countries one fetch each). Coordinates parsed from the Google Maps onclick `q` parameter (split on `@` and comma). Output grouped by country: storeName, address, lat, lng, cabinets, and `context` metadata (`allNetCt`, `allNetAt`, `allNetSid`). No rate limiting.
- Frontend: React + Chakra UI + `@react-google-maps/api` (Google Maps, not Leaflet) - not reusable for our stack, and unlicensed anyway.

Other ALL.Net hits from GitHub code search for `"location.am-all.net/alm/location"` (31 total, [verified] list): mlchanjc/chunithm-jp-map (TS, no license, 2024), Goatgarien/GekiChuMai-Shop-Locator (Python, **GPL-3.0**, pushed 2024-06-27, iterates every prefecture via the cab search), Admirable0531/maimaiStore, Eeezhi/maimai_map (Python, 2026-01), inonote/uni_locator (PHP), asaburodesu/chu_map, hker9527/otoge-locator, djzmo/otoge-app, bemusicscript/gcm-storefinder.

### 1.2 eagate (p.eagate.573.jp) facility search scrapers

**A. djzmo/otoge-app `FetchEAmusement.ts`** - the reference recipe. [verified]
- Exact URL pattern: `https://p.eagate.573.jp/game/facility/search/p/list.html?finder=area&gkey={gameId}&pref={pref}&page={currentPage}` iterating prefectures `JP-01`..`JP-47` with pagination.
- gkey values used: `DAN, DDR, DDR20TH, GITADORADM, GITADORAGF, IIDX, IIDX_LN, JUBEAT, MUSECA, PMSP, REFLECC, SDVX, SDVX_VM`.
- **Cookie required: `facility_dspcount=50`** (sets 50 results per page).
- Coordinates come directly from `data-latitude` / `data-longitude` HTML attributes - no geocoding needed. Output: name, address, access, hours, coordinates, cabinet info, plus original facility descriptor as `context`. No auth beyond the cookie; no rate limiting.
- I reproduced this recipe live from a US IP [verified]: `curl -b "facility_dspcount=50" "https://p.eagate.573.jp/game/facility/search/p/list.html?gkey=IIDX&paselif=false&pref=JP-13&finder=area"` returned 50 stores with `data-latitude="35.640433"` etc. The entry page is `https://p.eagate.573.jp/game/facility/search/p/index.html?gkey=IIDX` (200); note `/search/p/location.html` is a 404.
- Other eagate scrapers found via code search for `"eagate.573.jp/game/facility"` (11 hits) [verified list]: Goatgarien/e-amuse-shop-locator (Python), 6CE-TW/konami-arcade-scraper (Python, no license, pushed 2025-06-18, "A script to scrape KONAMI game center locations"), sweshelo/medusa (`src/service/scraping/prefecture-facilities.ts`), anon5r/amcrawler (PHP), ssdh233/geisen-map (`server/src/crawlers/bemaniCrawler.ts`).

### 1.3 map.bemanicn.com (China community map)

**Login wall confirmed.** [verified]
- `https://map.bemanicn.com/` is a Laravel app that embeds its entire route table in the homepage HTML via Ziggy. Extracted public API-shaped routes: `api/shared/dxmap`, `api/shared/chuni`, `api/shared/taiko`, `api/shared/shop/{shop}`, plus a WeChat mini-program API surface under `api/miniapp/...` (shop index/create/edit/checkin/review, common/region, ranking, auth/login, auth/bind), and web routes `dxmap`, `indmap`, `shop`, `arcade`, `map-bind/{type}/{orig_id}`, etc.
- However, **all of them 302-redirect to `https://map.bemanicn.com/login`**: tested `api/shared/dxmap`, `api/shared/chuni`, `api/shared/taiko`, and even the public map pages `/dxmap` and `/shop` (all 302 to /login). Scraping bemanicn requires an authenticated account session cookie; there is no anonymous API.
- No public GitHub project scrapes it directly. Code search for `"map.bemanicn.com"` returns 475 hits but they are almost all links/bookmarks. Notable: **Naptie/nearcade** (below) credits BEMANICN as its domestic-data source; passworked/rythem_arcade_distribute_map (HTML, no license, 2025-01, "maimai & chunithm map base on map.bemanicn.com", 0 stars, file layout fetch 404ed - [unverified] contents).

**Naptie/nearcade** - biggest licensed prior-art product. [verified]
- URL: https://github.com/Naptie/nearcade . **MPL-2.0**, 124 stars, pushed 2026-07-26 (active daily).
- What it is: a community platform ("NearArcade") for locating arcades + campus clubs + forums. Data sources per README: BEMANICN 全国音游地图 (domestic China), **Zenius-I-vanisher.com (international)**, Chinese Ministry of Education university list, Tencent Maps geocoding.
- Stack: SvelteKit + Svelte 5 + TypeScript + Tailwind 4 + daisyUI, MongoDB, Better Auth, Meilisearch, maps via Amap/Tencent/Google Maps. Requires Node 18+, MongoDB, map API keys, OAuth creds; Docker Compose deploy.
- Assessment: it is NOT the map we want to build - it is a server-backed community product (DB, auth, search cluster, commercial map SDKs with API keys), not a static GitHub Pages site, and it does not cover the SEGA/Konami official-source scraping loop. Reusable for us: MPL-2.0 permits file-level code reuse (copyleft applies per modified file); their BEMANICN/ZIv ingestion and China-coordinate handling code is worth reading before we write ours, and it proves BEMANICN data access is negotiable/possible. It also validates demand.

### 1.4 WAHLAP (China official)

- **JSON REST endpoint exists: `https://wc.wahlap.net/maidx/rest/location`** - [verified] returns HTTP 200 `application/json; charset=utf-8`. Fields (per Yuri-YuzuChaN/maimaiDX `core/arcade.py`, fetched): `id`, `arcadeName`, `address`, `province`, `mall`, `machineCount`. **No coordinates** - needs geocoding.
- The HTML page `https://wc.wahlap.net/maidx/location/index.html` (200 [verified]) is JS-rendered; starwey604/MaiMap-scrape (Python, no license, 2025-01, fetched source) drives it with headless Selenium and then geocodes addresses with the **Tencent geocoder** (`https://apis.map.qq.com/ws/geocoder/v1/`) - which returns **GCJ-02** coordinates (see section 4). Prefer the REST endpoint + geocoding over Selenium.
- Consumers of `wc.wahlap.net` on GitHub: 23 code hits [verified], mostly QQ-bot maimai plugins (Yuri-YuzuChaN/maimaiDX, 404MaximWang/astrbot_plugin_maimaidx, etc.).

### 1.5 Zenius-I-Vanisher

- **No scraper needed: ZIv publishes a ready-made KML** at `https://zenius-i-vanisher.com/v5.2/arcade_locations.kml` - [verified] HTTP 200, `<kml>` with Placemarks containing name, region, per-game table (game/condition/price) in HTML CDATA descriptions, generated "as of 2026-01-05". Parse with any KML/XML lib.
- **Andrew67/ddr-finder** family [verified via search + README result]: https://github.com/Andrew67/ddr-finder (PHP+MySQL API, **MIT**), ddr-finder-ng (web UI, live at https://ddrfinder.andrew67.com/), DdrFinder (Android). Aggregates ZIv + DDR-Navi + OSM. MIT and reusable, but it is an API server + DB, not a static site.

---

## 2. Existing open-source arcade map websites

| Project | Stack | Map lib | License | Status |
|---|---|---|---|---|
| bemusicscript/gcm-storefinder | Static HTML/JS + Python cron | Leaflet 1.9.4 + markercluster 1.5.3 (+ maplibre-gl-leaflet basemap) | none | active (2026-07-26) |
| hker9527/otoge-locator | Static single index.html + Bun cron | Leaflet + markercluster + locatecontrol | none | active (daily bot) |
| djzmo/otoge-app | React + Chakra, Node API | Google Maps | none | last push 2025-08 |
| fishuvn/maimap | Next.js 16 + SQLite | Google Maps (@vis.gl/react-google-maps) | **MIT** | seed data only (60 arcades), no scraping |
| Naptie/nearcade | SvelteKit + MongoDB | Amap/Tencent/Google | **MPL-2.0** | very active |
| Andrew67/ddr-finder(-ng) | PHP + MySQL API, web UI | Google Maps / Mapbox-style | **MIT** | live service |
| ssdh233/geisen-map | TS server + web (yarn monorepo, has bemaniCrawler.ts) | [unverified] | none | pushed 2026-02, 1 star |
| hureta-nuka/amusement-arcade-map | TypeScript, GitHub Pages (Polaris Chord stores) | Leaflet ([unverified] internals) | none | pushed 2026-04 |

Takeaways: the exact architecture we plan (static Leaflet + markercluster page on GitHub Pages, JSON data files committed by an Actions cron scraping ALL.Net) already exists twice (gcm-storefinder weekly, otoge-locator daily) and demonstrably works, **but both are unlicensed**, so we must write our own code (clean-room from the recipes above is fine; facts/protocols are not copyrightable). Nothing MIT/Apache exists that is directly liftable as a whole; MIT bits exist only in Google-Maps-based stacks.

---

## 3. Frontend stack verification

### 3a. Recommendation: Leaflet 1.9.4 + Leaflet.markercluster 1.5.3 (vendored, no build)

[verified from npm registry]: `leaflet` dist-tags: latest = **1.9.4** (published 2023-05-18); 2.x exists only as `2.0.0-alpha.1`. `leaflet.markercluster` latest = **1.5.3** (2021-10-18), which targets Leaflet 1.x.

Reasoning for Leaflet over maplibre-gl for this project:
- **No-build-step requirement**: both can be used as plain `<script>` tags, but Leaflet + markercluster is 2 small files; maplibre-gl is a much larger bundle (its dist JS is ~800 KB raw vs leaflet.js 147 KB + markercluster 34 KB raw, [verified sizes from downloads below]) and needs a vector style JSON + glyph/sprite hosting to be useful.
- **7k points**: Leaflet.markercluster handles this comfortably; enable `chunkedLoading: true` (its documented option for tens of thousands of markers). 7k is well inside its proven range. Per-game toggles map naturally to one `L.markerClusterGroup` per game plus `L.control.layers`.
- **Raster OSM tiles** (our free tile source) are Leaflet's native model; maplibre-gl's strength is vector tiles, which pulls in style hosting decisions (OpenFreeMap solves it, but adds moving parts).
- **Prior art convergence**: both working sister projects (gcm-storefinder, otoge-locator) chose exactly Leaflet + markercluster; gcm-storefinder only adds maplibre-gl-leaflet as an optional prettier basemap layer under the same Leaflet API - a pattern we can adopt later without rearchitecting.
- maplibre-gl + built-in GeoJSON `cluster: true` is a fine 2026 stack too (and clusters faster at 100k+ points), but its advantages do not bind at 7k points and it costs bundle size + style plumbing. Verdict: **Leaflet 1.9.4 + markercluster 1.5.3**.

### 3b. CDN-free vendoring plan (all URLs verified HTTP 200 on 2026-07-27)

Commit these under e.g. `site/vendor/`:

| File | Download URL | Size (bytes) |
|---|---|---|
| leaflet.js | https://unpkg.com/leaflet@1.9.4/dist/leaflet.js | 147,552 |
| leaflet.css | https://unpkg.com/leaflet@1.9.4/dist/leaflet.css | 14,806 |
| images/marker-icon.png | https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png | 1,466 |
| images/marker-icon-2x.png | https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png | 2,464 |
| images/marker-shadow.png | https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png | 618 |
| images/layers.png | https://unpkg.com/leaflet@1.9.4/dist/images/layers.png | 696 |
| images/layers-2x.png | https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png | 1,259 |
| leaflet.markercluster.js | https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js | 34,136 |
| MarkerCluster.css | https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css | 872 |
| MarkerCluster.Default.css | https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css | 1,287 |

Notes: the `images/` folder must sit next to leaflet.css (CSS references relative `images/`). Whole-package alternatives (also verified 200): `https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz` (869,361 B) and `https://registry.npmjs.org/leaflet.markercluster/-/leaflet.markercluster-1.5.3.tgz` (1,237,832 B). Optionally also grab `leaflet.js.map` / minified `-src` variants; not required.

### 3c. Tile layers

**OSM standard tiles - allowed for our use.** [verified from https://operations.osmfoundation.org/policies/tiles/]
- Normal interactive browsing by users of a modest-audience site is exactly the permitted use; capacity is donated, so requirements: clearly visible attribution ("Show OpenStreetMap licence attribution clearly on the map (typically bottom-right)"), valid Referer (do not suppress via Referrer-Policy), a distinctive User-Agent for apps, honor cache headers ("If your cache cannot read them, cache each tile for at least 7 days"), HTTPS `https://tile.openstreetmap.org/{z}/{x}/{y}.png` only. Forbidden: bulk/pre-emptive downloading, offline archives, no-cache directives. "Access may be blocked without prior notice."
- Standard config:

```js
const OSM = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
});
```

**Fallback constants:**
1. CARTO raster basemaps - technically open and working ([verified] `https://a.basemaps.cartocdn.com/light_all/3/4/3.png` and `https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png` both 200, no key), **but policy caveat**: CARTO's own FAQ (docs.carto.com/faqs/carto-basemaps, [verified]) now says commercial use needs an Enterprise license and free use is "by CARTO grantees" (grants program). The old "free non-commercial 75k views" wording is gone. Keep as a fallback constant with attribution `&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>`, accept it may require a (free, nonprofit) grant or removal if challenged.
2. OpenFreeMap - [verified from openfreemap.org]: completely free, **no API key, no registration, no limits** on views/requests, run by Zsolt Ero, donation-funded. Vector tiles for MapLibre (no raster endpoint), so this is the basemap to pair with the optional maplibre-gl-leaflet upgrade path (exactly what gcm-storefinder does). Required attribution: OpenMapTiles + OpenStreetMap ("OpenFreeMap" name optional).

---

## 4. GCJ-02 / BD-09 conversion

- **Standard tiny library: googollee/eviltransform** - https://github.com/googollee/eviltransform . [verified] 2,580 stars, last push 2024-01-15 (stable/finished, not abandoned-broken). Implementations in Go, C/C++/ObjC, JavaScript, Python, PHP, C#, Haskell, Java, MATLAB, Rust, Swift.
- **License**: BSD 2-Clause style (fetched LICENSE verbatim: "Copyright (c) 2015, Googol Lee ... Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met: 1. Redistributions of source code must retain the above copyright notice... 2. Redistributions in binary form must reproduce..."). GitHub's API reports spdx `NOASSERTION` because of the custom header, but the text is the standard BSD-2-Clause permission grant - safe to vendor with the notice retained.
- Functions ([verified] from `python/eviltransform/__init__.py` and `javascript/transform.js`): `outOfChina`, `transform`, `delta`, `wgs2gcj`, `gcj2wgs` (1-2 m accuracy), `gcj2wgs_exact` (<0.5 m, iterative), `distance`, `gcj2bd`, `bd2gcj`, `wgs2bd`, `bd2wgs`. The Python module is a single small file - vendor it directly.
- **Confirmation of the pipeline**: OSM tiles are WGS-84 (Web Mercator on WGS-84 datum). AMap/Tencent-sourced China coordinates (including anything geocoded through `apis.map.qq.com` - which is how MaiMap-scrape geocodes WAHLAP addresses) are GCJ-02 and will land offset by roughly 100-700 m on OSM unless converted with `gcj2wgs`/`gcj2wgs_exact`. Baidu-sourced coordinates are BD-09 and need `bd2wgs` (internally bd09 -> gcj02 -> wgs84; eviltransform exposes the one-shot `bd2wgs`). Coordinates scraped from SEGA/Konami official pages (Google-Maps-derived) and from ZIv KML are already WGS-84 - do not convert those. `outOfChina` guards against double-converting non-China points.

---

## 5. GitHub Actions: cron scraper + auto-commit

**Verified real-world example #1** - hker9527/otoge-locator `.github/workflows/main.yml`, fetched verbatim, proven working by daily bot commits:

```yaml
name: Update Locator data
on:
  workflow_dispatch:
  schedule:
    - cron: '1 14 * * *'
jobs:
  update:
    permissions:
      contents: write
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: oven-sh/setup-bun@v1
    - run: bun i
    - run: bun run index.ts
    - name: Commit and push changes
      continue-on-error: true
      run: |
        git config --global user.name 'github-actions[bot]'
        git config --global user.email 'github-actions[bot]@users.noreply.github.com'
        git add games.json stores.json
        git commit -m 'Update data'
        git push
```

**Verified real-world example #2** - gcm-storefinder `crawler.yaml` (fetched; summarized): weekly cron `Sunday 17:00 UTC` + workflow_dispatch, `permissions: contents: write`, concurrency group, checkout master, run `storemap.py`, bot-credential commit of `json/` with an explicit "skip if no changes" guard (cleaner than `continue-on-error`).

**Recommended minimal skeleton for us** (Python, merging the two verified patterns):

```yaml
name: Scrape arcade data
on:
  workflow_dispatch:
  schedule:
    - cron: '0 17 * * 0'   # weekly; ALL.Net data churn is low
permissions:
  contents: write
concurrency:
  group: scrape
  cancel-in-progress: false
jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: python scrape.py
      - name: Commit changes if any
        run: |
          git config user.name 'github-actions[bot]'
          git config user.email 'github-actions[bot]@users.noreply.github.com'
          git add data/
          git diff --cached --quiet || git commit -m "data: automated refresh $(date -u +%F)"
          git push
```

(The default `GITHUB_TOKEN` with `permissions: contents: write` is all that is needed; no PAT. `stefanzweifel/git-auto-commit-action` is the popular packaged alternative [unverified in this session]; the plain-git approach above is the one proven by both prior-art repos.)

**Geo-blocking from GitHub-hosted (US) runners - empirical evidence, both hosts reachable:**
- location.am-all.net: **proven reachable** - otoge-locator's daily cron on `ubuntu-latest` scrapes it and its bot committed fresh `stores.json` on 2026-07-19, 20, 21, 22, 23 [verified commit log].
- p.eagate.573.jp: **proven reachable** - public run log of tts1374/iidx_all_songs_master run 30170921377 (2026-07-25, ubuntu-latest) shows its connectivity-check step: `curl https://p.eagate.573.jp/...` returning `HTTP/1.1 200` with `http_code=200`, `remote_ip=45.60.12.131` (an Imperva/Incapsula edge, i.e. Konami fronts eagate with a WAF-CDN). Last 3 scheduled runs all `success` [verified].
- Caveats: the eagate evidence is for a `/game/infinitas/` page, not `/game/facility/`, and the very existence of that debug step suggests the author investigated flakiness at some point; Imperva WAF behavior can change per-path or rate-limit. My own US residential IP fetched the actual facility search with full data (50 stores, `data-latitude` present). Conclusion: no geo-blocking observed as of July 2026 for either host, but keep polite pacing (sleep between requests, honest User-Agent) and still do the planned empirical smoke test from a throwaway workflow before relying on it.

---

## 6. Google My Maps limits (from Google's own docs)

[verified from https://support.google.com/mymaps/answer/3024836 and https://support.google.com/mymaps/answer/3024933]:
- Supported import formats: **CSV, TSV, KML, KMZ, GPX, XLSX, Google Sheets** (plus photos from Drive/Photos).
- File size per import: **unzipped KML/KMZ up to 5 MB; other files up to 40 MB**.
- Rows per import: **"Do not import files with more than 2,000 rows"** (per layer import).
- Photos: up to 100 per import.
- Layers per map: **"Maps are created with one layer, but you can have up to 10."**
- Total features per map: a 10,000-features-per-map cap is widely cited in community answers but I could NOT find it in Google's current official docs - [unverified]. Practical planning number: 10 layers x 2,000 rows = 20,000 hard ceiling, with 2,000 per layer the binding constraint.
- **API: none.** There is no My Maps API for programmatic map/layer creation; import is manual/browser only. Workarounds are limited to generating KML/CSV files for hand-import, or abandoning My Maps for the Maps JavaScript API (verified by search of Google developer docs surface; Google's Maps Platform offers no My Maps endpoints - the closest historical product, Maps Engine API, was shut down years ago).
- Implication for Arcade Maps: ~7,000 markers fits in My Maps only if split into <=2,000-row per-game/per-region layers (max 10), refreshed by hand each time. Fine as a manual export target (we can emit per-game CSV/KML under 2,000 rows each), useless as an automated pipeline.

---

## 7. Recommendations distilled

1. Build our own scrapers; nothing reusable is suitably licensed. Clean-room from: gcm-storefinder/otoge-locator (ALL.Net recipe), otoge-app FetchEAmusement (eagate recipe: `list.html?finder=area&gkey=X&pref=JP-NN&page=N` + `facility_dspcount=50` cookie + `data-latitude`/`data-longitude`), WAHLAP REST JSON + geocoding, ZIv ready-made KML.
2. bemanicn requires an account session; either obtain cooperation (nearcade evidently did) or treat China coverage as WAHLAP-official + ZIv + manual, and add bemanicn later.
3. Static site: vendored Leaflet 1.9.4 + markercluster 1.5.3 (chunkedLoading), one cluster group per game + `L.control.layers`, OSM standard tiles with proper attribution/referer; CARTO raster and (via maplibre-gl-leaflet) OpenFreeMap vector as fallback constants.
4. Vendor eviltransform (BSD-2-Clause style) and convert only China points: Tencent/AMap-derived -> `gcj2wgs_exact`; Baidu-derived -> `bd2wgs`; guard with `outOfChina`.
5. Weekly cron with `permissions: contents: write` + plain git commit; both target hosts are empirically reachable from GitHub-hosted runners as of July 2026.
6. My Maps only as an optional manual export (per-game <=2,000-row CSV/KML files); no API exists.
