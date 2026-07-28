"""Regenerate data/china_areas.json from the AreaCity ok_geo.csv release.

Maintenance tool, like tools/build_tier_icons.py. It is NOT part of the weekly
pipeline: the table it writes changes only when China redraws an administrative
boundary, so it is committed and read, never rebuilt on a schedule.

    python tools/build_china_areas.py                       # download + build
    python tools/build_china_areas.py --csv ok_geo.csv      # from a local copy
    python tools/build_china_areas.py --check               # verify, write nothing

Source: https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov, release asset
ok_geo.csv.7z. That file carries three administrative levels - province (deep 0),
prefecture-level city (deep 1) and district/county (deep 2) - with a centroid and
a boundary polygon for each. Only the centroids are kept; the polygons are 160 MB
of the 167 MB CSV and nothing here needs them.

Downloading needs `py7zr` (the asset is a .7z). It is the ONE non-stdlib
dependency in this repo and it stops at this file: the committed JSON is what
scrapers/china_place.py reads, and that module stays stdlib-only. Pass --csv to
skip the download and the dependency entirely.

Coordinates are converted GCJ-02 -> WGS-84 at build time, so china_place never
has to think about coordinate systems. The upstream data is GCJ-02 because it is
compiled from Chinese mapping services, which are required by law to publish the
offset grid.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
import eviltransform    # noqa: E402  (path set above)

OUT_PATH = os.path.join(ROOT, "data", "china_areas.json")

RELEASE = "2025.251231.260403"
ASSET_URL = ("https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov/"
             "releases/download/%s/ok_geo.csv.7z" % RELEASE)

SOURCE_BLOCK = {
    "url": ASSET_URL,
    "repo": "https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov",
    "release": "%s (2026-04-03)" % RELEASE,
    "file": "ok_geo.csv (deep 0/1/2, centroid column `geo`; polygons dropped)",
    "license": ("MIT (repository LICENSE, Copyright (c) 2019 xiangyuecn); "
                "ok_geo.csv is marked free/open for use in the bundled data "
                "doc. Upstream administrative data compiled from "
                "国家地名信息库 2025-12-31, 腾讯地图行政区划 2025-11-19 and "
                "高德地图行政区划."),
    "native_coord_system": "gcj02",
    "levels": ("0 = province/municipality/autonomous region, 1 = "
               "prefecture-level city/prefecture/league, 2 = district/county/"
               "banner. Level 3 (乡镇/街道) exists upstream but is a paid "
               "asset except for a Shenzhen/Zhongshan/HK/Macau sample, so "
               "district is the finest level this table can reach."),
    "taiwan": ("absent upstream (the release ships no coordinates for it); "
               "china_place hard-skips Taiwan anyway."),
    "regenerate": "python tools/build_china_areas.py",
}

# Every level-2 name ends in one of these. Used only to derive the short alias
# (罗湖区 -> 罗湖) that Chinese addresses sometimes use in place of the full
# name, and to spot a name that ends in nothing recognisable so the build can
# say so instead of silently producing a useless alias.
AREA_SUFFIXES = ("特别行政区", "自治州", "自治县", "自治旗", "新区", "林区",
                 "地区", "矿区", "盟", "市", "州", "区", "县", "旗")


def base_name(name):
    """罗湖区 -> 罗湖, 深圳市 -> 深圳. Returns None when nothing is stripped."""
    for suf in AREA_SUFFIXES:
        if name.endswith(suf) and len(name) > len(suf) + 1:
            return name[:-len(suf)]
    return None


def read_rows(csv_path):
    """Yield (id, pid, deep, name, path, lat, lng) for rows that have a
    centroid. A few upstream rows carry an empty `geo` (mostly disputed or
    newly split units); they are dropped rather than guessed at."""
    csv.field_size_limit(10 ** 9)     # the polygon column is megabytes wide
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            geo = (row.get("geo") or "").split()
            if len(geo) != 2:
                continue
            try:
                lng, lat = float(geo[0]), float(geo[1])
            except ValueError:
                continue
            wlat, wlng = eviltransform.gcj2wgs(lat, lng)
            yield (row["id"], row["pid"], int(row["deep"]), row["name"],
                   row["ext_path"], round(wlat, 6), round(wlng, 6))


def build(csv_path):
    areas = {}
    dropped = 0
    for aid, pid, deep, name, _path, lat, lng in read_rows(csv_path):
        if deep > 2:
            dropped += 1
            continue
        areas[aid] = {"n": name, "p": pid, "d": deep, "lat": lat, "lng": lng}
    return areas, dropped


def check(areas):
    """Structural invariants china_place depends on. Raises on violation."""
    problems = []
    by_deep = {0: 0, 1: 0, 2: 0}
    for aid, a in areas.items():
        by_deep[a["d"]] = by_deep.get(a["d"], 0) + 1
        if a["d"] and a["p"] not in areas:
            problems.append("%s (%s) has no parent %s" % (aid, a["n"], a["p"]))
        # The southern bound has to reach 3N, not the 17N of the populated
        # mainland: 三沙市 and its two districts are the South China Sea
        # islands, and they are legitimate rows even though no arcade will
        # ever resolve to them.
        if not (3.0 <= a["lat"] <= 55.0 and 72.0 <= a["lng"] <= 136.0):
            problems.append("%s (%s) outside China: %s,%s"
                            % (aid, a["n"], a["lat"], a["lng"]))
    if not all(by_deep.get(d) for d in (0, 1, 2)):
        problems.append("a whole level is missing: %r" % by_deep)
    return by_deep, problems


def download_csv(dest_dir):
    try:
        import py7zr
    except ImportError:
        raise SystemExit(
            "downloading needs py7zr (pip install py7zr), or pass --csv with "
            "an already-extracted ok_geo.csv")
    import urllib.request
    archive = os.path.join(dest_dir, "ok_geo.csv.7z")
    print("fetching %s" % ASSET_URL)
    urllib.request.urlretrieve(ASSET_URL, archive)
    with py7zr.SevenZipFile(archive) as z:
        z.extract(dest_dir, targets=["ok_geo.csv"])
    return os.path.join(dest_dir, "ok_geo.csv")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", help="local ok_geo.csv (skips the download)")
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed table, write nothing")
    args = ap.parse_args()

    if args.check:
        with open(args.out, encoding="utf-8") as fh:
            blob = json.load(fh)
        areas = blob["areas"]
        by_deep, problems = check(areas)
        print("china_areas.json: %d areas %r" % (len(areas), by_deep))
        for p in problems[:20]:
            print("  PROBLEM: " + p)
        return 1 if problems else 0

    csv_path = args.csv or download_csv(os.path.dirname(args.out))
    areas, dropped = build(csv_path)
    by_deep, problems = check(areas)
    if problems:
        for p in problems[:20]:
            print("  PROBLEM: " + p, file=sys.stderr)
        raise SystemExit("refusing to write a table with %d problem(s)"
                         % len(problems))

    payload = {
        "source": SOURCE_BLOCK,
        "coord_system": "wgs84",
        "conversion": "gcj02 -> wgs84 at build time (scrapers/eviltransform)",
        "counts": {"province": by_deep[0], "city": by_deep[1],
                   "district": by_deep[2]},
        "areas": {k: areas[k] for k in sorted(areas)},
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"),
                  sort_keys=False)
        fh.write("\n")
    print("wrote %s: %d areas %r (%d deeper rows dropped)"
          % (args.out, len(areas), by_deep, dropped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
