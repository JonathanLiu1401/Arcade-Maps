"""Zenius -I- vanisher.com arcade database scraper.

API: https://zenius-i-vanisher.com/api/arcades.php
     ?action=query&country={name}&skip_pictures=1&skip_visitors=1&skip_comments=1
The United States is too large for a single country query (it returns
HTTP 500) and must be fetched per rhythm series id and merged by arcade
id: USA_SERIES (which doubles as the seriesID -> slug map) plus
USA_EXTRA_SERIES (US-fetch-only ids for Pump It Up / StepManiaX /
Guitar Hero / In The Groove / Beat Saber / StepMania, whose machines
still resolve to "other" and are never counted).

Country names must be spelled exactly as ZIv spells them: an unknown
name returns {"arcades": [], "success": true}, an HTTP 200 that looks
like an empty country rather than an error. run_all.scrape_all treats
a zero-arcade country as a hard failure for this reason.

Entries whose name or info mark them as closed are excluded.
Coordinates are WGS-84; longitudes are wrapped to [-180, 180].
Machine list entries are dicts with a nested "game" object
({name, seriesID, ...}); slugs come from game.seriesID via USA_SERIES
first, then name-substring patterns (legacy flat {name: ...} machine
dicts are still handled).

Output schema per row (matches data_extra/community.json):
{name, name_en, address, lat, lng, coord_system, games, source, source_url, notes}
plus a "country" field recording which country query returned the arcade,
plus an OPTIONAL "game_counts" {slug: int}: machines in the arcade's cab
list tallied per mapped slug (one cab list entry = one machine; cabs that
only map to "other" are NOT counted; absent when nothing mapped).

ENRICHMENT (added 2026-07-27; see docs/research/enrichment-sources.md
section 1b and scrapers/enrich.py):

VERIFIED 2026-07-27 against a live Philippines query: the three skip
flags strip ONLY `pictures`, `comments` and `visitors`. Every pricing
and venue field still comes back with skip_pictures=1, measured over
343 PH arcades:

  openingTimes  343/343    displayPrice  322/343    condition 229/343
  information   173/343    price         187/343    pricing   121/343
  website        93/343    continuePrice 117/343    freePlay    5/343
  pictures/comments/visitors  0/343  (stripped by the flags)

So machine_prices / website / hours_text / info_text are parsed
UNCONDITIONALLY at zero extra request cost, on every crawl. `--enrich`
therefore exists only for `pictures`, which genuinely needs the flag
dropped. Optional row fields:

  machine_prices {slug: "PHP 40.00 for 3 songs"} from each machine's
                 displayPrice / pricing / price / freePlay
  website        venue website URL
  hours_text     openingTimes rendered "Mon 10:00-21:00; ..." (the API
                 returns a 7-element array, index 0 = Monday, VERIFIED
                 against the rendered arcade.php page for id 88)
  info_text      venue free-text `information`, HTML-stripped
  pictures       up to 3 absolutePath URLs (--enrich mode only)
  enriched_at    ISO date the row was scraped

Cost of --enrich, measured live 2026-07-27: Philippines with pictures
enabled was 1,372,303 bytes vs 1,279,351 skipped (+7.3%) for 1,010
picture URLs across 169/343 arcades; Singapore +2,755 bytes. Pictures
are cheap in bytes; the reason they stay opt-in is that the bulk crawl
already runs ~65 countries plus a 21-request US series loop.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import enrich

API = "https://zenius-i-vanisher.com/api/arcades.php"
ARCADE_URL = "https://zenius-i-vanisher.com/v5.2/arcade.php?id=%s"

# Rhythm series ids used for the per-series USA fetch AND as the
# primary machine.game.seriesID -> slug mapping (name substrings below
# are the fallback for series without an id here).
USA_SERIES = {
    1: "ddr", 2: "iidx", 3: "popn", 4: "gitadora", 5: "jubeat",
    12: "taiko", 173: "sdvx", 267: "gitadora", 284: "maimai_dx",
    506: "chunithm", 549: "museca", 643: "nostalgia", 694: "drs",
    1366: "ongeki", 1556: "dance_around",
}

# Extra series ids fetched by the per-series United States crawl ONLY:
# Pump It Up (7), In The Groove (8), Guitar Hero Arcade (18),
# StepManiaX (766), Beat Saber (1281), StepMania (1536). Without them
# the US crawl misses ~780 arcades whose only rhythm cabs are these,
# because the unsegmented country query 500s and the US set is the
# union of the per-series queries.
#
# Deliberately NOT part of USA_SERIES: that dict doubles as the
# seriesID -> canonical-slug map, so listing these there would map
# their machines to a real slug (or to "other", which merge.py counts
# because "other" is in GAME_SLUGS) and would put an "other" key into
# game_counts worldwide. These machines keep resolving to "other" via
# the no-pattern-hit fallback and are never counted.
USA_EXTRA_SERIES = [7, 8, 18, 766, 1281, 1536]

# Substring -> canonical slug fallback mapping for ZIV cab/game titles
# (used when the machine's game.seriesID is not in USA_SERIES).
#
# Regional and script variants of a title belong here even when seriesID
# already covers them, because merge.py's counts test (see
# `slugs_for_title`) has only the title text to work from: a variant this
# table misses looks like a title that maps to no game at all, and one
# unmapped variant sitting beside its own sibling ("GUITARFREAKS" plus
# "PercussionFreaks") is what makes two separate cabinets read as a tally
# of two.
GAME_PATTERNS = [
    ("dancedancerevolution", "ddr"), ("dance dance revolution", "ddr"),
    ("dancing stage", "ddr"),   # DDR's European branding
    ("beatmania iidx", "iidx"), ("pop'n music", "popn"), ("popn music", "popn"),
    ("guitarfreaks", "gitadora"), ("drummania", "gitadora"),
    ("percussionfreaks", "gitadora"),   # GuitarFreaks' export drum sibling
    ("狂熱鼓手", "gitadora"), ("狂热鼓手", "gitadora"),   # DrumMania (zh)
    ("gitadora", "gitadora"), ("jubeat", "jubeat"),
    ("ubeat", "jubeat"),        # jubeat's Korean release title
    ("太鼓の達人", "taiko"), ("taiko no tatsujin", "taiko"),
    ("wadaiko master", "taiko"),   # Taiko's western release title
    ("sound voltex", "sdvx"), ("maimai", "maimai_dx"),
    ("舞萌", "maimai_dx"),      # maimai's Chinese title
    ("chunithm", "chunithm"), ("museca", "museca"),
    ("múseca", "museca"),       # the accented spelling ZIv actually uses
    ("nostalgia", "nostalgia"), ("ノスタルジア", "nostalgia"),
    ("dancerush", "drs"),
    ("dance around", "dance_around"), ("dance around", "dance_around"),
    ("ongeki", "ongeki"), ("オンゲキ", "ongeki"),
    ("polaris chord", "polaris_chord"), ("ポラリスコード", "polaris_chord"),
    ("project diva", "project_diva"),
    ("danceevolution", "dance_evo"), ("reflec beat", "reflec"),
]

_CLOSED_RE = re.compile(r'closed|permanently closed|閉店', re.I)

# Countries whose ZIv rows are dense enough with community edits to be
# worth the picture-enabled fetch in --enrich mode. Spellings are ZIv's
# own ("USA" is the per-series United States sentinel).
ENRICH_COUNTRIES = [
    "USA", "Japan", "Philippines", "Canada", "United Kingdom",
    "Australia", "Taiwan", "South Korea", "Singapore", "Malaysia",
    "Thailand", "Indonesia", "Hong Kong",
]

MAX_PICTURES = 3          # per arcade; enrichment.json is browser-fetched
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _fmt_opening_times(times):
    """ZIv `openingTimes` -> "Mon-Thu 10:00-21:00; Fri-Sun 10:00-22:00".

    The API returns a 7-element array of [open, close, closedFlag],
    index 0 = Monday (VERIFIED against the rendered arcade.php page for
    arcade 88). Consecutive identical days are collapsed into ranges.
    Returns None when the array is missing, the wrong shape, or carries
    no usable day."""
    if not isinstance(times, (list, tuple)) or len(times) != 7:
        return None
    day_txt = []
    for d in times:
        if not isinstance(d, (list, tuple)) or len(d) < 2:
            day_txt.append(None)
            continue
        op, cl = d[0], d[1]
        closed = d[2] if len(d) > 2 else False
        # op == cl is ZIv's "nobody filled these in" default, not a real day.
        # The API hands back ["00:00", "00:00", false] for every day of an
        # unrecorded venue, and "00:00" is a truthy string, so an `op and cl`
        # test let it through: 1,730 rows (24.8% of the ZIv set) shipped
        # "Mon-Sun 00:00-00:00" as if it were published opening hours.
        # A zero-length day is not hours under any reading, so it is dropped
        # rather than guessed at; enrich.py re-checks the formatted string so
        # rows already sitting in data_raw/ are cleaned too.
        op_s, cl_s = str(op or "").strip(), str(cl or "").strip()
        if closed:
            day_txt.append("closed")
        elif op_s and cl_s and op_s != cl_s:
            day_txt.append("%s-%s" % (op_s, cl_s))
        else:
            day_txt.append(None)
    if not any(t for t in day_txt):
        return None
    runs = []       # [(first day idx, last day idx, text)]
    for i, t in enumerate(day_txt):
        if t is None:
            continue
        if runs and runs[-1][2] == t and runs[-1][1] == i - 1:
            runs[-1][1] = i
        else:
            runs.append([i, i, t])
    parts = []
    for a, b, t in runs:
        label = _DAYS[a] if a == b else "%s-%s" % (_DAYS[a], _DAYS[b])
        parts.append("%s %s" % (label, t))
    return "; ".join(parts) or None


def _machine_price_text(m):
    """Best human-readable price string for one machine, or None.

    displayPrice is the community's own formatted text and wins; pricing
    is the plain-text twin; the numeric `price` is the last resort (bare
    number, no currency - labelled as such). freePlay short-circuits."""
    if m.get("freePlay"):
        return "free play"
    for key in ("displayPrice", "pricing"):
        txt = enrich.strip_html(m.get(key), limit=enrich.MAX_PRICE_TEXT)
        # "???" and similar placeholders carry no information
        if txt and txt.strip("?").strip():
            return txt
    p = m.get("price")
    try:
        p = float(p)
    except (TypeError, ValueError):
        return None
    if p > 0:
        return ("%g per play (currency per venue)" % p)
    return None


def arcade_enrichment(a, machines_raw, enrich_pictures=False):
    """Optional enrichment fields for one ZIv arcade payload.

    `machines_raw` is the arcade's raw machine list (dicts), used to key
    prices by the same canonical slug the games list uses. Machines that
    only map to "other" are skipped - that bucket mixes unrelated cabs
    and their prices would overwrite each other.

    Returns {} when nothing enrichable is present."""
    out = {}
    website = enrich.clean_text(a.get("website"), limit=300)
    if website and website.lower() not in ("http://", "https://", "n/a"):
        out["website"] = website
    hours = _fmt_opening_times(a.get("openingTimes"))
    if hours:
        out["hours_text"] = hours
    info = enrich.strip_html(a.get("information"))
    if info:
        out["info_text"] = info
    prices = {}
    for m in machines_raw:
        if not isinstance(m, dict):
            continue
        g = m.get("game")
        if isinstance(g, dict):
            nm, sid = str(g.get("name") or ""), g.get("seriesID")
        else:
            nm, sid = str(m.get("name") or ""), m.get("seriesID")
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            sid = None
        if not nm or _CLOSED_RE.search(nm):
            continue
        txt = _machine_price_text(m)
        if not txt:
            continue
        for slug in _machine_slugs(nm, sid):
            # first priced machine wins per slug
            prices.setdefault(slug, txt)
    if prices:
        out["machine_prices"] = {s: prices[s] for s in sorted(prices)}
    if enrich_pictures:
        pics = []
        for p in (a.get("pictures") or []):
            url = p.get("absolutePath") if isinstance(p, dict) else p
            url = enrich.clean_text(url, limit=None)
            if url and url not in pics:
                pics.append(url)
            if len(pics) >= MAX_PICTURES:
                break
        if pics:
            out["pictures"] = pics
    if out:
        out["enriched_at"] = date.today().isoformat()
    return out


def _machine_slugs(nm, sid):
    """Distinct canonical slugs one machine maps to (empty set if none):
    seriesID via USA_SERIES first, then name-substring patterns."""
    slugs = set()
    if sid is not None and sid in USA_SERIES:
        slugs.add(USA_SERIES[sid])
    low = nm.lower()
    for pat, slug in GAME_PATTERNS:
        if pat in low or pat in nm:
            slugs.add(slug)
    return slugs


def slugs_for_title(name):
    """Canonical slugs a cab TITLE alone maps to, with no seriesID to help.

    Public because merge.py has to re-derive per-slug title counts from the
    committed "Cabs:" note (the raw row keeps the title list nowhere else) to
    tell a real machine tally from two different titles sharing one slug. It
    is deliberately the weaker of the two lookups: a title the name patterns
    miss returns nothing rather than guessing, and the caller treats that as
    "no evidence" instead of as a count from nowhere.
    """
    return _machine_slugs(name, None)


def _slugs_for_machines(machines):
    slugs = set()
    for nm, sid in machines:
        slugs |= _machine_slugs(nm, sid) or {"other"}
    return sorted(slugs) or ["other"]


def _counts_for_machines(machines):
    """{slug: machine count}: each machine list entry is one machine and
    increments every distinct slug it maps to ("other" is not counted)."""
    counts = {}
    for nm, sid in machines:
        for slug in _machine_slugs(nm, sid):
            counts[slug] = counts.get(slug, 0) + 1
    return counts


def _wrap_lng(lng):
    while lng > 180:
        lng -= 360
    while lng < -180:
        lng += 360
    return lng


def _parse_arcades(payload, country, enrich_pictures=False):
    """Normalize one API response into output rows keyed by arcade id.

    enrich_pictures: also keep `pictures` URLs (only meaningful when the
    request was made without skip_pictures=1). All other enrichment
    fields are parsed unconditionally - they survive the skip flags."""
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
        machines = []   # (machine name, series id or None)
        machines_raw = a.get("cabs") or a.get("machines") or []
        for c in (a.get("cabs") or a.get("machines") or []):
            if isinstance(c, dict):
                g = c.get("game")
                if isinstance(g, dict):   # current API: nested game obj
                    nm, sid = str(g.get("name") or ""), g.get("seriesID")
                else:                     # legacy flat shape
                    nm, sid = str(c.get("name") or ""), c.get("seriesID")
                try:
                    sid = int(sid)
                except (TypeError, ValueError):
                    sid = None
                machines.append((nm, sid))
            else:
                machines.append((str(c), None))
        machines = [(nm, sid) for nm, sid in machines
                    if nm and not _CLOSED_RE.search(nm)]
        cabs = [nm for nm, _ in machines]
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
            "games": _slugs_for_machines(machines),
            "source": "ziv",
            "source_url": ARCADE_URL % aid,
            "notes": notes,
            "country": country,
        }
        counts = _counts_for_machines(machines)
        if counts:
            out[aid]["game_counts"] = {s: counts[s] for s in sorted(counts)}
        # optional enrichment; absent keys simply do not appear
        out[aid].update(arcade_enrichment(a, machines_raw, enrich_pictures))
    return out


def _query_url(country, pictures=False, series_id=None):
    """Country query URL. skip_pictures is dropped only when pictures are
    wanted; visitors/comments are always skipped (never used, and they
    are the bulk of the payload)."""
    url = (API + "?action=query&country=" + urllib.parse.quote(country)
           + "&skip_visitors=1&skip_comments=1")
    if not pictures:
        url += "&skip_pictures=1"
    if series_id is not None:
        url += "&series_id=%d" % series_id
    return url


def fetch_country(country, pictures=False):
    url = _query_url(country, pictures)
    return _parse_arcades(json.loads(common.fetch(url)), country, pictures)


def fetch_usa(pictures=False):
    """Per-series United States fetch.

    ZIV spells the country "United States"; the legacy "USA" spelling
    silently returns {"arcades": [], "success": true} (a whole-country
    dropout that no HTTP error reveals), and the unsegmented
    country=United States query 500s because the payload is too large -
    hence the per-series loop. The rows keep country "USA"; merge.py
    remaps that to "United States"."""
    merged = {}
    for sid in sorted(set(USA_SERIES) | set(USA_EXTRA_SERIES)):
        url = _query_url("United States", pictures, series_id=sid)
        part = _parse_arcades(json.loads(common.fetch(url)), "USA", pictures)
        for aid, row in part.items():
            if aid in merged:
                merged[aid]["games"] = sorted(
                    set(merged[aid]["games"]) | set(row["games"]))
                gc = merged[aid].get("game_counts") or {}
                for slug, n in (row.get("game_counts") or {}).items():
                    if n > gc.get(slug, 0):
                        gc[slug] = n
                if gc:
                    merged[aid]["game_counts"] = {s: gc[s]
                                                  for s in sorted(gc)}
                # each series query returns only that series' machines,
                # so per-slug prices and pictures accumulate across the
                # per-series loop rather than one query seeing them all
                mp = merged[aid].get("machine_prices") or {}
                for slug, txt in (row.get("machine_prices") or {}).items():
                    mp.setdefault(slug, txt)
                if mp:
                    merged[aid]["machine_prices"] = {s: mp[s]
                                                     for s in sorted(mp)}
                pics = merged[aid].get("pictures") or []
                for u in (row.get("pictures") or []):
                    if u not in pics and len(pics) < MAX_PICTURES:
                        pics.append(u)
                if pics:
                    merged[aid]["pictures"] = pics
                for k in ("website", "hours_text", "info_text",
                          "enriched_at"):
                    if k not in merged[aid] and k in row:
                        merged[aid][k] = row[k]
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
    ap.add_argument("--enrich", action="store_true",
                    help="also fetch pictures for priority countries "
                         "(ENRICH_COUNTRIES). Pricing/website/hours are "
                         "parsed on every run regardless - they survive "
                         "skip_pictures=1 at no extra request cost.")
    args = ap.parse_args()
    merged = {}
    for country in args.country:
        pictures = args.enrich and country in ENRICH_COUNTRIES
        if country.upper() == "USA":
            got = fetch_usa(pictures)
        else:
            got = fetch_country(country, pictures)
        n_pic = sum(1 for r in got.values() if r.get("pictures"))
        n_price = sum(1 for r in got.values() if r.get("machine_prices"))
        print("ziv %s: %d arcades (%d priced%s)"
              % (country, len(got), n_price,
                 ", %d with pictures" % n_pic if pictures else ""),
              file=sys.stderr)
        merged.update(got)
    if not merged:
        common.die("ziv returned 0 arcades for %s" % args.country)
    rows = sorted(merged.values(), key=lambda r: (r["country"], r["name"]))
    path = os.path.join(args.out, args.outfile)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
