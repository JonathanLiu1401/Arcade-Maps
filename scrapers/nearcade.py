"""nearcade.phizone.cn (Naptie) public shop scraper.

Public JSON (no login):

  (i)  GET /api/shops?page=N[&regionId=CN]
       -> {shops, totalCount, currentPage, hasNextPage, hasPrevPage}
       Page size is 48. regionId=CN yields ~3941 Mainland China shops.
       Each shop already carries full per-cab lineups (titleId, name,
       quantity, cost, version) plus GeoJSON Point coordinates.
  (ii) GET /api/shops/{id} -> {shop}  (same shape; list is enough for crawl)
  (iii) GET /api/regions   -> country list (hasChildren tree)

Early CN data was seeded from BemaniCN and overseas from ZIv; today
community edits often add richer multi-title lineups. Treat as an
enrichment source (dedupe by source_url / shop id later, not here).

Output schema per row (community/bemanicn shape):
{name, name_en, address, lat, lng, coord_system, games, source,
 source_url, notes}
plus optional game_counts, hours, game_prices, game_versions,
enriched_at, is_open when present.

Coordinates for CN shops are GCJ-02 (site uses Tencent maps). Non-CN
rows (if crawled without regionId) would be WGS-84; this scraper
defaults to regionId=CN and labels coord_system "gcj02".

stdlib only. Polite: common.fetch retries + sleep >= 0.4s sequential.
"""

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

BASE = "https://nearcade.phizone.cn"
API_SHOPS = BASE + "/api/shops"
OUTFILE = "nearcade.json"
SOURCE = "nearcade"
# Page size observed live (2026-08-04): 48. Not a query param.
PAGE_SIZE_HINT = 48
SLEEP = 0.5
RETRIES = 3

# titleId -> GAME_SLUGS entry. Anything missing becomes "other" with the
# site's title name recorded in notes (mirrors bemanicn.TITLE_GAME).
# titleId 2 is maimai CLASSIC / FiNALE: deliberately "other" so it does
# not get a separate venue chip (same policy as merge.GAME_SLUGS).
TITLE_GAME = {
    1: "maimai_dx",
    3: "chunithm",
    4: "sdvx",
    5: "iidx",
    6: "jubeat",
    7: "nostalgia",
    8: "gitadora",
    9: "gitadora",
    10: "drs",
    11: "ddr",
    12: "popn",
    13: "dance_evo",
    14: "reflec",
    15: "taiko",
    16: "groove_coaster",
    17: "wacca",
    19: "pump_it_up",
    24: "project_diva",
    27: "ongeki",
    29: "dance_around",
    31: "taiko",
    34: "jubeat",
}


def _clean(text):
    """Whitespace-collapse + common.unescape (ASCII dash policy)."""
    if text is None:
        return None
    return common.unescape(str(text))


def _as_int(v):
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


def _fetch_json(url):
    """GET url as JSON via common.fetch (retries + politeness sleep)."""
    text = common.fetch(url, extra_headers={"Accept": "application/json"},
                        retries=RETRIES, sleep=SLEEP, timeout=45)
    try:
        return json.loads(text)
    except ValueError as e:
        raise common.FetchError("bad JSON from %s: %s" % (url, e))


def _region_labels(shop):
    """(country_id, province_zh_or_en, city_zh_or_en) from address.region."""
    regions = ((shop.get("address") or {}).get("region") or [])
    country = province = city = None
    if regions:
        country = regions[0].get("id")
    if len(regions) > 1:
        nm = regions[1].get("name") or {}
        province = nm.get("zh") or nm.get("en")
    if len(regions) > 2:
        nm = regions[2].get("name") or {}
        city = nm.get("zh") or nm.get("en")
    return country, _clean(province), _clean(city)


def _fmt_hours(opening_hours):
    """Render openingHours [[[h,m],[h,m]], ...] to 'HH:MM-HH:MM' (day0).

    The API stores one [open, close] pair per weekday index. Day-0 is
    used as the headline when present; empty/zero pairs are skipped.
    Overnight (close hour < open hour, or close == 0:0 with open > 0)
    is annotated '(+1d)' when close is before open and not both zero.
    """
    if not isinstance(opening_hours, list) or not opening_hours:
        return None
    # Prefer first non-zero pair; fall back to first entry.
    pair = None
    for day in opening_hours:
        if not isinstance(day, list) or len(day) < 2:
            continue
        a, b = day[0], day[1]
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        ah = _as_int(a.get("hour")) or 0
        am = _as_int(a.get("minute")) or 0
        bh = _as_int(b.get("hour")) or 0
        bm = _as_int(b.get("minute")) or 0
        if ah == 0 and am == 0 and bh == 0 and bm == 0:
            continue
        pair = (ah, am, bh, bm)
        break
    if pair is None:
        return None
    ah, am, bh, bm = pair
    label = "%02d:%02d-%02d:%02d" % (ah, am, bh, bm)
    # Overnight: close time earlier than open (e.g. 10:00-02:00)
    open_m = ah * 60 + am
    close_m = bh * 60 + bm
    if close_m and close_m < open_m:
        label += " (+1d)"
    return label


def _coords(shop):
    """(lat, lng) from GeoJSON Point [lng, lat], else (None, None)."""
    loc = shop.get("location") or {}
    coords = loc.get("coordinates") if isinstance(loc, dict) else None
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None, None
    lng = _as_float(coords[0])
    lat = _as_float(coords[1])
    if lat is None or lng is None:
        return None, None
    return lat, lng


def _map_games(shop_games):
    """Return (games_list, counts_dict, other_names, prices, versions).

    games_list preserves first-seen order of mapped slugs (+ other once).
    counts sum positive quantities per mapped slug (not for other).
    prices/versions: first non-empty cost/version string per mapped slug.
    """
    games, counts, other_names = [], {}, []
    prices, versions = {}, {}
    for g in shop_games or []:
        if not isinstance(g, dict):
            continue
        tid = g.get("titleId")
        if tid is None:
            tid = g.get("title_id")
        slug = TITLE_GAME.get(tid)
        raw_name = _clean(g.get("name")) or ("titleId=%s" % tid)
        if slug is None:
            if raw_name not in other_names:
                other_names.append(raw_name)
            slug = "other"
        else:
            q = _as_int(g.get("quantity")) or 0
            if q > 0:
                counts[slug] = counts.get(slug, 0) + q
            cost = _clean(g.get("cost"))
            if cost and slug not in prices:
                prices[slug] = cost
            ver = _clean(g.get("version"))
            if ver and slug not in versions:
                versions[slug] = ver
        if slug not in games:
            games.append(slug)
    return games, counts, other_names, prices, versions


def shop_row(shop):
    """One output row from a list-or-detail shop payload."""
    sid = shop.get("id")
    if sid is None:
        return None
    name = _clean(shop.get("name"))
    if not name:
        return None

    addr_obj = shop.get("address") or {}
    detailed = _clean(addr_obj.get("detailed"))
    country, province, city = _region_labels(shop)
    general = addr_obj.get("general") or []
    # Prefer Chinese detailed address; fall back to general join.
    address = detailed
    if not address and general:
        address = _clean(", ".join(str(x) for x in general if x))

    games, counts, other_names, prices, versions = _map_games(
        shop.get("games")
    )
    if not games:
        games = ["other"]

    note_parts = []
    note_parts.append("sid=%s" % sid)
    if country:
        note_parts.append("country=%s" % country)
    region_bits = [b for b in (province, city) if b]
    if region_bits:
        note_parts.append("region: " + " ".join(region_bits))
    if other_names:
        note_parts.append("other games: " + ", ".join(other_names))
    is_open = shop.get("isOpen")
    if is_open is False:
        # Closed shops stay out of the map entirely. Keeping them as open
        # pins is worse than omitting them; users travel to ghosts.
        return None

    lat, lng = _coords(shop)
    # CN: GCJ-02 (Tencent). Without regionId filter non-CN would be WGS-84;
    # this scraper is CN-scoped so always label gcj02 when coords exist.
    if lat is not None and lng is not None:
        coord_system = "gcj02"
    else:
        coord_system = "unknown"

    # Merge requires a country string for geo_validate and grouping.
    # regionId defaults to CN; map known region ids to our country names.
    country_name = None
    if country in (None, "CN", "cn", "China"):
        country_name = "China"
    elif country in ("HK", "hk", "Hong Kong"):
        country_name = "Hong Kong"
    elif country in ("TW", "tw", "Taiwan"):
        country_name = "Taiwan"
    elif country in ("MO", "mo", "Macau", "Macao"):
        country_name = "Macau"
    elif country:
        country_name = str(country)

    row = {
        "name": name,
        "name_en": None,
        "address": address,
        "country": country_name or "China",
        "lat": lat,
        "lng": lng,
        "coord_system": coord_system,
        "games": games,
        "source": SOURCE,
        "source_url": "%s/shops/%s" % (BASE, sid),
        "notes": "; ".join(note_parts),
    }
    if counts:
        row["game_counts"] = {s: counts[s] for s in sorted(counts)}
    hours = _fmt_hours(shop.get("openingHours"))
    if hours:
        row["hours"] = hours
    if prices:
        row["game_prices"] = {s: prices[s] for s in sorted(prices)}
    if versions:
        row["game_versions"] = {s: versions[s] for s in sorted(versions)}
    if is_open is not None:
        row["is_open"] = bool(is_open)
    row["enriched_at"] = date.today().isoformat()
    return row


def fetch_page(page, region_id="CN"):
    """One paginated shops response dict."""
    url = "%s?page=%d" % (API_SHOPS, page)
    if region_id:
        url += "&regionId=%s" % region_id
    data = _fetch_json(url)
    if not isinstance(data, dict):
        raise common.FetchError("unexpected shops JSON shape: %r"
                                % type(data).__name__)
    return data


def scrape(smoke=False, region_id="CN", max_pages=None):
    """Crawl all pages for region_id (default CN). smoke => 1 page only."""
    rows = []
    page = 1
    total = None
    while True:
        if smoke and page > 1:
            break
        if max_pages is not None and page > max_pages:
            break
        data = fetch_page(page, region_id=region_id)
        shops = data.get("shops") or []
        if total is None:
            total = data.get("totalCount")
            print("nearcade: totalCount=%s regionId=%s (page size ~%d)"
                  % (total, region_id or "(all)", len(shops)),
                  file=sys.stderr)
        print("nearcade: page %d: %d shops (rows so far %d)"
              % (page, len(shops), len(rows)), file=sys.stderr)
        for shop in shops:
            row = shop_row(shop)
            if row:
                rows.append(row)
        has_next = data.get("hasNextPage")
        if smoke:
            break
        if has_next is False or not shops:
            break
        # Safety: if total known, stop past expected last page
        if total is not None and PAGE_SIZE_HINT > 0:
            last = (int(total) + PAGE_SIZE_HINT - 1) // PAGE_SIZE_HINT
            if page >= last and not has_next:
                break
        page += 1
        # hard guard against infinite loop if API lies about hasNextPage
        if page > 500:
            print("nearcade: abort at page 500 (guard)", file=sys.stderr)
            break
    return rows


def main():
    ap = argparse.ArgumentParser(
        description="nearcade.phizone.cn shop scraper (CN by default)"
    )
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--smoke", action="store_true",
                    help="one page only; print rows, write nothing")
    ap.add_argument("--region", default="CN",
                    help="regionId filter (default CN; empty string = all)")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="stop after N pages (debug)")
    args = ap.parse_args()
    region = args.region if args.region != "" else None
    rows = scrape(smoke=args.smoke, region_id=region,
                  max_pages=args.max_pages)
    if args.smoke:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        print("smoke: %d rows (nothing written)" % len(rows),
              file=sys.stderr)
        return
    if not rows:
        common.die("nearcade returned 0 rows")
    path = os.path.join(args.out, OUTFILE)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
