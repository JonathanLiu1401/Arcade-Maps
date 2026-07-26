"""Zenius -I- vanisher.com arcade database scraper.

API: https://zenius-i-vanisher.com/api/arcades.php
     ?action=query&country={name}&skip_pictures=1&skip_visitors=1&skip_comments=1
USA is too large for a single country query and must be fetched per rhythm
series id and merged by arcade id.

Entries whose name or info mark them as closed are excluded.
Coordinates are WGS-84; longitudes are wrapped to [-180, 180].

Output schema per row (matches data_extra/community.json):
{name, name_en, address, lat, lng, coord_system, games, source, source_url, notes}
plus a "country" field recording which country query returned the arcade.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

API = "https://zenius-i-vanisher.com/api/arcades.php"
ARCADE_URL = "https://zenius-i-vanisher.com/v5.2/arcade.php?id=%s"

# Rhythm series ids used for the per-series USA fetch.
USA_SERIES = {
    1: "ddr", 2: "iidx", 3: "popn", 4: "gitadora", 5: "jubeat",
    12: "taiko", 173: "sdvx", 267: "gitadora", 284: "maimai_dx",
    506: "chunithm", 549: "museca", 643: "nostalgia", 694: "drs",
    1366: "ongeki", 1556: "dance_around",
}

# Substring -> canonical slug mapping for ZIV cab/game titles.
GAME_PATTERNS = [
    ("dancedancerevolution", "ddr"), ("dance dance revolution", "ddr"),
    ("beatmania iidx", "iidx"), ("pop'n music", "popn"), ("popn music", "popn"),
    ("guitarfreaks", "gitadora"), ("drummania", "gitadora"),
    ("gitadora", "gitadora"), ("jubeat", "jubeat"),
    ("太鼓の達人", "taiko"), ("taiko no tatsujin", "taiko"),
    ("sound voltex", "sdvx"), ("maimai", "maimai_dx"),
    ("chunithm", "chunithm"), ("museca", "museca"),
    ("nostalgia", "nostalgia"), ("dancerush", "drs"),
    ("dance around", "dance_around"), ("dance around", "dance_around"),
    ("ongeki", "ongeki"), ("オンゲキ", "ongeki"),
    ("polaris chord", "polaris_chord"), ("project diva", "project_diva"),
    ("danceevolution", "dance_evo"), ("reflec beat", "reflec"),
]

_CLOSED_RE = re.compile(r'closed|permanently closed|閉店', re.I)


def _slugs_for_cabs(cab_names):
    slugs = set()
    for cab in cab_names:
        low = cab.lower()
        hit = False
        for pat, slug in GAME_PATTERNS:
            if pat in low or pat in cab:
                slugs.add(slug)
                hit = True
        if not hit:
            slugs.add("other")
    return sorted(slugs) or ["other"]


def _wrap_lng(lng):
    while lng > 180:
        lng -= 360
    while lng < -180:
        lng += 360
    return lng


def _parse_arcades(payload, country):
    """Normalize one API response into output rows keyed by arcade id."""
    out = {}
    arcades = payload.get("arcades") if isinstance(payload, dict) else payload
    if isinstance(arcades, dict):
        arcades = list(arcades.values())
    if not isinstance(arcades, list):
        return out
    for a in arcades:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("id") or a.get("arcadeid") or "")
        name = common.unescape(str(a.get("name") or ""))
        if not aid or not name:
            continue
        info = str(a.get("info") or "")
        if _CLOSED_RE.search(name) or _CLOSED_RE.search(info):
            continue
        lat = a.get("latitude") or a.get("lat")
        lng = a.get("longitude") or a.get("lng")
        try:
            lat = float(lat) if lat not in (None, "") else None
            lng = _wrap_lng(float(lng)) if lng not in (None, "") else None
        except (TypeError, ValueError):
            lat = lng = None
        cabs = []
        for c in (a.get("cabs") or a.get("machines") or []):
            if isinstance(c, dict):
                cabs.append(str(c.get("name") or ""))
            else:
                cabs.append(str(c))
        cabs = [c for c in cabs if c and not _CLOSED_RE.search(c)]
        addr_bits = [str(a.get(k) or "") for k in
                     ("address", "city", "state", "postalcode")]
        addr = ", ".join(b for b in addr_bits if b)
        notes = "Cabs: " + "; ".join(sorted(set(cabs))) if cabs else None
        out[aid] = {
            "name": name,
            "name_en": name if name.isascii() else None,
            "address": common.unescape(addr),
            "lat": lat,
            "lng": lng,
            "coord_system": "wgs84",
            "games": _slugs_for_cabs(cabs),
            "source": "ziv",
            "source_url": ARCADE_URL % aid,
            "notes": notes,
            "country": country,
        }
    return out


def fetch_country(country):
    url = (API + "?action=query&country=" + urllib.parse.quote(country)
           + "&skip_pictures=1&skip_visitors=1&skip_comments=1")
    return _parse_arcades(json.loads(common.fetch(url)), country)


def fetch_usa():
    merged = {}
    for sid in sorted(USA_SERIES):
        url = (API + "?action=query&country=USA&series_id=%d" % sid
               + "&skip_pictures=1&skip_visitors=1&skip_comments=1")
        part = _parse_arcades(json.loads(common.fetch(url)), "USA")
        for aid, row in part.items():
            if aid in merged:
                merged[aid]["games"] = sorted(
                    set(merged[aid]["games"]) | set(row["games"]))
            else:
                merged[aid] = row
    return merged


def main():
    ap = argparse.ArgumentParser(description="ZIv arcade scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--country", action="append", required=True,
                    help="country name(s) as ZIV spells them; "
                         "use USA for the per-series United States fetch")
    ap.add_argument("--outfile", default="ziv.json")
    args = ap.parse_args()
    merged = {}
    for country in args.country:
        got = fetch_usa() if country.upper() == "USA" else fetch_country(country)
        print("ziv %s: %d arcades" % (country, len(got)), file=sys.stderr)
        merged.update(got)
    if not merged:
        common.die("ziv returned 0 arcades for %s" % args.country)
    rows = sorted(merged.values(), key=lambda r: (r["country"], r["name"]))
    path = os.path.join(args.out, args.outfile)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
