# Arcade Maps

[![Last data update](https://img.shields.io/github/last-commit/JonathanLiu1401/Arcade-Maps?label=last%20data%20update)](https://github.com/JonathanLiu1401/Arcade-Maps/commits)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Worldwide rhythm game arcade locations on one interactive map. Arcade Maps tracks where you can play CHUNITHM, maimai DX, ONGEKI, SOUND VOLTEX, beatmania IIDX, DanceDanceRevolution, Polaris Chord, GITADORA, jubeat, pop'n music, Nostalgia, DANCERUSH STARDOM, DANCE aROUND, Project DIVA Arcade, and community-tracked games including Taiko no Tatsujin. The data is rebuilt automatically from official operator sources (SEGA ALL.Net, Konami e-amusement, WAHLAP) plus the Zenius-I-Vanisher and BemaniCN community databases, committed to this repo on a weekly schedule, and served as a fast static Leaflet map on GitHub Pages.

## Live map

**https://jonathanliu1401.github.io/Arcade-Maps/**

![Arcade Maps site](docs/screenshot.png)

## Features

- One map, every game: per-game layer toggles with marker clustering, so you can show only the cabs you care about
- Official-source data: SEGA ALL.Net, Konami eagate facility search, and WAHLAP (China) are scraped directly, not copied from other maps
- Community coverage where official sources stop: Zenius-I-Vanisher fills in worldwide arcades (68 countries at the last pull), Taiko, and offline cabs for retired games
- Real coordinates: SEGA and Konami publish exact lat/lng; China points are datum-corrected (GCJ-02 to WGS-84) before plotting
- Automated freshness: a GitHub Action re-scrapes weekly and commits the diff, so the badge above tells you exactly how stale the data is
- Google My Maps export: numbered KMZ layers in `mymaps/` let you rebuild the classic My Maps experience in your own Google account (see [docs/MYMAPS.md](docs/MYMAPS.md))
- No backend, no API keys: static HTML + vendored Leaflet 1.9.4 + Leaflet.markercluster 1.5.3 on GitHub Pages, OpenStreetMap raster tiles

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
| WAHLAP official REST (sega-register.wahlap.net) | maimai DX CN (3125 stores at last refresh), CHUNITHM CN (581) | Mainland China | No (addresses only; optional geocoding) | WAHLAP scraper, weekly Action |
| Zenius-I-Vanisher community DB | Everything the community tracks, incl. Taiko and offline cabs of retired games (DIVA, MUSECA, REFLEC BEAT, DanceEvolution) | Worldwide, 68 countries at last pull | Yes (community-pinned) | ZIv JSON API, weekly Action |
| Round1 USA (Storepoint API) | Standard Round1 rhythm lineup (assumed per chain standard, not per-store verified) | United States | Yes | Round1 scraper, weekly Action |
| BemaniCN community map (map.bemanicn.com) | Community-tracked China listings: maimai DX, CHUNITHM, Taiko, and the wider Bemani lineup, with per-store game lists | Mainland China (392 city indexes) | No (public Inertia endpoints publish addresses + game lists; the coordinate map layers are login-only) | BemaniCN scraper, weekly Action |

Deep per-source detail (exact URLs, parse markers, caveats): [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Known gaps

- **BemaniCN coordinates are login-walled.** map.bemanicn.com's community China listings ARE included (via its public Inertia endpoints: addresses + per-store game lists), but the site's coordinate map layers require a login, so BemaniCN entries ship address-only unless they merge with a coordinate-bearing source (official WAHLAP twin, or ZIv coordinate inheritance). They appear in the site's No-coords list and in `mymaps/china_all_addresses.csv`.
- **CHUNITHM US:** SEGA's ALL.Net locator currently lists zero official CHUNITHM locations in the US. US CHUNITHM cabs appear only via community sources (ZIv) and the Round1 lineup assumption.
- **Konami overseas:** the eagate facility search is Japan-only, so overseas Bemani cabs (US Round1, Asia, Europe) come only from ZIv / community data.
- **Near-extinct games:** Project DIVA Arcade, MUSECA, REFLEC BEAT, and DanceEvolution have almost no surviving official listings; they are tracked mostly through ZIv offline-cab records.
- Listings lag reality in both directions: stores close, cabs move, and official locators update on their own schedule.

## Update cadence

A GitHub Action re-runs every scraper weekly (Monday 18:00 UTC, plus manual `workflow_dispatch`) and auto-commits changed data files with a bot identity. The "last data update" badge above reflects that commit.

## Repository layout

```
Arcade-Maps/
|- index.html            interactive map (GitHub Pages entry point)
|- app.js, style.css     map logic and styling
|- vendor/               vendored Leaflet 1.9.4 + markercluster 1.5.3
|- data/                 merged JSON (arcades, stats, merge log), auto-committed weekly
|- data_raw/             per-source scraped rows, auto-committed weekly
|- scrapers/             per-source scrapers (ALL.Net, eagate, WAHLAP, BemaniCN, ZIv, Round1)
|  |- run_all.py         run the full pipeline (scrape -> merge -> mymaps)
|  |- build_mymaps.py    regenerate the Google My Maps KMZ/CSV layers
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
- [Leaflet](https://leafletjs.com/) and [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) - the map engine
- [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors - base map tiles
- The [Zenius-I-Vanisher](https://zenius-i-vanisher.com/) community - decades of worldwide arcade tracking

## License and disclaimer

Code in this repository is MIT licensed (see LICENSE). Location data belongs to the respective operators (SEGA, Konami, WAHLAP) and community maintainers; it is republished here for player convenience only. Listings can lag reality: stores close, machines move, and hours change. Verify with the venue before traveling any distance to play.
