# Frontend Upgrade Research

Date: 2026-07-27. Read-only research for Arcade Maps
(`C:\Users\jonny\Desktop\Arcade Maps`): static, no build step, vendored
Leaflet 1.9.4 + markercluster 1.5.3, OSM raster tiles, GitHub Pages.

Every claim is marked **[VERIFIED]** with URL/evidence or **[UNVERIFIED]**.
Live data snapshot used for counts: `data/arcades.json` dated 2026-07-27
(12,037 arcades, 6,080 plottable).

Owner goals addressed:

1. Smooth zoom / high-Hz motion
2. MapLibre path comparison
3. 6-12k point rendering
4. ZIv-style game search with better UI
5. Rich place detail (Google Maps place-panel IA, original dark neon chrome)
6. Nearby search
7. Perf / data-file split
8. Graduated markers by cab count
9. Settings modal (sources, display, location, about/legend)

---

## 0. Current frontend baseline (repo facts)

**[VERIFIED]** from `index.html`, `app.js`, `style.css`, `vendor/`:

| Piece | Status |
| --- | --- |
| Leaflet | 1.9.4 vendored (`vendor/leaflet.js` 147,552 B) |
| markercluster | 1.5.3 (`vendor/leaflet.markercluster.js` 34,136 B), `chunkedLoading: true` |
| Tiles | `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, `maxZoom: 19` |
| Markers | `L.circleMarker` on shared `L.canvas({ padding: 0.5 })` renderer |
| Clustering | single `L.markerClusterGroup`, `disableClusteringAtZoom: 16` |
| Search | name+address substring, max 20 hits, keyboard nav |
| Detail | Leaflet popup only (name, addr, game chips, cab badges, sources, GMaps link) |
| Filters | left drawer: game chips + cab variants; mobile drawer closed by default |
| Data | one fetch of `data/arcades.json` (~8.5 MB raw on disk) |

Map init options today (no fractional zoom tuning):

```js
L.map("map", {
  zoomControl: true,
  worldCopyJump: true,
  fadeAnimation: !REDUCED,
  zoomAnimation: !REDUCED,
  markerZoomAnimation: !REDUCED
});
```

Canonical game set: 19 slugs in `GAMES` (maimai_dx ... other). Schema allows
optional `game_counts` (**[VERIFIED]** `docs/ARCHITECTURE.md`), and scrapers
write it for ZIv/BemaniCN (**[VERIFIED]** `scrapers/ziv.py`,
`scrapers/bemanicn.py`, `scrapers/merge.py`), but the live
`data/arcades.json` currently has **zero** `game_counts` keys
(**[VERIFIED]** full scan 2026-07-27). Raw `data_raw/ziv.json` has
`game_counts` on 2,807 / 6,985 rows; raw BemaniCN file has 0
(pipeline gap or stale scrape - root cause **[UNVERIFIED]** without re-running
merge). Graduated-marker design must treat unknown count as first-class.

---

## 1. Smooth zoom - Leaflet path

### 1.1 What Leaflet 1.9 actually exposes

**[VERIFIED]** Leaflet docs
[Zoom levels tutorial](https://leafletjs.com/examples/zoom-levels/) and
[Map options reference](https://leafletjs.com/reference.html#map-zoomsnap):

| Option | Default | Effect |
| --- | --- | --- |
| `zoomSnap` | `1` | Snap zoom to multiples of this. `0.25` / `0.1` enable fractional levels; `0` disables snapping (continuous). |
| `zoomDelta` | `1` | Step for +/- buttons and keyboard. |
| `wheelPxPerZoomLevel` | `60` | Scroll pixels per full zoom level (lower = faster). |
| `wheelDebounceTime` | `40` | Min ms between wheel zoom firings. |
| `scrollWheelZoom` | `true` | Also accepts `'center'`. |
| `zoomAnimation` | `true` | CSS3 transition zoom; off on some Android. |
| `zoomAnimationThreshold` | `4` | Skip anim if delta exceeds this. |
| `fadeAnimation` | `true` | Tile fade. |
| `markerZoomAnimation` | `true` | Markers track zoom anim. |
| inertia pan | on by default | `inertia`, `inertiaDeceleration` (3000), `inertiaMaxSpeed`, `easeLinearity` (0.2). |

**[VERIFIED]** fractional zoom tile behavior (same tutorial): Leaflet loads
tiles only at **integer** z and **CSS-scales** them between levels. With
`zoomSnap: 0.25`, intermediate zooms are stretched/shrunk rasters, not new
vector detail.

**[VERIFIED]** vendored `leaflet.js` contains `zoomSnap:1` default,
`_animateZoom` (13 refs), one `requestAnimFrame` use, `translate3d` (1),
**zero** `will-change`. Zoom animation is CSS-transform based; Leaflet does
not hard-cap frame rate to 60 Hz. If the browser composites CSS transforms at
display refresh, pan/zoom anim can exceed 60 Hz on high-Hz panels - but wheel
zoom is still debounced and stepped, so the *feel* stays discrete unless
options/plugins change it.

### 1.2 SmoothWheelZoom plugin

**[VERIFIED]** [mutsuyuki/Leaflet.SmoothWheelZoom](https://github.com/mutsuyuki/Leaflet.SmoothWheelZoom):

- MIT, ~106 stars, not archived
- Last push 2026-03-26 (README merge); 7 open issues; 0 open PRs
- Single file `SmoothWheelZoom.js` measured **3,586 B raw / ~1.0 KB gzip**
- Usage: disable core `scrollWheelZoom`, enable `smoothWheelZoom`, recommend
  `zoomSnap: 0`
- Goal stated by author: "smooth zoom ux like Google map"
- Forks/npm republishes exist (`@luomus/leaflet-smooth-wheel-zoom`, alexatiks
  fork) - original is lightly maintained, not abandoned-broken

Honest maintenance verdict: small surface, usable, not a heavily stewarded
project. Vendor the ~3.5 KB file and own it if needed.

### 1.3 Raster blur at fractional zooms

**[VERIFIED]** Leaflet scales integer OSM tiles between z levels. On OSM
standard PNGs this means:

- Between z and z+1, labels and road casings look soft/blurry
- At half-levels especially, text is least sharp
- Real projects that stay on raster either (a) keep integer snap for "sharp
  final state" and only animate between integers, or (b) accept soft
  intermediate frames (Google-like continuous zoom is *expected* to soften
  raster briefly)

What real sister projects do **[VERIFIED]** from `docs/PRIOR_ART.md`:

- `bemusicscript/gcm-storefinder`: Leaflet API + **maplibre-gl-leaflet**
  vector basemap under Leaflet markers (prettier continuous basemap without
  full MapLibre migration)
- `hker9527/otoge-locator`: plain Leaflet + locatecontrol

### 1.4 CSS / perf knobs

- Leaflet already GPU-composites via CSS transforms; sprinkling
  `will-change: transform` on `.leaflet-proxy` / `.leaflet-tile-container` is
  a low-risk experiment, not a documented Leaflet API (**[UNVERIFIED]** net
  gain on Windows Chrome/Edge high-Hz).
- Respect existing `prefers-reduced-motion` path in `app.js`.
- Do **not** expect `wheelDebounceTime: 0` alone to feel like Google Maps;
  core wheel zoom still jumps by delta levels.

### 1.5 Honest Leaflet smoothness verdict

**How close to Google Maps can raster Leaflet get?**

| Dimension | Leaflet ceiling |
| --- | --- |
| Continuous / fractional zoom | Good with `zoomSnap: 0` + SmoothWheelZoom |
| Wheel inertia feel | Fair-good with plugin; not identical to Maps |
| Basemap sharpness mid-zoom | **Poor-fair** (scaled rasters) |
| Rotation / pitch | None (2D only) |
| High-Hz pan fling | Good if CSS compositing keeps up; not WebGL rAF |
| Marker layer during zoom | Canvas circleMarkers + cluster recompute can hitch at dense zooms |

**Verdict:** Leaflet tuning can fix the *steppy wheel* complaint (~70-80% of
the feel gap) but cannot match Google Maps' always-sharp vector basemap +
true continuous camera. For a high-Hz owner who notices motion quality,
Leaflet-only is a plateau, not the ceiling.

**Low-effort Leaflet tune package (recommended first shippable step):**

```js
L.map("map", {
  zoomSnap: 0,            // or 0.25 if full continuous feels too soft
  zoomDelta: 0.5,
  wheelPxPerZoomLevel: 80, // slightly slower, finer
  wheelDebounceTime: 20,
  // + SmoothWheelZoom: scrollWheelZoom:false, smoothWheelZoom:true
});
```

Effort: ~0.5-1 day including reduced-motion and touch regression.

---

## 2. Smooth zoom - MapLibre GL path

### 2.1 Current stable version and dist shape

**[VERIFIED]** npm `maplibre-gl@6.0.0` (published ~2026-07-22),
license **BSD-3-Clause**, description "BSD licensed community fork of
mapbox-gl".

Release notes **[VERIFIED]**
[maplibre-gl-js releases](https://github.com/maplibre/maplibre-gl-js/releases):

- **ESM-only** distribution (`dist/maplibre-gl.mjs`); UMD and CSP builds
  removed in v6
- **WebGL2 required** (WebGL1 dropped)
- Official example usage: `<script type="module">` +
  `import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.0.0/dist/maplibre-gl.mjs'`

Measured files **[VERIFIED]** download 2026-07-27:

| File | Raw | gzip-9 |
| --- | --- | --- |
| maplibre-gl@6.0.0 `maplibre-gl.mjs` | 564,301 B | ~142 KB |
| maplibre-gl@6.0.0 CSS | 70,024 B | ~10 KB |
| maplibre-gl@5.6.2 UMD `maplibre-gl.js` (prior major) | 937,395 B | ~248 KB |
| Leaflet 1.9.4 + markercluster (current) | 181,688 B | (not re-gzipped; raw ~182 KB) |

No-build implication: v6 is fine on static Pages via
`<script type="module" src="vendor/maplibre-gl.mjs">` (or import map).
Classic blocking UMD `<script src=...maplibre-gl.js>` is **gone in v6**.
Fallback: vendor last v5 UMD if a non-module path is mandatory.

### 2.2 Continuous zoom + high-Hz rendering

**[VERIFIED]** MapLibre `MapOptions` docs
([MapOptions](https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapOptions/)):

- Default `zoomSnap` is **`0`** (continuous zoom)
- WebGL canvas renders on animation frames; camera zoom/pan/rotate/pitch are
  first-class. This is the stack that can track 120 Hz+ display refresh when
  the browser/GPU allow it.

Leaflet cannot rotate/pitch the basemap; MapLibre can.

### 2.3 OpenFreeMap (keyless vector tiles)

**[VERIFIED]** [openfreemap.org](https://openfreemap.org/) +
[quick start](https://openfreemap.org/quick_start/):

- No API key, no registration, no view limits, commercial use allowed,
  donation-funded, no SLA
- Styles: liberty, bright, positron, dark, fiord, 3D via
  `https://tiles.openfreemap.org/styles/{name}`
- Attribution required: OpenMapTiles + OpenStreetMap (OpenFreeMap name nice
  but optional); MapLibre adds attribution control automatically
- Live check 2026-07-27: liberty style JSON HTTP 200; `glyphs` =
  `https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf`; fonts used
  = Noto Sans Regular/Bold/Italic; 111 layers; sources `openmaptiles` +
  `ne2_shaded`

**CJK label quality:**

**[VERIFIED]** MapLibre
[local ideographs example](https://maplibre.org/maplibre-gl-js/docs/examples/use-locally-generated-ideographs/)
uses OpenFreeMap bright and documents:

- `localIdeographFontFamily` default **`'sans-serif'`** (MapOptions)
- CJK glyphs rasterized **on-device** from system fonts (fast); set `false`
  to use server glyph PBFs (slow for CJK ranges)
- Non-CJK still uses style glyphs (Noto Sans from OpenFreeMap)

Practical for Japan/China arcade map: keep default local ideographs (or set
an explicit stack like `"Hiragino Sans", "Noto Sans CJK JP", "Microsoft YaHei", sans-serif`).
Label quality then tracks the user's installed CJK fonts - generally
readable on Windows/macOS/iOS; weaker on minimal Linux VMs
(**[UNVERIFIED]** exhaustive OS matrix).

### 2.4 Clustering in MapLibre

**[VERIFIED]** official example
[Create and style clusters](https://maplibre.org/maplibre-gl-js/docs/examples/create-and-style-clusters/)
(MapLibre 6.0.0 module import):

```js
map.addSource('arcades', {
  type: 'geojson',
  data: geojson,
  cluster: true,
  clusterMaxZoom: 14,
  clusterRadius: 50
});
// circle layer filter ['has','point_count']
// symbol layer text-field '{point_count_abbreviated}'
// unclustered-point layer filter ['!', ['has','point_count']]
// click cluster -> getClusterExpansionZoom + easeTo
```

Also **[VERIFIED]** [large-data guide](https://maplibre.org/maplibre-gl-js/docs/guides/large-data/):
GeoJSON clustering reduces rendered features; strip properties; ~6 decimal
coordinate precision; for pure points source `maxzoom` ~12 is a suggested
balance. No hard "N points = X fps" number published there.

Native `cluster: true` uses supercluster under the hood in the Mapbox/MapLibre
lineage (**[UNVERIFIED]** exact package name in v6 without reading source;
behavior is the documented GL-JS cluster API).

Custom cluster properties (e.g. sum of cab counts) are supported via
`clusterProperties` in the GeoJSON source options
(**[UNVERIFIED]** exact v6 option name not re-fetched this session; treat as
follow-up before implementing sum-cabs cluster badges).

### 2.5 Marker / popup migration cost from Leaflet

| Leaflet concept | MapLibre analogue | Cost |
| --- | --- | --- |
| `L.circleMarker` + canvas | `circle` layer + paint expressions | Medium (data-driven style rewrite) |
| `L.markerClusterGroup` | GeoJSON `cluster: true` + 2-3 layers | Medium |
| `bindPopup` HTML | `maplibregl.Popup` or custom DOM panel | Medium-low |
| `L.divIcon` halo | HTML marker / symbol layer / separate canvas | Low-medium |
| game color chips on markers | `circle-color` match expression on `display_game` prop | Medium |
| filter re-apply `clearLayers/addLayers` | `setFilter` / `setData` / feature-state | Medium (can be *better* than full rebuild) |
| hash `setView` | `jumpTo` / `easeTo` / `fitBounds` | Low |
| Locate control | MapLibre GeolocateControl (built-in) or hand-roll | Low |

No-build constraint remains satisfied with ESM module script.

### 2.6 Licensing

**[VERIFIED]** MapLibre GL JS: BSD-3-Clause. OpenFreeMap project MIT;
map data OSM ODbL; OpenMapTiles attribution required.

### 2.7 Hybrid path: maplibre-gl-leaflet

**[VERIFIED]** prior art (`docs/PRIOR_ART.md`): gcm-storefinder runs MapLibre
as a **Leaflet basemap layer** via `@maplibre/maplibre-gl-leaflet`, keeping
Leaflet markers/clusters. OpenFreeMap quick start documents the same pattern:

```js
L.maplibreGL({ style: 'https://tiles.openfreemap.org/styles/liberty' }).addTo(map)
```

This buys continuous sharp vector basemap + Leaflet plugin ecosystem, at the
cost of **two** map engines in memory and some gesture/zoom impedance mismatch
(**[UNVERIFIED]** measured jank). Good intermediate if marker rewrite is
deferred.

### 2.8 Leaflet-tune vs MapLibre-migrate

| Criterion | Leaflet tune | Hybrid (ML basemap under Leaflet) | Full MapLibre |
| --- | --- | --- | --- |
| Wheel smoothness | Good with plugin | Good basemap, Leaflet markers still Leaflet | Best |
| Basemap mid-zoom sharpness | Soft (raster scale) | Sharp vector | Sharp vector |
| Bundle | +~4 KB plugin | +~550 KB ML + bridge | +~550 KB ML, drop Leaflet ~182 KB |
| High-Hz WebGL camera | No | Partial | Yes |
| Migration risk | Minimal | Medium | High |
| Fits "no build" | Yes | Yes (module) | Yes (module) |
| CJK labels | OSM raster (baked) | Vector + localIdeograph | Vector + localIdeograph |
| 12k points | Already OK | Same Leaflet markers | Trivial for GL |

**Recommend:** phased

1. **Now:** Leaflet tune + SmoothWheelZoom (cheap, addresses steppy zoom).
2. **Next (if still unsatisfied):** full MapLibre migrate for camera + vector
   basemap + circle layers (not long-term hybrid; hybrid is only a demo
   spike). Keep OSM raster as runtime fallback style if OpenFreeMap is down.

Fallback stance:

```text
primary style: OpenFreeMap liberty (or dark if themed)
on style/data error: raster OSM tile source in MapLibre
  (type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
   tileSize: 256) + matching attribution
```

Effort estimate:

- Leaflet tune: **0.5-1 day**
- Hybrid spike: **1-2 days** (optional)
- Full MapLibre migrate (markers, filters, search flyTo, halo, hash, locate):
  **5-8 days** including CJK/visual QA on JP dense areas
- Raster fallback path: **+0.5 day**

---

## 3. Rendering 6-12k points at high frame rate

### 3.1 Current Leaflet path

**[VERIFIED]** `app.js`:

- Shared `L.canvas` renderer for all circleMarkers (not SVG)
- markercluster `chunkedLoading: true`
- ~6,080 plottable today; architecture targets ~12k

**[VERIFIED]** [Leaflet.markercluster README](https://github.com/Leaflet/Leaflet.markercluster):

- Claims handle **10,000 or even 50,000** markers in Chrome
- `chunkedLoading` splits `addLayers` into intervals (`chunkInterval` 200 ms,
  `chunkDelay` 50 ms) so the page does not freeze
- Realworld demos for 10k/50k enable chunkedLoading

Reality for this site: initial load and filter re-apply call
`cluster.clearLayers()` + `cluster.addLayers(vis)`. At 6k this is acceptable;
at 12k with frequent filter toggling, main-thread cost is the bottleneck, not
GPU fill rate. Canvas markers already beat SVG DOM markers by a wide margin.

### 3.2 MapLibre path

**[VERIFIED]** clustering example + large-data guide: 12k points with
`cluster: true` and circle layers is well inside WebGL comfort (earthquake
demo is larger). Unclustered 12k circles at city zoom is also typically fine;
Tokyo density still wants clustering for readability more than raw GPU limits.

Evidence grade: documentation + industry practice, **not** a controlled fps
benchmark run in this session. Label any "120 fps at 12k" claim as
**[UNVERIFIED]** until profiled on the owner's high-Hz machine.

### 3.3 Practical guidance

- Leaflet: keep canvas + cluster; avoid per-filter full rebuild if possible
  (incremental hide via `_icon`/`setStyle` experiments) - **[UNVERIFIED]**
  win size
- MapLibre: one GeoJSON source, cluster on, data-driven `circle-radius` /
  `circle-color`; filter with `setFilter` rather than rebuilding GeoJSON when
  possible
- Either stack: do not attach photo URLs or long notes onto every rendered
  feature property (see section 7)

---

## 4. ZIv-style game search, but better

### 4.1 How ZIv works today

**[VERIFIED]** fetch of
[zenius-i-vanisher.com/v5.2/arcades.php](https://zenius-i-vanisher.com/v5.2/arcades.php):

- Filters: **Location** (country dropdown, ~90 entries), **Series** (huge
  dropdown of 1000+ series), **Game** (dependent: "Pick a series first")
- Search/Reset are JS `query()` / `reset()`
- Default view is "Recent Updates" list (~25 rows): name link, address,
  relative edit time, editor, Map link with lat/lng in title
- No modern omnibox; no fuzzy typeahead; no map-first UX on that page

### 4.2 Our current search

**[VERIFIED]** `app.js` `buildSearch`: lowercased `name + " " + addr`
substring, first 20 hits, keyboard listbox. No game-name search, no aliases,
no city grouping.

### 4.3 Fuzzy libs that can be vendored (no build)

| Library | Version | License | Size (measured) | Browser packaging |
| --- | --- | --- | --- | --- |
| **uFuzzy** `@leeoniya/ufuzzy` | **1.0.19** **[VERIFIED]** npm | MIT | IIFE min **8,410 B** / ~4.0 KB gzip | `uFuzzy.iife.min.js` |
| **Fuse.js** | **7.5.0** **[VERIFIED]** npm | Apache-2.0 | `fuse.min.mjs` **26,095 B** / ~9.2 KB gzip; basic min ~19 KB | ESM/CJS only in modern package (`./min`, `./basic` exports); no classic `fuse.min.js` path |

**[VERIFIED]** uFuzzy README ([leeoniya/uFuzzy](https://github.com/leeoniya/uFuzzy)):
~7.5 KB min, zero deps, typeahead-oriented, Latin-optimized (unicode mode
slower), multi-insert / single-error modes, highlight helper. Author argues
better ranking than default Fuse for partial needles.

### 4.4 Alias table vs fuzzy (for games)

We have a **closed set of 19 canonical game slugs** plus community "other"
names in notes. For game intent ("wacca", "iidx", "舞萌", "prsk"):

| Approach | Pros | Cons |
| --- | --- | --- |
| Hand-rolled alias table | Deterministic, tiny, CJK-friendly, no false "twirling" matches | Must maintain aliases |
| uFuzzy over game labels only | Typo tolerance | Still need aliases for 舞萌/prsk |
| Fuse over all arcades | Weighted multi-field | Heavier; weaker default ranking |

**Recommend hybrid:**

1. **Alias table** (primary) for games and cab variants, e.g.
   `iidx -> beatmania iidx`, `bm -> iidx`, `sdvx -> sound voltex`,
   `voltex -> sdvx`, `舞萌 -> maimai_dx`, `中二 -> chunithm`,
   `prsk`/`pjsk`/`prosuka` -> project-related if ever added, `wacca` ->
   other or a future slug, etc.
2. **Substring** (current) on arcade name/addr/pref/country
3. Optional **uFuzzy** only on arcade names if alias+substring feels harsh
   on typos - vendor 8 KB IIFE

Fuzzy-over-games alone will **not** map 舞萌 or prsk without aliases.

### 4.5 Combined search UX

**Recommend one omnibox** with **grouped results**, not ZIv's triple
dropdown:

```text
[  Search games, arcades, cities...        ]

Games
  SOUND VOLTEX  (filter map to SDVX)     ↵ applies game chip
  ...
Arcades
  Round1 Foo  · Tokyo · JP
  ...
Places
  Akihabara · jump map
```

Patterns from real map UIs (IA only):

1. **Google Maps** omnibox: mixed places, keyboard, then place panel
   **[VERIFIED]** common knowledge / owner screenshot reference; not re-fetched
2. **OpenStreetMap.org** search + "query features" nearby pattern
   **[VERIFIED]** listed on [osm.org](https://www.openstreetmap.org/) tooling
3. **ddrfinder.andrew67.com** (MIT prior art family): map + search over DDR
   locations **[VERIFIED]** existence via `docs/PRIOR_ART.md` (Andrew67
   ddr-finder-ng); exact 2026 UI details **[UNVERIFIED]** this session
4. **ZIv**: series/country structured filters (keep as *advanced* chips, not
   primary)

Also keep existing **game chips** as the durable filter state; omnibox game
hits should *toggle/activate chips*, not replace them.

Keyboard: keep current Arrow/Enter/Esc; add section headers as non-selectable
rows; show "Filter to {game}" vs "Go to {arcade}" affordances.

Effort: **2-3 days** (alias table + grouped UI + chip integration + tests).

---

## 5. Rich detail UI (Google Maps place-panel IA, original chrome)

### 5.1 Patterns

| Pattern | Who | Notes |
| --- | --- | --- |
| Map popup only | Current Arcade Maps, many Leaflet demos | Too small for photos/transit/prices |
| Full page per shop | bemanicn (login-walled full app) | Wrong for static map-first site |
| Left / side place panel | Google Maps | Owner-pinned IA reference |
| Bottom sheet | Mobile Maps, many PWAs | Needed under ~760 px |

Owner constraint (2026-07-27): treat Google Maps as **information
architecture only**. Visual identity stays **dark arcade-neon**
(`--bg #17181d`, accent `#E4007F`), not Google white/teal.

### 5.2 Recommended architecture

**Desktop / wide:**

1. Marker click opens a **left full-height place panel** over the map's left
   edge (same column width as today's filter drawer, ~320-360 px, or slightly
   wider ~380 for media).
2. **Filter drawer is replaced in-place** by the place panel (not a second
   stacked column). Top of panel: back chevron "Filters" restoring chip UI.
   Rationale: two simultaneous left columns crush the map; stacking matches
   Maps' "search/filters vs place" mutual exclusion and reuses existing
   drawer infrastructure (`#panel`, `drawer-closed`, `invalidateSize`).
3. Leaflet/MapLibre **popup becomes minimal or none**:
   - Prefer **skip popup** on click: panel is the detail surface (cleaner,
     one source of truth).
   - Optional hover tooltip: name + 1-2 game dots only.
4. Panel content order (IA):

```text
[ <- Filters ]
[ media / photo header | gradient placeholder if none ]
Name
native / alt name subtitle (when we have name_en etc.)
★★★★☆ 4.2 (128) · ¥¥ · 12 cabs     (hide missing bits, don't show empties)
( o Directions ) ( o Nearby ) ( o Share ) ( o Sources )
icon Address ....
icon Price per play ....
icon Hours .... (when known)
icon Transit / access ....
icon Games: chips with counts
icon Cab variants
icon Sources badges (links)
notes (collapsed)
```

Action buttons: circular, dark fill, accent on hover; **not** Google teal.
Directions = existing GMaps link-out. Nearby = section 6. Share =
`navigator.share` or copy URL with hash. Sources = scroll to source rows /
open links.

**Mobile (<760 px, already used in CSS):**

- Place detail as **bottom sheet** (drag handle, 45-90% height states)
- Filter drawer stays the existing slide/toggle panel
- Selecting a place closes filters and opens sheet; back returns

### 5.3 What we can fill today vs later

| Field | Today in `arcades.json` | Notes |
| --- | --- | --- |
| name, addr, country, pref | yes | |
| games[], cabs[] | yes | |
| game_counts | schema yes, live file no | fix pipeline; UI must tolerate absence |
| links.gmaps/ziv/bemanicn | yes | |
| notes | often (8,407 rows) | may contain cab lists for ZIv |
| ratings, photos, hours, price, transit | **not in schema yet** | enrichment file (section 7) |

Until enrichment exists, panel still works: omit empty rows; photo header
becomes a subtle monogram / game-color gradient so layout does not jump when
photos arrive later.

### 5.4 Settings modal coexistence

Settings (section 9) is a **centered modal overlay**, not a left-column mode.
Place panel and settings never compete for the same surface.

### 5.5 Effort

- Place panel + back-to-filters + mobile bottom sheet: **3-4 days**
- Minimal hover tooltip: **+0.5 day**
- Wire enrichment fields when data exists: **1 day**

---

## 6. Nearby search UX

### 6.1 Locate control

**[VERIFIED]** npm `leaflet.locatecontrol@0.90.0`, MIT, main
`dist/L.Control.Locate.min.js`.

Measured: JS **14,854 B** (~4.5 KB gzip) + CSS **3,481 B** (~0.8 KB gzip).

**[VERIFIED]** [domoritz/leaflet-locatecontrol](https://github.com/domoritz/leaflet-locatecontrol):
used by osm.org start page et al.; Leaflet 1.9 + 2.x; `L.control.locate()`,
`drawCircle`, `flyTo`, events. Actively maintained signal (npm 0.90.0, ESM
export `LocateControl`).

MapLibre path: built-in `maplibregl.GeolocateControl` (no extra plugin).

Hand-roll alternative: `navigator.geolocation.watchPosition` + accuracy
circle + marker, ~50-80 lines. Prefer **plugin on Leaflet** / **built-in on
MapLibre** unless bundle absolutism wins (plugin is small).

### 6.2 Nearby list UX

Recommended flow:

1. User clicks Locate (permission prompt once).
2. On success: pan/zoom to user, draw accuracy circle, open **Nearby** list
   in the left panel (or a tab): nearest N plottable arcades by haversine,
   show distance (m/km) + coarse bearing (N/NE/...).
3. Optional "Search this area" control: re-query whatever is in current
   bounds (useful when user pans away from GPS).
4. Respect game/source filters (AND).
5. Failures: clear messages for denied permission / timeout / insecure origin
   (geolocation needs https - GitHub Pages is fine).

Haversine is trivial; no dependency. Bearing: `atan2` formula.

Cluster interaction: picking a nearby row uses existing flyTo + halo +
`zoomToShowLayer` path.

Effort: **1-1.5 days** with locatecontrol; **+0.5 day** polish for
denied-permission and mobile.

---

## 7. Perf budget and data-file split

### 7.1 Current weight

**[VERIFIED]** 2026-07-27:

| Asset | Size |
| --- | --- |
| `data/arcades.json` | **8,502,989 B** (~8.5 MB) for 12,037 rows |
| Lean projection (id,name,addr,lat,lng,country,pref,games,cabs,src only) | ~3.0 MB |
| Leaflet+cluster | ~182 KB raw |
| MapLibre 6 mjs | ~564 KB raw / ~142 KB gzip |

Notes and long strings dominate. 8.5 MB JSON parse on mid phones is the real
startup tax, not marker GL.

### 7.2 Recommended split

```text
data/arcades.json          # map + search core (keep lean)
data/enrichment.json       # keyed by arcade id: photos[], rating, review_count,
                           # price_hint, hours, transit, maybe long notes
                           # fetched ONLY when place panel opens (or idle prefetch
                           # viewport ids)
```

Rules:

1. **Never** put photo blobs in JSON; store URLs (and prefer lazy `<img>`).
2. Popup/panel first paint uses lean fields already in memory.
3. On panel open: `enrichment[id]` lookup from cached fetch of
   `enrichment.json` **or** (better long-term) `data/enrichment/{id}.json`
   if the file grows large. For hundreds of enriched rows, one side file is
   enough; for tens of thousands, shard.
4. `game_counts` belongs in **core** arcades.json (needed for marker scale +
   chips) once pipeline emits it - small integers.
5. Keep `arcades.json` under ~3-4 MB if possible (drop redundant notes that
   only restate game lists; move ZIv cab novels to enrichment).

Lazy-load strategy for images: `loading="lazy"` in panel; thumbnail in header
only; full gallery on expand.

Effort: schema + loader **1-2 days**; content pipeline separate.

---

## 8. Graduated marker icons (cab-count prominence)

### 8.1 Cartographic baseline

**[VERIFIED]** [Wikipedia: Proportional symbol map](https://en.wikipedia.org/wiki/Proportional_symbol_map):

- People judge **area** poorly vs length; larger circles under-read without
  compensation
- **Flannery (apparent magnitude) scaling**: exponent **0.5716** instead of
  0.5 for circles (mixed modern acceptance; legend still essential)
- **Range grading (discrete size classes)** preferred when continuous sizes
  are hard to read or when data is sparse/noisy
- Overlap: some overlap OK; smaller on top; outlines / semi-transparency help
- Legends should show sample sizes (min / mid / max)

### 8.2 Channel assignment (this product)

- **Hue** = primary game color (already taken)
- **Size** = total rhythm-cab count (graduated)
- Optional **stroke brightness / soft halo** for mega venues only (not extra
  hues)
- **Do not** add a second categorical hue for size

### 8.3 Unknown counts (critical)

Live data: most stores lack `game_counts`. Official ALL.Net / eagate publish
presence not quantities.

**Rule: unknown != smallest.**

| Class | Total cabs (sum of game_counts) | Circle radius (canvas px) | Visual |
| --- | --- | --- | --- |
| U unknown | key absent | **7** (current default) | solid fill, current stroke |
| S | 1 | 5 | slightly subtler opacity 0.85 |
| M | 2-4 | 7 | same as today |
| L | 5-9 | 9 | |
| XL | 10-19 | 11 | light outer halo optional |
| XXL | 20+ | 13 | soft accent halo, still one hue |

Rationale: discrete classes beat continuous Flannery here because (a) counts
are incomplete and integer-skewed, (b) Tokyo density needs only a few
perceptible steps, (c) legend stays teachable.

If only **game list length** is known (no counts), do **not** pretend it is
cab count; optionally a separate weak signal later. Prefer real
`game_counts` from ZIv/BemaniCN once merge emits them.

### 8.4 Clustering interaction

| Approach | Verdict |
| --- | --- |
| Cluster badge = **count of stores** (current) | Keep as default; matches mental model "how many places" |
| Badge = **sum of cabs** | Interesting for "cabinet mass" but confuses store density; make optional in settings later |
| Cluster size/color by max child class | Optional enhancement; not required v1 |

When cluster expands to individuals, graduated sizes apply. At
`disableClusteringAtZoom: 16` (current), dense Tokyo shows real sizes.

Markercluster `iconCreateFunction` can encode store-count only (status quo).

### 8.5 Legend placement

- Full explanation in **Settings > About / Legend** (owner request)
- Plus a **tiny on-map collapsed legend chip** (bottom-left or bottom-right
  above attribution): "Dot size = cab count" expanding to 4 sample dots.
  Discoverability dies if legend is modal-only.

### 8.6 Effort

- Size classes + legend chip + settings toggle: **1-1.5 days** after
  `game_counts` present in JSON
- Pipeline fix to actually emit counts: **separate scraper/merge bugfix**
  (out of pure frontend; flag as blocker for this feature's value)

---

## 9. Settings modal (Claude-desktop-style)

### 9.1 Desired IA

Centered modal, dimmed backdrop, **left nav** (Sources / Display / Location /
About), **right rows**: label + one-line description + switch.

**Sources** (live map filters, AND with games/cabs):

- ALL.Net, e-amusement, WAHLAP, BemaniCN, ZIv, Round1 USA, community

**Display:**

- Marker size by cab count on/off
- Legend chip on/off
- (future) basemap style, cluster on/off

**Location:**

- Enable locate control / request permission explainer
- Nearby radius N

**About / Legend:**

- Size classes, game colors, data sources blurb, repo link

### 9.2 Accessible implementation without a framework

**[VERIFIED]** [MDN dialog](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog):

- Prefer `<dialog>` + `showModal()`: top layer, `::backdrop`, Esc closes,
  background becomes **inert**, focus moves into dialog
- Always ship a visible Close control; `autofocus` on appropriate control
- Baseline widely available since 2022

**[VERIFIED]** focus-trap debate
([CSS-Tricks](https://css-tricks.com/there-is-no-need-to-trap-focus-on-a-dialog-element/),
[Schalk Neethling](https://schalkneethling.com/posts/html-dialog-native-solution-for-accessible-modal-interactions/)):

- Native modal already blocks page content; tabbing to **browser chrome** is
  intentional and OK
- Still label with `aria-labelledby`, restore focus to the gear button on
  close (native generally returns focus when opened via scripted
  `showModal` from a button)

Do **not** hand-roll `div[role=dialog]` unless dialog proves insufficient.

### 9.3 Persistence

`localStorage` key e.g. `arcadeMaps.settings.v1`:

```json
{
  "sources": {"allnet": true, "eagate": true, "wahlap": true,
              "bemanicn": true, "ziv": true, "round1usa": true,
              "community": true},
  "markerScale": true,
  "legendChip": true
}
```

Compose with filters:

```text
visible = hasCoords
  AND displayGame match (existing game+cab logic)
  AND arcade.src intersects enabledSources  (any-of sources, AND with games)
```

URL hash today stores games/cabs/view - optional later extension for sources;
settings can stay device-local so shared links do not hide half the map
unexpectedly. **Recommend:** sources in localStorage only; games/cabs remain
hash-shareable.

### 9.4 Effort

Settings shell + source toggles + persistence: **2 days**.
Display/legend rows: **+0.5 day**.

---

## 10. What was NOT verified / residual risks

1. No on-device high-Hz fps profiling of Leaflet vs MapLibre on the owner's
   display.
2. No side-by-side CJK label screenshots (Tokyo/Shanghai) for OpenFreeMap
   liberty vs bright vs OSM raster.
3. Root cause of missing `game_counts` in live `arcades.json` despite ZIv raw
   having them (merge intended to pass through - needs a merge re-run debug).
4. MapLibre `clusterProperties` sum-cabs option not line-checked in v6 d.ts
   this session.
5. Fuse browser global build: modern package is ESM/CJS; IIFE path not
   confirmed (prefer uFuzzy IIFE or alias table).
6. Hybrid maplibre-gl-leaflet gesture conflict not measured.
7. OpenFreeMap uptime/SLA explicitly none - hence raster fallback plan.
8. Photos/ratings/transit enrichment sources not specified here (see any
   separate enrichment research file if present).

---

## RECOMMENDATION

### A. Map engine: Leaflet-tune now, MapLibre migrate next

1. **Ship immediately (0.5-1 d):** Leaflet fractional/smooth wheel package
   (`zoomSnap: 0` or `0.25`, `zoomDelta: 0.5`, tuned wheel options,
   vendored SmoothWheelZoom ~4 KB, keep canvas markers + markercluster).
2. **Do not** stop at hybrid long-term; if motion/basemap sharpness still
   fails the high-Hz bar, **migrate to MapLibre GL JS 6** (ESM vendor,
   OpenFreeMap liberty/dark, `localIdeographFontFamily` for CJK, native
   GeoJSON clusters, OSM raster fallback style).
3. Effort MapLibre full migrate: **5-8 d**. Fallback OSM raster: **+0.5 d**.

### B. Search architecture

- One **omnibox** with grouped results: Games / Arcades / Places.
- **Alias table** for the 19 games + community nicknames (舞萌, iidx, sdvx,
  prsk, wacca, ...); omnibox game hit toggles existing chips.
- Keep substring on name/addr; add **uFuzzy 1.0.19** (~8 KB IIFE) only if
  typos remain painful.
- ZIv-style country/series dropdowns are inferior as primary UX; optional
  advanced filters only.
- Effort: **2-3 d**.

### C. Detail UI architecture

- **Google Maps place-panel IA, original dark-neon chrome.**
- Desktop: left full-height **place panel replaces filter drawer** (back
  button returns to filters). No dual left columns.
- Mobile: **bottom sheet**.
- Marker click -> panel; skip rich popup (optional hover name tooltip only).
- Circular action row: Directions (GMaps), Nearby, Share, Sources.
- Empty enrichment fields omitted, not stubbed as "N/A" walls.
- Effort: **3-4 d** shell + **+1 d** when enrichment lands.

### D. Nearby UX

- Vendor **leaflet.locatecontrol 0.90.0** (~15 KB JS) on Leaflet path; use
  MapLibre GeolocateControl after migrate.
- Nearest-N list with haversine distance + bearing; "search this area"
  control; AND with game/source filters.
- Effort: **1-1.5 d**.

### E. Graduated markers

- Discrete classes U/S/M/L/XL/XXL; **unknown uses medium default (r=7), never
  smallest**.
- Hue stays game color; size = sum `game_counts`; optional soft halo only on
  XL+.
- Cluster badge stays **store count** by default.
- Legend: settings About section **and** tiny on-map chip.
- Blocked on `game_counts` actually appearing in `arcades.json` (pipeline
  fix).
- Effort UI: **1-1.5 d** after data.

### F. Settings modal

- Native `<dialog showModal()>`, left nav + toggle rows, `localStorage`
  persistence.
- Source toggles AND with game chips (source any-of among enabled).
- Sources not written to URL hash (shareable views stay predictable).
- Effort: **2-2.5 d**.

### G. Data-file split

- Lean `arcades.json` for map/search/markers (`game_counts` in core).
- On-demand `enrichment.json` (photos, ratings, hours, transit, long notes).
- Lazy images only when panel opens.
- Effort loader: **1-2 d**.

### H. Suggested implementation order

| Phase | Work | Days (est.) | Unlocks |
| --- | --- | --- | --- |
| P0 | Leaflet smooth zoom tune + SmoothWheelZoom | 0.5-1 | Complaint (a) partial |
| P0 | Fix `game_counts` merge emission (data) | 0.5-1 | Marker scale truth |
| P1 | Place panel + mobile sheet + minimal tooltip | 3-4 | Complaint (c) |
| P1 | Settings modal + source toggles | 2-2.5 | Sources UX |
| P1 | Omnibox + alias table | 2-3 | Complaint (b) |
| P2 | Locate + nearby list | 1-1.5 | Complaint (d) |
| P2 | Graduated markers + legend chip | 1-1.5 | Prominence |
| P2 | enrichment.json split + lazy panel fields | 1-2 | Perf + richness |
| P3 | MapLibre migrate + OpenFreeMap + raster fallback | 5-8 | True Google-like camera |

**Total to a clearly better site without MapLibre:** ~11-16 engineer-days.
**With MapLibre:** ~16-24 engineer-days.

### I. Decision one-liner

> Tune Leaflet zoom this week; rebuild detail as a dark-neon left place panel
> with settings modal and alias omnibox; split enrichment data; migrate to
> MapLibre only if vector basemap + high-Hz camera remain must-haves after
> the Leaflet tune.

---

## Primary sources (fetched or measured this session)

- Repo: `app.js`, `index.html`, `style.css`, `vendor/*`, `docs/ARCHITECTURE.md`,
  `docs/PRIOR_ART.md`, `data/arcades.json`, `data_raw/ziv.json`
- https://leafletjs.com/examples/zoom-levels/
- https://leafletjs.com/reference.html (Map options)
- https://github.com/mutsuyuki/Leaflet.SmoothWheelZoom
- https://github.com/Leaflet/Leaflet.markercluster
- https://github.com/maplibre/maplibre-gl-js/releases (v6.0.0)
- https://www.npmjs.com/package/maplibre-gl (via registry.npmjs.org)
- https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapOptions/
- https://maplibre.org/maplibre-gl-js/docs/examples/create-and-style-clusters/
- https://maplibre.org/maplibre-gl-js/docs/examples/use-locally-generated-ideographs/
- https://maplibre.org/maplibre-gl-js/docs/guides/large-data/
- https://openfreemap.org/ and https://openfreemap.org/quick_start/
- https://tiles.openfreemap.org/styles/liberty (style JSON)
- https://zenius-i-vanisher.com/v5.2/arcades.php
- https://www.npmjs.com/package/fuse.js (7.5.0 tarball sizes)
- https://www.npmjs.com/package/@leeoniya/ufuzzy (1.0.19)
- https://github.com/leeoniya/uFuzzy
- https://www.npmjs.com/package/leaflet.locatecontrol (0.90.0)
- https://github.com/domoritz/leaflet-locatecontrol
- https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog
- https://en.wikipedia.org/wiki/Proportional_symbol_map
- https://css-tricks.com/there-is-no-need-to-trap-focus-on-a-dialog-element/
- https://schalkneethling.com/posts/html-dialog-native-solution-for-accessible-modal-interactions/
