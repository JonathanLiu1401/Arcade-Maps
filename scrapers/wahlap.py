"""WAHLAP (China SEGA distributor) official location scraper.

GET https://sega-register.wahlap.net/api/sega/maidx/rest/location  (maimai DX)
GET https://sega-register.wahlap.net/api/sega/midtr/rest/location  (CHUNITHM)
Each returns a single JSON array; fields include province / arcadeName /
address / placeId (no coordinates).

Output schema per row (matches the existing scratch data_extra files):
{name, name_en, address, lat, lng, coord_system, games, source, source_url, notes}
lat/lng are always null (the API has no coordinates); coord_system "unknown".
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

ENDPOINTS = {
    "maimai_dx": ("wahlap_maidx",
                  "https://sega-register.wahlap.net/api/sega/maidx/rest/location"),
    "chunithm":  ("wahlap_midtr",
                  "https://sega-register.wahlap.net/api/sega/midtr/rest/location"),
}

OUTFILE = {
    "maimai_dx": "china_wahlap_maimai_dx.json",
    "chunithm":  "china_wahlap_chunithm.json",
}


def scrape_game(slug):
    source, url = ENDPOINTS[slug]
    text = common.fetch(url, extra_headers={"Accept-Language": "zh-CN"})
    data = json.loads(text)
    if not isinstance(data, list):
        # some deployments wrap the array in {data: [...]}
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            data = data["data"]
        else:
            raise common.FetchError("unexpected JSON shape from " + url)
    rows = []
    for e in data:
        name = common.unescape(str(e.get("arcadeName") or e.get("name") or ""))
        if not name:
            continue
        meta = []
        for k in ("province", "placeId", "id"):
            if e.get(k) not in (None, ""):
                meta.append("%s=%s" % (k, e[k]))
        rows.append({
            "name": name,
            "name_en": None,
            "address": common.unescape(str(e.get("address") or "")),
            "lat": None,
            "lng": None,
            "coord_system": "unknown",
            "games": [slug],
            "source": source,
            "source_url": url,
            "notes": "; ".join(meta) if meta else None,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description="WAHLAP location scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--game", action="append", choices=sorted(ENDPOINTS),
                    help="game(s); default: both")
    args = ap.parse_args()
    for slug in (args.game or sorted(ENDPOINTS)):
        rows = scrape_game(slug)
        if not rows:
            common.die("wahlap %s returned 0 rows" % slug)
        path = os.path.join(args.out, OUTFILE[slug])
        common.save_json(path, rows)
        print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
