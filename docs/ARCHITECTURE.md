# Architecture

## Pipeline

```mermaid
flowchart LR
  allnet["SEGA ALL.Net<br>location.am-all.net"] --> run
  eagate["KONAMI e-amusement<br>p.eagate.573.jp"] --> run
  wahlap["WAHLAP<br>sega-register.wahlap.net"] --> run
  bemanicn["BemaniCN<br>map.bemanicn.com Inertia"] --> run
  ziv["Zenius-I-Vanisher<br>arcades.php API"] --> run
  round1["Round1 USA"] --> run
  run["scrapers/run_all.py"] --> raw[("data_raw/<br>per-source raw output")]
  raw --> merge["merge: dedupe, slug mapping,<br>gcj2wgs conversion"]
  merge --> geov["geo_validate:<br>bbox country vs coords"]
  geov --> china["china_place:<br>city centroids + approx"]
  china --> canon[("data/arcades.json<br>+ stats.json")]
  china --> enrich["enrich:<br>join raw extras by URL"]
  enrich --> enj[("data/enrichment.json")]
  canon --> site["index.html + js/*.js<br>static Leaflet page"]
  enj --> site
  fxstep["fx.py<br>Frankfurter + fallback"] --> fxj[("data/fx_rates.json")]
  fxj --> site
  canon --> builder["mymaps builder"]
  builder --> exports[("mymaps/<br>KMZ / CSV exports")]
```

One weekly GitHub Action (see `docs/UPDATING.md`) runs scrape -> merge (including geo validation, China approx placement, and enrichment) -> My Maps rebuild -> FX bake, then commits the results. The static site is a pure function of `data/arcades.json` plus on-demand `data/enrichment.json` and `data/fx_rates.json`. FX failure is non-fatal (previous rates retained).

### Merge stage order (inside `scrapers/merge.py`)

1. Load raw units, within-source dedupe, supersede bundled `community.json` rows when fresh files exist
2. Cross-source cluster / merge, optional coordinate inheritance
3. Assign sequential ids after sort by country, name, address
4. **`geo_validate`** - source-aware country vs bounding-box checks (official: null bad geocodes; community: fix wrong country labels)
5. **`china_place`** - for remaining coordinate-less China rows, resolve city centroid from `data/china_cities.json`, jitter cosmetically, set `approx: true` (never overwrites a real pin; never places Taiwan from this table)
6. Write `data/arcades.json` + `data/stats.json`
7. **`enrich.build_enrichment`** - join raw BemaniCN/ZIv extras onto merged ids via `links.*` URLs; write `data/enrichment.json` (does not mutate arcade rows)
8. Write `data/merge_log.json` (includes `geo_validation` and `china_approx` logs)

After merge returns, `run_all.py` rebuilds My Maps, then runs `fx.run` into `data/fx_rates.json`.

## Schema reference: `data/arcades.json`

```
{"updated": "2026-07-28",
 "counts": {"total": int,
            "by_game": {slug: int},
            "by_source": {src: int},
            "by_country": {country: int}},
 "arcades": [
  {"id": int (sequential after sorting by country,name,addr;
   renumbered on each refresh),
   "name": str,
   "addr": str (original language),
   "lat": float|null,
   "lng": float|null (WGS-84 ONLY; convert gcj02 via embedded
          eviltransform gcj2wgs before writing; (0,0) or missing
          means null). For China rows with approx:true these are
          city-centroid coordinates with cosmetic fan-out, NOT
          street-accurate pins,
   "country": str (English: "Japan","China","Taiwan","United States",...),
   "pref": str|null (JP prefecture / CN province / US state where known,
           original language ok),
   "games": [slug array, non-empty],
   "game_counts": {slug: int} (OPTIONAL - key absent when unknown;
          per-game machine counts, present only where a source
          reported them: BemaniCN per-title quantities and ZIv
          machine-list tallies, merged as per-slug max; every counted
          slug also appears in games; official sources publish no
          counts, so a store can list games without counts),
   "counts_src": "bemanicn"|"ziv"|null (OPTIONAL - present only when
          some source reported counts for this arcade. Names which
          source the surviving game_counts came from; BemaniCN wins
          when both contributed. null means counts existed but were
          ZIv placeholders (every per-game tally == 1, which is ZIv's
          baseline one-row-per-game-version shape rather than a real
          quantity) and were DROPPED, so game_counts is absent and
          nothing renders as "x1". ZIv counts survive only when some
          slug is >= 2, which proves the list was really tallied. Key
          absent entirely = no source ever counted this arcade, which
          is distinct from a suppressed placeholder.
          Invariant: game_counts present <=> counts_src is non-null.
          Dropping counts never drops games),
   "cabs": [variant slugs among: sdvx_vm, iidx_lm, ddr_gold,
            gitadora_gf_arena, gitadora_dm_arena, popn_pikapika],
   "src": [ids among: allnet, eagate, wahlap, ziv, round1usa,
           bemanicn, community],
   "links": {"gmaps": str|null, "ziv": str|null, "bemanicn": str|null},
   "notes": str|null,
   "approx": true (OPTIONAL - present only when china_place assigned
          a city-centroid pin; never set on real / inherited coords)}
 ]}
```

### `approx` field semantics

- Present and `true` only after successful city-centroid placement.
- Means: "somewhere in this city (or municipality district), addresses authoritative; pin is not a surveyed storefront."
- Fan-out offset is deterministic from name+address (not id) so weekly renumbering does not jump pins, and is purely cosmetic.
- Entries that stay coordinate-less have no `approx` key and `lat`/`lng` null (sidebar / no-coords list).
- `links.gmaps` for those rows stays a name+address search URL; merge deliberately does not rewrite it to the centroid pin.

### Game slugs (canonical, used by the site layers too)

`maimai_dx, chunithm, ongeki, project_diva, sdvx, iidx, ddr,
polaris_chord, gitadora, jubeat, popn, nostalgia, drs, dance_around,
dance_evo, museca, reflec, taiko, other`

### Source-to-slug mapping

- `maimai_jp` + `maimai_intl` + WAHLAP `maidx` -> `maimai_dx`
- `chunithm_jp` + `chunithm_intl` + WAHLAP `midtr` -> `chunithm`
- `gitadora_gf` / `gitadora_dm` (+ arena variants) -> `gitadora`, with
  the arena variants recorded in `cabs`
- `sdvx_vm` implies game `sdvx` + cab `sdvx_vm`
- `iidx_lm` implies game `iidx` + cab `iidx_lm`
- `ddr_gold` implies game `ddr` + cab `ddr_gold`
- `popn_pikapika` implies game `popn` + cab `popn_pikapika`
- US ZIv extra series (Pump It Up, ITG, StepManiaX, etc.) map to `other` only

## Schema reference: `data/enrichment.json`

Kept **separate** from `arcades.json` so the file every visitor downloads on first paint stays lean. The frontend fetches enrichment on demand (detail panel / price display).

Rationale for the split:

- Free-text opening hours, venue info and per-machine price strings are bulky relative to name/address/coords, and the parsers can emit transit prose (BemaniCN) and photo URL lists (either source) on top of that when a crawl reaches them.
- Only about half of arcades have anything enrichable (6,523 of 13,681 in the current build); a sparse side file avoids null-padding 13k rows.
- Enrichment goes stale on a different clock from the arcade rows, so each entry carries its own `enriched_at` and the whole file can be replaced without touching `arcades.json`.

Shape (see also `scrapers/enrich.py` docstring and `docs/DATA_SOURCES.md` section 10):

```
{"updated": str,
 "price_defaults": {ISO2: {... typical country defaults ...}},
 "country_to_code": {country name: ISO2},
 "counts": {...},
 "arcades": {"<id>": {
    "hours_text", "info_text", "website", "machine_prices"
        (the ONLY four entry fields in the file as built; each is
         optional, and an arcade with none of them gets no entry),
    "sources": {field: "bemanicn"|"ziv"},
    "enriched_at": "YYYY-MM-DD"
 }}}
```

What ships today is ZIv-only: 6,523 of 13,681 arcades have an entry, with `hours_text` on 5,213, `info_text` on 4,209, `website` on 4,092 and `machine_prices` on 2,414, and every tag in `sources` reads `"ziv"`. `scrapers/enrich.py` also parses `transport`, `price_text`, `pay_type`, `hours`, `images`, `fav_count`, `game_prices` and `game_versions`. Of those the place panel actually renders `transport`, `hours`, `price_text`, `game_prices` and `images`; `pay_type`, `fav_count` and `game_versions` are parsed and stored but never displayed. Seven of the eight are BemaniCN-only, and `counts.bemanicn_rows_contributed` in the current file is 0 against 3,812 rows available. `images` is the exception: it can come from either source (BemaniCN `image_thumb` or ZIv `pictures`), but the committed ZIv crawl ran with `skip_pictures`, so no row carries a `pictures` key. The net effect is the same - no transit text, no image URL, no favourite count and no coin/token pricing on disk right now. Those fields are pipeline capability, not data the site can count on.

`hours_text` is ZIv's 7-day table rendered Mon-first. Days ZIv reports as zero-length (`["00:00","00:00",false]`, its shape for "nobody recorded this") are rejected rather than formatted, at two points: `scrapers/ziv.py` drops them when building the string, and `scrapers/enrich.py` `_clean_hours_text` drops them again per segment when copying, which cleans rows crawled before the fix. A venue with no recorded hours therefore has no `hours_text` at all rather than a fabricated `Mon-Sun 00:00-00:00`, and a venue with a partly filled week keeps only its real days. This mattered: 1,742 arcades, a quarter of the enrichment set, were publishing that fabricated string.

Join is by stable source URLs (`links.bemanicn` / `links.ziv`), not by fragile name matching, so enrichment does not need to participate in clustering.

## Schema reference: `data/fx_rates.json`

```
{"base": "USD",
 "date": "YYYY-MM-DD",
 "rates": {CODE: float, ...},
 "source": "frankfurter+open.er-api.com" | "frankfurter" | ...,
 "sources": {CODE: "frankfurter"|"open.er-api.com"|"base"},
 "fetched_at": "ISO-8601 Z"}
```

Client multiplies local price estimates by these rates. Missing exotic codes are gap-filled from the fallback feed; total failure leaves the previous file untouched.

## Frontend modules (`js/`)

No build step, no bundler, no framework. `index.html` loads vendored Leaflet
plus ten plain scripts, each an IIFE that hangs one namespace off the global
`AM` object. Everything is served exactly as it sits in the repo.

```mermaid
flowchart TD
  subgraph load["load order (index.html)"]
    direction TB
    state["state.js<br>AM.consts / AM.util / AM.data / AM.state"]
    format["format.js<br>AM.format - distance, counts, money, FX"]
    mapcore["mapcore.js<br>AM.map - Leaflet map, panes, URL hash"]
    tiericons["tier-icons.js<br>AM.tierIcons - generated tier SVG sources"]
    markers["markers.js<br>AM.markers - cluster, visibility predicate,<br>tier-icon sizes, halo"]
    search["search.js<br>AM.search - omnibox: games / arcades / places"]
    panel["panel.js<br>AM.panel - filter drawer, no-coords tab,<br>place panel + bottom sheet"]
    settings["settings.js<br>AM.settings - dialog, source toggles,<br>prefs, legend chip"]
    nearby["nearby.js<br>AM.nearby - locate control, haversine list"]
    init["app-init.js<br>fetch -> ingest -> build() -> start()"]
    state --> format --> mapcore --> tiericons --> markers --> search --> panel --> settings --> nearby --> init
  end

  store[("AM.state<br>selectedGames, selectedCabs,<br>enabledSources, selectedArcade,<br>shownCount, nearbyFrom,<br>markerScaling, locationEnabled")]

  markers -. subscribes .-> store
  search -. subscribes .-> store
  panel -. subscribes .-> store
  settings -. subscribes .-> store
  nearby -. subscribes .-> store
```

### Load-order invariant (do not "tidy" this)

`markers.js` captures `AM.format`, `AM.map.map` and `AM.tierIcons.SRC` into
locals at IIFE parse time, not lazily inside its functions. **`format.js`,
`mapcore.js` and `tier-icons.js` must therefore all be evaluated before
`markers.js`.** Reordering to the alphabetical-looking `state, mapcore,
markers, format, ...` was tried and measured: the page boots to `data load
failed`, 0 markers, no place panel and no settings gear, and because
`app-init.js` swallows the throw in its `.catch(fail)` the console stays
completely silent.

The `tier-icons.js` half of that ordering fails even more quietly. The capture
is defensive - `(AM.tierIcons && AM.tierIcons.SRC) || {}` - so loading
`tier-icons.js` after `markers.js` throws nothing at all. The artwork table is
just `{}`, every tier lookup misses, `tintedUrl` tints the empty string, and
each marker gets a data URL holding no SVG. The map draws, the cluster badges
count correctly, the console stays clean, and every marker is invisible. A
silent break is easy to reintroduce and this one leaves no evidence, so treat
this ordering as load-bearing.

### State-event contract

Modules never call each other's render functions. Each one reads from
`AM.state` and re-renders off state events, so a feature can be removed by
deleting its script tag without editing the others.

`state.set(key, value, meta)` normally no-ops when the value is unchanged.
`meta.focus` deliberately bypasses that guard: focusing a store is a command
("show me this"), not a state change, so re-picking the store you are already
on still flies, re-halos and re-opens the panel.

### Cross-module seams

| Seam | Written by | Reacted to by |
| --- | --- | --- |
| `selectedArcade` | marker click (cluster-level handler resolving `__amId`), omnibox arcade row, nearby row, no-coords row, `#arcade=` hash | `panel.js` opens the place panel; `markers.js` flies + halos when `meta.focus`; `nearby.js` steps aside for coordinate-less stores |
| `nearbyFrom` `{lat, lng, label}` | place panel Nearby button | `nearby.js` opens the list; optional listener, so nothing breaks if that module is absent |
| `enabledSources` | settings source toggles | `markers.js` re-filters, `nearby.js` re-ranks, `search.js` invalidates cached per-game counts |
| `selectedGames` / `selectedCabs` | filter chips, omnibox game row, URL hash | markers, nearby, search, panel chips |
| `markerScaling`, `locationEnabled` | settings prefs | `markers.js` `applyScale()` swaps each marker's `L.Icon` for the new tier size, then unspiderfies, because spiderfy leg geometry is derived from icon size; `nearby.js` adds or removes the locate control |

`#pane-nearby` overlays `#pane-filters` in the same left column, so the place
panel's back control is labelled from whichever surface is actually underneath
("Filters" or "Nearby") rather than from a fixed string.

Escape peels exactly one layer per press: the settings `<dialog>` is a native
modal in the browser's top layer and closes itself, so the place panel skips
its own Escape handler while that dialog is open.

### Marker tiers have one owner

`markers.js` exports `TIER_CLASSES`, `UNKNOWN_TIER`, `TIER_LEGEND` and
`tierIconUrl()`. Both legends (the on-map chip and Settings > About) render
their thresholds, their labels AND their artwork from those exports. Never
restate the bands as literals and never ship a stand-in shape - a hard-coded
copy had already drifted out of step with the real bands once.

Six tiers by total cabinets: T1 1-2, T2 3-9, T3 10-19, T4 20-49, T5 50+, and
TU for "count not published". Each is a different silhouette, so the tier is
readable without comparing sizes; the size ramp (20/24/26/30/36px, TU 25px) is
a reinforcing signal only, and the Display toggle flattens it to a uniform
25px without changing the shapes.

Unknown is deliberately mid-weight, never the smallest: most official listings
publish which games a store has but not how many cabinets, and drawing
"unknown" smallest would read as "this store is tiny". A tier is only computed
from `game_counts` when `counts_src` is a source whose quantities we trust
(`bemanicn`, or `ziv` where the merge kept a real count); everything else is
TU, so the counts-honesty policy has exactly one enforcement point.

### Asset URLs carry a content stamp

Every local CSS and JS URL in `index.html` ends in `?v=<8 hex>`, written by
`tools/stamp_assets.py` from a hash of the file's own bytes. Run it after
changing anything under `js/` or `style.css`; `--check` exits nonzero when a
stamp is stale.

This is not cosmetic. Pages caches assets for much longer than it caches
`index.html`, so without the stamp a returning visitor gets a FRESH page and a
STALE script, which is worse than an entirely stale page: the new markup loads
`js/tier-icons.js` (a new URL, so fetched) while the browser serves the old
`js/markers.js` from cache, and that old module ignores `AM.tierIcons`
completely. The map silently renders the previous marker style with nothing in
the console. That is exactly how the tier-icon release looked "not updated"
after it went live.

Data files are deliberately NOT stamped: their URLs are built in JavaScript,
and they change weekly rather than per release. `app-init.js`, `panel.js` and
`format.js` fetch them with `cache: "no-cache"`, which revalidates and takes a
cheap 304 when nothing changed, so a weekly data refresh is picked up without a
new page load.

### Tier artwork is generated, not hand-copied

The six SVGs under `assets/markers/` are the source of truth.
`tools/build_tier_icons.py` embeds them into `js/tier-icons.js` as strings and
checks the invariants the tint depends on (one `0 0 32 32` viewBox, a
`currentColor` region, no `color=` on the root `<svg>`, no `<text>`). Edit the
SVGs, then re-run the script - never edit the generated file.

They are embedded rather than fetched because `markers.js` builds icons
synchronously inside `build()`: it replaces `currentColor` with the store's
game colour and hands the result to `L.icon` as a data URL. A fetch would make
marker construction asynchronous and would not survive the fixed script order
in `index.html`. An externally referenced SVG cannot work at all here - it is a
separate document and inherits nothing, so `currentColor` would resolve to
black.

Markers are `L.marker` with image icons, not canvas `circleMarker`: the canvas
renderer can only draw geometry. Each `(tier, colour)` data URL is built once
and shared, so the browser decodes each of the at most 6 x 19 variants a single
time, and the artwork stays vector-crisp at `devicePixelRatio` 2.

## Design decisions

### Why a static Leaflet page instead of Google My Maps

- Performance: My Maps degrades beyond a few thousand pins; this dataset
  is ~14,000 arcades and growing. Leaflet.markercluster with
  `chunkedLoading` handles that comfortably.
- Import limits: My Maps caps imports at 2,000 rows per layer and 10
  layers per map, so the full dataset does not fit as one map without
  awkward splitting.
- No automation: My Maps has no API; every refresh would be a manual
  browser import. A static page redeploys itself from
  `data/arcades.json` on every data commit.
- My Maps is still supported as a manual export target: the mymaps
  builder emits per-game KMZ/CSV files under `mymaps/`, each kept under
  the 2,000-row limit, for people who prefer the Google Maps app.

### Why not a claude.ai artifact

Artifacts run under a strict Content-Security-Policy that blocks all
requests to external hosts, including tile servers. A slippy map with no
basemap tiles is useless, so the site is a normal static page (GitHub
Pages) that may load OpenStreetMap tiles under the OSMF tile policy.

### Why conservative cross-source merging

The same arcade appears in multiple sources with different names
("Round1 Yokohama" vs a katakana name vs a ZIv nickname), different
address formats, and slightly different coordinates. A wrong merge is
worse than a duplicate: it silently attaches one store's game list to
another store and is hard to spot. So the merger only unifies entries on
strong evidence (very close coordinates plus name/address agreement) and
otherwise keeps both entries. Merged entries list every contributing
source in `src`. Expect some residual duplicates; that is by design.

### Why a fresh scrape supersedes the bundled community rows

`data_raw/community.json` is a committed bundle that carries rows from
three sources at once (`ziv`, `round1usa`, and a few curated
`community` entries). When a per-source scraper writes its own fresh
file (`data_raw/ziv.json`, `data_raw/round1usa.json`), the merger skips
that source's rows inside `community.json` and takes only the fresh
file. Without this the two copies of ZIv would BOTH load: the same
arcade is spelled differently between them (the API's address parts are
joined differently now, e.g. `"1 Old St, Tokyo"` vs
`"1 Old St Tokyo, Tokyo"`), so the within-source dedupe key
`(source, name, addr)` does not collapse them: only 3 of the bundle's
4,682 ZIv rows share a key with `ziv.json`'s 6,986, so ZIv would go
from 6,969 deduped source units to 11,647.

The skip is keyed on the ROW's `source` field, not on the file, so
`round1usa` and curated `community` rows inside `community.json` are
still ingested; and it only engages when the fresh file actually
exists, so a checkout without it still gets the bundled rows. The count
of superseded rows is written to `data/merge_log.json` as
`community_rows_superseded`.

### Why China entries use approx city centroids (and still can be coordinate-less)

The official WAHLAP endpoint returns name, address, province, and
machine count but NO coordinates, and BemaniCN's public endpoints are
addresses + game lists only (its coordinate layers are login-walled).
Commercial Chinese geocoders need API keys, quotas, and still return
GCJ-02. Rather than leave ~5.9k China stores invisible, `china_place`
assigns **city-level** WGS-84 centroids from `data/china_cities.json` and
marks them `approx: true`. Unresolved rows keep `lat`/`lng` = null and
appear in the no-coords list. Addresses remain authoritative for
navigation. See the README China accuracy disclosure.

### GCJ-02 in one paragraph

Chinese regulations require consumer map services in China (AMap,
Tencent, and anything geocoded through them) to use GCJ-02, a datum that
applies a deterministic pseudo-random offset to true WGS-84 positions
("Mars coordinates"). Plotting GCJ-02 values on an OSM basemap (which is
WGS-84) lands markers roughly 100-700 m off. The pipeline therefore
converts any GCJ-02-sourced coordinate with the vendored eviltransform
`gcj2wgs` before writing `data/arcades.json`, guarded by
`outOfChina` so non-China points are never double-converted. The
`china_cities.json` table is pre-converted the same way at build time.
Baidu coordinates (BD-09) would need `bd2wgs` instead. Coordinates from
SEGA/KONAMI pages, ZIv, and Round1 USA are already WGS-84 and are
written unchanged. `data/arcades.json` is WGS-84 only, always.

### Why enrichment and FX are separate files

`arcades.json` is the critical path for map markers. Enrichment is
optional UI detail; FX is a tiny weekly rates blob. Isolating them keeps
first paint small, lets FX fail without blocking arcade commits, and
makes it obvious which fields can go stale (`enriched_at`, the FX rate
date).
