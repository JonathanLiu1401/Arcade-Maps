"""Cross-script matching for Hong Kong and Macau venues.

Hong Kong is the only place in the dataset where one arcade is routinely
published under two names that share not a single character. The official
sources are English, BemaniCN is Chinese, and neither carries the other's
script:

    PIK FU GAME CENTRE, 26-30 WO YI HOP ROAD, KWAI CHUNG
    碧富遊戲機, 和宜合道

    TIN TIN GAME CENTRE, 5 TSING PAK PATH, TUEN MUN
    屯門天天遊戲機中心, 屯門新墟青柏徑5號 四寶大廈

Nothing in the general merge pipeline can pair those. Name similarity is zero
by construction, and the BemaniCN side has no coordinate to measure a distance
from. What DOES survive is that the English is the Cantonese READING of the
Chinese: 碧富 is Pik Fu, 天天 is Tin Tin, 和宜合 is Wo Yi Hop.

So this module reconstructs the reading from ``data/hk_romanize.json`` and
compares it to the Latin text. It cannot compare them literally. Hong Kong's
street and place names use the old Hong Kong Government romanisation, which
predates Jyutping and disagrees with it constantly - Jyutping writes 觀塘 as
`gun tong` where the road signs read `Kwun Tong`, and 沙田 as `saa tin` where
they read `Sha Tin`. Both are folded onto a coarse phonetic SKELETON that
throws away exactly the distinctions the two systems disagree about (voicing,
sibilant spelling, vowel doubling), and what survives is compared with a
one-edit tolerance for the rest.

The skeleton is deliberately lossy, so a single match means little: `sa tin`
would also skeletonize close to a dozen other syllable pairs. Callers are
expected to require SEVERAL independent anchors before merging anything, which
is what ``anchors()`` counts.
"""

from __future__ import annotations

import json
import os
import re

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "hk_romanize.json")

_READINGS = None

#: Words that appear in half the venue names in the territory and therefore
#: prove nothing. Kept in skeleton form so both scripts are covered by one
#: list: 中心 reads `zung sam` and never collides with "centre", but 香港 does
#: read like "Hong Kong" and would otherwise anchor every pair in the dataset.
_STOP_SKELETONS = frozenset({
    "hongkong", "hongkong", "honkong", "kaulung", "kowloon", "santkai",
    "sunkai", "macau", "mokou", "oumun", "cunkwok", "cungkwok",
    "kam", "game", "gamecentre", "gamecenter", "centre", "center", "plaza",
    "shop", "road", "street", "floor", "basement", "building", "hong", "kong",
})

#: Generic Chinese words in venue names. A shared 遊戲機 or 娛樂城 says only
#: that both rows describe an arcade.
_STOP_CJK = ("遊戲機中心", "游戏机中心", "遊戲機", "游戏机", "遊戲", "游戏",
             "電子遊戲", "电子游戏", "娛樂城", "娱乐城", "遊戲城", "游戏城",
             "遊戲廣場", "游戏广场", "電玩", "电玩", "機中心", "机中心",
             "中心", "廣場", "广场", "大廈", "大厦", "商場", "商场",
             "遊樂", "游乐", "娛樂", "娱乐", "樂園", "乐园", "天地", "世界",
             "電子", "电子", "機城", "机城", "廣場", "俱樂部", "俱乐部",
             "香港", "九龍", "九龙", "新界", "澳門", "澳门", "特别行政区",
             "特別行政區", "地下", "地庫", "地库", "地舖", "地铺")


def load_readings(path=None, force=False):
    """char -> [jyutping syllable, ...]. Memoized."""
    global _READINGS
    if _READINGS is not None and not force and path is None:
        return _READINGS
    with open(path or _DATA_PATH, encoding="utf-8") as fh:
        table = json.load(fh)["readings"]
    if path is None:
        _READINGS = table
    return table


# ------------------------------------------------------------- skeletons ---
# Both normalizers target one alphabet: initials p t k c f s h m n l w y kw,
# vowels a e i o u, codas p t k m n ng. Everything the two romanization
# systems spell differently is folded away before the comparison.

def _fold_common(s):
    s = re.sub(r"ng", "N", s)          # protect the velar nasal from n-folds
    s = s.replace("aa", "a").replace("oo", "u").replace("ee", "i")
    s = s.replace("N", "ng")
    return s


def skel_jyutping(syllable):
    """Jyutping syllable -> skeleton. `bik` -> `pik`, `gun` -> `kun`."""
    s = syllable.lower()
    # Initials. Jyutping voices what Hong Kong romanisation does not, and its
    # `j` is a glide (jyun = "yuen"), not the affricate the Latin side spells
    # with `j`.
    for a, b in (("gw", "kw"), ("kw", "kw"), ("ng", "\x01"), ("b", "p"),
                 ("d", "t"), ("g", "k"), ("z", "c"), ("j", "y")):
        if s.startswith(a):
            s = b + s[len(a):]
            break
    s = s.replace("\x01", "ng")
    s = s.replace("yu", "u").replace("oe", "o").replace("eo", "o")
    return _fold_common(s)


def skel_latin(word):
    """Latin word -> skeleton. `Pik` -> `pik`, `Tsuen` -> `cun`."""
    s = re.sub(r"[^a-z]", "", word.lower())
    if not s:
        return ""
    for a, b in (("ts", "c"), ("ch", "c"), ("tz", "c"), ("sh", "s"),
                 ("kw", "kw"), ("qu", "kw"), ("j", "c"), ("b", "p"),
                 ("d", "t"), ("g", "k")):
        if s.startswith(a):
            s = b + s[len(a):]
            break
    s = s.replace("sh", "s").replace("ue", "u").replace("eu", "o")
    return _fold_common(s)


def _readings_for(char, table):
    return table.get(char) or []


def cjk_skeletons(token, table=None, cap=12):
    """Every skeleton a CJK token could read as. Empty when unreadable.

    A character with several readings multiplies the candidates, so the
    product is capped: a five-character token with three readings each would
    otherwise be 243 strings compared against every Latin group on the other
    side, for no gain - the long tokens are building names that match on their
    first two characters anyway.
    """
    table = table if table is not None else load_readings()
    combos = [""]
    for ch in token:
        rs = _readings_for(ch, table)
        if not rs:
            return set()
        nxt = []
        for prefix in combos:
            for r in rs:
                nxt.append(prefix + skel_jyutping(r))
                if len(nxt) >= cap:
                    break
            if len(nxt) >= cap:
                break
        combos = nxt
    return {c for c in combos if c}


def latin_skeleton(words):
    return "".join(skel_latin(w) for w in words)


def _edit_ok(a, b):
    """Equal, or within one edit. Two skeletons that differ by more than one
    character are different words: `kun`/`kwun` (觀 Kwun) and `wongkok`/
    `mongkok` (旺角 Mong Kok) are the real drift this has to absorb, and both
    are a single edit."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1 or not a or not b:
        return False
    if len(a) > len(b):
        a, b = b, a
    # a is the shorter; allow one insertion or one substitution
    for i in range(len(b)):
        if len(a) == len(b):
            if a[:i] + b[i] + a[i + 1:] == b:
                return True
        elif a[:i] + b[i] + a[i:] == b:
            return True
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1


def cjk_tokens(text, lo=2, hi=4):
    """CJK substrings worth testing, generic words removed."""
    out = set()
    for run in re.findall(r"[一-鿿]{2,}", text or ""):
        for n in range(lo, hi + 1):
            for i in range(len(run) - n + 1):
                tok = run[i:i + n]
                if tok in _STOP_CJK:
                    continue
                out.add(tok)
    return out


def latin_groups(text, lo=1, hi=3):
    """Consecutive Latin word groups, as (words, skeleton) pairs."""
    out = {}
    for run in re.findall(r"[A-Za-z][A-Za-z' ]*[A-Za-z]|[A-Za-z]+", text or ""):
        words = [w for w in run.split() if w]
        for n in range(lo, hi + 1):
            for i in range(len(words) - n + 1):
                grp = tuple(words[i:i + n])
                sk = latin_skeleton(grp)
                if len(sk) >= 4 and sk not in _STOP_SKELETONS:
                    out[grp] = sk
    return out


def romanization_matches(cjk_text, latin_text, table=None):
    """Distinct (cjk token, latin words) pairs that read alike.

    Overlapping tokens are collapsed to one hit per CJK token, so a four
    character building name cannot count as three separate anchors.
    """
    table = table if table is not None else load_readings()
    groups = latin_groups(latin_text)
    hits = {}
    for tok in sorted(cjk_tokens(cjk_text), key=lambda t: (-len(t), t)):
        skels = cjk_skeletons(tok, table)
        if not skels or all(s in _STOP_SKELETONS for s in skels):
            continue
        for grp, gsk in groups.items():
            if any(_edit_ok(s, gsk) for s in skels):
                if not any(tok in seen or seen in tok for seen in hits):
                    hits[tok] = grp
                break
    return hits


# ---------------------------------------------------------- place names ----
#: Hong Kong and Macau toponyms whose English form is a TRANSLATION or an
#: exonym rather than a romanization, so no amount of phonetic folding will
#: connect the two halves. Every entry below is a name that actually occurs in
#: this dataset's addresses; the list is not meant to be a gazetteer.
#:
#:   香港仔 is Aberdeen, not "Heung Kong Tsai".
#:   青山公路 is Castle Peak Road - 青山 means "green hill".
#:   廣東道 is Canton Road, from the old exonym for the province.
#:   旺角's official English is Mong Kok, which the romanizer does reach, but
#:   its neighbours 太子 (Prince Edward) and 中環 (Central) are translations.
EXONYMS = {
    "香港仔": "aberdeen", "鴨脷洲": "apleichau", "中環": "central",
    "金鐘": "admiralty", "銅鑼灣": "causewaybay", "跑馬地": "happyvalley",
    "淺水灣": "repulsebay", "赤柱": "stanley", "太古": "taikoo",
    "青山": "castlepeak", "廣東道": "cantonroad", "太子": "princeedward",
    "北角": "northpoint", "上環": "sheungwan", "西環": "saiwan",
    "堅尼地城": "kennedytown", "深水埗": "shamshuipo", "尖沙咀": "tsimshatsui",
    "尖東": "tsimshatsuieast", "九龍城": "kowlooncity", "黃大仙": "wongtaisin",
    "鑽石山": "diamondhill", "新蒲崗": "sanpokong", "牛頭角": "ngautaukok",
    "西灣河": "saiwanho", "西湾河": "saiwanho", "筲箕灣": "shaukeiwan",
    "筲箕湾": "shaukeiwan", "柴灣": "chaiwan", "柴湾": "chaiwan",
    "路氹": "cotai", "路凼": "cotai", "氹仔": "taipa", "路環": "coloane",
    "澳門": "macau", "澳门": "macau",
    # Roads whose English name is a surname or a translation. They belong here
    # rather than among the localities because a road carries a house number,
    # and a shared road at conflicting numbers is what vetoes a pair.
    "彌敦道": "nathanroad", "弥敦道": "nathanroad", "青山公路": "castlepeakroad",
    "太子道": "princeedwardroad", "英皇道": "kingsroad",
}
_EXONYM_LATIN = {v: k for k, v in EXONYMS.items()}
#: Road exonyms keyed on the name WITHOUT its road word, because the sources
#: abbreviate it differently: "557-559NATHAN RD." and "30 Canton Road" have to
#: reach the same key as 彌敦道 and 廣東道.
_EXONYM_ROAD_BASE = {}
for _k in list(_EXONYM_LATIN):
    for _suf in ("road", "street"):
        if _k.endswith(_suf) and len(_k) > len(_suf):
            _EXONYM_ROAD_BASE[_k[:-len(_suf)]] = _k

#: Street-type words. Stripped from both scripts before a street name is
#: compared: 洗衣街 has to line up with "Sai Yee Street", and 街 reads `kai`
#: while "street" skeletonizes to `strit`.
_CJK_STREET_SUFFIX = ("大馬路", "公路", "馬路", "花園", "廣場", "大廈", "中心",
                      "街", "道", "路", "徑", "里", "巷", "圍", "坊", "臺", "台")
_LATIN_STREET_SUFFIX = ("STREET", "ROAD", "PATH", "AVENUE", "LANE", "TERRACE",
                        "CIRCUIT", "PRAYA", "CRESCENT", "SQUARE", "PLAZA",
                        "CENTRE", "CENTER", "BUILDING", "COURT", "GARDEN",
                        "ST", "RD", "AVE", "LN")

_CJK_SUFFIX_RE = re.compile("(%s)" % "|".join(_CJK_STREET_SUFFIX))
_LATIN_SUFFIX_RE = re.compile(r"\b(%s)\b" % "|".join(_LATIN_STREET_SUFFIX),
                              re.I)
_NUM_RE = re.compile(r"[0-9]{1,4}(?:\s*-\s*[0-9]{1,4})?")


def _interval(tok):
    if not tok:
        return None
    parts = [int(x) for x in tok.replace(" ", "").split("-")]
    return (min(parts), max(parts))


def _cjk_street_refs(text):
    """Scan for <name><street word><number>號.

    Written as a scan rather than one regex because the name has no left
    boundary: 旺角洗衣街 is the locality 旺角 followed by the street 洗衣街, and
    a regex that grabs everything before 街 produces `旺角洗衣`, which reads
    nothing like "Sai Yee". The two, three and four characters before the
    street word are all emitted and the caller keeps whichever one matches.
    """
    out = set()
    for m in _CJK_SUFFIX_RE.finditer(text):
        tail = text[m.end():]
        num = None
        nm = _NUM_RE.match(tail.lstrip())
        if nm and tail.lstrip()[nm.end():nm.end() + 1] in ("號", "号", ""):
            num = nm.group(0)
        elif nm and tail.lstrip().startswith(nm.group(0)):
            num = nm.group(0)
        head = text[:m.start()]
        full = head[-6:] + m.group(0)
        for cjk, key in EXONYMS.items():
            # Either spelling reaches the key: 彌敦道 carries the road word,
            # 筲箕湾 does not. The simplified forms matter here too, because
            # the Cantonese readings table is traditional and cannot read 湾.
            if full.endswith(cjk) or head.endswith(cjk):
                out.add((key, _interval(num)))
        for n in (2, 3, 4):
            if len(head) < n:
                break
            tok = head[-n:]
            if not all("一" <= c <= "鿿" for c in tok):
                continue
            for sk in cjk_skeletons(tok):
                if len(sk) >= 4:
                    out.add((sk, _interval(num)))
    return out


def _latin_street_refs(text):
    """Scan for <number> <name> <street word>, the Hong Kong postal order."""
    out = set()
    for m in _LATIN_SUFFIX_RE.finditer(text):
        head = text[:m.start()]
        words = re.findall(r"[A-Za-z]+", head)
        nums = _NUM_RE.findall(head)
        num = nums[-1] if nums else None
        # Only the words after the last digit belong to this street name:
        # "2/F, GOLDEN ERA PLAZA, 39SAI YEE STREET" must not read as
        # "GOLDEN ERA PLAZA SAI YEE".
        if nums:
            tail_text = head[head.rfind(nums[-1]) + len(nums[-1]):]
            words = re.findall(r"[A-Za-z]+", tail_text)
        for n in (1, 2, 3):
            if len(words) < n:
                break
            grp = words[-n:]
            base = re.sub(r"[^a-z]", "", "".join(grp).lower())
            named = base + re.sub(r"[^a-z]", "", m.group(1).lower())
            if named in _EXONYM_LATIN:
                out.add((named, _interval(num)))
            elif base in _EXONYM_ROAD_BASE:
                out.add((_EXONYM_ROAD_BASE[base], _interval(num)))
            elif base in _EXONYM_LATIN:
                out.add((base, _interval(num)))
            sk = latin_skeleton(grp)
            if len(sk) >= 4 and sk not in _STOP_SKELETONS:
                out.add((sk, _interval(num)))
    return out


_LATIN_NO_RE = re.compile(r"\bNO\.?\s*([0-9]{1,4}(?:\s*-\s*[0-9]{1,4})?)",
                          re.I)


def street_numbers(text):
    """House numbers attached to something that reads as a street.

    Kept separate from street_refs because the NAME can be unreadable while
    the NUMBER is perfectly clear: 旧大街82号 is "82 Old Main Street", a
    translation the romanizer will never reach, and 旧 is not even in the
    Cantonese readings table. The number is still worth having.
    """
    text = text or ""
    out = set()
    for m in _CJK_SUFFIX_RE.finditer(text):
        tail = text[m.end():].lstrip()
        nm = _NUM_RE.match(tail)
        if nm and tail[nm.end():nm.end() + 1] in ("號", "号", ""):
            out.add(_interval(nm.group(0)))
    for m in _LATIN_SUFFIX_RE.finditer(text):
        nums = _NUM_RE.findall(text[:m.start()])
        if nums:
            out.add(_interval(nums[-1]))
    # "NO.63 MODY DOAD" - the source typo'd the road word, and without this the
    # only unambiguous part of the address would be thrown away.
    for m in _LATIN_NO_RE.finditer(text):
        out.add(_interval(m.group(1)))
    return {iv for iv in out if iv}


def street_refs(text):
    """{(street skeleton, interval or None)} named in a piece of address text.

    Both scripts are read, because the evidence often sits on ZIv's bilingual
    row rather than across the two sources: 龍蟠街3號 appears verbatim on the
    BemaniCN row AND inside ZIv's address for Plaza Hollywood.
    """
    text = text or ""
    return _cjk_street_refs(text) | _latin_street_refs(text)


def street_match(a, b):
    """(street skeletons in common, overlapping intervals on those streets)."""
    streets, numbers = set(), set()
    for ska, iva in a:
        for skb, ivb in b:
            if not _edit_ok(ska, skb):
                continue
            streets.add(ska)
            if iva and ivb and iva[0] <= ivb[1] and ivb[0] <= iva[1]:
                numbers.add((max(iva[0], ivb[0]), min(iva[1], ivb[1])))
    return streets, numbers


def places(text):
    """Canonical place keys a text names: exonyms plus romanizable toponyms."""
    out = set()
    txt = text or ""
    for cjk, key in EXONYMS.items():
        if cjk in txt:
            out.add(key)
    letters = re.sub(r"[^a-z]", "", txt.lower())
    for key in EXONYMS.values():
        if key in letters:
            out.add(key)
    return out


def numbers_anywhere(text):
    """Street numbers regardless of which street they belong to. Only ever
    used as corroboration once a place already agrees; on its own a bare 68
    pairs Kwun Tong Plaza with an arcade in Shau Kei Wan."""
    return {iv for _sk, iv in street_refs(text) if iv}


# --------------------------------------------------------------- evidence ---
#: Latin words that name a kind of business rather than a business. A shared
#: GAMECENTRE says both rows are arcades and nothing else.
_GENERIC_LATIN = frozenset({
    "GAME", "GAMES", "GAMECENTRE", "GAMECENTER", "CENTRE", "CENTER",
    "AMUSEMENT", "ARCADE", "PLAZA", "SHOP", "CITY", "CLUB", "LAND",
    "WORLD", "HOUSE", "ARENA", "ENTERTAINMENT",
    # GAMEZONE deliberately absent: six Hong Kong rows carry it, but it is the
    # operator's name and the locality tells the branches apart.
})


def _latin_runs(text):
    return {re.sub(r"[^A-Z]", "", m.group(0).upper())
            for m in re.finditer(r"[A-Za-z][A-Za-z' ]*[A-Za-z]", text or "")}


def _brand_runs(name):
    """Latin runs from a venue NAME that could identify the operator."""
    out = set()
    for run in _latin_runs(name):
        for word in re.findall(r"[A-Z]+", run):
            pass
        if len(run) >= 6 and run not in _GENERIC_LATIN:
            out.add(run)
    return out


def shared_places(text_a, text_b):
    """Place keys both texts name, by exonym or by Cantonese reading.

    Restricted to two and three character toponyms. A longer CJK run is a
    building or a venue, and letting those in here is what turned every pair
    of arcades in Kowloon into a plausible match.
    """
    keys = set()
    for cjk, key in EXONYMS.items():
        in_a = cjk in (text_a or "") or key in re.sub(r"[^a-z]", "", (text_a or "").lower())
        in_b = cjk in (text_b or "") or key in re.sub(r"[^a-z]", "", (text_b or "").lower())
        if in_a and in_b:
            keys.add(key)
    for src, dst in ((text_a, text_b), (text_b, text_a)):
        for tok in romanization_matches(src, dst):
            if 2 <= len(tok) <= 3 and not (set(tok) & set("舖鋪樓層号號室座期庫")):
                keys.add(tok)
    # A raw CJK substring shared by two addresses was tried here and had to go:
    # it produced 號沙, 田娛, 樂城 and a dozen other fragments that straddle word
    # boundaries, so every pair in the territory looked corroborated.
    return keys


def evidence(text_a, name_a, text_b, name_b):
    """Independent evidence that two Hong Kong / Macau rows are one venue.

    Returns ``(types, veto)``. ``types`` maps an evidence KIND to the tokens
    that produced it; the caller counts kinds, not tokens, because five
    overlapping substrings of one building name are one fact. ``veto`` is set
    when the two rows name the same street at different numbers, which is the
    one signal here that positively separates two venues.
    """
    refs_a, refs_b = street_refs(text_a), street_refs(text_b)
    streets, numbers = street_match(refs_a, refs_b)

    # Same street, different numbers, and no number anywhere that does agree:
    # 觀塘道418號 (APM) against 觀塘道410號地庫 is two buildings on one road.
    veto = False
    if streets and not numbers:
        for ska, iva in refs_a:
            for skb, ivb in refs_b:
                if iva and ivb and _edit_ok(ska, skb):
                    veto = True

    # Street numbers that agree even though the street names did not line up.
    # 旧大街82号 and "82 OLD MAIN STREET" are the same address translated, not
    # romanized, so the names never match and only the number survives. On its
    # own a bare number is noise, so this is admitted below only when some
    # other kind of evidence already holds.
    loose_numbers = set()
    for iva in street_numbers(text_a):
        for ivb in street_numbers(text_b):
            if iva[0] <= ivb[1] and ivb[0] <= iva[1]:
                # Only a distinctive number. Hong Kong shop and floor numbers
                # are single digits, so a shared 2 or 5 pairs half the
                # territory; a range or a number of 10 or more does not.
                if iva[0] != iva[1] or ivb[0] != ivb[1] or iva[1] >= 10:
                    loose_numbers.add((max(iva[0], ivb[0]),
                                       min(iva[1], ivb[1])))

    places = shared_places(text_a, text_b)
    # A token that already counted as the street cannot count again as the
    # locality: 彌敦道 is one fact, and letting it be two merged 760 Nathan
    # Road with 688 Nathan Road.
    places = {p for p in places
              if p not in streets
              and not any(_edit_ok(sk, s2) for s2 in streets
                          for sk in (cjk_skeletons(p) if not p.isascii()
                                     else {p}))}
    brands = {r for r in _brand_runs(name_a)
              if any(r in o or o in r for o in _brand_runs(name_b))}
    # A locality is not a brand: TIN TIN GAME CENTRE(TUEN MUN) and
    # 屯門威水 (Smart TV Game Centre) both carry TUENMUN and are two arcades.
    brands = {r for r in brands
              if not any(_edit_ok(skel_latin(r), skel_latin(p)) or p in r.lower()
                         for p in places if p.isascii())
              and not any(_edit_ok(skel_latin(r), s)
                          for p in places if not p.isascii()
                          for s in cjk_skeletons(p))}

    generic = "".join(_STOP_CJK)
    cjk_names = {tok for tok in cjk_tokens(name_a, lo=2, hi=4)
                 if tok in (name_b or "")
                 and tok not in places
                 and tok not in generic}
    rom_names = set(romanization_matches(name_a, name_b))
    rom_names |= set(romanization_matches(name_b, name_a))
    rom_names -= places

    types = {}
    if streets:
        types["street"] = sorted(streets)
    if not numbers and (places or brands or cjk_names or rom_names):
        numbers = loose_numbers
    if numbers:
        types["number"] = sorted("%d-%d" % iv for iv in numbers)
    if places:
        types["place"] = sorted(places)
    if brands:
        types["brand"] = sorted(brands)
    if cjk_names:
        types["cjkname"] = sorted(cjk_names)
    if rom_names:
        types["romname"] = sorted(rom_names)
    return types, veto
