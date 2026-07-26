# Data sources

Deep per-source reference for the Arcade Maps scrapers: exact URL patterns, response formats, parse markers, zero-result detection, politeness settings, and the caveats discovered during live scraping. Facts marked "approximate" change over time or are configured in the scraper source; check the scraper code for the canonical current values.

Cross-cutting rules:

- **Politeness:** every scraper sleeps after each request (0.4 s by default, `DEFAULT_SLEEP` in `scrapers/common.py`) and retries at most 3 times with exponential backoff. Requests are sequential, never parallel fan-out against a single host. The shared User-Agent is currently a fixed desktop-browser string (`common.USER_AGENT`); switching to a project-identifying UA is desirable but untested against the eagate WAF.
- **Coordinate systems:** SEGA ALL.Net, Konami eagate, and ZIv coordinates are WGS-84 (Google-Maps-derived or community-pinned on OSM-style maps) and are used as-is. Anything geocoded through Tencent/AMap for China is GCJ-02 and is converted with vendored eviltransform (`gcj2wgs_exact`); Baidu-derived points would need `bd2wgs`. `outOfChina` guards against double-converting non-China points.
- **Coordinate sanity:** longitudes are wrapped into [-180, 180] (some sources emit values outside that range). The `(0, 0)` coordinate pair is treated as a sentinel for "no real coordinates" and such stores are dropped from the map layer (kept in the address-only data), never plotted at Null Island.

---

## 1. SEGA ALL.Net (location.am-all.net)

Official SEGA location search backing maimai DX, CHUNITHM, ONGEKI, and Project DIVA Arcade.

**URL patterns:**

```
Japan:         https://location.am-all.net/alm/location?gm={GAME_ID}&lang=ja&ct=1000&at={0..46}
International: https://location.am-all.net/alm/location?gm={GAME_ID}&lang=en&ct={1000..1015}
```

- `gm` game ids: 96 = maimai DX (Japan), 98 = maimai DX International, 109 = CHUNITHM (Japan), 104 = CHUNITHM International, 88 = ONGEKI, 34 = Project DIVA Arcade
- Japan: `ct=1000` with `at=0..46` (one request per prefecture, `lang=ja`)
- International: one request per `ct` code 1000..1015 with `lang=en`; ct=1000 is Japan's code and returns no international list, leaving 15 international codes (14 returned stores at the last pull)

**Caveat (live verification):** `ct=1000` is REQUIRED for Japan queries. Omitting `ct` returns the interactive landing/search form instead of a result list, which parses as zero stores. The scraper treats "page contains the search form and no result list" as a malformed query, distinct from a genuine zero-result page.

**Response format:** server-rendered HTML list.

**Parse markers:**

- Store name: `<span class="store_name">`
- Address: `<span class="store_address">`
- Coordinates: regexed from the Google Maps link/button onclick, pattern `@{lat},{lng}` (e.g. `//maps.google.com/maps?q=...@35.6,139.7`); on `lang=en` pages the button class is `store_bt_google_map_en`
- Stable store id: `sid=` parameter inside the details button onclick (`bt_details_en` on English pages)

**Zero-result marker:** a valid result page with zero `store_name` spans. CHUNITHM US currently returns zero official locations this way (that is real, not a scraper bug).

**Known data quirks:** a handful of stores carry wrong or `(0,0)` official coordinates (prior-art scrapers keep hardcoded override lists for ~10 such stores); the `(0,0)` sentinel rule above applies.

---

## 2. Konami eagate facility search (p.eagate.573.jp)

Official Konami facility search for Bemani titles.

**URL pattern:**

```
https://p.eagate.573.jp/game/facility/search/p/list.html?finder=area&gkey={GKEY}&pref=JP-{01..47}&paselif=false&page={N}
```

- Entry page (per game): `https://p.eagate.573.jp/game/facility/search/p/index.html?gkey={GKEY}`. Note `/search/p/location.html` is a 404; `list.html` is the real endpoint.
- Iterate all 47 prefectures `JP-01`..`JP-47` with pagination.

**Cookie required:** `facility_dspcount=50` (sets 50 results per page; without it you page through tiny result sets).

**Game keys:** 20 gkeys are scraped: IIDX, SDVX, DDR, GITADORAGF, GITADORADM, JUBEAT, pop'n (PMSP), Nostalgia, DANCERUSH (DAN), DANCE aROUND, Polaris Chord (`PLRS`), MUSECA, REFLEC BEAT (`REFLECC`), DanceEvolution (`DANEVOAC`), and cab-variant keys: `SDVX_VM` (SOUND VOLTEX Valkyrie model), `IIDX_LN` (IIDX Lightning model; note the key is `IIDX_LN`, not `IIDX_LM`), `DDR20TH` (DDR gold cab), plus Arena (`GITADORAGFA` / `GITADORADMA`) and Pikapika (`PMPM`) variant keys. The canonical 20-key list is `GKEYS` in `scrapers/eagate.py`.

**Caveat (live verification):** as scraped today, the `SDVX` base key returns the same store count as the `SDVX_VM` Valkyrie key, i.e. the base key currently reports Valkyrie cabinets only rather than a superset. Treat base-vs-variant counts with suspicion and prefer the union.

**Coverage caveat (live verification): JAPAN ONLY.** The facility search exposes no overseas listings. Overseas Konami cabs enter the dataset only via Zenius-I-Vanisher and the Round1 lineup assumption.

**Response format:** server-rendered HTML list.

**Parse markers:**

- Coordinates come directly from `data-latitude` / `data-longitude` attributes on each facility element (no geocoding needed)
- Name, address, access, and hours are in the facility list item markup

**Zero-result marker:** the text 店舗が見つかりませんでした on the list page means zero stores for that prefecture/gkey pair.

**Pagination caveat (live verification):** the server CLAMPS out-of-range `page` values and re-serves the last page instead of returning an empty list, so "fetch until no rows" would loop forever. The scraper stops when a page adds no new (name, address) pairs or when the advertised total ("N件の店舗が見つかりました") is reached, capped at 50 pages per prefecture.

**Infrastructure note:** eagate is fronted by an Imperva/Incapsula WAF-CDN. It is reachable from US IPs and GitHub-hosted runners as of July 2026, but keep polite pacing and an honest UA; WAF behavior can change without notice.

---

## 3. WAHLAP official REST (sega-register.wahlap.net)

WAHLAP operates SEGA rhythm games in mainland China and publishes store lists.

**URL patterns (verified; `ENDPOINTS` in `scrapers/wahlap.py`):**

```
https://sega-register.wahlap.net/api/sega/maidx/rest/location   (maimai DX CN)
https://sega-register.wahlap.net/api/sega/midtr/rest/location   (CHUNITHM CN)
```

Each returns HTTP 200 with a single JSON array (some deployments wrap it as `{"data": [...]}`; the scraper handles both).

**Response format:** JSON array. Fields per store include `arcadeName`, `address`, `province`, `placeId`, `id`.

**Caveat: NO coordinates.** The REST payload is addresses only. Stores are shipped address-only by default; optional geocoding (e.g. Tencent `https://apis.map.qq.com/ws/geocoder/v1/`, needs a key) returns GCJ-02 coordinates that MUST be converted with eviltransform `gcj2wgs_exact` before plotting on OSM tiles, or China points land 100-700 m off.

**Volume (at last refresh, approximate):** maimai DX CN 3125 stores, CHUNITHM CN 581.

**Note:** WAHLAP's public HTML map page (`wc.wahlap.net/maidx/location/index.html`) is JS-rendered; prior art drives it with Selenium, but the REST endpoints above make that unnecessary.

---

## 4. Zenius-I-Vanisher community DB

Community-maintained worldwide arcade database, strongest for Bemani and for games with no surviving official locator.

**URL pattern (JSON API; `scrapers/ziv.py`):**

```
https://zenius-i-vanisher.com/api/arcades.php?action=query&country={NAME}&skip_pictures=1&skip_visitors=1&skip_comments=1
```

- One request per country, with country names spelled exactly as ZIv spells them (`ZIV_COUNTRIES` in `scrapers/run_all.py`; 24 countries are queried today).
- USA is too large for a single country query and is fetched per rhythm-game series (`&country=USA&series_id={ID}`, ids in `USA_SERIES` in `scrapers/ziv.py`) and merged by arcade id.

**Response format:** JSON; each arcade carries an id, name, address parts (address / city / state / postalcode), latitude / longitude, an info text, and a cab (machine) list. Cab titles are mapped to canonical game slugs by substring patterns; unrecognized cabs map to `other`.

**Coverage:** 68 countries had ZIv-sourced arcades at the last pull (grows and shrinks with community edits; only queried countries can contribute). Includes Taiko no Tatsujin and offline cabs of retired games (Project DIVA Arcade, MUSECA, REFLEC BEAT, DanceEvolution).

**Caveats:**

- **No structured closed flag.** ZIv does not mark closed arcades in a machine-readable field, so heuristics over the name and info text (e.g. "CLOSED", "permanently closed", 閉店 markers the community writes in) are used to filter dead venues. Expect both false positives and false negatives.
- Coordinates are community-pinned: usually good, occasionally hand-placed on the wrong building.
- Some longitudes arrive outside [-180, 180] and are wrapped (see cross-cutting rules).
- ZIv also publishes a ready-made KML (`https://zenius-i-vanisher.com/v5.2/arcade_locations.kml`); the scraper uses the JSON API instead because it exposes per-arcade machine lists and cleaner address fields.

---

## 5. Round1 USA (Storepoint API)

Round1's US store locator is a Storepoint (storepoint.co) embed; Storepoint exposes a JSON locations API for the embed's account id (pattern `https://api.storepoint.co/v1/{ACCOUNT_ID}/locations`; the account id is in the scraper config).

**Response format:** JSON list of locations with names, addresses, and coordinates.

**Caveat: standard lineup assumption.** Round1 does not publish per-store cab lists, so every US Round1 location is tagged with the chain's standard rhythm game lineup rather than a verified per-store inventory. Individual stores can deviate (missing cabs, extra cabs, out-of-order machines).

---

## 6. BemaniCN community map (map.bemanicn.com)

Community-maintained map of rhythm game locations in mainland China; the richest community source for China (maimai DX, CHUNITHM, Taiko, plus the wider Bemani lineup with per-store game lists). Scraper: `scrapers/bemanicn.py`.

**Recipe (public Inertia.js JSON endpoints, verified live):**

1. `GET https://map.bemanicn.com/api/miniapp/common/region` -> plain JSON `{"data": {"provinces": {code: name}, "cities": {code: name}}}`; 392 city codes, a city's province is the code sharing its 2-digit prefix.
2. Per city: `GET https://map.bemanicn.com/region/city/{code}` with headers `X-Inertia: true`, `X-Inertia-Version: ""`, `X-Inertia-Partial-Component: Region/City`, `X-Inertia-Partial-Data: city` -> `props.city.shops` = `[{id, name, address, ...}]`.
3. Per shop: `GET https://map.bemanicn.com/s/{id}` with `X-Inertia-Partial-Component: Shop/Show`, `X-Inertia-Partial-Data: shop` -> `props.shop.arcades` = `[{title_id, quantity, version, ...}]`.
4. Title-id map (from the site's `/games` Inertia props, `TITLE_GAME` in the scraper): 1 maimai DX, 3 CHUNITHM, 27 ONGEKI, 4 SDVX, 5 IIDX, 11 DDR, 8/9 GITADORA, 6 and 34 jubeat, 12 pop'n, 7 Nostalgia, 10 DANCERUSH, 29 DANCE aROUND, 31 and 15 Taiko; every other title maps to `other` with the site's own title name recorded in notes.

**Politeness:** 0.5 s sleep after every request, sequential fetching, 3 retries with exponential backoff, the shared desktop Chrome UA. A full crawl is roughly 1 + 392 + ~3,800 requests; keep it weekly.

**Caveat: coordinates are login-only.** The map layers / API routes that carry lat/lng (e.g. `api/shared/dxmap`) 302-redirect to `/login`. The public endpoints above expose NO coordinates, so every row ships coordinate-less with `coord_system: "gcj02"` (anything this source ever produces would be GCJ-02 and must go through eviltransform). BemaniCN entries gain coordinates only by merging with the official WAHLAP list or inheriting from a matched ZIv pin (see the `china_wahlap_bemanicn` rule in `scrapers/merge.py` and the merge log).

**Caveat: shop detail 404s.** A few shops listed in a city index have no detail page (404). They are kept, with games `["other"]` and a `detail page 404 (listed in city index only); games unknown` note.

**Caveat: em dashes in source data.** 3 entries contain the site's own em dash character (U+2014) inside addresses (floor ranges written like "1F to 3F" with a long dash). They are source data and are kept verbatim in `data_raw/china_bemanicn.json` / `data/arcades.json` - the scraper only collapses whitespace and deliberately does not rewrite source punctuation (note this differs from `common.unescape`, which other scrapers use and which converts en/em dashes to hyphens).

---

## Refresh pipeline

All sources are re-scraped by a single GitHub Action: weekly cron, Monday 18:00 UTC, plus `workflow_dispatch` for manual runs. The job runs with `permissions: contents: write`, commits changed files under `data/`, `data_raw/`, and `mymaps/` with a bot identity, and skips the commit when nothing changed. Both scrape targets (location.am-all.net, p.eagate.573.jp) are empirically reachable from GitHub-hosted US runners as of July 2026.
