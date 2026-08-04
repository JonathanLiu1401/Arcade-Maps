"""WAHLAP Rhythmvaders (Groove Coaster China) official location scraper.

GET https://wc.wahlap.net/gc/rest/location
Returns a JSON array of {id, province, arcadeName, address}. No coords.
Single-title presence flag (groove_coaster); ~31 shops.

Separate from scrapers/wahlap.py (maidx + chunithm register endpoints)
so the existing WAHLAP scraper is untouched.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

URL = "https://wc.wahlap.net/gc/rest/location"
SOURCE = "wahlap_gc"
OUTFILE = "china_wahlap_gc.json"
SLUG = "groove_coaster"


def scrape():
    text = common.fetch(URL, extra_headers={"Accept-Language": "zh-CN"})
    data = json.loads(text)
    if not isinstance(data, list):
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            data = data["data"]
        else:
            raise common.FetchError("unexpected JSON shape from " + URL)
    rows = []
    for e in data:
        name = common.unescape(str(e.get("arcadeName") or e.get("name") or ""))
        if not name:
            continue
        meta = []
        for k in ("province", "id"):
            if e.get(k) not in (None, ""):
                meta.append("%s=%s" % (k, e[k]))
        rows.append({
            "name": name,
            "name_en": None,
            "address": common.unescape(str(e.get("address") or "")),
            "lat": None,
            "lng": None,
            "coord_system": "unknown",
            "games": [SLUG],
            "source": SOURCE,
            "source_url": URL,
            "notes": "; ".join(meta) if meta else None,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(
        description="WAHLAP Groove Coaster China location scraper"
    )
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--smoke", action="store_true",
                    help="print rows only; write nothing")
    args = ap.parse_args()
    rows = scrape()
    if args.smoke:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        print("smoke: %d rows (nothing written)" % len(rows),
              file=sys.stderr)
        return
    if not rows:
        common.die("wahlap_gc returned 0 rows")
    path = os.path.join(args.out, OUTFILE)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
