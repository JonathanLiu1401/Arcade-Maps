# Data sources

Deep per-source reference for the Arcade Maps scrapers: exact URL patterns, response formats, parse markers, zero-result detection, politeness settings, and the caveats discovered during live scraping. Facts marked "approximate" change over time or are configured in the scraper source; check the scraper code for the canonical current values.

Cross-cutting rules:

- **Politeness:** every scraper sleeps after each request (0.4 s by default, `DEFAULT_SLEEP` in `scrapers/common.py`) and retries at most 3 times with exponential backoff. Requests are sequential, never parallel fan-out against a single host. The shared User-Agent is currently a fixed desktop-browser string (`common.USER_AGENT`); switching to a project-identifying UA is desirable but untested against the eagate WAF.
- **Coordinate systems:** SEGA ALL.Net, Konami eagate, and ZIv coordinates are WGS-84 (Google-Maps-derived or community-pinned on OSM-style maps) and are used as-is. Anything geocoded through Tencent/AMap for China is GCJ-02 and is converted with vendored eviltransform (`gcj2wgs_exact`); Baidu answers are BD-09 (and arrive as Mercator metres times 100) and go through `bd2wgs`. Google is GCJ-02 too **for mainland-China locations only**, which is the trap that ships every Chinese pin 100-700 m off if you assume it speaks WGS-84 everywhere. `outOfChina` guards against double-converting non-China points. `data/china_areas.json` and `data/china_geocode.json` are both stored already converted to WGS-84 (see sections 8 and 8c).
- **Coordinate sanity:** longitudes are wrapped into [-180, 180] (some sources emit values outside that range). The `(0, 0)` coordinate pair is treated as a sentinel for "no real coordinates" and such stores are dropped from the map layer (kept in the address-only data), never plotted at Null Island.
- **Geo validation:** after merge, `scrapers/geo_validate.py` checks every coordinated entry against country bounding boxes. Official sources (allnet / eagate / wahlap, and address-trusting rows without community pins) null out-of-country geocodes; community sources (ziv / round1usa / community) correct a wrong country label from the pin when the pin falls cleanly in another country box.
- **Enrichment split:** optional per-arcade extras land in `data/enrichment.json` keyed by merged arcade id, not in `data/arcades.json`. The shipped file carries four ZIv text fields (opening hours, venue info text, website, per-machine prices), venue photos from three sources, and a measured price table derived from those quoted prices. Transit prose and the remaining BemaniCN fields are parsed by the pipeline but are still not populated in it. See sections 10 and 11 and `scrapers/enrich.py`.
- **Photos are out of band.** No photo source is part of `run_all.py`. `photos.py`, `chain_photos.py`, `bemanicn_photos.py` and `photo_quality.py` are manual crawls that write committed artefacts under `data_raw/` (and `assets/venues/` for the mirrored bytes); the weekly build only reads them. See section 11.

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

**Caveat: NO coordinates.** The REST payload is addresses only. Stores ship address-only into merge, which places them from the committed geocode cache where the address resolved (`approx_level: "address"`) and from an administrative centroid otherwise (see sections 8 and 8c, and the README China accuracy disclosure). Either way the row keeps `approx: true`: a POI search answers with a building, not necessarily the right one.

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
- The United States is too large for a single country query (the unsegmented query returns HTTP 500) and is fetched per rhythm-game series (`&country=United States&series_id={ID}`) and merged by arcade id. The series ids are `USA_SERIES` (which doubles as the seriesID -> slug map) plus `USA_EXTRA_SERIES` in `scrapers/ziv.py` - Pump It Up, In The Groove, Guitar Hero Arcade, StepManiaX, Beat Saber and StepMania. `USA_EXTRA_SERIES` controls only WHICH series the US crawl fetches, not how their machines are slugged: Pump It Up and StepManiaX now have canonical slugs of their own (as do WACCA, Groove Coaster, crossbeats and BeatStream, which arrive through ordinary country queries), while In The Groove, Guitar Hero Arcade, Beat Saber and StepMania still resolve to `other` and are never counted in `game_counts`. Other countries need no equivalent because their whole-country query already returns those venues.

### Country-name trap (loud)

**A country name ZIv does not recognize returns `{"arcades": [], "success": true}` - HTTP 200, empty, no error.**

This is the most dangerous silent-dropout in the whole pipeline. Spelling the United States as `USA` (or any other non-ZIv spelling) makes the whole US set return zero rows while the rest of the crawl looks healthy. Live incident 2026-07-27: that exact mistake dropped ~1,250 US arcades. `scrape_all` now **hard-fails** on any country returning 0 arcades. Probe a new country name live before adding it, or the guard will abort the pipeline. Known-unsupported: `Panama` (no accepted spelling found; a handful of Panama arcades can still enter via geo_validation country fixes on mislabeled ZIv pins).

### Response format and machine mapping

JSON; each arcade carries an id, name, address parts (address / city / state / postalcode), latitude / longitude, an info text, and a machine list whose entries hold a nested `game` object (`{name, seriesID, genre, ...}`). Machines are mapped to canonical game slugs primarily by `game.seriesID` (`USA_SERIES` in `scrapers/ziv.py`), falling back to name-substring patterns; unrecognized machines map to `other`.

**Machine counts:** yes, and each one is now labelled with the evidence behind it rather than published bare. Three classes reach `count_evidence` (see the schema in `docs/ARCHITECTURE.md`):

| Evidence | What it is | How it renders |
|---|---|---|
| `ziv_listed` | the number of machine ROWS the listing enumerates | a FLOOR, not a total. Suppressed entirely at n == 1, hedged as "listed" at n >= 2 |
| `ziv_comment` | a human wrote a quantity on the listing ("12 machines", "6x") | authoritative at any value, including 1 |
| `bemanicn_qty` | BemaniCN's published per-title quantity | authoritative |

The `ziv_listed` rule is the important one: ZIv's machine list is a record of WHAT a venue has rather than HOW MANY, so a store owning one of each game tallies to 1 everywhere, and one owning GuitarFreaks plus DrumMania tallies `gitadora: 2` off two single cabinets. `merge.py` keeps a ZIv row's numbers only when some slug counts more machines than the row lists distinct titles for it, which happens only when a title appears twice and so proves the list was entered machine by machine. In the current build 903 merged arcades carry surviving ZIv counts against 3,246 whose counts were placeholders and were dropped (`counts_src: null`, no numbers), out of 4,319 raw ZIv rows that carried any tally.

The same rule applies one level down to `cab_models`: a quantity reaches a cabinet model only when the listing comment NAMES that model. A comment on a "SOUND VOLTEX (Valkyrie model)" row describes the venue's SDVX machines, not its Valkyrie ones, and taking it made 230 of 317 numbered variant pills byte-identical to their parent game's count.

**Coverage:** 65 country queries returned ZIv arcades at the last pull; **6,989** merged source rows under `ziv` in `data/stats.json`, from **7,022** raw rows. Includes Taiko no Tatsujin, Pump It Up, StepManiaX, WACCA, Groove Coaster, crossbeats, BeatStream, and offline cabs of retired games (Project DIVA Arcade, MUSECA, REFLEC BEAT, DanceEvolution).

### Enrichment fields (ZIv)

With the default skip flags, **pricing and venue fields still arrive** (verified 2026-07-27 on a Philippines query: only `pictures` / `comments` / `visitors` are stripped). The scraper maps:

| Raw / derived field | Enrichment key | Notes |
|---|---|---|
| machine `displayPrice` / `pricing` / numeric `price` / `freePlay` | `machine_prices` `{slug: text}` | Free-text preferred when present |
| venue `website` | `website` | |
| `openingTimes` (7-day Mon-first arrays) | `hours_text` | Rendered `Mon 10:00-21:00; ...`; days whose open and close times are identical are dropped, see below |
| `information` | `info_text` | HTML-stripped free text |
| `pictures[].absolutePath` | `images` (max 3) | Only when a crawl drops `skip_pictures`; the weekly crawl keeps it for payload size, so photos come from the separate harvest in section 11 instead |
| scrape date | `enriched_at` | ISO date on the raw row / enrichment entry |

These land in `data/enrichment.json` via `scrapers/enrich.py`, not in `arcades.json`. Images are the exception: the weekly crawl keeps `skip_pictures=1`, so no picture URLs come from `data_raw/ziv.json` itself. The 2,610 ZIv venue photos in the shipped file were collected by `scrapers/photos.py` and `scrapers/chain_photos.py`, which query without that flag, and join by ZIv arcade id rather than through the bulk rows.

**Opening-hours trap:** a day whose open and close times are identical is ZIv's "nobody recorded this" default, not a real 24-hour day. The API hands back `["00:00", "00:00", false]` for all seven days of an unrecorded venue, and `"00:00"` is a truthy string, so a plain truthiness test published `Mon-Sun 00:00-00:00` as if it were real hours. `scrapers/ziv.py` now rejects any zero-length day when rendering `hours_text`, and `_clean_hours_text` in `scrapers/enrich.py` re-checks the formatted string so rows already sitting in `data_raw/` are cleaned too. A string with no parseable `HH:MM-HH:MM` range is passed through untouched rather than guessed at. Effect when the fix landed: `hours_text` fell from 6,955 to 5,211 entries, and 432 entries whose only field was that string were dropped entirely. The field now stands at 5,259 as the ZIv crawl has grown.

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

**Machine counts:** yes - each shop's `arcades[]` entries carry a per-title `quantity`; quantities are summed per mapped slug into `game_counts` (titles that map to `other` are not counted) and tagged `bemanicn_qty` in `count_evidence`, the strongest of the three classes. At the last re-crawl, **93.8%** of raw BemaniCN rows carried a non-empty `game_counts` (3,576 / 3,812). Merged source rows under `bemanicn` in stats: **3,802**.

### Enrichment fields (BemaniCN)

Optional shop/detail fields (all omitted when the payload does not carry them; see `shop_enrichment` in `scrapers/bemanicn.py` and research notes in `docs/research/enrichment-sources.md`):

| Shop / arcade field | Enrichment key | Notes |
|---|---|---|
| `transport` | `transport` | Public-transit directions prose (HTML-stripped) |
| `price` | `price_text` | Venue token/coin unit price (free text, often CNY/token) |
| `pay_type` | `pay_type` | Payment-mode enum (kept raw; not fully reverse-documented) |
| `start_time` / `end_time` | `hours` | Integers; `>24` means next day (e.g. 10/26 -> `10:00-02:00 (+1d)`) |
| `image_thumb.url` | `images` (via the mirrored file, NOT this URL) | **Signed OSS URL** with `e=` expiry. Unusable as a stored link; see section 11 for the mirror |
| `fav_count` | `fav_count` | Community favourites count, **not** a star rating |
| `arcades[].coin` (+ venue price) | `game_prices` `{slug: text}` | e.g. `5 coins/play (~CNY 5.00)` when both parse |
| `arcades[].version` | `game_versions` `{slug: text}` | e.g. `舞萌DX2025` |
| scrape date | `enriched_at` | ISO date |

`shop.comment` (long HTML: membership packs, QQ groups, photo rules) is deliberately **not** emitted into enrichment (large, mostly social prose).

**Still not populated, except for photos.** The committed `data_raw/china_bemanicn.json` rows carry name, address, games, notes, and `game_counts` only (coordinates are null, see the login-only caveat below), so none of the TEXT fields above reach `data/enrichment.json`: `transport`, `price_text`, `pay_type`, `hours`, `fav_count`, `game_prices` and `game_versions` are absent from every entry, and every text field in the shipped file is tagged `ziv`. The parsers stay in place for a re-crawl that collects shop details; until then, treat those rows of the table as the pipeline's capability, not as data on disk.

The one exception is `images`. `counts.bemanicn_rows_contributed` reads **2,256** of 3,812 available, and every one of those contributions is a photo: the separate `scrapers/bemanicn_photos.py` crawl mirrored 3,210 shop thumbnails into `assets/venues/cn/`, and they join to arcades by merged id rather than by source URL. See section 11.

**Staleness:** every enrichment entry carries `enriched_at` (ISO date of the crawl/build). Prices, hours, transit prose, and signed thumbs go stale; treat them as community data that may be outdated. Thumbs expire independently of `enriched_at` when the OSS signature lapses.

**Caveat: coordinates are login-only.** The map layers / API routes that carry lat/lng (e.g. `api/shared/dxmap`) 302-redirect to `/login`. The public endpoints above expose NO coordinates, so every row ships coordinate-less with `coord_system: "gcj02"` (anything this source ever produces would be GCJ-02 and must go through eviltransform). BemaniCN entries gain coordinates by (1) merging with WAHLAP or inheriting a ZIv pin, (2) geocoding the printed address from the committed cache, or (3) administrative-centroid placement for the residue. Options 2 and 3 both set `approx: true`. See the `china_wahlap_bemanicn` rule in `scrapers/merge.py`, plus `scrapers/geocode_cn.py` and `scrapers/china_place.py`.

**Caveat: shop detail 404s.** A few shops listed in a city index have no detail page (404). They are kept, with games `["other"]` and a `detail page 404 (listed in city index only); games unknown` note.

**Caveat: em dashes in source data.** A few entries contain the site's own em dash character (U+2014) inside addresses (floor ranges written like "1F to 3F" with a long dash). They are source data and are kept verbatim in `data_raw/china_bemanicn.json` / `data/arcades.json` - the scraper only collapses whitespace and deliberately does not rewrite source punctuation (note this differs from `common.unescape`, which other scrapers use and which converts en/em dashes to hyphens).

---

## 7. Superseded `community.json` mechanics

`data_raw/community.json` is a committed historical bundle that carries rows from three sources at once (`ziv`, `round1usa`, and a few curated `community` entries). A fresh per-source scrape writes its own file instead: `data_raw/ziv.json` exists today, and `scrapers/round1usa.py` would write `data_raw/round1usa.json`, but that file is **not** in the tree, so the bundle is still the live source of the `round1usa` rows.

**Rule:** when a fresh file for a source exists, the merger **skips that source's rows inside `community.json`** and takes only the fresh file. The skip is keyed on the **row's** `source` field, not on the file name, so curated `community` rows (and any non-superseded sources still only present in the bundle) continue to load. The skip only engages when the fresh file actually exists, so a checkout without it still gets the bundled rows.

**Why it matters:** without the skip, ZIv would load twice. The same arcade is spelled differently between the old bundle and the live API (address parts joined differently), so the within-source dedupe key `(source, name, addr)` does not collapse them and ZIv would silently double. At the last merge, `community_rows_superseded` reported **4,682** `ziv` rows skipped from the bundle; the bundle's **59** `round1usa` rows were all loaded (no fresh file to supersede them), and live stats show only **6** pure `community` source rows remaining.

The superseded count is written to `data/merge_log.json` as `community_rows_superseded`.

---

## 8. `data/china_areas.json` (administrative centroids for approx placement)

Lookup table used by `scrapers/china_place.py` to place coordinate-less mainland China stores at the centroid of the deepest administrative unit their address names. Rebuilt by `tools/build_china_areas.py`, not by the weekly Action.

| Item | Value |
|---|---|
| Path | `data/china_areas.json` |
| Shape | `{source, coord_system, conversion, counts, areas: {id: {n, p, d, lat, lng}}}` where `p` is the parent id and `d` the level |
| Rows | **3,257**: 34 provinces, 372 prefecture-level cities, 2,851 districts/counties |
| Depth | District (区/县) is the floor. Upstream publishes 乡镇/街道 boundaries only as a paid asset (free sample: Shenzhen, Zhongshan, HK, Macau), so `东门街道` in an address cannot be resolved |
| Stored coord system | **WGS-84** (`coord_system: "wgs84"`) |
| Upstream native system | **GCJ-02** |
| Conversion | `GCJ-02 -> WGS-84` via vendored `scrapers/eviltransform.py` `gcj2wgs()` at table build time |
| Upstream source | [xiangyuecn/AreaCity-JsSpider-StatsGov](https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov) release `2025.251231.260403`, file `ok_geo.csv` (deep 0/1/2 centroid column `geo`) |
| License | **MIT** (repository LICENSE, Copyright (c) 2019 xiangyuecn); ok_geo.csv marked free/open in the bundled data doc. Upstream administrative data compiled from 国家地名信息库, 腾讯地图行政区划, and 高德地图行政区划 |
| Taiwan | **Province row only, no cities.** Upstream ships no coordinates below it. `china_place` hard-skips anything labeled Taiwan so street names like `中山路` / `北屯路` never false-match mainland `中山市` / `北屯市` |

**Why the parent chain matters:** short names such as `中山` / `东城` / `和平` / `北屯` are street and district names as often as they are cities. A bare longest-substring match over the whole country mis-places roughly 0.4% of rows. `china_place` never scans the whole country: it resolves province, then city among that province's children, then district among that city's children, so `中山市` is simply not a candidate for a 河北 address. Short forms are tried only when no full official name is present, and are rejected when the next character continues a road or building name (`南山路` is not `南山区`).

**Approx semantics:** placed entries get real-looking `lat`/`lng` plus `approx: true` and `approx_level` (`district` or `city`). Entries sharing an area sit on its centroid exactly, with no fan-out, so a cluster badge is the honest reading of them. Addresses remain the authoritative location for navigation.


## 8b. `data/hk_romanize.json` (Cantonese readings for cross-script merging)

Hong Kong and Macau are the only places where one venue is published under two names that share no characters: ALL.Net writes `PIK FU GAME CENTRE, 26-30 WO YI HOP ROAD` and BemaniCN writes `碧富遊戲機, 和宜合道`. The English is the Cantonese READING of the Chinese, so `scrapers/hk_match.py` reconstructs the reading and compares it.

| Item | Value |
|---|---|
| Path | `data/hk_romanize.json` |
| Shape | `{source, readings: {char: [jyutping syllable, ...]}}`, tones stripped, at most 3 readings per character |
| Rows | **25,001** characters |
| Upstream source | [rime/rime-cantonese](https://github.com/rime/rime-cantonese) `jyut6ping3.chars.dict.yaml` |
| License | **CC BY 4.0**, 粵語計算語言學基礎建設組 (CanCLID) |
| Rebuilt by | `python tools/build_hk_romanize.py` (not the weekly Action) |

**Jyutping is not what Hong Kong street signs use.** The signs use the older Hong Kong Government romanisation, which disagrees with Jyutping constantly: 觀塘 is `gun tong` in Jyutping and `Kwun Tong` on the sign, 沙田 is `saa tin` against `Sha Tin`. Both sides are folded onto a coarse phonetic skeleton that discards exactly the distinctions the two systems argue about (voicing, sibilant spelling, doubled vowels) and the remainder is compared with a one-edit tolerance. The skeleton is lossy on purpose, so `merge.py` never acts on one match alone: the Hong Kong tier requires two independent kinds of evidence.

Some names are translations rather than romanizations and no phonetic method reaches them (香港仔 is Aberdeen, 青山公路 is Castle Peak Road, 旧大街 is Old Main Street). Those live in a short, individually commented `EXONYMS` table in `scrapers/hk_match.py`.

---

## 8c. `data/china_geocode.json` (street-level China addresses, keyless)

The committed answer cache that places almost every mainland-China arcade. Written by `scrapers/geocode_cn.py`, read by merge, and never refreshed on a normal build.

| Item | Value |
|---|---|
| Path | `data/china_geocode.json` (plus `data/china_manual_coords.json` for hand-researched pins) |
| Shape | `{"<query key>": {lat, lng, provider, precision, formatted, query, fetched_at}}`, or `{"miss": true, provider, fetched_at}` for an address nothing resolves |
| Rows | **5,738**: 5,723 hits (all `provider: "baidu"`), 15 recorded misses |
| Default provider | **Baidu, keyless.** `https://api.map.baidu.com/?qt=s`, the backend map.baidu.com's own frontend calls, over plain HTTPS with a browser UA and a map.baidu.com Referer |
| Other providers | `AMAP_KEY` / `GOOGLE_MAPS_API_KEY` win when present in the environment. Neither is required, and CI has neither |
| Native coord system | Baidu **BD-09, as Mercator metres times 100** (`x: 1267877300`). AMap and Google-in-China are **GCJ-02** |
| Stored coord system | **WGS-84**, converted through `bd2wgs` / `gcj2wgs` before anything reaches the cache |
| Refresh | `python scrapers/run_all.py --skip-scrape --only geocode`, then re-merge. Hours of polite serial requests, so it is asked for by name and never part of a default run |
| Effect | 5,757 rows placed at address level; China distinct coordinates 2,090 -> 5,305; worst pile-up on one point 69 venues -> 6 |

**Why a miss is stored.** An address no geocoder can resolve (a bare mall-floor label, a closed venue) is written as `{"miss": true}` rather than left absent, so the next refresh does not re-pay for the same dead end. `lookup` never hands a miss back as a coordinate.

**Three gates, all of them about garbage rather than jurisdiction:**

1. **Mainland bounding box.** A partial address like `中山路` or `万达广场3F` resolves *somewhere*, and every provider would rather return a confident point in Kazakhstan than admit it does not know. Outside the box, the candidate is discarded and the next coarser one tried. The box does NOT filter by jurisdiction (Taiwan, Hong Kong and Macau all sit inside it); keeping those out is the caller's job, exactly as it is in `china_place`.
2. **Area check.** Baidu states the answer's own administrative area in `area_name` (`深圳市宝安区`), and a mismatch against the city the address named is a rejection rather than a pin. This is why the province/city prefix on the query is not optional: BemaniCN's `全运路万达3F` names no city, so `qualified_address` prepends the one the region note knows, and a row with no stated city is skipped rather than guessed at.
3. **District check at READ time, not only at fetch time.** 5,702 answers were already committed when the gate was added and `run()` never re-asks a cached hit, so a fetch-only gate would have fixed nothing that already shipped. `apply_cache` re-checks and refuses; refused rows fall through to a centroid and are logged as `china_geocode_rejected` in `data/merge_log.json`.

**Progressive queries.** A printed Chinese address is a province, a city, a district, a road, a number, a mall, a floor and a unit stacked together. Handing the whole string to a POI search resolves about a tenth of the time, because no index holds a row for "3rd floor, next to the lift". `scrapers/cn_address.py` strips that tail (`strip_noise`) and emits progressively coarser candidates (`candidates`): full cleaned address, then city + district + mall, then city + mall, then road + number. The venue NAME is a candidate too, because BemaniCN names its shops after the mall they sit in (`环游嘉年华（北京朝阳大悦城店）`) even when the address does not.

**What the cache does NOT establish, and this is the whole caveat:** the keyless endpoint is a POI SEARCH. A `precision: "poi"` answer says the result was a building, never that it was THIS building. Every placed row therefore keeps `approx: true`. See the README China accuracy disclosure and the long comment in `scrapers/merge.py`.

**`data/china_manual_coords.json`** holds the few venues nothing resolves, applied BEFORE the cache. Every record must carry a `source_url` (a coordinate nobody can audit is indistinguishable from one somebody invented) and a `name`. The name is a safety interlock, not decoration: merge renumbers ids 1..N by (country, name, addr) on every build, so an id alone would silently drift onto a different venue when the upstream feed adds or drops a row. `apply_cache` refuses to place a record whose name no longer matches its id, and says so loudly.

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
  "prices": {as_of, basis, source, note, min_measured, countries, coverage,
             stats, artifacts},
  "price_defaults": {ISO2: {currency, display, notes, typical, source, as_of}},
  "country_to_code": {"Japan": "JP", ...},
  "counts": {arcades_enriched, of_total, by_field, bemanicn_rows_*, ziv_rows_*,
             arcades_with_venue_photos, venue_photos_by_source, photos_index_ids},
  "arcades": {"<merged id>": {transport, price_text, pay_type, hours, hours_text,
                               images, image, image_tier, fav_count, game_prices,
                               game_versions, machine_prices, website, info_text,
                               sources, enriched_at}}
}
```

Only arcades with at least one enrichable field (or a photo) get an entry. Frontend price priority: a MEASURED figure from the `prices` table for this country and this game > the country's measured overall > the hand-written `price_defaults` entry, which is a last resort and always carries `typical: true`. A cell tiered `unknown` renders nothing at all rather than falling back to a guess. A store's own quoted `machine_prices` are shown separately, as its own listing rather than a country figure.

**The measured price table (`prices`).** Built by `scrapers/prices.py` from the same `machine_prices` strings the ZIv rows contribute, aggregated per country and per game. It exists because the `price_defaults` table was hand-guessed and at least one cell was wrong: it asserted "HKD 8-15/play typical" where every Hong Kong listing in the dataset quotes HK$6.00 for maimai and CHUNITHM, n=15, zero variance.

Rules, in priority order:

1. **A wrong price is worse than no price.** Every ambiguous construction is rejected and counted rather than guessed. The current run parsed 4,316 of 8,194 candidate rows and accepted 4,291; rejections break down as 1,918 token systems, 1,272 free play, 570 with no identifiable currency, 118 where every play tier was rejected.
2. **Store tokens are not money.** "3 Medals", "8 creds", "6.8 Funcoins" have no public exchange rate and are classified `token_system`, never coerced to a number.
3. **Play tiers are not interchangeable.** Light / Standard / Premium / Galaxy / Blaster starts cost different amounts; the STANDARD tier wins and a Premium figure is never averaged in as though it were the standard price.
4. **The headline is the MODE, not the mean or an interpolated median.** The mode is always an amount somebody actually quoted; a median over `{6, 8}` invents HK$7, which nobody charges. `median` is still emitted for reference, and a cell whose median disagrees or whose spread is wide is demoted (`demoted_by`).
5. **Local currency only.** `js/format.js` converts at render time against `data/fx_rates.json`, so baking converted values in would freeze them.

Tiers: `measured` needs n >= 5, `sparse` is 2 to 4 and renders with an explicit "based on only N listings" caveat, `unknown` renders nothing. Current coverage across 29 countries: **116 measured, 113 sparse, 87 unknown**. The block also carries `stats.unmapped_countries` (countries with quoted prices but no currency mapping, so their rows are dropped rather than guessed at) and an `artifacts` list of the individual rows a plausibility gate rejected, each with the text that produced it, so a bad parse is auditable rather than invisible.

**Note on the parser, worth knowing before changing it:** the number pattern treats a space as a thousands separator ONLY when it is followed by exactly three digits. That is what a thousands separator always looks like (`₩2 500`, `Rp10 000`) and what a trailing quantity almost never does. An earlier unrestricted run of digits, commas, dots and spaces walked through the word boundary and read "R$4,00 5 hearts" as BRL 4005. The extreme case is caught by the plausibility gate; the dangerous sibling is not, because "R$2 5 hearts" parses as BRL 25.00, an entirely ordinary-looking price.

**What the shipped file actually contains.** The key list above is the full set the builder can emit, not the set on disk. The current `data/enrichment.json` holds **9,862** entries against **13,540** arcades: `hours_text` (5,259), `info_text` (4,241), `website` (4,095), `machine_prices` (3,664) and `images` / `image_tier` (5,824), plus the per-entry `sources` and `enriched_at` metadata. Every text field is tagged `ziv`. There is still no `transport`, `fav_count`, `game_prices`, `game_versions`, `pay_type`, `price_text` or `hours`: `bemanicn_rows_contributed` is 2,256 of 3,812, and every one of those contributions is a photo (see sections 6 and 11).

---

## 11. Venue photos (`assets/venues/`, `data_raw/*photo*.json`)

Real photographs OF the venue, as distinct from the stock cabinet shots under `assets/cabs/`. **Nothing in this section runs during the weekly Action.** Each crawl below is manual and writes a committed artefact; `scrapers/enrich.py` only reads them.

**Coverage today: 5,824 of 13,540 arcades (43.0%)**, by contributing source: BemaniCN 3,192, ZIv 2,610, Wikimedia Commons 22. By country it is very uneven: China 51.1%, United Kingdom 60.1%, United States 57.5%, Japan **6.9%**, Taiwan 6.8%.

| Module | Source | Output | Mirrored? |
|---|---|---|---|
| `scrapers/photos.py` | ZIv, `skip_pictures` dropped | `data_raw/ziv_photos.json` | No, hotlinked with credit + deep link |
| `scrapers/chain_photos.py` | ZIv full-country sweep, Wikimedia Commons, GiGO link-out repair | `data_raw/chain_photos.json` | Commons only |
| `scrapers/bemanicn_photos.py` | BemaniCN shop thumbnails | `assets/venues/cn/<shop_id>.jpg` + `data_raw/bemanicn_photos.json` | **Yes, of necessity** |
| `scrapers/photo_quality.py` | none (scores existing images) | `data_raw/photo_quality.json` + probe cache | n/a |
| `scrapers/streetphotos.py` | measured and rejected | `data_raw/street_photos.json`, intentionally empty | n/a |

**Only tier `venue` counts as coverage.** A chain logo is not a photo of that arcade, and neither is a photo of the mall around it or a closeup of one cabinet. Link-outs count as zero.

**Why BemaniCN photos are mirrored rather than linked.** `props.shop.image_thumb.url` is a **signed OSS link**: it carries `?e=<unix expiry>&token=...` scoped to one exact path, and measured behaviour is that the token expires within the hour, stripping the query returns 401, and every larger variant (`-large`, `-medium`, `-origin`, Qiniu `imageView2` params) also returns 401. A weekly JSON of remote URLs would therefore ship 100% dead images. Only one photo per shop is publicly reachable; the multi-photo gallery is login-walled. Expect ~150-200 px on the long edge and 7-10 KB per file: these are PANEL THUMBNAILS, and the index records real pixel dimensions so the frontend can refuse to upscale one into a hero slot.

**Licence position:** BemaniCN publishes no ToS, no CC grant and no photo licence page (`/terms`, `/privacy`, `/tos`, `/agreement` all 404); the site meta carries `(c) BEMANICN` and the photos are community uploads. They are **not** relicensed by this repo's MIT licence. Every file ships with attribution, a per-shop deep link and a takedown path in [`assets/venues/ATTRIBUTION.md`](../assets/venues/ATTRIBUTION.md). ZIv likewise publishes no photo licence, so its images are hotlinked with a visible credit and a deep link home and are never rehosted. Commons images are CC/PD with per-file attribution carried in the record.

**Ranking, not just rejecting.** `scrapers/photo_quality.py` never decodes a pixel (the repo is stdlib-only). It reads the image HEADER plus the byte length the server reports and reasons from four measurables: pixel dimensions, byte size, aspect ratio, and bytes per pixel. That honestly answers "will this upscale into a blurry mess in the hero slot", "will `object-fit: cover` crop it to a meaningless sliver", and "was this uploaded in 2012" (ZIv filenames carry a unix timestamp). It CANNOT answer "is this blurry" or "is this a photo of somebody's legs", and does not claim to. Every image gets a score, a verdict and a human-readable reason list, so the ordering is auditable rather than trusted.

**Chain store pages: measured, and deliberately not used.** GiGO, Taito, Round1, namco, APINA, Timezone, Dave & Buster's, Cineplex and Tom's World were probed and scrape at 95-100% technically. Every one of them publishes all-rights-reserved terms, Taito and namco explicitly restrict copying and transmitting, and namco asks that image files not be deep-linked at all. Hotlinking their CDN from a public GitHub Pages map is exactly the pattern those terms forbid, so `chain_photos.py` emits **zero** chain imagery. Those chains appear only as `link_outs`, which carry `page_url` and never `url` or `file` (a record with a `url` key is a DISPLAY path regardless of its tier, so mixing them would render an all-rights-reserved image). This is the main reason Japanese coverage is 6.9% while the UK is 60%.

**Street-level imagery: measured and rejected.** Five sources were probed against a fixed-seed stratified sample of 210 arcades (`data_raw/streetlevel_imagery_probe.json`, 30 each across Japan, US, UK, Taiwan, Philippines, Singapore, China):

| Source | Verdict |
|---|---|
| KartaView | REJECT. Keyless and the only one with real hits, but only **5.2%** of arcades have a photo within 60 m whose camera is pointed at them, and **0 of 7** best-case frames downloaded and inspected showed an arcade. All were road-forward windshield dashcam shots. Japan and China measure 0-3% |
| Mapillary | BLOCKED. Token-gated, and a shared token must never be committed to a public repo. Same dashcam capture model regardless |
| Wikimedia Commons geosearch | REJECT. Raw hits are majority tourist/transport geography; no hit was confirmed to be the arcade. (The category-walked, hand-reviewed Commons path in `chain_photos.py` is a different thing and does ship, at 22 arcades) |
| OSM `image=*` tags | REJECT. 0 of 210 in the sample; global ceiling 24 objects of ~8,880 mapped arcades, and those point at unmirrorable third-party hosts |
| Wikidata P18 | REJECT. 32 items worldwide in the arcade class. Brand-level P18 is actively harmful: it would put a corporate HQ photo on every branch of a chain |

Dashcams photograph roads, not shops, and radius hit rate overstates usable storefront coverage by roughly an order of magnitude. `streetphotos.py` therefore ships an empty index WITH the rationale rather than being deleted, so the measurement does not have to be repeated.

**Google Places photos** are a separate optional path: place IDs may be stored (Google exempts them explicitly), photo bytes may not be, so nothing is ever written to disk and the whole feature is a no-op without a key. Full detail, costs and match verification: [`docs/GOOGLE_PHOTOS.md`](GOOGLE_PHOTOS.md).

---

## Refresh pipeline

All sources are re-scraped by a single GitHub Action: weekly cron, Monday 18:00 UTC, plus `workflow_dispatch` for manual runs. The job runs with `permissions: contents: write`, commits changed files under `data/`, `data_raw/`, and `mymaps/` with a bot identity, and skips the commit when nothing changed. Arcade scrapers fail-fast (one broken source blocks the commit). FX is the exception: total feed failure keeps the previous rates file and does not fail the job. Both scrape targets (location.am-all.net, p.eagate.573.jp) are empirically reachable from GitHub-hosted US runners as of July 2026.

**What the Action does NOT run,** and must not start running, because each costs hours of somebody else's bandwidth or somebody's API quota: the China geocode refresh (section 8c), every photo harvest (section 11), and Google place-ID resolution. All of those write committed artefacts that the weekly build merely reads, so the Action needs no key for any of them and a keyless CI run produces the same output as a developer's machine. `run_all.py --only` accepts `geocode` for the first of these; the rest are invoked directly.
