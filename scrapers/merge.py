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
     Hong Kong and Macau add two more tiers, because no name rule can
     bridge an official English listing and BemaniCN's Chinese one:
     `hk-street-number` pairs them on a street number that survives
     translation, and `hk-locality-brand` pairs them on the operator's
     own Latin branding plus the locality, for the case where the two
     sources cite different faces of one corner building (65 Argyle
     Street and 688 Nathan Road are both Argyle Centre). Locality
     aliases are mined from ZIv's bilingual Hong Kong addresses, never
     hand-listed.
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
 (m) counts confidence, decided per slug from "count_evidence":
       bemanicn_qty  BemaniCN's per-title 台数. A real quantity.
       ziv_comment   A human stated a quantity on the ZIv listing ("12
                     machines", "4x"). A real quantity.
       ziv_listed    Nobody stated one. ZIv's payload lists one row per
                     game version, so a bare tally is a LOWER BOUND: any
                     title the arcade merely has tallies to 1, and two
                     versions - or two titles sharing one slug,
                     GuitarFreaks and DrumMania under `gitadora` - tally
                     to 2.
     An entry publishes game_counts when any slug carries real evidence,
     or when _ziv_counts_tallied vouches for a listed-only row (some slug
     counts MORE machines than that row lists distinct titles for it,
     so a title is repeated and the list was entered machine by machine,
     which makes its 1s real 1s too). Everything else is dropped with
     counts_src null, so placeholder data never renders as "x1".
     counts_src stays the four-value vocabulary the UI reads: bemanicn |
     ziv | null (dropped) | key absent (nobody counted). ALL.Net and
     e-amusement publish no quantities at all, so venues known only to
     them land in "absent" and the panel says counts are unavailable.
     count_evidence ships beside game_counts so the UI can render a
     listed 12 as "12 listed" rather than "x12". Dropping a count never
     drops the game - games is unioned first.
     cab_models (per hardware variant: Lightning, Valkyrie, gold cab,
     regional Taiko builds) is published independently of that gate - a
     cabinet model is a fact about the room, not a quantity claim.
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
     lat/lng) are placed at the centroid of the finest administrative
     unit their address names - the district where one is named, the
     prefecture-level city otherwise - from data/china_areas.json,
     flagged "approx": true, tagged "approx_level", and noted
     "position approximate: <level> centroid (<area>)". Every step is
     gated by the one above it through the table's parent-id chain,
     so a district can only ever be matched inside the city already
     resolved. Runs after geo validation, never touches an entry that
     already has coords, hard-skips Taiwan / Hong Kong / Macau, and
     places pins sharing an area on that point exactly rather than
     fanning them out. Logged to merge_log.json under "china_approx".
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
import geocode_cn     # opt-in street geocode cache (see (l))
import hk_match      # Cantonese-reading bridge for the Hong Kong tier
import name_match     # romanization-aware proximity tier (see (c))
import ziv            # title -> slug lookup for the counts test (see (m))

GAME_SLUGS = [
    "maimai_dx", "chunithm", "ongeki", "project_diva", "sdvx", "iidx",
    "ddr", "polaris_chord", "gitadora", "jubeat", "popn", "nostalgia",
    "drs", "dance_around", "dance_evo", "museca", "reflec", "taiko",
    # Six titles ziv.py already slugs out of the `other` bucket and this list
    # used to throw straight back into it, one line below at the `g if g in
    # GAME_SLUGS else "other"` guard. The scraper was right and the guard
    # silently overruled it, so 1,541 real rhythm-game venues rendered as an
    # unnamed grey chip: 1,562 Pump It Up rows, 597 StepManiaX, 252 WACCA,
    # 225 Groove Coaster, 51 crossbeats, 8 BeatStream.
    # maimai CLASSIC is deliberately NOT here even though ziv.py promotes it
    # too. A FiNALE cabinet is a maimai store's other cabinet, not a separate
    # venue category, and it is already modelled as the maimai_classic cab
    # variant that carries the offline warning. Giving it a slug as well would
    # make the 46 stores holding both show a "maimai" chip AND a "FiNALE"
    # badge for the same machine. Six, not seven; js/state.js GAMES agrees.
    "pump_it_up", "stepmaniax", "wacca", "groove_coaster", "crossbeats",
    "beatstream",
    "other",
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


_CN_DIGITS = {"零": "0", "一": "1", "二": "2", "两": "2", "三": "3",
              "四": "4", "五": "5", "六": "6", "七": "7", "八": "8",
              "九": "9", "十": "10"}


def cn_digits(s):
    """Chinese numerals -> ASCII, so 江北一店 and 江北1店 compare equal."""
    s = s or ""
    for k, v in _CN_DIGITS.items():
        s = s.replace(k, v)
    return s


# A "container" is the mall/building a venue sits inside. The 2-5 chars
# immediately before one are its name, which is the single most reliable
# thing distinguishing two branches of one chain in the same district.
# Deliberately NO bare 城 / 中心 / 乐园 here. Those are the generic words
# Chinese arcades put in their own names - 电玩城 means "arcade" and
# 家庭娱乐中心 means "family entertainment centre" - so treating them as
# building names made "酷玩时代兰州城关店" and "酷玩时代电玩城" look like
# two different buildings (兰州城 vs 电玩城) and rejected a true
# duplicate. A container word only counts when it can only be a venue.
_CN_CONTAINER = (r"(?:购物公园|购物中心|商业广场|广场|天街|大悦城|万达|"
                 r"吾悦|印象城|荟聚|银泰|龙湖|万象城|大融城|红场|奥莱|"
                 r"奥特莱斯|百货|商场|商城|大厦|步行街|生活广场)")
_CN_LANDMARK_RE = re.compile(r"[一-鿿]{2,5}?" + _CN_CONTAINER)
# Bare chain-container words that are themselves the landmark: every
# 万达广场 in a city is a different 万达广场, but "万达" vs "吾悦" in one
# district is decisive on its own.
_CN_BARE_LANDMARKS = ("大悦城", "万达", "吾悦", "印象城", "荟聚", "银泰",
                      "万象城", "大融城", "红场", "天街", "永旺", "梦乐城",
                      "恒隆", "天河城", "三峡广场", "世界城", "香港城",
                      "悦荟", "水游城", "禧欢里", "南风里", "苏宁",
                      "合胜", "金沙", "龙湖", "凯德", "宝龙", "百盛",
                      "步行街", "新天地", "奥莱", "SM广场", "KKMALL",
                      "INPARK", "MIXC", "IN99")
# Branch discriminator: 一店/二店, A店/B店, 1号店. These are how a chain
# says "this is our OTHER shop in the same mall", so a disagreement here
# is a hard reject no matter how similar the names are.
_CN_BRANCH_RE = re.compile(r"(?<![0-9])([0-9]{1,2}|[A-Za-z])号?店")


_CN_ADMIN_RE = re.compile(r"(省|自治区|特别行政区|市辖区|市|区|县|镇|乡|"
                          r"街道|新区|店)")


def cn_landmarks(text):
    """Building/mall tokens named by `text`."""
    out = set()
    s = cn_digits(text or "")
    up = s.upper()
    for m in _CN_LANDMARK_RE.finditer(s):
        if len(m.group(0)) >= 3:
            out.add(m.group(0))
    for k in _CN_BARE_LANDMARKS:
        if k in s or (k.isascii() and k in up):
            out.add(k)
    return out


def cn_branch_markers(name):
    return set(_CN_BRANCH_RE.findall(cn_digits(name or "")))


def cn_brand_key(name):
    """Chain name with branch parenthetical and romanized echo removed.

    "乐玩客潮玩城 Fun Guest (沙坪坝店)" -> "乐玩客潮玩城". Two listings of
    one venue almost always agree on a long prefix of this; two branches
    of one chain agree on a SHORTER one and then diverge into different
    place names, which is what the residue test below reads.
    """
    s = unicodedata.normalize("NFKC", cn_digits(name or ""))
    s = re.sub(r"[（(].*?[)）]", "", s)
    return re.sub(r"[A-Za-z0-9\s\-–—_,，。、·'\"!]+", "", s)


def cn_full_key(name):
    """Like cn_brand_key but KEEPING parenthetical text - the branch name
    frequently lives only in there ("宝贝王（禧欢里店）")."""
    s = unicodedata.normalize("NFKC", cn_digits(name or ""))
    s = s.replace("（", "(").replace("）", ")")
    return re.sub(r"[A-Za-z0-9\s\-–—_,，。、·'\"!()]+", "", s)


def _common_prefix_len(a, b):
    n = 0
    while n < len(a) and n < len(b) and a[n] == b[n]:
        n += 1
    return n


# A place name is the 2-3 chars immediately before an admin suffix.
# This only fires on the explicit forms (荆州市 / 洪湖市 / 江津区), which
# is the conservative direction: a missed city cannot cause a false
# merge, it just falls through to the landmark and distance tests.
_CN_PLACE_RE = re.compile(r"([一-鿿]{2,3})(?:市|县|区|州|盟|旗)")
# Words that are part of a district name rather than a place: every city
# has a 新区 and an 开发区, so they carry no discriminating information.
_CN_PLACE_SKIP = {"新区", "城区", "郊区", "开发", "高新"}


def cn_place_names(text):
    return {m for m in _CN_PLACE_RE.findall(cn_digits(text or ""))
            if m not in _CN_PLACE_SKIP}


def _landmarks_overlap(la, lb):
    """Substring containment counts as agreement: "南岗区哈西万达"
    contains "万达", and both mean the same building."""
    for x in la:
        for y in lb:
            if x in y or y in x:
                return True
    return False


CN_BRAND_MIN = 3      # CJK chars of shared brand prefix required
# A big Chinese mall is 200-500 m across and the two sources pin
# different doors of it, so same-building pairs routinely sit 100-400 m
# apart. The median confirmed-duplicate separation is 31 m, the 99th
# percentile 383 m.
CN_MAX_M = 500.0
# ...but a shared brand with no building evidence is much weaker, so
# that case gets a tighter gate. Measured over all China pairs passing
# the name test: the 60-200 m band is 402 pairs and reads as almost
# entirely one-venue-two-rows ("汤姆熊欢乐世界 Tom's World (金山店)" vs
# "汤姆熊欢乐世界（金山店）"), because the two sources pin different
# doors of one mall. Past ~200 m brand-only pairs start being genuinely
# different shops of one chain, so that is where this stops.
CN_BRAND_ONLY_M = 200.0


def cn_same_venue_evidence(a_name, b_name):
    """(compatible, reason) for two nearby China listings.

    Name similarity gets this exactly backwards, which is why the rule
    does not use it: "爱玩嘉年华(重庆江北一店)" and "爱玩嘉年华(重庆江北
    二店)" score 0.95 similar and are two different shops, while
    "51区天津南开大悦城店" and "51区超级乐园 AREA-51 (Tianjin)" share
    almost no characters and are one shop.

    What actually decides it is two independent tests:
      1. do the names share a real chain-brand prefix, and
      2. does the text AFTER that brand name a different building or a
         different numbered branch?
    Test 2 is the rejector, and it is read only off the NAMES. Addresses
    are not trustworthy enough to reject on here - the two sources
    routinely disagree about the building because one fell back to a
    district-level geocode, and rejecting on that discarded true
    duplicates sitting 0 m apart (宝贝王石家庄西桥禧欢里店 vs
    宝贝王（禧欢里店）, whose addresses name 禧欢里商业广场 and an
    unrelated 翰林大厦).

    Hand-checked against both addresses on 17 pairs spanning every
    failure mode seen in the reported bug; see test_china_dedupe.py.
    """
    ka, kb = cn_brand_key(a_name), cn_brand_key(b_name)
    blen = _common_prefix_len(ka, kb)
    if blen < CN_BRAND_MIN:
        return False, "brand_differs"
    ba, bb = cn_branch_markers(a_name), cn_branch_markers(b_name)
    if ba and bb and not (ba & bb):
        return False, "branch_marker_conflict"
    # Residue = what each name says after the shared brand. Admin words
    # (市/区/县/街道) are dropped: one source writes the full postal
    # hierarchy and the other does not, and that is not a disagreement.
    fa, fb = cn_full_key(a_name), cn_full_key(b_name)
    # Two rows that name DIFFERENT cities/counties are never one venue,
    # however close their pins landed: "星辉之城荆州购物公园店" and
    # "星辉之城（洪湖购物公园店）" are 60 m apart only because one of
    # them was geocoded to the wrong city.
    ca, cb = cn_place_names(fa[blen:]), cn_place_names(fb[blen:])
    if ca and cb and not (ca & cb):
        return False, "city_conflict"
    ra = _CN_ADMIN_RE.sub("", fa[blen:])
    rb = _CN_ADMIN_RE.sub("", fb[blen:])
    la, lb = cn_landmarks(ra), cn_landmarks(rb)
    if la and lb and not _landmarks_overlap(la, lb):
        return False, "landmark_conflict"
    return True, ("landmark_agree" if (la and lb) else "brand_only")


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


_ZIV_CABS_PREFIX = "Cabs: "

# (m2) Per-slug count evidence, strongest first. This vocabulary is the
# whole counts policy in one place, and every value is published into
# arcades.json under "count_evidence" so the UI can say what a number is
# rather than printing every number the same way.
#
#   bemanicn_qty  BemaniCN's per-title 台数 field. A real quantity.
#   ziv_comment   A human wrote a quantity on the ZIv listing ("12
#                 machines", "4x"). A real quantity, and the fix for
#                 GiGO Akihabara Building 3 rendering CHUNITHM as x1
#                 when its listing says twelve.
#   ziv_listed    ZIv lists one entry per machine and nobody stated a
#                 quantity, so the tally is a LOWER BOUND: it counts
#                 what somebody bothered to list, which is why the UI
#                 must render it "12 listed" and never "x12".
#
# Deliberately absent: any evidence class for ALL.Net, e-amusement,
# wahlap or round1usa. Those publish no quantities at all, so a venue
# known only to them carries no count and the panel says counts are
# unavailable. Inventing an x1 there is the bug this table exists to
# stop, not a default worth having.
COUNT_EVIDENCE_RANK = {"ziv_listed": 1, "ziv_comment": 2, "bemanicn_qty": 3}
COUNT_EVIDENCE = frozenset(COUNT_EVIDENCE_RANK)

# Evidence classes that publish a NUMBER (game_counts + counts_src set).
# ziv_listed does not: it is a floor, and it rides in game_counts only
# when _ziv_counts_tallied vouches for the row (see (m)).
REAL_COUNT_EVIDENCE = frozenset(("ziv_comment", "bemanicn_qty"))

# Hardware-variant slug -> the game slug it is a cabinet OF. Mirrors the
# `game:` key of the VARIANTS table in js/state.js, which is what decides
# where a pill renders; a variant missing from here cannot have its count
# justified and is therefore published without one.
CAB_MODEL_GAME = {
    "sdvx_vm": "sdvx", "sdvx_nemsys": "sdvx",
    "iidx_lm": "iidx",
    "ddr_gold": "ddr", "ddr_universal": "ddr", "ddr_legacy": "ddr",
    "gitadora_gf_arena": "gitadora", "gitadora_dm_arena": "gitadora",
    "popn_pikapika": "popn",
    "taiko_asia": "taiko", "taiko_jp": "taiko", "taiko_us": "taiko",
    "maimai_classic": "maimai_dx", "maimai_dx_cab": "maimai_dx",
}

# Hardware-variant slugs ziv.py can assert per cabinet. Wider than
# CAB_SLUGS (which is the e-amusement flag vocabulary); this is the set
# js/state.js reads out of an arcade's `cab_models`.
CAB_MODEL_SLUGS = frozenset(CAB_MODEL_GAME)


def _take_count(counts, evidence, slug, n, ev):
    """Fold one (slug, count, evidence) into a counts/evidence pair.

    Stronger evidence wins outright, ties break on the larger count.
    Ranking before comparing is the point: a comment-backed 3 must beat
    a listed 9, because "3 machines" is somebody reporting the room and
    9 is somebody having typed nine rows. A plain per-slug max would
    publish the 9 and label it with the comment's evidence, which is a
    number from one source wearing another source's credibility.
    """
    if n <= 0:
        return
    rank = COUNT_EVIDENCE_RANK.get(ev, 0)
    if slug in counts:
        cur_rank = COUNT_EVIDENCE_RANK.get(evidence.get(slug), 0)
        if rank < cur_rank:
            return
        if rank == cur_rank and n <= counts[slug]:
            return
    counts[slug] = n
    if ev:
        evidence[slug] = ev
    else:
        evidence.pop(slug, None)


def _ziv_counts_tallied(note, game_counts):
    """True when a ZIv row's counts are a real machine tally (see (m)).

    ZIv publishes a list of machines, so ziv.py tallies one per list entry
    and a slug reaches 2 in two very different ways. Two machines of the
    same title is a quantity the source actually asserted. Two DIFFERENT
    titles that happen to share one of our slugs is not: GuitarFreaksV7 and
    DrumManiaV7 both fold into `gitadora`, DDR A3 and DDR WORLD both fold
    into `ddr`, and a venue with one of each has one cabinet of each. The
    older "any slug >= 2" test could not tell those apart and published the
    second as a count.

    The row's "Cabs:" note is the same title list de-duplicated, so
    comparing a slug's count against the number of distinct titles mapping
    to it separates them: strictly more machines than titles means some
    title is listed twice, and a list only repeats a title when it was
    entered machine by machine. That makes the whole row a tally, which is
    why the caller then keeps its 1s too - on a machine-level list a 1
    really is one machine.

    A slug that no title maps to is skipped rather than read as evidence.
    Titles reach their slug by seriesID as well as by name and the note
    carries no IDs, so 0 titles means the name lookup missed, not that the
    count came from nowhere. GAME_PATTERNS covers every such title in the
    committed crawl (it gained `Wadaiko Master`, `PercussionFreaks`,
    `ノスタルジア` and the rest for exactly this reason), so the guard is
    dead weight today and stays only because the next crawl can introduce a
    spelling it has never seen. Skipping costs a suppressed real tally;
    trusting it would invent one.
    """
    if not game_counts or not note or not note.startswith(_ZIV_CABS_PREFIX):
        return False
    titles_per_slug = {}
    for title in note[len(_ZIV_CABS_PREFIX):].split("; "):
        title = title.strip()
        if not title:
            continue
        for slug in ziv.slugs_for_title(title):
            titles_per_slug[slug] = titles_per_slug.get(slug, 0) + 1
    return any(titles_per_slug.get(slug, 0) and n > titles_per_slug[slug]
               for slug, n in game_counts.items())


def load_units(raw_dir, stats):
    """Load all raw files -> deduped source units."""
    units = {}   # (source, normalized name, normalized addr) -> unit

    def add(source, name, addr, lat, lng, games, cabs, country, pref,
            ziv_url=None, note=None, coord_system="wgs84",
            cn_prov=None, cn_city=None, bemanicn_url=None,
            game_counts=None, count_evidence=None, cab_models=None):
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
        # (m2) per-slug evidence for the counts above. ziv.py emits
        # "ziv_comment" (a human wrote a quantity on the listing) or
        # "ziv_listed" (one list entry per machine, a lower bound).
        # bemanicn publishes real per-title 台数 and sends none, so its
        # slugs are labelled here rather than trusted to the payload.
        ev = {}
        raw_ev = count_evidence or {}
        for slug in gc:
            e = raw_ev.get(slug)
            if e in COUNT_EVIDENCE:
                ev[slug] = e
            elif source == "bemanicn":
                ev[slug] = "bemanicn_qty"
            elif source == "ziv":
                # A ziv row from before the quantity parser existed (or
                # community.json's bundled ziv rows) carries counts with
                # no evidence key. Those are list tallies by construction.
                ev[slug] = "ziv_listed"
        cm = {}
        for slug, n in (cab_models or {}).items():
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if slug in CAB_MODEL_SLUGS and n > 0:
                cm[slug] = n
        key = (source, _dedupe_key(name), _dedupe_key(addr))
        u = units.get(key)
        if u is None:
            u = {"source": source, "name": name, "addr": addr,
                 "lat": lat, "lng": lng, "games": set(), "cabs": set(),
                 "country": country, "pref": pref, "ziv_url": ziv_url,
                 "notes": [], "coord_system": coord_system,
                 "cn_prov": cn_prov, "cn_city": cn_city,
                 "bemanicn_url": bemanicn_url, "game_counts": {},
                 "count_evidence": {}, "cab_models": {},
                 "counts_tallied": False}
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
        # Per-slug pick across within-source dupes. The evidence has to
        # travel WITH the number it justifies, so this is not a bare max:
        # a stronger evidence class wins outright (a comment-backed 3
        # beats a listed 9 - the human who wrote "3 machines" saw the
        # room, the list did not), and within one class the max wins.
        # A counted slug is always also a game.
        for slug, n in gc.items():
            _take_count(u["game_counts"], u["count_evidence"], slug, n,
                        ev.get(slug))
        u["games"].update(gc)
        for slug, n in cm.items():
            if n > u["cab_models"].get(slug, 0):
                u["cab_models"][slug] = n
        # (m) one tallied row is enough: the flag rides the unit through
        # within-source dedupe, so a listing split across two rows keeps
        # its evidence.
        if source == "ziv" and _ziv_counts_tallied(note, gc):
            u["counts_tallied"] = True
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
                game_counts=row.get("game_counts"),
                count_evidence=row.get("count_evidence"),
                cab_models=row.get("cab_models"))

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
                game_counts=row.get("game_counts"),
                count_evidence=row.get("count_evidence"),
                cab_models=row.get("cab_models"))

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

    # ---- Hong Kong / Macau cross-script tier -------------------------
    # The only territory where one venue is routinely published under two
    # names that share not a single character. The official sources are
    # English with a coordinate; BemaniCN is Chinese with a precise address
    # and no coordinate. Name similarity is zero by construction and there is
    # no distance to measure, so every general tier above is blind here.
    #
    # scrapers/hk_match.py extracts independent kinds of evidence - the street
    # name (compared through the Cantonese reading, because 和宜合道 IS Wo Yi
    # Hop Road), the street number, the locality, the operator's Latin brand,
    # a shared Chinese venue name, and the venue name read aloud - and this
    # requires TWO KINDS before merging anything. One kind is never enough:
    # a bare 68 pairs Kwun Tong Plaza with an arcade in Shau Kei Wan, and a
    # bare GAMEZONE pairs all six Game Zone branches with each other.
    #
    # A shared street at conflicting numbers VETOES the pair outright. That is
    # the one signal in this dataset that positively separates two venues:
    # 觀塘道418號 (APM) and 觀塘道410號 (金沙) are two buildings on one road,
    # and every other kind of evidence would have called them the same arcade.
    #
    # Evidence is gathered per CLUSTER, not per unit. A venue already merged
    # from ALL.Net and ZIv carries the English name AND ZIv's bilingual
    # address, and the Chinese half of that address is often the only thing
    # the BemaniCN row can be compared against. Counting units separately also
    # made a BemaniCN row matching both halves of ONE venue look ambiguous and
    # merge with neither, which is how Plaza Hollywood stayed split despite
    # both sides plainly reading 383.
    #
    # Then a two-way uniqueness guard: a cluster merges only when it has
    # exactly one partner AND that partner has only it.
    HK_COUNTRIES = ("Hong Kong", "Macau")
    HK_NEAR_M = 1000.0    # both-coordinated pairs must still be plausible

    hk_idx = [i for i, u in enumerate(units) if u["country"] in HK_COUNTRIES]
    hk_clusters = {}
    for i in hk_idx:
        hk_clusters.setdefault(uf.find(i), []).append(i)

    def _cluster_field(members, key):
        return " ".join(units[k][key] or "" for k in members)

    hk_edge = {}
    hk_partners = {}
    roots = sorted(hk_clusters)
    for x in range(len(roots)):
        for y in range(x + 1, len(roots)):
            ra, rb = roots[x], roots[y]
            ma, mb = hk_clusters[ra], hk_clusters[rb]
            if ({units[k]["country"] for k in ma}
                    != {units[k]["country"] for k in mb}):
                continue
            if not ({units[k]["source"] for k in ma}
                    ^ {units[k]["source"] for k in mb}):
                continue                  # same single source, nothing to add
            coords_a = [k for k in ma if units[k]["lat"] is not None]
            coords_b = [k for k in mb if units[k]["lat"] is not None]
            if coords_a and coords_b:
                # Both already placed: only merge when the pins agree, so a
                # brand shared by two real branches cannot fuse them.
                if min(haversine_m(units[p]["lat"], units[p]["lng"],
                                   units[q]["lat"], units[q]["lng"])
                       for p in coords_a for q in coords_b) > HK_NEAR_M:
                    continue
            types, veto = hk_match.evidence(
                _cluster_field(ma, "addr"), _cluster_field(ma, "name"),
                _cluster_field(mb, "addr"), _cluster_field(mb, "name"))
            if veto or len(types) < 2:
                continue
            hk_edge[(ra, rb)] = (ma[0], mb[0], types)
            hk_partners.setdefault(ra, set()).add(rb)
            hk_partners.setdefault(rb, set()).add(ra)

    # Mutual best, with a margin. Plain uniqueness was too blunt: 佐敦Game Zone
    # shares a brand and a locality reading with Kwun Tong Plaza, which is
    # enough to be a candidate and was enough to block the real Kwun Tong pair
    # from merging. A cluster now picks the partner backed by the most KINDS of
    # evidence, and merges only when that partner picks it back and no runner
    # up ties it. Two Macau rows really are tied - 新遊戲/兒童王國 names two
    # arcades in one building - and a tie still refuses.
    def _rank(root):
        cands = []
        for other in hk_partners.get(root, ()):
            key = (min(root, other), max(root, other))
            cands.append((len(hk_edge[key][2]), other))
        cands.sort(key=lambda c: (-c[0], c[1]))
        return cands

    def _best_unambiguous(root):
        cands = _rank(root)
        if not cands:
            return None
        if len(cands) > 1 and cands[0][0] == cands[1][0]:
            return None
        return cands[0][1]

    for (ra, rb), (i, j, types) in sorted(hk_edge.items()):
        ambiguous = (_best_unambiguous(ra) != rb
                     or _best_unambiguous(rb) != ra)
        # Blocked pairs are logged rather than dropped silently. A refusal here
        # is either correct or a rule that needs another kind of evidence, and
        # there is no way to tell which without seeing them.
        log.append({"rule": ("hk-cross-script-blocked" if ambiguous
                             else "hk-cross-script"),
                    "evidence": types, "a": unit_ref(i), "b": unit_ref(j)})
        if not ambiguous:
            uf.union(i, j)

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
    # ---- China co-located tier ---------------------------------------
    #
    # Reported bug: Shenzhen and every other Chinese city shows the same
    # arcade two or three times, one pin per source. The proximity tier
    # above cannot reach these for two independent reasons:
    #   1. its hard gate is PROXIMITY_MAX_M = 30 m, and the median
    #      separation of a real China duplicate pair is 31 m - the two
    #      sources geocode the same mall to different doors, and a big
    #      Chinese mall is 200-500 m across;
    #   2. it only considers official-vs-community pairs, and China's
    #      duplicates are overwhelmingly bemanicn x wahlap (1409 of the
    #      1493 confirmed cases) - by that scoping, both community.
    # Widening the global gate is not an option (it is doing real work
    # at 120 m elsewhere and two Tokyo arcades 200 m apart are two
    # arcades), so this tier is scoped to China rows only.
    #
    # The evidence is NOT name similarity, which is actively misleading
    # here: sibling branches of one chain differ by a single character
    # ("江北一店" vs "江北二店", 0.95 similar, two shops) while one shop
    # listed by two sources can share almost nothing ("51区天津南开大悦城
    # 店" vs "51区超级乐园 AREA-51 SUPER PARK (Tianjin)"). What actually
    # separates them is whether the two rows name the same BUILDING and
    # the same numbered branch - see cn_same_venue_evidence.
    cn_idx = [i for i, u in enumerate(units)
              if u["country"] == "China" and u["lat"] is not None]
    if cn_idx:
        ccell = 0.006      # ~660 m: a 500 m ball fits the 3x3 window
        cgrid = {}
        for i in cn_idx:
            u = units[i]
            cgrid.setdefault((math.floor(u["lat"] / ccell),
                              math.floor(u["lng"] / ccell)), []).append(i)
        cn_pairs = {}
        for (cx, cy), members in cgrid.items():
            cand = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cand.extend(cgrid.get((cx + dx, cy + dy), ()))
            for i in members:
                ui = units[i]
                for j in cand:
                    if j <= i or uf.find(i) == uf.find(j):
                        continue
                    uj = units[j]
                    dist = haversine_m(ui["lat"], ui["lng"],
                                       uj["lat"], uj["lng"])
                    if dist > CN_MAX_M:
                        continue
                    ok, why = cn_same_venue_evidence(ui["name"], uj["name"])
                    if not ok:
                        continue
                    # A shared brand with NO building evidence either way
                    # is the weakest case ("酷玩时代兰州城关店" vs
                    # "酷玩时代电玩城"): plausible, but a chain can also
                    # run two shops in one district. Allow it only when
                    # the pins are close enough to be one storefront.
                    if why != "landmark_agree" and dist > CN_BRAND_ONLY_M:
                        continue
                    sim = china_name_similarity(
                        ui["name"], uj["name"], ui.get("cn_prov"),
                        ui.get("cn_city"), uj.get("cn_city"))
                    cn_pairs[(i, j)] = (sim, dist, why)
        # Mutual-best per (unit, other-source): a shop listed once by
        # wahlap and once by bemanicn should claim exactly one partner
        # per source, so a row of neighbouring shops cannot daisy-chain
        # into one blob through a shared counterpart.
        cbest = {}
        for (i, j), (sim, dist, _w) in cn_pairs.items():
            for a, b in ((i, j), (j, i)):
                key = (a, units[b]["source"])
                cand = (sim, -dist, b)
                if key not in cbest or cand > cbest[key]:
                    cbest[key] = cand
        for (i, j), (sim, dist, why) in sorted(
                cn_pairs.items(), key=lambda kv: (-kv[1][0], kv[1][1])):
            if (cbest[(i, units[j]["source"])][2] != j
                    or cbest[(j, units[i]["source"])][2] != i):
                continue
            if uf.union(i, j):
                log.append({"rule": "china_colocated",
                            "evidence": why,
                            "distance_m": round(dist, 1),
                            "similarity": round(sim, 3),
                            "a": unit_ref(i), "b": unit_ref(j)})
    # ---- END China co-located tier -----------------------------------

    groups = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    return groups


# -------------------------------------------- China co-located dedupe ------

# Evidence rank for choosing which of two counts to keep. Mirrors the
# tiers used when units are merged, so the second pass cannot silently
# downgrade a count the first pass had already justified.
_CE_RANK = {"bemanicn_qty": 3, "ziv_comment": 2, "ziv_listed": 1}


def _merge_two_china(keep, drop):
    """Union `drop` into `keep`, in place. Nothing is discarded.

    A dedupe that PICKS one row and deletes the other is worse than the
    duplicate pins it removes: dropping a links.ziv orphans that venue's
    photos (they join on the source URL), and dropping a games slug makes
    the arcade vanish from a filter it belongs in. So every list-valued
    and dict-valued field is unioned, and the scalar fields prefer
    whichever row actually has a value.
    """
    for key in ("games", "cabs", "src"):
        seen = list(keep.get(key) or [])
        for v in (drop.get(key) or []):
            if v not in seen:
                seen.append(v)
        keep[key] = seen
    links = dict(keep.get("links") or {})
    # links holds ONE url per source, so when two rows of the SAME source
    # merge, the loser's page url has nowhere to go - and photos join on
    # that url, so its pictures would be orphaned (measured: 16 China
    # photos lost this way). Extra urls are kept in links.also so the
    # photo join can still find them.
    # Only SOURCE PAGES belong in `also`. links.gmaps is a generated
    # search url, not a page anything is keyed to, and letting it in
    # buried the second ziv url behind two useless entries.
    also = list(links.get("also") or [])
    for k, v in (drop.get("links") or {}).items():
        if not v or k in ("also", "gmaps"):
            continue
        if not links.get(k):
            links[k] = v
        elif links[k] != v and v not in also:
            also.append(v)
    for v in (drop.get("links") or {}).get("also") or []:
        if v not in also and v not in links.values():
            also.append(v)
    if also:
        links["also"] = also
    keep["links"] = links
    # Counts: keep the better-evidenced number per game, not the first.
    # counts_src must end up naming the source that actually justifies
    # the surviving numbers. Taking it from whichever row happened to be
    # the survivor produced entries labelled counts_src="ziv" whose only
    # remaining count came from bemanicn, which trips the publish-rule
    # assertion further down (correctly - the label would be a lie).
    gc = dict(keep.get("game_counts") or {})
    ce = dict(keep.get("count_evidence") or {})
    src_of = {}
    for slug in gc:
        src_of[slug] = keep.get("counts_src")
    for slug, n in (drop.get("game_counts") or {}).items():
        their = (drop.get("count_evidence") or {}).get(slug)
        if slug not in gc or _CE_RANK.get(their, 0) > _CE_RANK.get(
                ce.get(slug), 0):
            gc[slug] = n
            src_of[slug] = drop.get("counts_src")
            if their:
                ce[slug] = their
            else:
                ce.pop(slug, None)
    if gc:
        keep["game_counts"] = gc
        keep["count_evidence"] = {s: e for s, e in ce.items() if s in gc}
        if not keep["count_evidence"]:
            keep.pop("count_evidence")
        # bemanicn publishes explicit quantities; prefer it whenever any
        # surviving count came from there.
        srcs = {s for s in src_of.values() if s}
        keep["counts_src"] = ("bemanicn" if "bemanicn" in srcs
                              else (sorted(srcs)[0] if srcs else None))
    cm = dict(keep.get("cab_models") or {})
    for slug, n in (drop.get("cab_models") or {}).items():
        if slug not in cm or (cm[slug] is None and n is not None):
            cm[slug] = n
    if cm:
        keep["cab_models"] = cm
    # A real pin beats an approximated one; keep the caveat only if the
    # surviving coordinate is still the approximate one.
    if keep.get("approx") and not drop.get("approx") and drop.get("lat"):
        keep["lat"], keep["lng"] = drop["lat"], drop["lng"]
        keep.pop("approx", None)
        keep.pop("approx_level", None)
    for key in ("addr", "pref", "counts_src"):
        if not keep.get(key) and drop.get(key):
            keep[key] = drop[key]
    na, nb = keep.get("notes") or "", drop.get("notes") or ""
    if nb and nb not in na:
        keep["notes"] = (na + " | " + nb) if na else nb
    return keep


def dedupe_china_colocated(entries, log, max_m=None, brand_only_m=None):
    """Merge China entries that two sources listed as separate pins.

    Runs on built entries rather than source units because the Chinese
    sources publish no coordinates - see the call site. Returns a new
    list; `entries` is not mutated in place beyond the survivors.
    """
    max_m = CN_MAX_M if max_m is None else max_m
    brand_only_m = (CN_BRAND_ONLY_M if brand_only_m is None
                    else brand_only_m)
    idx = [i for i, a in enumerate(entries)
           if a.get("country") == "China" and a.get("lat") is not None]
    if not idx:
        return entries
    cell = 0.006          # ~660 m, so a 500 m ball fits the 3x3 window
    grid = {}
    for i in idx:
        a = entries[i]
        grid.setdefault((math.floor(a["lat"] / cell),
                         math.floor(a["lng"] / cell)), []).append(i)
    pairs = {}
    for (cx, cy), members in grid.items():
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(grid.get((cx + dx, cy + dy), ()))
        for i in members:
            ai = entries[i]
            for j in cand:
                if j <= i or (i, j) in pairs:
                    continue
                aj = entries[j]
                dist = haversine_m(ai["lat"], ai["lng"],
                                   aj["lat"], aj["lng"])
                if dist > max_m:
                    continue
                # Distance is only evidence when the pins are real.
                # 5.7k China rows have no published coordinate and sit on
                # a district or city CENTROID, so two of them are 0.0 m
                # apart by construction - "七彩天空杭州临安锦北宝龙店" and
                # "七彩天空杭州临安青山湖宝龙店" are two different malls
                # sharing one approximated point. Requiring at least one
                # real pin means proximity means what the rule assumes.
                both_approx = ai.get("approx") and aj.get("approx")
                if both_approx and (ai.get("approx_level") != "address"
                                    or aj.get("approx_level") != "address"):
                    continue
                ok, why = cn_same_venue_evidence(ai["name"], aj["name"])
                if not ok:
                    continue
                if why != "landmark_agree" and dist > brand_only_m:
                    continue
                pairs[(i, j)] = (dist, why)
    if not pairs:
        return entries
    # Union-find over entry indices, so a venue listed by three sources
    # collapses to one pin rather than to two.
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    # Closest first: when a chain has several shops in one mall, the
    # tightest pair is the one most likely to be the true duplicate.
    for (i, j), (dist, why) in sorted(pairs.items(),
                                      key=lambda kv: kv[1][0]):
        ri, rj = find(i), find(j)
        if ri == rj:
            continue
        parent[rj] = ri
        log.append({"rule": "china_colocated", "evidence": why,
                    "distance_m": round(dist, 1),
                    "a": {"name": entries[i]["name"],
                          "addr": entries[i].get("addr"),
                          "src": entries[i].get("src")},
                    "b": {"name": entries[j]["name"],
                          "addr": entries[j].get("addr"),
                          "src": entries[j].get("src")}})
    clusters = {}
    for i in list(parent):
        clusters.setdefault(find(i), []).append(i)
    dropped = set()
    for root, members in clusters.items():
        if len(members) < 2:
            continue
        # The survivor is the row with the most sources, then the one
        # with a real (non-approximate) pin, then the longest name -
        # which in this data is the one that spells out the branch.
        members.sort(key=lambda i: (-len(entries[i].get("src") or []),
                                    bool(entries[i].get("approx")),
                                    -len(entries[i]["name"] or "")))
        keep = entries[members[0]]
        for i in members[1:]:
            _merge_two_china(keep, entries[i])
            dropped.add(i)
    return [a for i, a in enumerate(entries) if i not in dropped]


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
    also_urls = []
    pref = None
    country = best["country"]
    game_counts = {}
    count_evidence = {}
    cab_models = {}
    counts_contributors = set()   # (m) which sources actually counted
    for u in members:
        games |= u["games"]
        cabs |= u["cabs"]
        src.add(u["source"])
        # (m2) cross-source counts, resolved on EVIDENCE first and count
        # second (see _take_count): bemanicn's 台数 outranks a ZIv comment,
        # which outranks a bare ZIv list tally. Magnitude breaks ties only
        # WITHIN one evidence class - a bigger number from a weaker source
        # never wins, or the count would wear credibility it did not earn.
        if u["game_counts"]:
            counts_contributors.add(u["source"])
        for slug, n in u["game_counts"].items():
            _take_count(game_counts, count_evidence, slug, n,
                        u["count_evidence"].get(slug))
        for slug, n in u["cab_models"].items():
            if n > cab_models.get(slug, 0):
                cab_models[slug] = n
        for nt in u["notes"]:
            if nt and nt not in notes:
                notes.append(nt)
        # links carries ONE url per source, so a cluster holding two rows
        # of the same source would silently drop the second page - and
        # photos join on that page url, so its pictures are orphaned.
        # Extras go to links.also; see photos.photos_for_arcade.
        if u["ziv_url"]:
            if ziv_url is None:
                ziv_url = u["ziv_url"]
            elif u["ziv_url"] != ziv_url and u["ziv_url"] not in also_urls:
                also_urls.append(u["ziv_url"])
        if u["bemanicn_url"]:
            if bemanicn_url is None:
                bemanicn_url = u["bemanicn_url"]
            elif (u["bemanicn_url"] != bemanicn_url
                  and u["bemanicn_url"] not in also_urls):
                also_urls.append(u["bemanicn_url"])
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
        "links": ({"gmaps": gmaps, "ziv": ziv_url,
                   "bemanicn": bemanicn_url, "also": also_urls}
                  if also_urls else
                  {"gmaps": gmaps, "ziv": ziv_url,
                   "bemanicn": bemanicn_url}),
        "notes": note_str,
    }
    # ---- BEGIN counts confidence (owner: counts-honesty agent) -------
    # (m) A cabinet count is published only when a source ASSERTED one.
    # The decision is per slug and it is driven by count_evidence, not by
    # which source the row came from:
    #
    #   bemanicn_qty  BemaniCN's per-title 台数. A real quantity.
    #   ziv_comment   A human wrote a quantity on the ZIv listing ("12
    #                 machines", "4x"). A real quantity, and the reason
    #                 this block was rewritten: GiGO Akihabara Building 3
    #                 lists twelve CHUNITHM and used to render x1.
    #   ziv_listed    Nobody stated a quantity; ZIv's payload is a machine
    #                 LIST, so the tally is a LOWER BOUND. One row per
    #                 game version is the baseline shape, so a bare tally
    #                 reads 1 for any title the arcade merely HAS, and 2
    #                 for two versions or two titles sharing one slug
    #                 (GuitarFreaks + DrumMania -> gitadora).
    #
    # Rule, applied after the per-slug fold above so no count is lost
    # before the decision:
    #   any REAL evidence (bemanicn_qty / ziv_comment) on any slug
    #       -> publish game_counts. counts_src is "bemanicn" when
    #          bemanicn contributed at all, else "ziv". A ziv_listed slug
    #          on such a row rides along: the same listing that stated one
    #          quantity is a listing somebody maintained.
    #   ziv_listed only, and _ziv_counts_tallied vouches for the row
    #       -> publish, counts_src "ziv". A repeated title proves the list
    #          was entered machine by machine, so its 1s are real 1s.
    #   ziv_listed only, no repeated title
    #       -> DROP game_counts entirely, counts_src null. Placeholder
    #          -only data must not render as "x1".
    #
    # counts_src is written ONLY when some source reported counts:
    #   "bemanicn"/"ziv" = these counts are real (game_counts present),
    #   null             = counts existed but were placeholder-only and
    #                      were dropped (game_counts absent),
    #   key absent       = no source ever counted this arcade. ALL.Net and
    #                      e-amusement publish no quantities at all, so
    #                      every venue known only to them lands here and
    #                      the panel says counts are unavailable.
    # That keeps "suppressed placeholder" distinguishable from "never
    # counted", which a bare missing key would erase.
    #
    # count_evidence ships alongside so the UI can render a ziv_listed 12
    # as "12 listed" rather than "x12" - a floor is not a tally.
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
        has_real = any(e in REAL_COUNT_EVIDENCE
                       for e in count_evidence.values())
        if has_real or any(u["counts_tallied"] for u in members):
            counts_src = ("bemanicn" if "bemanicn" in counts_contributors
                          else "ziv")
        else:
            # placeholder-only: drop the quantities, keep the games.
            # `games |= set(game_counts)` ran above, so this must hold;
            # asserted rather than assumed because a future reorder of
            # that union would silently delete games instead of counts.
            assert set(game_counts) <= set(entry["games"]), \
                (best["name"], sorted(game_counts), entry["games"])
            game_counts = {}
            count_evidence = {}
            counts_src = None
        entry["counts_src"] = counts_src
    if game_counts:
        entry["game_counts"] = {s: game_counts[s]
                                for s in sorted(game_counts)}
        if count_evidence:
            entry["count_evidence"] = {s: count_evidence[s]
                                       for s in sorted(count_evidence)}
    # cab_models is per-CABINET-variant, not per game. WHICH variants exist
    # is a fact about the hardware in the room and is published regardless
    # of the counts gate above; HOW MANY of each is a quantity claim and
    # obeys the same rule as game_counts.
    #
    # ziv.py folds comment quantities into cab_models but discards the
    # evidence class while doing it (_counts_and_evidence_for_machines
    # returns the variant total and drops its `_ev`), so a bare title with
    # no comment arrives here as a 1 that means "this cabinet exists", not
    # "there is one of them". Publishing that renders "Lightning x1" in
    # js/panel.js variantPillsHtml - which is exactly the fabrication the
    # owner reported, moved from the game chip to the cabinet pill, and
    # exactly what that function's own comment forbids: "inventing 'x1'
    # from the presence of a title would be the same fabrication the
    # counts-honesty rule exists to stop".
    #
    # The evidence for the variant's PARENT game is the honest proxy: the
    # variant count is derived from the same machine list, so when nobody
    # stated a quantity for the game, nobody stated one for its cabinets
    # either. Backed counts are published; unbacked ones are published as
    # null, which keeps the variant (the pill still renders, and that is
    # real information) while withholding the number. js/state.js already
    # treats a non-number as "no count" - addHit stores `n: null` for it
    # and variantPillsHtml then omits the count entirely.
    if cab_models:
        pub = {}
        for slug in sorted(cab_models):
            ev = count_evidence.get(CAB_MODEL_GAME.get(slug))
            pub[slug] = cab_models[slug] if ev in REAL_COUNT_EVIDENCE else None
        entry["cab_models"] = pub
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
    # reorder keys for output (game_counts / count_evidence / counts_src /
    # cab_models are all optional)
    ordered = [{k: a[k] for k in
                ("id", "name", "addr", "lat", "lng", "country", "pref",
                 "games", "game_counts", "count_evidence", "counts_src",
                 "cab_models", "cabs", "src", "links", "notes")
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
    # coordinates), leaving ~5.7k China rows invisible on the map even
    # though their addresses name the district they are in. china_place
    # resolves each as deep as data/china_areas.json reaches - district
    # where the address names one, city otherwise - and marks it
    # "approx": true plus "approx_level".
    # Runs AFTER geo_validation on purpose: validation may null an
    # out-of-country geocode, and such a row then becomes eligible for a
    # centroid here. place_approx() self-guards - it refuses any entry
    # that already has coords (so a real pin is never overwritten and
    # "approx" is never set on one), any non-China country, and anything
    # labeled Taiwan (the table has no Taiwanese cities and a bare
    # substring match would drop Taiwanese addresses onto the mainland;
    # ZIv already covers Taiwan with real pins). Unresolved rows keep
    # lat/lng null. Deliberately NOT touched here: links.gmaps.
    # Coordless entries got a name+address *search* URL above, which is
    # strictly more useful than a district centroid, so the link must
    # stay as built - do not "sync" it to the new coords.
    # Note "approx" lands at the end of each entry dict (the key-order
    # comprehension above already ran); that is accepted, not an
    # oversight - geo_validate and this step both operate on `ordered`.
    # Street-level first, where a committed geocode exists for the address.
    # Empty in this repo today (nobody has run the opt-in refresh), so this is
    # a no-op that costs one dict lookup per coordless row; when the cache is
    # populated it takes those rows out of china_place's hands entirely.
    geocode_rejects = []
    geocode_log = geocode_cn.apply_cache(ordered, reject_log=geocode_rejects)
    if geocode_log:
        print("merge: geocode_cn placed %d coordless China entries from the "
              "address cache" % len(geocode_log), file=sys.stderr)
    if geocode_rejects:
        print("merge: geocode_cn REFUSED %d cached answer(s) that resolve to "
              "the wrong district; those rows fall through to a centroid"
              % len(geocode_rejects), file=sys.stderr)
        for r in geocode_rejects[:5]:
            print("  #%s %s | %s" % (r.get("id"), (r.get("name") or "")[:28],
                                     r.get("why")), file=sys.stderr)
    # There is deliberately NO "clear approx on the geocoded rows" step here
    # any more, and its absence is the fix for the worse of two bugs.
    #
    # It used to clear the flag for every row whose level was address or
    # street, on the premise that "a building is not an approximation". The
    # premise is false twice over. Baidu's keyless endpoint is a POI SEARCH,
    # so "poi precision" says the answer was a building, never that it was
    # THIS building: for a venue inside a mall the top result is routinely the
    # MALL (1号机长合肥瑶海天地店 -> 瑶海天地, the shopping centre it holds a
    # unit of), and when the query is thin it is a different branch entirely
    # (arcade 893, in 澧县, took the coordinate of a 欢乐城 in 武陵区, 100 km
    # away). The clearing turned 5,737 China rows into pins that asserted
    # building-level accuracy, 0 of which carried any caveat.
    #
    # The obvious repair - clear only where the answer can be confirmed to
    # name the arcade rather than its mall - was tried and MEASURED, and it
    # does not work. Three discriminators over the committed cache confirmed
    # 2,547, then 1,240, then 230 of 5,769 rows, and every one of them was
    # visibly wrong in both directions: a KFC and two shopping centres came
    # back "confirmed", while 1-7PLAY家庭娱乐中心(唐山中骏世界城店) - plainly
    # the arcade - came back "not confirmed". A discriminator that is ~20%
    # wrong, used to REMOVE a caveat, silently overclaims on scores of rows.
    # So nothing is cleared, and the honest reason is recorded here rather
    # than a tuned heuristic being left in the file for somebody to trust.
    #
    # Every geocoded row therefore keeps approx:true and its approx_level, and
    # js/panel.js renders the row it already has written for exactly this:
    # "Position from the address - the source publishes no coordinates, so
    # this pin was geocoded from the printed address." That sentence is true
    # whether the POI found was the arcade or the mall around it, which is
    # precisely why it is the one to show.
    #
    # Consequence to expect, and it is the intended one: China's approx count
    # goes from 29 back to ~5,700. That is not a regression. The previous
    # commit read the same rise as one and deleted the caveat instead.
    approx_log = china_place.place_arcades(ordered)
    if approx_log:
        lv = {}
        for rec in approx_log:
            lv[rec["level"]] = lv.get(rec["level"], 0) + 1
        print("merge: china_place placed %d coordless China entries "
              "(%d district, %d city; approx:true)"
              % (len(approx_log), lv.get("district", 0), lv.get("city", 0)),
              file=sys.stderr)
    # --- end China approximate placement ------------------------------

    # (n) China co-located dedupe, SECOND pass.
    #
    # cluster_units() cannot do this one. Both Chinese sources are
    # coordinate-less by construction, so at clustering time these rows
    # have no lat/lng at all and every distance-based rule silently
    # skips them; their coordinates only exist after geocode_cn above.
    # That is why the reported bug survived every earlier fix: the tier
    # that should have caught it was structurally blind to China.
    #
    # So the dedupe runs here, on built entries, and merges them with
    # merge_entries() - a union, not a pick-one - so no games, counts,
    # links or photos are lost.
    cn_log = []
    ordered = dedupe_china_colocated(ordered, cn_log)
    if cn_log:
        by = {}
        for rec in cn_log:
            by[rec["evidence"]] = by.get(rec["evidence"], 0) + 1
        print("merge: china_colocated merged %d duplicate China pins (%s)"
              % (len(cn_log),
                 ", ".join("%s=%d" % kv for kv in sorted(by.items()))),
              file=sys.stderr)
        merge_decisions.extend(cn_log)
        # ids were assigned before this pass, so renumber. Nothing keyed
        # to an id survives this function, and several joins downstream
        # (photos, manual China coords) key on source URLs precisely
        # because ids are not stable across builds.
        for i, a in enumerate(ordered, 1):
            a["id"] = i

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
        ce = a.get("count_evidence", {})
        assert set(ce) <= set(gc), (a["name"], sorted(ce), sorted(gc))
        assert all(v in COUNT_EVIDENCE for v in ce.values()), (a["name"], ce)
        assert ("count_evidence" in a) <= ("game_counts" in a), a["name"]
        cm = a.get("cab_models", {})
        assert all(s in CAB_MODEL_SLUGS for s in cm), (a["name"], sorted(cm))
        # null = "this cabinet is here, nobody said how many". A number is
        # only ever published when the parent game carries real evidence.
        assert all(n is None or (isinstance(n, int) and n > 0)
                   for n in cm.values()), (a["name"], cm)
        for slug, n in cm.items():
            if n is None:
                continue
            assert ce.get(CAB_MODEL_GAME[slug]) in REAL_COUNT_EVIDENCE, \
                (a["name"], slug, n, ce.get(CAB_MODEL_GAME[slug]))
        if "counts_src" in a:
            cs = a["counts_src"]
            assert cs in ("bemanicn", "ziv", None), (a["name"], cs)
            # game_counts present exactly when the counts were kept
            assert ("game_counts" in a) == (cs is not None), (a["name"], cs)
            # a dropped ziv-placeholder entry must still list the games
            if cs is None:
                assert a["games"], a["name"]
                assert "count_evidence" not in a, a["name"]
            if cs == "ziv":
                # A published ziv row is justified either by a stated
                # quantity (some slug is ziv_comment) or by the repeated
                # -title tally rule, which needs some slug >= 2.
                #
                # The old assertion was `any(n >= 2)` alone. That was
                # correct while the tally rule was the ONLY way a ziv row
                # could publish, and it is wrong now: a listing whose one
                # comment says "1 machine" is a real, human-asserted 1 and
                # must be publishable. Relaxed deliberately - the >= 2
                # branch below still guards the tally path exactly as
                # before, so the rule that stopped placeholder x1s is
                # intact; what changed is that a STATED 1 is no longer
                # mistaken for a placeholder 1.
                assert (any(e == "ziv_comment" for e in ce.values())
                        or any(n >= 2 for n in gc.values())), (a["name"], gc)
        else:
            assert "game_counts" not in a, a["name"]
            assert "count_evidence" not in a, a["name"]
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

    # (m) evidence mix, at ENTRY level: an entry counts once per evidence
    # class it carries, so the three buckets overlap by construction (a
    # venue can state a quantity for CHUNITHM and merely list its jubeat).
    # "real" is the honest headline - how many venues have at least one
    # quantity somebody actually asserted.
    ev_dist = {"any_real": 0, "bemanicn_qty": 0, "ziv_comment": 0,
               "ziv_listed_only": 0, "cab_models": 0}
    for a in ordered:
        ce = a.get("count_evidence") or {}
        vals = set(ce.values())
        for k in ("bemanicn_qty", "ziv_comment"):
            if k in vals:
                ev_dist[k] += 1
        if vals & REAL_COUNT_EVIDENCE:
            ev_dist["any_real"] += 1
        elif vals:
            ev_dist["ziv_listed_only"] += 1
        if a.get("cab_models"):
            ev_dist["cab_models"] += 1
    print("merge: count_evidence real=%d (bemanicn_qty=%d, ziv_comment=%d), "
          "ziv_listed-only=%d; %d entries with cab_models"
          % (ev_dist["any_real"], ev_dist["bemanicn_qty"],
             ev_dist["ziv_comment"], ev_dist["ziv_listed_only"],
             ev_dist["cab_models"]), file=sys.stderr)

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
        "count_evidence_distribution": ev_dist,       # (m)
        "cross_source_merges": len(merge_decisions),
        "coord_inheritances": len(inherit_log),
        "country_conflicts": conflict_log,
        "inheritance_log": inherit_log,
        "merge_decision_log": merge_decisions,
        "geo_validation": geo_log,
        "china_geocoded": geocode_log,
        # Every cached answer the district gate refused, with what came back
        # and why. Written to the log rather than only printed, because "this
        # pin was rejected" is the claim a reader is most entitled to check:
        # the row visibly falls back to a centroid and nothing else on the map
        # says why it did.
        "china_geocode_rejected": geocode_rejects,
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
