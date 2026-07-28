# Data sources

Deep per-source reference for the Arcade Maps scrapers: exact URL patterns, response formats, parse markers, zero-result detection, politeness settings, and the caveats discovered during live scraping. Facts marked "approximate" change over time or are configured in the scraper source; check the scraper code for the canonical current values.

Cross-cutting rules:

- **Politeness:** every scraper sleeps after each request (0.4 s by default, `DEFAULT_SLEEP` in `scrapers/common.py`) and retries at most 3 times with exponential backoff. Requests are sequential, never parallel fan-out against a single host. The shared User-Agent is currently a fixed desktop-browser string (`common.USER_AGENT`); switching to a project-identifying UA is desirable but untested against the eagate WAF.
- **Coordinate systems:** SEGA ALL.Net, Konami eagate, and ZIv coordinates are WGS-84 (Google-Maps-derived or community-pinned on OSM-style maps) and are used as-is. Anything geocoded through Tencent/AMap for China is GCJ-02 and is converted with vendored eviltransform (`gcj2wgs_exact`); Baidu-derived points would need `bd2wgs`. `outOfChina` guards against double-converting non-China points. City centroids in `data/china_cities.json` are stored already converted to WGS-84 (see section 8).
- **Coordinate sanity:** longitudes are wrapped into [-180, 180] (some sources emit values outside that range). The `(0, 0)` coordinate pair is treated as a sentinel for "no real coordinates" and such stores are dropped from the map layer (kept in the address-only data), never plotted at Null Island.
- **Geo validation:** after merge, `scrapers/geo_validate.py` checks every coordinated entry against country bounding boxes. Official sources (allnet / eagate / wahlap, and address-trusting rows without community pins) null out-of-country geocodes; community sources (ziv / round1usa / community) correct a wrong country label from the pin when the pin falls cleanly in another country box.
- **Enrichment split:** optional per-arcade extras land in `data/enrichment.json` keyed by merged arcade id, not in `data/arcades.json`. The shipped file today carries four ZIv fields only (opening hours, venue info text, website, per-machine prices); transit prose, photos, and the other BemaniCN fields are parsed by the pipeline but are not populated in it. See section 10 and `scrapers/enrich.py`.

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

**Machine counts:** no - the locator lists stores per game but never how many machines a store has, so ALL.Net entries carry no `game_counts`.

**Enrichment:** none structured. Official JP locators expose name/address/coords only (no cost-per-play, no store photo gallery).

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

**Machine counts:** no - the facility search lists stores per game with no per-store machine counts, so eagate entries carry no `game_counts`.

**Enrichment:** access / tel / hours exist on the HTML but are not currently persisted into `enrichment.json`. No structured price or photo fields (verified live).

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

**Caveat: NO coordinates.** The REST payload is addresses only. Stores ship address-only into merge; `china_place` then assigns city-centroid coordinates with `approx: true` when a city key resolves (see section 8 and the README China accuracy disclosure). Optional commercial geocoding (e.g. Tencent) is not used.

**Volume (at last refresh, from `data/stats.json`):** 3,207 merged source rows under `wahlap` (maimai DX CN + CHUNITHM CN combined after within-source handling).

**Machine counts:** no - the REST payload is store name/address/province only, no per-store machine counts, so wahlap entries carry no `game_counts`.

**Enrichment:** none (no price, photo, or transit fields on the REST payload).

**Note:** WAHLAP's public HTML map page (`wc.wahlap.net/maidx/location/index.html`) is JS-rendered; prior art drives it with Selenium, but the REST endpoints above make that unnecessary.

---

## 4. Zenius-I-Vanisher community DB

Community-maintained worldwide arcade database, strongest for Bemani and for games with no surviving official locator.

**URL pattern (JSON API; `scrapers/ziv.py`):**

```
https://zenius-i-vanisher.com/api/arcades.php?action=query&country={NAME}&skip_pictures=1&skip_visitors=1&skip_comments=1
```

- One request per country, with country names spelled **exactly** as ZIv spells them (`ZIV_COUNTRIES` in `scrapers/run_all.py`; **65 entries** are queried today, where the sentinel `"USA"` triggers the per-series United States fetch under the real name `"United States"`).
- The United States is too large for a single country query (the unsegmented query returns HTTP 500) and is fetched per rhythm-game series (`&country=United States&series_id={ID}`) and merged by arcade id. The series ids are `USA_SERIES` (which doubles as the seriesID -> slug map) plus `USA_EXTRA_SERIES` in `scrapers/ziv.py` - Pump It Up, In The Groove, Guitar Hero Arcade, StepManiaX, Beat Saber and StepMania. Those extra series are US-fetch-only and are deliberately NOT slug mappings: their machines still resolve to `other` and are never counted in `game_counts`. Other countries need no equivalent because their whole-country query already returns those venues.

### Country-name trap (loud)

**A country name ZIv does not recognize returns `{"arcades": [], "success": true}` - HTTP 200, empty, no error.**

This is the most dangerous silent-dropout in the whole pipeline. Spelling the United States as `USA` (or any other non-ZIv spelling) makes the whole US set return zero rows while the rest of the crawl looks healthy. Live incident 2026-07-27: that exact mistake dropped ~1,250 US arcades. `scrape_all` now **hard-fails** on any country returning 0 arcades. Probe a new country name live before adding it, or the guard will abort the pipeline. Known-unsupported: `Panama` (no accepted spelling found; a handful of Panama arcades can still enter via geo_validation country fixes on mislabeled ZIv pins).

### Response format and machine mapping

JSON; each arcade carries an id, name, address parts (address / city / state / postalcode), latitude / longitude, an info text, and a machine list whose entries hold a nested `game` object (`{name, seriesID, genre, ...}`). Machines are mapped to canonical game slugs primarily by `game.seriesID` (`USA_SERIES` in `scrapers/ziv.py`), falling back to name-substring patterns; unrecognized machines map to `other`.

**Machine counts:** yes - each arcade's machine list is tallied per mapped slug into `game_counts` (one machine list entry = one machine; cabs that only map to `other` are not counted).

**Coverage:** 65 country queries returned ZIv arcades at the last pull; **6,953** merged source rows under `ziv` in `data/stats.json`. Includes Taiko no Tatsujin and offline cabs of retired games (Project DIVA Arcade, MUSECA, REFLEC BEAT, DanceEvolution).

### Enrichment fields (ZIv)

With the default skip flags, **pricing and venue fields still arrive** (verified 2026-07-27 on a Philippines query: only `pictures` / `comments` / `visitors` are stripped). The scraper maps:

| Raw / derived field | Enrichment key | Notes |
|---|---|---|
| machine `displayPrice` / `pricing` / numeric `price` / `freePlay` | `machine_prices` `{slug: text}` | Free-text preferred when present |
| venue `website` | `website` | |
| `openingTimes` (7-day Mon-first arrays) | `hours_text` | Rendered `Mon 10:00-21:00; ...`; days whose open and close times are identical are dropped, see below |
| `information` | `info_text` | HTML-stripped free text |
| `pictures[].absolutePath` | `images` (max 3) | Only when crawl drops `skip_pictures` (`--enrich` mode); default weekly crawl skips pictures for payload size |
| scrape date | `enriched_at` | ISO date on the raw row / enrichment entry |

These land in `data/enrichment.json` via `scrapers/enrich.py`, not in `arcades.json`. Images are the exception: the default weekly crawl keeps `skip_pictures=1`, so no picture URLs reach the shipped file.

**Opening-hours trap:** a day whose open and close times are identical is ZIv's "nobody recorded this" default, not a real 24-hour day. The API hands back `["00:00", "00:00", false]` for all seven days of an unrecorded venue, and `"00:00"` is a truthy string, so a plain truthiness test published `Mon-Sun 00:00-00:00` as if it were real hours. `scrapers/ziv.py` now rejects any zero-length day when rendering `hours_text`, and `_clean_hours_text` in `scrapers/enrich.py` re-checks the formatted string so rows already sitting in `data_raw/` are cleaned too. A string with no parseable `HH:MM-HH:MM` range is passed through untouched rather than guessed at. Effect on the rebuilt file: `hours_text` fell from 6,955 to 5,211 entries, and 432 entries whose only field was that string were dropped entirely.

### Other caveats

- **No structured closed flag.** ZIv does not mark closed arcades in a machine-readable field, so heuristics over the name and info text (e.g. "CLOSED", "permanently closed", 閉店 markers the community writes in) are used to filter dead venues. Expect both false positives and false negatives.
- Coordinates are community-pinned: usually good, occasionally hand-placed on the wrong building.
- Some longitudes arrive outside [-180, 180] and are wrapped (see cross-cutting rules).
- ZIv also publishes a ready-made KML (`https://zenius-i-vanisher.com/v5.2/arcade_locations.kml`); the scraper uses the JSON API instead because it exposes per-arcade machine lists and cleaner address fields.

---

## 5. Round1 USA (Storepoint API)

Round1's US store locator is a Storepoint (storepoint.co) embed; Storepoint exposes a JSON locations API for the embed's account id (pattern `https://api.storepoint.co/v1/{ACCOUNT_ID}/locations`; the account id is in the scraper config).

**Response format:** JSON list of locations with names, addresses, and coordinates.

**Caveat: standard lineup assumption.** Round1 does not publish per-store cab lists, so every US Round1 location is tagged with the chain's standard rhythm game lineup rather than a verified per-store inventory. Individual stores can deviate (missing cabs, extra cabs, out-of-order machines).

**Machine counts:** no - Round1 publishes no per-store machine data at all, so round1usa entries carry no `game_counts`.

**Enrichment:** Storepoint may expose phone/hours/tags in the full API; the scraper currently keeps the standard lineup note only (full field list not exhaustively verified).

**Current build:** there is no `data_raw/round1usa.json` in the tree, so the 59 `round1usa` arcades in `data/arcades.json` still come from the bundled `community.json` rows, not from a fresh scrape (see section 7).

---

## 6. BemaniCN community map (map.bemanicn.com)

Community-maintained map of rhythm game locations in mainland China; the richest community source for China (maimai DX, CHUNITHM, Taiko, plus the wider Bemani lineup with per-store game lists). Scraper: `scrapers/bemanicn.py`.

**Recipe (public Inertia.js JSON endpoints, verified live):**

1. `GET https://map.bemanicn.com/api/miniapp/common/region` -> plain JSON `{"data": {"provinces": {code: name}, "cities": {code: name}}}`; 392 city codes, a city's province is the code sharing its 2-digit prefix.
2. Per city: `GET https://map.bemanicn.com/region/city/{code}` with headers `X-Inertia: true`, `X-Inertia-Version: ""`, `X-Inertia-Partial-Component: Region/City`, `X-Inertia-Partial-Data: city` -> `props.city.shops` = `[{id, name, address, ...}]`.
3. Per shop: `GET https://map.bemanicn.com/s/{id}` with `X-Inertia-Partial-Component: Shop/Show`, `X-Inertia-Partial-Data: shop` -> `props.shop.arcades` = `[{title_id, quantity, version, coin, ...}]` plus shop-level fields below.
4. Title-id map (from the site's `/games` Inertia props, `TITLE_GAME` in the scraper): 1 maimai DX, 3 CHUNITHM, 27 ONGEKI, 4 SDVX, 5 IIDX, 11 DDR, 8/9 GITADORA, 6 and 34 jubeat, 12 pop'n, 7 Nostalgia, 10 DANCERUSH, 29 DANCE aROUND, 31 and 15 Taiko; every other title maps to `other` with the site's own title name recorded in notes.

**Politeness:** 0.5 s sleep after every request, sequential fetching, 3 retries with exponential backoff, the shared desktop Chrome UA. A full crawl is roughly 1 + 392 + ~3,800 requests; keep it weekly.

**Machine counts:** yes - each shop's `arcades[]` entries carry a per-title `quantity`; quantities are summed per mapped slug into `game_counts` (titles that map to `other` are not counted). At the last re-crawl, **~93.8%** of raw BemaniCN rows carried a non-empty `game_counts` (3,576 / 3,812). Merged source rows under `bemanicn` in stats: **3,802**.

### Enrichment fields (BemaniCN)

Optional shop/detail fields (all omitted when the payload does not carry them; see `shop_enrichment` in `scrapers/bemanicn.py` and research notes in `docs/research/enrichment-sources.md`):

| Shop / arcade field | Enrichment key | Notes |
|---|---|---|
| `transport` | `transport` | Public-transit directions prose (HTML-stripped) |
| `price` | `price_text` | Venue token/coin unit price (free text, often CNY/token) |
| `pay_type` | `pay_type` | Payment-mode enum (kept raw; not fully reverse-documented) |
| `start_time` / `end_time` | `hours` | Integers; `>24` means next day (e.g. 10/26 -> `10:00-02:00 (+1d)`) |
| `image_thumb.url` | `images` (via `image_thumb` on the raw row) | **Signed OSS URL** with `e=` expiry; re-resolve weekly; clients must tolerate 403 |
| `fav_count` | `fav_count` | Community favourites count, **not** a star rating |
| `arcades[].coin` (+ venue price) | `game_prices` `{slug: text}` | e.g. `5 coins/play (~CNY 5.00)` when both parse |
| `arcades[].version` | `game_versions` `{slug: text}` | e.g. `舞萌DX2025` |
| scrape date | `enriched_at` | ISO date |

`shop.comment` (long HTML: membership packs, QQ groups, photo rules) is deliberately **not** emitted into enrichment (large, mostly social prose).

**Not populated today.** The committed `data_raw/china_bemanicn.json` rows carry name, address, games, notes, and `game_counts` only (coordinates are null, see the login-only caveat below), so none of the fields above reach `data/enrichment.json`: the counts block reports `bemanicn_rows_contributed: 0` against `bemanicn_rows_available: 3,812`, and every field in the shipped file is tagged `ziv`. The parsers stay in place for a re-crawl that collects shop details; until then, treat this table as the pipeline's capability, not as data on disk.

**Staleness:** every enrichment entry carries `enriched_at` (ISO date of the crawl/build). Prices, hours, transit prose, and signed thumbs go stale; treat them as community data that may be outdated. Thumbs expire independently of `enriched_at` when the OSS signature lapses.

**Caveat: coordinates are login-only.** The map layers / API routes that carry lat/lng (e.g. `api/shared/dxmap`) 302-redirect to `/login`. The public endpoints above expose NO coordinates, so every row ships coordinate-less with `coord_system: "gcj02"` (anything this source ever produces would be GCJ-02 and must go through eviltransform). BemaniCN entries gain coordinates by (1) merging with WAHLAP or inheriting a ZIv pin, or (2) city-centroid approx placement in merge. See the `china_wahlap_bemanicn` rule in `scrapers/merge.py` and `scrapers/china_place.py`.

**Caveat: shop detail 404s.** A few shops listed in a city index have no detail page (404). They are kept, with games `["other"]` and a `detail page 404 (listed in city index only); games unknown` note.

**Caveat: em dashes in source data.** A few entries contain the site's own em dash character (U+2014) inside addresses (floor ranges written like "1F to 3F" with a long dash). They are source data and are kept verbatim in `data_raw/china_bemanicn.json` / `data/arcades.json` - the scraper only collapses whitespace and deliberately does not rewrite source punctuation (note this differs from `common.unescape`, which other scrapers use and which converts en/em dashes to hyphens).

---

## 7. Superseded `community.json` mechanics

`data_raw/community.json` is a committed historical bundle that carries rows from three sources at once (`ziv`, `round1usa`, and a few curated `community` entries). A fresh per-source scrape writes its own file instead: `data_raw/ziv.json` exists today, and `scrapers/round1usa.py` would write `data_raw/round1usa.json`, but that file is **not** in the tree, so the bundle is still the live source of the `round1usa` rows.

**Rule:** when a fresh file for a source exists, the merger **skips that source's rows inside `community.json`** and takes only the fresh file. The skip is keyed on the **row's** `source` field, not on the file name, so curated `community` rows (and any non-superseded sources still only present in the bundle) continue to load. The skip only engages when the fresh file actually exists, so a checkout without it still gets the bundled rows.

**Why it matters:** without the skip, ZIv would load twice. The same arcade is spelled differently between the old bundle and the live API (address parts joined differently), so the within-source dedupe key `(source, name, addr)` does not collapse them and ZIv would silently double. At the last merge, `community_rows_superseded` reported **4,682** `ziv` rows skipped from the bundle; the bundle's **59** `round1usa` rows were all loaded (no fresh file to supersede them), and live stats show only **6** pure `community` source rows remaining.

The superseded count is written to `data/merge_log.json` as `community_rows_superseded`.

---

## 8. `data/china_cities.json` (city centroids for approx placement)

Lookup table used by `scrapers/china_place.py` to place coordinate-less mainland China stores at city-level centroids.

| Item | Value |
|---|---|
| Path | `data/china_cities.json` |
| Shape | `{source, coord_system, conversion, cities: {name: [lat, lng]}}` |
| Keys | **1,009** name keys (full name + suffix-stripped forms, plus municipality districts and ethnonym-free aliases) |
| Unique centroids | **457** (about 458 prefecture-level places counting HK/Macau; dual keys share one point) |
| Stored coord system | **WGS-84** (`coord_system: "wgs84"`) |
| Upstream native system | **GCJ-02** |
| Conversion | `GCJ-02 -> WGS-84` via vendored `scrapers/eviltransform.py` `gcj2wgs()` at table build time |
| Upstream source | [xiangyuecn/AreaCity-JsSpider-StatsGov](https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov) release `2025.251231.260403`, file `ok_geo.csv` (deep 0/1/2 centroid column `geo`) |
| License | **MIT** (repository LICENSE, Copyright (c) 2019 xiangyuecn); ok_geo.csv marked free/open in the bundled data doc. Upstream administrative data compiled from 国家地名信息库, 腾讯地图行政区划, and 高德地图行政区划 |
| Taiwan | **Absent.** Upstream ships no coordinates for Taiwan. `china_place` hard-skips anything labeled Taiwan so street names like `中山路` / `北屯路` never false-match mainland `中山市` / `北屯市` |

**Caveat (from the table's own `source.caveat`):** short keys such as `中山` / `东城` / `和平` / `北屯` also occur as street and district names elsewhere. A bare longest-substring match over the whole country mis-places roughly 0.4% of rows. `china_place` therefore applies a province-consistency guard and prefers BemaniCN `region:` notes over address substring matches.

**Approx semantics:** placed entries get real-looking `lat`/`lng` plus `approx: true`. Fan-out jitter is cosmetic only. Addresses remain the authoritative location for navigation.

---

## 9. FX rates (`data/fx_rates.json`)

Weekly USD-base rates for converting displayed local prices.

| Item | Value |
|---|---|
| Primary | [Frankfurter](https://api.frankfurter.app/latest?from=USD) (ECB-derived, **keyless**, verified live) |
| Fallback / gap-fill | [open.er-api.com](https://open.er-api.com/v6/latest/USD) (keyless; used for codes Frankfurter omits, e.g. TWD and VND, or full primary failure) |
| Module | `scrapers/fx.py` |
| Currencies | **Required** (the run fails and keeps the previous file if any is missing): USD base plus JPY, HKD, CNY, PHP, TWD, KRW, SGD, MYR, THB, VND, IDR, AUD, NZD, GBP, EUR, CAD. **Best-effort** (omitted from the file if neither feed publishes them, which is not an error): MOP, MXN, BRL. The set to keep in sync with is `js/panel.js` `CUR_TOKENS`, the price parser's token table, not `js/format.js` `CURRENCY_SYMBOL`: any code the parser can read off a scraped price needs a rate or that price renders with no USD equivalent |
| Shape | `{base, date, rates, source, sources, fetched_at}` with per-code `sources` map (`frankfurter` / `open.er-api.com` / `base`) |
| Failure mode | **Non-fatal.** If both feeds fail (or required rates remain missing), the previous `fx_rates.json` is left in place and the step exits 0 so the weekly Action can still commit arcade data |

Do not treat FX as a redistribution-grade rates API; it is a weekly display helper baked into this static site.

---

## 10. Enrichment file (`data/enrichment.json`)

Built inside merge after ids are assigned (`enrich.build_enrichment`). Join key: merged `links.bemanicn` / `links.ziv` URLs, which are the raw rows' `source_url` values.

```
{
  "updated": "YYYY-MM-DD",
  "price_defaults": {ISO2: {currency, display, notes, typical, source, as_of}},
  "country_to_code": {"Japan": "JP", ...},
  "counts": {arcades_enriched, of_total, by_field, bemanicn_rows_*, ziv_rows_*},
  "arcades": {"<merged id>": {transport, price_text, pay_type, hours, hours_text,
                               images, fav_count, game_prices, game_versions,
                               machine_prices, website, info_text, sources, enriched_at}}
}
```

Only arcades with at least one enrichable field get an entry. Country price defaults always carry `typical: true` and are display fallbacks, never quoted guarantees. Frontend price priority: ZIv `machine_prices` > BemaniCN `game_prices` / `price_text` > country defaults.

**What the shipped file actually contains.** The key list above is the full set the builder can emit, not the set on disk. The current `data/enrichment.json` holds **6,521** entries against **13,532** arcades, and exactly four data fields, all tagged `ziv`: `hours_text` (5,211), `info_text` (4,207), `website` (4,092), `machine_prices` (2,413), plus the per-entry `sources` and `enriched_at` metadata. There is no `transport`, `images`, `fav_count`, `game_prices`, `game_versions`, `pay_type`, `price_text`, or `hours` in it, because `bemanicn_rows_contributed` is **0** (see section 6).

---

## Refresh pipeline

All sources are re-scraped by a single GitHub Action: weekly cron, Monday 18:00 UTC, plus `workflow_dispatch` for manual runs. The job runs with `permissions: contents: write`, commits changed files under `data/`, `data_raw/`, and `mymaps/` with a bot identity, and skips the commit when nothing changed. Arcade scrapers fail-fast (one broken source blocks the commit). FX is the exception: total feed failure keeps the previous rates file and does not fail the job. Both scrape targets (location.am-all.net, p.eagate.573.jp) are empirically reachable from GitHub-hosted US runners as of July 2026.
