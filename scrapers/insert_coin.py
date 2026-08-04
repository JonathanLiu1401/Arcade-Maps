"""Insert Coin (insert-coin.app) multi-country rhythm arcade scraper.

Public backend API (API Platform / Symfony):
  GET https://backend.insert-coin.app/api/games?itemsPerPage=100&page=N
  GET https://backend.insert-coin.app/api/locations?locationGames.game.uuid={uuid}
      &itemsPerPage=1000
  Accept: application/json

GeoJSON map (id+coords only) and per-location location_games also exist,
but reverse-indexing by Music-genre game UUID is far cheaper than fetching
~7.6k location_games payloads. Filters on address.country are ignored by
the list endpoint; locationGames.game.uuid filtering works.

Output schema (merge-friendly optional community row):
  {name, name_en, address, lat, lng, coord_system, games, game_counts,
   count_evidence, source, source_url, sid, country, notes}

sid is the Insert Coin location UUID (never a row number).
--smoke fetches a few Music titles only and writes nothing.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

API = "https://backend.insert-coin.app/api"
SITE = "https://www.insert-coin.app"
OUTFILE = "insert_coin.json"
SOURCE = "insert_coin"
ACCEPT = {"Accept": "application/json"}
GAMES_PAGE = 100
LOC_PAGE = 1000
SMOKE_GAME_LIMIT = 3

COUNTRY_MAP = {
    "AU": "Australia", "NZ": "New Zealand", "SG": "Singapore",
    "PH": "Philippines", "ID": "Indonesia", "MY": "Malaysia",
    "TH": "Thailand", "VN": "Vietnam", "IN": "India", "BN": "Brunei",
    "MM": "Myanmar", "KH": "Cambodia", "LA": "Laos",
    "JP": "Japan", "KR": "South Korea", "TW": "Taiwan", "HK": "Hong Kong",
    "MO": "Macau", "CN": "China",
    "US": "United States", "USA": "United States", "CA": "Canada",
    "MX": "Mexico", "GB": "United Kingdom", "UK": "United Kingdom",
    "FR": "France", "DE": "Germany", "IT": "Italy", "ES": "Spain",
    "NL": "Netherlands", "BE": "Belgium", "CH": "Switzerland",
    "IE": "Ireland", "AT": "Austria", "PT": "Portugal", "PL": "Poland",
    "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
    "BR": "Brazil", "AR": "Argentina", "CL": "Chile", "PE": "Peru",
    "CO": "Colombia", "UY": "Uruguay", "VE": "Venezuela",
    "ZA": "South Africa", "AE": "United Arab Emirates",
    "SA": "Saudi Arabia", "IL": "Israel", "TR": "Turkey",
    "RU": "Russia", "UA": "Ukraine", "CZ": "Czech Republic",
    "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria",
    "GR": "Greece", "CY": "Cyprus", "MN": "Mongolia",
    "PR": "Puerto Rico", "DO": "Dominican Republic",
    "SV": "El Salvador", "GH": "Ghana", "NG": "Nigeria",
    "MA": "Morocco", "IR": "Iran", "MQ": "Martinique",
    "PY": "Paraguay", "BO": "Bolivia",
}

# series title -> canonical slug (longer / more specific first)
_SERIES_RULES = [
    (re.compile(r"sound\s*voltex|\bsdvx\b", re.I), "sdvx"),
    (re.compile(r"beatmania\s*iidx|\biidx\b", re.I), "iidx"),
    (re.compile(r"dance\s*dance\s*revolution|\bddr\b", re.I), "ddr"),
    (re.compile(r"dance\s*rush|dancerush|\bdrs\b", re.I), "drs"),
    (re.compile(r"dance\s*around", re.I), "dance_around"),
    (re.compile(r"dance\s*evolution", re.I), "dance_evo"),
    (re.compile(r"pop'?n\s*music|pop'?n\b", re.I), "popn"),
    (re.compile(r"gitadora|guitar\s*freaks|drum\s*mania", re.I), "gitadora"),
    (re.compile(r"\bjubeat\b", re.I), "jubeat"),
    (re.compile(r"chunithm", re.I), "chunithm"),
    (re.compile(r"ongeki", re.I), "ongeki"),
    (re.compile(r"maimai", re.I), "maimai_dx"),
    (re.compile(r"polaris\s*chord", re.I), "polaris_chord"),
    (re.compile(r"project\s*diva|hatsune\s*miku", re.I), "project_diva"),
    (re.compile(r"nostalgia", re.I), "nostalgia"),
    (re.compile(r"\bmuseca\b", re.I), "museca"),
    (re.compile(r"reflec\s*beat", re.I), "reflec"),
    (re.compile(r"taiko\s*no\s*tatsujin|\btaiko\b", re.I), "taiko"),
    (re.compile(r"pump\s*it\s*up|\bpump\b", re.I), "pump_it_up"),
    (re.compile(r"stepmania\s*x|stepmaniax", re.I), "stepmaniax"),
    (re.compile(r"\bwacca\b", re.I), "wacca"),
    (re.compile(r"groove\s*coaster", re.I), "groove_coaster"),
    (re.compile(r"crossbeats", re.I), "crossbeats"),
    (re.compile(r"beatstream", re.I), "beatstream"),
]

# Music titles we note but do not promote to a catalog chip
_OTHER_RHYTHM = re.compile(
    r"guitar\s*hero|in\s*the\s*groove|\bitg\b|ez2ac|ez2dj|"
    r"music\s*diver|danz\s*base|technomotion|synesthesia|"
    r"beat\s*saber|chrono\s*circle|stepmania\s*converted",
    re.I,
)


def api_get(path_or_url, params=None):
    if path_or_url.startswith("http"):
        url = path_or_url
    else:
        url = API + path_or_url
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    text = common.fetch(url, extra_headers=ACCEPT)
    return json.loads(text)


def name_to_slug(name):
    """Map an Insert Coin game title to a merge slug, or None."""
    if not name:
        return None
    for rx, slug in _SERIES_RULES:
        if rx.search(name):
            return slug
    if _OTHER_RHYTHM.search(name):
        return "other"
    return None


def list_all_games():
    """Paginate the full game catalog."""
    out = []
    page = 1
    while page <= 200:
        batch = api_get("/games", {"itemsPerPage": GAMES_PAGE, "page": page})
        if not isinstance(batch, list):
            raise common.FetchError("insert_coin: unexpected games shape")
        if not batch:
            break
        out.extend(batch)
        print("insert_coin: games page %d (+%d, total %d)"
              % (page, len(batch), len(out)), file=sys.stderr)
        if len(batch) < GAMES_PAGE:
            break
        page += 1
    return out


def rhythm_games(catalog, include_other=False):
    """Return [(uuid, name, slug, locationsCount), ...] for Music/rhythm titles."""
    rows = []
    for g in catalog:
        name = g.get("name") or ""
        genre = (g.get("genre") or {}).get("name") or ""
        slug = name_to_slug(name)
        if slug is None:
            continue
        # Default path is catalog chips only (iidx/ddr/maimai/...). "other"
        # Music titles (Guitar Hero, ITG, ...) are optional noise for the map.
        if slug == "other" and not include_other:
            continue
        # Drop pattern false-positives on non-Music genres (e.g. Initial D).
        if genre and genre != "Music":
            continue
        uuid = g.get("uuid")
        if not uuid:
            continue
        nloc = int(g.get("locationsCount") or 0)
        if nloc <= 0:
            continue
        rows.append((uuid, name, slug, nloc))
    # stable: more popular titles first (helps smoke + progress signal)
    rows.sort(key=lambda t: (-t[3], t[1]))
    return rows


def locations_for_game(game_uuid):
    """All locations listing a given game UUID (paginated)."""
    out = []
    page = 1
    while page <= 50:
        batch = api_get("/locations", {
            "locationGames.game.uuid": game_uuid,
            "itemsPerPage": LOC_PAGE,
            "page": page,
        })
        if not isinstance(batch, list):
            raise common.FetchError(
                "insert_coin: unexpected locations shape for %s" % game_uuid)
        if not batch:
            break
        out.extend(batch)
        if len(batch) < LOC_PAGE:
            break
        page += 1
    return out


def format_address(addr):
    if not isinstance(addr, dict):
        return ""
    parts = []
    for key in ("address", "city", "state", "postcode", "country"):
        v = addr.get(key)
        if v not in (None, ""):
            parts.append(str(v))
    return common.unescape(", ".join(parts))


def build_row(loc_uuid, loc, slug_counts, title_notes):
    addr = loc.get("address") or {}
    name = common.unescape(str(loc.get("name") or ""))
    if not name:
        return None
    lat = addr.get("latitude")
    lng = addr.get("longitude")
    try:
        lat = float(lat) if lat not in (None, "") else None
        lng = float(lng) if lng not in (None, "") else None
    except (TypeError, ValueError):
        lat = lng = None
    cc = str(addr.get("country") or "").upper()
    country = COUNTRY_MAP.get(cc, cc or None)
    games = sorted(s for s in slug_counts if s != "other")
    if not games:
        if "other" in slug_counts:
            games = ["other"]
        else:
            games = ["other"]
    notes_parts = []
    if title_notes:
        # keep notes compact: up to ~12 titles
        shown = title_notes[:12]
        notes_parts.append("IC cabs: " + "; ".join(shown))
        if len(title_notes) > 12:
            notes_parts.append("(+%d more)" % (len(title_notes) - 12))
    ltype = (loc.get("locationType") or {}).get("name")
    if ltype:
        notes_parts.append("type: " + str(ltype))
    page_url = "%s/location/%s" % (SITE, loc_uuid)
    row = {
        "name": name,
        "name_en": name,
        "address": format_address(addr),
        "lat": lat,
        "lng": lng,
        "coord_system": "wgs84",
        "games": games,
        "source": SOURCE,
        "source_url": page_url,
        "sid": loc_uuid,
        "country": country,
        "notes": " | ".join(notes_parts),
    }
    gc = {k: v for k, v in slug_counts.items() if k != "other" and v > 0}
    if gc:
        row["game_counts"] = gc
        row["count_evidence"] = {k: "insert_coin_qty" for k in gc}
    return row


def scrape(smoke=False, max_games=None, countries=None):
    """Scrape Insert Coin rhythm locations.

    countries: optional set of ISO codes (e.g. {"AU","NZ","SG"}). None = all.
    """
    catalog = list_all_games()
    rhythm = rhythm_games(catalog, include_other=False)
    print("insert_coin: %d catalog games, %d rhythm-mapped with locations"
          % (len(catalog), len(rhythm)), file=sys.stderr)

    if smoke:
        rhythm = rhythm[:SMOKE_GAME_LIMIT]
    elif max_games is not None:
        rhythm = rhythm[:max_games]

    # loc_uuid -> {meta, slug_counts: {slug: n}, titles: [name, ...]}
    agg = {}
    for i, (guuid, gname, slug, nloc) in enumerate(rhythm):
        try:
            locs = locations_for_game(guuid)
        except common.FetchError as e:
            print("insert_coin: game %s FAILED: %s" % (gname, e),
                  file=sys.stderr)
            continue
        print("insert_coin: [%d/%d] %s (%s) -> %d locs (catalog said %d)"
              % (i + 1, len(rhythm), gname, slug, len(locs), nloc),
              file=sys.stderr)
        for loc in locs:
            luuid = loc.get("uuid")
            if not luuid:
                continue
            if countries is not None:
                cc = str((loc.get("address") or {}).get("country") or "").upper()
                if cc not in countries:
                    continue
            bucket = agg.get(luuid)
            if bucket is None:
                bucket = {
                    "loc": loc,
                    "slug_counts": {},
                    "titles": [],
                }
                agg[luuid] = bucket
            else:
                # keep freshest-looking meta (updatedAt) when present
                prev = bucket["loc"]
                if (loc.get("updatedAt") or "") > (prev.get("updatedAt") or ""):
                    bucket["loc"] = loc
            bucket["slug_counts"][slug] = bucket["slug_counts"].get(slug, 0) + 1
            if gname not in bucket["titles"]:
                bucket["titles"].append(gname)

    rows = []
    for luuid, bucket in agg.items():
        row = build_row(luuid, bucket["loc"], bucket["slug_counts"],
                        bucket["titles"])
        if row:
            rows.append(row)
    rows.sort(key=lambda r: (
        r.get("country") or "",
        r.get("name") or "",
        r.get("sid") or "",
    ))
    print("insert_coin: done %d venues" % len(rows), file=sys.stderr)
    return rows


def main():
    ap = argparse.ArgumentParser(description="Insert Coin rhythm scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--outfile", default=OUTFILE)
    ap.add_argument("--smoke", action="store_true",
                    help="few Music titles only; print rows, write nothing")
    ap.add_argument("--max-games", type=int, default=None,
                    help="cap number of Music titles reverse-indexed")
    ap.add_argument("--countries", default=None,
                    help="comma-separated ISO country codes (e.g. AU,NZ,SG)."
                         " Default: all countries.")
    args = ap.parse_args()
    countries = None
    if args.countries:
        countries = {c.strip().upper() for c in args.countries.split(",")
                     if c.strip()}
    rows = scrape(smoke=args.smoke, max_games=args.max_games,
                  countries=countries)
    if args.smoke:
        print(json.dumps(rows[:20], ensure_ascii=False, indent=1))
        print("smoke: %d venues from %d titles (nothing written)"
              % (len(rows), SMOKE_GAME_LIMIT), file=sys.stderr)
        return
    if not rows:
        common.die("insert_coin returned 0 rows")
    path = os.path.join(args.out, args.outfile)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
