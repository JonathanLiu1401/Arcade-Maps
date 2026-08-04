"""Musecat (musecat.app) rhythm-arcade scraper.

Venue list: public PocketBase API at db-delta.musecat.app
  GET /api/collections/arcade/records?expand=basic
  (filter closed=false; optional country=KR/JP/...)

Game inventory relation is 403 without auth. Per-venue games, cab
counts, and series names are embedded in the SSR Next.js flight
payload on https://musecat.app/{locale}/arcade/{id}.

Output schema (merge-friendly community row):
  {name, name_en, address, lat, lng, coord_system, games, game_counts,
   count_evidence, source, source_url, country, notes, sid}

sid is the stable Musecat arcade id (never a row number).
--smoke fetches a few open KR venues only and writes nothing.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

API = ("https://db-delta.musecat.app/api/collections/arcade/records")
SITE = "https://musecat.app"
OUTFILE = "musecat.json"
SOURCE = "musecat"
PER_PAGE = 200
SMOKE_LIMIT = 3

# ISO country codes seen in the API -> merge country labels
COUNTRY_MAP = {
    "KR": "South Korea",
    "JP": "Japan",
    "TW": "Taiwan",
    "HK": "Hong Kong",
    "MO": "Macau",
    "CN": "China",
    "US": "United States",
    "USA": "United States",
    "MY": "Malaysia",
    "ID": "Indonesia",
    "PH": "Philippines",
    "SG": "Singapore",
    "VN": "Vietnam",
    "TH": "Thailand",
    "AU": "Australia",
    "NZ": "New Zealand",
    "CA": "Canada",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "FR": "France",
    "DE": "Germany",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "BR": "Brazil",
    "MX": "Mexico",
}

# series.en / series.kr / series.jp token -> canonical slug.
# Longer / more specific patterns first within each decision.
_SERIES_RULES = [
    (re.compile(r"sound\s*voltex|sdvx|サウンド\s*ボルテックス|사볼", re.I), "sdvx"),
    (re.compile(r"beatmania\s*iidx|iidx|비트매니아\s*iidx|투덱", re.I), "iidx"),
    (re.compile(r"dance\s*dance\s*revolution|\bddr\b|댄스댄스", re.I), "ddr"),
    (re.compile(r"dance\s*rush|dancerush|\bdrs\b", re.I), "drs"),
    (re.compile(r"dance\s*around", re.I), "dance_around"),
    (re.compile(r"dance\s*evolution|댄스\s*에볼루션", re.I), "dance_evo"),
    (re.compile(r"pop'?n\s*music|ポップン|팝픈", re.I), "popn"),
    (re.compile(r"gitadora|guitar\s*freaks|drum\s*mania|ギタドラ|"
                r"기타도라|기타\s*프릭스|드럼매니아|\b도라\b", re.I), "gitadora"),
    (re.compile(r"\bjubeat\b|ユビート|유비트", re.I), "jubeat"),
    (re.compile(r"chunithm|チュウニズム|츄니즘", re.I), "chunithm"),
    (re.compile(r"ongeki|オンゲキ|온게키", re.I), "ongeki"),
    (re.compile(r"maimai", re.I), "maimai_dx"),
    (re.compile(r"polaris\s*chord|ポラリス|폴라리스", re.I), "polaris_chord"),
    (re.compile(r"project\s*diva|プロジェクトディーヴァ|프로젝트\s*디바", re.I),
     "project_diva"),
    (re.compile(r"nostalgia|ノスタルジア|노스텔", re.I), "nostalgia"),
    (re.compile(r"\bmuseca\b|ミューゼカ", re.I), "museca"),
    (re.compile(r"reflec\s*beat|リフレク|리플렉", re.I), "reflec"),
    (re.compile(r"taiko|太鼓|태고", re.I), "taiko"),
    (re.compile(r"pump\s*it\s*up|\bpump\b|펌프", re.I), "pump_it_up"),
    (re.compile(r"stepmania\s*x|stepmaniax", re.I), "stepmaniax"),
    (re.compile(r"\bwacca\b|ワッカ|화카", re.I), "wacca"),
    (re.compile(r"groove\s*coaster|グルーヴコースター|그루브\s*코스터", re.I),
     "groove_coaster"),
    (re.compile(r"crossbeats|クロスビーツ", re.I), "crossbeats"),
    (re.compile(r"beatstream|ビートストリーム", re.I), "beatstream"),
]

# Non-catalog rhythm-ish titles we still note but map to "other"
_OTHER_RHYTHM = re.compile(
    r"ez2ac|ez2dj|beaton|beat\s*on|비트온|beat\s*saber|비트세이버|"
    r"guitar\s*hero|기타\s*히어로|chrono\s*circle|music\s*diver|"
    r"initial\s*d|湾岸|太鼓の達人\s*セッション",
    re.I)

_QTY_SERIES = re.compile(
    r'"quantity"\s*:\s*(\d+)\s*,\s*"series"\s*:\s*\{([^{}]*)\}',
    re.S)
_SERIES_EN = re.compile(r'"en"\s*:\s*"((?:\\.|[^"\\])*)"')
_SERIES_KR = re.compile(r'"kr"\s*:\s*"((?:\\.|[^"\\])*)"')
_SERIES_JP = re.compile(r'"jp"\s*:\s*"((?:\\.|[^"\\])*)"')
_SERIES_EN_SHORT = re.compile(r'"en_short"\s*:\s*"((?:\\.|[^"\\])*)"')


def _js_str(s):
    if not s:
        return ""
    try:
        return json.loads('"' + s + '"')
    except Exception:
        return s.replace("\\n", " ").replace('\\"', '"')


def series_to_slug(en, kr="", jp="", en_short=""):
    text = " / ".join(x for x in (en, en_short, kr, jp) if x)
    if not text.strip():
        return None
    for rx, slug in _SERIES_RULES:
        if rx.search(text):
            return slug
    if _OTHER_RHYTHM.search(text):
        return "other"
    return None


def _flight_payloads(html):
    """Decode self.__next_f.push([1, \"...\"]) string chunks."""
    out = []
    for m in re.finditer(
            r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html):
        raw = m.group(1)
        try:
            out.append(json.loads('"' + raw + '"'))
        except Exception:
            out.append(raw)
    return out


def parse_games_from_html(html):
    """Return (games_sorted, game_counts, count_evidence, cab_notes).

    Counts come from Musecat quantity fields (real totals).
    """
    counts = {}
    notes = []
    for payload in _flight_payloads(html):
        if '"quantity"' not in payload or '"series"' not in payload:
            continue
        for m in _QTY_SERIES.finditer(payload):
            try:
                qty = int(m.group(1))
            except ValueError:
                continue
            body = m.group(2)
            en_m = _SERIES_EN.search(body)
            kr_m = _SERIES_KR.search(body)
            jp_m = _SERIES_JP.search(body)
            es_m = _SERIES_EN_SHORT.search(body)
            en = _js_str(en_m.group(1) if en_m else "")
            kr = _js_str(kr_m.group(1) if kr_m else "")
            jp = _js_str(jp_m.group(1) if jp_m else "")
            en_short = _js_str(es_m.group(1) if es_m else "")
            slug = series_to_slug(en, kr, jp, en_short)
            label = en or en_short or kr or jp or "?"
            if qty > 0:
                notes.append("%s x%d" % (label, qty))
            if not slug:
                continue
            if qty <= 0:
                continue
            counts[slug] = counts.get(slug, 0) + qty
    # Drop pure-other from the published games list when real slugs exist
    real = {k: v for k, v in counts.items() if k != "other" and v > 0}
    if real:
        counts = real
        games = sorted(real.keys())
    elif counts:
        games = ["other"]
        counts = {"other": max(counts.values()) if counts else 1}
    else:
        games = []
        if notes:
            games = ["other"]
            counts = {"other": 1}
    evidence = {s: "musecat_quantity" for s in counts if s != "other"}
    return games, counts, evidence, notes


def locale_for_country(cc):
    cc = (cc or "").upper()
    if cc == "KR":
        return "kr"
    if cc == "JP":
        return "ja"
    return "en"


def fetch_arcade_page(arcade_id, country):
    loc = locale_for_country(country)
    url = "%s/%s/arcade/%s" % (SITE, loc, arcade_id)
    return common.fetch(url), url


def list_arcades(country=None, include_closed=False):
    """Paginate PocketBase arcade list with expand=basic."""
    page = 1
    items = []
    parts = []
    if not include_closed:
        parts.append("closed=false")
    if country:
        parts.append("country='%s'" % country.upper())
    filt = "&&".join(parts) if parts else None
    while True:
        q = {
            "page": str(page),
            "perPage": str(PER_PAGE),
            "expand": "basic",
        }
        if filt:
            q["filter"] = filt
        url = API + "?" + urllib.parse.urlencode(q)
        payload = json.loads(common.fetch(url))
        batch = payload.get("items") or []
        if not isinstance(batch, list):
            raise common.FetchError("musecat: unexpected list shape")
        items.extend(batch)
        total_pages = int(payload.get("totalPages") or 1)
        print("musecat: list page %d/%d (+%d, total %d)"
              % (page, total_pages, len(batch), len(items)),
              file=sys.stderr)
        if page >= total_pages or not batch:
            break
        page += 1
    return items


def row_from_item(item, games, counts, evidence, cab_notes, page_url):
    basic = (item.get("expand") or {}).get("basic") or {}
    name = common.unescape(str(basic.get("name") or item.get("name") or ""))
    if not name:
        return None
    addr = common.unescape(str(basic.get("address") or ""))
    loc = basic.get("location") or {}
    lat = loc.get("lat")
    lng = loc.get("lon") if "lon" in loc else loc.get("lng")
    try:
        lat = float(lat) if lat not in (None, "") else None
        lng = float(lng) if lng not in (None, "") else None
    except (TypeError, ValueError):
        lat = lng = None
    cc = str(item.get("country") or "").upper()
    country = COUNTRY_MAP.get(cc, cc or None)
    nick = basic.get("nickname") or []
    if isinstance(nick, list):
        nick = [common.unescape(str(n)) for n in nick if n]
    else:
        nick = []
    direction = common.unescape(str(basic.get("direction") or ""))
    note_parts = []
    if cab_notes:
        note_parts.append("Cabs: " + "; ".join(cab_notes))
    if direction:
        note_parts.append("Access: " + direction)
    if nick:
        note_parts.append("Nick: " + ", ".join(nick))
    if item.get("closed"):
        note_parts.append("closed on Musecat")
    sid = str(item.get("id") or "")
    games = list(games) if games else ["other"]
    row = {
        "name": name,
        "name_en": name,
        "address": addr,
        "lat": lat,
        "lng": lng,
        "coord_system": "wgs84",
        "games": games,
        "source": SOURCE,
        "source_url": page_url,
        "sid": sid,
        "country": country,
        "notes": " | ".join(note_parts),
    }
    if counts:
        # drop pure-other counts from game_counts (merge does not count other)
        gc = {k: v for k, v in counts.items() if k != "other" and v > 0}
        if gc:
            row["game_counts"] = gc
            row["count_evidence"] = {k: evidence.get(k, "musecat_quantity")
                                     for k in gc}
    return row


def scrape(country="KR", smoke=False, max_venues=None, include_closed=False):
    """Scrape Musecat. country=None means all countries."""
    items = list_arcades(country=country, include_closed=include_closed)
    # Prefer public open venues with a basic expand
    usable = []
    for it in items:
        if not include_closed and it.get("closed"):
            continue
        if it.get("public") is False:
            continue
        basic = (it.get("expand") or {}).get("basic")
        if not basic:
            continue
        usable.append(it)
    if smoke:
        usable = usable[:SMOKE_LIMIT]
    elif max_venues is not None:
        usable = usable[:max_venues]

    rows = []
    failed = 0
    for i, item in enumerate(usable):
        aid = str(item.get("id") or "")
        cc = str(item.get("country") or "KR")
        try:
            html, page_url = fetch_arcade_page(aid, cc)
            games, counts, evidence, cab_notes = parse_games_from_html(html)
            row = row_from_item(item, games, counts, evidence, cab_notes,
                                page_url)
            if row:
                rows.append(row)
        except common.FetchError as e:
            failed += 1
            print("musecat: venue %s FAILED: %s" % (aid, e), file=sys.stderr)
            # still emit a no-games row from list data so coords/name survive
            try:
                loc = locale_for_country(cc)
                page_url = "%s/%s/arcade/%s" % (SITE, loc, aid)
                row = row_from_item(item, ["other"], {}, {}, [], page_url)
                if row:
                    row["notes"] = ((row.get("notes") or "") +
                                    " | game page fetch failed").strip(" |")
                    rows.append(row)
            except Exception:
                pass
        if (i + 1) % 25 == 0:
            print("musecat: detail %d/%d (%d rows, %d failed)"
                  % (i + 1, len(usable), len(rows), failed),
                  file=sys.stderr)
    print("musecat: done %d rows (%d failed detail fetches)"
          % (len(rows), failed), file=sys.stderr)
    return rows


def main():
    ap = argparse.ArgumentParser(description="Musecat rhythm-arcade scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--outfile", default=OUTFILE)
    ap.add_argument("--country", default="KR",
                    help="ISO country filter (KR, JP, ...). "
                         "Use ALL for every country.")
    ap.add_argument("--smoke", action="store_true",
                    help="few open KR venues; print rows, write nothing")
    ap.add_argument("--max", type=int, default=None,
                    help="cap venue detail fetches")
    ap.add_argument("--include-closed", action="store_true")
    args = ap.parse_args()
    country = None if args.country.upper() == "ALL" else args.country.upper()
    if args.smoke and country is None:
        country = "KR"
    rows = scrape(country=country, smoke=args.smoke, max_venues=args.max,
                  include_closed=args.include_closed)
    if args.smoke:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        print("smoke: %d rows (nothing written)" % len(rows), file=sys.stderr)
        return
    if not rows:
        common.die("musecat returned 0 rows")
    path = os.path.join(args.out, args.outfile)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
