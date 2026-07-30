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
import china_place
import cn_address
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
    """(fake_fetch_callable, calls_list). Answers by ?address= value.

    ``payloads`` is keyed by ADDRESS, but geocode_one asks about the parsed
    QUERY candidates, not the address verbatim: ``河北省唐山市开平区中骏世界城
    二层`` is asked as ``河北省唐山市开平区中骏世界城``. So an exact match is
    tried first and a candidate match second, which keeps every case below
    readable (keyed by the address the case is about) without pretending the
    module asks the question it does not ask.
    """
    calls = []
    by_candidate = {}
    for addr, payload in payloads.items():
        for cand in gc.candidates_for(addr):
            by_candidate.setdefault(cand, payload)

    def fake(url, *args, **kwargs):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        addr = (query.get("address") or query.get("wd") or [""])[0]
        calls.append(addr)
        if addr in payloads:
            return json.dumps(payloads[addr], ensure_ascii=False)
        if addr in by_candidate:
            return json.dumps(by_candidate[addr], ensure_ascii=False)
        raise AssertionError("fake fetch: no canned payload for %r" % addr)

    return fake, calls


def install(payloads):
    fake, calls = fake_fetch(payloads)
    gc.fetch = fake
    return calls


def amap_hit(lng, lat, level, formatted="河北省唐山市开平区 AMAP FORMATTED"):
    """AMap packs "lng,lat" into one string - longitude first, on purpose.

    The default formatted address names 唐山市 because every canned point in
    this file is in Tangshan and verify_area now requires the answer to name
    the city the address asked about. A real AMap formatted_address always
    opens with the province and city, so this is the realistic shape, not a
    concession to the test.
    """
    return {"status": "1", "info": "OK", "infocode": "10000", "count": "1",
            "geocodes": [{"formatted_address": formatted,
                          "location": "%.6f,%.6f" % (lng, lat),
                          "level": level}]}


AMAP_ZERO = {"status": "1", "info": "OK", "infocode": "10000",
             "count": "0", "geocodes": []}
AMAP_DENIED = {"status": "0", "info": "INVALID_USER_KEY",
               "infocode": "10001", "geocodes": []}


def google_hit(lat, lng, location_type,
               formatted="中国上海市黄浦区南京东路300号 GOOGLE FORMATTED"):
    """Same as amap_hit: the formatted address has to name the city, because
    that is the string verify_area checks the answer against."""
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


def arc(**kw):
    """One arcade row, shaped as merge hands it to this module."""
    e = {"id": 0, "name": "", "addr": "", "lat": None, "lng": None,
         "country": "China", "pref": None, "notes": None}
    e.update(kw)
    return e


# GCJ-02 points as the providers would return them.
TANGSHAN = (39.630000, 118.176000)      # amap case
SHANGHAI = (31.230416, 121.473701)      # google case
BEIJING = (39.920000, 116.437000)       # NFKC-folding case
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
          rec.get("formatted") == "河北省唐山市开平区 AMAP FORMATTED",
          repr(rec.get("formatted")))
    check("the query that produced the hit is recorded",
          rec.get("query") == "河北省唐山市开平区中骏世界城",
          repr(rec.get("query")))
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
      gc.resolve_provider("nosuchmap") == (None, None),
      repr(gc.resolve_provider("nosuchmap")))

print("\n--- the keyless provider is a real one, not an opt-out ---")
set_keys()      # no key anywhere
check("with no key at all, baidu is selected",
      gc.resolve_provider() == ("baidu", None), repr(gc.resolve_provider()))
check("--provider baidu needs no key",
      gc.resolve_provider("baidu") == ("baidu", None))
set_keys(amap="a")
check("a real key still wins over the keyless fallback",
      gc.resolve_provider()[0] == "amap", repr(gc.resolve_provider()))
check("baidu is in PROVIDERS and in KEYLESS",
      "baidu" in gc.PROVIDERS and "baidu" in gc.KEYLESS)
check("baidu needs no entry in ENV_KEYS", "baidu" not in gc.ENV_KEYS)
check("the keyless provider is asked politely by default",
      gc._DEFAULT_SLEEP["baidu"] >= 0.3, repr(gc._DEFAULT_SLEEP))
check("map.baidu.com Referer is sent (the endpoint 200s without it, but "
      "answers with no POIs at all)",
      gc.BAIDU_HEADERS.get("Referer") == "https://map.baidu.com/",
      repr(gc.BAIDU_HEADERS))
check("gzip is NOT requested (urllib does not decompress and common.fetch "
      "decodes as utf-8, so every body would become mojibake)",
      "Accept-Encoding" not in gc.BAIDU_HEADERS, repr(gc.BAIDU_HEADERS))
url = gc._baidu_url("测试")
check("the query goes in wd=, percent-encoded", "wd=%E6%B5%8B%E8%AF%95" in url,
      url)
check("fromproduct=jsapi and res=api select the JSON API response",
      "fromproduct=jsapi" in url and "res=api" in url, url)
check("no key is interpolated into the keyless URL",
      "key=" not in url and "ak=" not in url, url)

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
cache = gc.run(sorted(payloads), out_dir=d, verify=False)
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
cache = gc.run(sorted(payloads), out_dir=d, verify=False)
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
cache = gc.run(["SINGAPORE"], out_dir=d, verify=False)
check("out-of-box amap result is cached as a miss",
      bool(cache.get("SINGAPORE", {}).get("miss")), repr(cache.get("SINGAPORE")))
check("out-of-box result never becomes a pin",
      gc.lookup(cache, "SINGAPORE") is None)

set_keys(google="testkey")
d = fresh_dir()
TOKYO = (35.680000, 139.760000)     # outside eviltransform's box: no conversion
calls = install({"TOKYO": google_hit(TOKYO[0], TOKYO[1], "ROOFTOP")})
cache = gc.run(["TOKYO"], out_dir=d, verify=False)
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
cache = gc.run(THREE, out_dir=d, limit=1, verify=False)
check("limit=1 makes exactly one request", len(calls) == 1, repr(calls))
check("limit=1 caches exactly one entry", len(cache) == 1, repr(sorted(cache)))
check("the capped addresses are untouched",
      all(a not in cache for a in THREE[1:]), repr(sorted(cache)))
check("the one geocoded address resolves",
      gc.lookup(cache, calls[0]) is not None)

calls = install(payloads)
cache = gc.run(THREE, out_dir=d, limit=1, verify=False)
check("the next run picks up where it stopped (one more request)",
      len(calls) == 1, repr(calls))
check("cache has grown to two entries", len(cache) == 2, repr(sorted(cache)))

calls = install(payloads)
cache = gc.run(THREE, out_dir=d, verify=False)
check("an uncapped run finishes the rest", len(calls) == 1, repr(calls))
check("all three are cached now", len(cache) == 3, repr(sorted(cache)))
check("limit=0 geocodes nothing",
      len(install(payloads)) == 0 and
      len(gc.run(["L4"], out_dir=d, limit=0, verify=False)) == 3)

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
# Upstream Chinese addresses really do contain en/em dashes in their in-mall
# unit codes (U+2013 / U+2014). They fold to ASCII hyphens for two reasons
# common.unescape folds them on every other feed: the cache is committed and
# the repo is ASCII-punctuation only, and a source that prints "1-3" one week
# and a dashed spelling the next would otherwise be two entries that miss.
# Written as escapes, never as the literal characters, so this file obeys the
# same rule it is testing.
EN, EM = chr(0x2013), chr(0x2014)
check("an em dash in an address folds to a hyphen",
      gc.norm_addr("包头市吾悦广场S7" + EM + "236") == "包头市吾悦广场S7-236",
      repr(gc.norm_addr("包头市吾悦广场S7" + EM + "236")))
check("an en dash folds too",
      gc.norm_addr("儿童城1" + EN + "3层") == "儿童城1-3层",
      repr(gc.norm_addr("儿童城1" + EN + "3层")))
check("all three spellings share one cache entry",
      gc.norm_addr("A1" + EM + "2") == gc.norm_addr("A1-2")
      == gc.norm_addr("A1" + EN + "2"))
check("the committed cache is free of both (the repo's ASCII rule)",
      (not any(c in open(gc._DATA_PATH, encoding="utf-8").read()
               for c in (EN, EM)))
      if os.path.isfile(gc._DATA_PATH) else True)

set_keys(amap="testkey")
d = fresh_dir()
calls = install({gc.norm_addr(NARROW): amap_hit(
    BEIJING[1], BEIJING[0], "兴趣点", formatted="北京市朝阳区朝阳北路1号")})
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
print("\n--- the read side never touches the network, with or without a key ---")
# This is the property that keeps the weekly Action green. It used to fall out
# of "no key -> no provider"; a keyless provider removes that guarantee, so it
# has to be asserted directly: everything merge calls is a file read.
set_keys()      # neither AMAP_KEY nor GOOGLE_MAPS_API_KEY
d = fresh_dir()
seed = {"SEEDED": {"lat": 39.628684, "lng": 118.169710, "provider": "amap",
                   "precision": "rooftop", "formatted": "seed", "query": "",
                   "fetched_at": "2026-07-01"}}
seed_path = os.path.join(d, gc.OUTFILE)
with open(seed_path, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(seed, fh, ensure_ascii=False, indent=1)
before = open(seed_path, encoding="utf-8").read()


def exploding_fetch(*args, **kwargs):
    raise AssertionError("the read side must never fetch")


gc.fetch = exploding_fetch
loaded = gc.load_cache(seed_path)
check("load_cache fetches nothing", loaded == seed, repr(loaded))
check("lookup fetches nothing", gc.lookup(loaded, "SEEDED") is not None)
rows = [{"id": 1, "name": "", "addr": "SEEDED", "lat": None, "lng": None,
         "country": "China", "pref": None, "notes": None}]
gc.apply_cache(rows, cache=loaded)
check("apply_cache fetches nothing", rows[0]["lat"] == 39.628684,
      repr(rows[0]))
check("the read side did not rewrite the file",
      open(seed_path, encoding="utf-8").read() == before)
check("load_cache on a missing file is {}",
      gc.load_cache(os.path.join(fresh_dir(), "nope.json")) == {})

print("\n--- a run with nothing to ask about writes nothing ---")
calls = install({})
cache = gc.run([], out_dir=d)
check("an empty address list makes no request", len(calls) == 0, repr(calls))
check("and returns the committed cache unchanged", cache == seed, repr(cache))
check("and does not rewrite the file",
      open(seed_path, encoding="utf-8").read() == before)

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
    cache = gc.run(["OK1", "BAD", "AFTER"], out_dir=d, verify=False)
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
gc.run(KEYS, out_dir=d, verify=False)
written = json.loads(open(os.path.join(d, gc.OUTFILE), encoding="utf-8").read())
check("keys are written sorted", list(written) == sorted(written),
      repr(list(written)))
check("every record keeps the documented field order",
      all(tuple(v) == gc.HIT_FIELDS for v in written.values()),
      repr([list(v) for v in written.values()][:1]))
check("coordinates are rounded to 6 dp",
      all(v["lat"] == round(v["lat"], 6) and v["lng"] == round(v["lng"], 6)
          for v in written.values()))

# ================================================================ BD-09 =====
print("\n--- BD-09 Mercator -> WGS-84 (the two-step conversion) ---")
# Ground truth is OpenStreetMap, not memory: each pair below is the x/y this
# module's own Baidu client returned for that landmark, and the lat/lng of the
# corresponding OSM node. A one-step conversion (treating BD-09 as GCJ-02, or
# skipping the projection) misses by hundreds of metres to thousands of km, so
# this is the test that would catch either mistake.
BD_CASES = [
    ("东方明珠", 1352616322, 364230590, 31.2419464, 121.4952604),
    ("广州塔", 1261609486, 262865109, 23.1090145, 113.3191477),
    ("深圳北站", 1269453933, 256902669, 22.6120365, 114.0239469),
    ("朝阳大悦城", 1297169901, 482823063, 39.9235000, 116.5130000),
]
for label, x, y, olat, olng in BD_CASES:
    blat, blng = gc.bdmc2bd(x / 100.0, y / 100.0)
    wlat, wlng = gc.to_wgs(blat, blng, "baidu")
    off = metres(wlat, wlng, olat, olng)
    check("%s lands within 120 m of its OSM node" % label, off < 120.0,
          "%.5f,%.5f is %.0f m from %.5f,%.5f" % (wlat, wlng, off, olat, olng))
    check("%s: the BD-09 step was not skipped" % label,
          metres(blat, blng, olat, olng) > 200.0,
          "raw BD-09 is only %.0f m out, so the test proves nothing"
          % metres(blat, blng, olat, olng))

x, y = 1267877300 / 100.0, 256218563 / 100.0
lat, lng = gc.bdmc2bd(x, y)
check("bdmc2bd returns (lat, lng), not (lng, lat) - a swap puts Shenzhen in "
      "the Atlantic", 20.0 < lat < 25.0 and 110.0 < lng < 118.0,
      "%.5f,%.5f" % (lat, lng))
check("to_wgs routes baidu through bd2wgs, not gcj2wgs",
      gc.to_wgs(lat, lng, "baidu") == eviltransform.bd2wgs(lat, lng))
check("to_wgs routes amap through gcj2wgs",
      gc.to_wgs(*TANGSHAN, "amap") == eviltransform.gcj2wgs(*TANGSHAN))
check("to_wgs routes google through gcj2wgs",
      gc.to_wgs(*SHANGHAI, "google") == eviltransform.gcj2wgs(*SHANGHAI))
check("haversine_km agrees with the test's own metres()",
      abs(gc.haversine_km(39.9, 116.4, 31.2, 121.5) * 1000.0
          - metres(39.9, 116.4, 31.2, 121.5)) < 2000.0)

# ========================================================== baidu parsing ====
print("\n--- baidu response shapes ---")


def poi(name, addr, x, y, di_tag="购物 购物中心", area="深圳市宝安区"):
    return {"name": name, "addr": addr, "x": x, "y": y, "di_tag": di_tag,
            "area_name": area}


SZ_X, SZ_Y = 1267877300, 256218563

# Shape 1: a normal POI list.
body = json.dumps({"content": [poi("深圳前海壹方城", "新湖路99号", SZ_X, SZ_Y)]},
                  ensure_ascii=False)
parsed = gc._parse_baidu(body)
check("a POI list parses", parsed is not None, repr(parsed))
if parsed:
    check("precision of a shop POI is poi", parsed[2] == "poi", repr(parsed[2]))
    check("name, addr and area_name are all folded into `formatted` (the "
          "area_name is what verify_area reads)",
          "深圳前海壹方城" in parsed[3] and "新湖路99号" in parsed[3]
          and "深圳市宝安区" in parsed[3], repr(parsed[3]))

# Shape 2: content is a DICT. This is the "you searched for an administrative
# area" jump, and its x/y is the district centroid - the exact thing this
# module exists to replace, so accepting it would be a silent regression.
body = json.dumps({"content": {"x": SZ_X, "y": SZ_Y, "code": 2617,
                               "level": 13}}, ensure_ascii=False)
check("content-as-a-dict yields no items", gc._baidu_items(body) == [])
check("content-as-a-dict is a miss, not a district centroid",
      gc._parse_baidu(body) is None)

# Shape 3: a list of CITY SUGGESTIONS. Different keys entirely, and no x/y:
# this is what a road name that exists in eleven cities comes back as.
body = json.dumps({"content": [{"name": "洛阳市", "code": 1, "num": 3},
                               {"name": "上海市", "code": 2, "num": 1}]},
                  ensure_ascii=False)
check("city suggestions yield no items", gc._baidu_items(body) == [])
check("city suggestions are a miss", gc._parse_baidu(body) is None)

check("a missing content key is a miss",
      gc._baidu_items(json.dumps({"result": {"error": 0}})) == [])
try:
    gc._baidu_items("[1,2,3]")
    raised = None
except Exception as exc:                       # noqa: BLE001
    raised = exc
check("a non-object body is a provider error, not a miss - a miss would be "
      "cached forever and never retried",
      isinstance(raised, gc.GeocodeError), repr(raised))

print("\n--- baidu POI selection: doors and car parks are not the building ---")
body = json.dumps({"content": [
    poi("万达广场-1号门", "全运路", 1374425727, 508607797, di_tag="出入口 门"),
    poi("万达广场-地下停车场", "全运路", 1374441779, 508612478,
        di_tag="交通设施 停车场 地下停车场"),
    poi("万达广场(沈阳全运店)", "全运路", 1374439474, 508613490,
        di_tag="购物 购物中心"),
]}, ensure_ascii=False)
parsed = gc._parse_baidu(body)
check("the gate/car-park rows are skipped and the mall itself is taken",
      parsed is not None and "沈阳全运店" in parsed[3], repr(parsed))

# The 街道办事处 case: a real substitution error, where the administrative half
# of the address matched better than the building did. Its coordinate is a
# district office, kilometres from the mall - a centroid wearing a POI badge.
body = json.dumps({"content": [
    poi("云南省临沧市临翔区凤翔街道办事处章嘎社区", "沧江东路", 1114000000,
        274000000, di_tag="政府机构", area="临沧市临翔区"),
    poi("强力广场", "汀旗路", 1114100000, 274100000, di_tag="购物 商业街",
        area="临沧市临翔区"),
]}, ensure_ascii=False)
parsed = gc._parse_baidu(body)
check("a 政府机构 answer is skipped in favour of the real POI below it",
      parsed is not None and "强力广场" in parsed[3], repr(parsed))

print("\n--- baidu precision tiers ---")
check("a shop tag is poi precision", gc._baidu_precision("购物 购物中心") == "poi")
check("a road tag is street precision", gc._baidu_precision("道路") == "street")
check("an untagged POI is still poi precision", gc._baidu_precision("") == "poi")
for tag in ("出入口 门", "交通设施 停车场", "行政地标", "政府机构"):
    check("%s is refused outright" % tag, gc._baidu_precision(tag) is None)

# A building anywhere in the list beats a road at the top of it, but a road
# beats nothing: an address whose only answer is its road is street precision,
# which the panel renders as "a door or two out" rather than as an address.
body = json.dumps({"content": [
    poi("新湖路", "广东省深圳市宝安区", SZ_X, SZ_Y, di_tag="道路"),
    poi("深圳前海壹方城", "新湖路99号", SZ_X + 500, SZ_Y, di_tag="购物 购物中心"),
]}, ensure_ascii=False)
parsed = gc._parse_baidu(body)
check("a building further down beats a road at the top",
      parsed is not None and parsed[2] == "poi", repr(parsed))
body = json.dumps({"content": [
    poi("新湖路", "广东省深圳市宝安区", SZ_X, SZ_Y, di_tag="道路")]},
    ensure_ascii=False)
parsed = gc._parse_baidu(body)
check("a road alone is taken, at street precision",
      parsed is not None and parsed[2] == "street", repr(parsed))

check("poi precision becomes approx_level 'address'",
      gc.USABLE_PRECISION.get("poi") == "address")
check("every approx_level this module emits is one js/panel.js knows "
      "(address/street/district/city) - an unknown one silently renders as "
      "'the centre of the city'",
      set(gc.USABLE_PRECISION.values()) <= {"address", "street"},
      repr(sorted(set(gc.USABLE_PRECISION.values()))))
check("an 'area' answer is still refused: it is a centroid without a level",
      "area" not in gc.USABLE_PRECISION)

# ======================================================= address parsing =====
print("\n--- strip_noise: the interior-of-a-building tail comes off ---")
NOISE_CASES = [
    ("朝阳区朝阳北路101号朝阳大悦城8F金逸影城旁", "8F", "the floor and the "
     "neighbouring tenant"),
    ("湖景东路9号新奥购物中心B1层H1-01", "H1-01", "the hyphenated unit code"),
    ("南州镇步步高桂花广场三楼f3015号铺", "f3015", "the shop number"),
    ("新华西街58号万达广场(通州店)3F东侧", "东侧", "which side of the building"),
    ("西大望路21号北京朝阳合生汇B1层21街区东侧", "21街区", "the in-mall block"),
    ("广东省深圳市宝安区新湖路99号壹方城3楼B1-023电梯口", "电梯口",
     "next to the lift"),
    ("政和路，详细地址请加群123456", "详细地址", "a withheld address"),
    ("步步高桂花广场三楼f3015号铺7484&爱巴爱麻电玩城", "&", "the trailing "
     "shop name after an ampersand"),
]
for raw, gone, why in NOISE_CASES:
    out = cn_address.strip_noise(raw)
    check("strip_noise removes %s" % why, gone not in out,
          "%r -> %r" % (raw, out))

check("a BUILDING number is not mistaken for a floor and deleted",
      "18号楼" in cn_address.strip_noise("和平路18号楼"),
      repr(cn_address.strip_noise("和平路18号楼")))
check("a road number survives (it is the only thing separating two malls on "
      "one street)",
      "99号" in cn_address.strip_noise("新湖路99号壹方城3楼"),
      repr(cn_address.strip_noise("新湖路99号壹方城3楼")))
check("strip_noise('') is ''", cn_address.strip_noise("") == "")
check("strip_noise(None) is ''", cn_address.strip_noise(None) == "")

print("\n--- find_landmark: the mall is the part a POI index knows ---")
LANDMARKS = [
    ("怀仁市新天地购物广场5楼", "新天地购物广场"),
    ("黄河西路与开元南大道交叉口荣盛国际购物广场F2", "荣盛国际购物广场"),
    ("天长西路54号苏宁广场负一层", "苏宁广场"),
    ("朝阳区朝阳北路101号朝阳大悦城", "朝阳大悦城"),
]
for raw, want in LANDMARKS:
    got = cn_address.find_landmark(cn_address.strip_noise(raw))
    check("landmark of %s" % raw[:18], got == want, repr(got))

check("a longer suffix wins, so 购物中心 is never truncated to 中心",
      (cn_address.find_landmark("湖景东路9号新奥购物中心") or "")
      .endswith("购物中心"),
      repr(cn_address.find_landmark("湖景东路9号新奥购物中心")))
check("the walk-back does not cross 市, so a mall named ...城市广场 survives",
      cn_address.find_landmark("SM滨海城市广场") == "SM滨海城市广场",
      repr(cn_address.find_landmark("SM滨海城市广场")))
check("but a genuine leading city token IS trimmed",
      cn_address.trim_admin("怀仁市新天地购物广场") == "新天地购物广场",
      repr(cn_address.trim_admin("怀仁市新天地购物广场")))
check("trim_admin will not trim a name down to nothing",
      cn_address.trim_admin("城市广场") == "城市广场",
      repr(cn_address.trim_admin("城市广场")))
for junk in ("电玩城", "购物中心", "县城", "城区", "广场"):
    check("%r is refused as a landmark (it names no building)" % junk,
          cn_address.find_landmark("某某路1号" + junk) != junk,
          repr(cn_address.find_landmark("某某路1号" + junk)))

print("\n--- find_road / name_landmark ---")
check("a numbered road is read whole",
      cn_address.find_road("朝阳区朝阳北路101号朝阳大悦城") == ("朝阳北路", "101"),
      repr(cn_address.find_road("朝阳区朝阳北路101号朝阳大悦城")))
check("桥北街道 is a SUBDISTRICT, not a road called 桥北街",
      cn_address.find_road("赤峰市红山区桥北街道众联时代城")[0] != "桥北街",
      repr(cn_address.find_road("赤峰市红山区桥北街道众联时代城")))
check("a crossroads does not yield the road '与开元南大道'",
      not (cn_address.find_road("黄河西路与开元南大道交叉口")[0] or "")
      .startswith("与"),
      repr(cn_address.find_road("黄河西路与开元南大道交叉口")))
check("the venue NAME names the mall its address never mentions",
      cn_address.name_landmark("环游嘉年华（北京朝阳大悦城店）") == "北京朝阳大悦城",
      repr(cn_address.name_landmark("环游嘉年华（北京朝阳大悦城店）")))
check("a bracket-free name works too",
      cn_address.name_landmark("尖峰玩家佛山南海万达店") is not None,
      repr(cn_address.name_landmark("尖峰玩家佛山南海万达店")))
check("a name with no mall in it yields nothing",
      cn_address.name_landmark("1-7PLAY") is None,
      repr(cn_address.name_landmark("1-7PLAY")))

print("\n--- candidates: progressively coarser, never a bare mall name ---")
cands = cn_address.candidates("朝阳区朝阳北路101号朝阳大悦城8F金逸影城旁",
                              city="北京市", district="朝阳区",
                              name="环游嘉年华（北京朝阳大悦城店）")
check("the full cleaned address leads", cands and "101号" in cands[0],
      repr(cands[:1]))
check("the floor and the tenant are gone from every candidate",
      all("8F" not in c and "金逸影城" not in c for c in cands), repr(cands))
check("every candidate names the city, so verify_area has something to check "
      "and a bare 万达广场 cannot resolve to another province",
      all("北京" in c for c in cands), repr(cands))
check("the mall-only rung exists", any(c.endswith("朝阳大悦城") for c in cands),
      repr(cands))
check("candidates are unique", len(cands) == len(set(cands)), repr(cands))
check("an address with nothing in it yields nothing",
      cn_address.candidates("") == [])
check("the city is not repeated when the address already names it",
      all(c.count("深圳市") <= 1 for c in
          cn_address.candidates("广东省深圳市宝安区新湖路99号壹方城3楼",
                                city="深圳市", province="广东省")),
      repr(cn_address.candidates("广东省深圳市宝安区新湖路99号壹方城3楼",
                                 city="深圳市", province="广东省")))

# ==================================================== the verification gate ==
print("\n--- verify_area: the answer must be in the city the address named ---")
SZ = eviltransform.gcj2wgs(22.55, 113.88)
ok, why = gc.verify_area("广东省深圳市宝安区新湖路99号壹方城", SZ[0], SZ[1],
                         "深圳前海壹方城 新湖路99号 深圳市宝安区")
check("the right city in the right place passes", ok, why)

ok, why = gc.verify_area("广东省深圳市宝安区新湖路99号壹方城", SZ[0], SZ[1],
                         "壹方城 长沙市岳麓区")
check("a same-named mall in another city is rejected", not ok, why)
check("and the rejection says which city it landed in", "长沙" in why, why)

# The distance backstop, for the case the name check cannot see: two real
# districts share a name (朝阳区 exists in Beijing AND in Changchun), so the
# formatted address agrees while the coordinate is 900 km away.
ok, why = gc.verify_area("北京市朝阳区朝阳北路101号", 43.87, 125.32,
                         "某某商场 北京市朝阳区")
check("a hit far outside the named city is rejected on distance", not ok, why)
check("and the rejection says how far", "km" in why, why)

check("a prefecture-level city is not treated as a town: a hit 60 km from "
      "the centroid of 重庆市 still passes",
      gc.verify_area("重庆市南岸区江南大道8号", 29.0, 106.9,
                     "某某广场 重庆市南岸区")[0],
      gc.verify_area("重庆市南岸区江南大道8号", 29.0, 106.9,
                     "某某广场 重庆市南岸区")[1])

# The radius is measured per area, not fixed, because one constant cannot fit
# both ends of this table. Chongqing's own counties are 350 km from its centre
# while a coastal prefecture is 30 km across, so a constant loose enough for
# the first waves through a pin in the next province.
idx = china_place.load_areas()
cq = idx.province_by_base["重庆"]
sz = [a for a, v in idx.areas.items()
      if v["d"] == 1 and china_place.cn_base(v["n"]) == "深圳"][0]
xj = idx.province_by_base["新疆"]
check("重庆's measured radius is much larger than 深圳's",
      gc.area_radius_km(cq, idx) > gc.area_radius_km(sz, idx) * 2,
      "重庆 %.0f km vs 深圳 %.0f km"
      % (gc.area_radius_km(cq, idx), gc.area_radius_km(sz, idx)))
check("no area is given a hair-trigger radius",
      gc.area_radius_km(sz, idx) >= gc.MIN_RADIUS_KM,
      "%.0f km" % gc.area_radius_km(sz, idx))
check("even 新疆 is capped, so a province check still rejects something",
      gc.area_radius_km(xj, idx) <= gc.MAX_RADIUS_KM,
      "%.0f km" % gc.area_radius_km(xj, idx))
check("巫山县, a real Chongqing county 350 km out, is NOT rejected",
      gc.verify_area("重庆市巫山县广东路", 31.07, 109.88, "某某广场")[0],
      gc.verify_area("重庆市巫山县广东路", 31.07, 109.88, "某某广场")[1])
check("but Lhasa is still rejected as an answer to a Chongqing question",
      not gc.verify_area("重庆市南岸区向黄路", 29.65, 91.13, "某某广场")[0],
      gc.verify_area("重庆市南岸区向黄路", 29.65, 91.13, "某某广场")[1])

ok, why = gc.verify_area("某某路1号", SZ[0], SZ[1], "某某广场 深圳市宝安区")
check("an address naming no city cannot be verified, and unverifiable is "
      "refused rather than trusted", not ok, why)

print("\n--- reading a province written without its 省/市 suffix ---")
# qualified_address prepends the BASE form (北京, 河北), not the official one,
# so requiring 北京市 would leave a large slice of the corpus unverifiable -
# and unverifiable is refused, so those addresses would silently lose their
# pins.
for text, want in [("北京朝阳区常营地区常通路1号", ("北京", "北京")),
                   ("河北任丘万达广场", ("河北", None)),
                   ("广东佛山顺德区大信新都汇", ("广东", "佛山")),
                   ("内蒙古通辽市奈曼旗", ("内蒙古", "通辽")),
                   ("重庆重庆郊县万达广场", ("重庆", "重庆郊县"))]:
    check("%s reads as %s" % (text[:14], want),
          gc._admin_tokens(text) == want, repr(gc._admin_tokens(text)))

# But a leading province token is only believed when something under it is
# named next, because plenty of Chinese chains are named after a city they
# are not in. 北京华联 is a nationwide supermarket, so a correct Lanzhou pin
# would otherwise be discarded as "in Beijing".
LANZHOU = "北京华联东方红购物中心 兰州市城关区南昌路982号 兰州市城关区"
check("北京华联 in a Lanzhou address is a BRAND, not a province",
      gc._admin_tokens(LANZHOU) == (None, "兰州"),
      repr(gc._admin_tokens(LANZHOU)))
check("and the Lanzhou answer therefore verifies",
      gc.verify_area("甘肃省兰州市城关区南昌路982号北京华联兰州购物中心",
                     36.056362, 103.842843, LANZHOU)[0],
      gc.verify_area("甘肃省兰州市城关区南昌路982号北京华联兰州购物中心",
                     36.056362, 103.842843, LANZHOU)[1])
# The short form mid-string stays refused: these are all real road names.
for text, want in [("江苏省南京市上海路100号", ("江苏", "南京")),
                   ("河南省郑州市河北大街1号", ("河南", "郑州"))]:
    check("a road called %s is not read as a province"
          % text.split("市")[-1][:4],
          gc._admin_tokens(text) == want, repr(gc._admin_tokens(text)))

print("\n--- the mainland box, and what it deliberately does NOT do ---")
check("Shenzhen is inside the box", gc.in_mainland(22.55, 113.88))
check("Harbin is inside the box", gc.in_mainland(45.75, 126.64))
check("Urumqi is inside the box", gc.in_mainland(43.83, 87.62))
check("Singapore is outside", not gc.in_mainland(1.35, 103.8))
check("Tokyo is outside", not gc.in_mainland(35.68, 139.76))
check("None coordinates are outside", not gc.in_mainland(None, None))

# The box is a RECTANGLE, so it necessarily swallows the neighbours: Seoul,
# Pyongyang, Hanoi and Vladivostok are all inside it, and so are Taipei, Hong
# Kong and Macau. This is asserted rather than fixed, because the box is a
# garbage filter ("did the geocoder hand back a point on another continent")
# and NOT a jurisdiction filter. Anyone who later reads it as one will ship a
# datum bug: gcj2wgs does not apply cleanly outside the mainland, so a correct
# Hong Kong answer would be shifted a few hundred metres and still pass.
for label, lat, lng in [("Seoul", 37.57, 126.98), ("Hanoi", 21.03, 105.85),
                        ("Vladivostok", 43.1, 131.9), ("Taipei", 25.03, 121.57),
                        ("Hong Kong", 22.32, 114.17), ("Macau", 22.20, 113.54)]:
    check("%s is INSIDE the box - the box is not a country filter" % label,
          gc.in_mainland(lat, lng))

# What actually stops them is verify_area, which is why it is not optional.
ok, why = gc.verify_area("广东省深圳市宝安区新湖路99号壹方城", 37.57, 126.98,
                         "Some Mall Seoul")
check("verify_area is what rejects a Seoul answer, not the box", not ok, why)
ok, why = gc.verify_area("广东省深圳市宝安区新湖路99号壹方城", 25.03, 121.57,
                         "台北101 台北市信义区")
check("verify_area rejects a Taipei answer to a Shenzhen question", not ok, why)

print("\n--- Taiwan / Hong Kong / Macau are excluded by the CALLER ---")
# All three already carry real street-level pins from ALL.Net / e-amusement /
# ZIv. Approximating them gains nothing and the GCJ-02 offset is not even
# correct outside the mainland, so a "fixed" Hong Kong pin would be a few
# hundred metres worse than the one it replaced.
territories = [
    arc(id=20, addr="台北市南港區忠孝東路", pref="台湾", country="China"),
    arc(id=21, addr="台北市信义区", country="Taiwan"),
    arc(id=22, addr="旺角彌敦道", country="Hong Kong"),
    arc(id=23, addr="澳門新馬路", country="Macau"),
]
harvested = gc.addresses_for(territories)
check("no Taiwan/HK/Macau row is harvested for geocoding", harvested == [],
      repr(harvested))
for e in territories:
    check("id %d is left alone by addresses_for" % e["id"],
          e["lat"] is None and "approx" not in e, repr(e))

# And the read side refuses them too, so a hand-added cache row cannot place
# one by the back door.
tw_cache = {gc.norm_addr("台北市信义区"): {
    "lat": 25.033, "lng": 121.565, "provider": "baidu", "precision": "poi",
    "formatted": "台北101 台北市信义区", "query": "", "fetched_at": "2026-07-30"}}
tw_rows = [arc(id=24, addr="台北市信义区", country="Taiwan"),
           arc(id=25, addr="台北市信义区", pref="台湾")]
tw_log = gc.apply_cache(tw_rows, cache=tw_cache)
check("apply_cache refuses a Taiwan row even with a cache hit sitting there",
      tw_log == [] and all(r["lat"] is None for r in tw_rows), repr(tw_rows))
hk_rows = [arc(id=26, addr="旺角彌敦道", country="Hong Kong"),
           arc(id=27, addr="澳門新馬路", country="Macau")]
hk_cache = {gc.norm_addr("旺角彌敦道"): {
    "lat": 22.319, "lng": 114.169, "provider": "baidu", "precision": "poi",
    "formatted": "旺角 香港", "query": "", "fetched_at": "2026-07-30"},
    gc.norm_addr("澳門新馬路"): {
    "lat": 22.194, "lng": 113.539, "provider": "baidu", "precision": "poi",
    "formatted": "新馬路 澳門", "query": "", "fetched_at": "2026-07-30"}}
check("apply_cache refuses Hong Kong and Macau rows too (not in "
      "PLACEABLE_COUNTRIES)",
      gc.apply_cache(hk_rows, cache=hk_cache) == []
      and all(r["lat"] is None for r in hk_rows), repr(hk_rows))

# ============================================ rate-limit / abort behaviour ===
print("\n--- a wall of empty answers stops the run instead of poisoning it ---")
# A cached miss is never retried. So if the endpoint starts answering
# everything with nothing, writing those as misses would permanently kill
# thousands of rows - the single worst thing this module could do.
set_keys()      # keyless: baidu
d = fresh_dir()
EMPTY = json.dumps({"content": {}}, ensure_ascii=False)
WALL = ["广东省深圳市宝安区新湖路%d号壹方城" % i
        for i in range(gc.MISS_STREAK_ABORT + 30)]
calls = []


def wall_fetch(url, *args, **kwargs):
    calls.append(url)
    return EMPTY


gc.fetch = wall_fetch
cache = gc.run(WALL, out_dir=d, sleep=0.0)
check("the run aborts on a long streak of empty answers",
      len(cache) < len(WALL), "cached %d of %d" % (len(cache), len(WALL)))
check("it aborts at roughly MISS_STREAK_ABORT, not after the whole corpus",
      len(cache) <= gc.MISS_STREAK_ABORT + 1,
      "cached %d, abort threshold %d" % (len(cache), gc.MISS_STREAK_ABORT))

print("\n--- but genuine misses and rejections do NOT trip the abort ---")
d = fresh_dir()
state = {"n": 0}


def mixed_fetch(url, *args, **kwargs):
    """Alternates a real hit with an empty answer, forever."""
    state["n"] += 1
    if state["n"] % 2:
        return json.dumps({"content": [poi("壹方城", "新湖路99号", SZ_X, SZ_Y)]},
                          ensure_ascii=False)
    return EMPTY


gc.fetch = mixed_fetch
cache = gc.run(WALL[:20], out_dir=d, sleep=0.0)
check("scattered misses never trip the abort", len(cache) == 20,
      "cached %d of 20" % len(cache))

print("\n--- the cache is written incrementally, so a crash resumes ---")
d = fresh_dir()
path = os.path.join(d, gc.OUTFILE)
seen = {"n": 0}


def crashing_fetch(url, *args, **kwargs):
    seen["n"] += 1
    if seen["n"] > gc.FLUSH_EVERY + 3:
        raise gc.GeocodeError("simulated network death")
    return json.dumps({"content": [poi("壹方城", "新湖路99号", SZ_X, SZ_Y)]},
                      ensure_ascii=False)


gc.fetch = crashing_fetch
gc.run(WALL[:gc.FLUSH_EVERY * 3], out_dir=d, sleep=0.0)
check("the work done before the crash is on disk", os.path.isfile(path), path)
on_disk = gc.load_cache(path)
check("and it is at least one full flush", len(on_disk) >= gc.FLUSH_EVERY,
      "%d entries, flush every %d" % (len(on_disk), gc.FLUSH_EVERY))
check("a resumed run only asks about what is missing",
      all(k not in on_disk for k in WALL[len(on_disk) + 5:]),
      "%d of %d cached" % (len(on_disk), gc.FLUSH_EVERY * 3))
check("no .tmp file is left behind by the atomic flush",
      not os.path.isfile(path + ".tmp"), path + ".tmp")
check("the flushed file is complete JSON, not a truncated one - a corrupt "
      "file reads as {} and would silently discard the whole run",
      json.loads(open(path, encoding="utf-8").read()) == on_disk)

print("\n--- a locked cache file does not kill the run ---")
# Observed live on Windows: os.replace raises PermissionError [WinError 5]
# when a virus scanner or indexer holds the destination for a moment, and it
# killed a refresh at record 250 of 2,436. A checkpoint that can destroy the
# run it exists to protect is worse than no checkpoint.
d = fresh_dir()
path = os.path.join(d, gc.OUTFILE)
real_replace = os.replace
attempts = {"n": 0}


def flaky_replace(src, dst, *args, **kwargs):
    attempts["n"] += 1
    raise PermissionError(5, "Access is denied")


gc.fetch = mixed_fetch
os.replace = flaky_replace
try:
    cache = gc.run(WALL[:gc.FLUSH_EVERY * 2], out_dir=d, sleep=0.0)
    raised = None
except Exception as exc:                       # noqa: BLE001
    cache, raised = None, exc
finally:
    os.replace = real_replace
check("a locked destination does not raise into the caller", raised is None,
      repr(raised))
check("the replace was retried, not abandoned on the first failure",
      attempts["n"] > 1, "%d attempts" % attempts["n"])
if cache is not None:
    check("every answer is still in the returned cache, so nothing paid for "
          "is lost", len(cache) == gc.FLUSH_EVERY * 2, "%d entries"
          % len(cache))
os.replace = real_replace

# --------------------------------------------------- merge-side integration -
print("\n--- merge-side integration ---")

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

# merge re-runs on top of the previous arcades.json, so the row arrives with
# LAST build's centroid note already on it. Leaving that in place makes the
# entry claim both "the middle of Shenyang" and "the address" at once, and
# js/panel.js will show the reader whichever it happens to find.
stale = arc(id=12, addr="全运路万达3F", pref="辽宁",
            notes="region: 辽宁省 沈阳市 | position approximate: city "
                  "centroid (沈阳市)")
gc.apply_cache([stale], cache=cache)
check("the superseded centroid note is removed, not appended to",
      "position approximate:" not in stale["notes"], stale["notes"])
check("the new note is there", "geocoded to address precision" in
      stale["notes"], stale["notes"])
check("unrelated notes survive", "region: 辽宁省 沈阳市" in stale["notes"],
      stale["notes"])
check("applying twice does not duplicate the note",
      stale["notes"].count("geocoded to address precision") == 1,
      stale["notes"])

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
