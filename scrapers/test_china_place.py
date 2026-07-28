"""Unit tests for scrapers/china_place.py against the real china_areas.json.

Every case here is a mis-placement that actually shipped, or one the gating is
there to prevent. Run: python scrapers/test_china_place.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import china_place as cp

# Chinese place names in test output die on the cp1252 Windows console.
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


def haversine_m(a, b):
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def entry(**kw):
    e = {"id": 0, "name": "", "addr": "", "lat": None, "lng": None,
         "country": "China", "pref": None, "notes": None}
    e.update(kw)
    return e


IX = cp.load_areas()
print("loaded %d areas (%d provinces)\n" % (len(IX.areas), len(IX.provinces)))


def area_id(name, parent=None):
    """Find an area by exact name, optionally under a named parent."""
    for aid in sorted(IX.areas):
        if IX.name(aid) != name:
            continue
        pid = IX.areas[aid]["p"]
        if parent is None or (pid in IX.areas and IX.name(pid) == parent):
            return aid
    raise KeyError(name)


# ------------------------------------------------------------ table sanity -
print("--- table ---")
orphans = [a for a in IX.areas
           if IX.areas[a]["d"] and IX.areas[a]["p"] not in IX.areas]
check("every non-province area has a parent in the table", not orphans,
      repr(orphans[:3]))
check("all three levels present",
      {IX.areas[a]["d"] for a in IX.areas} == {0, 1, 2})
check("province index resolves a bare province name",
      IX.name(IX.province_by_base["广东"]) == "广东省")

# --------------------------------------------- 1. district from the address -
print("\n--- 1. district resolution ---")
e1 = entry(id=1, name="AKIBA深圳奇谷米次元街区店",
           addr="广东省深圳市南山区沙河街道东方社区白石路2033号欢乐海岸购物中心L2-E202",
           pref="广东")
hit1 = cp.place_approx(e1)
check("1. resolves to 南山区", hit1 and hit1[3] == "district"
      and IX.name(hit1[2]) == "南山区", repr(hit1 and IX.name(hit1[2])))
city1 = IX.coords(area_id("深圳市", "广东省"))
check("1. moved %.1f km off the city centroid"
      % (haversine_m(hit1[:2], city1) / 1000),
      haversine_m(hit1[:2], city1) > 5000)

# 白石路 sits in the same address. Its 白石 is not a district here, but the
# short-form path must not invent one either: the full name 南山区 wins outright.
e1b = entry(id=11, name="某店", addr="深圳市宝安区南山路100号", pref="广东")
hit1b = cp.place_approx(e1b)
check("1b. 南山路 does not beat the full name 宝安区",
      hit1b and IX.name(hit1b[2]) == "宝安区", repr(hit1b and IX.name(hit1b[2])))

# A short form is allowed when no full name is present, which is how county-level
# cities inside a prefecture get found at all.
e1c = entry(id=12, name="某店", addr="奎屯友好4楼", pref="新疆",
            notes="region: 新疆维吾尔自治区 伊犁哈萨克自治州")
hit1c = cp.place_approx(e1c)
check("1c. short form 奎屯 -> 奎屯市",
      hit1c and IX.name(hit1c[2]) == "奎屯市", repr(hit1c and IX.name(hit1c[2])))

# ...but only when it is not the head of a longer word.
e1d = entry(id=13, name="某店", addr="天津市河北路200号", pref="天津")
hit1d = cp.place_approx(e1d)
check("1d. 河北路 does not resolve to 河北区 by short form",
      hit1d is None or IX.name(hit1d[2]) != "河北",
      repr(hit1d and IX.name(hit1d[2])))

# ----------------------------------------------- 2. region note is trusted -
print("\n--- 2. region note ---")
e2 = entry(id=2, name="1-7PLAY一起玩嘉年华(沧州一首诗生活中心店)",
           addr="沧州市运河区黄河西路与开元南大道交叉口荣盛国际购物广场F2",
           pref="河北", notes="region: 河北省 沧州市")
hit2 = cp.place_approx(e2)
check("2. region note city + address district -> 运河区",
      hit2 and IX.name(hit2[2]) == "运河区", repr(hit2 and IX.name(hit2[2])))

# geo_validate appends notes with " | ", and the region regex must stop there
# or it captures the next note as part of the city token.
prov, city = cp.region_tokens("region: 河北省 沧州市 | position approximate: x")
check("2b. region regex stops at '|'", (prov, city) == ("河北", "沧州市"),
      repr((prov, city)))

e2c = entry(id=21, name="某店", addr="某广场3F", pref="中国河北省",
            notes="region: 河北省 沧州市")
check("2c. pref '中国河北省' normalizes", cp.entry_province(e2c) == "河北")
check("2c. still resolves with a messy pref", cp.place_approx(e2c) is not None)

# ----------------------------------------------------------- 3. Taiwan skip -
print("\n--- 3. Taiwan ---")
e3 = entry(id=3, name="GiGO - Global Mall 南港車站店",
           addr="台北市南港區忠孝東路七段368號", pref="台湾")
check("3. Taiwan pref skipped", cp.place_approx(e3) is None)
e3b = entry(id=31, name="某店", addr="台中市北屯路二段100號中山路口",
            country="Taiwan", pref=None)
check("3b. Taiwan country skipped", cp.place_approx(e3b) is None)
# Why that skip has to come first: both halves of this Taiwanese address name a
# real mainland unit (北屯区 in 台中 shares its name with 北屯市 in 新疆, 中山路
# with 中山市 in 广东), so the address is one province guess away from landing on
# the mainland.
check("3b. the trap is real: 北屯市 and 中山市 both exist in the table",
      any(IX.name(a) == "北屯市" for a in IX.areas)
      and any(IX.name(a) == "中山市" for a in IX.areas))
hit3c, _ = cp.match_area("台中市北屯路二段100號中山路口",
                         IX.kids(IX.province_by_base["广东"]), IX)
check("3c. and only the continuation guard keeps 中山路 off 中山市",
      hit3c is None, repr(hit3c and IX.name(hit3c)))

# ----------------------------------------- 4. cross-province is structural --
print("\n--- 4. province gating ---")
e4 = entry(id=4, name="小洋人宝贝王定州南城店",
           addr="定州市中山中路国际购物广场三层", pref="河北")
hit4 = cp.place_approx(e4)
check("4. 中山中路 in 河北 never reaches 中山市 (广东)",
      hit4 is None or IX.name(hit4[2]) != "中山市",
      repr(hit4 and IX.name(hit4[2])))
check("4. 中山市 is not a child of 河北省",
      "中山市" not in [IX.name(a)
                       for a in IX.kids(IX.province_by_base["河北"])])

e4b = entry(id=41, name="玩计划沈阳和平K11店", addr="和平区中华路68号K11购物艺术中心",
            pref="辽宁", notes="region: 辽宁省 沈阳市")
hit4b = cp.place_approx(e4b)
check("4b. 和平区 resolves inside 沈阳市, not 天津",
      hit4b and IX.name(hit4b[2]) == "和平区"
      and IX.path(hit4b[2]).startswith("沈阳市"),
      repr(hit4b and IX.path(hit4b[2])))

# ---------------------------------------- 5. entries with coords untouched --
print("\n--- 5. never overwrite a real pin ---")
e5 = entry(id=5, name="街机烈火", addr="江宁路77恒顺大楼4层", lat=31.2304,
           lng=121.4737, pref="上海", notes="region: 上海市 上海市")
before = dict(e5)
check("5. place_approx returns None for a coordinated entry",
      cp.place_approx(e5) is None)
check("5. apply_approx is a no-op", cp.apply_approx(e5) is None)
check("5. coords unchanged", (e5["lat"], e5["lng"]) == (31.2304, 121.4737))
check("5. no approx flag added", "approx" not in e5)
check("5. notes unchanged", e5["notes"] == before["notes"])
check("5b. half-coordinated entry refused",
      cp.place_approx(entry(id=51, lat=31.2, lng=None, pref="上海")) is None)

# ------------------------------------------------- 6. municipality handling -
print("\n--- 6. municipalities ---")
e6 = entry(id=6, name="环游嘉年华（北京朝阳大悦城店）",
           addr="北京市朝阳区朝阳北路101号朝阳大悦城5层", pref="北京",
           notes="region: 北京市 北京市")
hit6 = cp.place_approx(e6)
check("6. 北京 refines to 朝阳区", hit6 and IX.name(hit6[2]) == "朝阳区"
      and IX.path(hit6[2]).startswith("北京市"), repr(hit6 and IX.path(hit6[2])))
d6 = haversine_m(hit6[:2], IX.coords(area_id("北京市", "北京市")))
check("6. district centroid differs from the municipality centroid (%.0f m)"
      % d6, d6 > 1000)

e6b = entry(id=61, name="某天津店", addr="解放北路1号", pref="天津",
            notes="region: 天津市 天津市")
hit6b = cp.place_approx(e6b)
check("6b. no district named -> city centroid",
      hit6b and hit6b[3] == "city", repr(hit6b and hit6b[3]))

# --------------------------------------------- 7. province read from address -
print("\n--- 7. undeclared province ---")
e7 = entry(id=7, name="某店", addr="江苏省苏州市工业园区某广场3F")
hit7 = cp.place_approx(e7)
check("7. province taken from the address text",
      hit7 and IX.path(hit7[2]).startswith("苏州市"),
      repr(hit7 and IX.path(hit7[2])))
# Only the full official name is accepted there: 河北路 must not make an entry
# with no province suddenly belong to 河北省.
e7b = entry(id=71, name="某店", addr="河北路200号某商场")
check("7b. a bare short form does not establish a province",
      cp.place_approx(e7b) is None, repr(cp.place_approx(e7b)))

# ------------------------------------------------- 8. skipped countries -----
print("\n--- 8. skipped countries ---")
check("8. non-China entry skipped",
      cp.place_approx(entry(id=8, name="Round1 Puente Hills",
                            addr="1600 Azusa Ave", country="United States",
                            pref="CA")) is None)
check("8b. Hong Kong skipped (its centroid is in Victoria Harbour)",
      cp.place_approx(entry(id=81, name="某店", addr="旺角彌敦道688號",
                            country="Hong Kong", pref="香港")) is None)
check("8c. Macau skipped",
      cp.place_approx(entry(id=82, name="某店", addr="澳门某广场",
                            country="Macau", pref="澳门")) is None)

# ----------------------------------------------------- 9. apply_approx ------
print("\n--- 9. apply_approx ---")
e9 = entry(id=9, name="全境方舟深圳东门店",
           addr="广东省深圳市罗湖区东门街道城东社区东门中路2010号信和东门商厦201",
           pref="广东", notes="region: 广东省 深圳市")
rec9 = cp.apply_approx(e9)
check("9. approx flag set", e9.get("approx") is True)
check("9. level recorded on the entry", e9.get("approx_level") == "district")
check("9. note names the level and the area",
      "position approximate: district centroid (深圳市 罗湖区)" in e9["notes"],
      e9["notes"])
check("9. original note preserved", "region: 广东省 深圳市" in e9["notes"])
check("9. log record carries level and area",
      rec9["level"] == "district" and rec9["area"] == "深圳市 罗湖区",
      repr(rec9))
check("9b. second apply is a no-op", cp.apply_approx(e9) is None)
check("9b. note not duplicated",
      e9["notes"].count("position approximate") == 1)

# ------------------------------------------------------ 10. no fan-out ------
print("\n--- 10. no fan-out ---")
a10 = entry(id=101, name="店A", addr="广东省深圳市宝安区某路1号", pref="广东")
b10 = entry(id=102, name="店B", addr="广东省深圳市宝安区另一路2号", pref="广东")
cp.apply_approx(a10)
cp.apply_approx(b10)
check("10. two venues in one district land on the exact same point",
      (a10["lat"], a10["lng"]) == (b10["lat"], b10["lng"]),
      "%r vs %r" % ((a10["lat"], a10["lng"]), (b10["lat"], b10["lng"])))
check("10. and that point is the district centroid",
      (a10["lat"], a10["lng"])
      == tuple(round(v, 6) for v in IX.coords(area_id("宝安区", "深圳市"))))
check("10. no jitter helper survives",
      not hasattr(cp, "jitter") and not hasattr(cp, "JITTER_M"))

# ------------------------------------------------------- 11. place_arcades --
print("\n--- 11. place_arcades ---")
batch = [entry(id=111, name="某店", addr="广东省深圳市福田区某路", pref="广东"),
         entry(id=112, name="Round1", addr="1600 Azusa Ave",
               country="United States"),
         entry(id=113, name="某店", addr="上海市浦东新区世纪大道100号",
               pref="上海")]
log = cp.place_arcades(batch)
check("11. placed exactly the two China rows", len(log) == 2, repr(len(log)))
check("11. US row untouched", batch[1]["lat"] is None)
check("11. 浦东新区 resolved", log[1]["area"] == "上海市 浦东新区",
      repr(log[1]["area"]))

print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
if FAILED:
    print("FAILURES:")
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL TESTS PASSED")
