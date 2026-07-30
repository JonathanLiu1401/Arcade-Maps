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
plus an OPTIONAL "game_counts" {slug: int}: per-slug cabinet quantity.
A list entry is NOT automatically one cabinet. When machines[].comment
states a quantity ("8 machines", "4x", "2台"), that number is used and
count_evidence[slug] is "ziv_comment". Otherwise the list-entry count is
only a lower bound (count_evidence "ziv_listed") - never invent a total.
Cabs that only map to "other" are NOT counted; game_counts is absent when
nothing mapped. Optional siblings:
  count_evidence {slug: "ziv_comment"|"ziv_listed"}
  cab_models     {variant_slug: int}  hardware variants from the cab title
                 (Lightning, Valkyrie, DDR gold, etc.), same count rules.

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
    7: "pump_it_up",
    12: "taiko", 173: "sdvx", 267: "gitadora", 284: "maimai_dx",
    506: "chunithm", 549: "museca", 643: "nostalgia", 694: "drs",
    766: "stepmaniax",
    1366: "ongeki", 1556: "dance_around",
}

# Extra series ids fetched by the per-series United States crawl ONLY:
# In The Groove (8), Guitar Hero Arcade (18), Beat Saber (1281),
# StepMania (1536). Without them the US crawl misses arcades whose only
# rhythm cabs are these, because the unsegmented country query 500s and
# the US set is the union of the per-series queries.
#
# Pump It Up (7) and StepManiaX (766) used to live here too and resolve
# to "other"; they now map to real slugs via USA_SERIES / GAME_PATTERNS.
#
# Remaining extras are deliberately NOT part of USA_SERIES: that dict
# doubles as the seriesID -> canonical-slug map, so listing them there
# would map their machines into game_counts. They still resolve to
# "other" via the no-pattern-hit fallback and are never counted.
USA_EXTRA_SERIES = [8, 18, 1281, 1536]

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
#
# maimai classic vs maimai DX is NOT decided here: both hit the shared
# "maimai" / "舞萌" token. _machine_slugs special-cases the split so a
# classic title never lands on maimai_dx (and a DX title never lands on
# the classic maimai slug). Order of the remaining patterns still
# matters for overlapping tokens.
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
    ("sound voltex", "sdvx"),
    # maimai tokens: placeholder slug; _machine_slugs rewrites to
    # maimai (classic) and/or maimai_dx via the ordered classic/DX rules.
    ("maimai", "maimai_dx"),
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
    # promoted out of the old "other" bucket (see research cab-variant spec)
    ("pump it up", "pump_it_up"), ("pumpitup", "pump_it_up"),
    ("stepmaniax", "stepmaniax"), ("stepmania x", "stepmaniax"),
    ("wacca", "wacca"), ("华卡音舞", "wacca"),
    ("groove coaster", "groove_coaster"), ("音炫轨道", "groove_coaster"),
    ("crossbeats", "crossbeats"), ("crossbeat", "crossbeats"),
    ("beatstream", "beatstream"),
]

_CLOSED_RE = re.compile(r'closed|permanently closed|閉店', re.I)

# ---- quantity parser over machines[].comment ----------------------------
# A ZIv machines[] element is a cab *title* entry, not a cabinet count.
# Real quantities live in free-text comments ("8 machines", "4x", "2台").
# False counts (treating floor numbers / version strings / yen as qty)
# are worse than no count: reject those hard.
#
# Evidence vocabulary (per slug, written next to game_counts):
#   "ziv_comment" - at least one machine for the slug had a parsed qty;
#                   the number is a real total and may render as "xN".
#   "ziv_listed"  - we only know N distinct list entries exist; lower
#                   bound, UI must say "N listed" (or bare chip for 1).

_UNIT_WORD = r"(?:machines?|cabs?|cabinets?|units?)"
# Optional short English descriptors between a number and a unit word
# ("8 LIGHTNING MODEL machines", "12 HG cabinets in total.").
_DESC_WORDS = r"(?:[A-Za-z./★☆*-]+\s+){0,4}"

_RE_QTY_PURE_NX = re.compile(r"^\s*(\d+)\s*[xX×]\s*$")
_RE_QTY_PURE_XN = re.compile(r"^\s*[xX×]\s*(\d+)\s*$")
_RE_QTY_NX_PREFIX = re.compile(r"^\s*(\d+)\s*[xX×]\b")
_RE_QTY_MULTI_NX = re.compile(r"(\d+)\s*[xX×]\b")
_RE_QTY_SETS_OF = re.compile(r"(\d+)\s*sets?\s+of\s+(\d+)", re.I)
_RE_QTY_IN_TOTAL = re.compile(
    r"(\d+)\s+" + _DESC_WORDS + _UNIT_WORD + r"\s+in\s+total", re.I)
_RE_QTY_THERE_ARE = re.compile(
    r"(?i)there\s+are\s+(\d+)\s+" + _DESC_WORDS + _UNIT_WORD)
_RE_QTY_N_WORD = re.compile(
    r"(?i)(\d+)\s+" + _DESC_WORDS + r"(" + _UNIT_WORD + r")\b")
_RE_QTY_N_WORD_TIGHT = re.compile(
    r"(?i)(\d+)\s*(" + _UNIT_WORD + r")\b")
_RE_QTY_LINKED = re.compile(
    r"(?i)(\d+)\s+linked(?:\s+side-by-side)?\s+" + _UNIT_WORD)
_RE_QTY_PAIR_OF = re.compile(
    r"(?i)(?:a\s+)?side-by-side\s+pair\s+of\s+(\d+)\s+linked")
_RE_QTY_VER_THEN_NX = re.compile(
    r"(?i)\bver(?:sion)?\.?\s*[\d.]+,\s*(\d+)\s*[xX×]\b")
_RE_QTY_CJK_INSTALL = re.compile(r"(\d+)\s*台(?:設置|置いて)")
_RE_QTY_CJK_TAI = re.compile(r"(\d+)\s*台")
_RE_QTY_N_TAIKO = re.compile(r"(?i)^\s*(\d+)\s+taiko\s*$")
_RE_QTY_SILVER_GOLD = re.compile(
    r"(?i)(\d+)\s+silver\s+cabs?,\s*(\d+)\s+gold")
_RE_QTY_N_HD = re.compile(r"(?i)(\d+)\s+HD\s+cabinets?\b")
_RE_QTY_ANOTHER_PAIR = re.compile(r"(?i)as well as another pair")

# Plausible cabinet totals. Real mega-venues top out well under this
# (GiGO Akihabara Bldg 5 has a 52x Gundam comment); anything above is
# almost certainly a false parse and is rejected.
_QTY_MAX = 200


def _qty_hard_reject(text):
    """True when `text` has digits that are NOT a cabinet quantity."""
    t = text.strip()
    if re.match(r"^\d+F$", t, re.I):
        return True
    if re.match(r"(?i)^ver(?:sion)?\.?\s*[\d.]+$", t):
        return True
    if re.match(r"(?i)^\d+\s*(yen|円)$", t):
        return True
    if re.match(r"(?i)^\d+P$", t):
        return True
    if re.match(r"(?i)^japanese\s+\d+P\b", t):
        return True
    # "Cabinet 1", "Cabinet 2 - First generation Lightning..."
    if re.match(r"(?i)^cabinet\s+\d+\b", t):
        return True
    # model names: "X2 cabinet.", "XG2 cabinet.", "XG cabinet, 2F"
    if re.match(r"(?i)^xg?\d*\s*cabinet\b", t):
        return True
    if re.match(r"(?i)^\d+(st|nd|rd|th)\s+gen\b", t):
        return True
    if re.match(r"(?i)^\d+g\s+switches", t):
        return True
    if re.search(r"(?i)\b\d+\s+in\s+\d+\s+cab", t):
        return True
    if re.match(r"(?i)^\d{4}\s+cabinet", t):
        return True
    if (re.match(r"(?i)^(jpn\.?\s*)?version\b", t)
            and not re.search(
                r"(?i)\d+\s*(?:[A-Za-z./-]+\s+){0,4}" + _UNIT_WORD, t)):
        return True
    if re.search(r"(?i)\b\d+\s*player\s+cab", t):
        return True
    if re.search(r"(?i)\b\d+\s*screen\s+cab", t):
        return True
    if (re.search(r"(?i)\b\d+\s*songs?\b", t)
            and not re.search(r"(?i)\d+\s*" + _UNIT_WORD, t)):
        return True
    # "Part of the 4 cabinets..." is a location note, not a total.
    if re.match(r"(?i)^part of the\b", t):
        return True
    return False


def parse_machine_quantity(comment):
    """Parse a ZIv machine comment into a cabinet count, or None.

    Returns an int in [1, _QTY_MAX] only when the comment explicitly
    states a quantity. Never invents a count from price/version/floor
    noise. Public so unit tests and other scrapers can call it directly.
    """
    if not comment or not isinstance(comment, str):
        return None
    text = comment.strip()
    if not text:
        return None
    if _qty_hard_reject(text):
        return None

    m = _RE_QTY_SETS_OF.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= 50 and 1 <= b <= 50:
            return a * b

    m = _RE_QTY_PAIR_OF.search(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 50:
            return 2 * n  # "pair of 4 linked" => 8

    m = _RE_QTY_PURE_NX.match(text) or _RE_QTY_PURE_XN.match(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= _QTY_MAX:
            return n

    multi = _RE_QTY_MULTI_NX.findall(text)
    if len(multi) >= 2:
        nums = [int(x) for x in multi]
        if all(1 <= x <= _QTY_MAX for x in nums):
            return sum(nums)

    m = _RE_QTY_NX_PREFIX.match(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= _QTY_MAX:
            return n

    m = _RE_QTY_VER_THEN_NX.search(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= _QTY_MAX:
            return n

    m = _RE_QTY_SILVER_GOLD.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= _QTY_MAX and 1 <= b <= _QTY_MAX:
            return a + b

    m = _RE_QTY_IN_TOTAL.search(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= _QTY_MAX:
            return n

    m = _RE_QTY_THERE_ARE.search(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= _QTY_MAX:
            return n

    m = _RE_QTY_LINKED.search(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= _QTY_MAX:
            if _RE_QTY_ANOTHER_PAIR.search(text):
                return n + 2
            return n

    m = _RE_QTY_N_TAIKO.match(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= _QTY_MAX:
            return n

    m = _RE_QTY_N_HD.search(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= _QTY_MAX:
            return n

    for rx in (_RE_QTY_N_WORD, _RE_QTY_N_WORD_TIGHT):
        matches = list(rx.finditer(text))
        if matches:
            n = int(matches[0].group(1))
            if 1 <= n <= _QTY_MAX:
                return n

    if "台" in text:
        # Ordinal "1台目" is a cabinet index, not a total, unless the
        # comment also has an install form ("2台置いてあり1台目...").
        if "台目" in text and not re.search(r"台設置|台置", text):
            return None
        # "新筐体2台ノーマルタイプ1台" => sum of type counts.
        if re.search(r"新筐体|ノーマル", text):
            nums = [int(x) for x in _RE_QTY_CJK_TAI.findall(text)]
            if nums and all(1 <= x <= _QTY_MAX for x in nums):
                return sum(nums)
        m = _RE_QTY_CJK_INSTALL.search(text)
        if m:
            n = int(m.group(1))
            if 1 <= n <= _QTY_MAX:
                return n
        nums = _RE_QTY_CJK_TAI.findall(text)
        if len(nums) == 1:
            n = int(nums[0])
            if 1 <= n <= _QTY_MAX:
                return n
        if nums and "台目" not in text:
            n = int(nums[0])
            if 1 <= n <= _QTY_MAX:
                return n
    return None


# ---- cab-model variants from the machine game NAME ----------------------
# Ordered rules; first match wins within each family. Patterns are applied
# case-insensitively to a single cab-title string. Spec source: research
# cab-variant hierarchy (maimai classic/DX split, IIDX Lightning, SDVX
# Valkyrie/NEMSYS, DDR gold/Universal/legacy, taiko regional, ...).

# maimai classic (pre-DX). Applied BEFORE the DX rule. A title may match
# both families across two different machine rows of one arcade; those
# produce two slugs, not a move.
_RE_MAIMAI_CLASSIC = [
    re.compile(r"^\s*maimai\b(?!\s*(?:dx|でらっくす))", re.I),
    re.compile(r"^舞萌\s*\((?!.*dx)", re.I),
    re.compile(r"^maimaiPLUS\b", re.I),
]
_RE_MAIMAI_DX = re.compile(
    r"maimai\s*dx|maimai\s*でらっくす|舞萌\s*dx", re.I)

# Cab-flag variants (hardware), keyed by the parent game slug they refine.
# Each entry: (variant_slug, compiled regex on the full title).
CAB_VARIANT_RULES = [
    # DDR three-state: gold and universal are positive; bare A/A20/A3/WORLD
    # is deliberately NOT asserted as white (unknown). Legacy is offline.
    ("ddr_gold", re.compile(
        r"(?:dancedancerevolution|dance\s*dance\s*revolution).*"
        r"\(20th anniversary model\)", re.I)),
    ("ddr_universal", re.compile(
        r"(?:dancedancerevolution|dance\s*dance\s*revolution).*"
        r"\(universal model\)", re.I)),
    # Legacy / CRT: require a DDR-family title token. Bare "7thMIX" /
    # "Solo" must NOT fire on beatmania III APPEND 7thMIX etc.
    ("ddr_legacy", re.compile(
        r"(?:dance\s*dance\s*revolution|dancedancerevolution)\s*"
        r"(?:extreme|ddrmax|supernova|solo|[2-7]th\s*mix|x2|x3)|"
        r"dancing\s*stage|"
        r"\bddrmax\b|"
        r"\bddr\s*(?:solo|[2-7]th\s*mix)\b", re.I)),
    # SOUND VOLTEX
    ("sdvx_vm", re.compile(
        r"sound\s*voltex.*\(valkyrie model\)", re.I)),
    ("sdvx_nemsys", re.compile(
        r"sound\s*voltex.*\(nemsys model\)", re.I)),
    # beatmania IIDX
    ("iidx_lm", re.compile(
        r"beatmania\s*iidx.*\(lightning model\)", re.I)),
    # Taiko regional builds (full-width parens must match)
    ("taiko_asia", re.compile(
        r"ニジイロVer\.[\(（]アシア版[\)）]")),
    ("taiko_jp", re.compile(
        r"太鼓の達人\s*ニジイロVer\.$")),
    ("taiko_us", re.compile(
        r"nijiro\s*usa|taiko.*nijiro\s*usa", re.I)),
]


def cab_variants_for_title(name):
    """Hardware variant slugs a single cab title asserts, or empty set.

    Never infers 'standard' / white / non-Lightning from a bare title;
    only positive pattern hits are returned.
    """
    if not name:
        return set()
    out = set()
    for variant, rx in CAB_VARIANT_RULES:
        if rx.search(name):
            out.add(variant)
    return out


def _maimai_slugs_for_title(name):
    """Classic and/or DX maimai slugs for one title (ordered rules)."""
    if not name:
        return set()
    out = set()
    for rx in _RE_MAIMAI_CLASSIC:
        if rx.search(name):
            out.add("maimai")
            break
    if _RE_MAIMAI_DX.search(name):
        out.add("maimai_dx")
    # Bare "maimai" token with no classic/DX decision still needs a home:
    # if neither rule fired but the title carries maimai/舞萌, treat as
    # classic only when it is clearly pre-DX; otherwise leave empty so
    # the seriesID path (284 -> maimai_dx) can still assign DX.
    if not out:
        low = name.lower()
        if "maimai" in low or "舞萌" in name:
            # seriesID 284 is DX; name-only classic detection already
            # ran above. Remaining bare hits without dx/でらっくす are
            # classic (e.g. "maimai FiNALE", "maimai").
            if not re.search(r"(?i)dx|でらっくす", name):
                out.add("maimai")
            else:
                out.add("maimai_dx")
    return out


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
    seriesID via USA_SERIES first, then name-substring patterns.

    maimai is special: classic (pre-DX) and DX are different game slugs.
    The ordered classic/DX rules run on the title. seriesID 284 only
    contributes maimai_dx when the title does not assert classic alone.
    """
    slugs = set()
    low = (nm or "").lower()
    is_maimai = ("maimai" in low or "舞萌" in (nm or ""))
    if is_maimai:
        # Title rules are authoritative for the classic/DX split.
        title_slugs = _maimai_slugs_for_title(nm)
        slugs |= title_slugs
        if sid is not None and sid in USA_SERIES:
            mapped = USA_SERIES[sid]
            if mapped == "maimai_dx":
                # seriesID 284 is the DX series. Honour a classic-only
                # title assertion; otherwise ensure maimai_dx is present.
                if "maimai" in title_slugs and "maimai_dx" not in title_slugs:
                    pass  # classic title wins over the seriesID default
                else:
                    slugs.add("maimai_dx")
            else:
                slugs.add(mapped)
        return slugs

    if sid is not None and sid in USA_SERIES:
        slugs.add(USA_SERIES[sid])
    for pat, slug in GAME_PATTERNS:
        if pat in low or pat in (nm or ""):
            # Skip the maimai placeholder pattern here; handled above.
            if slug == "maimai_dx" and pat in ("maimai", "舞萌"):
                continue
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
    for item in machines:
        if len(item) >= 2:
            nm, sid = item[0], item[1]
        else:
            continue
        slugs |= _machine_slugs(nm, sid) or {"other"}
    return sorted(slugs) or ["other"]


def _counts_and_evidence_for_machines(machines_with_comments):
    """Per-arcade game_counts, count_evidence, and cab_models.

    machines_with_comments: iterable of (name, series_id, comment).

    Counting rules (never invent a total):
      - If any machine of a slug has a comment-parsed quantity, sum those
        parsed quantities (entries with no parseable comment contribute
        nothing to a ziv_comment total - the comment is the authority).
        When SOME entries of a slug have comments and some do not, sum
        (parsed qtys) + 1 per unparsed entry, still tagged ziv_comment
        because at least one real quantity was asserted.
      - If no machine of a slug has a parseable quantity, the count is the
        number of list entries (lower bound) with evidence ziv_listed.
      - "other" is never counted.
      - cab_models uses the same rules, keyed by variant slug from the
        title (Lightning, Valkyrie, DDR gold, ...).
    """
    # slug -> list of per-entry quantities (int) or None if unparsed
    per_slug = {}
    per_variant = {}
    for nm, sid, comment in machines_with_comments:
        slugs = _machine_slugs(nm, sid)
        qty = parse_machine_quantity(comment)
        for slug in slugs:
            per_slug.setdefault(slug, []).append(qty)
        for variant in cab_variants_for_title(nm):
            per_variant.setdefault(variant, []).append(qty)

    def _fold(entries):
        """(total, evidence) from a list of per-entry qty-or-None."""
        parsed = [q for q in entries if q is not None]
        unparsed = len(entries) - len(parsed)
        if parsed:
            # Real comment quantity present. Unparsed siblings still count
            # as at least one cab each (they exist in the list).
            total = sum(parsed) + unparsed
            return total, "ziv_comment"
        # list-entry lower bound only
        return len(entries), "ziv_listed"

    counts = {}
    evidence = {}
    for slug, entries in per_slug.items():
        total, ev = _fold(entries)
        if total > 0:
            counts[slug] = total
            evidence[slug] = ev

    cab_models = {}
    for variant, entries in per_variant.items():
        total, _ev = _fold(entries)
        if total > 0:
            cab_models[variant] = total

    return counts, evidence, cab_models


def _counts_for_machines(machines):
    """Backward-compatible wrapper: {slug: count} from (nm, sid) pairs.

    Treats every list entry as quantity 1 with no comment (ziv_listed).
    Prefer _counts_and_evidence_for_machines when comments are available.
    """
    counts, _ev, _cm = _counts_and_evidence_for_machines(
        [(nm, sid, None) for nm, sid in machines])
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
        # (name, series_id, comment) - comment drives real quantities
        machines = []
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
                comment = c.get("comment")
                if comment is not None:
                    comment = str(comment)
                machines.append((nm, sid, comment))
            else:
                machines.append((str(c), None, None))
        machines = [(nm, sid, comment) for nm, sid, comment in machines
                    if nm and not _CLOSED_RE.search(nm)]
        machines_ns = [(nm, sid) for nm, sid, _ in machines]
        cabs = [nm for nm, _ in machines_ns]
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
            "games": _slugs_for_machines(machines_ns),
            "source": "ziv",
            "source_url": ARCADE_URL % aid,
            "notes": notes,
            "country": country,
        }
        counts, evidence, cab_models = _counts_and_evidence_for_machines(
            machines)
        if counts:
            out[aid]["game_counts"] = {s: counts[s] for s in sorted(counts)}
            out[aid]["count_evidence"] = {
                s: evidence[s] for s in sorted(evidence)}
        if cab_models:
            out[aid]["cab_models"] = {
                s: cab_models[s] for s in sorted(cab_models)}
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
                ce = merged[aid].get("count_evidence") or {}
                for slug, n in (row.get("game_counts") or {}).items():
                    row_ev = (row.get("count_evidence") or {}).get(
                        slug, "ziv_listed")
                    if slug not in gc:
                        gc[slug] = n
                        ce[slug] = row_ev
                    else:
                        # Prefer a comment-backed total over a list bound;
                        # within the same evidence class take the max.
                        cur_ev = ce.get(slug, "ziv_listed")
                        if row_ev == "ziv_comment" and cur_ev != "ziv_comment":
                            gc[slug] = n
                            ce[slug] = row_ev
                        elif row_ev == cur_ev and n > gc[slug]:
                            gc[slug] = n
                        elif (row_ev == "ziv_comment"
                              and cur_ev == "ziv_comment"
                              and n > gc[slug]):
                            gc[slug] = n
                if gc:
                    merged[aid]["game_counts"] = {s: gc[s]
                                                  for s in sorted(gc)}
                    merged[aid]["count_evidence"] = {
                        s: ce[s] for s in sorted(ce)}
                cm = merged[aid].get("cab_models") or {}
                for slug, n in (row.get("cab_models") or {}).items():
                    if n > cm.get(slug, 0):
                        cm[slug] = n
                if cm:
                    merged[aid]["cab_models"] = {s: cm[s]
                                                 for s in sorted(cm)}
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
