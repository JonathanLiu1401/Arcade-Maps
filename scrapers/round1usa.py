"""Round1 USA store list scraper (storepoint.co API).

GET https://api.storepoint.co/v1/16026f2c5ac3c7/locations?rq
-> {results: {locations: [...]}}
"coming soon" stores are excluded. Per-store game lineups are not
published, so every store is tagged with the standard Round1 US lineup.

Output schema per row (matches data_extra/community.json):
{name, name_en, address, lat, lng, coord_system, games, source, source_url, notes}
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

API = "https://api.storepoint.co/v1/16026f2c5ac3c7/locations?rq"
GAMES = ["chunithm", "ddr", "drs", "maimai_dx", "sdvx", "taiko"]
NOTE = "Standard Round1 US lineup, per-store lineup not published"


def scrape():
    payload = json.loads(common.fetch(API))
    locs = (payload.get("results") or {}).get("locations")
    if not isinstance(locs, list):
        raise common.FetchError("unexpected JSON shape from storepoint API")
    rows = []
    for loc in locs:
        name = common.unescape(str(loc.get("name") or ""))
        if not name or "coming soon" in name.lower():
            continue
        lat = loc.get("loc_lat")
        lng = loc.get("loc_long")
        try:
            lat = float(lat) if lat not in (None, "") else None
            lng = float(lng) if lng not in (None, "") else None
        except (TypeError, ValueError):
            lat = lng = None
        slug = str(loc.get("slug") or "").strip()
        rows.append({
            "name": name,
            "name_en": name,
            "address": common.unescape(str(loc.get("streetaddress") or "")),
            "lat": lat,
            "lng": lng,
            "coord_system": "wgs84",
            "games": list(GAMES),
            "source": "round1usa",
            "source_url": ("https://www.round1usa.com/locations/" + slug
                           if slug else "https://www.round1usa.com/locations"),
            "notes": NOTE,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description="Round1 USA scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--outfile", default="round1usa.json")
    args = ap.parse_args()
    rows = scrape()
    if not rows:
        common.die("round1usa returned 0 stores")
    path = os.path.join(args.out, args.outfile)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
