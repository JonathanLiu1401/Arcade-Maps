"""Unit tests for scrapers/china_place.py (fabricated entries).

Run: python scrapers/test_china_place.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import china_place as cp

# Test labels contain Chinese city names. On Windows the default console
# encoding is cp1252, so printing them raises UnicodeEncodeError and the
# suite dies on the first Chinese label rather than on a real failure.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):   # pragma: no cover - non-reconfigurable
    pass

FAILED = []


def check(label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print("%s  %s%s" % (status, label, ("  <- " + detail) if detail else ""))
    if not cond:
        FAILED.append(label)


def haversine_m(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dp = p2 - p1
    dl = math.radians(lo2 - lo1)
    h = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


cities = cp.load_cities()
print("loaded %d china_cities keys\n" % len(cities))

# ------------------------------------------------------------ table sanity -
unmapped, stale = cp.verify_table()
check("province table covers every china_cities key",
      not unmapped and not stale,
      "unmapped=%s stale=%s" % (unmapped[:5], stale[:5]))

# --------------------------------------------------- 1. hit by region note -
e = {"id": 1, "name": "1-7PLAY(西美花街店)", "addr": "红旗大街西美花街生活工场4楼",
     "lat": None, "lng": None, "country": "China", "pref": "河北",
     "notes": "other games: 头文字D; region: 河北省 石家庄市"}
hit = cp.place_approx(e)
check("1. region note -> 石家庄市", hit is not None and hit[2] == "石家庄市",
      repr(hit))
check("1. centroid matches table",
      hit is not None and [hit[0], hit[1]] == cities["石家庄市"], repr(hit))

# region note where geo_validate already appended a pipe-separated note:
# the regex must stop at "|" and not swallow the rest.
e_pipe = dict(e, notes="region: 河北省 沧州市 | bemanicn addr: 运河区黄河西路")
hit_pipe = cp.place_approx(e_pipe)
check("1b. region regex stops at '|'",
      hit_pipe is not None and hit_pipe[2] == "沧州市", repr(hit_pipe))

# --------------------------------------------------- 2. hit by address only -
e2 = {"id": 2, "name": "1-7PLAY唐山世界城店",
      "addr": "河北省唐山市开平区中骏世界城二层1-7PLAY家庭娱乐中心",
      "lat": None, "lng": None, "country": "China", "pref": "河北",
      "notes": None}
hit2 = cp.place_approx(e2)
check("2. address -> 唐山市", hit2 is not None and hit2[2] == "唐山市",
      repr(hit2))

# pref carrying the 省 suffix / 中国 prefix must still normalize.
e2b = dict(e2, pref="中国河北省")
check("2b. pref '中国河北省' normalizes to 河北",
      cp.entry_province(e2b) == "河北", cp.entry_province(e2b))
check("2b. still resolves with messy pref",
      (cp.place_approx(e2b) or (None, None, None))[2] == "唐山市")

# ----------------------------------------------------------- 3. Taiwan skip -
e3 = {"id": 3, "name": "GiGO - Global Mall 南港車站店",
      "addr": "忠孝東路七段371號B1AF", "lat": None, "lng": None,
      "country": "China", "pref": "台湾",
      "notes": "region: 台湾省 台北市"}
check("3. Taiwan pref skipped", cp.place_approx(e3) is None,
      repr(cp.place_approx(e3)))

e3b = {"id": 31, "name": "某店", "addr": "台中市北屯路二段100號中山路口",
       "lat": None, "lng": None, "country": "Taiwan", "pref": None,
       "notes": None}
naive = cp._scan(e3b["addr"], None, cities)
check("3b. Taiwan country skipped (naive scan would have hit %s)" % naive,
      cp.place_approx(e3b) is None, repr(cp.place_approx(e3b)))
check("3b. naive scan really would have mis-placed it",
      naive in ("中山路", "北屯", "台中", "中山"), repr(naive))

# ------------------------------------------- 4. province-conflict rejection -
# 中山中路 is a street in 定州, 河北. The bare longest-substring match hits
# 中山 (a city in 广东); the guard must reject it.
e4 = {"id": 4, "name": "小洋人宝贝王定州南城店",
      "addr": "河北省定州市南城区中山中路时代广场三楼小洋人宝贝王",
      "lat": None, "lng": None, "country": "China", "pref": "河北",
      "notes": None}
naive4 = cp._scan(e4["addr"], None, cities)
check("4. unguarded scan hits 中山 (广东)", naive4 == "中山", repr(naive4))
check("4. guard rejects the cross-province hit",
      cp.place_approx(e4) is None, repr(cp.place_approx(e4)))
check("4. _province_ok(中山, 河北) is False",
      cp._province_ok("中山", "河北") is False)

# Guard must RESCUE (not just reject) when a compatible key is also present:
# 和平区 (天津) appears first by length but 沈阳市 is province-consistent.
e4b = {"id": 41, "name": "玩计划沈阳和平K11店",
       "addr": "辽宁省沈阳市和平区博览路2甲1号K11购物艺术中心2楼玩计划",
       "lat": None, "lng": None, "country": "China", "pref": "辽宁",
       "notes": None}
naive4b = cp._scan(e4b["addr"], None, cities)
hit4b = cp.place_approx(e4b)
check("4b. unguarded scan hits %s (天津)" % naive4b, naive4b == "和平区")
check("4b. guard falls through to 沈阳市",
      hit4b is not None and hit4b[2] == "沈阳市", repr(hit4b))

# ----------------------------------------- 5. already-has-coords untouched -
e5 = {"id": 5, "name": "街机烈火", "addr": "江宁路77恒顺大楼4层",
      "lat": 31.2304, "lng": 121.4737, "country": "China", "pref": "上海",
      "notes": "region: 上海市"}
before = dict(e5)
check("5. place_approx returns None for coordinated entry",
      cp.place_approx(e5) is None)
rec5 = cp.apply_approx(e5)
check("5. apply_approx is a no-op", rec5 is None)
check("5. coords unchanged", (e5["lat"], e5["lng"]) == (31.2304, 121.4737))
check("5. no approx flag added", "approx" not in e5)
check("5. notes unchanged", e5["notes"] == before["notes"])

# half-coordinated (lat set, lng null) must also be refused
e5b = dict(e5, lng=None)
check("5b. half-coordinated entry refused", cp.place_approx(e5b) is None)

# ------------------------------------ 6. municipality district refinement --
e6 = {"id": 6, "name": "环游嘉年华（北京朝阳大悦城店）",
      "addr": "朝阳区朝阳北路101号朝阳大悦城8F金逸影城旁",
      "lat": None, "lng": None, "country": "China", "pref": "北京",
      "notes": "region: 北京市"}
hit6 = cp.place_approx(e6)
check("6. 北京市 region note refined to 朝阳区",
      hit6 is not None and hit6[2] == "朝阳区", repr(hit6))
d6 = haversine_m((hit6[0], hit6[1]), tuple(cities["北京市"]))
check("6. district centroid differs from municipality centroid (%.0f m)" % d6,
      d6 > 1000)

e6b = {"id": 61, "name": "某上海店", "addr": "上海市浦东新区世纪大道100号",
       "lat": None, "lng": None, "country": "China", "pref": "上海",
       "notes": "region: 上海市"}
hit6b = cp.place_approx(e6b)
check("6b. 上海市 refined to 浦东新区",
      hit6b is not None and hit6b[2] == "浦东新区", repr(hit6b))

# A municipality address with no district still lands on the municipality.
e6c = {"id": 62, "name": "某天津店", "addr": "解放北路1号",
       "lat": None, "lng": None, "country": "China", "pref": "天津",
       "notes": "region: 天津市"}
hit6c = cp.place_approx(e6c)
check("6c. no district -> municipality centroid",
      hit6c is not None and hit6c[2] in ("天津市", "天津"), repr(hit6c))

# A municipality name occurring OUTSIDE that municipality must not refine:
# 上海路 in 黑龙江 is rejected by the guard entirely.
e6d = {"id": 63, "name": "金乐汇北安大润发店",
       "addr": "黑龙江省北安市上海路88号大润发超市二楼金乐汇电玩城",
       "lat": None, "lng": None, "country": "China", "pref": "黑龙江",
       "notes": None}
check("6d. 上海路 in 黑龙江 rejected", cp.place_approx(e6d) is None,
      repr(cp.place_approx(e6d)))

# ------------------------------------------------- 7. no-province behaviour -
e7 = {"id": 7, "name": "某店", "addr": "江苏省苏州市工业园区某广场3F",
      "lat": None, "lng": None, "country": "China", "pref": None,
      "notes": None}
hit7 = cp.place_approx(e7)
check("7. resolves with no declared province", hit7 is not None
      and hit7[2] == "苏州市", repr(hit7))

# --------------------------------------------------------- 8. unresolvable -
e8 = {"id": 8, "name": "58潮玩SPACE任丘万达店",
      "addr": "任丘万达广场二楼58潮玩SPACE", "lat": None, "lng": None,
      "country": "China", "pref": "河北", "notes": None}
check("8. county-level address unresolved (stays coordless)",
      cp.place_approx(e8) is None, repr(cp.place_approx(e8)))

# ------------------------------------- 9. non-China country never touched --
e9 = {"id": 9, "name": "Round1 Puente Hills", "addr": "1600 Azusa Ave",
      "lat": None, "lng": None, "country": "United States", "pref": "CA",
      "notes": None}
check("9. non-China entry skipped", cp.place_approx(e9) is None)

# ------------------------------------------------------- 10. apply_approx --
e10 = {"id": 10, "name": "1-7PLAY一起玩嘉年华(沧州一首诗生活中心店)",
       "addr": "沧州市运河区黄河西路与开元南大道交叉口荣盛国际购物广场F2",
       "lat": None, "lng": None, "country": "China", "pref": "河北",
       "notes": "region: 河北省 沧州市"}
rec10 = cp.apply_approx(e10)
cen10 = tuple(cities["沧州市"])
dist10 = haversine_m((e10["lat"], e10["lng"]), cen10)
check("10. apply_approx sets approx flag", e10.get("approx") is True)
check("10. note appended",
      "position approximate: city-level centroid (沧州市)" in e10["notes"],
      e10["notes"])
check("10. original note preserved", "region: 河北省 沧州市" in e10["notes"])
check("10. jittered %.0f m from centroid (<= %.0f)" % (dist10, cp.JITTER_M),
      0 < dist10 <= cp.JITTER_M + 1)
check("10. log record carries city + centroid",
      rec10["city"] == "沧州市"
      and (rec10["centroid_lat"], rec10["centroid_lng"]) == cen10,
      repr(rec10))

# apply twice: must be idempotent-ish (second call is a no-op, coords already
# set) and must not double-append the note.
rec10b = cp.apply_approx(e10)
check("10b. second apply is a no-op", rec10b is None)
check("10b. note not duplicated", e10["notes"].count("position approximate") == 1)

# ------------------------------------------------------------- 11. jitter --
seedA = cp.jitter_seed({"name": "A", "addr": "X"})
seedB = cp.jitter_seed({"name": "B", "addr": "X"})
j1 = cp.jitter(31.2336, 121.4681, seedA)
j2 = cp.jitter(31.2336, 121.4681, seedA)
j3 = cp.jitter(31.2336, 121.4681, seedB)
check("11. jitter deterministic", j1 == j2, "%r vs %r" % (j1, j2))
check("11. different seeds -> different points", j1 != j3)
check("11. seed ignores id",
      cp.jitter_seed({"id": 1, "name": "A", "addr": "X"})
      == cp.jitter_seed({"id": 999, "name": "A", "addr": "X"}))
dists = []
for i in range(2000):
    s = "seed-%d" % i
    p = cp.jitter(31.2336, 121.4681, s)
    dists.append(haversine_m(p, (31.2336, 121.4681)))
check("11. all 2000 jitters within %.0f m (max %.1f)"
      % (cp.JITTER_M, max(dists)), max(dists) <= cp.JITTER_M + 1)
check("11. none land exactly on the centroid (min %.1f m)" % min(dists),
      min(dists) > 0)
# high-latitude sanity: longitude scaling must not blow up
hi = cp.jitter(52.0, 124.0, "seed-hi")
check("11. high-latitude jitter still within radius",
      haversine_m(hi, (52.0, 124.0)) <= cp.JITTER_M + 1,
      "%.1f m" % haversine_m(hi, (52.0, 124.0)))

print()
if FAILED:
    print("%d FAILED: %s" % (len(FAILED), FAILED))
    sys.exit(1)
print("ALL TESTS PASSED")
