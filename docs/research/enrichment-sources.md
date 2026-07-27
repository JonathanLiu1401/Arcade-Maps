# Enrichment data sources research

Research date: 2026-07-27  
Scope: free/static-friendly paths to ratings, photos, cost-per-play, FX conversion, transit directions, and nearby search for the Arcade Maps static GitHub Pages site (weekly Actions rebuild, no server backend).  
Method: live HTTP fetches against existing sources + official docs. Claims are marked **VERIFIED** (fetch/doc evidence) or **UNVERIFIED**.

---

## 1. What we already have (unused fields)

### 1a. bemanicn shop payload (`map.bemanicn.com`)

**VERIFIED** by live Inertia partial fetch:

```
GET https://map.bemanicn.com/s/1
Headers:
  X-Inertia: true
  X-Inertia-Version: (empty)
  X-Inertia-Partial-Component: Shop/Show
  X-Inertia-Partial-Data: shop
  Accept: application/json
```

HTTP 200, `Content-Type: application/json`. Full response saved under session scratchpad as `bemanicn_shop1.json`.

`props.shop` keys (30 fields) for shop id=1 (街机烈火 / Shanghai):

| Field | Example (shop 1) | Notes |
| --- | --- | --- |
| `id` | `1` | Shop id |
| `name` | `街机烈火` | |
| `name_pinyin` | `liehuo` | |
| `address` | `江宁路77恒顺大楼4层(南京西路地铁站1号口步行430米)` | |
| `province_code` | `310000000000` | |
| `city_code` | `310100000000` | |
| `county_code` | `310106000000` | |
| `transport` | `地铁：2/12/13号线 南京西路 站 1号口出 步行430米 公交：23路（江宁路南京西路），15路，21路，927路，315路（北京西路泰兴路），68路，950路（昌化路）` | **Public-transport directions text (already present)** |
| `price` | `"1"` | Shop-level token/coin price string (here: 1 CNY per token). Free-text, not structured multi-currency. |
| `pay_type` | `4` | Payment mode enum (meaning not fully reverse-documented here) |
| `start_time` / `end_time` | `10` / `26` | Hours as integers (26 = 02:00 next day) |
| `status` | `1` | |
| `locked` | `1` | |
| `type` | `1` | |
| `collab` | `true` | |
| `fav_count` | `730` | Community favorites (not a star rating) |
| `ea_status` | `1` | |
| `comment` | long HTML (Weibo/WeChat/XHS links, **代币价格** tables, membership card packs, photo rules, QQ groups) | Rich free-text pricing + amenities |
| `url` | `null` | |
| `image_thumb` | `{id, filename, url, shop_id}` with OSS URL on `oss.bemanicn.com` (signed `token` + `e=` expiry) | **Photo thumbnail exists** |
| `option1`..`option5` | mostly 0 / null; `option4` is another OSS static PNG URL | Possibly badges/icons |
| `events` | `[]` | |
| `created_at` / `updated_at` | ISO timestamps (`updated_at`: `2026-06-30T11:01:28.000000Z`) | Good for scraped-date stamps |
| `arcades` | list of per-title cabs | See below |

Each `arcades[]` entry keys (**VERIFIED** sample):

| Field | Example | Notes |
| --- | --- | --- |
| `id` | `7` | |
| `title_id` | `1` (maimai) | Mapped in scraper already |
| `quantity` | `9` | Machine count (already used) |
| `version` | `舞萌DX2025` | |
| `coin` | `5` | **Coins/credits per play for this title** |
| `eacoin` | `0` | EA-coin related flag/count |
| `comment` | free text (cab variants, hourly rental rates, membership-only notes) | |
| `shop_id` | `1` | |
| `order` | `10` | Display order |

**Currently used by `scrapers/bemanicn.py`:** city index `name`/`address`/`id`; detail `arcades[].title_id` + `quantity` only.  
**Unused but high-value for enrichment:** `transport`, `price`, `pay_type`, `start_time`/`end_time`, `comment`, `image_thumb`, `fav_count`, `arcades[].coin`, `arcades[].eacoin`, `arcades[].comment`, `arcades[].version`, `updated_at`.

Caveats:

- Coordinates still login-walled (unchanged from `docs/DATA_SOURCES.md`).
- `image_thumb.url` is a signed OSS URL (expires); do not bake long-lived CDN links without re-fetching weekly.
- `price` + per-arcade `coin` give China coin-economy data (e.g. 1 CNY/token, 5 coins/play => ~5 CNY/play) but not USD/JPY.

### 1b. Zenius-I-Vanisher API

**VERIFIED** live fetch without skip flags:

```
GET https://zenius-i-vanisher.com/api/arcades.php?action=query&country=Philippines
```

(no `skip_pictures` / `skip_visitors` / `skip_comments`)

HTTP 200, 343 arcades. Union of top-level fields:

`address`, `addressLine1`, `addressLine2`, `city`, `comments`, `contactNumber`, `country`, `formattedInformation`, `id`, `information`, `lastUpdateDifference`, `lastUpdateTime`, `latitude`, `longitude`, `machines`, `name`, `openingTimes`, `pictureCategory`, `pictures`, `postalCode`, `subregion`, `visitors`, `website`

Pictures (**VERIFIED**): 169/343 PH arcades had non-empty `pictures`. Shape:

```json
[{"id": 51434, "absolutePath": "http://zenius-i-vanisher.com/pictures/1538211501.154.jpg"}]
```

HEAD on that JPEG returned `200 image/jpeg` (~57 KB). Pictures are hostable as hotlinks, but hotlinking depends on ZIv hosting policy (community site; no formal CDN/ToS audit done here - treat as **community-courtesy**, cache/rehost only if license allows).

Machine pricing (**VERIFIED**, abundant): each machine can carry:

- `displayPrice` (free text, e.g. `PHP 40.00 for 3 songs`, `₱50.00 | 1 gacha token | 1 credit`)
- `pricing` (alternate free text)
- `price` / `minPrice` / `continuePrice` / `minContinuePrice` (numeric; often 0 when only free-text is filled)
- `freePlay` (bool)
- `condition` (1-5-ish community rating of cab condition, not a venue star rating)
- `comment`, `location`, `songs`

Example Quantum SM North EDSA (id 88): 23 pictures, 31 comments; CHUNITHM `displayPrice` = `PHP 40.00 for 3 songs`; maimai `price` = 50; token system described in `information` ("One token costs PHP5.00").

Comments (**VERIFIED**): array of `{id, dateTime, content, formattedContent, user:{id,username}, timeSpan}`.

`openingTimes`: 7-day arrays of `[open, close, closedFlag]`.

**Current scraper (`scrapers/ziv.py`)** always uses `skip_pictures=1&skip_visitors=1&skip_comments=1` and only maps id/name/address parts/lat/lng/machines->games. **Unused:** pictures, comments, visitors, website, contactNumber, openingTimes, information free-text (except closed heuristics), and **all per-machine pricing fields**.

Payload size note: PH without skips was ~1.6 MB for 343 arcades. Worldwide with pictures would be large; weekly Actions may need per-country or "pictures only for top N / recently updated" strategy.

### 1c. eagate / ALL.Net pricing or photos

**VERIFIED** quick HTML checks:

- eagate IIDX Tokyo list (`list.html?gkey=IIDX&pref=JP-13`): `data-*` attrs on shop blocs are only `name`, `address`, `latitude`, `longitude`, `access`, `telno`, `operationtime`, `holiday`, etc. **No price fields, no store photos.** `円` appears only incidental (4 hits, not structured pricing). PASELI icon remains a boolean already scraped.
- ALL.Net maimai JP (`location.am-all.net`, gm=96, Tokyo-area): `store_name` list present; **0 hits** for 円/料金/price/photo patterns of interest.

**Conclusion:** official JP locators give name/address/coords/(hours|access|paseli). No cost-per-play, no photo gallery.

### Other raw inventory (already on disk)

| Source file | Fields present | Unused enrichment potential |
| --- | --- | --- |
| `china_wahlap_*.json` | name, address, province notes, no coords | none for photos/ratings/price |
| `maimai_jp.json` / ALL.Net family | name, address, lat, lng, sid, region | none |
| eagate family (`iidx.json` etc.) | + `paseli` bool | access/tel/hours exist on HTML but not always persisted |
| `community.json` | merged community schema | no pricing/photos |
| Round1 USA Storepoint | name, address, lat, lng, slug | Storepoint may expose phone/hours/tags in full API; scraper keeps standard lineup note only (**partially UNVERIFIED** full Storepoint field list) |

---

## 2. Ratings / photos from Google Places

### Pricing model (2026)

**VERIFIED** from [Google Maps Platform pricing](https://mapsplatform.google.com/pricing/) (fetched 2026-07-27):

As of 2025-03-01, the old USD $200 monthly credit was replaced by **per-SKU free monthly quotas**:

| Tier | Free calls / SKU / month |
| --- | --- |
| Essentials | 10,000 |
| Pro | 5,000 |
| Enterprise | 1,000 |

New customers still get a separate trial credit (page text: $300 trial).

**Field / SKU mapping for Place Details (New)** (**VERIFIED** from [Place Details docs](https://developers.google.com/maps/documentation/places/web-service/place-details)):

| Data | SKU tier |
| --- | --- |
| `photos` (photo resource names/refs) | Essentials IDs Only |
| address / location basics | Essentials |
| `displayName`, status, maps URI, etc. | Pro |
| **`rating`, `userRatingCount`** | **Enterprise** |
| **`reviews`**, editorial/generative summaries | **Enterprise + Atmosphere** |
| **Place Details Photos** (bytes fetch) | **Enterprise** (separate Photos SKU; free pool = 1,000/month) |

Billing rule: request is charged at the **highest** SKU of any requested field.

### Caching / storage terms

**VERIFIED** from [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies) and Service Specific Terms summaries:

- General rule: **must not pre-fetch, cache, or store** Places content beyond allowed exceptions.
- **`place_id` may be stored indefinitely** (exempt from no-cache rule).
- **lat/lng** may be temporarily cached up to **30 consecutive days**, then deleted.
- Names, addresses, **ratings, reviews, photos, hours, phone, website**: session-display style - request live, do **not** warehouse in your weekly `data/*.json` rebuild.
- Attribution: Google Maps logo / "Google Maps" text; photo/review author credits required.

### Client-side key on a public Pages site

Technically possible: browser key restricted by **HTTP referrer** to `https://your-user.github.io/*` (and custom domain). This is a common Maps JS pattern.

However for this product:

1. **Ratings need Enterprise Place Details** (1,000 free calls/SKU/month).
2. **Photo bytes need Place Details Photos** (also Enterprise-tier free pool of 1,000).
3. Terms forbid baking ratings/photos into the weekly static dataset; client-side-on-open is the compliant pattern.
4. At ~1,000 visits/month, if each visit opens 1 arcade detail and fetches rating + 1 photo:
   - 1,000 Enterprise Details (rating) => **hits free cap exactly** (or exceeds if users open more than one).
   - 1,000 Photo loads => **hits Photos free cap**.
5. What breaks first at 1,000 visits/month: **Enterprise free quotas for rating and photos**, not Essentials. After free tier, pay-as-you-go Enterprise rates apply (order of tens of USD per 1,000 calls; confirm live pricing list before enabling billing).
6. Referrer-restricted keys still leak (any browser can call from your origin). For abuse, attackers can burn your quota from the public site. Google recommends server proxies for production; this site has no backend.

### Scraping Google Maps / Images

**Forbidden.** Scraping Google Maps, Google Images, or Places HTML/JSON outside the official API **violates Google Terms of Service**. Do not scrape. Do not propose scrapers.

### Concrete answer

| Question | Answer |
| --- | --- |
| Zero-cost path for static site? | Only if usage stays under per-SKU free caps **and** data is fetched client-side per session (not baked weekly). Ratings are Enterprise (1k free). |
| Free-tier key referrer-restricted on Pages for ratings+photos? | Technically yes, terms-wise only for live session display with attribution; **not** for storing in `arcades.json`. |
| What breaks at ~1000 visits/month? | Enterprise Place Details (rating) and Place Photos free pools. |
| Bake Google ratings into weekly data? | **No** (ToS). |

**Owner decision required** before any Google integration: enable billing, accept Enterprise SKUs, implement session-only client fetch + attribution UI, accept quota risk.

---

## 3. Ratings / photos alternatives

### Foursquare / Swarm Places API

**VERIFIED** from [foursquare.com/pricing](https://foursquare.com/pricing/) and [Upcoming Changes](https://docs.foursquare.com/developer/reference/upcoming-changes) (fetched 2026-07-27):

- Pay-as-you-go. Pro endpoints (search/details default fields): free band then ~$15 CPM after free tier.
- **Premium (Tips & Photos)** starts ~$18.75 CPM with **no meaningful free photo tier**.
- Effective **2026-06-01**: free Pro calls drop to **500**/month (per upcoming-changes doc).
- Key is server-style; embedding a secret in a static site is a bad idea (quota theft). Needs a proxy (this project has none).
- JP coverage for game centers is mixed/historical Swarm check-ins; CN coverage is weak for rhythm arcades (**spot coverage UNVERIFIED** beyond general industry reputation).

**Verdict for this site:** not free enough for photos/ratings at scale; not static-key-safe.

### Yelp Fusion / Places API

**VERIFIED** from Yelp developer docs (rate limiting / plans pages via search + docs links):

- Classic free Fusion tier is gone; product is paid Places API with a short trial (order of thousands of trial calls), then paid plans (Starter on the order of ~$8 per 1k calls - confirm live).
- Coverage is strong in US/CA/parts of EU. **Japan Yelp consumer product was shut down years ago; mainland China is not a Yelp market.** Useless for GiGO JP / China arcades; weak for PH/SEA vs local apps.

**Verdict:** not useful for this dataset's geography; not free.

### OpenStreetMap (Overpass) tags

**VERIFIED** live Overpass queries (2026-07-27):

Akihabara bbox (`leisure=amusement_arcade` / `adult_gaming_centre` / name~GiGO): found GiGO buildings and other game centers. Tags present were typically `name`, `leisure`, sometimes `opening_hours`, `level`, `check_date`. **No `image` or `wikimedia_commons` on those samples.**

Manila SM North area: found a `Timezone` node with `brand=Timezone`, `leisure=amusement_arcade`; Quantum Fitness (sports, not arcade). **No photos.**

OSM can occasionally carry `image=*`, `wikimedia_commons=*`, `website=*`, but arcade coverage of those tags is sparse. License: ODbL (share-alike for databases). Overpass is free with polite use; not a ratings source.

### Wikimedia Commons

Free media under various CC licenses. Good for famous venues / chains if someone uploaded; not a systematic per-arcade photo DB. Attribution required per file license. Discovery via Commons API is keyless and cacheable. **Coverage for individual Quantum/GiGO branches is spotty (UNVERIFIED exhaustive search).**

### Mapillary

Street-level imagery; free/CC BY-SA style after Meta acquisition (API token required). Japan urban coverage is usable; China is patchy vs Baidu. Images are streets/facades, not interior arcade shots. Useful as "street view link-out", not as store photo galleries.

### Practical alternative ranking (free / static-friendly)

1. **ZIv pictures + machine condition + comments** (already in API; scraper currently skips them).
2. **bemanicn `image_thumb` + `fav_count` + comment HTML** for China.
3. OSM/Mapillary/Commons as optional link-outs or rare extras.
4. Google Places session-only if owner enables billing.
5. Foursquare/Yelp: skip for this geography + cost profile.

**Spot-check summary**

| Venue | Google (link-out) | ZIv photos | OSM image tags | Yelp |
| --- | --- | --- | --- | --- |
| GiGO Akihabara | ubiquitous Maps listing (not scraped) | ZIv has 200+ GiGO rows in raw; pictures need non-skip fetch (**structure VERIFIED** on PH) | name/leisure only in sample | none useful |
| Quantum (Manila) | Maps listing | **VERIFIED** e.g. SM North EDSA: 23 pics, prices filled | thin | none useful |

---

## 4. Cost-per-play data

### Structured sources that exist

| Source | Structured? | Evidence |
| --- | --- | --- |
| bemanicn `price` + `arcades[].coin` (+ membership text in `comment`) | **Partial** (CN coin economy) | **VERIFIED** shop 1: `price="1"`, maimai `coin=5` |
| ZIv per-machine `displayPrice` / `pricing` / `price` | **Yes, free text + optional numeric** | **VERIFIED** PH sample; dense where community edits |
| eagate / ALL.Net | **No** | **VERIFIED** HTML has no fee fields |
| WAHLAP REST | **No** | address-only (existing docs) |
| Round1 USA | chain standard pricing pages exist on round1usa.com marketing site; **not** in Storepoint location JSON used today | store API **VERIFIED** for locations only; public price pages **not exhaustively fetched** (UNVERIFIED exact per-store fees) |

### Community norms (contextual, not API)

Japan game centers commonly use 100 yen per credit for many rhythm games, with premium starts / extra songs varying by title and shop. That is a **community norm**, not a live structured feed. Store it as a **country default with `typical: true`**, never as a guaranteed price.

### Realistic conclusion

Mostly **manual / community** data outside ZIv free-text and bemanicn coin fields. No global structured "cost per play" API.

### Maintainable representation (recommended)

Bake into weekly data (your own schema, not Google's):

```json
"pricing": {
  "currency": "JPY",
  "per_credit": 100,
  "typical": true,
  "source": "country_default",
  "as_of": "2026-07-27",
  "notes": "Common JP game-center credit; verify on-site",
  "by_game": {
    "maimai_dx": {"credits_per_play": 1, "display": "100 yen / credit (typical)"}
  }
}
```

Merge priority:

1. ZIv machine `displayPrice` / numeric `price` when present (per game).
2. bemanicn `price` + `coin` for China (compute CNY/play ≈ price * coin when both parse).
3. Country/region defaults with `"typical": true`.
4. Optional manual overrides file (`data_extra/pricing_overrides.json`) for chains (Round1, Timezone, Quantum token systems).

Display always: local currency first, converted estimates secondary, label **typical / community / may be outdated**.

---

## 5. Currency conversion (weekly static bake)

### Candidates

| API | Key? | Live fetch 2026-07-27 | Notes |
| --- | --- | --- | --- |
| **Frankfurter** `https://api.frankfurter.app/latest?from=USD&to=JPY,HKD,CNY,EUR` | No | **VERIFIED** 200 JSON | ECB-derived; same payload via `api.frankfurter.dev` |
| **open.er-api.com** `https://open.er-api.com/v6/latest/USD` | No | **VERIFIED** 200 JSON | ExchangeRate-API open access; daily update; attribution required; caching allowed; no redistribute |
| exchangerate.host | Key now required (APILayer) | not used | no longer keyless |

### Live rates pasted (evidence)

Frankfurter (date field `2026-07-24`, base USD):

```json
{"amount": 1.0, "base": "USD", "date": "2026-07-24", "rates": {"CNY": 6.7722, "EUR": 0.87897, "HKD": 7.8426, "JPY": 163.82}}
```

open.er-api.com (update `Mon, 27 Jul 2026 00:02:31 +0000`, base USD):

```
JPY 163.679291
HKD 7.842426
CNY 6.777732
EUR 0.877986
PHP 61.795217
```

### Recommendation

- **Primary for Actions bake:** Frankfurter (ECB reference, no key, simple JSON). Confirm license on [frankfurter.dev](https://frankfurter.dev/) (open-source wrapper of public ECB rates; suitable for non-redistribution-sensitive display). Note: ECB set historically may omit some exotic pairs; **CNY/HKD/JPY present in live response**.
- **Fallback:** open.er-api.com (broader currency list including PHP); must show attribution ("Rates By Exchange Rate API") and not re-publish a competing rates API.
- Store `data/fx_rates.json` weekly: `{as_of, base: "USD", rates: {...}, source}`. Client multiplies local price estimates. One request per week is trivially under any free limit.

---

## 6. Transit directions

### China: bemanicn `transport` text

**VERIFIED** (Q1). Store with:

- `transport_text` (verbatim)
- `transport_scraped_at` (ISO date from crawl or `updated_at`)
- UI label: **"Community directions; may be outdated"**

### Keyless deep links (no storage of route geometry)

**Google Maps URLs** - **VERIFIED** [Maps URLs docs](https://developers.google.com/maps/documentation/urls/get-started):

- No API key required.
- Transit example pattern:

```
https://www.google.com/maps/dir/?api=1&destination=LAT,LNG&travelmode=transit
```

Optional `origin=` (omit to use device location).

**Apple Maps** - **VERIFIED** from Apple Map Links / community docs:

```
https://maps.apple.com/?daddr=LAT,LNG&dirflg=r
```

(`dirflg=r` = public transit; `d` driving, `w` walking.) On non-Apple devices opens web Maps.

**AMap (高德)** - **VERIFIED** [URI route guide](https://lbs.amap.com/api/uri-api/guide/travel/route):

```
https://uri.amap.com/navigation?from=LON,LAT,start&to=LON,LAT,name&mode=bus&policy=0&src=arcademaps&callnative=1
```

App schemes also exist (`amapuri://route/plan/?...&t=...`) per [amap-mobile](https://lbs.amap.com/api/amap-mobile/summary).

**Baidu Maps** - official URI docs pages respond (**VERIFIED** HTTP 200 on lbsyun.baidu.com uri/api pages). Common web pattern used in industry (exact parameter table should be copied from docs when implementing):

```
https://api.map.baidu.com/direction?destination=latlng:LAT,LNG|name:NAME&mode=transit&region=CITY&output=html&src=webapp.arcademaps
```

App scheme family: `baidumap://map/direction?...` (**format details partially UNVERIFIED** in this pass; confirm against Baidu URI docs at implementation time).

### Recommended link-out set by region

| Region | Primary | Secondary | Tertiary |
| --- | --- | --- | --- |
| Japan / KR / TW / PH / SEA / US / EU | Google Maps `travelmode=transit` | Apple Maps `dirflg=r` | - |
| Mainland China | AMap `mode=bus` (+ show bemanicn `transport` text) | Baidu direction HTML | Google often weak/unusable on-device in CN |
| Global fallback | Google Maps destination pin (`query=lat,lng`) | - | - |

Do **not** call paid Directions/Routes APIs for a static free site. Link-out is enough.

Staleness: always pair scraped transport prose with date + "may be outdated".

---

## 7. User location / nearby search

### Standard static-site approach (**VERIFIED** industry standard + platform facts)

1. **`navigator.geolocation.getCurrentPosition`** on HTTPS (GitHub Pages is HTTPS - OK).
2. Permission UX:
   - Do not prompt on first paint.
   - Button: "Use my location" with short purpose text ("sort arcades nearest you; stays on your device").
   - On deny/error: fall back to manual search.
3. **Client-side Haversine** over 6-12k points: trivial in plain JS (no library). Precompute nothing; O(n) once per locate is fine.
4. Optional IP geolocation: free IP APIs exist but are imprecise and often need keys; **not required**. Prefer manual city/address search.

### Nominatim (OSM geocoding) for "search near an address"

**VERIFIED** [OSMF Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/):

- **Max 1 request per second** absolute; heavy/bulk closer to 4 req/min.
- Valid identifying User-Agent or Referer required (not a stock library UA).
- **No autocomplete** (including client-side autocomplete against the public API).
- Cache identical queries; attribute OSM.
- Limits apply per app across all users - a viral autocomplete widget would get the site blocked.

For a low-traffic arcade map: a single geocode on form submit (debounced, no autocomplete) with UA like `ArcadeMaps/1.0 (https://...; contact@...)` is policy-compatible. Better long-term: self-host Nominatim or use a commercial geocoder if traffic grows.

### Nearby algorithm sketch

```
if geolocation OK -> (lat,lng)
else if user geocoded a place -> (lat,lng)
else -> skip distance sort

for each arcade with coords:
  d = haversine(user, arcade)
return top N sorted by d
```

No backend. No paid Places Nearby Search required.

---

## What was NOT fully verified

- Exhaustive bemanicn field value distributions across all ~3.8k shops (only shop id=1 full detail + scraper code review).
- ZIv picture hosting ToS / hotlink permanence for all countries; JP series payload size with pictures enabled.
- Google Enterprise exact USD list prices beyond free thresholds (pricing list page structure varies; free thresholds VERIFIED on mapsplatform.google.com/pricing).
- Baidu URI query parameter table line-by-line (docs page loaded; copy params at implement time).
- Round1 public price-page structure per store.
- Mapillary/Wikimedia hit-rate for the full arcade set.
- Foursquare JP/CN arcade match rate live search (pricing VERIFIED; coverage UNVERIFIED).

---

## RECOMMENDATION (one page)

### Feasible free-tier, static-friendly (do these)

1. **Expand bemanicn scraper** to keep `transport`, `price`, `pay_type`, hours, `comment` (strip/sanitize HTML), `image_thumb` (re-resolve weekly; store scraped_at), `fav_count`, per-title `coin`/`eacoin`/`version`/`comment`. Label transport + prices as community data that may be outdated.
2. **Expand ZIv scraper** (selectively) to stop skipping pictures/comments for priority countries, and map machine `displayPrice`/`pricing`/`price`/`freePlay`/`condition` plus venue `website`/`openingTimes`/`information`. Expect larger artifacts; consider `skip_pictures=0` only for PH/US/JP or only when `lastUpdateTime` is recent.
3. **Bake FX weekly** via Frankfurter (fallback open.er-api.com) into `data/fx_rates.json`; convert displayed local prices to USD/JPY/HKD/CNY client-side.
4. **Pricing model:** optional per-arcade structured field + per-country defaults with `"typical": true` + manual overrides file. Prefer ZIv/bemanicn when present.
5. **Directions:** deep links only (Google/Apple globally; AMap/Baidu in CN) + bemanicn transport text with date stamp.
6. **Nearby:** geolocation button + Haversine; optional Nominatim single-shot geocode (no autocomplete) with proper UA/attribution.

### Need owner API key + billing decision

- **Google Places ratings + photos:** only as **session-only client fetch** with referrer-restricted key, Enterprise free caps (1k/SKU/month), full attribution, **no** weekly cache of ratings/photos. Expect free tier to exhaust around 1k detail+photo views/month. Scraping Google is out of scope forever.
- Foursquare/Yelp: not recommended (cost + geography).

### Link-outs (no data storage)

- Google Maps / Apple Maps directions.
- AMap / Baidu for China.
- ZIv arcade page, bemanicn shop page, official chain pages (Round1, GiGO, etc.).
- Optional Mapillary/OSM links.

### Community / manual

- Country default credit prices (JP 100 yen norm, etc.).
- Chain token systems (Quantum PHP tokens, Round1 standard) as curated defaults.
- Any star rating system you own (user submissions) would need a backend you do not have - skip or use external forms.

### Explicit non-goals for v1 enrichment

- Baking Google ratings/reviews/photos into `arcades.json`.
- Paid Routes/Directions APIs.
- Yelp for Asia.
- Nominatim autocomplete.
- Scraping Google/Apple/Amap tile or place pages.

### Suggested implementation order

1. FX bake + display helpers.  
2. bemanicn transport/price/coin/hours/thumb fields.  
3. ZIv machine pricing free-text + optional pictures for one pilot country.  
4. Directions link-out buttons by region.  
5. Geolocation nearby sort.  
6. (Optional, owner billing) Google session rating badge.

---

*End of report.*
