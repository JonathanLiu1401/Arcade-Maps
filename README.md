# Arcade Maps

## **[Open the live map](https://jonathanliu1401.github.io/Arcade-Maps/)**

[![Last data update](https://img.shields.io/github/last-commit/JonathanLiu1401/Arcade-Maps?label=last%20data%20update)](https://github.com/JonathanLiu1401/Arcade-Maps/commits)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Worldwide rhythm game arcade locations on one interactive map. Arcade Maps tracks where you can play CHUNITHM, maimai DX, ONGEKI, SOUND VOLTEX, beatmania IIDX, DanceDanceRevolution, Polaris Chord, GITADORA, jubeat, pop'n music, Nostalgia, DANCERUSH STARDOM, DANCE aROUND, Project DIVA Arcade, and community-tracked games including Taiko no Tatsujin. The data is rebuilt automatically from official operator sources (SEGA ALL.Net, Konami e-amusement, WAHLAP) plus the Zenius-I-Vanisher and BemaniCN community databases, committed to this repo on a weekly schedule, and served as a fast static Leaflet map on GitHub Pages.

**Current dataset (last rebuild):** 13,512 arcades across 68 countries (191 cross-source duplicates were unified by romanization-aware matching, so a Japanese official listing and its romaji community twin now share one pin, and a further 150 where two sources geocoded the same venue hundreds of metres apart - ALL.Net's fullwidth "アミューズメントパークＭＧ西条" and e-amusement's "アミューズメントパークMG西条店" were one store drawn as two icons). Sources include SEGA ALL.Net, Konami eagate, WAHLAP China, BemaniCN, Round1 USA, and Zenius-I-Vanisher (65 country queries, plus a United States per-series crawl that also tracks Pump It Up / ITG / StepManiaX and related cabs under `other`).

## Live map

**https://jonathanliu1401.github.io/Arcade-Maps/**

![Arcade Maps site](docs/screenshot.png)

## Features

- One map, every game: per-game layer toggles with marker clustering, so you can show only the cabs you care about
- One search box for three things: type a game (`iidx`, `舞萌`) to switch that filter on, a store name to fly to it, or a city (`Osaka`, `大阪`) to zoom to its arcades. Japanese, Chinese and romaji all match
- Store detail panel: click any marker and a full-height panel (a drag-to-expand bottom sheet on phones) opens with the store's games and per-game cab counts, address, source badges, notes, and buttons for directions, share-this-store link, and nearby
- Nearby search: the locate button (or any store's Nearby button) ranks the closest arcades by great-circle distance with a compass bearing, and honours whatever game, cab and source filters are active
- Settings you keep: turn individual data sources off, flatten the marker size ramp so every icon draws at 25px (the tier shapes stay), and disable location features entirely. Choices persist per device in localStorage and never travel in a shared link. The on-map legend is a click-to-expand chip, not a setting
- Tiered kawaii markers: each store draws one of six original chibi-style icons by total cabinet count (note, button pad, star, cat-ear chibi at 20-49 cabs, crowned idol at 50+, and a "?" pad when no source publishes a count). Each icon is tinted by the store's game colour, tiers only use counts a source actually reported, and at the deepest zoom a stacked bundle fans out (spiderfies) when you click it, so overlapping stores stay clickable
- Cab photos in the detail panel: a CC-licensed photo of that game's cabinet from Wikimedia Commons (with the required author/license credit rendered on the image), otherwise a game-colour banner. The panel prefers a store's own photo, but no source ships one today
- Resizable sidebar: drag the panel edge to any width (double-click resets), remembered per device
- Shareable URLs: the hash carries the map view plus selected games and cabs, and the Share button adds the exact store, so a link reopens on what you were looking at
- Official-source data: SEGA ALL.Net, Konami eagate facility search, and WAHLAP (China) are scraped directly, not copied from other maps
- Community coverage where official sources stop: Zenius-I-Vanisher fills in worldwide arcades (65 countries queried at the last pull), Taiko, offline cabs for retired games, and US extra series (Pump It Up, In The Groove, StepManiaX, and related titles) tracked under Other
- Machine counts where sources report them: BemaniCN per-title quantities and ZIv machine-list tallies land in optional `game_counts` (about 30% of merged arcades; BemaniCN raw coverage is ~94% of its shops). ZIv counts are only kept when a store's list repeats a machine title - a ZIv page lists what is there rather than how many, so every game shows as "1" and two versions of one game show as "2", and neither is a quantity the site actually published. Those are dropped rather than shown as "x1". Each counted arcade records which source the numbers came from in `counts_src`
- Community enrichment: `data/enrichment.json` covers 6,521 of the 13,512 arcades, and every row in it comes from ZIv - opening hours (5,211 arcades), venue info text (4,207), a website (4,092), and free-text machine prices per game (2,413), plus country-level typical-price defaults. Weekly USD FX rates come from Frankfurter (ECB) with open.er-api.com gap-fill, so the site can show a local price and a converted estimate. `scrapers/enrich.py` also parses the BemaniCN fields (transit prose, venue coin/token price, per-title coins per play, game versions, photo thumbnails, favourite counts), but no BemaniCN row has landed in the shipped file yet
- Directions: every store links out to Google Maps, by coordinate when it has one and by name + address search when it does not
- Approximate China placement: coordinate-less mainland China stores are placed at the centre of the **district** their address names (city centre only when it names no district), stacked on that point rather than scattered around it. See the China accuracy disclosure below
- Automated freshness: a GitHub Action re-scrapes weekly and commits the diff, so the badge above tells you exactly how stale the data is
- Google My Maps export: numbered KMZ layers in `mymaps/` let you rebuild the classic My Maps experience in your own Google account (see [docs/MYMAPS.md](docs/MYMAPS.md))
- No backend, no API keys: static HTML + vendored Leaflet 1.9.4 + Leaflet.markercluster 1.5.3 on GitHub Pages, OpenStreetMap raster tiles

## China accuracy disclosure

**Mainland China marker positions are approximate, not street-accurate.**

Every Chinese primary source used here (WAHLAP's official venue API and BemaniCN's public Inertia shop endpoints) publishes store **addresses without coordinates**. BemaniCN's map layers that carry lat/lng are login-walled. Exact WGS-84 positions for those stores are therefore unavailable to this project.

What the map does instead:

1. Prefer a real coordinate when one exists (ZIv community pin, or a WAHLAP/BemaniCN row that merged with a coordinate-bearing twin).
2. Otherwise read the address as far down the administrative chain as `data/china_areas.json` goes and place the store at that unit's centroid: the **district** (区/县) where the address names one, the prefecture-level **city** where it does not. Mark the entry `approx: true` and record which level was used in `approx_level`.
3. Place every such store on that centroid **exactly**. Stores sharing an area stack into one cluster badge and fan out only when you click it, because that is what the data supports: an earlier revision spread them over a 600 m circle, which made a district-wide guess look like a street address.

**Addresses remain authoritative.** For navigation, copy the address into a local map app (AMap, Baidu Maps, Apple Maps, Google Maps) rather than trusting the pin.

At the last rebuild this affected **5625 of 6482 China entries** (`approx: true`): **4064 at district level** and 1561 at city level. About 621 China entries have real (non-approx) coordinates, and 236 remain coordinate-less because no city could be resolved. Taiwan, Hong Kong and Macau are never approximated (ZIv, ALL.Net and e-amusement cover them with real pins).

District is as far as free data reaches: the upstream release publishes 乡镇/街道 boundaries only as a paid asset.

**Street-level is available but opt-in.** `scrapers/geocode_cn.py` geocodes the printed addresses through AMap or Google and commits the answers to `data/china_geocode.json`, which merge then prefers over any centroid. It is off in this repo: it needs an API key, so with no key set it fetches nothing, writes nothing and cannot fail a build. To turn it on, add `AMAP_KEY` (or `GOOGLE_MAPS_API_KEY`) to the repository secrets and run `python scrapers/run_all.py --skip-scrape --only geocode`, then re-merge. Only rooftop and street answers are taken; a provider's vaguer "area" guess is discarded in favour of the district centroid, which at least comes with a level attached.

## Quick start

**Just browse:** open the [live map](https://jonathanliu1401.github.io/Arcade-Maps/), toggle game layers, click a marker for the store name, address, and game list.

**Use it in Google My Maps:** import the numbered `mymaps/01_*.kmz` ... `10_*.kmz` files as layers into a new map at https://www.google.com/maps/d/. Full walkthrough: [docs/MYMAPS.md](docs/MYMAPS.md).

**Run the scrapers yourself:**

```
git clone https://github.com/JonathanLiu1401/Arcade-Maps.git
cd Arcade-Maps
python scrapers/run_all.py                 # scrape all sources, merge into data/, rebuild mymaps/
python scrapers/run_all.py --skip-scrape   # re-merge + rebuild from existing data_raw/ (no network)
```

The scrapers are stdlib-only (Python 3.12 or newer); there is nothing to pip install. Please keep the built-in politeness settings (sequential fetching, delays between requests) if you run the scrapers. Details per source: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Data sources

| Source | Games | Coverage | Coordinates | Refresh path |
|---|---|---|---|---|
| SEGA ALL.Net (location.am-all.net) | maimai DX JP + International (gm 96 / 98), CHUNITHM JP + International (gm 109 / 104), ONGEKI (gm 88), Project DIVA Arcade (gm 34) | Japan (47 prefectures via ct=1000) + 15 international country codes | Yes (official) | ALL.Net scraper, weekly Action |
| Konami eagate facility search (p.eagate.573.jp) | 20 game keys: IIDX, SDVX, DDR, GITADORA (GF/DM), jubeat, pop'n, Nostalgia, DANCERUSH, DANCE aROUND, Polaris Chord (PLRS), MUSECA, REFLEC BEAT, DanceEvolution, and cab variants (SDVX Valkyrie, IIDX Lightning, DDR gold cab, plus Arena and Pikapika variants) | Japan only (verified live: the facility search exposes no overseas listings) | Yes (official, `data-latitude` / `data-longitude`) | eagate scraper, weekly Action |
| WAHLAP official REST (sega-register.wahlap.net) | maimai DX CN, CHUNITHM CN (3,207 merged source rows at last refresh) | Mainland China | No (addresses only; district-centroid approx placement in merge) | WAHLAP scraper, weekly Action |
| Zenius-I-Vanisher community DB | Everything the community tracks, incl. Taiko, offline cabs of retired games, and US extra series (Pump It Up / ITG / StepManiaX / etc. under `other`) | Worldwide, 65 country queries at last pull (6,953 merged source rows) | Yes (community-pinned) | ZIv JSON API, weekly Action |
| Round1 USA (Storepoint API) | Standard Round1 rhythm lineup (assumed per chain standard, not per-store verified) | United States | Yes | Round1 scraper, weekly Action |
| BemaniCN community map (map.bemanicn.com) | Community-tracked China listings: maimai DX, CHUNITHM, Taiko, and the wider Bemani lineup, with per-store game lists and per-title machine counts (3,567 shops) | Mainland China (392 city indexes; 3,802 merged source rows) | No (public Inertia endpoints publish addresses + game lists; the coordinate map layers are login-only; district-centroid approx placement in merge) | BemaniCN scraper, weekly Action |

Deep per-source detail (exact URLs, parse markers, caveats): [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Known gaps

- **China coordinates are approximate or missing.** WAHLAP and BemaniCN publish addresses without lat/lng. Most China pins are district (or city) centroids (`approx: true`); a minority inherit real pins from ZIv merges. See the China accuracy disclosure above.
- **BemaniCN map layers are login-walled.** Public endpoints give addresses + game lists + per-title machine counts; exact coordinates still require a login the scraper does not use. The shop detail pages also expose transit prose, prices, hours and thumbnails, but the crawl behind the shipped `data_raw/china_bemanicn.json` captured none of them, so `data/enrichment.json` currently holds zero BemaniCN rows.
- **CHUNITHM US:** SEGA's ALL.Net locator currently lists zero official CHUNITHM locations in the US. US CHUNITHM cabs appear only via community sources (ZIv) and the Round1 lineup assumption.
- **Konami overseas:** the eagate facility search is Japan-only, so overseas Bemani cabs (US Round1, Asia, Europe) come only from ZIv / community data.
- **Near-extinct games:** Project DIVA Arcade, MUSECA, REFLEC BEAT, and DanceEvolution have almost no surviving official listings; they are tracked mostly through ZIv offline-cab records.
- Listings lag reality in both directions: stores close, cabs move, and official locators update on their own schedule. Community prices, hours, and venue notes can be outdated; check `enriched_at` where shown.

## Update cadence

A GitHub Action re-runs every scraper weekly (Monday 18:00 UTC, plus manual `workflow_dispatch`) and auto-commits changed data files with a bot identity. The "last data update" badge above reflects that commit.

## Repository layout

```
Arcade-Maps/
|- index.html            interactive map (GitHub Pages entry point)
|- js/                   map logic, one plain script per module, loaded in
|                        dependency order (see docs/ARCHITECTURE.md):
|  |- state.js           constants, helpers, loaded data, the state store
|  |- format.js          distance / count / money / FX formatting
|  |- mapcore.js         Leaflet map, panes, URL hash sync
|  |- tier-icons.js      GENERATED tier artwork strings (tools/build_tier_icons.py)
|  |- markers.js         cluster layer, visibility predicate, tier icons, spiderfy
|  |- search.js          omnibox over games, arcades and places
|  |- panel.js           filter drawer, no-coords tab, store detail panel
|  |- settings.js        settings dialog, source toggles, legend chip
|  |- nearby.js          locate control and nearest-arcades list
|  |- app-init.js        fetch, seed state, build and start every module
|- style.css             styling
|- vendor/               vendored Leaflet 1.9.4 + markercluster + SmoothWheelZoom
|- assets/               favicon, tier marker SVGs, CC-licensed cab photos (+ attribution)
|- data/                 merged JSON (arcades, stats, enrichment, fx rates, china cities, merge log), auto-committed weekly
|- data_raw/             per-source scraped rows, auto-committed weekly
|- scrapers/             per-source scrapers + merge / geo_validate / china_place / enrich / fx
|  |- run_all.py         run the full pipeline (scrape -> merge -> mymaps -> fx)
|  |- guard_regression.py  block a commit when a crawl shrinks implausibly
|  |- build_mymaps.py    regenerate the Google My Maps KMZ/CSV layers
|- tools/
|  |- build_tier_icons.py  embed assets/markers/*.svg into js/tier-icons.js
|  |- stamp_assets.py    content-hash ?v= stamps on the css/js in index.html
|- mymaps/               numbered KMZ layers for My Maps import (+ README)
|- docs/
|  |- ARCHITECTURE.md    pipeline, data schema, design decisions
|  |- DATA_SOURCES.md    per-source URLs, parse markers, caveats
|  |- MYMAPS.md          Google My Maps import walkthrough
|  |- UPDATING.md        weekly Action details + manual refresh guide
|- .github/workflows/    weekly scrape + auto-commit Action, manual smoke test
|- README.md
|- LICENSE
```

## Credits

Prior art studied while designing this project (protocols and recipes, no code copied from unlicensed repos):

- [bemusicscript/gcm-storefinder](https://github.com/bemusicscript/gcm-storefinder) - ALL.Net scraping recipe + Leaflet/markercluster static-site pattern
- [hker9527/otoge-locator](https://github.com/hker9527/otoge-locator) - daily-cron + auto-commit architecture proof
- [djzmo/otoge-app](https://github.com/djzmo/otoge-app) - multi-source scraper suite, eagate facility-search recipe
- [Naptie/nearcade](https://github.com/Naptie/nearcade) (MPL-2.0) - China data-source landscape and demand validation
- [googollee/eviltransform](https://github.com/googollee/eviltransform) (BSD-2-Clause) - GCJ-02 / BD-09 to WGS-84 conversion, vendored
- [xiangyuecn/AreaCity-JsSpider-StatsGov](https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov) (MIT) - China province / city / district centroids underlying `data/china_areas.json`
- [Leaflet](https://leafletjs.com/) and [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) - the map engine
- [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors - base map tiles
- [Frankfurter](https://www.frankfurter.app/) / ECB reference rates - weekly FX bake
- The [Zenius-I-Vanisher](https://zenius-i-vanisher.com/) community - decades of worldwide arcade tracking

## License and disclaimer

Code in this repository is MIT licensed (see LICENSE). Location data belongs to the respective operators (SEGA, Konami, WAHLAP) and community maintainers; it is republished here for player convenience only. Listings can lag reality: stores close, machines move, and hours change. China map pins that carry `approx: true` are district-level or city-level only (see the China accuracy disclosure). Verify with the venue before traveling any distance to play.
