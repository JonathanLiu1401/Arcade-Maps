# Updating the data

## How the weekly Action works

`.github/workflows/update-data.yml` runs every Monday at 18:00 UTC
(Tuesday 03:00 JST, a quiet window for the Japanese source sites). It:

1. Checks out the repo on `ubuntu-latest` with Python 3.12.
2. Runs `python scrapers/run_all.py`, which:
   - fetches every arcade source (ALL.Net, eagate, WAHLAP, BemaniCN,
     Zenius-I-Vanisher across 65 country queries + US series crawl,
     Round1 USA) into `data_raw/`;
   - merges into `data/arcades.json` (dedupe, geo_validate, China
     placement from the committed `data/china_geocode.json` cache,
     china_place centroids for the residue, stats);
   - builds `data/enrichment.json` from the enrichment fields on the raw
     BemaniCN/ZIv rows joined by source URL, plus venue photos joined by
     merged arcade id from the committed photo sidecars, plus the
     measured price table (`scrapers/prices.py`). Every TEXT field in
     the committed `data_raw/` comes from ZIv; BemaniCN contributes
     photos only;
   - rebuilds the My Maps export files under `mymaps/`;
   - bakes `data/fx_rates.json` (Frankfurter primary, open.er-api.com
     gap-fill / fallback).
   The BemaniCN crawl is the slowest step (one request per city index
   plus one per shop, ~4,200 requests at 0.5 s pacing).
3. Commits `data/`, `data_raw/`, and `mymaps/` as
   `github-actions[bot]` with message `data: automated refresh YYYY-MM-DD`,
   but only if something actually changed (`git diff --cached --quiet`
   guard). No changes, no commit.

### What a successful weekly run produces

| Path | Role |
|---|---|
| `data/arcades.json` | Canonical merged arcades (incl. `approx` China pins) |
| `data/stats.json` | Totals / by_game / by_source / by_country |
| `data/merge_log.json` | Dedupe counts, geo_validation log, china_geocoded / china_geocode_rejected / china_approx logs, superseded community rows |
| `data/enrichment.json` | Optional extras: ZIv opening hours, venue info text, website and per-machine prices; venue photos; the measured `prices` table |
| `data/fx_rates.json` | USD FX rates for price display |
| `mymaps/*` | KMZ/CSV layers + regenerated README manifest |
| `data_raw/*.json` | Per-source scraped rows (incl. optional enrichment fields on bemanicn/ziv rows) |

**Read, never written, by a weekly run.** These are committed artefacts from
manual steps. The Action needs no API key for any of them, and must not gain
one:

| Path | Refreshed by |
|---|---|
| `data/china_areas.json` | `tools/build_china_areas.py`, by hand |
| `data/hk_romanize.json` | `tools/build_hk_romanize.py`, by hand. Used only by the Hong Kong / Macau merge tier |
| `data/china_geocode.json` | `run_all.py --skip-scrape --only geocode`, by name only. Keyless by default (Baidu); `AMAP_KEY` / `GOOGLE_MAPS_API_KEY` win when set |
| `data/china_manual_coords.json` | Hand-researched pins, edited by a human. Every record needs a `source_url` and a `name` |
| `data_raw/ziv_photos.json`, `data_raw/chain_photos.json`, `data_raw/bemanicn_photos.json`, `data_raw/photo_index.json`, `data_raw/photo_quality.json` | The manual photo crawls in `docs/DATA_SOURCES.md` section 11 |
| `assets/venues/cn/*.jpg` | `scrapers/bemanicn_photos.py`, by hand |
| `data/place_ids.json` | `scrapers/place_ids.py`, opt-in and needs a Google key. **Absent from the tree today** because nobody has run it; the frontend treats that as "feature off". See `docs/GOOGLE_PHOTOS.md` |

### Failure handling

Arcade scrapers are fail-fast: every fetch retries 3 times with
exponential backoff, and if a source still fails (site down, markup
changed so a game parses to zero rows, or a ZIv country returns the
silent empty-200 trap), `run_all.py` exits nonzero, the job fails, and
nothing is committed - the previously committed data simply stays in
place until a later run succeeds. There is currently no per-source skip
for arcade sources; one broken arcade source blocks the whole weekly
refresh.

**A quiet shrink is caught separately.** The checks above are all
fail-loud: a source returning nothing, a ZIv country hitting the empty-200
trap. None of them notice an upstream that answers every request and
returns a third of its usual rows, because that produces a smaller but
perfectly well-formed dataset. `scrapers/guard_regression.py` runs after
the build and before the commit, compares the fresh output against what is
already committed, and fails the job when the drop is implausible, so
nothing lands and the previous data stays live.

It checks `data_raw/` as well as `data/`, and that matters: dedupe folds
most community rows into official entries, so a 30% collapse in raw ZIv
rows moves the merged arcade total by only about half a percent and would
sail past a merged-only check. It also tracks ZIv country coverage, which
is the sharpest signal that source has, since rows drift but a whole
country going missing does not.

Defaults are loose on purpose: more than 5% off the total, more than 25%
off any one source or raw file, a source vanishing, or any ZIv country
disappearing. Growth is never blocked. If a shrink is real, re-run the
workflow with raised thresholds or run it locally with `--force` and
commit by hand:

```
python scrapers/guard_regression.py             # compare against HEAD
python scrapers/guard_regression.py --force     # report but exit 0
python scrapers/guard_regression.py --source-drop 40
```

**FX is the graceful exception.** `scrapers/fx.py` never fails the job
for feed problems: if Frankfurter and open.er-api.com both fail (or
required codes remain missing after both), it leaves the previous
`data/fx_rates.json` in place, prints a warning, and returns success so
arcade data can still commit. Stale FX is better than blocking the map
refresh. When only some codes are missing from the primary, the fallback
fills gaps and the combined `source` / per-code `sources` map records
where each rate came from.

## Triggering a refresh manually

GitHub web UI: repo -> **Actions** tab -> select **Update arcade data**
in the left sidebar -> **Run workflow** button (top right of the run
list) -> keep branch `main` -> **Run workflow**.

CLI alternative: `gh workflow run update-data.yml`.

There is also a **Smoke test scrapers** workflow (manual only) that runs
`run_all.py --smoke`: one-region connectivity probes per source, writing
`data_raw/smoke_*.json` (real raw files untouched), skipping merge and
My Maps. Partial failures are tolerated (exit 0 unless every source
fails). FX smoke performs the real one-request fetch and may write
`data/fx_rates.json` on success.

## Running locally on Windows

From the repo root:

```powershell
# Windows launcher (picks the newest installed Python):
py scrapers/run_all.py

# or, if python is on PATH:
python scrapers/run_all.py

# re-run merge + mymaps + fx from existing data_raw/ (no arcade network):
py scrapers/run_all.py --skip-scrape

# scrape a single source only (merge still runs unless you pass only fx):
py scrapers/run_all.py --only eagate

# FX only (re-fetch rates; does not re-merge):
py scrapers/run_all.py --only fx

# connectivity smoke (no merge / My Maps):
py scrapers/run_all.py --smoke

# opt-in China address geocoding. Refreshes data/china_geocode.json only;
# re-run the merge afterwards so the new coordinates reach
# data/arcades.json:
py scrapers/run_all.py --skip-scrape --only geocode
py scrapers/run_all.py --skip-scrape
```

`--only geocode` is never part of a default run, and the reason is time
rather than money: the default provider is Baidu's **keyless** public
endpoint, so no API key is needed, but a full pass is a couple of hours of
polite serial requests against an undocumented endpoint. `AMAP_KEY` or
`GOOGLE_MAPS_API_KEY` take precedence when they are set in the environment.
The answers are committed, so an ordinary build (including every CI run)
reads the file and makes no request at all, and nobody re-pays for the same
address. `--limit N` caps how many NEW addresses one run buys, which is how
a first full pass over the coordinate-less China rows can be spread out.
Addresses nothing resolves are stored as explicit misses so a later refresh
does not retry the same dead ends.

The scrapers are stdlib-only: no virtualenv or `pip install` is needed.
Python 3.12 or newer is expected. Review the resulting diff of
`data/arcades.json`, `data/enrichment.json`, and `data/fx_rates.json`
before committing.

## Refreshing venue photos (manual, occasional)

None of this is wired into `run_all.py` or the weekly Action, on purpose:
each crawl is hours of somebody else's bandwidth, and the results are
committed artefacts a normal build simply reads. Run them when coverage
has clearly gone stale, not on a schedule. Full source-by-source detail,
including the licence position for each, is in `docs/DATA_SOURCES.md`
section 11.

```powershell
# 1. harvest. Each writes its own sidecar under data_raw/.
py scrapers/photos.py                      # ZIv, without skip_pictures
py scrapers/chain_photos.py --all          # ZIv full-country sweep + Commons + link-outs

# BemaniCN thumbnails: mirrors BYTES into assets/venues/cn/, because the
# upstream URLs are signed and expire within the hour. ~4.5 h serially,
# resumable from its journal, so smoke it first.
py scrapers/bemanicn_photos.py --limit 25
py scrapers/bemanicn_photos.py

# 2. score every image from its header (ranked, not just filtered)
py scrapers/photo_quality.py --enrichment data/enrichment.json --out data_raw/photo_quality.json

# 3. unify every harvest into data_raw/photo_index.json. Offline, no network.
#    This is the file enrich.py joins BY ARCADE ID, so skipping it means the
#    new photos never reach the site.
py scrapers/photos.py --merge

# 4. re-merge so the index reaches data/enrichment.json
py scrapers/run_all.py --skip-scrape
```

Step 3 is the one that is easy to forget and silent when missed. Two checks on
the diff afterwards: `counts.arcades_with_venue_photos` in
`data/enrichment.json` should move in the direction you expect, and every
`file` path in the new records must exist under `assets/venues/`. A record
carrying `file` and no `url` is normal for the mirrored China photos, and it is
exactly the shape a renderer has silently dropped before, leaving thousands of
photos sitting in the repo unseen.

Google Places photos are a separate, optional, keyed path and are documented
on their own: [`docs/GOOGLE_PHOTOS.md`](GOOGLE_PHOTOS.md). `scrapers/place_ids.py`
is not part of `run_all.py` and makes no request without `GOOGLE_MAPS_API_KEY`.

## When a source breaks

Symptoms: the Action log shows a source marked failed, or a source's
count in `data/arcades.json` (`counts.by_source`) drops to zero or
falls sharply. ZIv empty-200 traps abort the run loudly with
`ziv <country> returned 0 arcades`.

1. Look at `data_raw/` for that source: it holds the parsed per-source
   JSON rows from the last successful run (not raw HTML). Compare row
   counts against the previous commit to see what changed or vanished.
2. Open the source's URL (see `docs/DATA_SOURCES.md`) in a browser and
   compare. If the markup changed, adjust the regex / parsing in that
   source's scraper under `scrapers/` to match.
3. For ZIv specifically: probe the country spelling live. An unknown
   name returns HTTP 200 with an empty arcades list (not an error).
   Never add a country without a live non-empty probe. `"USA"` is only
   the run_all sentinel; the API name is `"United States"`.
4. For BemaniCN: confirm Inertia partial headers still return JSON shop
   payloads; login-walled coordinate routes remaining 302 is expected.
   If enrichment fields disappear from raw rows, `enrichment.json`
   simply omits them (`bemanicn_rows_contributed` drops) while arcade
   placement still works. That counter reads **3,100** of 3,812 in the
   current build, and every one of those contributions is a PHOTO: the
   committed BemaniCN rows still carry no text enrichment, so every
   text field in `enrichment.json` today comes from ZIv. A drop in that
   counter with the photo sidecars untouched therefore means the photo
   JOIN broke, not the crawl.
5. Re-run locally (`py scrapers/run_all.py --only <source>` first, then
   a full run) until the source produces sane counts again.
6. If the site is temporarily down rather than changed, do nothing:
   the weekly run keeps the previous committed data for a failing arcade
   source and will pick it back up when the site returns.

### FX-specific checks

- Primary URL: `https://api.frankfurter.app/latest?from=USD`
- Fallback: `https://open.er-api.com/v6/latest/USD`
- If rates look wrong: inspect `data/fx_rates.json` `sources` map and
  `fetched_at`. Soft sanity bands in `fx.py` (JPY/HKD/CNY) log loudly
  when a rate is out of band but still accept it.
- If both feeds are down: previous file remains; the map still loads
  with last week's conversion factors. Re-run `py scrapers/run_all.py
  --only fx` when the feeds recover.

### China placement checks

Two different mechanisms place China rows now, and they have different
healthy values. `merge_log.json` carries a log for each:

- **`china_geocoded`** is the main path: rows placed from the committed
  address cache. Last good run **4,200**, all at level `address`. A sharp
  drop here means `data/china_geocode.json` is missing or truncated, not
  that addresses changed.
- **`china_approx`** is now only the residue that no cached answer covers.
  Last good run **9** (7 district, 2 city). This number being small is
  healthy; it was ~5,625 before the geocode cache existed, so an old note
  quoting thousands is describing the previous design.
- **`china_geocode_rejected`** lists cached answers the district gate
  refused at read time. Last good run **1**. A jump here means upstream
  addresses changed shape or the area table moved, and those rows fall
  through to a centroid rather than being placed wrongly.
- Never add Taiwan rows to `china_areas.json` without a real Taiwan
  centroid source; the placer hard-skips Taiwan by design, as it does
  Hong Kong and Macau.
- Run `python scrapers/test_china_place.py` and
  `python scrapers/test_geocode_cn.py` before assuming the data moved.
- **`approx: true` should stay high, and that is correct.** All 5,767
  placed China rows carry it. The flag does not mean "we failed to
  geocode this"; it means the pin was derived rather than published, and
  a POI search answers with a building rather than necessarily the right
  one. Do not add a step that clears it: one was written, measured to be
  roughly a fifth wrong in both directions, and deleted. The metric that
  actually tracks placement quality is how many rows SHARE a coordinate
  while claiming precision, which is 2. See the README China accuracy
  disclosure and the comment in `merge.py`.
- If a hand-researched pin in `data/china_manual_coords.json` stops
  applying, look for a loud warning about a name/id mismatch rather than
  assuming the file is ignored: merge renumbers ids on every build, so a
  record whose venue has shifted id is refused on purpose and needs
  re-keying to the new id.

## Rate-limit etiquette

These are small hobby/operator sites donating their bandwidth. The
scrapers are deliberately polite and must stay that way:

- Keep the pause between requests that the scrapers already implement;
  do not remove sleeps or parallelize fetches against one host.
- Keep the single shared User-Agent (`USER_AGENT` in
  `scrapers/common.py`). It is a fixed desktop-browser string today,
  not a project-identifying one; switching to an honest project UA is
  desirable but untested against the eagate WAF.
- Do not run full scrapes in a tight loop while debugging; re-run the
  merge/build stages from the saved files with
  `run_all.py --skip-scrape`, or limit fetching with `--only <source>`,
  instead of re-fetching everything.
- Leave the schedule weekly and off-peak (Tuesday 03:00 JST). Arcade
  listings churn slowly; more frequent scraping gains nothing.
- If a site operator objects, stop scraping that source and open an
  issue to discuss alternatives.
