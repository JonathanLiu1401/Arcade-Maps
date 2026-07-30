"""Measured per-country, per-game arcade play prices from real quoted strings.

Why this module exists
----------------------
enrich.py has shipped a hand-guessed PRICE_DEFAULTS table of country
"community norms" (HK: "HKD 8-15/play typical"). Nobody measured them and at
least one is simply wrong: a Hong Kong player reported the real standard price
is HK$6 for one maimai/chunithm credit, and the repo's own data agrees.

Meanwhile every ZIv machine row already carries a free-text quoted price,
harvested into data/enrichment.json as

    arcades[<arcade_id>]["machine_prices"] = {game_slug: "HK$6.00 for 3 songs"}

That is ~5,900 real quoted prices nothing aggregated. This module parses them,
aggregates per country+game, and attaches an evidence tier so the UI can say
"HK$6 per credit (9 listings)" where the data supports it and say nothing at
all where it does not.

Design rules, in priority order
-------------------------------
1.  A WRONG PRICE IS WORSE THAN NO PRICE. Every ambiguous construction is
    rejected, not guessed. Rejections are counted and reportable.
2.  Store tokens are not money. "3 Medals", "8 creds", "10.0 chips",
    "3 quarters", "20 Points", "6.8 Funcoins" have no public exchange rate.
    They are classified as `token_system` and never coerced to a number.
3.  Play tiers are not interchangeable. Light / Standard / Premium / Galaxy /
    Blaster starts cost different amounts. The STANDARD (base) tier wins; a
    Premium figure is never averaged in as if it were the standard price.
4.  The headline figure is the MODE, not the mean and not an interpolated
    median. The mode is always an amount somebody actually quoted. A median
    over an even sample can invent a value that no store charges (a {6, 8}
    cell medians to 7.00, and "HK$7 per credit" is exactly the fabrication
    this module exists to remove). `median` is still emitted for reference.
5.  LOCAL CURRENCY ONLY. Nothing here is converted. js/format.js converts at
    render time against data/fx_rates.json, which scrapers/fx.py refreshes
    weekly, so displayed USD/JPY/CNY figures stay current with no data
    rebuild. Baking converted values in here would freeze them.

Public API (what enrich.py should call)
---------------------------------------
    import prices

    table = prices.build_price_table(enrichment_arcades, arcade_countries,
                                     as_of="2026-07-29")

      enrichment_arcades : dict  {arcade_id_str: enrichment_record}
                           (i.e. the "arcades" object of data/enrichment.json)
      arcade_countries   : dict  {arcade_id_str: country_name}
                           (built from data/arcades.json: str(a["id"]) ->
                            a["country"])
      as_of              : str   ISO date stamped onto every cell; defaults to
                           the enrichment file's own `updated` when the caller
                           passes it, else today.

      returns            : dict, JSON-serializable, see build_price_table.

Lower-level helpers, all pure and unit-tested in test_prices.py:

    prices.parse_price(text, local_currency=None) -> dict | None
    prices.classify(text, local_currency=None)    -> dict   (with reject reason)
    prices.aggregate(rows, ...)                   -> dict

Run `python scrapers/prices.py` to print the measured table and coverage.
"""

from __future__ import annotations

import collections
import json
import os
import re
import statistics
import sys
from datetime import date

# --------------------------------------------------------------- currencies -

YEN = "¥"        # yen sign
YEN_W = "￥"      # full-width yen sign
WON = "₩"
WON_W = "￦"

# Prefix tokens, longest-first at match time. Mirrors js/panel.js CUR_TOKENS so
# the Python table and the browser parser agree on what a currency looks like.
CURRENCY_TOKENS = [
    ("CN" + YEN, "CNY"), ("CN" + YEN_W, "CNY"),
    ("JP" + YEN, "JPY"), ("JP" + YEN_W, "JPY"),
    ("US$", "USD"), ("HKD$", "HKD"), ("HK$", "HKD"), ("NT$", "TWD"),
    ("AUD$", "AUD"), ("A$", "AUD"), ("CA$", "CAD"), ("S$", "SGD"),
    ("MOP$", "MOP"), ("MX$", "MXN"), ("R$", "BRL"),
    ("Rp.", "IDR"), ("Rp", "IDR"), ("RM", "MYR"),
    ("USD", "USD"), ("JPY", "JPY"), ("CNY", "CNY"), ("HKD", "HKD"),
    ("TWD", "TWD"), ("KRW", "KRW"), ("PHP", "PHP"), ("Php", "PHP"),
    ("THB", "THB"), ("IDR", "IDR"), ("VND", "VND"), ("SGD", "SGD"),
    ("MYR", "MYR"), ("AUD", "AUD"), ("NZD", "NZD"), ("GBP", "GBP"),
    ("EUR", "EUR"), ("CAD", "CAD"),
    (WON, "KRW"), (WON_W, "KRW"),
    ("£", "GBP"), ("€", "EUR"),
    ("₱", "PHP"), ("฿", "THB"),
    ("₫", "VND"), ("đ", "VND"),
]

# Suffix tokens: "3 SGD", "100 JPY", "3 yuan" written as "3元", "100Y".
# "Y" and the CJK unit characters are guarded: they only resolve when the
# store's own country already uses that currency, because a bare "Y" in an
# English string is far more often a stray letter than a yen sign.
SUFFIX_TOKENS = [(t, c) for t, c in CURRENCY_TOKENS if t.isalpha()]
GUARDED_SUFFIX = [("元", "CNY"), ("円", "JPY"), ("Y", "JPY")]

_CODE = {}
for _t, _c in CURRENCY_TOKENS:
    _CODE.setdefault(_t, _c)

_ordered = sorted(CURRENCY_TOKENS, key=lambda t: -len(t[0]))
_ALTS = "|".join(re.escape(t[0]) for t in _ordered)
_NUM = r"[0-9][0-9,. ]*[0-9]|[0-9]"

PREFIX_RE = re.compile("(" + _ALTS + r")\s*(" + _NUM + ")")

_SUF_ALTS = "|".join(re.escape(t[0]) for t in
                     sorted(SUFFIX_TOKENS, key=lambda t: -len(t[0])))
SUFFIX_RE = re.compile(r"([0-9][0-9,.]*[0-9]|[0-9])\s*(" + _SUF_ALTS +
                       r")(?![A-Za-z])")

_GRD_ALTS = "|".join(re.escape(t[0]) for t in GUARDED_SUFFIX)
GUARDED_SUFFIX_RE = re.compile(r"([0-9][0-9,.]*[0-9]|[0-9])\s*(" + _GRD_ALTS +
                               r")(?![A-Za-z0-9])")
_GRD_CODE = dict(GUARDED_SUFFIX)

# Continental style: "1.00€ / 3 songs", "0,50€". Only the euro and pound
# glyphs are safe unsuffixed - each means exactly one currency - so unlike the
# guarded CJK suffixes these need no country agreement.
SYMBOL_SUFFIX = [("€", "EUR"), ("£", "GBP")]
SYMBOL_SUFFIX_RE = re.compile(r"([0-9][0-9,.]*[0-9]|[0-9])\s*([" +
                              "".join(t[0] for t in SYMBOL_SUFFIX) + "])")
_SYM_CODE = dict(SYMBOL_SUFFIX)

# A bare glyph only resolves against a compatible local currency. "$" in the
# United Kingdom and "¥" in the United Kingdom are both real strings in the
# shipped data, and both are import cabs or copy-paste errors - never GBP.
BARE_RE = re.compile(r"(?<![A-Za-z0-9])([$" + YEN + YEN_W + r"])\s*"
                     r"([0-9][0-9,.]*)")
DOLLAR_CURRENCIES = {"USD", "HKD", "TWD", "AUD", "CAD", "SGD", "NZD",
                     "MOP", "MXN", "BRL"}
YEN_CURRENCIES = {"JPY", "CNY"}

# Currencies with no minor unit in circulation. A dot before exactly three
# digits in one of these is a thousands separator ("Rp10.900" is 10,900 rupiah,
# not ten rupiah ninety), which is how Indonesian and Vietnamese listings are
# written throughout the data.
ZERO_DECIMAL = {"JPY", "KRW", "VND", "IDR"}

# ------------------------------------------------------------ country table -

# merge.py's exact country strings -> the currency a store there prices in.
# Used both to resolve ambiguous glyphs and as the currency sanity gate: a
# quote in any other currency is an import cab or a data error and is dropped.
COUNTRY_CURRENCY = {
    "Japan": "JPY", "United States": "USD", "China": "CNY", "Taiwan": "TWD",
    "South Korea": "KRW", "Singapore": "SGD", "Malaysia": "MYR",
    "Thailand": "THB", "Philippines": "PHP", "Indonesia": "IDR",
    "Hong Kong": "HKD", "Australia": "AUD", "United Kingdom": "GBP",
    "Canada": "CAD", "New Zealand": "NZD", "Vietnam": "VND", "Macau": "MOP",
    "Mexico": "MXN", "Brazil": "BRL",
    # Euro area
    "Spain": "EUR", "Netherlands": "EUR", "France": "EUR", "Germany": "EUR",
    "Ireland": "EUR", "Italy": "EUR", "Belgium": "EUR", "Portugal": "EUR",
    "Austria": "EUR", "Finland": "EUR", "Greece": "EUR", "Slovakia": "EUR",
    "Slovenia": "EUR", "Estonia": "EUR", "Latvia": "EUR", "Lithuania": "EUR",
    "Luxembourg": "EUR", "Malta": "EUR", "Cyprus": "EUR", "Croatia": "EUR",
}

# Static per-currency plausibility bands for ONE credit / one standard play.
# Deliberately static rather than FX-derived: an FX-derived band makes the
# table non-reproducible, because a borderline value would flip in or out of
# the table every time the weekly rate moved. Bands are wide - they exist to
# catch parse artifacts (JP¥1, IDR 7.00) and unit confusion, not to enforce
# an opinion about what an arcade should charge.
PLAUSIBLE = {
    "JPY": (50, 600),
    "USD": (0.25, 10),
    "CNY": (1, 30),
    "KRW": (100, 5000),
    "TWD": (5, 200),
    "HKD": (2, 50),
    "PHP": (5, 300),
    "SGD": (0.30, 20),
    "MYR": (1, 30),
    "THB": (10, 300),
    "IDR": (1000, 100000),
    "VND": (5000, 500000),
    "AUD": (0.50, 15),
    "NZD": (0.50, 15),
    "GBP": (0.20, 10),
    "EUR": (0.20, 10),
    "CAD": (0.50, 15),
    "MOP": (2, 50),
    "MXN": (5, 200),
    "BRL": (1, 50),
}

# ------------------------------------------------------------- text masking -

# Parenthesised asides and "if/when/except" clauses carry conditions, not
# prices: "HK$6.00 / 3 songs (4 songs if multiplay)" is the STANDARD HK$6
# maimai price, and reading "multiplay" out of that aside would throw away the
# single most important row in the whole dataset. They are masked (blanked to
# spaces, so offsets survive) before soft tier keywords are scanned.
#
# Hard tier keywords are still scanned on the raw text, because a parenthesised
# "(VIP)" or "(Platinum Card)" genuinely does name a cheaper members-only tier
# that must not be read as the walk-in price.
PAREN_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
CLAUSE_RE = re.compile(r"(?i)\b(?:if|when|except|unless|otherwise|also)\b"
                       r"[^/|;\n]*")

# scope "raw"  : scanned on the original text, parentheses included
# scope "soft" : scanned only outside parentheses / conditional clauses
TIER_PATTERNS = [
    # --- non-standard, more expensive or members-only tiers -> reject ---
    (r"premium", "reject", "raw"),
    (r"galaxy", "reject", "raw"),
    (r"blaster", "reject", "raw"),
    (r"deluxe", "reject", "raw"),
    (r"\bcourse\b", "reject", "raw"),
    (r"\bvip\b", "reject", "raw"),
    (r"\bplatinum\b", "reject", "raw"),
    (r"\bplat\b", "reject", "raw"),
    (r"\bgold\b", "reject", "raw"),
    (r"\belite\b", "reject", "raw"),
    # Loyalty-card ladders. The higher card colours are members-only discount
    # rates; the walk-in price is the entry card. Real ladders in the data:
    # PH "Yellow card / Blue card", NZ "Welcome / Blue&Gold / Platinum",
    # AU "Regular [Red Card] / VIP [Blue, Gold, Platinum Card]".
    (r"\bblue\b", "reject", "raw"),
    (r"\bsilver\b", "reject", "raw"),
    (r"\bmembers?\b", "reject", "raw"),
    (r"\badvanced\b", "reject", "raw"),
    (r"\bforte\b", "reject", "raw"),
    (r"\bexpert option", "reject", "raw"),
    (r"to continue", "reject", "raw"),
    (r"\bguest\b", "reject", "raw"),
    # --- multiplayer / doubles: one credit, two players, twice the money ---
    (r"\bdoubles?\b", "reject", "soft"),
    (r"\bDP\b", "reject", "soft"),
    (r"\bversus\b", "reject", "soft"),
    (r"\bmulti[- ]?play", "reject", "soft"),
    (r"\bextra\b", "reject", "soft"),
    (r"\b2\s*P\b", "reject", "soft"),
    (r"\btwo\s+player", "reject", "soft"),
    (r"\b2\s+players?\b", "reject", "soft"),
    # --- explicit standard / base tier ---
    (r"standard", "base", "raw"),
    (r"\bnormal\b", "base", "raw"),
    (r"\bbasic\b", "base", "raw"),
    # Entry rung of a loyalty ladder: the price anybody walking in pays.
    (r"\bwelcome\b", "base", "raw"),
    (r"\bvisitor\b", "base", "raw"),
    # "Regular" is the entry rung ONLY when it is not the second half of
    # "$3.75 Approximate Cost / $2.50 Approximate Cost for $100 reload",
    # where the reload rate is the discounted one. BUNDLE_RE already drops
    # reload lines, so this stays a plain entry-tier label.
    (r"\bregular\b", "base", "raw"),
    (r"\bred\b", "base", "raw"),
    (r"\byellow\b", "base", "raw"),
    (r"\bsingles?\b", "base", "raw"),
    # "1P" / "one player" only marks a tier outside a parenthetical. Inside
    # one it is describing the songs you get ("3 songs (1P and 2P)"), and
    # letting it set a tier there lets a members-card row outrank the
    # walk-in row above it.
    (r"\b1\s*P\b", "base", "soft"),
    (r"\bone\s+player", "base", "soft"),
    # --- light / lite: real, cheaper, fewer features. Kept but ranked below
    #     an explicit standard price so it is only used when nothing else is.
    (r"\blight\b", "light", "raw"),
    (r"\blite\b", "light", "raw"),
]
_TIER_COMPILED = [(re.compile(p, re.I), tag, scope)
                  for p, tag, scope in TIER_PATTERNS]

# Not a per-play price at any tier: time passes, rentals, day tickets.
TIME_RE = re.compile(r"(?i)\b(hours?|hrs?|minutes?|mins?|all[- ]day|daily\s*pass"
                     r"|unlimited|rental|free\s*play|freeplay)\b")

# Promotional / conditional pricing. A price that only applies on Wednesday or
# during a limited promotion is not the store's standard price.
PROMO_RE = re.compile(r"(?i)\b(promo|promotion|discount|happy\s*hour|"
                      r"monday|tuesday|wednesday|thursday|friday|saturday|"
                      r"sunday|weekday|weekend|holiday)s?\b")

# Bundle / stored-value pricing: money buys a pile of credits or tokens, and
# the per-play cost is that pile divided by the credits a play consumes. Those
# amounts are not play prices and reading them as such produces figures like
# "GBP 50 per credit".
BUNDLE_RE = re.compile(
    r"(?i)(worth\s+of"
    r"|\b\d+\s*(?:credits?|tokens?|coins?|chips?|points?|pts?)\s*(?:for|is|=|:)"
    r"|(?:for|=|:)\s*\d{2,}\s*(?:credits?|tokens?|coins?|chips?|points?)"
    r"|\b\d+\s*(?:credits?|tokens?)\s*[≈~]"
    r"|\breload\b)")

# A token exchange rate, not a price: "1 TOKEN = Rp. 2500,00", "1 FUN = Rp.
# 1000,00", "1 Tizo = Rp.1.000", "1 Token = R4". The money named is what one
# token costs; the play costs several. Reading these as play prices is how a
# 7-token Rp 17,500 play became "IDR 2500". Whole-string reject: once a token
# rate is stated, every figure in the string is denominated in tokens.
TOKEN_RATE_RE = re.compile(
    r"(?i)\b\d+\s*(?:token|tizo|fun|goldie|zip|coin|chip|medal|credit|cred)s?\b"
    r"\s*(?:=|is\b|:)\s*[^/|;]{0,12}?[0-9¥￥$£€₱"
    r"₩￦₫]")

# Stored-value reload economics. "$3.75 Approximate Cost / $2.50 Approximate
# Cost for $100 reload" prices a play in credits bought at a volume discount:
# the figures depend on how much the player loaded, so neither is a posted
# price. Whole-string reject - the cheap figure is the one a naive nearest-
# label reading would pick, which is the wrong direction to be wrong in.
RELOAD_RE = re.compile(r"(?i)\breload\b")

# Unit prices. "$2.10 Per Credit" is a play price, because outside token
# arcades one credit is one play; that convention is what the Australian and
# UK listings rely on. "3元/币" (3 yuan per COIN) is not, because a coin is a
# sub-credit unit and a play swallows several - reading it as a play price
# understates by whatever the coins-per-play ratio is. So a per-CREDIT rate is
# kept and a per-COIN / per-TOKEN rate is rejected outright.
PER_CREDIT_RE = re.compile(r"(?i)(per\s+credit|/\s*credits?\b)")
PER_COIN_RE = re.compile(r"(?i)(per\s+(?:coin|token)|/\s*(?:coins?|tokens?|币))")
CREDITS_PER_PLAY_RE = re.compile(
    r"(?i)\b(\d+)\s*(?:credits?|coins?|tokens?|tizo|chips?)\b")

SONGS_RE = re.compile(r"(?i)\b([0-9]+)\s*(?:\+\s*[0-9]+\s*)?(?:songs?|tracks?|stages?)\b")

# A second bare decimal in a window is usually the NEXT price in a
# slash-separated list that lost its currency token ("$3.00/2.80 (VIP)").
# Truncate the window there so the tier keywords of the next price are not
# attributed to this one.
PSEUDO_RE = re.compile(r"(?<![A-Za-z0-9.,])([0-9]+\.[0-9]{2})(?![0-9])")
UNIT_AFTER_RE = re.compile(
    r"(?i)^\s*(?:songs?|tracks?|credits?|tokens?|coins?|chips?|players?|"
    r"minutes?|mins?|hours?|hrs?|gp|pts?|points?|medals?|tizo|stages?|plays?)")

# Store-token vocabulary. Present + no currency token at all => token_system.
TOKEN_WORDS_RE = re.compile(
    r"(?i)\b(credits?|creds?|tokens?|coins?|chips?|medals?|quarters?|points?|"
    r"pts?|tizo|funcoins?|gp|币)\b")
FREE_RE = re.compile(r"(?i)\b(free\s*play|freeplay|free\s+during|no\s+charge)\b")


# ------------------------------------------------------------------ parsing -

def _blank(match):
    return " " * (match.end() - match.start())


def mask_conditions(text):
    """Blank parentheticals and conditional clauses, preserving offsets."""
    masked = PAREN_RE.sub(_blank, text)
    masked = CLAUSE_RE.sub(_blank, masked)
    return masked


def to_amount(raw, code=None):
    """'1,320.00' -> 1320.0, '6,90' -> 6.9, 'Rp10.900' -> 10900.0.

    Returns None for anything that is not a positive number.
    """
    s = str(raw).strip().replace(" ", "").rstrip(".,-")
    if not s:
        return None
    # European "10.900,00": dot thousands + comma decimal.
    if re.search(r"^\d{1,3}(?:\.\d{3})+,\d{1,2}$", s):
        s = s.replace(".", "").replace(",", ".")
    # "6,90" decimal comma.
    elif re.search(r",\d{1,2}$", s) and "." not in s:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    # "10.900" in a currency with no minor unit is ten thousand nine hundred.
    if code in ZERO_DECIMAL and re.search(r"^\d{1,3}(?:\.\d{3})+$", s):
        s = s.replace(".", "")
    try:
        value = float(s)
    except ValueError:
        return None
    return value if value > 0 else None


def _find_hits(masked, local):
    """[(start, end, currency, amount)] for every money mention, in order."""
    hits = []
    spans = []

    def add(start, end, code, raw):
        if any(s <= start < e for s, e in spans):
            return
        amount = to_amount(raw, code)
        if amount is None:
            return
        hits.append((start, end, code, amount))
        spans.append((start, end))

    for m in PREFIX_RE.finditer(masked):
        add(m.start(), m.end(), _CODE[m.group(1)], m.group(2))
    for m in SUFFIX_RE.finditer(masked):
        add(m.start(), m.end(), _CODE[m.group(2)], m.group(1))
    for m in SYMBOL_SUFFIX_RE.finditer(masked):
        add(m.start(), m.end(), _SYM_CODE[m.group(2)], m.group(1))
    for m in GUARDED_SUFFIX_RE.finditer(masked):
        code = _GRD_CODE[m.group(2)]
        if code != local:          # guarded: only when the country agrees
            continue
        add(m.start(), m.end(), code, m.group(1))
    if not hits and local:
        for m in BARE_RE.finditer(masked):
            glyph = m.group(1)
            if glyph == "$" and local not in DOLLAR_CURRENCIES:
                continue
            if glyph in (YEN, YEN_W) and local not in YEN_CURRENCIES:
                continue
            add(m.start(), m.end(), local, m.group(2))
    hits.sort()
    return hits


def _tier_of(win_raw, win_masked):
    """Nearest tier keyword wins.

    Ranking by severity would misread '$2.70 / Standard / Premium Play /
    $10.80 / Galaxy Play': the 2.70 window names both Standard and Premium, and
    the one that applies to 2.70 is simply the closer one.
    """
    best = None
    for rx, tag, scope in _TIER_COMPILED:
        hay = win_raw if scope == "raw" else win_masked
        m = rx.search(hay)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), tag)
    return best[1] if best else "plain"


def _tier_of_before(win_raw, win_masked):
    """Same, for a label that PRECEDES its price - nearest means last."""
    best = None
    for rx, tag, scope in _TIER_COMPILED:
        hay = win_raw if scope == "raw" else win_masked
        last = None
        for m in rx.finditer(hay):
            last = m
        if last and (best is None or last.end() > best[0]):
            best = (last.end(), tag)
    return best[1] if best else "plain"


def _labels_precede(text, hits):
    """True when this listing writes 'Welcome Card $3.80 / Platinum $3.25'
    rather than '$3.80 / Welcome Card / $3.25 / Platinum'.

    Decided per string, because both layouts are common in the data and
    guessing wrong silently swaps a members-only rate for the walk-in price.
    The signal is the text before the FIRST amount: a tier word there means
    the listing labels first.
    """
    if not hits:
        return False
    # Only the segment immediately before the first amount counts, and only
    # when it is short enough to be a label rather than prose. Without this,
    # a preamble sentence like "Standard/Premium Modes Are The Same Price."
    # flips the whole string into backwards mode and every price then inherits
    # the label belonging to the price before it.
    head = re.split(r"[/|;]", text[:hits[0][0]])[-1].strip()
    if not head or len(head) > 25:
        return False
    for rx, _tag, _scope in _TIER_COMPILED:
        if rx.search(head):
            return True
    return False


def _min_units_per_play(text):
    """Smallest credits/coins/tokens count the string says a play costs."""
    counts = [int(m.group(1)) for m in CREDITS_PER_PLAY_RE.finditer(text)]
    return min(counts) if counts else None


def classify(text, local_currency=None):
    """Full parse result including why a string was rejected.

    Returns a dict with `ok` plus, when ok, `amount`, `currency`, `tier` and
    `songs`. When not ok, `reason` is one of:

      empty            - not a usable string
      free_play        - the cab is on free play, there is no price
      token_system     - priced in store tokens/credits/chips with no public
                         exchange rate; never coerced to a number
      no_currency      - a number with no currency this parser trusts
      time_based       - an hour pass / day ticket, not a per-play price
      bundle           - money buys a stored-value pile, not one play
      all_tiers_rejected - every amount in the string is premium/VIP/doubles/
                         continue/promotional
    """
    out = {"ok": False, "reason": "empty", "text": text}
    if not isinstance(text, str) or not text.strip():
        return out

    if FREE_RE.search(text) and not PREFIX_RE.search(text):
        out["reason"] = "free_play"
        return out

    if TOKEN_RATE_RE.search(text) or RELOAD_RE.search(text):
        out["reason"] = "token_system"
        return out

    masked = mask_conditions(text)
    hits = _find_hits(masked, local_currency)

    if not hits:
        if FREE_RE.search(text):
            out["reason"] = "free_play"
        elif TOKEN_WORDS_RE.search(text):
            out["reason"] = "token_system"
        else:
            out["reason"] = "no_currency"
        return out

    min_units = _min_units_per_play(text)
    multi_credit_play = min_units is not None and min_units >= 2
    labels_first = _labels_precede(text, hits)

    candidates = []
    for i, (start, end, code, amount) in enumerate(hits):
        nxt = hits[i + 1][0] if i + 1 < len(hits) else len(masked)
        prev_end = hits[i - 1][1] if i else 0
        win_raw = text[end:nxt]
        win_masked = masked[end:nxt]
        before = text[prev_end:start]

        # Stop the window at a bare decimal that is the next price, not a count.
        pm = PSEUDO_RE.search(win_masked)
        if pm and not UNIT_AFTER_RE.match(win_masked[pm.end():]):
            win_raw = win_raw[:pm.start()]
            win_masked = win_masked[:pm.start()]

        context = before + " " + win_raw
        if TIME_RE.search(context):
            continue
        if PROMO_RE.search(context):
            continue
        if BUNDLE_RE.search(context):
            continue
        if PER_COIN_RE.search(context):
            continue
        if PER_CREDIT_RE.search(context) and multi_credit_play:
            continue

        if labels_first:
            before_masked = masked[prev_end:start]
            tier = _tier_of_before(before, before_masked)
        else:
            tier = _tier_of(win_raw, win_masked)
        if tier == "reject":
            continue
        sm = SONGS_RE.search(win_masked)
        candidates.append({
            "amount": amount,
            "currency": code,
            "tier": tier,
            "songs": int(sm.group(1)) if sm else None,
        })

    if not candidates:
        out["reason"] = "all_tiers_rejected"
        return out

    # A price in the store's own currency beats an aside quoting another.
    if local_currency:
        local_hits = [c for c in candidates if c["currency"] == local_currency]
        if local_hits:
            candidates = local_hits

    rank = {"base": 0, "plain": 1, "light": 2}
    candidates.sort(key=lambda c: (rank[c["tier"]], c["amount"]))
    best = dict(candidates[0])
    best["ok"] = True
    best["reason"] = None
    best["text"] = text
    return best


def parse_price(text, local_currency=None):
    """The parsed standard-tier price, or None. Thin wrapper over classify."""
    result = classify(text, local_currency)
    return result if result.get("ok") else None


# -------------------------------------------------------------- aggregation -

MEASURED_MIN = 5
SPARSE_MIN = 2
# A country-level figure has to be measured across games, not just across rows.
OVERALL_MIN_GAMES = 3


def _tier_for_n(n):
    if n >= MEASURED_MIN:
        return "measured"
    if n >= SPARSE_MIN:
        return "sparse"
    return "unknown"


def _mode(values):
    """Most common value; ties break to the lowest, which is the walk-in
    price far more often than the highest."""
    counts = collections.Counter(values)
    top = max(counts.values())
    return min(v for v, c in counts.items() if c == top)


def _summarise(entries, as_of, currency):
    """entries: [{'amount','arcade','tier','songs'}] already currency-checked."""
    amounts = [e["amount"] for e in entries]
    n = len(amounts)
    cell = {
        "currency": currency,
        "n": n,
        "tier": _tier_for_n(n),
        "as_of": as_of,
    }
    if not n:
        cell["value"] = None
        return cell
    mode = _mode(amounts)
    median = statistics.median(amounts)
    cell.update({
        "value": mode,            # what the UI renders: always a quoted figure
        "mode": mode,
        "median": median,         # reference only; may be an interpolated value
        "min": min(amounts),
        "max": max(amounts),
        "mode_share": round(amounts.count(mode) / float(n), 3),
        "median_differs": abs(median - mode) > 1e-9,
    })
    # Is the modal figure actually representative? Two things have to fail
    # together for it not to be: no single price holds a majority, AND the
    # median disagrees with the mode. Either alone is fine -
    #
    #   US ddr   n=164 mode 1.00 (40% plurality) median 1.00 -> agree, keep.
    #            A plurality across 164 independent arcades where the middle
    #            of the distribution lands on the same figure is a real price.
    #   HK gitadora n=5 spread 2..10 mode 2 (40%) median 6 -> disagree, demote.
    #            This one would have printed "HK$2 per credit" in the very
    #            country the owner complained about.
    #   SG maimai   n=14 mode 3.50 (36%) median 3.15 -> disagree, demote.
    #
    # "measured" is contracted to render as a definite figure, so the tier
    # itself has to carry this, not a side flag a renderer may ignore.
    cell["dispersed"] = (n >= 3
                         and amounts.count(mode) / float(n) <= 0.5
                         and abs(median - mode) > 1e-9)
    songs = [e["songs"] for e in entries if e.get("songs")]
    cell["songs"] = _mode(songs) if songs else None
    tiers = sorted({e["tier"] for e in entries})
    cell["row_tiers"] = tiers
    cell["tier_homogeneous"] = len(tiers) == 1
    arcades = collections.Counter(e["arcade"] for e in entries)
    top_share = max(arcades.values()) / float(n)
    cell["arcades"] = len(arcades)
    cell["max_arcade_share"] = round(top_share, 3)
    if cell["dispersed"] and cell["tier"] == "measured":
        cell["tier"] = "sparse"
        cell["demoted_by"] = "dispersed"
    # One arcade speaking for a whole country is not a measurement.
    if n >= SPARSE_MIN and top_share > 0.5 and len(arcades) < 3:
        cell["tier"] = "unknown"
        cell["rejected_by"] = "single_arcade_dominance"
    return cell


def aggregate(rows, as_of, min_measured=MEASURED_MIN):
    """rows: iterable of (arcade_id, country, game, price_text).

    Returns (countries, stats). Nothing is converted; every figure is in the
    country's own currency.
    """
    global MEASURED_MIN
    saved = MEASURED_MIN
    MEASURED_MIN = min_measured
    try:
        return _aggregate(rows, as_of)
    finally:
        MEASURED_MIN = saved


def _aggregate(rows, as_of):
    per_cell = collections.defaultdict(list)
    per_arcade = collections.defaultdict(list)
    stats = collections.Counter()
    reasons = collections.Counter()
    unmapped = collections.Counter()
    gate_drops = collections.Counter()
    artifacts = []

    for arcade_id, country, game, text in rows:
        stats["rows"] += 1
        if not country:
            stats["no_country"] += 1
            continue
        local = COUNTRY_CURRENCY.get(country)
        if local is None:
            unmapped[country] += 1
        parsed = classify(text, local)
        if not parsed.get("ok"):
            reasons[parsed.get("reason") or "unknown"] += 1
            continue
        stats["parsed"] += 1
        code = parsed["currency"]
        if local and code != local:
            gate_drops["currency_mismatch"] += 1
            artifacts.append((country, game, arcade_id, "currency_mismatch",
                              code, parsed["amount"], text))
            continue
        if local is None:
            gate_drops["country_currency_unknown"] += 1
            continue
        lo, hi = PLAUSIBLE.get(code, (None, None))
        if lo is not None and not (lo <= parsed["amount"] <= hi):
            gate_drops["implausible"] += 1
            artifacts.append((country, game, arcade_id, "implausible",
                              code, parsed["amount"], text))
            continue
        stats["accepted"] += 1
        entry = {"amount": parsed["amount"], "arcade": arcade_id,
                 "tier": parsed["tier"], "songs": parsed.get("songs")}
        per_cell[(country, game)].append(entry)
        per_arcade[(country, arcade_id)].append(parsed["amount"])

    countries = {}
    for (country, game), entries in sorted(per_cell.items()):
        currency = COUNTRY_CURRENCY[country]
        node = countries.setdefault(country, {"currency": currency,
                                              "games": {}, "overall": None})
        node["games"][game] = _summarise(entries, as_of, currency)

    # Country-level fallback: one vote per arcade (its own modal price across
    # the games it lists) so a single big chain cannot carry a country.
    #
    # It is only emitted as "measured" when it is measured ACROSS GAMES. Per
    # game spread inside one country is large (HK maimai 6 vs taiko 8; TW
    # jubeat 20 vs ddr 40), so a country figure drawn from one game is that
    # game's price wearing a country label. The United Kingdom is the live
    # example: 110 of 111 arcade votes come from DDR-only venues.
    for country, node in countries.items():
        votes = []
        for (c, arcade_id), amounts in per_arcade.items():
            if c != country:
                continue
            votes.append({"amount": _mode(amounts), "arcade": arcade_id,
                          "tier": "arcade_mode", "songs": None})
        overall = _summarise(votes, as_of, node["currency"])
        # Games that carry real evidence of their own, not the raw game count:
        # the UK lists 8 games but 6 of them have a single listing each.
        distinct_games = sum(1 for c in node["games"].values()
                             if c["n"] >= SPARSE_MIN)
        overall["games"] = distinct_games
        if distinct_games < OVERALL_MIN_GAMES and overall["tier"] == "measured":
            overall["tier"] = "sparse"
            overall["demoted_by"] = "too_few_games"
        node["overall"] = overall

    stats["reject_reasons"] = dict(reasons)
    stats["gate_drops"] = dict(gate_drops)
    stats["unmapped_countries"] = {k: v for k, v in unmapped.items() if v >= 1}
    return countries, dict(stats), artifacts


# ------------------------------------------------------------- public build -

def rows_from_enrichment(enrichment_arcades, arcade_countries):
    """(arcade_id, country, game, price_text) for every quoted machine price."""
    out = []
    for arcade_id, record in (enrichment_arcades or {}).items():
        prices = (record or {}).get("machine_prices") or {}
        if not isinstance(prices, dict):
            continue
        country = arcade_countries.get(str(arcade_id))
        for game, text in prices.items():
            if isinstance(text, str) and text.strip():
                out.append((str(arcade_id), country, game, text))
    return out


def build_price_table(enrichment_arcades, arcade_countries, as_of=None,
                      min_measured=MEASURED_MIN):
    """Measured per-country, per-game price table.

    Shape:

      {
        "as_of": "2026-07-29",
        "basis": "quoted",
        "source": "ziv machine_prices",
        "note": "...",
        "countries": {
          "Hong Kong": {
            "currency": "HKD",
            "games": {
              "maimai_dx": {
                "value": 6.0,        <- render this, it is a real quoted figure
                "mode": 6.0, "median": 6.0, "min": 6.0, "max": 6.0,
                "n": 9, "tier": "measured", "currency": "HKD",
                "songs": 3, "as_of": "2026-07-29",
                "arcades": 9, "max_arcade_share": 0.111,
                "mode_share": 1.0, "median_differs": false,
                "row_tiers": ["base", "plain"], "tier_homogeneous": false
              }, ...
            },
            "overall": { ...same shape, one vote per arcade... }
          }, ...
        },
        "coverage": {"measured": .., "sparse": .., "unknown": ..},
        "stats": {...}
      }

    UI contract:
      tier == "measured" -> definite figure, e.g. "HK$6 per credit (9 listings)"
      tier == "sparse"   -> same figure with an explicit "based on N listings"
      tier == "unknown"  -> render NOTHING, or "we do not know". Never fall back
                            to a guessed range.

    Every amount is in `currency`, unconverted. js/format.js converts at render
    time against data/fx_rates.json so displayed USD/JPY/CNY figures track the
    weekly rate refresh without a data rebuild.
    """
    as_of = as_of or date.today().isoformat()
    rows = rows_from_enrichment(enrichment_arcades, arcade_countries)
    countries, stats, artifacts = aggregate(rows, as_of,
                                            min_measured=min_measured)
    coverage = collections.Counter()
    for node in countries.values():
        for cell in node["games"].values():
            coverage[cell["tier"]] += 1
    return {
        "as_of": as_of,
        "basis": "quoted",
        "source": "ziv machine_prices",
        "note": ("Measured from real quoted per-machine prices. Standard/base "
                 "play tier only; premium, galaxy, blaster, VIP, doubles and "
                 "promotional prices are excluded. Local currency only - "
                 "convert at render time against data/fx_rates.json."),
        "min_measured": min_measured,
        "countries": countries,
        "coverage": dict(coverage),
        "stats": stats,
        "artifacts": [
            {"country": c, "game": g, "arcade": a, "gate": k,
             "currency": cur, "amount": amt, "text": t}
            for c, g, a, k, cur, amt, t in artifacts
        ],
    }


# ------------------------------------------------------------ file plumbing -

def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_inputs(root=None):
    """(enrichment_arcades, arcade_countries, as_of) read off disk."""
    root = root or _repo_root()
    with open(os.path.join(root, "data", "enrichment.json"),
              encoding="utf-8") as fh:
        enrichment = json.load(fh)
    with open(os.path.join(root, "data", "arcades.json"),
              encoding="utf-8") as fh:
        arcades = json.load(fh)
    countries = {str(a["id"]): a.get("country")
                 for a in arcades.get("arcades", [])}
    return (enrichment.get("arcades") or {}, countries,
            enrichment.get("updated"))


def build_from_disk(root=None, min_measured=MEASURED_MIN):
    enrichment_arcades, countries, as_of = load_inputs(root)
    return build_price_table(enrichment_arcades, countries, as_of=as_of,
                             min_measured=min_measured)


# --------------------------------------------------------------------- cli --

REPORT_COUNTRIES = ["Hong Kong", "Japan", "Taiwan", "United States",
                    "Philippines", "Singapore", "China", "United Kingdom",
                    "Malaysia", "Australia"]


def _fmt(v):
    if v is None:
        return "-"
    return ("%.2f" % v).rstrip("0").rstrip(".") if v < 1000 else "%d" % v


def main(argv=None):
    argv = argv or sys.argv[1:]
    table = build_from_disk()
    only = argv or REPORT_COUNTRIES
    if only == ["--all"]:
        only = sorted(table["countries"])
    print("as_of=%s  min_measured=%d" % (table["as_of"], table["min_measured"]))
    print()
    header = "%-14s %-14s %-4s %8s %8s %8s %8s %5s  %-8s" % (
        "country", "game", "cur", "value", "median", "min", "max", "n", "tier")
    for country in only:
        node = table["countries"].get(country)
        if not node:
            print("%-14s (no data)" % country)
            continue
        print(header)
        for game, cell in sorted(node["games"].items()):
            print("%-14s %-14s %-4s %8s %8s %8s %8s %5d  %-8s" % (
                country, game, cell["currency"], _fmt(cell.get("value")),
                _fmt(cell.get("median")), _fmt(cell.get("min")),
                _fmt(cell.get("max")), cell["n"], cell["tier"]))
        ov = node["overall"]
        print("%-14s %-14s %-4s %8s %8s %8s %8s %5d  %-8s" % (
            country, "* OVERALL *", ov["currency"], _fmt(ov.get("value")),
            _fmt(ov.get("median")), _fmt(ov.get("min")), _fmt(ov.get("max")),
            ov["n"], ov["tier"]))
        print()
    print("coverage:", table["coverage"])
    print("stats:", json.dumps(table["stats"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
