"""Romanization-aware venue-name comparison for the merge proximity tier.

Why this exists
---------------
ZIv (community) and ALL.Net / e-amusement (official) list the same
physical Japanese arcade under names with ZERO textual overlap:

    ziv       "AmiPara Kokoja (アミパラ ここじゃ店)"
    official  "アミパラここじゃ店"                     <- 0.9 m away

merge.name_similarity() scores that pair 0.571, just under the 0.6
cross-source gate, so it survives as two stacked pins on one rooftop.
The fix is not to loosen the textual threshold globally (0.6 is doing
real work at 120 m) but to add a SEPARATE, distance-gated tier that
knows katakana and romaji are the same alphabet.

What it does
------------
1. norm_text / norm_name       - NFKC + casefold + punctuation strip,
                                 mirroring merge._norm_text (see
                                 test_name_match.py's drift guard).
2. romanize()                  - kana -> Hepburn romaji, in-place, with
                                 kanji / latin / digits passed through
                                 untouched, so mixed names romanize to
                                 mixed strings that still compare well.
3. fold_long()                 - collapses long-vowel spellings so that
                                 "Tokyo" / "Toukyou" / "Tookyoo" and
                                 "ゲーセン" -> "geesen" all meet at one
                                 form. ADDITIVE ONLY: it is offered as
                                 an extra reading inside the max, never
                                 as a replacement, because ou -> o also
                                 mangles English ("round" -> "rond").
4. similarity()                - max over the cross product of both
                                 names' readings of {dice on compact
                                 forms, token-set overlap}.
5. proximity_decision()        - THE shared decision function. merge.py
                                 and any audit script both call this;
                                 neither reimplements the rules.

No external dependencies (the scrapers are stdlib-only by design).
"""

from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------- normalize --

# Mirrors merge._PAREN_RE / merge._KEEP_RE / merge._norm_text. Kept as a
# local copy rather than an import because merge.py imports THIS module;
# test_name_match.py asserts the two implementations agree so they cannot
# silently drift apart.
_PAREN_RE = re.compile(r"\([^)]*\)|（[^）]*）")
_KEEP_RE = re.compile(r"[^0-9a-z&぀-ヿ㐀-鿿가-힯ｦ-ﾟ]+")


def norm_text(s):
    """NFKC + casefold + punctuation/space normalization (paren KEPT)."""
    s = unicodedata.normalize("NFKC", s or "").casefold()
    s = re.sub(r"^[0-9]{2,}", "", s)        # wahlap numeric venue prefixes
    return _KEEP_RE.sub(" ", s).strip()


def norm_name(s):
    """norm_text with parenthetical content stripped.

    ZIv's house style is "<romaji> (<japanese>)", so the paren-stripped
    form is the clean latin reading and the paren-kept form is the full
    bilingual string. Both are needed: matching official kana against the
    ziv PARENTHETICAL is what makes the Kokoja pair score 1.0.
    """
    out = norm_text(_PAREN_RE.sub(" ", s or ""))
    if not out:            # name was entirely parenthetical
        out = norm_text(s or "")
    return out


def paren_inner(s):
    """Just the parenthetical content, normalized ("" when there is none).

    ZIv puts the native-script name in the parens; comparing it directly
    against an official kana name is the cleanest signal available.
    """
    parts = _PAREN_RE.findall(s or "")
    return norm_text(" ".join(p[1:-1] for p in parts)) if parts else ""


def compact(s):
    """Space-free comparison form with a trailing 店 (branch) dropped."""
    c = (s or "").replace(" ", "")
    if len(c) > 2 and c.endswith("店"):
        c = c[:-1]
    return c


# ---------------------------------------------------------------- romanize --

# Hepburn. Digraphs are matched before single kana, so キャ never falls
# through to キ + ャ. Foreign-sound combos (ファ, ヴィ, ティ, シェ ...) are
# included because arcade names are full of them.
_DIGRAPH = {
    "キャ": "kya", "キュ": "kyu", "キョ": "kyo", "キェ": "kye",
    "シャ": "sha", "シュ": "shu", "ショ": "sho", "シェ": "she",
    "チャ": "cha", "チュ": "chu", "チョ": "cho", "チェ": "che",
    "ニャ": "nya", "ニュ": "nyu", "ニョ": "nyo",
    "ヒャ": "hya", "ヒュ": "hyu", "ヒョ": "hyo",
    "ミャ": "mya", "ミュ": "myu", "ミョ": "myo",
    "リャ": "rya", "リュ": "ryu", "リョ": "ryo",
    "ギャ": "gya", "ギュ": "gyu", "ギョ": "gyo",
    "ジャ": "ja", "ジュ": "ju", "ジョ": "jo", "ジェ": "je",
    "ヂャ": "ja", "ヂュ": "ju", "ヂョ": "jo",
    "ビャ": "bya", "ビュ": "byu", "ビョ": "byo",
    "ピャ": "pya", "ピュ": "pyu", "ピョ": "pyo",
    "ファ": "fa", "フィ": "fi", "フェ": "fe", "フォ": "fo", "フュ": "fyu",
    "ヴァ": "va", "ヴィ": "vi", "ヴェ": "ve", "ヴォ": "vo", "ヴュ": "vyu",
    "ウィ": "wi", "ウェ": "we", "ウォ": "wo",
    "ティ": "ti", "テュ": "tyu", "トゥ": "tu",
    "ディ": "di", "デュ": "dyu", "ドゥ": "du",
    "ツァ": "tsa", "ツィ": "tsi", "ツェ": "tse", "ツォ": "tso",
    "クァ": "kwa", "クィ": "kwi", "クェ": "kwe", "クォ": "kwo",
    "グァ": "gwa", "スィ": "si", "ズィ": "zi", "イェ": "ye",
}

_MONO = {
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヲ": "o", "ン": "n", "ヰ": "i", "ヱ": "e",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "ヴ": "vu",
    # small kana standing alone (a digraph would have consumed them)
    "ァ": "a", "ィ": "i", "ゥ": "u", "ェ": "e", "ォ": "o",
    "ャ": "ya", "ュ": "yu", "ョ": "yo", "ヮ": "wa", "ヵ": "ka",
    "ヶ": "ke",
}

_VOWELS = "aiueo"
_KANA_RE = re.compile(r"[぀-ヿｦ-ﾟ]")


def has_kana(s):
    return bool(_KANA_RE.search(s or ""))


def _to_katakana(s):
    """Hiragana -> katakana so one table covers both syllabaries."""
    return "".join(chr(ord(c) + 0x60) if 0x3041 <= ord(c) <= 0x3096 else c
                   for c in s)


def _last_vowel(chunks):
    for chunk in reversed(chunks):
        for ch in reversed(chunk):
            if ch in _VOWELS:
                return ch
        if chunk.strip():          # a non-kana chunk breaks the vowel run
            return ""
    return ""


def romanize(s):
    """Kana -> Hepburn romaji; kanji / latin / digits pass through.

    Handles the three things that actually break naive tables:
      ッ (sokuon)  doubles the next consonant (っち -> tchi, Hepburn)
      ー (chouon)  repeats the previous vowel  (ゲーセン -> geesen)
      ン (moraic)  emits a bare "n"
    A trailing ッ or a leading ー must not raise - both are real in
    scraped data (truncated names, decorative dashes).
    """
    if not s:
        return s or ""
    t = _to_katakana(s)
    out = []
    i = 0
    n = len(t)
    sokuon = False
    while i < n:
        two = t[i:i + 2]
        if len(two) == 2 and two in _DIGRAPH:
            r, adv = _DIGRAPH[two], 2
        elif t[i] in _MONO:
            r, adv = _MONO[t[i]], 1
        elif t[i] in ("ッ", "っ"):
            sokuon = True
            i += 1
            continue
        elif t[i] in ("ー", "〜", "～"):
            v = _last_vowel(out)
            if v:
                out.append(v)
            i += 1
            continue
        else:                        # kanji, latin, digit, space: verbatim
            if sokuon:
                out.append("tsu")    # stray sokuon before a non-kana
                sokuon = False
            out.append(t[i])
            i += 1
            continue
        if sokuon:
            # gemination: っ + chi -> "tchi", otherwise double the consonant
            if r.startswith("ch"):
                out.append("t")
            elif r[0] not in _VOWELS:
                out.append(r[0])
            sokuon = False
        out.append(r)
        i += adv
    if sokuon:                       # trailing っ / ッ
        out.append("tsu")
    return "".join(out)


_REPEAT_VOWEL_RE = re.compile(r"([aiueo])\1+")


def fold_long(s):
    """Collapse long-vowel spellings to one canonical short form.

    oo / ou / oh -> o, aa -> a, uu -> u, ee -> e, ii -> i. This is what
    makes Tokyo == Toukyou == Tookyoo and geesen == gesen. Applied to
    BOTH sides of every comparison or not at all - it is lossy for
    English ("round" -> "rond", "book" -> "bok"), which is harmless when
    symmetric and only ever offered as an EXTRA reading.
    """
    if not s:
        return s or ""
    s = _REPEAT_VOWEL_RE.sub(r"\1", s)
    s = s.replace("ou", "o")
    return _REPEAT_VOWEL_RE.sub(r"\1", s)


# ---------------------------------------------------------------- readings --

def readings(name):
    """Every comparable spelling of `name`, as space-separated strings.

    Cross product of {paren-stripped, paren-kept, paren-inner} x
    {as-written, romanized} x {as-is, long-vowel-folded}. Small (<= 12
    forms) and computed only for sub-30 m candidate pairs, so the O(n^2)
    similarity below is cheap in practice.
    """
    forms = set()
    for base in (norm_name(name), norm_text(name), paren_inner(name)):
        if not base:
            continue
        variants = [base]
        if has_kana(base):
            variants.append(romanize(base))
        for v in variants:
            if not v:
                continue
            forms.add(v)
            folded = fold_long(v)
            if folded:
                forms.add(folded)
    return forms


def _bigrams(s):
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _dice(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ba, bb = _bigrams(a), _bigrams(b)
    return 2.0 * len(ba & bb) / (len(ba) + len(bb)) if (ba or bb) else 0.0


def _tokens(s):
    # 1-char tokens ("1", "b", stray kanji) carry no evidence and inflate
    # the overlap ratio, so they are dropped.
    return {t for t in s.split() if len(t) >= 2}


def _pair_score(ra, rb):
    ca, cb = compact(ra), compact(rb)
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    ta, tb = _tokens(ra), _tokens(rb)
    # Token overlap needs >= 2 tokens on BOTH sides. With a min()
    # denominator a single-token reading scores 1.0 off one shared word,
    # and in a mall the shared word is the MALL: "PACO FUNWORLD(BUGIS
    # PLUS)" vs "TOG - Toy Or Game (Bugis+)" both yield the reading
    # "bugis", scoring a perfect 1.0 for two unrelated arcades. Requiring
    # two tokens each means the venue name has to participate, not just
    # the address-like part. Dice on the compact form still runs for
    # short names, which is what carries the genuine one-token matches.
    tok = (len(ta & tb) / min(len(ta), len(tb))
           if len(ta) >= 2 and len(tb) >= 2 else 0.0)
    return max(tok, _dice(ca, cb))


def similarity(a, b):
    """Romanization-aware similarity in [0, 1].

    max over readings(a) x readings(b) of {compact dice, token overlap}.
    Always >= merge.name_similarity(a, b) for the same input, because the
    as-written paren-stripped and paren-kept forms are among the
    readings - the romanized forms can only add.
    """
    ra, rb = readings(a), readings(b)
    best = 0.0
    for x in ra:
        for y in rb:
            s = _pair_score(x, y)
            if s > best:
                best = s
                if best >= 1.0:
                    return 1.0
    return best


SUBSTRING_MIN_LEN = 5


def substring_match(a, b, min_len=SUBSTRING_MIN_LEN):
    """True when one name's romanized compact form contains the other's.

    Catches truncation ("アミパラ" listed against "アミパラここじゃ店").
    The length floor matters: without it a 2-3 char fragment ("gigo",
    "am") matches half the country.
    """
    ca = {compact(r) for r in readings(a)}
    cb = {compact(r) for r in readings(b)}
    for x in ca:
        if len(x) < min_len:
            continue
        for y in cb:
            if len(y) < min_len:
                continue
            if x != y and (x in y or y in x):
                return True
    return False


# --------------------------------------------------------------- decision ---

PROXIMITY_MAX_M = 30.0      # hard gate; nothing below is applied beyond it
ISOLATION_RADIUS_M = 60.0   # radius for the "only two on this rooftop" test
SIM_THRESHOLD = 0.5         # romanization-aware, NOT the global 0.6

# The isolated-coincident rule merges names with NO textual evidence
# whatsoever, so it gets a much tighter distance gate than the two
# evidence-bearing rules. Measured on all 37 decisions the 30 m version
# produced (each judged by hand against both addresses):
#     0-10 m   15 decisions, 14 right, 1 wrong   93% precision
#    10-30 m   22 decisions, 10 right, 12 wrong  45% precision
# Every 10-30 m error is the same failure: a shopping mall geocodes all
# its tenants to one rooftop point, so "the only two listings within
# 60 m" are genuinely two DIFFERENT operators - Taito F Station vs Kids
# Park in one AEON, 楽市楽座 vs Molly Fantasy, namco vs シルクハット.
# Under ~10 m the pair is a single storefront and the heuristic holds.
# The spec's own wording for this rule is "two listings alone on the
# same rooftop"; 10 m is that, 30 m is a whole mall floor plate. The
# 30 m gate still governs proximity_romaji_sim / proximity_substring,
# which carry name evidence and measured ~98% precision.
ISOLATION_MAX_M = 10.0

# rule id -> confidence label. Documented meaning:
#   high   - the two names demonstrably say the same thing once kana and
#            romaji are put in one alphabet; would have merged already if
#            the matcher had understood the script.
#   medium - one name contains the other; consistent with the same venue
#            under a longer/shorter official title, but the extra text is
#            unexplained.
#   low    - NO textual evidence at all. Merged purely on the geometric
#            argument that two isolated listings under 30 m apart, with
#            nothing else within 60 m, are one business. Review these
#            first if a false merge is ever reported.
RULE_CONFIDENCE = {
    "proximity_romaji_sim": "high",
    "proximity_substring": "medium",
    "coincident_isolated": "low",
}


def proximity_decision(name_a, name_b, dist_m, clusters_within_60):
    """Shared accept/reject for the merge proximity tier.

    Callers supply their own geometry; the RULES live here exactly once
    so merge.py and any audit script cannot disagree.

    name_a, name_b        venue names (any script, as scraped)
    dist_m                great-circle metres between the two
    clusters_within_60    number of DISTINCT already-merged clusters with
                          coordinates within ISOLATION_RADIUS_M of either
                          endpoint, counting the two candidates. Must be
                          clusters, not raw rows: an official venue that
                          is one allnet row plus one eagate row is two
                          rows but one cluster, and counting rows would
                          make the isolation test never fire.

    Returns (accept, rule_id, similarity, confidence). rule_id and
    confidence are None when rejected.

    The caller is still responsible for the two preconditions this tier
    assumes and cannot verify: the pair must cross the official/community
    source-family boundary, and the existing name rule must already have
    failed on it.
    """
    sim = similarity(name_a, name_b)
    if dist_m is None or dist_m >= PROXIMITY_MAX_M:
        return False, None, sim, None
    if sim >= SIM_THRESHOLD:
        rule = "proximity_romaji_sim"
    elif substring_match(name_a, name_b):
        rule = "proximity_substring"
    elif clusters_within_60 == 2 and dist_m < ISOLATION_MAX_M:
        # no name evidence at all -> the tighter geometric gate
        rule = "coincident_isolated"
    else:
        return False, None, sim, None
    return True, rule, sim, RULE_CONFIDENCE[rule]
