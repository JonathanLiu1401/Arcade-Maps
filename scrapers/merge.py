"""Merge raw scraped sources (data_raw/) into the unified data/arcades.json.

Pipeline rules (see README / task spec):
 (a) lat==0 and lng==0 -> null (counted)
 (b) within-source dedupe by NFKC-normalized, whitespace-collapsed
     (name, address)
 (c) conservative cross-source physical-store merge:
     distance < 120 m AND name similarity >= 0.6, OR exact normalized
     name match when one side lacks coords (same resolved country only).
     PLUS a distance-gated proximity tier (see the delimited section
     below): official-vs-community pairs under 30 m that the 0.6 name
     gate rejected are re-examined with romanization-aware matching
     (scrapers/name_match.py), because a ZIv romaji name and an official
     kana name for one arcade can share zero characters. The 0.6 gate
     and the 120 m radius themselves are UNCHANGED.
     Two coordinate-less entries merge only on exact (name, address),
     EXCEPT the China-scoped wahlap x bemanicn rule: same province,
     city-gated, name similarity >= 0.8 (parenthetical branch text
     kept) - both sources are coordinate-less so the global rules can
     never fire for them. Same-source listings merge only when the
     compact names are identical AND coords are within 30 m.
     Official sources (allnet, eagate, wahlap) win name/addr/coords.
     Every cross-source union is logged to data/merge_log.json.
 (d) wahlap / bemanicn (China, coordinate-less) inherit coords from
     matched ziv entries; recorded as inherited:true in notes.
 (e) gcj02 / bd09 -> wgs84 via eviltransform when coord_system says so.
 (f) country from region labels / wahlap province / geo+address heuristics.
 (g) links.gmaps / links.ziv / links.bemanicn.
 (h) a fresh per-source scrape file (ziv.json / round1usa.json)
     SUPERSEDES that source's rows bundled inside community.json, so
     a re-crawl replaces rather than doubles it; community.json's
     other sources are still ingested.
 (i) game_counts (bemanicn quantities / ziv machine tallies) survive
     within-source dedupe and cross-source merges as the per-slug MAX
     over the merged members (bemanicn wins where only it has a slug,
     ziv where only it does, max where both do). A counted slug is
     always added to games; entries with no counted slug carry no
     game_counts key.
 (m) counts confidence: a ZIv per-game count of exactly 1 is a
     PLACEHOLDER (its payload lists one row per game version, so any
     title the arcade merely has tallies to 1), while bemanicn counts
     are true per-title 台数. Every entry whose members reported counts
     is therefore tagged "counts_src": bemanicn wins when both sources
     contributed; ziv-only counts survive when ANY slug is >= 2 (a 2
     proves the list was really tallied, so that entry's 1s are real
     1s); ziv-only counts that are ALL 1 are dropped entirely with
     counts_src null, so placeholder data never renders as "x1". The
     key is absent when no source counted at all, keeping "suppressed
     placeholder" distinguishable from "never counted". Dropping a
     count never drops the game - games is unioned first.
 (j) source-aware geo validation (scrapers/geo_validate.py): after
     country resolution, every entry with coords is checked against
     the labeled country's bbox. Official sources (allnet/eagate/
     wahlap) trust the address and null out-of-country geocodes;
     community sources (ziv/round1usa/community) trust the pin and
     correct a wrong country label. Actions land in merge_log.json
     under "geo_validation".
 (k) optional enrichment (bemanicn transit/coin pricing/hours/thumb,
     ziv machine pricing/website/hours/photos) is written to a SEPARATE
     data/enrichment.json keyed by merged id, NOT into arcades.json,
     which stays lean for the initial page load. See scrapers/enrich.py.
 (l) China approximate placement (scrapers/china_place.py): the ~5.9k
     coordinate-less China rows (wahlap and bemanicn publish no
     lat/lng) are placed at their city's centroid from
     data/china_cities.json, flagged "approx": true and noted
     "position approximate: city-level centroid (<city>)". Runs after
     geo validation, never touches an entry that already has coords,
     hard-skips Taiwan, and rejects any city whose province
     contradicts the entry's. Pins sharing a centroid are fanned out
     by a deterministic sub-600 m offset - cosmetic only, it encodes
     no real position. Logged to merge_log.json under "china_approx".
"""

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import china_place    # China approximate placement (see (l) in run())
import common
import enrich          # enrichment section (see (k) in run())
import eviltransform
import geo_validate
import name_match     # romanization-aware proximity tier (see (c))

GAME_SLUGS = [
    "maimai_dx", "chunithm", "ongeki", "project_diva", "sdvx", "iidx",
    "ddr", "polaris_chord", "gitadora", "jubeat", "popn", "nostalgia",
    "drs", "dance_around", "dance_evo", "museca", "reflec", "taiko", "other",
]
CAB_SLUGS = ["sdvx_vm", "iidx_lm", "ddr_gold", "gitadora_gf_arena",
             "gitadora_dm_arena", "popn_pikapika"]

SRC_PRIORITY = {"allnet": 0, "eagate": 1, "wahlap": 2, "bemanicn": 3,
                "ziv": 4, "round1usa": 5, "community": 6}
OFFICIAL = {"allnet", "eagate", "wahlap"}

# data_raw file -> (games, cabs) per source
ALLNET_FILES = {
    "maimai_jp": ["maimai_dx"], "maimai_intl": ["maimai_dx"],
    "chunithm_jp": ["chunithm"], "chunithm_intl": ["chunithm"],
    "ongeki": ["ongeki"], "project_diva": ["project_diva"],
}
EAGATE_FILES = {
    "polaris_chord": (["polaris_chord"], []),
    "sdvx": (["sdvx"], []),
    "sdvx_vm": (["sdvx"], ["sdvx_vm"]),
    "iidx": (["iidx"], []),
    "iidx_lm": (["iidx"], ["iidx_lm"]),
    "ddr": (["ddr"], []),
    "ddr_gold": (["ddr"], ["ddr_gold"]),
    "gitadora_gf": (["gitadora"], []),
    "gitadora_dm": (["gitadora"], []),
    "gitadora_gf_arena": (["gitadora"], ["gitadora_gf_arena"]),
    "gitadora_dm_arena": (["gitadora"], ["gitadora_dm_arena"]),
    "jubeat": (["jubeat"], []),
    "popn": (["popn"], []),
    "popn_pikapika": (["popn"], ["popn_pikapika"]),
    "nostalgia": (["nostalgia"], []),
    "drs": (["drs"], []),
    "dance_around": (["dance_around"], []),
    "dance_evo": (["dance_evo"], []),
    "museca": (["museca"], []),
    "reflec": (["reflec"], []),
}
WAHLAP_FILES = {
    "china_wahlap_maimai_dx": ["maimai_dx"],
    "china_wahlap_chunithm": ["chunithm"],
}

JP_PREFS_JA = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]
JP_PREFS_EN = [
    "Hokkaido", "Aomori", "Iwate", "Miyagi", "Akita", "Yamagata",
    "Fukushima", "Ibaraki", "Tochigi", "Gunma", "Saitama", "Chiba",
    "Tokyo", "Kanagawa", "Niigata", "Toyama", "Ishikawa", "Fukui",
    "Yamanashi", "Nagano", "Gifu", "Shizuoka", "Aichi", "Mie", "Shiga",
    "Kyoto", "Osaka", "Hyogo", "Nara", "Wakayama", "Tottori", "Shimane",
    "Okayama", "Hiroshima", "Yamaguchi", "Tokushima", "Kagawa", "Ehime",
    "Kochi", "Fukuoka", "Saga", "Nagasaki", "Kumamoto", "Oita",
    "Miyazaki", "Kagoshima", "Okinawa",
]

ALLNET_REGION_COUNTRY = {
    "Taiwan": "Taiwan", "Hong Kong": "Hong Kong", "Macau": "Macau",
    "Korea": "South Korea", "Viet Nam": "Vietnam", "Singapore": "Singapore",
    "Malaysia": "Malaysia", "Thailand": "Thailand", "Indonesia": "Indonesia",
    "Philippines": "Philippines", "Australia": "Australia",
    "Myanmar": "Myanmar", "New Zealand": "New Zealand",
}

# ---------------------------------------------------------------- country ---

_HANGUL = re.compile(r"[가-힯]")
_KANA = re.compile(r"[぀-ヿ]")
_CA_POSTAL = re.compile(r"\b[ABCEGHJ-NPRSTVXY]\d[A-Z]\s?\d[A-Z]\d\b")
_US_STATE_ZIP = re.compile(
    r"\b(A[LKZR]|C[AOT]|D[EC]|FL|GA|HI|I[DLNA]|K[SY]|LA|M[EDAINSOT]"
    r"|N[EVHJMYCD]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[TA]|W[AVIY])"
    r"\.?\s+\d{5}(?:-\d{4})?\b")
_CA_PROVINCES = re.compile(
    r"\b(Ontario|Quebec|Québec|British Columbia|Alberta|Manitoba"
    r"|Saskatchewan|Nova Scotia|New Brunswick|Newfoundland"
    r"|Prince Edward Island)\b", re.I)

_COUNTRY_HINTS = [
    (re.compile(r"\btaiwan\b|台湾|臺灣", re.I), "Taiwan"),
    (re.compile(r"\bhong\s?kong\b|香港", re.I), "Hong Kong"),
    (re.compile(r"\bmacau\b|\bmacao\b|澳門|澳门", re.I), "Macau"),
    (re.compile(r"\bsingapore\b", re.I), "Singapore"),
    (re.compile(r"\bjapan\b", re.I), "Japan"),
    (re.compile(r"\bkorea\b", re.I), "South Korea"),
    (re.compile(r"\bviet\s?nam\b", re.I), "Vietnam"),
    (re.compile(r"\bmalaysia\b", re.I), "Malaysia"),
    (re.compile(r"\bindonesia\b", re.I), "Indonesia"),
    (re.compile(r"\bphilippines\b", re.I), "Philippines"),
    (re.compile(r"\bthailand\b", re.I), "Thailand"),
    (re.compile(r"\bcambodia\b", re.I), "Cambodia"),
    (re.compile(r"\bmyanmar\b", re.I), "Myanmar"),
    (re.compile(r"\baustralia\b|\bnew south wales\b", re.I), "Australia"),
    (re.compile(r"\bnew zealand\b", re.I), "New Zealand"),
    (re.compile(r"\bcanada\b", re.I), "Canada"),
    (re.compile(r"\busa\b|\bu\.s\.a\b|\bunited states\b", re.I),
     "United States"),
    (re.compile(r"\bmexico\b|\bméxico\b", re.I), "Mexico"),
    (re.compile(r"\bbrazil\b|\bbrasil\b", re.I), "Brazil"),
    (re.compile(r"\bunited kingdom\b|\bengland\b|\bscotland\b"
                r"|(?<!new south )\bwales\b", re.I), "United Kingdom"),
    (re.compile(r"\bchina\b|中国|中國", re.I), "China"),
    (re.compile(r"\bindia\b", re.I), "India"),
]

# Ordered bounding boxes (country, lat_min, lat_max, lng_min, lng_max).
# Small / enclosed regions first; approximate on borders (see README).
COUNTRY_BOXES = [
    # lat_max 22.50: north of that is Shenzhen (real HK venues top out
    # around Tin Shui Wai / Tai Po at ~22.46; Sheung Shui ~22.50)
    ("Hong Kong", 22.13, 22.50, 113.82, 114.45),
    ("Macau", 22.06, 22.24, 113.52, 113.65),
    ("Singapore", 1.15, 1.458, 103.59, 104.10),
    ("Taiwan", 21.85, 25.35, 119.30, 122.05),
    ("South Korea", 33.00, 38.65, 124.50, 129.70),
    ("Japan", 24.00, 45.70, 122.80, 146.10),
    ("Brunei", 4.00, 5.10, 114.00, 115.40),
    ("Malaysia", 0.80, 7.50, 99.50, 104.70),
    ("Malaysia", 0.80, 7.50, 109.50, 119.40),
    ("Philippines", 4.50, 21.20, 116.80, 126.70),
    ("Vietnam", 8.40, 23.40, 102.10, 109.60),
    ("Cambodia", 10.30, 14.70, 102.30, 107.70),
    ("Thailand", 5.50, 20.50, 97.30, 105.70),
    ("Laos", 13.90, 22.60, 100.00, 107.80),
    ("Myanmar", 9.50, 28.60, 92.10, 101.20),
    ("Indonesia", -11.10, 6.20, 94.90, 141.10),
    ("Mongolia", 41.55, 52.20, 87.70, 119.95),
    ("China", 18.00, 53.70, 73.40, 134.90),
    ("Pakistan", 23.60, 37.10, 60.80, 77.90),
    ("Nepal", 26.30, 30.50, 80.00, 88.30),
    ("Bangladesh", 20.50, 26.70, 88.00, 92.70),
    ("Sri Lanka", 5.85, 9.90, 79.50, 82.00),
    ("India", 6.50, 35.60, 68.00, 97.50),
    ("Guam", 13.20, 13.70, 144.60, 145.05),
    ("New Zealand", -47.50, -34.00, 166.00, 178.70),
    ("Australia", -44.00, -10.00, 112.90, 154.00),
    ("United States", 18.70, 22.50, -160.50, -154.50),   # Hawaii
    ("United States", 51.00, 71.50, -170.00, -129.90),   # Alaska
    ("United States", 24.40, 49.40, -125.00, -66.80),    # contiguous
    ("Canada", 41.60, 83.20, -141.10, -52.50),
    ("Puerto Rico", 17.90, 18.55, -67.35, -65.20),
    ("Dominican Republic", 17.40, 19.95, -72.05, -68.25),
    ("Jamaica", 17.60, 18.60, -78.50, -76.10),
    ("Trinidad and Tobago", 10.00, 11.40, -62.00, -60.40),
    ("Mexico", 14.50, 32.80, -118.50, -86.60),
    ("Guatemala", 13.70, 17.90, -92.30, -88.10),
    ("El Salvador", 13.10, 14.45, -90.20, -87.65),
    ("Honduras", 12.90, 16.50, -89.40, -83.10),
    ("Nicaragua", 10.70, 15.05, -87.70, -82.60),
    ("Costa Rica", 8.00, 11.30, -85.98, -82.50),
    ("Panama", 7.10, 9.70, -83.10, -77.10),
    ("Colombia", -4.30, 12.60, -79.10, -66.80),
    ("Venezuela", 0.60, 12.30, -73.40, -59.70),
    ("Ecuador", -5.05, 1.70, -81.10, -75.10),
    ("Peru", -18.40, -0.03, -81.40, -68.60),
    ("Bolivia", -22.95, -9.60, -69.70, -57.40),
    ("Uruguay", -35.10, -30.00, -58.25, -53.00),
    ("Paraguay", -27.70, -19.20, -62.70, -54.20),
    ("Chile", -56.00, -17.40, -76.00, -69.80),
    ("Argentina", -55.20, -21.70, -73.60, -53.60),
    ("Brazil", -34.00, 5.30, -74.10, -34.70),
    ("Ireland", 51.40, 55.40, -10.60, -6.00),
    ("United Kingdom", 49.80, 60.90, -8.70, 1.80),
    ("Spain", 27.40, 29.50, -18.30, -13.30),      # Canary Islands
    ("Martinique", 14.38, 14.90, -61.25, -60.80),
    ("Hungary", 45.70, 48.60, 16.45, 21.80),
    ("Bulgaria", 41.20, 44.20, 22.30, 28.60),
    ("Romania", 43.60, 48.30, 20.20, 29.70),
    ("Ukraine", 44.30, 52.40, 23.50, 40.20),
    ("Cyprus", 34.50, 35.70, 32.20, 34.60),
    ("Ghana", 4.70, 11.20, -3.30, 1.20),
    ("Iran", 25.00, 39.80, 44.00, 63.30),
    ("Portugal", 36.90, 42.20, -9.60, -6.20),
    ("Spain", 35.90, 43.80, -9.40, 3.40),
    ("Belgium", 49.50, 51.60, 2.50, 6.40),
    ("Netherlands", 50.70, 53.60, 3.30, 7.20),
    ("Switzerland", 45.80, 47.90, 5.90, 10.50),
    ("Austria", 46.30, 49.10, 9.50, 17.20),
    ("Czechia", 48.50, 51.10, 12.00, 18.90),
    ("Denmark", 54.50, 57.80, 8.00, 12.80),
    ("France", 42.30, 51.10, -5.20, 8.30),
    ("Italy", 36.60, 47.10, 6.60, 18.60),
    ("Germany", 47.20, 55.10, 5.80, 15.10),
    ("Poland", 49.00, 54.90, 14.10, 24.20),
    ("Greece", 34.80, 41.80, 19.30, 28.30),
    ("Norway", 57.90, 71.30, 4.50, 31.20),
    ("Sweden", 55.30, 69.10, 10.90, 24.20),
    ("Finland", 59.70, 70.10, 20.50, 31.60),
    ("Turkey", 35.80, 42.20, 25.90, 44.90),
    ("Israel", 29.40, 33.40, 34.20, 35.90),
    ("United Arab Emirates", 22.60, 26.10, 51.50, 56.40),
    ("Saudi Arabia", 16.30, 32.20, 34.40, 55.70),
    ("Egypt", 22.00, 31.70, 24.60, 36.90),
    ("Morocco", 27.60, 35.95, -13.50, -1.00),
    ("Nigeria", 4.20, 13.90, 2.60, 14.70),
    ("Kenya", -4.80, 4.70, 33.90, 41.90),
    ("South Africa", -35.00, -22.10, 16.40, 33.00),
    ("Bahrain", 25.75, 26.35, 50.30, 50.85),
    ("Qatar", 24.40, 26.25, 50.70, 51.70),
    ("Kuwait", 28.50, 30.10, 46.50, 48.50),
    ("Russia", 41.00, 82.00, 27.00, 180.00),
]


def bbox_country(lat, lng):
    for name, la1, la2, lo1, lo2 in COUNTRY_BOXES:
        if la1 <= lat <= la2 and lo1 <= lng <= lo2:
            return name
    return None


def resolve_country(lat, lng, addr, name):
    """Order matters (audit D1): script checks, then the strong signals
    (coordinate bounding box, US state+ZIP), then keyword hints matched
    against the ADDRESS ONLY - venue names like "JAPAN VILLAGE" in
    Brooklyn must never set the country.

    Canadian province names are checked AFTER the coordinate bbox so
    street strings like "Ontario, California" or "Quebec Rd, Mablethorpe"
    do not override a real US/UK pin. CA postal codes stay early - they
    are unambiguous. When no coords are present the province-name check
    still runs and labels bare "Toronto, Ontario" addresses as Canada."""
    text = "%s %s" % (addr or "", name or "")
    addr = addr or ""
    if _HANGUL.search(text):
        return "South Korea"
    if _CA_POSTAL.search(text):
        return "Canada"
    if lat is not None and lng is not None:
        hit = bbox_country(lat, lng)
        if hit:
            return hit
    if _CA_PROVINCES.search(text):
        return "Canada"
    if _US_STATE_ZIP.search(addr):
        return "United States"
    for rx, country in _COUNTRY_HINTS:
        if rx.search(addr):
            return country
    if _KANA.search(text):
        return "Japan"
    return "Unknown"


_US_STATE_RE = _US_STATE_ZIP
_CN_PROV_RE = re.compile(r"([一-鿿]{1,8}(?:省|自治区))")


def extract_pref(country, addr):
    addr = addr or ""
    if country == "United States":
        m = _US_STATE_RE.search(addr)
        return m.group(1) if m else None
    if country == "Japan":
        for en in JP_PREFS_EN:
            if re.search(r"\b%s\b" % en, addr):
                return en
        for ja in JP_PREFS_JA:
            if ja in addr or ja.rstrip("県府都") in addr[:6]:
                return ja
        return None
    if country == "China":
        m = _CN_PROV_RE.search(addr)
        return m.group(1) if m else None
    return None


# ------------------------------------------------------------ name matching -

_PAREN_RE = re.compile(r"\([^)]*\)|（[^）]*）")
_KEEP_RE = re.compile(
    r"[^0-9a-z&぀-ヿ㐀-鿿가-힯ｦ-ﾟ]+")


def _norm_text(s):
    s = unicodedata.normalize("NFKC", s or "").casefold()
    s = re.sub(r"^[0-9]{2,}", "", s)        # wahlap numeric venue prefixes
    return _KEEP_RE.sub(" ", s).strip()


def norm_name(s):
    out = _norm_text(_PAREN_RE.sub(" ", s or ""))
    if not out:  # name was entirely parenthetical; retry without stripping
        out = _norm_text(s or "")
    return out


def compact_name(s):
    c = norm_name(s).replace(" ", "")
    if len(c) > 2 and c.endswith("店"):
        c = c[:-1]
    return c


def compact_name_exact(s):
    """Compact form for the exact-name merge path.

    Unlike compact_name this KEEPS parenthetical content (branch names
    often live in parentheses; stripping them would collapse different
    branches of one chain into a single fake match)."""
    c = _norm_text(s).replace(" ", "")
    if len(c) > 2 and c.endswith("店"):
        c = c[:-1]
    return c


def _bigrams(s):
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


# -------------------------------------------- China (wahlap x bemanicn) ---

_CN_SUFFIXES = ["壮族自治区", "回族自治区", "维吾尔自治区", "特别行政区",
                "自治区", "省", "市", "城区", "地区"]


def cn_base(s):
    """Bare province/city name: 广东省 -> 广东, 上海市 -> 上海."""
    s = (s or "").strip()
    for suf in _CN_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            return s[:-len(suf)]
    return s


_REGION_NOTE_RE = re.compile(r"region:\s*([^;]+)")


def bemanicn_region(note):
    """(province_base, city_base) from a bemanicn 'region: 省 市' note.
    Municipalities (上海市...) have no city token; city falls back to
    the province itself."""
    m = _REGION_NOTE_RE.search(note or "")
    if not m:
        return None, None
    toks = m.group(1).split()
    prov = cn_base(toks[0])
    city = cn_base(toks[1]) if len(toks) > 1 else prov
    return prov, city


def _china_dice(ca, cb):
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    ba, bb = _bigrams(ca), _bigrams(cb)
    return 2.0 * len(ba & bb) / (len(ba) + len(bb)) if (ba or bb) else 0.0


def china_name_similarity(a, b, prov, city_a, city_b):
    """Similarity for the china_wahlap_bemanicn rule: NFKC compact names
    KEEPING parenthetical branch text, compared both raw and with the
    known province/city names stripped - wahlap official names embed the
    city ("星际传奇上海松江印象城店") while bemanicn community names
    usually omit it ("星际传奇松江印象城店")."""
    ca, cb = compact_name_exact(a), compact_name_exact(b)
    best = _china_dice(ca, cb)
    geos = sorted({g for g in (prov, city_a, city_b) if g and len(g) >= 2},
                  key=lambda g: (-len(g), g))
    for geo in geos:
        ca = ca.replace(geo, "")
        cb = cb.replace(geo, "")
    if len(ca) >= 4 and len(cb) >= 4:
        best = max(best, _china_dice(ca, cb))
    return best


def _sim_pair(na, nb):
    if not na or not nb:
        return 0.0
    ca, cb = na.replace(" ", ""), nb.replace(" ", "")
    if ca == cb:
        return 1.0
    ta, tb = set(na.split()), set(nb.split())
    tok = len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0
    ba, bb = _bigrams(ca), _bigrams(cb)
    dice = 2.0 * len(ba & bb) / (len(ba) + len(bb)) if (ba or bb) else 0.0
    return max(tok, dice)


def name_similarity(a, b):
    """Max of paren-stripped and paren-kept similarity. The paren-kept
    pass fixes audit D3's "ROUND1 MEADOWOOD MALL" vs "Round1 Reno
    (Meadowood Mall)": the branch name lives in the parentheses, and
    stripping it left nothing to match on."""
    return max(_sim_pair(norm_name(a), norm_name(b)),
               _sim_pair(_norm_text(a), _norm_text(b)))


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


# ------------------------------------------------------------------ loading -

class Stats(object):
    def __init__(self):
        self.nulled_rows = 0
        self.nulled_examples = []
        self.within_dupes = 0
        self.raw_rows = 0
        # {source: rows skipped in community.json because a fresh
        # per-source scrape file superseded them}
        self.superseded_rows = {}


def _null_zero(row, stats, origin):
    if row.get("lat") == 0 and row.get("lng") == 0:
        stats.nulled_rows += 1
        if len(stats.nulled_examples) < 100:
            stats.nulled_examples.append(
                {"file": origin, "name": row.get("name")})
        return None, None
    return row.get("lat"), row.get("lng")


def _dedupe_key(s):
    """NFKC + whitespace collapse (audit D2): allnet mixes U+3000
    ideographic spaces with ASCII spaces in otherwise identical rows."""
    return " ".join(unicodedata.normalize("NFKC", s or "").split())


def load_units(raw_dir, stats):
    """Load all raw files -> deduped source units."""
    units = {}   # (source, normalized name, normalized addr) -> unit

    def add(source, name, addr, lat, lng, games, cabs, country, pref,
            ziv_url=None, note=None, coord_system="wgs84",
            cn_prov=None, cn_city=None, bemanicn_url=None,
            game_counts=None):
        name = (name or "").strip()
        addr = (addr or "").strip()
        if not name:
            return
        gc = {}
        for slug, n in (game_counts or {}).items():
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if slug in GAME_SLUGS and n > 0:
                gc[slug] = n
        key = (source, _dedupe_key(name), _dedupe_key(addr))
        u = units.get(key)
        if u is None:
            u = {"source": source, "name": name, "addr": addr,
                 "lat": lat, "lng": lng, "games": set(), "cabs": set(),
                 "country": country, "pref": pref, "ziv_url": ziv_url,
                 "notes": [], "coord_system": coord_system,
                 "cn_prov": cn_prov, "cn_city": cn_city,
                 "bemanicn_url": bemanicn_url, "game_counts": {}}
            units[key] = u
        else:
            stats.within_dupes += 1
            if u["lat"] is None and lat is not None:
                u["lat"], u["lng"] = lat, lng
                u["coord_system"] = coord_system
            if u["pref"] is None and pref:
                u["pref"] = pref
            if u["ziv_url"] is None and ziv_url:
                u["ziv_url"] = ziv_url
            if u["cn_prov"] is None and cn_prov:
                u["cn_prov"], u["cn_city"] = cn_prov, cn_city
            if u["bemanicn_url"] is None and bemanicn_url:
                u["bemanicn_url"] = bemanicn_url
        u["games"].update(games)
        u["cabs"].update(cabs)
        # per-slug max across within-source dupes; a counted slug is
        # always also a game
        for slug, n in gc.items():
            if n > u["game_counts"].get(slug, 0):
                u["game_counts"][slug] = n
        u["games"].update(gc)
        if note and note not in u["notes"]:
            u["notes"].append(note)

    def path(fn):
        return os.path.join(raw_dir, fn + ".json")

    # --- allnet ---
    for fn, games in ALLNET_FILES.items():
        if not os.path.exists(path(fn)):
            print("merge: missing %s (skipped)" % path(fn), file=sys.stderr)
            continue
        for row in common.load_json(path(fn)):
            stats.raw_rows += 1
            lat, lng = _null_zero(row, stats, fn)
            code = str(row.get("region_code", ""))
            label = row.get("region_label") or ""
            if code.isdigit() and int(code) < 1000:
                country, pref = "Japan", (label or JP_PREFS_JA[int(code)])
            else:
                country = ALLNET_REGION_COUNTRY.get(label)
                if country is None:  # North America and anything unmapped
                    country = resolve_country(lat, lng, row.get("address"),
                                              row.get("name"))
                    if country == "Unknown" and label == "North America":
                        country = "United States"
                pref = extract_pref(country, row.get("address"))
            add("allnet", row.get("name"), row.get("address"), lat, lng,
                games, [], country, pref)

    # --- eagate ---
    for fn, (games, cabs) in EAGATE_FILES.items():
        if not os.path.exists(path(fn)):
            print("merge: missing %s (skipped)" % path(fn), file=sys.stderr)
            continue
        for row in common.load_json(path(fn)):
            stats.raw_rows += 1
            lat, lng = _null_zero(row, stats, fn)
            code = str(row.get("region_code", ""))
            pref = None
            if code.startswith("JP-"):
                idx = int(code[3:]) - 1
                if 0 <= idx < 47:
                    pref = JP_PREFS_JA[idx]
            add("eagate", row.get("name"), row.get("address"), lat, lng,
                games, cabs, "Japan", pref)

    # --- wahlap ---
    for fn, games in WAHLAP_FILES.items():
        if not os.path.exists(path(fn)):
            print("merge: missing %s (skipped)" % path(fn), file=sys.stderr)
            continue
        for row in common.load_json(path(fn)):
            stats.raw_rows += 1
            lat, lng = _null_zero(row, stats, fn)
            note = row.get("notes") or ""
            m = re.search(r"province=([^;]+)", note)
            pref = m.group(1).strip() if m else None
            add("wahlap", row.get("name"), row.get("address"), lat, lng,
                games, [], "China", pref,
                coord_system=row.get("coord_system") or "unknown")

    # --- community-schema files (community.json bundles ziv / round1usa /
    #     community rows; fresh full scrapes write ziv.json / round1usa.json
    #     in the same schema plus a country field) ---
    # A fresh per-source scrape SUPERSEDES that source's rows inside the
    # bundled community.json: without this, community.json's 4.7k ziv
    # rows and ziv.json's re-crawl BOTH load and ZIv doubles (the two
    # files' names/addresses differ cosmetically, so within-source
    # dedupe cannot collapse them). Scoped by row source, not by file,
    # because round1usa/curated rows live in community.json too and
    # must still be ingested. Conditional on the fresh file existing so
    # a checkout without it still gets the bundled rows.
    superseded = {s for s in ("ziv", "round1usa") if os.path.exists(path(s))}
    for fn, default_src in (("community", "community"), ("ziv", "ziv"),
                            ("round1usa", "round1usa")):
        if not os.path.exists(path(fn)):
            continue
        for row in common.load_json(path(fn)):
            stats.raw_rows += 1
            source = row.get("source") or default_src
            if source not in SRC_PRIORITY:
                source = "community"
            if fn == "community" and source in superseded:
                stats.superseded_rows[source] = (
                    stats.superseded_rows.get(source, 0) + 1)
                continue
            lat, lng = _null_zero(row, stats, fn)
            country = row.get("country")
            if country:
                country = {"USA": "United States", "UK": "United Kingdom",
                           "Korea": "South Korea"}.get(country, country)
            else:
                country = resolve_country(
                    lat, lng, row.get("address"), row.get("name"))
            pref = extract_pref(country, row.get("address"))
            games = [g if g in GAME_SLUGS else "other"
                     for g in (row.get("games") or ["other"])]
            add(source, row.get("name"), row.get("address"), lat, lng,
                games, [], country, pref,
                ziv_url=(row.get("source_url") if source == "ziv" else None),
                note=row.get("notes"),
                coord_system=row.get("coord_system") or "wgs84",
                game_counts=row.get("game_counts"))

    # --- bemanicn (optional) ---
    fn = "china_bemanicn"
    if os.path.exists(path(fn)):
        for row in common.load_json(path(fn)):
            stats.raw_rows += 1
            lat, lng = _null_zero(row, stats, fn)
            # entries with an empty games list (detail 404 / no known
            # cabs) map to ["other"], keeping their original note
            games = [g if g in GAME_SLUGS else "other"
                     for g in (row.get("games") or ["other"])]
            prov, city = bemanicn_region(row.get("notes"))
            # BemaniCN is a mainland-Chinese site and labels everything it
            # lists as China, including its Hong Kong and Macau shops. Left as
            # "China" those rows sit in a different country bucket from the
            # ALL.Net / e-amusement / ZIv rows for the SAME venues, so no
            # cross-source rule can ever pair them, and china_place then
            # assigns them the Hong Kong city centroid - which is in the middle
            # of Victoria Harbour. That is exactly what put a scatter of pins
            # in the water off Central and Wan Chai.
            #
            # The province in the row's own "region:" note is the authority
            # here, NOT the address text. Six mainland rows carry 香港 inside a
            # BUILDING name (香港财富广场 in Fuyang, 香港东路 in Qingdao) while
            # their region says 安徽省 / 山东省, and matching on the address
            # would drag them to Hong Kong.
            country = "China"
            if prov.startswith("香港"):
                country = "Hong Kong"
            elif prov.startswith("澳门") or prov.startswith("澳門"):
                country = "Macau"
            pref = prov or extract_pref("China", row.get("address"))
            add("bemanicn", row.get("name"), row.get("address"), lat, lng,
                games, [], country, pref, note=row.get("notes"),
                coord_system=row.get("coord_system") or "unknown",
                cn_prov=prov, cn_city=city,
                bemanicn_url=row.get("source_url"),
                game_counts=row.get("game_counts"))

    out = list(units.values())

    # (e) convert gcj02 / bd09 -> wgs84
    converted = 0
    for u in out:
        if u["lat"] is None:
            continue
        cs = (u["coord_system"] or "wgs84").lower()
        if cs == "gcj02":
            u["lat"], u["lng"] = eviltransform.gcj2wgs(u["lat"], u["lng"])
            u["coord_system"] = "wgs84"
            converted += 1
        elif cs in ("bd09", "bd-09", "bd09ll"):
            u["lat"], u["lng"] = eviltransform.bd2wgs(u["lat"], u["lng"])
            u["coord_system"] = "wgs84"
            converted += 1
        # wrap longitudes
        while u["lng"] is not None and u["lng"] > 180:
            u["lng"] -= 360
        while u["lng"] is not None and u["lng"] < -180:
            u["lng"] += 360
    stats.converted = converted
    return out


# ----------------------------------------------------------------- clusters -

class UnionFind(object):
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.p[rb] = ra
        return True


def cluster_units(units, log):
    n = len(units)
    uf = UnionFind(n)
    compacts = [compact_name_exact(u["name"]) for u in units]

    def unit_ref(i):
        u = units[i]
        return {"src": u["source"], "name": u["name"], "addr": u["addr"]}

    # spatial grid for coordinate pairs
    cell = 0.003
    grid = {}
    for i, u in enumerate(units):
        if u["lat"] is None:
            continue
        key = (math.floor(u["lat"] / cell), math.floor(u["lng"] / cell))
        grid.setdefault(key, []).append(i)

    # Collect all qualifying pairs first, then only union MUTUAL BEST
    # matches per (unit, other-source). Without this, near-identical
    # sister branches (e.g. GiGO赤羽 vs GiGO赤羽駅前, ~100 m apart) chain
    # into one cluster through their cross-source counterparts.
    pairs = {}
    for (cx, cy), members in grid.items():
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(grid.get((cx + dx, cy + dy), ()))
        for i in members:
            ui = units[i]
            for j in cand:
                if j <= i:
                    continue
                uj = units[j]
                if ui["source"] == uj["source"]:
                    continue
                if (i, j) in pairs:
                    continue
                d = haversine_m(ui["lat"], ui["lng"], uj["lat"], uj["lng"])
                if d >= 120:
                    continue
                sim = name_similarity(ui["name"], uj["name"])
                if sim < 0.6:
                    continue
                pairs[(i, j)] = (sim, d)
    best = {}   # (unit_idx, other_source) -> (sim, -dist, other_idx)
    for (i, j), (sim, d) in pairs.items():
        for a, b in ((i, j), (j, i)):
            key = (a, units[b]["source"])
            cand = (sim, -d, b)
            if key not in best or cand > best[key]:
                best[key] = cand
    for (i, j), (sim, d) in sorted(pairs.items(),
                                   key=lambda kv: (-kv[1][0], kv[1][1])):
        if (best[(i, units[j]["source"])][2] == j
                and best[(j, units[i]["source"])][2] == i):
            if uf.union(i, j):
                log.append({"rule": "dist+name", "distance_m": round(d, 1),
                            "similarity": round(sim, 3),
                            "a": unit_ref(i), "b": unit_ref(j)})

    # ---- BEGIN proximity tier (owner: stacked-pins agent) ------------
    # Bug: one physical arcade shows as two stacked pins when a community
    # source romanizes the name and an official source keeps it in kana:
    #   ziv "AmiPara Kokoja (アミパラ ここじゃ店)"  0.9 m from
    #   allnet+eagate "アミパラここじゃ店"
    # name_similarity() scores that 0.571 - just under the 0.6 gate - so
    # the pair above never unions, and the two pins also cover each other
    # so neither can be clicked. Loosening 0.6 globally is the wrong fix
    # (it is doing real work out at 120 m); instead this pass re-examines
    # ONLY what the loop above rejected, under a hard 30 m gate, with a
    # matcher that knows kana and romaji are one alphabet. Under 30 m two
    # listings are essentially never distinct businesses.
    #
    # Deliberately a SEPARATE pass, not extra entries in `pairs`: that
    # dict's mutual-best ranking is (sim, -dist), so injecting low-sim
    # coincident pairs would outrank-and-displace existing 0.6+ matches
    # and silently rewrite decisions the audit already signed off on.
    # Running afterwards, and skipping anything already unioned, means
    # this pass can only ADD merges - the existing rule's output is
    # provably untouched (verified by rule-count assertions).
    #
    # Scoped to official-vs-community pairs only. Two community sources
    # disagreeing at 5 m is exactly the ambiguous case this must not
    # guess at, and same-source pairs have their own tighter rule below.
    prox_pairs = {}
    for (cx, cy), members in grid.items():
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(grid.get((cx + dx, cy + dy), ()))
        for i in members:
            ui = units[i]
            for j in cand:
                if j <= i:
                    continue
                uj = units[j]
                # exactly one side official: the community listing is the
                # one being reconciled INTO the official record
                if (ui["source"] in OFFICIAL) == (uj["source"] in OFFICIAL):
                    continue
                if (i, j) in prox_pairs:
                    continue
                if uf.find(i) == uf.find(j):
                    continue          # already merged by the rule above
                d = haversine_m(ui["lat"], ui["lng"], uj["lat"], uj["lng"])
                if d >= name_match.PROXIMITY_MAX_M:
                    continue
                prox_pairs[(i, j)] = d

    if prox_pairs:
        # Isolation counts CLUSTERS, not units. An official venue listed
        # by both allnet and eagate is two units already unioned into one
        # cluster; counting units would see 3 "neighbours" for a lone
        # pair and the isolated-pair heuristic would never fire - which
        # is precisely the Kokoja case (allnet + eagate + ziv).
        involved = {i for pair in prox_pairs for i in pair}
        roots = {}
        for i, u in enumerate(units):
            if u["lat"] is None:
                continue
            roots.setdefault(uf.find(i), (u["lat"], u["lng"]))
        rcell = 0.001      # ~110 m: a 60 m ball fits in the 3x3 window
        rgrid = {}
        for r, (rlat, rlng) in roots.items():
            rgrid.setdefault((math.floor(rlat / rcell),
                              math.floor(rlng / rcell)), []).append(r)

        def clusters_near(i):
            """Distinct coordinate-bearing clusters within 60 m of unit i."""
            u = units[i]
            key = (math.floor(u["lat"] / rcell), math.floor(u["lng"] / rcell))
            near = set()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for r in rgrid.get((key[0] + dx, key[1] + dy), ()):
                        rlat, rlng = roots[r]
                        if (haversine_m(u["lat"], u["lng"], rlat, rlng)
                                < name_match.ISOLATION_RADIUS_M):
                            near.add(r)
            return near

        near_cache = {i: clusters_near(i) for i in involved}

        # Mutual-best per (unit, other-source), same anti-chaining guard
        # the primary rule uses: without it a row of neighbouring shops
        # daisy-chains into one blob through shared counterparts.
        decided = {}
        for (i, j), d in prox_pairs.items():
            ok, rule, sim, conf = name_match.proximity_decision(
                units[i]["name"], units[j]["name"], d,
                len(near_cache[i] | near_cache[j]))
            if ok:
                decided[(i, j)] = (sim, d, rule, conf)
        pbest = {}
        for (i, j), (sim, d, _r, _c) in decided.items():
            for a, b in ((i, j), (j, i)):
                key = (a, units[b]["source"])
                cand = (sim, -d, b)
                if key not in pbest or cand > pbest[key]:
                    pbest[key] = cand
        # One cluster may hold at most one unit per official source. An
        # official source lists a given storefront exactly once, so two
        # allnet rows in one cluster means something chained: at Bugis+
        # (Singapore) three arcades share a mall entrance, and merging
        # ziv's listing into two different allnet venues would fuse
        # PACO FUNWORLD, VIRTUALAND and TOG into one pin. Verified to
        # hold for all 2251 pre-existing clusters, so enforcing it can
        # only constrain the new tier, never undo an existing merge.
        official_in = {}
        for i, u in enumerate(units):
            if u["source"] in OFFICIAL:
                official_in.setdefault(uf.find(i), set()).add(u["source"])

        for (i, j), (sim, d, rule, conf) in sorted(
                decided.items(), key=lambda kv: (-kv[1][0], kv[1][1])):
            if (pbest[(i, units[j]["source"])][2] != j
                    or pbest[(j, units[i]["source"])][2] != i):
                continue
            ri, rj = uf.find(i), uf.find(j)
            if official_in.get(ri, set()) & official_in.get(rj, set()):
                continue          # would put one official source twice
            if uf.union(i, j):
                merged = official_in.pop(ri, set()) | official_in.pop(rj, set())
                if merged:
                    official_in[uf.find(i)] = merged
                log.append({"rule": rule, "distance_m": round(d, 1),
                            "similarity": round(sim, 3),
                            "confidence": conf,
                            "a": unit_ref(i), "b": unit_ref(j)})
    # ---- END proximity tier -----------------------------------------

    # ---- exact-name tier: one venue, two sources, two geocodes --------
    #
    # The dist+name rule above gates on 120 m, which is tuned for a FUZZY
    # name match (similarity >= 0.6). That gate is wrong when the names are
    # not fuzzy at all but byte-identical after normalization, because the
    # thing that actually separates the two rows is not the venue moving,
    # it is the two sources geocoding the same building differently. A mall
    # entrance versus its car park is routinely 150-500 m.
    #
    # Real example, reported as two icons on one store: ALL.Net lists
    # "アミューズメントパークＭＧ西条" and e-amusement lists
    # "アミューズメントパークMG西条店" - identical once NFKC folds the
    # fullwidth ＭＧ and the trailing 店 is dropped - but their pins are
    # 176 m apart, so the 120 m rule never saw the pair. 51 such pairs
    # survived, and every one inspected was a single venue: Timezone,
    # アピナ, GiGO, Kingpin, MOLLY FANTASY branches listed twice.
    #
    # So: exact name equality carries the evidence here, and distance is
    # demoted to a locality sanity bound whose only job is to stop two
    # genuinely different branches that happen to share a name from merging
    # across a city. Safeguards against over-merging:
    #
    #   * compact_name_exact KEEPS parenthetical branch names, so
    #     "GiGO(1号館)" and "GiGO(2号館)" never collapse.
    #   * a minimum length, so a bare chain name is never enough on its own.
    #   * MUTUAL-NEAREST only. If three rows in one town share a name, no
    #     pair is each other's unambiguous best and none of them merge.
    #   * cross-source only; same-source duplicates keep their tighter rule
    #     below, and pairs already clustered are skipped, so this pass can
    #     only ADD merges.
    # 3 km is not a guess about how far a venue moves, it is the measured gap
    # between the two populations. Sorting every surviving exact-name
    # cross-source pair by distance, the genuine ones run out at 2,441 m
    # (MoCity Cosmic Park, PT434 vs PT435 of one Melaka lot) and the next pair
    # is 7,746 m away and is NOT one venue ("168 GAME CENTRE" in Kwun Tong vs
    # "GAME CENTRE" in Central). 3 km sits in that gap with margin either side.
    #
    # The bound is load-bearing, not decoration: two イーグルボウル rows 722 km
    # apart, one in Towada and one in Chiryu, are a real chain sharing one name
    # with no branch suffix. An unbounded exact-name rule would fuse them.
    NAME_EXACT_MAX_M = 3000.0
    NAME_EXACT_MIN_LEN = 5
    NAME_BRAND_PREFIX_MIN = 5

    def exact_keys(name):
        """Every normalized form that counts as this venue's exact name.

        ZIv routinely writes a bilingual name, "Romaji (日本語店名)", where the
        PARENTHETICAL is the official name an operator source publishes on its
        own. compact_name_exact deliberately keeps parentheses (so two branches
        of one chain never collapse), which means the bilingual form never
        equals the official one:

            ziv     "PLAZA CAPCOM Niihama (プラサカプコン 新居浜店)"
                    -> plazacapcomniihamaプラサカプコン新居浜
            allnet  "プラサカプコン新居浜店"
                    -> プラサカプコン新居浜

        Comparing the parenthetical on its own closes that gap exactly: both
        sides reduce to プラサカプコン新居浜. The pair was 130.8 m apart with a
        name similarity of 0.526, so it missed the dist+name rule on BOTH its
        gates (120 m and 0.6) and had nothing else to catch it.

        The paren-STRIPPED form is deliberately NOT a key. "GiGO(1号館)" and
        "GiGO(2号館)" both strip to "gigo", and keying on that would fuse two
        genuinely different branches in one building. Keeping only the full
        form and the parenthetical means those two share no key at all.
        """
        keys = set()
        c = compact_name_exact(name)
        if len(c) >= NAME_EXACT_MIN_LEN:
            keys.add(c)
        inner = name_match.compact(name_match.paren_inner(name))
        if len(inner) >= NAME_EXACT_MIN_LEN:
            keys.add(inner)
        return keys

    def _common_prefix_len(a, b):
        n = 0
        while n < min(len(a), len(b)) and a[n] == b[n]:
            n += 1
        return n

    def exact_name_match(na, nb):
        """Do these two names denote the same venue by exact-name evidence?

        The key index above only proposes candidates; this makes the call,
        because not every shared key is equally strong.

        Strongest, and the common cases: the two full compact names are equal,
        or one side's parenthetical IS the other side's whole name (the ZIv
        bilingual pattern).

        Weakest, and the one that needs a guard: BOTH sides merely share a
        parenthetical. That parenthetical is frequently a shopping centre
        rather than a store, e.g. "Round1 Houston (Willowbrook Mall)" against
        "Round1 Bowling & Arcade (Willowbrook Mall)". Those two are one venue,
        but the same shape would also equate "Timezone (Westfield)" with
        "Round1 (Westfield)" - two different operators under one roof. So when
        the parenthetical is all the sides have in common, the brands outside
        the parentheses must agree as well. Every real pair in this category
        is a Round1 or Tom's World listing whose prefixes agree on at least
        six characters; a cross-operator collision agrees on zero.
        """
        fa, fb = compact_name_exact(na), compact_name_exact(nb)
        ia = name_match.compact(name_match.paren_inner(na))
        ib = name_match.compact(name_match.paren_inner(nb))
        if len(fa) >= NAME_EXACT_MIN_LEN and fa == fb:
            return True
        if len(ia) >= NAME_EXACT_MIN_LEN and ia == fb:
            return True
        if len(ib) >= NAME_EXACT_MIN_LEN and ib == fa:
            return True
        if len(ia) >= NAME_EXACT_MIN_LEN and ia == ib:
            return (_common_prefix_len(compact_name(na), compact_name(nb))
                    >= NAME_BRAND_PREFIX_MIN)
        return False

    exact_index = {}
    for i, u in enumerate(units):
        if u["lat"] is None:
            continue
        for k in exact_keys(u["name"]):
            exact_index.setdefault((u["country"], k), []).append(i)

    # Repeated to a fixed point, because mutual-nearest resolves only ONE pair
    # per group per pass and three sources naming one venue is common. At
    # AEON MALL Miyazaki the ALL.Net and e-amusement rows are 164 m apart and
    # are each other's nearest, so they pair on the first pass; the ZIv row
    # 334 m away is nearest to ALL.Net but not the reverse, so it was left
    # stranded as a second pin. Once the first two are one cluster they stop
    # being candidates for each other, ZIv becomes the unambiguous best, and
    # the second pass folds it in. Bounded, and it stops as soon as a pass
    # changes nothing.
    for _pass in range(6):
        exact_best = {}     # unit -> (dist, other) nearest qualifying partner
        for (_country, _c), idxs in exact_index.items():
            if len(idxs) < 2:
                continue
            for x in range(len(idxs)):
                for y in range(x + 1, len(idxs)):
                    i, j = idxs[x], idxs[y]
                    if units[i]["source"] == units[j]["source"]:
                        continue
                    if uf.find(i) == uf.find(j):
                        continue
                    if not exact_name_match(units[i]["name"], units[j]["name"]):
                        continue
                    d = haversine_m(units[i]["lat"], units[i]["lng"],
                                    units[j]["lat"], units[j]["lng"])
                    if d >= NAME_EXACT_MAX_M:
                        continue
                    for a, b in ((i, j), (j, i)):
                        if a not in exact_best or d < exact_best[a][0]:
                            exact_best[a] = (d, b)

        merged_any = False
        for i, (d, j) in sorted(exact_best.items()):
            if exact_best.get(j, (None, None))[1] != i:
                continue    # not mutual: ambiguous, leave both alone
            if uf.union(i, j):
                merged_any = True
                log.append({"rule": "exact-name-locality",
                            "distance_m": round(d, 1),
                            "a": unit_ref(i), "b": unit_ref(j)})
        if not merged_any:
            break

    # ---- branch-suffix tier: "Game Zone" vs "Game Zone (Mong Kok)" ----
    #
    # One source publishes the bare venue name and the other appends a branch
    # qualifier in parentheses. Reported from Hong Kong: ZIv's "Game Zone" and
    # ALL.Net's "GAMEZONE(MONG KOK)" are both B/F, 65 Argyle St, Mong Kok, but
    # they are 172 m apart with a name similarity below the 0.6 the fuzzy rule
    # needs, and no exact-name key can match them either - the whole point of
    # keeping parentheses is that the two forms differ.
    #
    # So this compares the bare name against the other side's PAREN-STRIPPED
    # name, which is the one comparison the tiers above deliberately refuse to
    # make. Refusing it is right in general: "GiGO" would otherwise match every
    # GiGO branch. What makes it safe here is the ambiguity guard - a bare-name
    # row is merged only when it has exactly ONE candidate inside the radius,
    # and that candidate has only it. A bare "GiGO" sitting between two GiGO
    # branches has two candidates and is left alone, which is the case the
    # guard exists for.
    #
    # Measured over the whole dataset: 7 qualifying pairs, none ambiguous, and
    # every one a single venue (Hong Kong's Game Zone, Taiwan's Rhythm Arena,
    # Laser Bounce Glendale, Indah Family Centre, and three Chinese venues
    # where BemaniCN parenthesises a mall or a former name).
    BRANCH_SUFFIX_MAX_M = 600.0

    branch_cands = {}   # unit -> list of (dist, other)
    base_index = {}
    for i, u in enumerate(units):
        if u["lat"] is None:
            continue
        base = compact_name(u["name"])
        if len(base) >= NAME_EXACT_MIN_LEN:
            base_index.setdefault((u["country"], base), []).append(i)

    for (_country, _base), idxs in base_index.items():
        if len(idxs) < 2:
            continue
        bare = [i for i in idxs if not name_match.paren_inner(units[i]["name"])]
        qual = [i for i in idxs if name_match.paren_inner(units[i]["name"])]
        for i in bare:
            for j in qual:
                if units[i]["source"] == units[j]["source"]:
                    continue
                if uf.find(i) == uf.find(j):
                    continue
                d = haversine_m(units[i]["lat"], units[i]["lng"],
                                units[j]["lat"], units[j]["lng"])
                if d >= BRANCH_SUFFIX_MAX_M:
                    continue
                branch_cands.setdefault(i, []).append((d, j))
                branch_cands.setdefault(j, []).append((d, i))

    for i, cand in sorted(branch_cands.items()):
        if len(cand) != 1:
            continue                      # ambiguous: this row has rivals
        d, j = cand[0]
        if len(branch_cands.get(j, [])) != 1:
            continue                      # the partner has rivals of its own
        if uf.union(i, j):
            log.append({"rule": "exact-name-branch-suffix",
                        "distance_m": round(d, 1),
                        "a": unit_ref(i), "b": unit_ref(j)})

    # same-source near-duplicates (audit D3): one source listing the
    # same physical store twice with cosmetically different address
    # strings (Woking Superbowl, Funworld Sun East Mall). Very tight:
    # identical compact name AND coords within 30 m.
    for (cx, cy), members in grid.items():
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(grid.get((cx + dx, cy + dy), ()))
        for i in members:
            ui = units[i]
            for j in cand:
                if j <= i:
                    continue
                uj = units[j]
                if ui["source"] != uj["source"]:
                    continue
                if compacts[i] != compacts[j] or len(compacts[i]) < 3:
                    continue
                d = haversine_m(ui["lat"], ui["lng"], uj["lat"], uj["lng"])
                if d >= 30:
                    continue
                if uf.union(i, j):
                    log.append({"rule": "same-source-dup",
                                "distance_m": round(d, 1),
                                "a": unit_ref(i), "b": unit_ref(j)})

    # exact-name path when one side lacks coords (same country, diff source)
    # Bucketed on the same key set the coord-based tier uses, not on the full
    # compact name alone. Mainland China rows arrive here coordinate-less (the
    # sources publish addresses only, and china_place assigns centroids AFTER
    # merge), so this path is the only chance those rows get - and ZIv writes
    # them bilingually, exactly the shape a full-compact key cannot match:
    #
    #   ziv       "汤姆熊欢乐世界 Tom's World (上海南翔印象城店)"
    #   bemanicn  "汤姆熊欢乐世界(上海南翔印象城店)"
    #
    # Those never shared a bucket, so both survived and later drew two pins,
    # one on a real coordinate and one on a city centroid kilometres away.
    # exact_name_match below still makes the accept/reject call, so the extra
    # buckets only widen what is CONSIDERED, never what is accepted.
    by_compact = {}
    for i, u in enumerate(units):
        ks = set(exact_keys(u["name"]))
        if len(compacts[i]) >= 3:
            ks.add(compacts[i])
        for k in ks:
            by_compact.setdefault(k, []).append(i)
    for c, idxs in by_compact.items():
        if len(idxs) < 2:
            continue
        for x in range(len(idxs)):
            for y in range(x + 1, len(idxs)):
                i, j = idxs[x], idxs[y]
                ui, uj = units[i], units[j]
                if ui["source"] == uj["source"]:
                    continue
                if compacts[i] != compacts[j] and not exact_name_match(
                        ui["name"], uj["name"]):
                    continue
                ci, cj = ui["country"], uj["country"]
                if (ci not in (None, "Unknown") and cj not in (None, "Unknown")
                        and ci != cj):
                    continue
                a_no = ui["lat"] is None
                b_no = uj["lat"] is None
                if not (a_no or b_no):
                    continue  # both have coords: distance rule only
                if a_no and b_no:
                    # both coordinate-less: exact (name, address) only
                    if (norm_name(ui["addr"]) != norm_name(uj["addr"])
                            or not ui["addr"]):
                        continue
                    rule = "exact-name-addr-coordless"
                else:
                    rule = "exact-name-one-coordless"
                if uf.union(i, j):
                    log.append({"rule": rule, "a": unit_ref(i),
                                "b": unit_ref(j)})

    # Hong Kong / Macau rule: BemaniCN publishes those shops with a precise
    # Chinese address and NO coordinates, while ALL.Net, e-amusement and ZIv
    # publish the same venues in English WITH coordinates. Nothing above can
    # pair them - the names share no script ("168遊戲機中心" against
    # "168 GAME CENTRE", "珍宝游戏机中心" against "JUMBO GAME") and one side has
    # no pin to measure a distance from.
    #
    # The STREET NUMBER survives translation, and in a territory this dense it
    # is specific. "300-302", "557-559", "290-296" identify a building outright.
    #
    # Two things had to be handled before this was trustworthy, both found by
    # checking the output rather than by reasoning about it:
    #
    #   * Unit codes are not street numbers. "SHOP A15" made three different
    #     BemaniCN rows match INTERNATIONAL GAMES CENTRE on "15". A digit run
    #     glued to an ASCII letter is therefore ignored. The check is
    #     ASCII-specific on purpose: Python treats CJK as alphabetic, so a
    #     plain isalpha() test rejected "道300" and matched nothing at all.
    #   * Small numbers are weak. Only ranges and numbers >= 10 count.
    #
    # Then a two-way uniqueness guard: a row merges only when it has exactly
    # one partner AND that partner has only it, so a number appearing on both
    # sides of two different venues merges neither.
    #
    # Result: 10 pairs, each independently corroborated by the names once
    # translated (金星 = Gold Star, 荷里活 = Hollywood, 珍宝 = Jumbo,
    # 紅棉 = Hung Min, 西岸國際 = West Coast, RETROCITY CONCEPT verbatim).
    HK_COUNTRIES = ("Hong Kong", "Macau")

    def _hk_street_numbers(addr):
        s = (addr or "").replace("號", "").replace("号", "")
        out = set()
        for m in re.finditer(r"[0-9]{1,4}(?:\s*-\s*[0-9]{1,4})?", s):
            tok = m.group(0).replace(" ", "")
            prev = s[m.start() - 1] if m.start() else ""
            if prev.isascii() and prev.isalpha():
                # A15 / B03 / G71 are unit codes, not street numbers. A RANGE
                # is exempt: the official addresses run words into the number
                # ("TAI ON BLDG57-87SHAU KEI WAN RD"), and "57-87" is a street
                # range whatever precedes it.
                if "-" not in tok:
                    continue
            if "-" in tok or (tok.isdigit() and int(tok) >= 10):
                out.add(tok)
        return out

    # Edges are keyed by CLUSTER, not by unit. A venue already merged from
    # ALL.Net and ZIv is two units, and counting them separately made a
    # BemaniCN row matching both halves of ONE venue look ambiguous and merge
    # with neither - which is how Plaza Hollywood stayed split despite both
    # sides plainly reading 383.
    hk_edge = {}        # (root_a, root_b) -> (i, j, shared numbers)
    hk_partners = {}    # root -> set of partner roots
    hk_idx = [i for i, u in enumerate(units) if u["country"] in HK_COUNTRIES]
    for x in range(len(hk_idx)):
        for y in range(x + 1, len(hk_idx)):
            i, j = hk_idx[x], hk_idx[y]
            ui, uj = units[i], units[j]
            if ui["source"] == uj["source"]:
                continue
            if ui["country"] != uj["country"]:
                continue
            ra, rb = uf.find(i), uf.find(j)
            if ra == rb:
                continue
            # exactly one side coordinate-less: the other supplies the pin
            if (ui["lat"] is None) == (uj["lat"] is None):
                continue
            shared = _hk_street_numbers(ui["addr"]) & _hk_street_numbers(uj["addr"])
            if not shared:
                continue
            key = (min(ra, rb), max(ra, rb))
            hk_edge.setdefault(key, (i, j, sorted(shared)))
            hk_partners.setdefault(ra, set()).add(rb)
            hk_partners.setdefault(rb, set()).add(ra)

    for (ra, rb), (i, j, sh) in sorted(hk_edge.items()):
        if len(hk_partners.get(ra, ())) != 1 or len(hk_partners.get(rb, ())) != 1:
            continue                          # ambiguous on either side
        if uf.union(i, j):
            log.append({"rule": "hk-street-number", "numbers": sh,
                        "a": unit_ref(i), "b": unit_ref(j)})

    # China rule (wahlap x bemanicn): both sources are coordinate-less,
    # so the global rules cannot merge them and the China list would
    # double. Scoped to China: same province, city-gated (bemanicn knows
    # its city from the region note; the wahlap city is recognized in
    # the official name/address), NFKC name similarity >= 0.8 with
    # parenthetical branch text KEPT. Each bemanicn unit unions with its
    # single best wahlap match only.
    bem_idx = [i for i, u in enumerate(units) if u["source"] == "bemanicn"]
    wah_idx = [i for i, u in enumerate(units) if u["source"] == "wahlap"]
    if bem_idx and wah_idx:
        cities = {}   # province base -> known city bases (from bemanicn)
        for i in bem_idx:
            u = units[i]
            if u["cn_prov"]:
                cities.setdefault(u["cn_prov"], set()).add(u["cn_city"])
        wah_by_prov = {}
        for j in wah_idx:
            u = units[j]
            prov = cn_base(u["pref"])
            u["cn_prov"] = prov
            hay = "%s %s" % (u["name"], u["addr"])
            for c in sorted(cities.get(prov, ()),
                            key=lambda s: (-len(s or ""), s or "")):
                if c and c != prov and len(c) >= 2 and c in hay:
                    u["cn_city"] = c
                    break
            wah_by_prov.setdefault(prov, []).append(j)
        for i in bem_idx:
            ui = units[i]
            prov, city = ui["cn_prov"], ui["cn_city"]
            if not prov:
                continue
            best = (0.0, None)
            for j in wah_by_prov.get(prov, ()):
                uj = units[j]
                wc = uj["cn_city"]
                if wc and city and wc != city and city != prov:
                    continue      # cities known on both sides and differ
                sim = china_name_similarity(ui["name"], uj["name"],
                                            prov, city, wc)
                if sim > best[0]:
                    best = (sim, j)
            if best[1] is not None and best[0] >= 0.8:
                j = best[1]
                if uf.union(j, i):
                    log.append({"rule": "china_wahlap_bemanicn",
                                "similarity": round(best[0], 3),
                                "province": prov,
                                "a": unit_ref(j), "b": unit_ref(i)})
    groups = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    return groups


# -------------------------------------------------------------------- merge -

def merged_entry(units, idxs, inherit_log, conflict_log):
    members = sorted(
        (units[i] for i in idxs),
        key=lambda u: (SRC_PRIORITY[u["source"]], u["lat"] is None,
                       -len(u["addr"])))
    best = members[0]
    coord_u = next((u for u in members if u["lat"] is not None), None)
    lat = lng = None
    inherited_from = None
    if coord_u is not None:
        lat, lng = coord_u["lat"], coord_u["lng"]
        if (coord_u["source"] not in OFFICIAL
                and any(u["source"] in ("wahlap", "bemanicn")
                        for u in members)):
            inherited_from = coord_u["source"]
    games = set()
    cabs = set()
    src = set()
    notes = []
    ziv_url = None
    bemanicn_url = None
    pref = None
    country = best["country"]
    game_counts = {}
    counts_contributors = set()   # (m) which sources actually counted
    for u in members:
        games |= u["games"]
        cabs |= u["cabs"]
        src.add(u["source"])
        # cross-source counts: per-slug max (bemanicn where only it
        # knows a slug, ziv where only it does, max when both do)
        if u["game_counts"]:
            counts_contributors.add(u["source"])
        for slug, n in u["game_counts"].items():
            if n > game_counts.get(slug, 0):
                game_counts[slug] = n
        for nt in u["notes"]:
            if nt and nt not in notes:
                notes.append(nt)
        if ziv_url is None and u["ziv_url"]:
            ziv_url = u["ziv_url"]
        if bemanicn_url is None and u["bemanicn_url"]:
            bemanicn_url = u["bemanicn_url"]
        if pref is None and u["pref"]:
            pref = u["pref"]
        if (u["country"] not in (None, "Unknown") and country
                in (None, "Unknown")):
            country = u["country"]
    if best["source"] == "wahlap":
        # keep the (differing) community address for reference
        for u in members:
            if (u["source"] == "bemanicn" and u["addr"]
                    and norm_name(u["addr"]) != norm_name(best["addr"])):
                bn = "bemanicn addr: " + u["addr"]
                if bn not in notes:
                    notes.append(bn)
    countries = {u["country"] for u in members
                 if u["country"] not in (None, "Unknown")}
    if len(countries) > 1:
        conflict_log.append({
            "kept": country,
            "members": [{"src": u["source"], "name": u["name"],
                         "country": u["country"]} for u in members]})
    if inherited_from:
        notes.append("inherited:true (coords from %s)" % inherited_from)
        inherit_log.append({
            "coordless": [u["name"] for u in members
                          if u["source"] in ("wahlap", "bemanicn")],
            "coords_from": {"src": coord_u["source"], "name": coord_u["name"]},
            "lat": lat, "lng": lng})
    note_str = " | ".join(notes) if notes else None
    if note_str and len(note_str) > 800:
        note_str = note_str[:797] + "..."
    if lat is not None:
        gmaps = ("https://www.google.com/maps/search/?api=1&query=%.7f,%.7f"
                 % (lat, lng))
    else:
        import urllib.parse
        q = urllib.parse.quote(("%s %s" % (best["name"], best["addr"])).strip())
        gmaps = "https://www.google.com/maps/search/?api=1&query=" + q
    games |= set(game_counts)   # a counted slug is always also a game
    entry = {
        "name": best["name"],
        "addr": best["addr"],
        "lat": lat,
        "lng": lng,
        "country": country or "Unknown",
        "pref": pref,
        "games": sorted(games),
        "cabs": sorted(cabs),
        "src": sorted(src, key=lambda s: SRC_PRIORITY[s]),
        "links": {"gmaps": gmaps, "ziv": ziv_url, "bemanicn": bemanicn_url},
        "notes": note_str,
    }
    # ---- BEGIN counts confidence (owner: counts-honesty agent) -------
    # (m) A ZIv per-game count of exactly 1 is NOT a measured quantity.
    # ZIv's payload is a machine LIST and one row per game version is the
    # baseline shape, so tallying it yields 1 for any title the arcade
    # merely HAS. Rendering that as "x1" states a fact the source never
    # asserted. BemaniCN counts are real 台数 (a per-title `quantity`
    # field), so they are always trustworthy.
    #
    # Rule, applied after the per-slug max above so no count is lost
    # before the decision:
    #   bemanicn contributed          -> keep, counts_src "bemanicn"
    #                                    (bemanicn WINS when both did)
    #   ziv only, any slug >= 2       -> keep ALL its counts, "ziv".
    #                                    A 2 proves someone really
    #                                    tallied that arcade's list, so
    #                                    its 1s are then real 1s too.
    #   ziv only, every slug == 1     -> DROP game_counts entirely and
    #                                    set counts_src null. Placeholder
    #                                    -only data must not render.
    # counts_src is written ONLY when some source reported counts:
    #   "bemanicn"/"ziv" = these counts are real (game_counts present),
    #   null             = counts existed but were placeholder-only and
    #                      were dropped (game_counts absent),
    #   key absent       = no source ever counted this arcade.
    # That keeps "suppressed placeholder" distinguishable from "never
    # counted", which a bare missing key would erase.
    #
    # Note the ordering above: `games |= set(game_counts)` already ran,
    # so a dropped slug still shows as a GAME here - we are removing a
    # quantity claim, never the fact that the machine exists.
    counts_src = None
    if counts_contributors:
        unexpected = counts_contributors - {"bemanicn", "ziv"}
        assert not unexpected, (
            "game_counts from unexpected source(s) %s for %s - counts_src "
            "only documents bemanicn|ziv; teach this rule about the new "
            "source before shipping it" % (sorted(unexpected), best["name"]))
        if "bemanicn" in counts_contributors:
            counts_src = "bemanicn"
        elif any(n >= 2 for n in game_counts.values()):
            counts_src = "ziv"
        else:
            # placeholder-only: drop the quantities, keep the games.
            # `games |= set(game_counts)` ran above, so this must hold;
            # asserted rather than assumed because a future reorder of
            # that union would silently delete games instead of counts.
            assert set(game_counts) <= set(entry["games"]), \
                (best["name"], sorted(game_counts), entry["games"])
            game_counts = {}
            counts_src = None
        entry["counts_src"] = counts_src
    if game_counts:
        entry["game_counts"] = {s: game_counts[s]
                                for s in sorted(game_counts)}
    # ---- END counts confidence ---------------------------------------
    return entry


def run(raw_dir, out_dir, updated=None):
    stats = Stats()
    units = load_units(raw_dir, stats)
    print("merge: %d raw rows -> %d source units (%d within-source dupes, "
          "%d rows with (0,0) coords nulled, %d gcj02/bd09 converted)"
          % (stats.raw_rows, len(units), stats.within_dupes,
             stats.nulled_rows, stats.converted), file=sys.stderr)
    for s, n in sorted(stats.superseded_rows.items()):
        print("merge: %d community.json %s row(s) superseded by a fresh "
              "%s.json scrape" % (n, s, s), file=sys.stderr)
    merge_decisions = []
    groups = cluster_units(units, merge_decisions)
    inherit_log = []
    conflict_log = []
    arcades = [merged_entry(units, idxs, inherit_log, conflict_log)
               for idxs in groups.values()]
    arcades.sort(key=lambda a: (a["country"], a["name"].casefold(),
                                a["addr"]))
    for i, a in enumerate(arcades, 1):
        a["id"] = i
    # reorder keys for output (game_counts / counts_src are optional)
    ordered = [{k: a[k] for k in
                ("id", "name", "addr", "lat", "lng", "country", "pref",
                 "games", "game_counts", "counts_src", "cabs", "src",
                 "links", "notes")
                if k in a} for a in arcades]

    # (j) source-aware geo validation: official sources trust the
    # address/country and drop out-of-country geocodes; community sources
    # trust the pin and correct a wrong country label. See geo_validate.py.
    geo_log = geo_validate.validate_arcades(ordered, COUNTRY_BOXES)
    if geo_log:
        print("merge: geo_validation changed %d entries"
              % len(geo_log), file=sys.stderr)

    # --- China approximate placement (owner: china-placement agent) ----
    # (l) The two Chinese sources are coordinate-less by construction
    # (wahlap's API returns no lat/lng; bemanicn login-walls its
    # coordinates), leaving ~5.9k China rows invisible on the map even
    # though we know their city. china_place resolves each to its city
    # centroid from data/china_cities.json and marks it "approx": true.
    # Runs AFTER geo_validation on purpose: validation may null an
    # out-of-country geocode, and such a row then becomes eligible for a
    # centroid here. place_approx() self-guards - it refuses any entry
    # that already has coords (so a real pin is never overwritten and
    # "approx" is never set on one), any non-China/HK/Macau country, and
    # anything labeled Taiwan (china_cities.json has no Taiwan rows and a
    # bare substring match would drop Taiwanese addresses onto the
    # mainland; ZIv already covers Taiwan with real pins). Unresolved
    # rows keep lat/lng null. Deliberately NOT touched here: links.gmaps.
    # Coordless entries got a name+address *search* URL above, which is
    # strictly more useful than a pin 600 m from a city centroid, so the
    # link must stay as built - do not "sync" it to the new coords.
    # Note "approx" lands at the end of each entry dict (the key-order
    # comprehension above already ran); that is accepted, not an
    # oversight - geo_validate and this step both operate on `ordered`.
    approx_log = china_place.place_arcades(ordered)
    if approx_log:
        print("merge: china_place placed %d coordless China entries at "
              "city centroids (approx:true)" % len(approx_log),
              file=sys.stderr)
    # --- end China approximate placement ------------------------------

    # ------- validation (hard fails) -------
    for a in ordered:
        assert a["games"], "empty games for %s" % a["name"]
        assert all(g in GAME_SLUGS for g in a["games"]), a["games"]
        assert all(c in CAB_SLUGS for c in a["cabs"]), a["cabs"]
        gc = a.get("game_counts", {})
        assert set(gc) <= set(a["games"]), (a["name"], gc, a["games"])
        assert all(isinstance(n, int) and n > 0 for n in gc.values()), \
            (a["name"], gc)
        # (m) counts confidence invariants
        if "counts_src" in a:
            cs = a["counts_src"]
            assert cs in ("bemanicn", "ziv", None), (a["name"], cs)
            # game_counts present exactly when the counts were kept
            assert ("game_counts" in a) == (cs is not None), (a["name"], cs)
            # a dropped ziv-placeholder entry must still list the games
            if cs is None:
                assert a["games"], a["name"]
            if cs == "ziv":
                assert any(n >= 2 for n in gc.values()), (a["name"], gc)
        else:
            assert "game_counts" not in a, a["name"]
        if a["lat"] is not None:
            assert -90 <= a["lat"] <= 90 and -180 <= a["lng"] <= 180, a
            assert not (a["lat"] == 0 and a["lng"] == 0), a

    # (m) counts confidence distribution, for the merge log only. Kept
    # OUT of stats.json/counts: the frontend reads that shape.
    counts_src_dist = {"bemanicn": 0, "ziv": 0,
                       "null_placeholder_dropped": 0, "absent_never_counted": 0}
    for a in ordered:
        if "counts_src" not in a:
            counts_src_dist["absent_never_counted"] += 1
        elif a["counts_src"] is None:
            counts_src_dist["null_placeholder_dropped"] += 1
        else:
            counts_src_dist[a["counts_src"]] += 1
    print("merge: counts_src bemanicn=%d ziv=%d null(dropped placeholder)=%d "
          "absent(never counted)=%d"
          % (counts_src_dist["bemanicn"], counts_src_dist["ziv"],
             counts_src_dist["null_placeholder_dropped"],
             counts_src_dist["absent_never_counted"]), file=sys.stderr)

    by_game = {g: 0 for g in GAME_SLUGS}
    by_source = {}
    by_country = {}
    for a in ordered:
        for g in a["games"]:
            by_game[g] += 1
        for s in a["src"]:
            by_source[s] = by_source.get(s, 0) + 1
        by_country[a["country"]] = by_country.get(a["country"], 0) + 1
    by_game = {g: c for g, c in by_game.items() if c}
    counts = {
        "total": len(ordered),
        "by_game": by_game,
        "by_source": dict(sorted(by_source.items())),
        "by_country": dict(sorted(by_country.items(),
                                  key=lambda kv: -kv[1])),
    }
    updated = updated or date.today().isoformat()
    os.makedirs(out_dir, exist_ok=True)
    common.save_json(os.path.join(out_dir, "arcades.json"),
                     {"updated": updated, "counts": counts,
                      "arcades": ordered})
    common.save_json(os.path.join(out_dir, "stats.json"),
                     {"updated": updated, "counts": counts})

    # --- enrichment (owner: enrichment agent) -------------------------
    # (k) optional per-arcade extras (transit prose, coin/credit pricing,
    # photos, hours, venue websites) are written to a SEPARATE
    # data/enrichment.json keyed by merged id, so arcades.json - the file
    # every visitor downloads - stays lean and the frontend fetches
    # enrichment on demand. Joins raw rows to merged entries on the
    # source-native links.bemanicn / links.ziv URLs, so nothing here
    # touches load_units or merged_entry. `ordered` is NOT mutated.
    enrichment = enrich.build_enrichment(ordered, raw_dir, updated)
    common.save_json(os.path.join(out_dir, enrich.OUTFILE), enrichment)
    print("merge: enrichment for %d/%d arcades -> %s"
          % (enrichment["counts"]["arcades_enriched"], len(ordered),
             enrich.OUTFILE), file=sys.stderr)
    # --- end enrichment ----------------------------------------------

    common.save_json(os.path.join(out_dir, "merge_log.json"), {
        "updated": updated,
        "raw_rows": stats.raw_rows,
        "source_units": len(units),
        "within_source_dupes": stats.within_dupes,
        "community_rows_superseded": dict(sorted(
            stats.superseded_rows.items())),
        "zero_coord_rows_nulled": stats.nulled_rows,
        "zero_coord_examples": stats.nulled_examples,
        "gcj02_bd09_converted": stats.converted,
        "counts_src_distribution": counts_src_dist,   # (m)
        "cross_source_merges": len(merge_decisions),
        "coord_inheritances": len(inherit_log),
        "country_conflicts": conflict_log,
        "inheritance_log": inherit_log,
        "merge_decision_log": merge_decisions,
        "geo_validation": geo_log,
        "china_approx": approx_log,   # owner: china-placement agent
    })
    print("merge: wrote %d arcades to %s" % (len(ordered), out_dir),
          file=sys.stderr)
    return counts


def main():
    ap = argparse.ArgumentParser(description="merge raw sources")
    ap.add_argument("--raw", default="data_raw")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    counts = run(args.raw, args.out)
    print(json.dumps(counts, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
