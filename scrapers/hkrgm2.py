"""Hong Kong Rhythm Game Map 2 (HKRGM2) scraper.

Primary: live API GET https://hkrgm2-backend.vercel.app/places/all
Fallback: committed sample SQLite on GitHub
  WhiteNightAWA/hkrgm2-backend master test.sqlite (table places)

games JSON shape per place: {slug: [cab_count, version, price_HKD], ...}
HKRGM2 slugs are mapped onto Arcade Maps GAME_SLUGS.

Output rows (merge-friendly community family):
  name, address, lat, lng, coord_system, games, game_counts,
  game_prices, game_versions, source, source_url, country, notes
Keyed by stable place id in source_url (never row index).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

API_URL = "https://hkrgm2-backend.vercel.app/places/all"
SQLITE_URL = (
    "https://raw.githubusercontent.com/WhiteNightAWA/"
    "hkrgm2-backend/master/test.sqlite"
)
SITE_URL = "https://whitenightawa.github.io/hkrgm2/"
SOURCE = "hkrgm2"

# HKRGM2 game key -> Arcade Maps slug. Unknown keys fall to "other"
# and the raw key is recorded in notes.
GAME_MAP = {
    "maimaidx": "maimai_dx",
    "maimai": "maimai_dx",  # classic FiNALE etc.; count still useful
    "chunithm": "chunithm",
    "sdvx": "sdvx",
    "iidx": "iidx",
    "jubeat": "jubeat",
    "taiko": "taiko",
    "taiko_old": "taiko",
    "gtdr_dm": "gitadora",
    "gtdr_gf": "gitadora",
    "gitadora": "gitadora",
    "reflec": "reflec",
    "rb": "reflec",
    "wacca": "wacca",
    "gc": "groove_coaster",
    "diva": "project_diva",
    "ddr": "ddr",
    "pnm": "popn",
    "popn": "popn",
    "nostalgia": "nostalgia",
    "dr": "drs",
    "drs": "drs",
    "de": "dance_evo",
    "ongeki": "ongeki",
    "museca": "museca",
    "polaris": "polaris_chord",
}


def _as_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean(text):
    if text is None:
        return None
    # common.unescape also collapses whitespace and strips en/em dashes
    return common.unescape(str(text).replace("\r", "\n"))


def _parse_games(raw):
    """Return (games_list, counts, prices, versions, other_keys, cab_lines).

    prices are HKD per play when present.
    versions are free-text version strings (first seen per slug).
    cab_lines is a human list preserving raw HKRGM2 keys so classic
    maimai and maimaidx do not lose separate version/price in notes.
    """
    empty = ([], {}, {}, {}, [], [])
    if raw is None or raw == "":
        return empty
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return [], {}, {}, {}, ["unparseable_games"], []
    elif isinstance(raw, dict):
        obj = raw
    else:
        return empty

    games = []
    counts = {}
    prices = {}
    versions = {}
    other_keys = []
    cab_lines = []
    for key, val in obj.items():
        slug = GAME_MAP.get(key)
        if slug is None:
            other_keys.append(key)
            slug = "other"
        cab = None
        ver = None
        price = None
        if isinstance(val, (list, tuple)):
            if len(val) >= 1:
                try:
                    cab = int(val[0])
                except (TypeError, ValueError):
                    cab = None
            if len(val) >= 2 and val[1] not in (None, ""):
                ver = _clean(val[1])
            if len(val) >= 3 and val[2] not in (None, ""):
                try:
                    price = int(val[2])
                except (TypeError, ValueError):
                    try:
                        price = float(val[2])
                    except (TypeError, ValueError):
                        price = None
        if slug not in games:
            games.append(slug)
        if cab is not None and cab > 0:
            # sum if both classic maimai + maimaidx map to maimai_dx
            counts[slug] = counts.get(slug, 0) + cab
        if ver and slug not in versions:
            versions[slug] = ver
        if price is not None and slug not in prices:
            prices[slug] = price
        # preserve raw key detail (classic vs DX, old taiko, etc.)
        bit = "%s->%s" % (key, slug)
        if cab is not None:
            bit += " x%d" % cab
        if ver:
            bit += " (%s)" % ver
        if price is not None:
            bit += " HK$%s" % price
        cab_lines.append(bit)
    if not games:
        games = ["other"]
    return games, counts, prices, versions, other_keys, cab_lines


def _row_from_place(p, data_origin):
    pid = str(p.get("id") or "").strip()
    if not pid:
        return None
    name = _clean(p.get("name"))
    if not name:
        return None

    place_d = _clean(p.get("placeD") or p.get("place_d"))
    desc = _clean(p.get("desc"))
    addr_parts = []
    if place_d:
        addr_parts.append(place_d)
    if desc:
        # desc is often floor notes like "*2樓"
        addr_parts.append(desc.lstrip("*").strip())
    address = ", ".join(addr_parts) if addr_parts else None

    lat = _as_float(p.get("locationX") if "locationX" in p else p.get("lat"))
    lng = _as_float(p.get("locationY") if "locationY" in p else p.get("lng"))

    games, counts, prices, versions, other_keys, cab_lines = _parse_games(
        p.get("games")
    )

    note_parts = []
    if data_origin:
        note_parts.append("data: " + data_origin)
    last_edit = p.get("last_edit") or p.get("lastEdit")
    if last_edit:
        note_parts.append("last_edit " + str(last_edit)[:19])
    district = _clean(p.get("place"))
    if district:
        note_parts.append("area code " + district)
    if other_keys:
        note_parts.append(
            "unmapped game keys: " + ", ".join(sorted(set(other_keys)))
        )
    if cab_lines:
        note_parts.append("cabs: " + "; ".join(cab_lines))

    source_url = SITE_URL + "#place=" + pid
    row = {
        "name": name,
        "name_en": None,
        "address": address,
        "lat": lat,
        "lng": lng,
        "coord_system": "wgs84",
        "games": games,
        "source": SOURCE,
        "source_url": source_url,
        "country": "Hong Kong",
        "notes": "; ".join(note_parts),
        "sid": pid,
    }
    if counts:
        row["game_counts"] = {s: counts[s] for s in sorted(counts)}
    if prices:
        # store as "HK$N" strings to match bemanicn-ish enrichment style
        row["game_prices"] = {
            s: "HK$%s" % prices[s] for s in sorted(prices)
        }
    if versions:
        row["game_versions"] = {s: versions[s] for s in sorted(versions)}
    return row


def fetch_live_api(timeout=45):
    """Return list of place dicts from live API, or raise FetchError."""
    text = common.fetch(API_URL, timeout=timeout, retries=3, sleep=0.5)
    data = json.loads(text)
    if isinstance(data, dict):
        # tolerate {places: [...]} or {data: [...]}
        for key in ("places", "data", "results", "rows"):
            if isinstance(data.get(key), list):
                return data[key]
        raise common.FetchError("unexpected API object keys: %s"
                                % list(data.keys())[:12])
    if not isinstance(data, list):
        raise common.FetchError("unexpected API type: %s" % type(data).__name__)
    return data


def fetch_sqlite_fallback():
    """Download GitHub test.sqlite and return places as list of dicts."""
    raw = None
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                SQLITE_URL, headers={"User-Agent": common.USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            time.sleep(common.DEFAULT_SLEEP)
            break
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            last_err = e
            time.sleep(2 ** attempt)
    if raw is None:
        raise common.FetchError(
            "sqlite fallback failed after 3 attempts: %s" % last_err
        )

    # write to temp file (sqlite needs a path)
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(raw)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM places").fetchall()
        finally:
            conn.close()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    out = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return out


def scrape(prefer_api=True):
    """Scrape HKRGM2 places. Returns (rows, origin_label)."""
    places = None
    origin = None
    if prefer_api:
        try:
            places = fetch_live_api()
            origin = "api"
            print("hkrgm2: live API returned %d places" % len(places),
                  file=sys.stderr)
        except (common.FetchError, json.JSONDecodeError, ValueError) as e:
            print("hkrgm2: live API failed (%s); using GitHub sqlite"
                  % e, file=sys.stderr)
    if places is None:
        places = fetch_sqlite_fallback()
        origin = "github_sqlite"
        print("hkrgm2: sqlite fallback returned %d places" % len(places),
              file=sys.stderr)

    rows = []
    seen = set()
    for p in places:
        if not isinstance(p, dict):
            continue
        row = _row_from_place(p, origin)
        if row is None:
            continue
        sid = row["sid"]
        if sid in seen:
            continue
        seen.add(sid)
        rows.append(row)
    return rows, origin


def main():
    ap = argparse.ArgumentParser(description="HKRGM2 Hong Kong cab map scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--outfile", default="hkrgm2.json")
    ap.add_argument("--smoke", action="store_true",
                    help="write at most 5 rows (and smoke_hkrgm2.json)")
    ap.add_argument("--sqlite-only", action="store_true",
                    help="skip live API; use GitHub test.sqlite only")
    args = ap.parse_args()

    rows, origin = scrape(prefer_api=not args.sqlite_only)
    if not rows:
        common.die("hkrgm2 returned 0 places")

    if args.smoke:
        rows = rows[:5]
        out_name = "smoke_hkrgm2.json"
    else:
        out_name = args.outfile

    path = os.path.join(args.out, out_name)
    # strip internal sid before write? Keep it - merge can use source_url.
    # Also keep sid for stable identity.
    common.save_json(path, rows)
    print("wrote %s (%d rows, origin=%s)" % (path, len(rows), origin))


if __name__ == "__main__":
    main()
