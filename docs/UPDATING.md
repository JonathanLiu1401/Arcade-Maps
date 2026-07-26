# Updating the data

## How the weekly Action works

`.github/workflows/update-data.yml` runs every Monday at 18:00 UTC
(Tuesday 03:00 JST, a quiet window for the Japanese source sites). It:

1. Checks out the repo on `ubuntu-latest` with Python 3.12.
2. Runs `python scrapers/run_all.py`, which fetches every source
   (ALL.Net, eagate, WAHLAP, BemaniCN, Zenius-I-Vanisher, Round1 USA),
   writes per-source raw output to `data_raw/`, merges everything into
   `data/arcades.json`, and rebuilds the My Maps export files under
   `mymaps/`. The BemaniCN crawl is the slowest step (one request per
   city index plus one per shop, ~4,200 requests at 0.5 s pacing).
3. Commits `data/`, `data_raw/`, and `mymaps/` as
   `github-actions[bot]` with message `data: automated refresh YYYY-MM-DD`,
   but only if something actually changed (`git diff --cached --quiet`
   guard). No changes, no commit.

Failure handling is fail-fast: every fetch retries 3 times with
exponential backoff, and if a source still fails (site down, markup
changed so a game parses to zero rows), `run_all.py` exits nonzero, the
job fails, and nothing is committed - the previously committed data
simply stays in place until a later run succeeds. There is currently no
per-source skip; one broken source blocks the whole weekly refresh.

## Triggering a refresh manually

GitHub web UI: repo -> **Actions** tab -> select **Update arcade data**
in the left sidebar -> **Run workflow** button (top right of the run
list) -> keep branch `main` -> **Run workflow**.

CLI alternative: `gh workflow run update-data.yml`.

There is also a **Smoke test scrapers** workflow (manual only) intended
to run `run_all.py --smoke` and fetch just one region per source, with
the produced files uploaded as a run artifact named `smoke-output`.
**Known gap:** the `--smoke` flag is not implemented in `run_all.py`
yet, so this workflow currently fails at argument parsing; implement
the flag before relying on it.

## Running locally on Windows

From the repo root:

```powershell
# Windows launcher (picks the newest installed Python):
py scrapers/run_all.py

# or, if python is on PATH:
python scrapers/run_all.py

# re-run merge + mymaps build from existing data_raw/ (no network):
py scrapers/run_all.py --skip-scrape

# scrape a single source only:
py scrapers/run_all.py --only eagate
```

The scrapers are stdlib-only: no virtualenv or `pip install` is needed.
Python 3.12 or newer is expected. Review the resulting diff of
`data/arcades.json` before committing.

## When a source breaks

Symptoms: the Action log shows a source marked failed, or a source's
count in `data/arcades.json` (`counts.by_source`) drops to zero or
falls sharply.

1. Look at `data_raw/` for that source: it holds the parsed per-source
   JSON rows from the last successful run (not raw HTML). Compare row
   counts against the previous commit to see what changed or vanished.
2. Open the source's URL (see `docs/DATA_SOURCES.md`) in a browser and
   compare. If the markup changed, adjust the regex / parsing in that
   source's scraper under `scrapers/` to match.
3. Re-run locally (`py scrapers/run_all.py --only <source>` first, then
   a full run) until the source produces sane counts again.
4. If the site is temporarily down rather than changed, do nothing:
   the weekly run keeps the previous data for a failing source and will
   pick it back up when the site returns.

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
