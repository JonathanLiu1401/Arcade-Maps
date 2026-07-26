"""map.bemanicn.com (China community Bemani map) scraper.

Public Inertia.js JSON endpoints (all verified live):

 (i)   GET /api/miniapp/common/region
       -> {"data": {"provinces": {code: name}, "cities": {code: name}}}
       (392 city codes; a city's province is the code whose 2-digit
       prefix matches)
 (ii)  GET /region/city/{code} with the Inertia partial headers
       (component "Region/City", partial data "city")
       -> props.city.shops = [{id, name, address, ...}]
 (iii) GET /s/{id} with the Inertia partial headers
       (component "Shop/Show", partial data "shop")
       -> props.shop.arcades = [{title_id, quantity, version, ...}]
 (iv)  GET /games (Inertia) -> props.arcade_type = [{id, name, ...}],
       used to name unmapped titles inside notes

The site's coordinate map layers are login-walled; these public
endpoints expose NO lat/lng, so every row ships coordinate-less with
coord_system "gcj02" (any coordinates this source ever grows would be
GCJ-02 and need eviltransform before plotting).

Text is kept verbatim from the source apart from whitespace collapsing
(a few addresses contain the site's own em dashes; they are source
data and are NOT rewritten, unlike common.unescape's behavior).

Output schema per row (community-file schema):
{name, name_en, address, lat, lng, coord_system, games, source,
 source_url, notes}
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

BASE = "https://map.bemanicn.com"
SLEEP = 0.5          # politeness pause after every successful request
RETRIES = 3
OUTFILE = "china_bemanicn.json"
SMOKE_CITY = "拉萨市"  # small city (3 shops) used by --smoke

# title_id -> canonical game slug; anything else becomes "other" with
# the site's own title name recorded in notes
TITLE_GAME = {
    1: "maimai_dx", 3: "chunithm", 27: "ongeki", 4: "sdvx", 5: "iidx",
    11: "ddr", 8: "gitadora", 9: "gitadora", 6: "jubeat", 34: "jubeat",
    12: "popn", 7: "nostalgia", 10: "drs", 29: "dance_around",
    31: "taiko", 15: "taiko",
}

INERTIA_HDRS = {"X-Inertia": "true", "X-Inertia-Version": "",
                "Accept": "application/json"}


def _clean(text):
    """Whitespace-collapse only; source text (incl. its own em dashes)
    is kept verbatim."""
    if text is None:
        return None
    return " ".join(str(text).split())


def _fetch_json(url, partial=None, allow_404=False):
    """GET url as JSON with retries/backoff like common.fetch.

    partial: (component, prop) adds the Inertia partial-reload headers.
    allow_404: return None immediately on HTTP 404 (shop pages vanish
    between the city index and the detail fetch)."""
    headers = {"User-Agent": common.USER_AGENT}
    headers.update(INERTIA_HDRS)
    if partial:
        headers["X-Inertia-Partial-Component"] = partial[0]
        headers["X-Inertia-Partial-Data"] = partial[1]
    last_err = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            time.sleep(SLEEP)
            return json.loads(raw.decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404 and allow_404:
                time.sleep(SLEEP)
                return None
            last_err = e
        except (urllib.error.URLError, OSError, ValueError) as e:
            last_err = e
        wait = 2 ** attempt
        print("fetch attempt %d/%d failed for %s: %s (retry in %ds)"
              % (attempt + 1, RETRIES, url, last_err, wait),
              file=sys.stderr)
        time.sleep(wait)
    raise common.FetchError("giving up on %s after %d attempts: %s"
                            % (url, RETRIES, last_err))


def fetch_cities():
    """[(city_code, city_name, province_name)] for all 392 cities."""
    data = _fetch_json(BASE + "/api/miniapp/common/region")
    d = (data or {}).get("data") or {}
    provinces = d.get("provinces") or {}
    cities = d.get("cities") or {}
    if not cities:
        raise common.FetchError("region endpoint returned no cities")
    out = []
    for code, name in cities.items():
        prov = next((p for pc, p in provinces.items()
                     if pc[:2] == code[:2]), None)
        out.append((code, _clean(name), _clean(prov)))
    return sorted(out)


def fetch_titles():
    """{title_id: title name} from the /games Inertia props."""
    data = _fetch_json(BASE + "/games")
    titles = {}
    for t in ((data or {}).get("props") or {}).get("arcade_type") or []:
        if isinstance(t, dict) and t.get("id") is not None:
            titles[t["id"]] = _clean(t.get("name")) or ("title_id=%s"
                                                        % t["id"])
    return titles


def city_shops(code):
    data = _fetch_json(BASE + "/region/city/%s" % code,
                       partial=("Region/City", "city"))
    city = ((data or {}).get("props") or {}).get("city") or {}
    return city.get("shops") or []


def shop_row(shop, city_name, prov_name, titles):
    """One output row for a city-index shop (fetches the detail page)."""
    region = (prov_name if city_name in (None, prov_name)
              else "%s %s" % (prov_name, city_name))
    detail = _fetch_json(BASE + "/s/%s" % shop["id"],
                         partial=("Shop/Show", "shop"), allow_404=True)
    games, other_names, note_parts = [], [], []
    detail_404 = detail is None
    if not detail_404:
        arcades = (((detail or {}).get("props") or {}).get("shop")
                   or {}).get("arcades") or []
        for a in arcades:
            slug = TITLE_GAME.get(a.get("title_id"))
            if slug is None:
                nm = titles.get(a.get("title_id"),
                                "title_id=%s" % a.get("title_id"))
                if nm not in other_names:
                    other_names.append(nm)
                slug = "other"
            if slug not in games:
                games.append(slug)
    if other_names:
        note_parts.append("other games: " + ", ".join(other_names))
    note_parts.append("region: " + region)
    if detail_404:
        # keep the store: it exists in the city index, only the detail
        # page is gone; games are unknown
        games = ["other"]
        note_parts.append("detail page 404 (listed in city index only)")
        note_parts.append("games unknown")
    return {
        "name": _clean(shop.get("name")),
        "name_en": None,
        "address": _clean(shop.get("address")),
        "lat": None,
        "lng": None,
        "coord_system": "gcj02",
        "games": games,
        "source": "bemanicn",
        "source_url": "%s/s/%s" % (BASE, shop["id"]),
        "notes": "; ".join(note_parts),
    }


def scrape(smoke=False):
    cities = fetch_cities()
    titles = fetch_titles()
    if smoke:
        cities = ([c for c in cities if c[1] == SMOKE_CITY]
                  or cities[:1])
    rows = []
    for ci, (code, city_name, prov_name) in enumerate(cities, 1):
        shops = city_shops(code)
        print("bemanicn: city %d/%d %s (%s): %d shops"
              % (ci, len(cities), city_name, code, len(shops)),
              file=sys.stderr)
        for shop in shops:
            if not shop.get("name") or shop.get("id") is None:
                continue
            rows.append(shop_row(shop, city_name, prov_name, titles))
    return rows


def main():
    ap = argparse.ArgumentParser(description="map.bemanicn.com scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--smoke", action="store_true",
                    help="one small city only; print rows, write nothing")
    args = ap.parse_args()
    rows = scrape(smoke=args.smoke)
    if args.smoke:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        print("smoke: %d rows (nothing written)" % len(rows),
              file=sys.stderr)
        return
    if not rows:
        common.die("bemanicn returned 0 rows")
    path = os.path.join(args.out, OUTFILE)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
