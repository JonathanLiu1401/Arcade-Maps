# Google My Maps import guide

Recreate the classic "arcade map in Google My Maps" experience with this repo's data. The generated KMZ layers live in [`mymaps/`](../mymaps/) and are sized to fit Google's import limits.

Google My Maps has **no API**: everything below is manual, in the browser. That is exactly why the [GitHub Pages map](https://jonathanliu1401.github.io/Arcade-Maps/) exists as the automated, always-fresh path. Use My Maps when you specifically want it (offline star lists, sharing into Google Maps mobile, personal annotations on top of the data).

## The limits (and how our files respect them)

Google's documented My Maps import limits:

- **10 layers per map** (a map is created with one layer; you can have up to 10)
- **2,000 features per import** (Google: "Do not import files with more than 2,000 rows")
- **5 MB per KML/KMZ file** (unzipped; other formats up to 40 MB)

`scrapers/build_mymaps.py` emits 10 primary numbered layers (01-10), each under 2,000 features and under 5 MB, so every file imports cleanly as one layer. A layer whose data exceeds 2,000 features is split into `_a`/`_b`/... KMZ part files, each of which imports as its own layer.

## Import walkthrough

1. Go to **https://www.google.com/maps/d/** and sign in.
2. Click **Create a new map**.
3. The new map starts with one empty layer ("Untitled layer"). Click **Import** inside that layer.
4. Pick `mymaps/01_*.kmz` from this repo (download the repo or grab the file from GitHub first).
5. Click **Add layer**, then **Import**, and pick `02_*.kmz`.
6. Repeat until `10_*.kmz`. Import them **in numbered order** so your layer list matches the manifest in [`mymaps/README.md`](../mymaps/README.md).
7. Rename the map (e.g. "Rhythm Arcades") and set sharing as you like.

### Optional extras (files 11 and 12)

If `mymaps/` contains files numbered `11_*` or `12_*`, they are optional extra layers. My Maps caps you at 10 layers per map, so to use an extra: **delete (or skip) one numbered layer you do not need** and import the extra in its place. Alternatively, put extras on a second map. Note that layer 12 currently ships as three part files (`12_*_a.kmz` / `_b` / `_c`), each of which needs its own layer slot; a second map is the practical home for it.

## Restyling a layer

Each layer imports with default markers. To color a whole layer:

1. In the layer's panel, click the style entry (usually "Uniform style").
2. Choose **Uniform style** if it is not already selected.
3. Click the paint-bucket / marker icon next to "All items" and pick a color and icon.

One color per layer is the practical scheme (layers are per-game or per-region, so this gives you a per-game color code). You can also style by data column ("Style by data column") if you want finer control.

## Performance warning

My Maps gets noticeably laggy with many layers of thousands of markers visible at once. Toggle layers off while browsing a region, or keep only the games you play visible. If you just want to LOOK at the data, the [GitHub Pages map](https://jonathanliu1401.github.io/Arcade-Maps/) with marker clustering is the fast path; My Maps is the "carry it in my Google account" path.

## Refreshing after a data update

My Maps layers are snapshots: they do NOT update when this repo's data refreshes. After a weekly data refresh (or whenever you want to sync):

1. Open your map at https://www.google.com/maps/d/.
2. For each layer you want to refresh: open the layer's menu and **Delete this layer**.
3. **Add layer**, **Import**, and pick the **same numbered file** (fresh copy from the repo).
4. Re-apply your layer color (styling is lost with the deleted layer).

Because the files keep stable numbered names across refreshes, "delete layer N, re-import file N" is the whole workflow. There is no way to automate this; Google provides no My Maps API.
