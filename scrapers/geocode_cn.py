"""Street-level geocoding cache for mainland-China addresses (opt-in).

``china_place`` can only put a coordinate-less Chinese venue on an
ADMINISTRATIVE centroid: ~5.9k pins land on a few hundred downtown points,
marked ``approx: true``, and any two arcades in one city are equally
"somewhere in that city". The addresses themselves are authoritative - the
only thing missing is a coordinate for them. This module buys that coordinate
once from a commercial Chinese geocoder and commits the answer to
``data/china_geocode.json``, so merge can place the venue at its real address
instead of the centroid.

The cache is the whole point. Geocoding thousands of addresses costs money and
quota, so the answer is a checked-in file: a normal build - every CI run,
every contributor without a key - reads it and pays nothing. Only an explicit
refresh with a key in the environment talks to a provider, and it only asks
about addresses the file does not already answer.

Opt-in, and silent when off. With neither AMAP_KEY nor GOOGLE_MAPS_API_KEY
set, ``run`` does nothing at all: no request, no write, no nonzero exit. That
is the normal state of this repo's weekly Actions run, which has no key, so
this step must never be the reason a build fails or a data file churns. It is
fx.py's contract, for the same reason: an optional network step that can fail
the pipeline is worse than no step at all.

Misses are cached too. An address no geocoder can resolve (a bare mall-floor
label, a closed venue) is stored as ``{"miss": true}`` rather than left
absent, so the next refresh does not re-pay for the same dead end every week.
``lookup`` never hands a miss back as a coordinate.

Coordinate systems, which is why this file is not thirty lines:

  * AMap returns GCJ-02, as Chinese regulation requires of every consumer map
    service operating in China.
  * Google returns GCJ-02 **as well** for mainland-China locations. That is
    the trap: the very same endpoint is WGS-84 everywhere else on earth, so
    anyone who "knows" Google speaks WGS-84 ships every Chinese pin 100-700 m
    off, in a direction that drifts with position and so reads as ordinary
    sloppiness instead of a systematic datum bug.

Both providers are therefore run through the vendored
``eviltransform.gcj2wgs`` before anything reaches the cache, and
``china_geocode.json`` is WGS-84 only - like the China centroid table, and
like ``data/arcades.json``, which is WGS-84 only, always.

Mainland bounding box, applied to every result. The gate is not about
jurisdiction, it is about garbage: a partial address such as ``中山路`` or
``万达广场3F`` resolves *somewhere*, and both providers would rather hand back
a confident-looking point in Kazakhstan or Hokkaido than admit they do not
know. Anything landing outside the box is stored as a miss, with a loud
warning, instead of becoming a pin.

What the box does NOT do is filter by jurisdiction - Taiwan, Hong Kong and
Macau all sit comfortably inside it. Those rows are out of scope for a
different reason, the one ``china_place`` gives for refusing them outright:
ALL.Net, e-amusement and ZIv already cover all three with real street-level
pins, so nothing is gained and the datum is not even safe there (the GCJ-02
offset does not apply uniformly outside the mainland, so a correct Hong Kong
answer could be shifted a few hundred metres by ``gcj2wgs`` and land inside
the box looking perfectly fine). Keeping them out is the CALLER's job, exactly
as it is in ``china_place``; the box will not catch the mistake.

Nor can the box catch a wrong-but-plausible answer, so the caller owns
address quality too: hand over a string that identifies the city. WAHLAP rows
already do (``河北省唐山市开平区中骏世界城二层``); a BemaniCN address like
``全运路万达3F`` names no city and will happily resolve to a 万达广场 in the
wrong province, inside the box, looking perfectly fine.

Refresh (nothing here runs during a normal build):

    AMAP_KEY=... python scrapers/geocode_cn.py --addresses-from addrs.json
    python scrapers/geocode_cn.py --addresses-from addrs.json --limit 500
    python scrapers/geocode_cn.py --addresses-from addrs.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import china_place    # shared skip rules + region parsing
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

#: Provider order for auto-selection: first one with a key in the environment
#: wins. AMap leads because it is the accurate one on Chinese street
#: addresses; Google is the fallback for contributors who cannot get an AMap
#: key (it needs a mainland-registered account).
PROVIDERS = ("amap", "google")

ENV_KEYS = {"amap": "AMAP_KEY", "google": "GOOGLE_MAPS_API_KEY"}

#: Floor on the gap between two requests. Both providers rate-limit per key
#: and answer a burst with quota errors rather than results, and a run that
#: trips the limit halfway through has spent real money on nothing. Requests
#: are also strictly serial for the same reason - see run().
MIN_SLEEP = 0.2

#: Mainland-China sanity box (lat_min, lat_max, lng_min, lng_max). Deliberately
#: tighter than eviltransform.out_of_china, which is a datum-coverage test and
#: not a plausibility test.
CN_BBOX = (17.5, 54.0, 73.0, 135.5)

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

def norm_addr(addr):
    """Cache key for an address: NFKC, whitespace collapsed, stripped.

    NFKC is what makes the key stable across sources. The same venue arrives
    as ``红旗大街 西美花街`` from one feed and with a U+3000 ideographic space
    or fullwidth digits from another; without folding them together the cache
    stores - and pays for - the same address twice and merge still misses.
    """
    if addr is None:
        return ""
    return " ".join(unicodedata.normalize("NFKC", str(addr)).split())


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


def _hit_record(lat, lng, provider, precision, formatted, day):
    # Fixed key order and 6 dp (~0.1 m, far past what any geocoder promises)
    # so a re-run that changes nothing produces a byte-identical file and the
    # weekly commit stays empty.
    return {
        "lat": round(float(lat), 6),
        "lng": round(float(lng), 6),
        "provider": provider,
        "precision": precision,
        "formatted": formatted or "",
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


_URL_BUILDERS = {"amap": _amap_url, "google": _google_url}
_PARSERS = {"amap": _parse_amap, "google": _parse_google}


def resolve_provider(provider=None):
    """(name, key) for the provider to use, or (None, None) when off.

    An explicit ``provider`` with no key is a mistake worth saying out loud
    (a typo'd env var name in CI otherwise looks identical to "opted out"),
    but it is still not fatal.
    """
    if provider:
        provider = str(provider).strip().lower()
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
        key = os.environ.get(ENV_KEYS[name], "").strip()
        if key:
            return name, key
    return None, None


def geocode_one(addr, provider, key, sleep=MIN_SLEEP, day=None):
    """Geocode one normalized address. Returns (record, kind).

    ``kind`` is "hit", "miss" (provider found nothing) or "rejected" (found
    something outside the mainland box). Raises GeocodeError when the provider
    itself failed, so run() can stop with the cache intact instead of writing
    a miss it would never retry.
    """
    day = day or _today()
    url = _URL_BUILDERS[provider](addr, key)
    # common.fetch sleeps AFTER a successful request, so passing the interval
    # here is the rate limit - no separate throttle to keep in sync with it.
    text = fetch(url, sleep=max(float(sleep), MIN_SLEEP))
    try:
        parsed = _PARSERS[provider](text)
    except GeocodeError:
        raise
    except Exception as e:
        raise GeocodeError("%s returned an unparseable body for %r (%s: %s)"
                           % (provider, addr, type(e).__name__, e))
    if parsed is None:
        return _miss_record(provider, day), "miss"
    gcj_lat, gcj_lng, precision, formatted = parsed
    lat, lng = eviltransform.gcj2wgs(gcj_lat, gcj_lng)
    if not in_mainland(lat, lng):
        print("geocode_cn: WARNING %s put %r at %.6f,%.6f - outside the "
              "mainland box %s; caching as a miss rather than pinning it"
              % (provider, addr, lat, lng, CN_BBOX), file=sys.stderr)
        return _miss_record(provider, day), "rejected"
    return _hit_record(lat, lng, provider, precision, formatted, day), "hit"


# ------------------------------------------------------------------ refresh -

def run(addresses, out_dir="data", limit=None, provider=None,
        sleep=MIN_SLEEP, dry_run=False, path=None):
    """Refresh the cache for ``addresses``. Returns the cache dict.

    Never raises for a feed problem, and never shrinks the cache. A provider
    failure stops the run where it stands, keeps whatever was already paid
    for, prints a warning and returns - the file on disk is only ever added
    to, so a half-finished refresh is a smaller cache, never a broken one.
    """
    path = path or os.path.join(out_dir, OUTFILE)
    cache = load_cache(path)

    name, key = resolve_provider(provider)
    if not name:
        print("geocode_cn: no provider key in the environment (%s); skipping "
              "- the committed cache at %s is used as-is"
              % (", ".join(ENV_KEYS[p] for p in PROVIDERS), path),
              file=sys.stderr)
        return cache

    # Normalize and dedupe up front: the same address reaches us from both
    # WAHLAP and BemaniCN for a good number of venues, and paying twice for
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

    hits = misses = rejected = 0
    for k in pending:
        try:
            rec, kind = geocode_one(k, name, key, sleep=sleep)
        except Exception as e:
            # fx.py's contract: an optional network step never fails the
            # build. Stop asking (whatever broke will break the next call
            # too), keep what we have, say so loudly.
            print("geocode_cn: WARNING %s failed on %r (%s: %s); stopping "
                  "here and keeping the existing cache"
                  % (name, k, type(e).__name__, e), file=sys.stderr)
            break
        cache[k] = rec
        if kind == "hit":
            hits += 1
        elif kind == "rejected":
            rejected += 1
        else:
            misses += 1

    new = hits + misses + rejected
    if new:
        # Sorted keys so the committed diff is the new lines and nothing else;
        # common.save_json truncates on open, so it is called once, at the
        # end, with a complete payload (same pattern as fx.run).
        common.save_json(path, {k: cache[k] for k in sorted(cache)})
        print("geocode_cn: wrote %s (%d entries; +%d hit, +%d miss, "
              "+%d rejected this run; %d already cached, %d capped)"
              % (path, len(cache), hits, misses, rejected, cached, capped),
              file=sys.stderr)
    else:
        # Leaving the file untouched keeps `git status` clean on a no-op
        # refresh, which is what makes this safe to wire into a scheduled job.
        print("geocode_cn: nothing new to geocode (%d cached, %d capped); "
              "%s left untouched" % (cached, capped, path), file=sys.stderr)
    return cache


# ------------------------------------------------- merge-side integration ---
# The harvest side and the read side have to agree on the exact string, or the
# refresh pays for addresses merge will never look up. Both go through
# qualified_address(), which is why it lives here rather than in merge.

#: Precisions worth taking. A provider's "area" answer is its own
#: administrative guess, and a worse one than china_place's: it comes with no
#: level attached, so we cannot tell the reader whether it means a district or
#: a whole city. Those fall through to the centroid table instead.
USABLE_PRECISION = {"rooftop": "address", "street": "street"}


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


def addresses_for(arcades):
    """Qualified addresses for every row a cache hit could actually help.

    Deliberately the same guards as china_place: an entry that already has a
    coordinate, or that belongs to a territory we refuse to approximate, must
    not consume quota.
    """
    out = []
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
    return out


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
        entry["approx"] = True
        entry["approx_level"] = level
        note = ("position from address: geocoded to %s precision by %s"
                % (level, rec.get("provider") or "an unnamed provider"))
        existing = entry.get("notes")
        if not existing:
            entry["notes"] = note
        elif note not in existing:
            entry["notes"] = existing + " | " + note
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
        description="refresh data/china_geocode.json (needs %s or %s; a no-op "
                    "without one)" % (ENV_KEYS["amap"], ENV_KEYS["google"]))
    ap.add_argument("--limit", type=int, default=None,
                    help="max NEW addresses to geocode this run "
                         "(default: all); lets a first full pass be spread "
                         "over several runs")
    ap.add_argument("--provider", choices=sorted(PROVIDERS), default=None,
                    help="force a provider (default: first one whose key is "
                         "set, in the order %s)" % ", ".join(PROVIDERS))
    ap.add_argument("--data", default="data",
                    help="directory holding " + OUTFILE)
    ap.add_argument("--addresses-from", default=None,
                    help="JSON file containing a list of address strings")
    ap.add_argument("--from-arcades", default=None,
                    help="harvest the addresses out of a built arcades.json "
                         "(every coordinate-less mainland-China row), which is "
                         "how the pipeline calls this")
    ap.add_argument("--sleep", type=float, default=MIN_SLEEP,
                    help="seconds between requests (floor %.1f)" % MIN_SLEEP)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be geocoded; fetch nothing, "
                         "write nothing")
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
    if args.from_arcades:
        blob = common.load_json(args.from_arcades)
        addresses += addresses_for(blob.get("arcades") or [])
    if addresses:
        print("geocode_cn: %d address(es) from %s"
              % (len(addresses), args.addresses_from), file=sys.stderr)
    elif resolve_provider(args.provider)[0]:
        print("geocode_cn: a provider key is set but no addresses were given; "
              "pass --addresses-from <file.json>", file=sys.stderr)

    cache = run(addresses, out_dir=args.data, limit=args.limit,
                provider=args.provider, sleep=args.sleep,
                dry_run=args.dry_run)
    resolved = sum(1 for v in cache.values()
                   if isinstance(v, dict) and not v.get("miss"))
    print("geocode_cn: cache holds %d address(es), %d with coordinates"
          % (len(cache), resolved))


if __name__ == "__main__":
    main()
