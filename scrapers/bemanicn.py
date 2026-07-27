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
plus an OPTIONAL "game_counts" {slug: int}: the shop's per-title
quantity values summed per mapped slug (titles that map to "other"
are NOT counted; the key is absent when no mapped title carried a
positive quantity).

ENRICHMENT (added 2026-07-27, all optional and all omitted when the
shop payload does not carry them - see docs/research/enrichment-sources.md
section 1a and scrapers/enrich.py):

  transport      shop.transport, HTML-stripped transit directions prose
  price_text     shop.price, the venue's token/coin unit price verbatim
  pay_type       shop.pay_type, the site's payment-mode enum (kept raw)
  hours          shop.start_time/end_time rendered "10:00-02:00 (+1d)"
                 (the site stores hours as integers with a >24 = next-day
                 convention: 10/26 means 10:00 to 02:00 the next day)
  image_thumb    shop.image_thumb.url - a SIGNED OSS URL carrying an "e="
                 epoch expiry, so it is only valid for a few weeks after
                 the crawl and consumers must tolerate a 403
  fav_count      shop.fav_count community favourites (NOT a star rating)
  game_prices    {slug: "5 coins/play (~CNY 5.00)"} from arcades[].coin,
                 costed with the venue price when both parse
  game_versions  {slug: "舞萌DX2025"} from arcades[].version
  enriched_at    ISO date this row was scraped

shop.comment (long HTML: membership packs, photo rules, QQ groups) is
deliberately NOT emitted - it is large and mostly social prose, and
enrichment.json is fetched by browsers on demand.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import enrich

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


# --------------------------------------------------------- enrichment ------

def _as_int(v):
    """int(v) for ints and clean numeric strings, else None. The site
    sends some numbers as strings ("1") and some as ints (4)."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _as_float(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _fmt_hours(start, end):
    """"10:00-22:00", or "10:00-02:00 (+1d)" when the site's >24 next-day
    convention is in play.

    None when the hours are absent, out of range, or are the s == e
    placeholder (0/0, 24/24) that means "unknown" rather than a
    zero-length day.

    A span of exactly 24 hours (0/24, 10/34, 24/48) is "24 hours": the
    naive rendering would be "00:00-00:00" / "10:00-10:00", which reads
    as CLOSED rather than always-open."""
    s, e = _as_int(start), _as_int(end)
    if s is None or e is None:
        return None
    if s == e:                       # 0/0 and 24/24 are both placeholders
        return None
    if not (0 <= s <= 48 and 0 <= e <= 48):
        return None
    if e - s >= 24:
        return "24 hours"
    out = "%02d:00-%02d:00" % (s % 24, e % 24)
    if e > 24:
        out += " (+1d)"
    return out


def _price_display(coin, shop_price):
    """"5 coins/play (~CNY 5.00)" when the venue token price parses,
    else "5 coins/play". None when the title has no coin figure."""
    c = _as_int(coin)
    if c is None or c <= 0:
        return None
    out = "%d coin%s/play" % (c, "" if c == 1 else "s")
    unit = _as_float(shop_price)
    if unit is not None and unit > 0:
        out += " (~CNY %.2f)" % (unit * c)
    return out


def shop_enrichment(shop, games_by_title):
    """Optional enrichment fields for one shop detail payload.

    `games_by_title` maps the shop's own arcades[] rows to canonical
    slugs (same mapping shop_row already computed) so per-title coin and
    version data lands under the slug the frontend filters on. Titles
    that map to "other" are skipped: several unrelated cabs share that
    bucket and their prices would overwrite each other.

    Returns {} when the payload carries nothing enrichable, so callers
    can splat it into a row without emitting empty keys."""
    out = {}
    transport = enrich.strip_html(shop.get("transport"))
    if transport:
        out["transport"] = transport
    price_text = enrich.clean_text(shop.get("price"),
                                   limit=enrich.MAX_PRICE_TEXT)
    if price_text:
        out["price_text"] = price_text
    pay_type = _as_int(shop.get("pay_type"))
    if pay_type is not None:
        out["pay_type"] = pay_type
    hours = _fmt_hours(shop.get("start_time"), shop.get("end_time"))
    if hours:
        out["hours"] = hours
    thumb = shop.get("image_thumb")
    if isinstance(thumb, dict):
        url = enrich.clean_text(thumb.get("url"), limit=None)
        if url:
            out["image_thumb"] = url
    fav = _as_int(shop.get("fav_count"))
    if fav is not None and fav > 0:
        out["fav_count"] = fav
    prices, versions = {}, {}
    for a in (shop.get("arcades") or []):
        if not isinstance(a, dict):
            continue
        slug = games_by_title.get(a.get("title_id"))
        if slug in (None, "other"):
            continue
        disp = _price_display(a.get("coin"), shop.get("price"))
        # first title wins per slug: several cabs of one game can be
        # listed separately and the cheapest/first is the headline
        if disp and slug not in prices:
            prices[slug] = disp
        ver = enrich.clean_text(a.get("version"), limit=120)
        if ver and slug not in versions:
            versions[slug] = ver
    if prices:
        out["game_prices"] = {s: prices[s] for s in sorted(prices)}
    if versions:
        out["game_versions"] = {s: versions[s] for s in sorted(versions)}
    if out:
        out["enriched_at"] = date.today().isoformat()
    return out


def shop_row(shop, city_name, prov_name, titles):
    """One output row for a city-index shop (fetches the detail page)."""
    region = (prov_name if city_name in (None, prov_name)
              else "%s %s" % (prov_name, city_name))
    detail = _fetch_json(BASE + "/s/%s" % shop["id"],
                         partial=("Shop/Show", "shop"), allow_404=True)
    games, counts, other_names, note_parts = [], {}, [], []
    detail_404 = detail is None
    shop_detail = {}
    games_by_title = {}
    if not detail_404:
        shop_detail = (((detail or {}).get("props") or {}).get("shop")
                       or {})
        arcades = shop_detail.get("arcades") or []
        for a in arcades:
            slug = TITLE_GAME.get(a.get("title_id"))
            if slug is None:
                nm = titles.get(a.get("title_id"),
                                "title_id=%s" % a.get("title_id"))
                if nm not in other_names:
                    other_names.append(nm)
                slug = "other"
            else:
                try:
                    q = int(a.get("quantity"))
                except (TypeError, ValueError):
                    q = 0
                if q > 0:
                    counts[slug] = counts.get(slug, 0) + q
            games_by_title[a.get("title_id")] = slug
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
    row = {
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
    if counts:
        row["game_counts"] = {s: counts[s] for s in sorted(counts)}
    # optional enrichment fields; absent keys simply do not appear
    row.update(shop_enrichment(shop_detail, games_by_title))
    return row


def _crawl_pass(city_list, titles, rows, failed_cities, failed_shops,
                tag=""):
    """One crawl pass over city_list. Per-city / per-shop FetchErrors
    (already 3-attempted inside _fetch_json) are collected into
    failed_cities / failed_shops instead of aborting the crawl."""
    for ci, (code, city_name, prov_name) in enumerate(city_list, 1):
        try:
            shops = city_shops(code)
        except common.FetchError as e:
            print("bemanicn:%s city %s (%s) FAILED: %s"
                  % (tag, city_name, code, e), file=sys.stderr)
            failed_cities.append((code, city_name, prov_name))
            continue
        print("bemanicn:%s city %d/%d %s (%s): %d shops"
              % (tag, ci, len(city_list), city_name, code, len(shops)),
              file=sys.stderr)
        for shop in shops:
            if not shop.get("name") or shop.get("id") is None:
                continue
            try:
                rows.append(shop_row(shop, city_name, prov_name, titles))
            except common.FetchError as e:
                print("bemanicn:%s shop s/%s (%s) FAILED: %s"
                      % (tag, shop.get("id"), city_name, e),
                      file=sys.stderr)
                failed_shops.append((shop, city_name, prov_name))


def scrape(smoke=False):
    cities = fetch_cities()
    titles = fetch_titles()
    if smoke:
        cities = ([c for c in cities if c[1] == SMOKE_CITY]
                  or cities[:1])
    rows = []
    failed_cities, failed_shops = [], []
    _crawl_pass(cities, titles, rows, failed_cities, failed_shops)
    if failed_cities or failed_shops:
        # retry the failed remainder once, then proceed without the rest
        print("bemanicn: retrying %d failed city(ies) and %d failed "
              "shop(s) once" % (len(failed_cities), len(failed_shops)),
              file=sys.stderr)
        still_cities, still_shops = [], []
        _crawl_pass(failed_cities, titles, rows, still_cities,
                    still_shops, tag=" retry")
        for shop, city_name, prov_name in failed_shops:
            try:
                rows.append(shop_row(shop, city_name, prov_name, titles))
            except common.FetchError as e:
                print("bemanicn: retry shop s/%s (%s) FAILED: %s"
                      % (shop.get("id"), city_name, e), file=sys.stderr)
                still_shops.append((shop, city_name, prov_name))
        for code, city_name, _ in still_cities:
            print("bemanicn: UNRECOVERED city %s (%s); its shops are "
                  "missing from this crawl" % (city_name, code),
                  file=sys.stderr)
        for shop, city_name, _ in still_shops:
            print("bemanicn: UNRECOVERED shop s/%s %s (%s); skipped"
                  % (shop.get("id"), shop.get("name"), city_name),
                  file=sys.stderr)
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
