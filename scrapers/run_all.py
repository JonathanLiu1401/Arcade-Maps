"""Orchestrate the full Arcade Maps pipeline.

  scrape all sources -> data_raw/   (skippable with --skip-scrape)
  merge              -> data/arcades.json, stats.json, merge_log.json,
                        enrichment.json (inside merge)
  build MyMaps       -> mymaps/*.kmz + *.csv
  FX rates           -> data/fx_rates.json (non-fatal; keeps previous)

Scrape steps run the individual scraper CLIs in-process. A scraper
failure aborts the run (nonzero exit) rather than producing partial
silent output. ZIV country spellings must match ZIV's own list; adjust
ZIV_COUNTRIES as needed. FX is the exception: a total feed failure is
non-fatal (previous fx_rates.json is retained, exit still 0 for that
step) so the weekly commit can still land other refreshed data.

--smoke runs every source in a minimal one-region connectivity mode
instead: outputs go to data_raw/smoke_*.json (real raw files are never
touched), merge and MyMaps are skipped, and a per-source PASS/FAIL
table is printed. Partial failures print loudly but exit 0; the exit
code is nonzero only when EVERY source failed. fx smoke is the real
one-request fetch (writes data/fx_rates.json on success).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allnet
import eagate
import wahlap
import bemanicn
import ziv
import round1usa
import merge
import build_mymaps
import fx
import common

# Spellings must match ZIV's own country list EXACTLY: an unknown name
# returns an empty 200, not an error (see the guard in scrape_all).
# "USA" is the sentinel for the per-series United States fetch, which
# queries ZIV under the name "United States".
# Every name below was probed live on 2026-07-27 and returned rows.
# Known-unsupported: "Panama" (no spelling ZIV accepts was found; its
# ~5 arcades are therefore not covered).
ZIV_COUNTRIES = [
    "Japan", "USA", "Canada", "Mexico", "Brazil", "Argentina", "Chile",
    "United Kingdom", "France", "Germany", "Spain", "Italy", "Australia",
    "New Zealand", "South Korea", "China", "Taiwan", "Hong Kong",
    "Singapore", "Malaysia", "Indonesia", "Thailand", "Philippines",
    "Vietnam",
    # added 2026-07-27: previously uncrawled countries that the bundled
    # community.json ziv rows did cover (ZIV lists 68 countries)
    "Colombia", "Netherlands", "South Africa", "Puerto Rico", "Poland",
    "Norway", "Iran", "Ireland", "Belgium", "Peru", "Russia", "Ukraine",
    "Israel", "Switzerland", "Uruguay", "United Arab Emirates", "India",
    "Macau", "Greece", "Hungary", "Mongolia", "Portugal", "Austria",
    "Myanmar", "Bolivia", "Denmark", "Morocco", "Romania",
    "Saudi Arabia", "Sweden", "Turkey", "Venezuela", "Bulgaria",
    "Cyprus", "Dominican Republic", "El Salvador", "Ghana", "Martinique",
    "Paraguay", "Nigeria", "Czech Republic",
]

# Small country used by --smoke (must be spelled the ZIV way).
ZIV_SMOKE_COUNTRY = "Singapore"


def scrape_all(raw_dir, only=None):
    def want(name):
        return only is None or name in only

    if want("allnet"):
        for gm in sorted(allnet.GAMES):
            slug, mode = allnet.GAMES[gm]
            rows = allnet.scrape_game(gm, mode)
            if not rows:
                common.die("allnet gm=%d returned 0 rows" % gm)
            common.save_json(os.path.join(raw_dir, slug + ".json"), rows)
    if want("eagate"):
        for gkey in sorted(eagate.GKEYS):
            rows = eagate.scrape_game(gkey)
            common.save_json(
                os.path.join(raw_dir, eagate.GKEYS[gkey] + ".json"), rows)
    if want("wahlap"):
        for slug in sorted(wahlap.ENDPOINTS):
            rows = wahlap.scrape_game(slug)
            if not rows:
                common.die("wahlap %s returned 0 rows" % slug)
            common.save_json(
                os.path.join(raw_dir, wahlap.OUTFILE[slug]), rows)
    if want("bemanicn"):
        rows = bemanicn.scrape()
        if not rows:
            common.die("bemanicn returned 0 rows")
        common.save_json(os.path.join(raw_dir, bemanicn.OUTFILE), rows)
    if want("ziv"):
        merged = {}
        for country in ZIV_COUNTRIES:
            got = (ziv.fetch_usa() if country == "USA"
                   else ziv.fetch_country(country))
            # A country whose ZIV spelling drifted returns an EMPTY
            # 200 ({"arcades": [], "success": true}) rather than an
            # error, silently dropping that whole country from the
            # crawl (this is how "USA" lost ~1,250 US arcades). Treat
            # it as a hard failure.
            if not got:
                common.die("ziv %s returned 0 arcades - check the "
                           "country spelling in ZIV_COUNTRIES" % country)
            merged.update(got)
        if not merged:
            common.die("ziv returned nothing")
        rows = sorted(merged.values(),
                      key=lambda r: (r["country"], r["name"]))
        common.save_json(os.path.join(raw_dir, "ziv.json"), rows)
    if want("round1usa"):
        rows = round1usa.scrape()
        if not rows:
            common.die("round1usa returned 0 stores")
        common.save_json(os.path.join(raw_dir, "round1usa.json"), rows)


def _smoke_ziv():
    got = ziv.fetch_country(ZIV_SMOKE_COUNTRY)
    return sorted(got.values(), key=lambda r: (r["country"], r["name"]))


def _smoke_fx(data_dir):
    """Real one-request FX fetch (primary + gap fill). Writes data/fx_rates.json.

    Returns a one-element list so the smoke table can print a row count
    (number of currency rates). Raises on total failure so smoke marks FAIL.
    """
    path, payload = fx.run(data_dir)
    if payload is None:
        raise RuntimeError("fx both feeds failed; no rates written")
    return list(payload.get("rates") or {})


def smoke_all(raw_dir, only=None, data_dir="data"):
    """One-region connectivity probe of every source.

    Writes data_raw/smoke_<source>.json (never the real raw files) for
    arcade scrapers. fx smoke writes data/fx_rates.json (real path; it is
    one cheap request and is the production artifact). Returns
    [(source, ok, row_count, error)]. Per the tolerant smoke contract,
    failures are collected rather than aborting the run.
    """
    specs = [
        # allnet: Tokyo only (at=12, ct=1000) for gm=96 (maimai JP)
        ("allnet", lambda: allnet.scrape_game(96, "jp", smoke=True)),
        # eagate: pref JP-13 (Tokyo) only, gkey SDVX only
        ("eagate", lambda: eagate.scrape_game("SDVX", smoke=True)),
        # wahlap: full maidx REST fetch (one request), first 20 rows
        ("wahlap", lambda: wahlap.scrape_game("maimai_dx")[:20]),
        # bemanicn: its existing one-small-city smoke mode
        ("bemanicn", lambda: bemanicn.scrape(smoke=True)),
        # ziv: one small country
        ("ziv", _smoke_ziv),
        # round1usa: full fetch (one request), first 5 rows
        ("round1usa", lambda: round1usa.scrape()[:5]),
        # fx: real fetch (primary + per-currency fallback); one/few requests
        ("fx", lambda: _smoke_fx(data_dir)),
    ]
    results = []
    for name, fn in specs:
        if only is not None and name not in only:
            continue
        try:
            rows = fn()
            if not rows:
                raise RuntimeError("returned 0 rows")
            # fx already wrote data/fx_rates.json; do not clobber a smoke_*.json
            if name != "fx":
                path = os.path.join(raw_dir, "smoke_%s.json" % name)
                common.save_json(path, rows)
                print("smoke %s: wrote %s (%d rows)"
                      % (name, path, len(rows)), file=sys.stderr)
            else:
                print("smoke fx: wrote data/fx_rates.json (%d rates)"
                      % len(rows), file=sys.stderr)
            results.append((name, True, len(rows), None))
        except Exception as e:
            print("SMOKE FAILURE %s: %s: %s"
                  % (name, type(e).__name__, e), file=sys.stderr)
            results.append((name, False, 0, e))
    return results


def main():
    ap = argparse.ArgumentParser(description="run the full pipeline")
    ap.add_argument("--raw", default="data_raw")
    ap.add_argument("--data", default="data")
    ap.add_argument("--mymaps", default="mymaps")
    ap.add_argument("--skip-scrape", action="store_true",
                    help="reuse existing data_raw/ (no network)")
    ap.add_argument("--only", action="append",
                    choices=["allnet", "eagate", "wahlap", "bemanicn",
                             "ziv", "round1usa", "fx"],
                    help="scrape only these sources")
    ap.add_argument("--smoke", action="store_true",
                    help="one-region connectivity probe per source; "
                         "writes data_raw/smoke_*.json, skips merge and "
                         "MyMaps; exits nonzero only if all sources fail")
    args = ap.parse_args()
    if args.smoke:
        if args.skip_scrape:
            ap.error("--smoke and --skip-scrape are mutually exclusive")
        results = smoke_all(args.raw,
                            set(args.only) if args.only else None,
                            data_dir=args.data)
        print()
        print("smoke summary:")
        print("  %-10s %-6s %s" % ("source", "status", "rows"))
        for name, ok, n, err in results:
            note = "" if ok else "  (%s: %s)" % (type(err).__name__, err)
            print("  %-10s %-6s %d%s"
                  % (name, "PASS" if ok else "FAIL", n, note))
        sys.stdout.flush()
        n_fail = sum(1 for r in results if not r[1])
        if n_fail == len(results):
            common.die("smoke: every source failed")
        if n_fail:
            print("smoke: %d/%d source(s) FAILED (tolerated; exit 0)"
                  % (n_fail, len(results)), file=sys.stderr)
        return
    only = set(args.only) if args.only else None
    if not args.skip_scrape:
        # Arcade scrapers only; fx is a post-merge step (writes data/).
        arcade_only = None if only is None else (only - {"fx"})
        if arcade_only is None or arcade_only:
            scrape_all(args.raw, arcade_only)
    # merge (incl. enrichment + china_place + geo_validate) + MyMaps
    # only when we are not restricted to fx-only.
    if only is None or (only - {"fx"}):
        merge.run(args.raw, args.data)
        build_mymaps.run(args.data, args.mymaps)
    # FX rates: non-fatal. fx.run never raises for feed failure; it keeps
    # the previous file and returns (path, None).
    if only is None or "fx" in only:
        fx.run(args.data)


if __name__ == "__main__":
    main()
