"""Orchestrate the full Arcade Maps pipeline.

  scrape all sources -> data_raw/   (skippable with --skip-scrape)
  merge              -> data/arcades.json, stats.json, merge_log.json
  build MyMaps       -> mymaps/*.kmz + *.csv

Scrape steps run the individual scraper CLIs in-process. A scraper
failure aborts the run (nonzero exit) rather than producing partial
silent output. ZIV country spellings must match ZIV's own list; adjust
ZIV_COUNTRIES as needed.
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
import common

ZIV_COUNTRIES = [
    "Japan", "USA", "Canada", "Mexico", "Brazil", "Argentina", "Chile",
    "United Kingdom", "France", "Germany", "Spain", "Italy", "Australia",
    "New Zealand", "South Korea", "China", "Taiwan", "Hong Kong",
    "Singapore", "Malaysia", "Indonesia", "Thailand", "Philippines",
    "Vietnam",
]


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


def main():
    ap = argparse.ArgumentParser(description="run the full pipeline")
    ap.add_argument("--raw", default="data_raw")
    ap.add_argument("--data", default="data")
    ap.add_argument("--mymaps", default="mymaps")
    ap.add_argument("--skip-scrape", action="store_true",
                    help="reuse existing data_raw/ (no network)")
    ap.add_argument("--only", action="append",
                    choices=["allnet", "eagate", "wahlap", "bemanicn",
                             "ziv", "round1usa"],
                    help="scrape only these sources")
    args = ap.parse_args()
    if not args.skip_scrape:
        scrape_all(args.raw, set(args.only) if args.only else None)
    merge.run(args.raw, args.data)
    build_mymaps.run(args.data, args.mymaps)


if __name__ == "__main__":
    main()
