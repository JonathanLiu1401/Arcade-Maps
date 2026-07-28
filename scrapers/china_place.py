"""China approximate placement: the finest administrative centroid the address
actually names.

The two Chinese sources are coordinate-less by construction:

  * ``wahlap``   - the official SEGA China venue API returns an address and a
    province string, never a lat/lng.
  * ``bemanicn`` - map.bemanicn.com login-walls its coordinates; the public
    payload gives an address plus a ``region: <province> <city>`` label that
    ``scrapers/bemanicn.py`` copies into ``notes``.

Roughly 5.7k of the 6.5k China entries therefore carry ``lat: null``. Their
addresses, though, are excellent: ``广东省深圳市罗湖区东门街道城东社区东门中路
2010号信和东门商厦201`` names five nested administrative units, a road, a street
number and a building. This module reads as far down that chain as
``data/china_areas.json`` can follow and places the entry at that unit's
centroid.

**District, not city.** An earlier revision resolved only to the prefecture-level
city, which for a place like Shenzhen dropped all 119 of its coordinate-less
venues onto one point near 市民中心 and then fanned them out cosmetically, so the
map showed a fake arcade district a few hundred metres wide in Futian while the
real venues sit in Bao'an, Longgang and Nanshan, up to 40 km away. Resolving the
district named in the address moves 71% of the placed rows, by a median of 10 km
and a p90 of 60 km. It is still an approximation and still says so, but it is an
approximation of the right neighbourhood rather than of the wrong one.

District is as deep as free data goes. The upstream release publishes 乡镇/街道
boundaries (level 4) only as a paid asset, apart from a Shenzhen/Zhongshan/HK/
Macau sample, so the ``东门街道`` in that address cannot be resolved here. Real
street-number precision needs a geocoding API; see ``scrapers/geocode_cn.py``.

Resolution for one entry, each step gated by the one above it through the
parent-id chain in ``china_areas.json``:

  1. **Province** - the entry's own ``pref``, or the province token of the
     bemanicn ``region:`` note. An entry with no province is refused outright;
     without it a bare substring scan is free to match anything.
  2. **City** - the region note's city token first (the site's own
     administrative label, not a guess), else the earliest city name of that
     province appearing in the address or the venue name.
  3. **District** - the earliest district name of that city appearing in the
     address or the venue name.

The gating is structural rather than a maintained lookup table. An earlier
revision carried a hand-built 1,009-key ``KEY_PROVINCE`` map purely to stop
``中山中路`` in 定州 (河北) resolving to 中山市 (广东); with the hierarchy in the
data file, 中山市 is simply not among 河北's children and can never be
considered. The same structure fixes the harder half of that problem too: a
district name is only ever matched against the districts of the city already
resolved, so ``朝阳区`` cannot pull a 沈阳 address to 北京.

**Names, and their short forms.** Addresses usually write the full official name
(``宝安区``), and a full-name match always wins. When none is present the short
form is tried (``奎屯`` for ``奎屯市``), guarded against the obvious trap: a short
form immediately followed by a road/place character is part of a longer word, not
an administrative unit, so ``南山路`` never resolves to ``南山区``. Short forms
supply 13% of the district matches.

Three hard skips:

  * **Taiwan.** ``china_areas.json`` has the province but no cities or districts
    under it (the upstream release ships no coordinates for Taiwan), while ZIv
    already covers Taiwan with real, community-verified pins. Anything whose
    country or province says Taiwan is refused before any lookup runs, so a
    stray substring can never drop a Taiwanese address on the mainland.
  * **Hong Kong and Macau.** Excluded outright. The table holds one point for
    each, and Hong Kong's sits in Victoria Harbour: every coordinate-less Hong
    Kong row placed there landed in the water off Central and Wan Chai. ALL.Net,
    e-amusement and ZIv all cover Hong Kong with real street-level pins, so a
    venue that exists there is placed by merge instead, and anything unmatched
    keeps its authoritative address in the no-coords list.
  * **Entries that already have coordinates.** ``place_approx`` returns None for
    them, so an approximate centroid can never overwrite a real pin and
    ``approx`` can never be set on one.

**No fan-out.** Entries sharing a centroid are placed on it exactly, stacked.
A previous revision pushed each one off the centroid by up to 600 m so they
rendered as separate pins; that is precisely the lie this module should not
tell, because a reader zoomed into a street sees what looks like a specific
address for every one of them. Stacked, they cluster into a single badge that
reads "28 arcades in Bao'an" and spiderfy on click, which is exactly what the
data supports.
"""

from __future__ import annotations

import json
import os
import re

# Mirrors merge.cn_base / merge._CN_SUFFIXES. Duplicated rather than imported:
# merge.py imports this module, so importing merge here would be circular, and
# this module must also run standalone against a frozen arcades.json.
_CN_SUFFIXES = ["壮族自治区", "回族自治区", "维吾尔自治区", "特别行政区",
                "自治区", "省", "市", "城区", "地区"]

#: Suffixes that turn an area name into its short form (宝安区 -> 宝安). Longest
#: first, so 自治州 is stripped before 州.
_AREA_SUFFIXES = ("特别行政区", "自治州", "自治县", "自治旗", "新区", "林区",
                  "地区", "矿区", "盟", "市", "州", "区", "县", "旗")

#: A short form directly followed by one of these is part of a road or building
#: name rather than an administrative unit: 南山路, 和平街, 朝阳大厦. Full names
#: never need this guard because 南山区路 is not a thing.
_CONTINUATION = set("路街道巷里号弄村镇乡桥站城湖山河园苑府庭阁院场坊道")


def cn_base(s):
    """Bare province/city name: 广东省 -> 广东, 上海市 -> 上海."""
    s = (s or "").strip()
    for suf in _CN_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            return s[:-len(suf)]
    return s


def short_name(name):
    """宝安区 -> 宝安, 奎屯市 -> 奎屯. None when nothing can be stripped, or
    when what is left is a single character and far too weak to match on."""
    for suf in _AREA_SUFFIXES:
        if name.endswith(suf) and len(name) - len(suf) >= 2:
            return name[:-len(suf)]
    return None


# Own regex rather than merge.bemanicn_region's: that one is r"region:\s*([^;]+)"
# and does not stop at "|", which is exactly the separator geo_validate uses
# when appending notes, so it would capture across the pipe.
_REGION_RE = re.compile(r"region:\s*([^;|]+)")

_TAIWAN_PREFS = frozenset({"台湾", "臺灣", "台灣", "臺湾"})
_TAIWAN_COUNTRIES = frozenset({"Taiwan"})

#: Countries whose coordinate-less rows this module is allowed to place.
#: Mainland China only - see the Hong Kong / Macau / Taiwan note above.
PLACEABLE_COUNTRIES = frozenset({"China"})

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "china_areas.json")

_INDEX = None


class AreaIndex(object):
    """china_areas.json, indexed for parent-gated name lookup.

    ``areas`` is id -> {n, p, d, lat, lng}; ``children`` is parent id -> list of
    child ids, ordered by id so a rebuild picks the same candidate every time.
    """

    def __init__(self, areas):
        self.areas = areas
        self.children = {}
        for aid in sorted(areas):
            self.children.setdefault(areas[aid]["p"], []).append(aid)
        self.provinces = [aid for aid in sorted(areas)
                          if areas[aid]["d"] == 0]
        self.province_by_base = {}
        for aid in self.provinces:
            self.province_by_base.setdefault(cn_base(areas[aid]["n"]), aid)

    def kids(self, aid):
        return self.children.get(aid, [])

    def name(self, aid):
        return self.areas[aid]["n"]

    def coords(self, aid):
        a = self.areas[aid]
        return float(a["lat"]), float(a["lng"])

    def path(self, aid):
        """深圳市 宝安区 - the chain from city down, for the note text.

        A repeated name is collapsed: 东莞 and the other 直筒子市 have no
        districts, so the table repeats the city as its own only child and the
        raw chain reads "东莞市 东莞市".
        """
        parts = []
        while aid in self.areas and self.areas[aid]["d"] >= 1:
            name = self.areas[aid]["n"]
            if not parts or parts[-1] != name:
                parts.append(name)
            aid = self.areas[aid]["p"]
        return " ".join(reversed(parts))


def load_areas(path=None, force=False):
    """Load (and memoize) the administrative centroid table."""
    global _INDEX
    if _INDEX is not None and not force and path is None:
        return _INDEX
    with open(path or _DATA_PATH, encoding="utf-8") as fh:
        blob = json.load(fh)
    if blob.get("coord_system") != "wgs84":
        raise ValueError("china_areas.json is not wgs84: %r"
                         % blob.get("coord_system"))
    index = AreaIndex(blob["areas"])
    if path is None:
        _INDEX = index
    return index


# ------------------------------------------------------------- extraction ---

def entry_province(entry):
    """Province base for an entry: 广东省 -> 广东, 中国湖南省 -> 湖南.

    Falls back to the bemanicn region note's province token when ``pref`` is
    absent. Returns None when the entry declares no province."""
    pref = (entry.get("pref") or "").strip()
    pref = re.sub(r"^中国", "", pref)
    if pref:
        return cn_base(pref)
    prov, _city = region_tokens(entry.get("notes"))
    return prov


def region_tokens(notes):
    """(province_base, city_token) from a ``region: 省 市`` note.

    The city token is returned verbatim (``沧州市``) so the exact name can be
    tried before the suffix-stripped form. Municipalities carry only one
    token, in which case the city token is that same token."""
    m = _REGION_RE.search(notes or "")
    if not m:
        return None, None
    toks = m.group(1).split()
    if not toks:
        return None, None
    prov = cn_base(toks[0].strip())
    city = toks[1].strip() if len(toks) > 1 else toks[0].strip()
    return prov, city


def is_taiwan(entry):
    """True when country or province marks this entry as Taiwanese."""
    if (entry.get("country") or "") in _TAIWAN_COUNTRIES:
        return True
    pref = cn_base(re.sub(r"^中国", "", (entry.get("pref") or "").strip()))
    if pref in _TAIWAN_PREFS:
        return True
    prov, _ = region_tokens(entry.get("notes"))
    return prov in _TAIWAN_PREFS


# ------------------------------------------------------------ resolution ---

def match_area(text, ids, index, allow_short=True):
    """Earliest area from ``ids`` named in ``text``. Returns (id, how).

    Full official names are considered first and as a group, so a full-name hit
    anywhere in the string beats a short-form hit that happens to come earlier:
    ``深圳市宝安区南山路`` must resolve to 宝安区, not 南山区.
    """
    best = None
    for aid in ids:
        pos = text.find(index.name(aid))
        if pos >= 0 and (best is None or pos < best[0]):
            best = (pos, aid)
    if best:
        return best[1], "name"
    if not allow_short:
        return None, None
    for aid in ids:
        short = short_name(index.name(aid))
        if not short:
            continue
        pos = text.find(short)
        while pos >= 0:
            after = text[pos + len(short):pos + len(short) + 1]
            if after not in _CONTINUATION:
                if best is None or pos < best[0]:
                    best = (pos, aid)
                break
            pos = text.find(short, pos + 1)
    return (best[1], "short") if best else (None, None)


def _search_text(entry):
    """Address first, then the venue name, joined so one scan covers both. The
    address leads because a city named in it always outranks one that only
    appears in a brand (``玩计划沈阳和平K11店``)."""
    return "%s %s" % (entry.get("addr") or "", entry.get("name") or "")


def resolve(entry, index=None):
    """Deepest administrative unit this entry names.

    Returns ``(area_id, level)`` where level is "district" or "city", or None.
    Applies the country / Taiwan / already-placed guards.
    """
    if entry.get("lat") is not None or entry.get("lng") is not None:
        return None
    if (entry.get("country") or "") not in PLACEABLE_COUNTRIES:
        return None
    if is_taiwan(entry):
        return None

    index = index if index is not None else load_areas()
    text = _search_text(entry)

    prov_base = entry_province(entry)
    prov_id = index.province_by_base.get(prov_base) if prov_base else None
    if prov_id is None:
        # No usable declared province. A well-formed Chinese address opens with
        # one (``江苏省苏州市工业园区...``), so read it from the text - but by
        # full official name only. The short forms are the dangerous half of
        # the province list: 河北, 山东 and 上海 are all common road names, and
        # a wrong province here mis-gates every step below it.
        prov_id, _how = match_area(text, index.provinces, index,
                                   allow_short=False)
    if prov_id is None:
        return None

    # City: the region note's own label first, matched against this province's
    # children only, then a scan of the address.
    city_id = None
    _rprov, rcity = region_tokens(entry.get("notes"))
    if rcity:
        want = (rcity, cn_base(rcity))
        for aid in index.kids(prov_id):
            name = index.name(aid)
            if name in want or short_name(name) in want:
                city_id = aid
                break
    if city_id is None:
        city_id, _how = match_area(text, index.kids(prov_id), index)
    if city_id is None:
        return None

    district_id, _how = match_area(text, index.kids(city_id), index)
    if district_id is not None:
        return district_id, "district"
    return city_id, "city"


def place_approx(entry, index=None):
    """Resolve one entry to a centroid.

    Returns ``(lat, lng, area_id, level)`` on a hit, or None when the entry is
    skipped or unresolvable. The coordinates are the centroid exactly; nothing
    is added to them.
    """
    index = index if index is not None else load_areas()
    hit = resolve(entry, index)
    if hit is None:
        return None
    area_id, level = hit
    lat, lng = index.coords(area_id)
    return lat, lng, area_id, level


def _append_note(entry, note):
    existing = entry.get("notes")
    if not existing:
        entry["notes"] = note
        return
    if note in existing:
        return
    entry["notes"] = existing + " | " + note


def apply_approx(entry, index=None):
    """Place one entry in place. Returns a log record, or None if untouched."""
    index = index if index is not None else load_areas()
    hit = place_approx(entry, index)
    if hit is None:
        return None
    lat, lng, area_id, level = hit
    path = index.path(area_id)
    entry["lat"] = round(lat, 6)
    entry["lng"] = round(lng, 6)
    entry["approx"] = True
    entry["approx_level"] = level
    _append_note(entry, "position approximate: %s centroid (%s)" % (level, path))
    return {
        "id": entry.get("id"),
        "name": entry.get("name"),
        "src": list(entry.get("src") or []),
        "pref": entry.get("pref"),
        "level": level,
        "area": path,
        "area_id": area_id,
        "lat": entry["lat"],
        "lng": entry["lng"],
    }


def place_arcades(arcades, index=None):
    """Place every eligible coordinate-less entry. Mutates in place.

    Returns the list of log records (merge_log.json "china_approx").
    """
    index = index if index is not None else load_areas()
    log = []
    for entry in arcades:
        rec = apply_approx(entry, index)
        if rec is not None:
            log.append(rec)
    return log
