"""Street-level geocoding cache for mainland-China addresses (keyless).

``china_place`` can only put a coordinate-less Chinese venue on an
ADMINISTRATIVE centroid: ~5.9k pins land on a few hundred downtown points,
marked ``approx: true``, and any two arcades in one city are equally
"somewhere in that city". The addresses themselves are authoritative - the
only thing missing is a coordinate for them. This module gets that coordinate
once from a Chinese geocoder and commits the answer to
``data/china_geocode.json``, so merge can place the venue at its real address
instead of the centroid.

The cache is the whole point. Geocoding thousands of addresses costs time and
somebody's quota, so the answer is a checked-in file: a normal build - every
CI run, every contributor - reads it and pays nothing. Only an explicit
refresh talks to a provider, and it only asks about addresses the file does
not already answer.

**The default provider needs no API key.** ``baidu`` is Baidu Maps' own
JS-API search backend, the one map.baidu.com's front end calls; it answers
``?qt=s`` over plain HTTPS with a browser User-Agent and a map.baidu.com
Referer, and nothing else. That matters because the alternative on offer was
"register a mainland company, get a key, and hope CI has it" - which in
practice means this file stays empty forever and 5.7k pins stay stacked on
district centroids. AMAP_KEY / GOOGLE_MAPS_API_KEY still win when present;
Baidu is simply the one that is always available.

Being keyless does NOT make it free to run on every build. The refresh is a
couple of hours of polite serial requests against an undocumented endpoint,
so it stays exactly where it was: behind ``run_all.py --only geocode``, asked
for by name. Nothing on merge's path (``load_cache`` / ``lookup`` /
``apply_cache``) ever opens a socket - they are file reads, and that is what
keeps the weekly Action passing with no key, no traffic and no churn.

Misses are cached too. An address no geocoder can resolve (a bare mall-floor
label, a closed venue) is stored as ``{"miss": true}`` rather than left
absent, so the next refresh does not re-pay for the same dead end every week.
``lookup`` never hands a miss back as a coordinate.

Coordinate systems, which is why this file is not thirty lines:

  * AMap returns GCJ-02, as Chinese regulation requires of every consumer map
    service operating in China.
  * Baidu returns BD-09, which is GCJ-02 with a second, Baidu-only obfuscation
    on top - and it hands it over as BD-09 **Mercator metres times 100**
    (``x: 1267877300``), not degrees. Two conversions, in order, or the pin is
    somewhere in the Gulf of Guinea (forgetting the projection) or 300 m off
    (forgetting the BD-09 step, which reads as ordinary sloppiness).
  * Google returns GCJ-02 **as well** for mainland-China locations. That is
    the trap: the very same endpoint is WGS-84 everywhere else on earth, so
    anyone who "knows" Google speaks WGS-84 ships every Chinese pin 100-700 m
    off, in a direction that drifts with position and so reads as ordinary
    sloppiness instead of a systematic datum bug.

Every provider is therefore run through the vendored ``eviltransform``
(``gcj2wgs`` or ``bd2wgs``) before anything reaches the cache, and
``china_geocode.json`` is WGS-84 only - like the China centroid table, and
like ``data/arcades.json``, which is WGS-84 only, always.

Mainland bounding box, applied to every result. The gate is not about
jurisdiction, it is about garbage: a partial address such as ``中山路`` or
``万达广场3F`` resolves *somewhere*, and every provider would rather hand back
a confident-looking point in Kazakhstan or Hokkaido than admit it does not
know. A candidate landing outside the box is discarded and the next, coarser
candidate is tried; when none of them lands inside, the address is cached as
a miss rather than becoming a pin.

What the box does NOT do is filter by jurisdiction - Taiwan, Hong Kong and
Macau all sit comfortably inside it. Those rows are out of scope for a
different reason, the one ``china_place`` gives for refusing them outright:
ALL.Net, e-amusement and ZIv already cover all three with real street-level
pins, so nothing is gained and the datum is not even safe there (the GCJ-02
offset does not apply uniformly outside the mainland, so a correct Hong Kong
answer could be shifted a few hundred metres by ``gcj2wgs`` and land inside
the box looking perfectly fine). Keeping them out is the CALLER's job, exactly
as it is in ``china_place``; the box will not catch the mistake.

The box cannot catch a wrong-but-plausible answer, and on a POI search engine
- which is what the keyless Baidu endpoint is - wrong-but-plausible is the
normal failure. Ask about ``万达广场`` and you get one of the four hundred of
them; ask about a road that does not exist and you get a same-named road in
Henan. So every hit is put through ``verify_area``, which requires the city
the address named to be the city the answer came back in. Baidu states that
itself, in ``area_name`` (``深圳市宝安区``), and a mismatch is a rejection, not
a pin. A distance backstop, sized from each area's own measured extent,
catches the residue where two real places share a name. Rejections are
counted, logged, and stored as misses so the next run does not re-ask.

That gate is also why the province/city prefix on the query is not optional:
BemaniCN's ``全运路万达3F`` names no city, so ``qualified_address`` prepends
the ones the region note knows. Without a stated city there is nothing to
verify against and the row is skipped rather than guessed at.

Progressive queries. A printed Chinese address is not one question - it is a
province, a city, a district, a road, a number, a mall, a floor and a unit,
stacked. Handing the whole string to a POI search resolves badly (measured:
about 11% on the open geocoders), because no index has a row for "3rd floor,
next to the lift". ``cn_address`` strips that tail and produces
progressively coarser candidates - full address, then city+district+mall,
then city+mall, then road+number - and ``geocode_one`` walks them until one
answers and verifies. The venue NAME is a candidate too: bemanicn names its
shops after the mall they sit in (``环游嘉年华（北京朝阳大悦城店）``) even when
the address does not.

Refresh (nothing here runs during a normal build):

    python scrapers/run_all.py --only geocode
    python scrapers/geocode_cn.py --from-arcades data/arcades.json
    python scrapers/geocode_cn.py --from-arcades data/arcades.json --limit 50
    python scrapers/geocode_cn.py --from-arcades data/arcades.json --dry-run
    AMAP_KEY=... python scrapers/geocode_cn.py --addresses-from addrs.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import unicodedata
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import china_place    # shared skip rules + region parsing
import cn_address     # address -> ordered query candidates
import common
import eviltransform

OUTFILE = "china_geocode.json"

#: Absolute default, derived from this file rather than from the cwd, because
#: the read side (merge / china_place) is imported from several working
#: directories and a relative "data/..." would silently become an empty cache
#: in all but one of them - which looks exactly like "no addresses geocoded
#: yet" and would quietly send every China pin back to its city centroid.
_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", OUTFILE)

#: Provider order for auto-selection. The keyed providers lead ONLY because a
#: contributor who went to the trouble of getting a key presumably wants it
#: used; ``baidu`` needs no key, so it is what actually runs, here and in CI's
#: absence of any key at all. It is last in the list and first in practice.
PROVIDERS = ("amap", "google", "baidu")

ENV_KEYS = {"amap": "AMAP_KEY", "google": "GOOGLE_MAPS_API_KEY"}

#: Providers that need no credential. resolve_provider falls back to these
#: when no key is in the environment, which is the normal case.
KEYLESS = ("baidu",)

#: Floor on the gap between two requests. The keyed providers rate-limit per
#: key and answer a burst with quota errors rather than results; the keyless
#: one is somebody's undocumented front-end backend and the only thing keeping
#: it available is that we ask slowly. Requests are strictly serial for the
#: same reason - see run().
MIN_SLEEP = 0.2

#: Default gap for the keyless provider, well above the floor. A full refresh
#: is ~5.7k addresses; at this rate it is a couple of hours, once, and it is
#: cached forever afterwards. There is no deadline that justifies hammering an
#: endpoint nobody promised us.
BAIDU_SLEEP = 0.35

#: Mainland-China sanity box (lat_min, lat_max, lng_min, lng_max). Deliberately
#: tighter than eviltransform.out_of_china, which is a datum-coverage test and
#: not a plausibility test.
CN_BBOX = (17.5, 54.0, 73.0, 135.5)

#: Slack added to an area's MEASURED extent before a hit is called too far
#: away. The extent itself comes from china_areas.json (see ``area_radius_km``)
#: rather than from a constant, because a Chinese "city" is an administrative
#: region and their sizes are not comparable: 重庆市 spans 470 km while a
#: coastal prefecture spans 40. A fixed radius either waves through a pin in
#: the next province or rejects a real arcade in an outlying county, and this
#: dataset contains both.
#:
#: This is not a precision check - ``verify_area`` does that, by name. It is
#: the backstop for the case the name check structurally cannot see: the
#: answer names the right city and the coordinate is somewhere else entirely.
RADIUS_SLACK_KM = 60.0

#: Floor and ceiling on that measured radius. The floor keeps a small district
#: from becoming a hair-trigger; the ceiling stops Xinjiang, whose centroid is
#: 1000 km from its own corners, from allowing anything at all.
MIN_RADIUS_KM = 120.0
MAX_RADIUS_KM = 1100.0

#: AMap `level` -> our precision. Anything else recognisable but unlisted
#: (省/市/区县/开发区/村庄...) is area: it named a place, just not a street.
AMAP_LEVEL = {
    "门牌号": "rooftop",
    "兴趣点": "rooftop",
    "道路": "street",
    "道路交叉路口": "street",
}

#: Google `location_type` -> our precision. RANGE_INTERPOLATED is street by
#: definition; GEOMETRIC_CENTER is the centre of a road or polyline, which is
#: the same claim.
GOOGLE_LOCATION_TYPE = {
    "ROOFTOP": "rooftop",
    "RANGE_INTERPOLATED": "street",
    "GEOMETRIC_CENTER": "street",
    "APPROXIMATE": "area",
}

#: Baidu ``di_tag`` prefixes we refuse to take the coordinate of, even when
#: they are the top result. Two different failures, both observed:
#:
#:   * 出入口 / 交通设施 - searching a mall returns its car park entrance, its
#:     west door and its lift lobby as separate POIs, all real, all 50-200 m
#:     from where a visitor would stand, and all named after the mall so a name
#:     check waves them straight through.
#:   * 行政地标 / 政府机构 - the answer to a query whose administrative head
#:     matched better than its building did. A real case:
#:     ``云南省临沧市临翔区凤翔街道办事处...强力广场`` returns the 街道办事处
#:     itself, 3 km from 强力广场, because the office's own name IS the first
#:     half of the address. That is a district centroid wearing a POI's badge -
#:     exactly the answer this module exists to improve on - so it is skipped
#:     and the next, mall-only candidate gets its turn (which resolves 强力广场
#:     correctly).
_BAIDU_REJECT_TAGS = ("出入口", "交通设施", "行政地标", "政府机构")

#: Baidu ``di_tag`` values that mean "this is a road, not a building". The
#: coordinate is real but it is the road's label point, so it is street
#: precision, and street precision is what the map is told.
_BAIDU_ROAD_TAGS = ("道路",)

# --- BD-09 Mercator -> BD-09 degrees -----------------------------------------
# Baidu hands back projected metres (times 100), not degrees. The inverse is a
# 6th-order polynomial fitted per latitude band - Baidu's own, as published in
# every JS map SDK and in the gcoord library; there is no closed form to derive
# here, and the numbers are transcribed, not invented. Checked against OSM in
# test_geocode_cn.py: four landmarks land 9-49 m from their OSM node.
_MC_BAND = (12890594.86, 8362377.87, 5591021.0, 3481989.83, 1678043.12, 0.0)
_MC2LL = (
    (1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331,
     200.9824383106796, -187.2403703815547, 91.6087516669843,
     -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2),
    (-7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289,
     96.32687599759846, -1.85204757529826, -59.36935905485877,
     47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86),
    (-3.030883460898826e-8, 0.00000898305509983578, 0.30071316287616,
     59.74293618442277, 7.357984074871, -25.38371002664745,
     13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37),
    (-1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591,
     40.31678527705744, 0.65659298677277, -4.44255534477492,
     0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06),
    (3.09191371068437e-9, 0.000008983055096812155, 0.00006995724062,
     23.10934304144901, -0.00023663490511, -0.6321817810242,
     -0.00663494467273, 0.03430082397953, -0.00466043876332, 2555164.4),
    (2.890871144776878e-9, 0.000008983055095805407, -3.068298e-8,
     7.47137025468032, -0.00000353937994, -0.02145144861037,
     -0.00001234426596, 0.00010322952773, -0.00000323890364, 826088.5),
)


def bdmc2bd(x, y):
    """BD-09 Mercator metres -> (lat, lng) in BD-09 degrees.

    Note the argument order: ``x`` is EASTING (longitude) and ``y`` NORTHING
    (latitude), matching Baidu's own field names, while the return is
    ``(lat, lng)``, matching every other coordinate in this repo. The swap is
    the single most likely bug in this file and it is silent - both halves stay
    plausible floats and the pin just lands in the wrong hemisphere.
    """
    ax, ay = abs(float(x)), abs(float(y))
    coef = _MC2LL[-1]
    for i, band in enumerate(_MC_BAND):
        if ay >= band:
            coef = _MC2LL[i]
            break
    lng = coef[0] + coef[1] * ax
    t = ay / coef[9]
    lat = (coef[2] + coef[3] * t + coef[4] * t ** 2 + coef[5] * t ** 3
           + coef[6] * t ** 4 + coef[7] * t ** 5 + coef[8] * t ** 6)
    return (lat if y >= 0 else -lat), (lng if x >= 0 else -lng)


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km. Used only by the sanity backstop."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))

# Bound at module level rather than called as common.fetch(...) so
# scrapers/test_geocode_cn.py can swap in canned provider payloads and
# exercise every path with no network and no API key. Production still goes
# through common.fetch, which is where the shared UA, the 3x retry and the
# exponential backoff live.
fetch = common.fetch


class GeocodeError(common.FetchError):
    """Provider said no (bad key, quota, malformed body).

    Distinct from a miss: a miss is a real answer ("this address does not
    resolve") and is worth caching, while this means we learned nothing and
    must NOT poison the cache with a miss we would then never retry.
    """


# ------------------------------------------------------------ normalization -

#: En dash (U+2013) and em dash (U+2014), as they arrive inside upstream
#: Chinese addresses: bemanicn and wahlap both print in-mall unit codes with
#: one (``S7<emdash>236``, ``儿童城1<emdash>3层``). Folded to an ASCII hyphen
#: for the same two reasons common.unescape folds them on every other feed
#: here: this file is committed and the repo's punctuation policy is ASCII
#: only, and a source that prints the same unit as ``1-3`` one week and with a
#: dash the next would otherwise be two cache entries that both miss.
#:
#: Spelled as escapes, not as the literal characters, so the rule holds for
#: this source file too.
_DASHES = {0x2013: "-", 0x2014: "-"}


def norm_addr(addr):
    """Cache key for an address: NFKC, dashes folded, whitespace collapsed.

    NFKC is what makes the key stable across sources. The same venue arrives
    as ``红旗大街 西美花街`` from one feed and with a U+3000 ideographic space
    or fullwidth digits from another; without folding them together the cache
    stores - and pays for - the same address twice and merge still misses.
    """
    if addr is None:
        return ""
    text = unicodedata.normalize("NFKC", str(addr)).translate(_DASHES)
    return " ".join(text.split())


def in_mainland(lat, lng):
    """True when a WGS-84 point sits inside the mainland sanity box."""
    if lat is None or lng is None:
        return False
    lat_min, lat_max, lng_min, lng_max = CN_BBOX
    return lat_min <= lat <= lat_max and lng_min <= lng <= lng_max


# -------------------------------------------------------------- cache I/O ---

def load_cache(path=None):
    """Load the committed cache. ``{}`` when absent, unreadable or corrupt.

    Never raises. This is the one function merge calls, on the critical path
    of every build, including builds by people who have never heard of a
    geocoding key - a truncated or hand-edited file must cost us the
    street-level pins, not the run.
    """
    path = path or _DATA_PATH
    if not os.path.isfile(path):
        return {}
    try:
        data = common.load_json(path)
    except (OSError, ValueError) as e:
        print("geocode_cn: WARNING cannot read %s (%s: %s); continuing with "
              "an empty cache" % (path, type(e).__name__, e), file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print("geocode_cn: WARNING %s is %s, expected an object; continuing "
              "with an empty cache" % (path, type(data).__name__),
              file=sys.stderr)
        return {}
    return data


def lookup(cache, addr):
    """Cached record for ``addr``, or None on a miss / absence / bad row.

    The bbox is re-checked on read, not just on write. The cache is a
    committed file that people will hand-edit and merge conflicts will touch,
    and a single bad row here becomes a pin in the ocean with no "approx"
    flag on it - far worse than the centroid it replaced.
    """
    if not cache:
        return None
    rec = cache.get(norm_addr(addr))
    if not isinstance(rec, dict) or rec.get("miss"):
        return None
    lat, lng = rec.get("lat"), rec.get("lng")
    if isinstance(lat, bool) or isinstance(lng, bool):
        return None
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return None
    if not in_mainland(lat, lng):
        return None
    return rec


def _today():
    return datetime.now(timezone.utc).date().isoformat()


#: The exact key order every hit record is written in. Fixed so a re-run that
#: changes nothing produces a byte-identical file and the weekly commit stays
#: empty; asserted in test_geocode_cn.py so a new field cannot be bolted on in
#: the middle and churn the whole file.
HIT_FIELDS = ("lat", "lng", "provider", "precision", "formatted", "query",
              "fetched_at")


def _hit_record(lat, lng, provider, precision, formatted, day, query=""):
    # 6 dp is ~0.1 m, far past what any geocoder promises.
    #
    # ``query`` is which of the candidate strings actually produced this
    # answer, and it is in the committed file on purpose: when a pin turns out
    # to be wrong, the single most useful thing to know is whether we asked
    # about the address, the mall, or the road - and that is not recoverable
    # from the coordinate afterwards.
    return {
        "lat": round(float(lat), 6),
        "lng": round(float(lng), 6),
        "provider": provider,
        "precision": precision,
        "formatted": formatted or "",
        "query": query or "",
        "fetched_at": day,
    }


def _miss_record(provider, day):
    return {"miss": True, "provider": provider, "fetched_at": day}


# -------------------------------------------------------------- providers ---

def _amap_url(addr, key):
    return ("https://restapi.amap.com/v3/geocode/geo?address=%s&key=%s"
            % (urllib.parse.quote(addr, safe=""),
               urllib.parse.quote(key, safe="")))


def _google_url(addr, key):
    return ("https://maps.googleapis.com/maps/api/geocode/json?address=%s"
            "&region=cn&language=zh-CN&key=%s"
            % (urllib.parse.quote(addr, safe=""),
               urllib.parse.quote(key, safe="")))


def _first_str(value):
    """AMap empties come back as ``[]``, not ``""`` or null."""
    if isinstance(value, list):
        value = value[0] if value else ""
    if value is None:
        return ""
    return str(value).strip()


def _parse_amap(text):
    """(lat, lng, precision, formatted) in GCJ-02, or None for no results."""
    data = json.loads(text)
    if str(data.get("status", "")) != "1":
        raise GeocodeError(
            "amap status=%s infocode=%s info=%s"
            % (data.get("status"), data.get("infocode"), data.get("info")))
    geocodes = data.get("geocodes") or []
    if not geocodes or not isinstance(geocodes[0], dict):
        return None
    g = geocodes[0]
    # AMap packs the pair into one "lng,lat" string with LONGITUDE FIRST, the
    # opposite of every other coordinate in this repo. Swapping them puts a
    # Beijing arcade in the Indian Ocean, and quietly: both halves are still
    # valid floats.
    parts = _first_str(g.get("location")).split(",")
    if len(parts) != 2:
        return None
    try:
        lng, lat = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    level = _first_str(g.get("level"))
    if level in AMAP_LEVEL:
        precision = AMAP_LEVEL[level]
    elif level:
        precision = "area"
    else:
        precision = "unknown"
    return lat, lng, precision, _first_str(g.get("formatted_address"))


def _parse_google(text):
    """(lat, lng, precision, formatted) in GCJ-02, or None for ZERO_RESULTS.

    GCJ-02, not WGS-84: see the module docstring. Google applies the mainland
    offset to mainland results even though the same endpoint is WGS-84
    everywhere else.
    """
    data = json.loads(text)
    status = str(data.get("status", ""))
    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        # OVER_QUERY_LIMIT / REQUEST_DENIED / INVALID_REQUEST tell us nothing
        # about the address, so they must not be cached as a miss.
        raise GeocodeError("google status=%s error_message=%s"
                           % (status, data.get("error_message")))
    results = data.get("results") or []
    if not results or not isinstance(results[0], dict):
        return None
    r = results[0]
    geometry = r.get("geometry") or {}
    loc = geometry.get("location") or {}
    try:
        lat, lng = float(loc["lat"]), float(loc["lng"])
    except (KeyError, TypeError, ValueError):
        return None
    precision = GOOGLE_LOCATION_TYPE.get(
        str(geometry.get("location_type") or ""), "unknown")
    return lat, lng, precision, _first_str(r.get("formatted_address"))


def _baidu_url(addr, key=None):
    """map.baidu.com's own search backend. ``key`` is accepted and ignored.

    ``fromproduct=jsapi`` and ``res=api`` are what select the JSON API
    response; the same endpoint on map.baidu.com without them answers with an
    anti-bot page (``need_recaptcha: true``) and no content. ``c=1`` is the
    nationwide scope - the query already carries its own province and city, so
    a per-city code would only add a table to maintain.
    """
    return ("https://api.map.baidu.com/?qt=s&c=1&wd=%s&rn=10&ie=utf-8"
            "&oue=1&fromproduct=jsapi&res=api"
            % urllib.parse.quote(addr, safe=""))


#: Baidu refuses the request outright without a browser Referer: the response
#: is a 200 with a ``content`` that is not a POI list. Not optional. (Verified:
#: the identical URL fetched without this header comes back with content as a
#: dict and no POIs, every time.)
#:
#: Deliberately no ``Accept-Encoding: gzip``. urllib does not decompress, and
#: common.fetch hands back ``raw.decode("utf-8", errors="replace")`` - so
#: asking for gzip turns every response into replacement characters and every
#: parse into a GeocodeError. The endpoint answers plain text happily.
BAIDU_HEADERS = {"Referer": "https://map.baidu.com/"}


def _baidu_items(text):
    """POI dicts from a ``qt=s`` body, in Baidu's own ranking order.

    ``content`` has three shapes and only one of them is a result list:

      * a **list of POIs** - what a normal query returns.
      * a **dict** - the "you searched for an administrative area" jump, e.g.
        ``广东省深圳市宝安区``. It carries an x/y (the district centroid), which
        is precisely the answer we already have and must not accept as an
        address.
      * a **list of city suggestions** - ``政和路`` matches a road in eleven
        cities, so Baidu answers with the cities instead: ``{name: 洛阳市,
        code, num}``, no x/y at all.

    Only the first is a result. The other two are filtered here rather than
    downstream, so "Baidu answered with cities" and "Baidu answered with a POI
    we rejected" stay distinguishable.
    """
    data = json.loads(text)
    if not isinstance(data, dict):
        raise GeocodeError("baidu returned %s, expected an object"
                           % type(data).__name__)
    content = data.get("content")
    if not isinstance(content, list):
        return []
    out = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("x") is None or item.get("y") is None:
            continue    # city suggestion, not a POI
        out.append(item)
    return out


def _baidu_precision(di_tag):
    """"poi" / "street" for a result's tag, or None when it must be skipped."""
    tag = str(di_tag or "")
    for bad in _BAIDU_REJECT_TAGS:
        if tag.startswith(bad):
            return None
    for road in _BAIDU_ROAD_TAGS:
        if tag.startswith(road):
            return "street"
    return "poi"


def _parse_baidu(text):
    """(lat, lng, precision, formatted) in BD-09 degrees, or None.

    Takes the best usable POI rather than the first one. Baidu's ranking is
    excellent at finding the right BUILDING and indifferent to which of its
    dozen POIs it hands you first: a search for a mall routinely returns its
    underground car park or its north gate above the mall itself. Those are
    dropped, and a road-typed result is taken but demoted to street precision.
    """
    items = _baidu_items(text)
    if not items:
        return None
    road_fallback = None
    for item in items:
        precision = _baidu_precision(item.get("di_tag"))
        if precision is None:
            continue
        try:
            lat, lng = bdmc2bd(float(item["x"]) / 100.0,
                               float(item["y"]) / 100.0)
        except (TypeError, ValueError):
            continue
        # area_name (深圳市宝安区) is Baidu's own statement of which city the
        # answer is in, and it is what verify_area checks. Carrying it in
        # `formatted` alongside the address keeps the record self-describing
        # and keeps the check on one string.
        parts = (item.get("name"), item.get("addr"), item.get("area_name"))
        formatted = norm_addr(" ".join(str(p) for p in parts if p))
        if precision == "street":
            # Held back one round: a building further down the list beats a
            # road at the top of it, but a road beats nothing.
            if road_fallback is None:
                road_fallback = (lat, lng, precision, formatted)
            continue
        return lat, lng, precision, formatted
    return road_fallback


_URL_BUILDERS = {"amap": _amap_url, "google": _google_url,
                 "baidu": _baidu_url}
_PARSERS = {"amap": _parse_amap, "google": _parse_google,
            "baidu": _parse_baidu}

#: Datum each provider answers in, and therefore which conversion runs before
#: the value is cached. Getting this wrong is a silent 300 m - 1 km error.
_DATUM = {"amap": "gcj02", "google": "gcj02", "baidu": "bd09"}

_EXTRA_HEADERS = {"baidu": BAIDU_HEADERS}

#: Per-provider default gap between requests, when the caller does not say.
_DEFAULT_SLEEP = {"baidu": BAIDU_SLEEP}


def to_wgs(lat, lng, provider):
    """Provider-native coordinate -> WGS-84."""
    if _DATUM.get(provider) == "bd09":
        return eviltransform.bd2wgs(lat, lng)
    return eviltransform.gcj2wgs(lat, lng)


def resolve_provider(provider=None):
    """(name, key) for the provider to use, or (None, None) when off.

    A keyless provider resolves with ``key=None``, which is a normal, working
    configuration - not the "opted out" signal it used to be. Callers must
    test the NAME, never the key.

    An explicit KEYED provider with no key is still a mistake worth saying out
    loud: a typo'd env var name in CI otherwise looks identical to a
    deliberate opt-out.
    """
    if provider:
        provider = str(provider).strip().lower()
        if provider in KEYLESS:
            return provider, None
        if provider not in ENV_KEYS:
            print("geocode_cn: WARNING unknown provider %r (known: %s)"
                  % (provider, ", ".join(PROVIDERS)), file=sys.stderr)
            return None, None
        key = os.environ.get(ENV_KEYS[provider], "").strip()
        if not key:
            print("geocode_cn: WARNING provider %s requested but %s is not "
                  "set; nothing to do" % (provider, ENV_KEYS[provider]),
                  file=sys.stderr)
            return None, None
        return provider, key
    for name in PROVIDERS:
        if name in KEYLESS:
            return name, None
        key = os.environ.get(ENV_KEYS[name], "").strip()
        if key:
            return name, key
    return None, None


# ----------------------------------------------------------- verification ---
# A geocoder that always answers is not the same as a geocoder that is always
# right, and the keyless one always answers. Everything below exists to turn
# "here is a coordinate" into "here is a coordinate in the city you asked
# about", because a pin in the wrong province is strictly worse than the
# district centroid it would replace: the centroid is honest about being
# approximate, and a confident wrong pin is not.

def _admin_tokens(text):
    """(province_base, city_base) named in ``text``, as bare names.

    ``深圳市宝安区`` -> ``(None, "深圳")``; ``广东省广州市海珠区`` ->
    ``("广东", "广州")``. Both may be None: Baidu's ``area_name`` usually
    names the city and district and leaves the province out.
    """
    text = norm_addr(text)
    if not text:
        return None, None
    index = china_place.load_areas()
    prov = None
    prov_id, _how = china_place.match_area(text, index.provinces, index,
                                           allow_short=False)
    if prov_id is None:
        # A province's SHORT form is dangerous in the middle of a string -
        # 河北, 山东 and 上海 are all ordinary road names - which is why
        # china_place refuses it outright. At position 0 it is usually safe,
        # and it is extremely common here: qualified_address prepends the base
        # form (``北京朝阳区...``, ``河北任丘万达广场``), so requiring 北京市
        # would leave those unverifiable, and unverifiable means rejected.
        #
        # Usually, not always: a shop name can START with one. The real case
        # is 北京华联, a nationwide supermarket chain, so a Lanzhou answer
        # reading ``北京华联东方红购物中心 兰州市城关区南昌路982号`` reads as
        # "in Beijing" and its perfectly correct pin gets thrown away.
        #
        # The guard is corroboration: the token counts as a province only when
        # somewhere BELOW it in the table is named right after it. ``北京朝阳区``
        # names 朝阳区; ``河北任丘万达广场`` names 任丘市 (a county-level city,
        # so a grandchild, which is why the whole subtree is searched and not
        # just the city level). ``北京华联...兰州市城关区`` names nothing under
        # 北京 - 兰州 and 城关区 belong to 甘肃 - so 北京 is left unread and the
        # 兰州 further down the string is found instead.
        for aid in index.provinces:
            base = china_place.cn_base(index.name(aid))
            if not base or len(base) < 2 or not text.startswith(base):
                continue
            if china_place.match_area(text[len(base):],
                                      _descendants(aid, index), index)[0]:
                prov_id = aid
                break
    if prov_id is not None:
        prov = china_place.cn_base(index.name(prov_id))
    city = None
    scope = index.kids(prov_id) if prov_id is not None else None
    if scope is None:
        # No province named, so every city in the country is a candidate. Full
        # official names only (``深圳市``): the short forms include 通州, 东城
        # and a hundred other strings that are ordinary road and district names
        # elsewhere, and a false city here would let a wrong answer through the
        # very check that exists to stop it.
        best = None
        for aid, area in index.areas.items():
            if area["d"] != 1:
                continue
            pos = text.find(area["n"])
            if pos >= 0 and (best is None or pos < best[0]):
                best = (pos, aid)
        if best:
            city = china_place.cn_base(index.name(best[1]))
    else:
        city_id, _how = china_place.match_area(text, scope, index)
        if city_id is not None:
            city = china_place.cn_base(index.name(city_id))
    return prov, city


_DESCENDANT_CACHE = {}


def _descendants(area_id, index):
    """Every area under ``area_id``, cities and districts alike. Memoized.

    Both levels are needed: a bare leading province is corroborated by
    whatever it is followed by, and that is a city in ``河北省唐山市`` but a
    county-level city in ``河北任丘`` and a district in ``北京朝阳区``.
    """
    if area_id in _DESCENDANT_CACHE:
        return _DESCENDANT_CACHE[area_id]
    out = []
    stack = list(index.kids(area_id))
    while stack:
        kid = stack.pop()
        out.append(kid)
        stack.extend(index.kids(kid))
    out.sort()
    _DESCENDANT_CACHE[area_id] = out
    return out


_RADIUS_CACHE = {}


def area_radius_km(area_id, index=None):
    """How far this area actually reaches, measured from its own children.

    china_areas.json has a centroid per area and no polygon, so the extent is
    read off the child centroids: the farthest district from the city's own
    centre is a fair lower bound on the city's radius, and it is the number
    that separates 重庆市 (a province-sized municipality whose counties are
    350 km out) from a coastal prefecture 30 km across. Using one constant for
    both is what forces the choice between waving through a pin in the next
    province and rejecting a real arcade in an outlying county.

    Clamped to [MIN_RADIUS_KM, MAX_RADIUS_KM], and memoized: verify_area runs
    once per candidate per address, several thousand times a run.
    """
    index = index if index is not None else china_place.load_areas()
    if area_id in _RADIUS_CACHE:
        return _RADIUS_CACHE[area_id]
    clat, clng = index.coords(area_id)
    far = 0.0
    stack = list(index.kids(area_id))
    while stack:
        kid = stack.pop()
        if kid not in index.areas:
            continue
        klat, klng = index.coords(kid)
        far = max(far, haversine_km(clat, clng, klat, klng))
        stack.extend(index.kids(kid))
    radius = min(max(far, MIN_RADIUS_KM), MAX_RADIUS_KM)
    _RADIUS_CACHE[area_id] = radius
    return radius


def expected_area(addr):
    """(province_base, city_base) the QUERIED address claims to be in.

    This is the assertion the answer has to satisfy. It reads the address we
    sent, not the entry, because ``qualified_address`` already prepended the
    administrative tokens and the cache is keyed by that exact string - so the
    check works for a hand-written ``--addresses-from`` list too.
    """
    return _admin_tokens(addr)


def verify_area(addr, lat, lng, formatted, index=None):
    """Does a hit belong to the place the address named? (ok, reason).

    Two independent gates, and a hit has to clear both:

      * **Name.** The city the address names must be the city the provider
        says the answer is in. Baidu states that itself in ``area_name``,
        which ``_parse_baidu`` folds into ``formatted``; AMap and Google state
        it in their formatted address. This is the gate that catches the
        characteristic POI-search failure - you asked about 万达广场 and got
        one of the four hundred others.
      * **Distance.** The hit must be within a generous radius of that city's
        centroid. This is NOT a precision check: prefecture-level cities are
        the size of small countries, so the radius is 220 km and it is only
        there to catch a name coincidence (two 朝阳区, one in Beijing and one
        in Changchun) that the name gate cannot see.

    An address that names no city cannot be verified, and unverifiable is
    treated as failed - the caller prepends the region tokens precisely so
    this does not happen, and a row where it still does is a row we know
    nothing about.
    """
    want_prov, want_city = expected_area(addr)
    if not want_city and not want_prov:
        return False, "address names no city or province to verify against"

    index = index if index is not None else china_place.load_areas()
    got_prov, got_city = _admin_tokens(formatted)

    if want_city:
        if got_city and got_city == want_city:
            pass
        elif got_city and got_city != want_city:
            return False, ("answer is in %s, address says %s"
                           % (got_city, want_city))
        elif want_city in norm_addr(formatted):
            pass    # named, just not as a resolvable administrative token
        else:
            return False, ("answer does not name %s (%r)"
                           % (want_city, formatted[:60]))
    elif want_prov and got_prov and got_prov != want_prov:
        return False, ("answer is in %s province, address says %s"
                       % (got_prov, want_prov))

    # Distance backstop, against the deepest centroid we can name.
    target = None
    if want_city:
        for aid, area in index.areas.items():
            if area["d"] == 1 and china_place.cn_base(area["n"]) == want_city:
                target = aid
                break
    if target is None and want_prov:
        target = index.province_by_base.get(want_prov)
    if target is None:
        return True, "ok (no centroid to measure against)"
    limit = area_radius_km(target, index) + RADIUS_SLACK_KM
    clat, clng = index.coords(target)
    km = haversine_km(lat, lng, clat, clng)
    if km > limit:
        return False, ("%.0f km from %s, limit %.0f km"
                       % (km, index.name(target), limit))
    return True, "ok (%.0f km from %s)" % (km, index.name(target))


# ------------------------------------------------------------------ lookup ---

def geocode_one(addr, provider, key, sleep=None, day=None, queries=None,
                verify=True, on_reject=None):
    """Geocode one normalized address. Returns (record, kind).

    ``kind`` is one of:

      * "hit"      - a POI resolved and passed every gate.
      * "rejected" - POIs came back for at least one candidate, and every one
        of them failed the mainland box or the area check. We learned
        something real: this address does not resolve to anywhere it claims to
        be. Safe to cache.
      * "miss"     - no candidate produced a usable POI at all.

    The hit/rejected/miss split is not cosmetic, it is the rate-limit
    safeguard. A cached miss is permanent by design (never retried), so if the
    endpoint quietly starts answering everything with an empty list, writing
    those as misses would burn thousands of rows forever. "rejected" proves
    the provider is still talking; a LONG RUN of plain "miss" is what a wall
    looks like, and run() aborts on one rather than recording it.

    ``queries`` is the ordered candidate list from ``cn_address.candidates``.
    Each is tried in turn and the FIRST verified answer wins; the address
    itself is the fallback when the caller has nothing better. A candidate
    that resolves to the wrong city does not end the search - the next, coarser
    candidate gets its turn, which is what rescues a row whose street number
    is wrong but whose mall is named.
    """
    day = day or _today()
    if sleep is None:
        sleep = _DEFAULT_SLEEP.get(provider, MIN_SLEEP)
    queries = [q for q in (queries or []) if q] or [addr]
    headers = _EXTRA_HEADERS.get(provider)
    index = china_place.load_areas() if verify else None

    saw_any_poi = False
    for query in queries:
        url = _URL_BUILDERS[provider](query, key)
        # common.fetch sleeps AFTER a successful request, so passing the
        # interval here is the rate limit - no separate throttle to keep in
        # sync with it.
        text = fetch(url, extra_headers=headers,
                     sleep=max(float(sleep), MIN_SLEEP))
        try:
            parsed = _PARSERS[provider](text)
        except GeocodeError:
            raise
        except Exception as e:
            raise GeocodeError("%s returned an unparseable body for %r "
                               "(%s: %s)" % (provider, query,
                                             type(e).__name__, e))
        if parsed is None:
            continue
        saw_any_poi = True
        native_lat, native_lng, precision, formatted = parsed
        lat, lng = to_wgs(native_lat, native_lng, provider)
        if not in_mainland(lat, lng):
            if on_reject:
                on_reject(addr, query, lat, lng, formatted,
                          "outside the mainland box %s" % (CN_BBOX,))
            continue
        if verify:
            ok, why = verify_area(addr, lat, lng, formatted, index)
            if not ok:
                if on_reject:
                    on_reject(addr, query, lat, lng, formatted, why)
                continue
        return _hit_record(lat, lng, provider, precision, formatted, day,
                           query=query), "hit"

    if not saw_any_poi:
        return _miss_record(provider, day), "miss"
    return _miss_record(provider, day), "rejected"


# ------------------------------------------------------------------ refresh -

#: Records between flushes to disk. A full refresh is ~5.7k addresses at about
#: a second each, so a crash or a Ctrl-C at minute 80 of 95 must not throw the
#: work away: the file on disk is the resume point, because ``pending`` is
#: computed by subtracting it. Small enough to lose almost nothing, large
#: enough that we are not rewriting a 700 kB file every second.
FLUSH_EVERY = 25

#: Consecutive plain misses that mean "the endpoint has stopped answering"
#: rather than "these addresses are bad". Real data does not produce 40 in a
#: row - the observed miss rate is a few percent and they are scattered - so a
#: streak this long is a wall, and the run stops instead of writing 5,000
#: permanent misses. See geocode_one for why misses and rejections differ.
MISS_STREAK_ABORT = 40


def candidates_for(addr):
    """Query candidates for a bare address string, with no entry behind it.

    The fallback for ``--addresses-from`` and for any caller that did not
    build the ``queries`` map. It cannot supply the venue name or the resolved
    district, but the address itself still names its province and city (that
    is what ``qualified_address`` guaranteed), so cn_address can still strip
    the floor tail and derive the coarser rungs.
    """
    addr = norm_addr(addr)
    if not addr:
        return []
    prov, city = _admin_tokens(addr)
    index = china_place.load_areas()
    city_name = None
    if city:
        for aid, area in index.areas.items():
            if area["d"] == 1 and china_place.cn_base(area["n"]) == city:
                city_name = area["n"]
                break
    prov_name = None
    if prov:
        pid = index.province_by_base.get(prov)
        if pid is not None:
            prov_name = index.name(pid)
    return cn_address.candidates(addr, city=city_name, province=prov_name)


def _flush(path, cache):
    """Write the cache, sorted. Returns True on success. NEVER raises.

    Sorted keys so the committed diff is the new lines and nothing else.

    Written to a temp file and then ``os.replace``d, rather than straight
    through common.save_json, because this runs every FLUSH_EVERY records
    rather than once at the end. save_json truncates on open, so an interrupt
    mid-write leaves a half-file, and ``load_cache`` answers a corrupt file
    with ``{}`` - indistinguishable from "nothing geocoded yet", which would
    silently discard an hour of work on the resume. os.replace is atomic on
    both Windows and POSIX, so a reader sees the old complete file or the new
    one and never a partial one.

    The retry is not defensive programming, it is Windows. ``os.replace``
    fails with ``PermissionError: [WinError 5]`` when anything holds a handle
    on the destination for even a moment - a virus scanner, the search
    indexer, an open editor - and it is transient. Observed live: a full
    refresh died at record 250 of 2,436 on exactly this, taking the run with
    it. A checkpoint that can kill the run it exists to protect is worse than
    no checkpoint, so every failure path here ends in a warning and a return,
    never an exception: the cache in memory is still good, the file on disk is
    still the last complete flush, and the next flush will catch up.
    """
    tmp = path + ".tmp"
    payload = {k: cache[k] for k in sorted(cache)}
    try:
        common.save_json(tmp, payload)
    except OSError as e:
        print("geocode_cn: WARNING could not write %s (%s: %s); keeping the "
              "cache in memory and carrying on"
              % (tmp, type(e).__name__, e), file=sys.stderr)
        return False
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return True
        except OSError as e:
            if attempt == 4:
                print("geocode_cn: WARNING %s is locked by another process "
                      "(%s: %s); this checkpoint stays in %s and the next one "
                      "will retry" % (path, type(e).__name__, e, tmp),
                      file=sys.stderr)
                return False
            time.sleep(0.2 * (attempt + 1))
    return False    # pragma: no cover - the loop always returns


def run(addresses, out_dir="data", limit=None, provider=None,
        sleep=None, dry_run=False, path=None, queries=None, verify=True,
        reject_log=None):
    """Refresh the cache for ``addresses``. Returns the cache dict.

    Never raises for a feed problem, and never shrinks the cache. A provider
    failure stops the run where it stands, keeps whatever was already written,
    prints a warning and returns - the file on disk is only ever added to, so
    a half-finished refresh is a smaller cache, never a broken one.

    ``queries`` maps a normalized address to its ordered candidate list
    (``addresses_for(..., with_queries=True)`` builds both together, which is
    the only way to get the venue NAME into the candidates). An address with
    no entry there still gets parsed candidates, just without the name - so a
    caller that passes a bare address list (``--addresses-from``, or
    run_all.py) still gets the noise stripped and the coarser fallbacks tried,
    rather than one verbatim question with a floor number in it.
    """
    path = path or os.path.join(out_dir, OUTFILE)
    cache = load_cache(path)
    queries = queries or {}
    rejections = reject_log if reject_log is not None else []

    name, key = resolve_provider(provider)
    if not name:
        print("geocode_cn: no usable provider; skipping - the committed cache "
              "at %s is used as-is" % path, file=sys.stderr)
        return cache

    # Normalize and dedupe up front: the same address reaches us from both
    # WAHLAP and BemaniCN for a good number of venues, and asking twice about
    # one string is the easiest quota to waste.
    wanted = []
    seen = set()
    for a in addresses or []:
        k = norm_addr(a)
        if k and k not in seen:
            seen.add(k)
            wanted.append(k)

    pending = [k for k in wanted if k not in cache]
    cached = len(wanted) - len(pending)
    capped = 0
    if limit is not None and 0 <= limit < len(pending):
        capped = len(pending) - limit
        pending = pending[:limit]
    if capped:
        print("geocode_cn: --limit %d caps this run; %d new address(es) left "
              "for the next one" % (limit, capped), file=sys.stderr)

    if dry_run:
        print("geocode_cn: dry run - would geocode %d new address(es) via %s "
              "(%d already cached, %d held back by the cap); nothing fetched, "
              "nothing written" % (len(pending), name, cached, capped),
              file=sys.stderr)
        return cache

    def note_rejection(addr, query, lat, lng, formatted, why):
        rejections.append({"addr": addr, "query": query,
                           "lat": round(float(lat), 6),
                           "lng": round(float(lng), 6),
                           "got": formatted, "why": why})

    hits = misses = rejected = 0
    unflushed = 0
    miss_streak = 0
    for i, k in enumerate(pending, 1):
        asks = queries.get(k) or candidates_for(k)
        try:
            rec, kind = geocode_one(k, name, key, sleep=sleep, queries=asks,
                                    verify=verify, on_reject=note_rejection)
        except Exception as e:
            # fx.py's contract: an optional network step never fails the
            # build. Stop asking (whatever broke will break the next call
            # too), keep what we have, say so loudly.
            print("geocode_cn: WARNING %s failed on %r (%s: %s); stopping "
                  "here and keeping the existing cache"
                  % (name, k, type(e).__name__, e), file=sys.stderr)
            break
        if kind == "miss":
            miss_streak += 1
            if miss_streak >= MISS_STREAK_ABORT:
                # Do NOT record this one either: the whole streak is suspect,
                # but the ones already written are the price of noticing late.
                print("geocode_cn: WARNING %d consecutive addresses resolved "
                      "to nothing at all - that is a rate limit or a blocked "
                      "endpoint, not %d bad addresses. Stopping before this "
                      "poisons the cache with permanent misses."
                      % (miss_streak, miss_streak), file=sys.stderr)
                break
        else:
            miss_streak = 0
        cache[k] = rec
        unflushed += 1
        if kind == "hit":
            hits += 1
        elif kind == "rejected":
            rejected += 1
        else:
            misses += 1
        if unflushed >= FLUSH_EVERY:
            # Only reset the counter when the file actually landed. A failed
            # flush leaves the work unwritten, so it must stay "unflushed" and
            # be retried on the next checkpoint rather than being counted as
            # saved and lost if the run then dies.
            if _flush(path, cache):
                unflushed = 0
            print("geocode_cn: %d/%d done (%d hit, %d rejected, %d miss)"
                  % (i, len(pending), hits, rejected, misses),
                  file=sys.stderr)

    new = hits + misses + rejected
    if new:
        if unflushed:
            _flush(path, cache)
        print("geocode_cn: wrote %s (%d entries; +%d hit, +%d miss, "
              "+%d rejected this run; %d already cached, %d capped)"
              % (path, len(cache), hits, misses, rejected, cached, capped),
              file=sys.stderr)
    else:
        # Leaving the file untouched keeps `git status` clean on a no-op
        # refresh, which is what makes this safe to wire into a scheduled job.
        print("geocode_cn: nothing new to geocode (%d cached, %d capped); "
              "%s left untouched" % (cached, capped, path), file=sys.stderr)
    if rejections:
        print("geocode_cn: %d candidate answer(s) rejected by the area gate; "
              "first few:" % len(rejections), file=sys.stderr)
        for r in rejections[:5]:
            print("  %s -> %s | %s" % (r["query"], r["got"][:50], r["why"]),
                  file=sys.stderr)
    return cache


# ------------------------------------------------- merge-side integration ---
# The harvest side and the read side have to agree on the exact string, or the
# refresh pays for addresses merge will never look up. Both go through
# qualified_address(), which is why it lives here rather than in merge.

#: Provider precision -> the ``approx_level`` the map speaks.
#:
#: The right-hand side is NOT free-form: js/panel.js looks the value up in its
#: own table and falls back to the CITY text for anything it does not know, so
#: inventing a level here would render "this pin is the centre of the city"
#: over a rooftop-accurate pin. Only address / street / district / city exist.
#:
#: "poi" is Baidu's building-level answer and maps to address; "rooftop" is
#: AMap's and Google's word for the same thing. A provider's "area" answer is
#: its own administrative guess and a worse one than china_place's - it comes
#: with no level attached, so we cannot tell the reader whether it means a
#: district or a whole city. Those are absent from this table and fall through
#: to the centroid table instead.
USABLE_PRECISION = {"rooftop": "address", "poi": "address", "street": "street"}


def qualified_address(entry):
    """The geocodable string for one arcade, or "" when there is nothing to ask.

    BemaniCN publishes plenty of addresses like ``全运路万达3F`` - a road and a
    mall floor, no city - and a geocoder answers those with a confident 万达广场
    in the wrong province. Prepending the administrative tokens the address is
    missing is what makes the question answerable. Tokens already present are
    not repeated: ``河北省沧州市河北省沧州市运河区...`` degrades the match.
    """
    addr = (entry.get("addr") or "").strip()
    if not addr:
        return ""
    prov, city = china_place.region_tokens(entry.get("notes"))
    if not prov:
        prov = china_place.entry_province(entry)
    prefix = "".join(t for t in (prov, city) if t and t not in addr)
    return norm_addr(prefix + addr)


def entry_area_names(entry, index=None):
    """(province, city, district) official names for one entry, or Nones.

    The administrative context ``cn_address.candidates`` prepends to its short
    queries. Resolved through china_place so the strings are the table's own
    (``深圳市``, ``宝安区``) rather than whatever the source happened to print.
    """
    index = index if index is not None else china_place.load_areas()
    hit = china_place.resolve(dict(entry, lat=None, lng=None), index)
    if hit is None:
        prov, city = china_place.region_tokens(entry.get("notes"))
        return (prov or china_place.entry_province(entry)), city, None
    area_id, level = hit
    area = index.areas[area_id]
    if level == "district":
        district = area["n"]
        city_id = area["p"]
    else:
        district = None
        city_id = area_id
    city = index.areas[city_id]["n"] if city_id in index.areas else None
    prov_id = index.areas[city_id]["p"] if city_id in index.areas else None
    prov = index.areas[prov_id]["n"] if prov_id in index.areas else None
    return prov, city, district


def query_candidates(entry, index=None):
    """Ordered geocoder queries for one entry, best first.

    The address alone is a poor question (a floor label, a unit number and no
    city); this is the address parsed into the several better ones that are
    hiding inside it. See cn_address for the parsing itself.
    """
    prov, city, district = entry_area_names(entry, index)
    return cn_address.candidates(entry.get("addr") or "", city=city,
                                 district=district, province=prov,
                                 name=entry.get("name") or "")


def addresses_for(arcades, with_queries=False):
    """Qualified addresses for every row a cache hit could actually help.

    Deliberately the same guards as china_place: an entry that already has a
    coordinate, or that belongs to a territory we refuse to approximate, must
    not consume quota.

    ``with_queries`` also returns ``{address: [query, ...]}``, the candidate
    list ``run`` walks for that address. Built here, next to the harvesting,
    because the cache is keyed by the ADDRESS and asked by the QUERIES: if the
    two were computed in different places they would drift and the refresh
    would fill in keys merge never looks up.
    """
    index = china_place.load_areas()
    out = []
    queries = {}
    seen = set()
    for entry in arcades:
        # An APPROXIMATE coordinate is exactly what this is meant to replace,
        # so a centroid does not disqualify a row. Harvesting runs against the
        # finished arcades.json, where china_place has already placed almost
        # everything; filtering on "has a coordinate" there would leave only
        # the few hundred rows nothing could resolve.
        if entry.get("lat") is not None and not entry.get("approx"):
            continue
        if (entry.get("country") or "") not in china_place.PLACEABLE_COUNTRIES:
            continue
        if china_place.is_taiwan(entry):
            continue
        addr = qualified_address(entry)
        if addr and addr not in seen:
            seen.add(addr)
            out.append(addr)
            if with_queries:
                queries[addr] = query_candidates(entry, index)
    return (out, queries) if with_queries else out


#: china_place's own note, which this module's answer supersedes. Matched as a
#: prefix on one pipe-separated segment.
_CENTROID_NOTE = "position approximate:"


def _replace_note(entry, note):
    """Append ``note``, dropping any centroid note it makes untrue.

    A row that already carries ``position approximate: city centroid (沈阳市)``
    from a PREVIOUS build is exactly the row this module is here to improve,
    and merge re-runs on top of the last arcades.json rather than from scratch.
    Simply appending leaves the entry claiming both "this is the middle of
    Shenyang" and "this is the address" at once, and js/panel.js shows the
    reader whichever it finds - so the stale half is removed, not kept.
    """
    parts = [p.strip() for p in (entry.get("notes") or "").split("|")]
    parts = [p for p in parts if p and not p.startswith(_CENTROID_NOTE)]
    if note not in parts:
        parts.append(note)
    entry["notes"] = " | ".join(parts)


def apply_cache(arcades, cache=None, path=None):
    """Place coordinate-less China rows from the committed cache. Mutates.

    Runs BEFORE china_place, so a geocoded address wins over a centroid, and
    china_place then only sees what the cache could not answer. Returns log
    records for merge_log.json.
    """
    cache = cache if cache is not None else load_cache(path)
    if not cache:
        return []
    log = []
    for entry in arcades:
        if entry.get("lat") is not None or entry.get("lng") is not None:
            continue
        if (entry.get("country") or "") not in china_place.PLACEABLE_COUNTRIES:
            continue
        if china_place.is_taiwan(entry):
            continue
        rec = lookup(cache, qualified_address(entry))
        if not rec:
            continue
        level = USABLE_PRECISION.get(rec.get("precision"))
        if not level:
            continue
        entry["lat"] = round(float(rec["lat"]), 6)
        entry["lng"] = round(float(rec["lng"]), 6)
        # Still "approx": the pin is the building the address names, not a
        # surveyed doorway, and the panel says so. What changes is the LEVEL -
        # "the mall in the address" instead of "the middle of the district".
        entry["approx"] = True
        entry["approx_level"] = level
        note = ("position from address: geocoded to %s precision by %s"
                % (level, rec.get("provider") or "an unnamed provider"))
        _replace_note(entry, note)
        log.append({"id": entry.get("id"), "name": entry.get("name"),
                    "level": level, "provider": rec.get("provider"),
                    "lat": entry["lat"], "lng": entry["lng"]})
    return log


def _load_addresses(path):
    """Read the --addresses-from file: a JSON list of address strings."""
    try:
        data = common.load_json(path)
    except (OSError, ValueError) as e:
        common.die("cannot read %s (%s: %s)" % (path, type(e).__name__, e))
    if not isinstance(data, list):
        common.die("%s must contain a JSON list of address strings, got %s"
                   % (path, type(data).__name__))
    out = []
    for i, item in enumerate(data):
        if not isinstance(item, str):
            common.die("%s[%d] is %s, expected a string"
                       % (path, i, type(item).__name__))
        out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser(
        description="refresh data/china_geocode.json. Uses the keyless Baidu "
                    "endpoint by default; %s / %s take over when set. Never "
                    "runs during a normal build."
                    % (ENV_KEYS["amap"], ENV_KEYS["google"]))
    ap.add_argument("--limit", type=int, default=None,
                    help="max NEW addresses to geocode this run "
                         "(default: all); lets a first full pass be spread "
                         "over several runs")
    ap.add_argument("--provider", choices=sorted(PROVIDERS), default=None,
                    help="force a provider (default: first usable one, in "
                         "the order %s; baidu needs no key)"
                         % ", ".join(PROVIDERS))
    ap.add_argument("--data", default="data",
                    help="directory holding " + OUTFILE)
    ap.add_argument("--addresses-from", default=None,
                    help="JSON file containing a list of address strings")
    ap.add_argument("--from-arcades", default=None,
                    help="harvest the addresses out of a built arcades.json "
                         "(every coordinate-less mainland-China row), which is "
                         "how the pipeline calls this")
    ap.add_argument("--sleep", type=float, default=None,
                    help="seconds between requests (floor %.1f; default %.2f "
                         "for baidu)" % (MIN_SLEEP, BAIDU_SLEEP))
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be geocoded; fetch nothing, "
                         "write nothing")
    ap.add_argument("--reject-log", default=None,
                    help="write every area-gate rejection to this JSON file "
                         "(query, what came back, and why it was refused)")
    args = ap.parse_args()

    # Chinese addresses in the warnings die on the cp1252 Windows console.
    # Only the CLI does this: importing a module must not reconfigure the
    # caller's streams.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):    # pragma: no cover
            pass

    addresses = (_load_addresses(args.addresses_from)
                 if args.addresses_from else [])
    queries = {}
    if args.from_arcades:
        blob = common.load_json(args.from_arcades)
        harvested, queries = addresses_for(blob.get("arcades") or [],
                                           with_queries=True)
        addresses += harvested
    if addresses:
        print("geocode_cn: %d address(es) from %s"
              % (len(addresses), args.from_arcades or args.addresses_from),
              file=sys.stderr)
    elif resolve_provider(args.provider)[0]:
        print("geocode_cn: no addresses were given; pass --from-arcades "
              "data/arcades.json or --addresses-from <file.json>",
              file=sys.stderr)

    rejections = []
    cache = run(addresses, out_dir=args.data, limit=args.limit,
                provider=args.provider, sleep=args.sleep,
                dry_run=args.dry_run, queries=queries,
                reject_log=rejections)
    if args.reject_log and rejections:
        common.save_json(args.reject_log, rejections)
        print("geocode_cn: %d rejection(s) written to %s"
              % (len(rejections), args.reject_log), file=sys.stderr)
    resolved = sum(1 for v in cache.values()
                   if isinstance(v, dict) and not v.get("miss"))
    tiers = {}
    for v in cache.values():
        if isinstance(v, dict) and not v.get("miss"):
            tiers[v.get("precision")] = tiers.get(v.get("precision"), 0) + 1
    print("geocode_cn: cache holds %d address(es), %d with coordinates (%s)"
          % (len(cache), resolved,
             ", ".join("%s %d" % kv for kv in sorted(tiers.items()))))


if __name__ == "__main__":
    main()
