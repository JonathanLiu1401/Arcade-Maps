# Updating the data

## How the weekly Action works

`.github/workflows/update-data.yml` runs every Monday at 18:00 UTC
(Tuesday 03:00 JST, a quiet window for the Japanese source sites). It:

1. Checks out the repo on `ubuntu-latest` with Python 3.12.
2. Runs `python scrapers/run_all.py`, which:
   - fetches every arcade source (ALL.Net, eagate, WAHLAP, BemaniCN,
     Zenius-I-Vanisher across 65 country queries + US series crawl,
     Round1 USA) into `data_raw/`;
   - merges into `data/arcades.json` (dedupe, geo_validate, china_place
     approx centroids, stats);
   - builds `data/enrichment.json` from raw BemaniCN/ZIv extras joined by
     source URL;
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
| `data/merge_log.json` | Dedupe counts, geo_validation log, china_approx log, superseded community rows |
| `data/enrichment.json` | Optional prices, hours, transport, images, websites |
| `data/fx_rates.json` | USD FX rates for price display |
| `data/china_cities.json` | Static centroid table (not rebuilt weekly; only when the table is refreshed by hand) |
| `data_raw/*.json` | Per-source scraped rows (incl. optional enrichment fields on bemanicn/ziv rows) |
| `mymaps/*` | KMZ/CSV layers + regenerated README manifest |

### Failure handling

Arcade scrapers are fail-fast: every fetch retries 3 times with
exponential backoff, and if a source still fails (site down, markup
changed so a game parses to zero rows, or a ZIv country returns the
silent empty-200 trap), `run_all.py` exits nonzero, the job fails, and
nothing is committed - the previously committed data simply stays in
place until a later run succeeds. There is currently no per-source skip
for arcade sources; one broken arcade source blocks the whole weekly
refresh.

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
```

The scrapers are stdlib-only: no virtualenv or `pip install` is needed.
Python 3.12 or newer is expected. Review the resulting diff of
`data/arcades.json`, `data/enrichment.json`, and `data/fx_rates.json`
before committing.

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
   placement still works.
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

- If many China pins vanish or cluster oddly: check
  `merge_log.json` -> `china_approx` length (last good run ~5,735) and
  that `data/china_cities.json` is present.
- Never set Taiwan keys in `china_cities.json` without a real Taiwan
  centroid source; the placer hard-skips Taiwan by design.
- `approx: true` count should stay in the same ballpark as
  WAHLAP+BemaniCN coordinate-less volume minus merges that inherit ZIv
  pins.

## Rate-limit etiquette

These are small hobby/operator sites donating their bandwidth. The
scrapers are deliberately polite and must stay that way:

- Keep the pause between requests that the scrapers already implement;
  do not remove sleeps or parallelize fetches against one host.
- Keep the honest, identifiable User-Agent string.
- Do not run full scrapes in a tight loop while debugging; re-run the
  merge/build stages from the saved files with
  `run_all.py --skip-scrape`, or limit fetching with `--only <source>`,
  instead of re-fetching everything.
- Leave the schedule weekly and off-peak (Tuesday 03:00 JST). Arcade
  listings churn slowly; more frequent scraping gains nothing.
- If a site operator objects, stop scraping that source and open an
  issue to discuss alternatives.
