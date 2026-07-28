"""Unit tests for scrapers/geocode_cn.py (canned provider payloads, no network).

Every request goes through the module-level ``geocode_cn.fetch`` alias, which
these tests replace with a fake that answers from a dict keyed by the address
in the query string. Nothing here touches the real committed cache: each case
gets its own temp directory.

Run: python scrapers/test_geocode_cn.py
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eviltransform
import geocode_cn as gc

# Chinese addresses in test output die on the cp1252 Windows console.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):   # pragma: no cover
    pass

FAILED = []
RAN = []


def check(label, cond, detail=""):
    print("%s  %s%s" % ("PASS" if cond else "FAIL", label,
                        ("  <- " + detail) if detail else ""))
    RAN.append(label)
    if not cond:
        FAILED.append(label)


# ------------------------------------------------------------------ helpers -

TMPDIRS = []


def fresh_dir():
    d = tempfile.mkdtemp(prefix="geocode_cn_test_")
    TMPDIRS.append(d)
    return d


def set_keys(amap=None, google=None):
    """Point the module at a provider (or at none) for the next run()."""
    for env, val in ((gc.ENV_KEYS["amap"], amap),
                     (gc.ENV_KEYS["google"], google)):
        if val:
            os.environ[env] = val
        else:
            os.environ.pop(env, None)


def fake_fetch(payloads):
    """(fake_fetch_callable, calls_list). Answers by ?address= value."""
    calls = []

    def fake(url, *args, **kwargs):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        addr = (query.get("address") or [""])[0]
        calls.append(addr)
        if addr not in payloads:
            raise AssertionError("fake fetch: no canned payload for %r" % addr)
        return json.dumps(payloads[addr], ensure_ascii=False)

    return fake, calls


def install(payloads):
    fake, calls = fake_fetch(payloads)
    gc.fetch = fake
    return calls


def amap_hit(lng, lat, level, formatted="AMAP FORMATTED"):
    """AMap packs "lng,lat" into one string - longitude first, on purpose."""
    return {"status": "1", "info": "OK", "infocode": "10000", "count": "1",
            "geocodes": [{"formatted_address": formatted,
                          "location": "%.6f,%.6f" % (lng, lat),
                          "level": level}]}


AMAP_ZERO = {"status": "1", "info": "OK", "infocode": "10000",
             "count": "0", "geocodes": []}
AMAP_DENIED = {"status": "0", "info": "INVALID_USER_KEY",
               "infocode": "10001", "geocodes": []}


def google_hit(lat, lng, location_type, formatted="GOOGLE FORMATTED"):
    return {"status": "OK",
            "results": [{"formatted_address": formatted,
                         "geometry": {"location": {"lat": lat, "lng": lng},
                                      "location_type": location_type}}]}


GOOGLE_ZERO = {"status": "ZERO_RESULTS", "results": []}
GOOGLE_DENIED = {"status": "OVER_QUERY_LIMIT", "results": [],
                 "error_message": "quota"}


def metres(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def is_day(s):
    return (isinstance(s, str) and len(s) == 10 and s[4] == "-"
            and s[7] == "-" and s.replace("-", "").isdigit())


# GCJ-02 points as the providers would return them.
TANGSHAN = (39.630000, 118.176000)      # amap case
SHANGHAI = (31.230416, 121.473701)      # google case
ADDR_CN = "河北省唐山市开平区中骏世界城二层"
ADDR_SH = "上海市黄浦区南京东路300号"

# -------------------------------------------------------------- amap hit ----
print("--- amap: GCJ-02 payload becomes a WGS-84 cache entry ---")
set_keys(amap="testkey")
d = fresh_dir()
calls = install({ADDR_CN: amap_hit(TANGSHAN[1], TANGSHAN[0], "门牌号")})
cache = gc.run([ADDR_CN], out_dir=d)
rec = gc.lookup(cache, ADDR_CN)
check("amap result is cached and looked up", rec is not None, repr(cache))
check("exactly one request was made", len(calls) == 1, repr(calls))
if rec:
    off = metres(TANGSHAN[0], TANGSHAN[1], rec["lat"], rec["lng"])
    check("GCJ-02 offset was actually removed (100-800 m)",
          100.0 < off < 800.0, "moved %.1f m" % off)
    check("stored point is not the raw GCJ-02 point",
          (round(rec["lat"], 6), round(rec["lng"], 6))
          != (round(TANGSHAN[0], 6), round(TANGSHAN[1], 6)))
    want = eviltransform.gcj2wgs(*TANGSHAN)
    check("stored point equals eviltransform.gcj2wgs of the payload",
          abs(rec["lat"] - want[0]) < 1e-6 and abs(rec["lng"] - want[1]) < 1e-6,
          "%r vs %r" % ((rec["lat"], rec["lng"]), want))
    check("amap lng/lat order was not swapped (point is in Hebei, not at sea)",
          38.0 < rec["lat"] < 41.0 and 117.0 < rec["lng"] < 119.5,
          "%.6f,%.6f" % (rec["lat"], rec["lng"]))
    check("provider recorded", rec.get("provider") == "amap")
    check("precision 门牌号 -> rooftop", rec.get("precision") == "rooftop",
          repr(rec.get("precision")))
    check("formatted address kept",
          rec.get("formatted") == "AMAP FORMATTED", repr(rec.get("formatted")))
    check("fetched_at is a YYYY-MM-DD day", is_day(rec.get("fetched_at")),
          repr(rec.get("fetched_at")))

path = os.path.join(d, gc.OUTFILE)
check("cache file written", os.path.isfile(path), path)
on_disk = gc.load_cache(path)
check("file round-trips through load_cache", on_disk == cache,
      "%r vs %r" % (on_disk, cache))
check("keyed by the normalized address", list(on_disk) == [gc.norm_addr(ADDR_CN)],
      repr(list(on_disk)))

print("\n--- amap: a second run re-uses the cache and asks nothing ---")
calls = install({})     # any request at all would raise AssertionError
cache2 = gc.run([ADDR_CN], out_dir=d)
check("cached address is not re-fetched", len(calls) == 0, repr(calls))
check("cache content survives the no-op run", cache2 == cache)

# ------------------------------------------------------------ google hit ----
print("\n--- google: mainland results are GCJ-02 too, and get converted ---")
set_keys(google="testkey")
d = fresh_dir()
calls = install({ADDR_SH: google_hit(SHANGHAI[0], SHANGHAI[1], "ROOFTOP")})
cache = gc.run([ADDR_SH], out_dir=d)
rec = gc.lookup(cache, ADDR_SH)
check("google result is cached and looked up", rec is not None, repr(cache))
check("exactly one request was made", len(calls) == 1, repr(calls))
if rec:
    off = metres(SHANGHAI[0], SHANGHAI[1], rec["lat"], rec["lng"])
    check("GCJ-02 offset was actually removed (100-800 m)",
          100.0 < off < 800.0, "moved %.1f m" % off)
    check("stored point is not the raw google point",
          (round(rec["lat"], 6), round(rec["lng"], 6))
          != (round(SHANGHAI[0], 6), round(SHANGHAI[1], 6)))
    want = eviltransform.gcj2wgs(*SHANGHAI)
    check("stored point equals eviltransform.gcj2wgs of the payload",
          abs(rec["lat"] - want[0]) < 1e-6 and abs(rec["lng"] - want[1]) < 1e-6,
          "%r vs %r" % ((rec["lat"], rec["lng"]), want))
    check("provider recorded", rec.get("provider") == "google")
    check("precision ROOFTOP -> rooftop", rec.get("precision") == "rooftop",
          repr(rec.get("precision")))

print("\n--- provider selection ---")
set_keys(amap="a", google="g")
check("amap wins when both keys are set",
      gc.resolve_provider()[0] == "amap", repr(gc.resolve_provider()))
check("--provider google forces google",
      gc.resolve_provider("google") == ("google", "g"),
      repr(gc.resolve_provider("google")))
set_keys(google="g")
check("google is used when only its key is set",
      gc.resolve_provider()[0] == "google", repr(gc.resolve_provider()))
check("forcing a provider whose key is missing is off, not a crash",
      gc.resolve_provider("amap") == (None, None),
      repr(gc.resolve_provider("amap")))
check("an unknown provider name is off, not a crash",
      gc.resolve_provider("baidu") == (None, None))

# ------------------------------------------------------------- precision ----
print("\n--- precision mapping (amap level) ---")
set_keys(amap="testkey")
AMAP_LEVELS = [("门牌号", "rooftop"), ("兴趣点", "rooftop"),
               ("道路", "street"), ("道路交叉路口", "street"),
               ("区县", "area"), ("省", "area"), ("", "unknown")]
d = fresh_dir()
payloads = {}
for level, _want in AMAP_LEVELS:
    payloads["A" + (level or "NONE")] = amap_hit(
        TANGSHAN[1], TANGSHAN[0], level)
calls = install(payloads)
cache = gc.run(sorted(payloads), out_dir=d)
for level, want in AMAP_LEVELS:
    rec = gc.lookup(cache, "A" + (level or "NONE"))
    got = rec.get("precision") if rec else None
    check("amap level %r -> %s" % (level, want), got == want, repr(got))

print("\n--- precision mapping (google location_type) ---")
set_keys(google="testkey")
GOOGLE_TYPES = [("ROOFTOP", "rooftop"), ("RANGE_INTERPOLATED", "street"),
                ("GEOMETRIC_CENTER", "street"), ("APPROXIMATE", "area"),
                ("", "unknown")]
d = fresh_dir()
payloads = {}
for ltype, _want in GOOGLE_TYPES:
    payloads["G" + (ltype or "NONE")] = google_hit(
        SHANGHAI[0], SHANGHAI[1], ltype)
calls = install(payloads)
cache = gc.run(sorted(payloads), out_dir=d)
for ltype, want in GOOGLE_TYPES:
    rec = gc.lookup(cache, "G" + (ltype or "NONE"))
    got = rec.get("precision") if rec else None
    check("google location_type %r -> %s" % (ltype, want), got == want,
          repr(got))

# ------------------------------------------------------------- zero hits ----
print("\n--- zero results are cached as a miss, never as a coordinate ---")
NOWHERE = "全运路万达3F"
set_keys(amap="testkey")
d = fresh_dir()
calls = install({NOWHERE: AMAP_ZERO})
cache = gc.run([NOWHERE], out_dir=d)
key = gc.norm_addr(NOWHERE)
check("amap zero-result address is in the cache", key in cache, repr(cache))
check("stored as a miss", bool(cache.get(key, {}).get("miss")),
      repr(cache.get(key)))
check("miss record carries provider and fetched_at",
      cache.get(key, {}).get("provider") == "amap"
      and is_day(cache.get(key, {}).get("fetched_at")), repr(cache.get(key)))
check("miss record has no coordinates",
      "lat" not in cache.get(key, {}) and "lng" not in cache.get(key, {}),
      repr(cache.get(key)))
check("lookup() refuses to return a miss", gc.lookup(cache, NOWHERE) is None)
calls = install({})
gc.run([NOWHERE], out_dir=d)
check("a cached miss is not re-paid for on the next run", len(calls) == 0,
      repr(calls))

set_keys(google="testkey")
d = fresh_dir()
calls = install({NOWHERE: GOOGLE_ZERO})
cache = gc.run([NOWHERE], out_dir=d)
check("google ZERO_RESULTS becomes a miss too",
      bool(cache.get(key, {}).get("miss")), repr(cache.get(key)))
check("lookup() refuses the google miss", gc.lookup(cache, NOWHERE) is None)

# ------------------------------------------------------------------ bbox ----
print("\n--- results outside the mainland box are rejected ---")
set_keys(amap="testkey")
d = fresh_dir()
SG = (1.350000, 103.800000)         # inside eviltransform's box, far outside ours
calls = install({"SINGAPORE": amap_hit(SG[1], SG[0], "门牌号")})
cache = gc.run(["SINGAPORE"], out_dir=d)
check("out-of-box amap result is cached as a miss",
      bool(cache.get("SINGAPORE", {}).get("miss")), repr(cache.get("SINGAPORE")))
check("out-of-box result never becomes a pin",
      gc.lookup(cache, "SINGAPORE") is None)

set_keys(google="testkey")
d = fresh_dir()
TOKYO = (35.680000, 139.760000)     # outside eviltransform's box: no conversion
calls = install({"TOKYO": google_hit(TOKYO[0], TOKYO[1], "ROOFTOP")})
cache = gc.run(["TOKYO"], out_dir=d)
check("out-of-box google result is cached as a miss",
      bool(cache.get("TOKYO", {}).get("miss")), repr(cache.get("TOKYO")))
check("out-of-box google result never becomes a pin",
      gc.lookup(cache, "TOKYO") is None)

print("\n--- lookup re-checks the box, so a bad committed row cannot pin ---")
check("hand-edited out-of-box row is refused on read",
      gc.lookup({"X": {"lat": 35.68, "lng": 139.76, "provider": "amap",
                       "precision": "rooftop", "formatted": "",
                       "fetched_at": "2026-07-28"}}, "X") is None)
check("non-numeric coordinates are refused on read",
      gc.lookup({"X": {"lat": "39.6", "lng": "118.1"}}, "X") is None)
check("lookup on an empty cache is None", gc.lookup({}, ADDR_CN) is None)
check("lookup on a missing address is None",
      gc.lookup({"other": {"lat": 39.6, "lng": 118.1}}, ADDR_CN) is None)

# ----------------------------------------------------------------- limit ----
print("\n--- --limit caps NEW addresses per run ---")
set_keys(amap="testkey")
d = fresh_dir()
THREE = ["L1", "L2", "L3"]
payloads = {a: amap_hit(TANGSHAN[1], TANGSHAN[0], "道路") for a in THREE}
calls = install(payloads)
cache = gc.run(THREE, out_dir=d, limit=1)
check("limit=1 makes exactly one request", len(calls) == 1, repr(calls))
check("limit=1 caches exactly one entry", len(cache) == 1, repr(sorted(cache)))
check("the capped addresses are untouched",
      all(a not in cache for a in THREE[1:]), repr(sorted(cache)))
check("the one geocoded address resolves",
      gc.lookup(cache, calls[0]) is not None)

calls = install(payloads)
cache = gc.run(THREE, out_dir=d, limit=1)
check("the next run picks up where it stopped (one more request)",
      len(calls) == 1, repr(calls))
check("cache has grown to two entries", len(cache) == 2, repr(sorted(cache)))

calls = install(payloads)
cache = gc.run(THREE, out_dir=d)
check("an uncapped run finishes the rest", len(calls) == 1, repr(calls))
check("all three are cached now", len(cache) == 3, repr(sorted(cache)))
check("limit=0 geocodes nothing",
      len(install(payloads)) == 0 and
      len(gc.run(["L4"], out_dir=d, limit=0)) == 3)

# ------------------------------------------------------------- normalizer ---
print("\n--- norm_addr folds NFKC / fullwidth spellings into one entry ---")
WIDE = "北京市　朝阳区　１号"        # U+3000 spaces + fullwidth digit
NARROW = "北京市 朝阳区 1号"
check("norm_addr collapses U+3000 and fullwidth digits",
      gc.norm_addr(WIDE) == gc.norm_addr(NARROW),
      "%r vs %r" % (gc.norm_addr(WIDE), gc.norm_addr(NARROW)))
check("norm_addr strips and collapses runs of whitespace",
      gc.norm_addr("  上海市   南京东路  ") == "上海市 南京东路",
      repr(gc.norm_addr("  上海市   南京东路  ")))
check("norm_addr(None) is empty", gc.norm_addr(None) == "")

set_keys(amap="testkey")
d = fresh_dir()
calls = install({gc.norm_addr(NARROW): amap_hit(TANGSHAN[1], TANGSHAN[0],
                                                "兴趣点")})
cache = gc.run([WIDE, NARROW], out_dir=d)
check("two spellings share one cache entry and one request",
      len(cache) == 1 and len(calls) == 1,
      "%r / %r" % (sorted(cache), calls))
check("either spelling looks the entry up",
      gc.lookup(cache, WIDE) is not None
      and gc.lookup(cache, NARROW) is not None)
check("blank addresses are dropped, not geocoded",
      len(install({})) == 0
      and gc.run(["", "   ", None], out_dir=fresh_dir()) == {})

# ---------------------------------------------------------------- opt-in ----
print("\n--- no key in the environment: a total no-op ---")
set_keys()      # neither AMAP_KEY nor GOOGLE_MAPS_API_KEY
d = fresh_dir()
seed = {"SEEDED": {"lat": 39.628684, "lng": 118.169710, "provider": "amap",
                   "precision": "rooftop", "formatted": "seed",
                   "fetched_at": "2026-07-01"}}
seed_path = os.path.join(d, gc.OUTFILE)
with open(seed_path, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(seed, fh, ensure_ascii=False, indent=1)
before = open(seed_path, encoding="utf-8").read()
calls = install({})
cache = gc.run([ADDR_CN, ADDR_SH], out_dir=d)
check("keyless run makes no request", len(calls) == 0, repr(calls))
check("keyless run returns the committed cache unchanged", cache == seed,
      repr(cache))
check("keyless run does not rewrite the file",
      open(seed_path, encoding="utf-8").read() == before)
check("the seeded entry still resolves",
      gc.lookup(cache, "SEEDED") is not None)
check("load_cache on a missing file is {}",
      gc.load_cache(os.path.join(fresh_dir(), "nope.json")) == {})

print("\n--- dry run: plan only ---")
set_keys(amap="testkey")
d = fresh_dir()
calls = install({})
cache = gc.run([ADDR_CN], out_dir=d, dry_run=True)
check("dry run fetches nothing", len(calls) == 0, repr(calls))
check("dry run writes nothing",
      not os.path.isfile(os.path.join(d, gc.OUTFILE)))
check("dry run returns the cache unchanged", cache == {})

# ------------------------------------------------------- provider failure ---
print("\n--- a provider failure never raises and never shrinks the cache ---")
set_keys(amap="testkey")
d = fresh_dir()
calls = install({"OK1": amap_hit(TANGSHAN[1], TANGSHAN[0], "门牌号"),
                 "BAD": AMAP_DENIED, "AFTER": AMAP_ZERO})
try:
    cache = gc.run(["OK1", "BAD", "AFTER"], out_dir=d)
    raised = None
except Exception as exc:                       # noqa: BLE001
    cache, raised = None, exc
check("an invalid key does not raise into the caller", raised is None,
      repr(raised))
if cache is not None:
    check("the run stops at the failure instead of burning the rest",
          calls == ["OK1", "BAD"], repr(calls))
    check("work already paid for is kept", gc.lookup(cache, "OK1") is not None,
          repr(cache))
    check("the failed address is NOT cached as a miss", "BAD" not in cache,
          repr(sorted(cache)))

set_keys(google="testkey")
d = fresh_dir()
calls = install({"Q": GOOGLE_DENIED})
try:
    cache = gc.run(["Q"], out_dir=d)
    raised = None
except Exception as exc:                       # noqa: BLE001
    cache, raised = None, exc
check("google OVER_QUERY_LIMIT does not raise", raised is None, repr(raised))
check("google OVER_QUERY_LIMIT is not cached as a miss", cache == {},
      repr(cache))
check("nothing is written when nothing succeeded",
      not os.path.isfile(os.path.join(d, gc.OUTFILE)))

# ------------------------------------------------------------------ file ----
print("\n--- output determinism ---")
set_keys(amap="testkey")
d = fresh_dir()
KEYS = ["Z", "A", "M"]
calls = install({a: amap_hit(TANGSHAN[1], TANGSHAN[0], "道路") for a in KEYS})
gc.run(KEYS, out_dir=d)
written = json.loads(open(os.path.join(d, gc.OUTFILE), encoding="utf-8").read())
check("keys are written sorted", list(written) == sorted(written),
      repr(list(written)))
check("every record keeps the documented field order",
      all(list(v) == ["lat", "lng", "provider", "precision", "formatted",
                      "fetched_at"] for v in written.values()),
      repr([list(v) for v in written.values()][:1]))
check("coordinates are rounded to 6 dp",
      all(v["lat"] == round(v["lat"], 6) and v["lng"] == round(v["lng"], 6)
          for v in written.values()))

# --------------------------------------------------- merge-side integration -
print("\n--- merge-side integration ---")


def arc(**kw):
    e = {"id": 0, "name": "", "addr": "", "lat": None, "lng": None,
         "country": "China", "pref": None, "notes": None}
    e.update(kw)
    return e


# The prefix exists so a floor label like this is answerable at all.
bare = arc(id=1, name="玩家来也", addr="全运路万达3F", pref="辽宁",
           notes="region: 辽宁省 沈阳市")
check("qualified_address prepends the missing province and city",
      gc.qualified_address(bare) == "辽宁沈阳市全运路万达3F",
      repr(gc.qualified_address(bare)))

full = arc(id=2, addr="河北省唐山市开平区中骏世界城二层", pref="河北",
           notes="region: 河北省 唐山市")
check("tokens already in the address are not repeated",
      gc.qualified_address(full) == "河北省唐山市开平区中骏世界城二层",
      repr(gc.qualified_address(full)))
check("an empty address yields nothing to ask",
      gc.qualified_address(arc(id=3, pref="河北")) == "")

# Harvesting runs on the finished arcades.json, where centroids are already in
# place; those rows are the whole point of the refresh.
rows = [arc(id=4, addr="全运路万达3F", pref="辽宁", lat=41.8, lng=123.4,
            approx=True, approx_level="city"),
        arc(id=5, addr="某路1号", pref="广东", lat=22.5, lng=114.0),
        arc(id=6, addr="1600 Azusa Ave", country="United States"),
        arc(id=7, addr="台北市南港區", pref="台湾")]
harvested = gc.addresses_for(rows)
check("approximate rows are harvested, real pins are not",
      harvested == ["辽宁全运路万达3F"], repr(harvested))

# apply_cache: only precise answers are taken.
cache = {
    gc.norm_addr("辽宁沈阳市全运路万达3F"): {
        "lat": 41.812, "lng": 123.435, "provider": "amap",
        "precision": "rooftop", "formatted": "", "fetched_at": "2026-07-28"},
    gc.norm_addr("广东某路2号"): {
        "lat": 23.1, "lng": 113.3, "provider": "amap",
        "precision": "area", "formatted": "", "fetched_at": "2026-07-28"},
}
a1 = arc(id=8, addr="全运路万达3F", pref="辽宁", notes="region: 辽宁省 沈阳市")
a2 = arc(id=9, addr="某路2号", pref="广东")
log = gc.apply_cache([a1, a2], cache=cache)
check("a rooftop hit places the entry", (a1["lat"], a1["lng"]) == (41.812, 123.435))
check("and is tagged as an address-level position",
      a1.get("approx") is True and a1.get("approx_level") == "address")
check("the note names the provider",
      "geocoded to address precision by amap" in a1["notes"], a1["notes"])
check("an area-precision answer is left to china_place",
      a2["lat"] is None and "approx" not in a2)
check("only the usable hit is logged", len(log) == 1 and log[0]["id"] == 8,
      repr(log))

a3 = arc(id=10, addr="全运路万达3F", pref="辽宁", notes="region: 辽宁省 沈阳市",
         lat=41.0, lng=123.0)
gc.apply_cache([a3], cache=cache)
check("a row that already has coordinates is never overwritten",
      (a3["lat"], a3["lng"]) == (41.0, 123.0))
check("an empty cache is a no-op", gc.apply_cache([arc(id=11)], cache={}) == [])

# ----------------------------------------------------------------- cleanup --
set_keys()
for tmp in TMPDIRS:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
if FAILED:
    print("FAILURES:")
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL PASS")
