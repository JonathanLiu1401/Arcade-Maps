"""Chinese address parsing: turn one printed address into geocodable queries.

A Chinese arcade address is not one question, it is several stacked on top of
each other. ``广东省深圳市宝安区新湖路99号壹方城3楼B1-023电梯口`` names a
province, a city, a district, a road, a street number, a shopping mall, a
floor, a unit and a landmark inside that unit. A geocoder is excellent at the
middle of that chain and actively harmed by the two ends: the administrative
head is what stops it answering with a 壹方城 in another province, and the
floor/unit tail is what makes it answer with nothing at all, because no POI
database has a row for "3rd floor, unit B1-023, next to the lift".

So this module does two jobs and no others:

  * **strip_noise** removes the tail - floors (``3F``, ``三楼``, ``负一层``),
    unit numbers (``B1-023``, ``f3015号铺``), and relational junk (``电梯口``,
    ``金逸影城旁``, ``详细地址请加群``). It is deliberately conservative: it
    only deletes shapes that are unambiguously interior-of-a-building, because
    deleting one character too many turns ``18号楼`` into ``18号`` and moves
    the answer to a different building.

  * **candidates** builds progressively coarser queries from what is left, so
    the caller can stop at the first one that answers confidently. The order
    matters and is measured, not guessed: the full cleaned address wins most
    of the time on a Chinese geocoder (it has the road number, which is the
    only thing that separates two malls on the same street), and the bare
    landmark is the rescue for the very common bemanicn row that names a mall
    and nothing else.

**Why the landmark is extracted at all.** Half of these venues are inside a
mall, and the mall is the part of the address a POI database definitely knows.
``怀仁市新天地购物广场5楼`` has no road and no number; without pulling
``新天地购物广场`` out of it and asking about that, the row has no answer
better than a district centroid. ``find_landmark`` walks backwards from a mall
suffix (广场, 购物中心, 大悦城, 天街 ...) and stops at the first character that
cannot be part of a name - a road, a number, or punctuation - which is what
keeps ``黄河西路与开元南大道交叉口荣盛国际购物广场`` from becoming the whole
string.

**Administrative characters are NOT walk-back stops**, which is the one
non-obvious decision here. Stopping on 市 looks right and silently breaks every
mall whose own name contains one: ``SM滨海城市广场`` truncates to
``SM滨海城市``, ``北京朝阳大悦城`` to ``京朝阳大悦城``. The walk therefore runs
through them and a separate pass, ``trim_admin``, strips a genuine leading
administrative token afterwards - which it can do safely because it requires
the whole token, ``怀仁市``, not a bare character.

**The venue name is a candidate too.** BemaniCN names its shops after the mall
they are in: ``环游嘉年华（北京朝阳大悦城店）`` names 朝阳大悦城 while its
address says only ``朝阳区朝阳北路101号``. When the address yields no landmark,
the name usually does.

Everything here is pure string work on stdlib ``re``. No data file, no
network, no import of the area table - that lives in geocode_cn, which owns
the administrative side. Keeping this half pure is what makes it testable
without a fixture.
"""

from __future__ import annotations

import re
import unicodedata

_CJK = "一-鿿"

#: Mall / landmark suffixes, LONGEST FIRST so 购物中心 is found before 中心 and
#: 购物广场 before 广场. A short suffix matching first would truncate the name
#: to its last two characters and ask about "中心", which resolves to a
#: different building in every city in China.
MALL_SUFFIXES = (
    "国际购物中心", "购物中心", "购物公园", "购物广场", "商业广场", "生活广场",
    "时代广场", "国际广场", "文化广场", "商业中心", "奥特莱斯", "万象天地",
    "万象城", "万象汇", "大悦城", "印象城", "新天地", "步行街", "商业街",
    "不夜城", "银泰城", "吾悦广场", "天虹商场", "宝龙广场", "苏宁广场",
    "世贸广场", "世界城", "国际城", "时代城", "购物广", "广场", "百货",
    "商厦", "商城", "商场", "大厦", "天街", "奥莱", "银泰", "吾悦", "天虹",
    "万达", "中心", "城市", "MALL", "Mall", "mall",
    # Bare 城 last, and only useful because the walk-back stops on digits and
    # road characters: it is what finds 壹方城 / 海岸城 / 大融城, a whole family
    # of mall brands that end in nothing more distinctive than "city". The
    # administrative false friends it could produce (县城, 城区) are killed by
    # _CITY_FALSE_FRIENDS below rather than by leaving the suffix out, which
    # would cost every one of those malls.
    "城",
)

#: Names ``find_landmark`` must never return even though they end in a listed
#: suffix: administrative words, generic nouns, and the venue-type words
#: Chinese arcades put in their own trading names. Each of these resolves
#: somewhere - just not anywhere related to the address.
_LANDMARK_REJECT = frozenset({
    "县城", "城区", "老城", "新城", "旧城", "城市", "全城", "本城",
    "电玩城", "游戏城", "动漫城", "游艺城", "娱乐城", "不夜城",
    "购物中心", "购物广场", "商业广场", "时代广场", "国际广场", "商业中心",
    "步行街", "商业街", "百货", "商厦", "商城", "商场", "大厦", "广场",
    "中心", "天街", "奥莱", "购物", "城市广场", "购物公园",
})

#: Characters the backwards walk refuses to cross. Punctuation, whitespace and
#: the road/positional vocabulary - the things that mark where a building name
#: cannot have started. Administrative characters are deliberately absent; see
#: the module docstring and ``trim_admin``.
_LANDMARK_STOP = set("路道街巷号口层楼室栋座与和及在近旁内侧对"
                     "，,、；;。.！!？?（）()【】[]{}<>《》|/\\ \t")

#: Road suffixes, longest first: 大道 before 道, 大街 before 街.
ROAD_SUFFIXES = ("大道", "大街", "小街", "环路", "公路", "马路", "路", "街",
                 "道", "巷", "弄", "胡同")

#: A leading administrative token, stripped off an extracted name. Whole
#: tokens only (``怀仁市``), never a bare character, so a mall called
#: ``城市广场`` survives while ``怀仁市新天地购物广场`` loses its city.
_ADMIN_HEAD_RE = re.compile(
    "^(?:中国|[" + _CJK + "]{2,4}(?:省|市|区|县|镇|乡|旗|盟|街道|办事处|新区))")

#: The noise tail. Order matters - the longer/more specific shapes go first so
#: a general rule cannot eat half of one and leave the rest behind.
#:
#: Each entry is (regex, why). The "why" is not decoration: every one of these
#: is a shape observed in data_raw that a geocoder answers badly.
_NOISE = [
    # "详细地址请加群xxxxx" - bemanicn rows where the operator refused to
    # publish an address at all. Nothing after this is an address.
    (r"详细地址.*$", "placeholder for a withheld address"),
    (r"请加群.*$", "placeholder for a withheld address"),
    # "&爱巴爱麻电玩城" - wahlap appends the shop's own trading name after an
    # ampersand. The shop is not in any POI database; the mall is.
    (r"&.*$", "trailing shop name after an ampersand"),
    # "(近华茂中心)" / "（近地铁口）" - a relational hint, never an address.
    (r"[（(]\s*近[^）)]*[)）]?", "relational hint in parentheses"),
    # Hyphenated in-mall unit codes: B1-023, H1-01, F3-15. This runs FIRST, and
    # before the basement-floor rule, or "B1" is chopped off B1-023 and the
    # orphan "-023" survives into the query. It requires a LETTER in front
    # because a bare 12-3 also spells a road-number range. The lookbehind
    # rejects only another letter or digit: these codes sit directly after a
    # Chinese floor word (``3楼B1-023``), so excluding CJK would never fire.
    (r"(?<![A-Za-z0-9])[A-Za-z]\d{1,4}-\d{1,4}(?![A-Za-z0-9])",
     "hyphenated unit"),
    # Floors, in every spelling seen: 3F, B1F, B1层, 三楼, 负一层, 3层.
    (r"(?<![A-Za-z0-9])[Bb]\d{1,2}[FfLl]?[层楼]?(?![A-Za-z0-9])",
     "basement floor"),
    (r"(?<![A-Za-z0-9])\d{1,3}[FfLl][层楼]?(?![A-Za-z0-9" + _CJK + r"])",
     "floor"),
    # The other spelling of the same thing: F2, L3, F2层. Letter first, which
    # the rule above (digit first) does not match.
    (r"(?<![A-Za-z0-9])[FfLl]\d{1,2}[层楼]?(?![A-Za-z0-9])",
     "floor, letter-first spelling"),
    (r"[负地][下]?[一二三四五六七八九十]{1,3}[楼层]", "basement floor in words"),
    (r"[一二三四五六七八九十]{1,3}[楼层]", "floor in words"),
    # ``(?<!\d)`` so 18楼 is taken whole rather than matching at "8楼" and
    # leaving a stray 1 behind. There is deliberately NO ``(?<!号)`` guard:
    # 号 immediately before 楼 spells a BUILDING number (``18号楼``), which this
    # pattern cannot match anyway since it needs a digit against the 楼, while
    # blocking on it would keep the floor in every ``...路1号3楼`` address.
    (r"(?<!\d)\d{1,3}[楼层](?![" + _CJK + r"])", "numeric floor"),
    # Units and shop numbers: f3015号铺, A301, 21街区, 1号机.
    (r"[A-Za-z]?\d{1,4}号?[铺舖室](?![" + _CJK + r"])", "unit"),
    (r"(?<![" + _CJK + r"A-Za-z])[A-Za-z]\d{2,4}(?![A-Za-z0-9" + _CJK + r"])",
     "unit code"),
    (r"\d{1,3}号机(?![" + _CJK + r"])", "cabinet position"),
    (r"\d{1,3}街区", "in-mall block"),
    # Relational tails: 电梯口, 金逸影城旁, 星巴克对面, 东侧, 1号入口.
    (r"[" + _CJK + r"]{0,6}电梯口", "next to the lift"),
    (r"[" + _CJK + r"]{2,8}?旁(?:边)?(?![" + _CJK + r"])", "next to a tenant"),
    (r"[" + _CJK + r"]{2,8}?对面(?![" + _CJK + r"])", "opposite a tenant"),
    (r"(?<![" + _CJK + r"])[东西南北]?[东西南北]侧(?![" + _CJK + r"])",
     "which side of the building"),
    (r"[①-⑳]", "circled digit entrance marker"),
    (r"\d{1,2}号?入口", "entrance number"),
]

_NOISE_RES = [(re.compile(pat), why) for pat, why in _NOISE]

#: Bracketed branch labels on a venue name: 环游嘉年华（北京朝阳大悦城店）.
#: The bracket contents are the useful half - that is where the mall is named.
_BRANCH_RE = re.compile(r"[（(]([^）)]{2,20})[)）]")

#: A road plus its number: 新湖路99号, 朝阳北路101号, 中山大道西1号.
#:
#: Two traps encoded here, both observed in this dataset:
#:   * ``街(?!道)`` and ``道(?<!街道)`` - 桥北街道 is a SUBDISTRICT, not a
#:     street. Read as a road it yields "桥北街道", which geocodes to an
#:     administrative area rather than a street.
#:   * ``_ROAD_HEAD_STOP`` - the character class for the road's own name
#:     excludes 与和及至到 and the positional words, so
#:     ``黄河西路与开元南大道`` does not produce the road "与开元南大道". A
#:     Chinese crossroads is written "A与B交叉口" and the 与 belongs to neither.
#: 和 is deliberately NOT here: 和平路, 和平大街 and 祥和路 are all real roads,
#: and excluding it costs more than the rare "A和B交叉口" it would catch.
_ROAD_HEAD_STOP = "与及至到近在旁内侧对号层楼口"
# Python re has no character-class intersection, so the exclusion is spelled
# as a lookahead in front of a class that still requires a CJK character.
_ROAD_CHAR = "(?![" + _ROAD_HEAD_STOP + "])[" + _CJK + "]"
_ROAD_BODY = "(?:大道(?<!街道)|大街|小街|环路|公路|马路|胡同|路|街(?!道)|道(?<!街道)|巷|弄)"

_ROAD_NUM_RE = re.compile(
    "((?:" + _ROAD_CHAR + "){1,8}" + _ROAD_BODY
    + r"(?:[东西南北]段?)?)\s*(\d{1,5})\s*号")

_ROAD_RE = re.compile("((?:" + _ROAD_CHAR + "){2,8}" + _ROAD_BODY + ")")


def norm(text):
    """NFKC, whitespace collapsed. The same folding geocode_cn.norm_addr uses.

    Duplicated deliberately rather than imported: geocode_cn imports this
    module, so importing it back would be circular, and this module must stay
    usable on its own.
    """
    if text is None:
        return ""
    return " ".join(unicodedata.normalize("NFKC", str(text)).split())


def trim_admin(name, floor=3):
    """Strip leading administrative tokens off an extracted name.

    ``怀仁市新天地购物广场`` -> ``新天地购物广场``. Stops as soon as the
    remainder would fall below ``floor`` characters, so a mall genuinely called
    ``城市广场`` or a district-named landmark cannot be trimmed into nothing.
    """
    name = norm(name)
    for _ in range(4):
        m = _ADMIN_HEAD_RE.match(name)
        if not m or len(name) - m.end() < floor:
            break
        name = name[m.end():]
    return name


def strip_noise(addr):
    """Address with the interior-of-a-building tail removed.

    Conservative on purpose. Anything it is not sure about it keeps, because a
    query with one extra token still resolves (the geocoder ignores it) while a
    query missing a street number resolves to the wrong building on the right
    road, which looks correct and is not.
    """
    text = norm(addr)
    if not text:
        return ""
    # Two passes, because the rules cascade: in ``朝阳大悦城8F金逸影城旁`` the
    # floor rule refuses 8F while a CJK character still follows it, and only
    # after the relational rule has taken ``金逸影城旁`` away does 8F become
    # removable. A second pass is cheaper and far more predictable than trying
    # to order twenty regexes so every cascade resolves in one.
    for _pass in (1, 2):
        for rx, _why in _NOISE_RES:
            text = rx.sub(" ", text)
    # The substitutions leave gaps and orphaned punctuation behind.
    text = re.sub(r"[\s,，、;；]+", " ", text)
    text = re.sub(r"[（(]\s*[)）]", " ", text)
    return " ".join(text.split()).strip(" -,，、;；")


def find_landmark(text):
    """The mall / building name in ``text``, or None.

    Walks backwards from a mall suffix until a character that cannot belong to
    a name. The RIGHTMOST suffix wins because a Chinese address runs coarse to
    fine, so the building is the last thing named; and the longest suffix is
    tried first so ``购物中心`` is never truncated to ``中心``.
    """
    text = norm(text)
    if not text:
        return None
    best = None
    for suf in MALL_SUFFIXES:
        start = 0
        while True:
            i = text.find(suf, start)
            if i < 0:
                break
            start = i + 1
            j = i
            # At most 12 characters back: longer than any real mall name, short
            # enough that a runaway walk cannot swallow the road in front of it.
            while j > 0 and (i - j) < 12:
                ch = text[j - 1]
                if ch in _LANDMARK_STOP or ch.isdigit():
                    break
                j -= 1
            name = trim_admin(text[j:i + len(suf)])
            if len(name) < 3 or name == suf or name in _LANDMARK_REJECT:
                continue
            # Rightmost wins; on a tie the longer name wins.
            if best is None or i > best[0] or (i == best[0]
                                               and len(name) > len(best[1])):
                best = (i, name)
    return best[1] if best else None


def find_road(text):
    """``(road, number)`` from ``text``; number is None when unnumbered.

    A numbered road is the strongest thing in a Chinese address after the
    building name, and the only thing that separates two malls on one street.
    """
    text = norm(text)
    if not text:
        return None, None
    hits = list(_ROAD_NUM_RE.finditer(text))
    if hits:
        m = hits[-1]
        road = trim_admin(m.group(1), floor=3)
        return road, m.group(2)
    hits = list(_ROAD_RE.finditer(text))
    if hits:
        return trim_admin(hits[-1].group(1), floor=3), None
    return None, None


def name_landmark(name):
    """The mall named inside a venue NAME, or None.

    ``环游嘉年华（北京朝阳大悦城店）`` -> ``北京朝阳大悦城``. The bracket
    contents are searched first because that is where the branch label lives;
    the bare name is the fallback for ``尖峰玩家佛山南海万达店``-style names with
    no brackets. A trailing 店 is dropped, since "store" is not part of the
    mall's name and pushes the geocoder toward chain outlets.
    """
    name = norm(name)
    if not name:
        return None
    for m in _BRANCH_RE.finditer(name):
        inner = re.sub(r"店$", "", m.group(1))
        hit = find_landmark(inner)
        if hit:
            return hit
    return find_landmark(re.sub(r"店$", "", name))


#: Venue-type words shared by half the arcades in the country. They must come
#: OFF both sides before two names are compared, or ``欢乐总动园电玩城`` and
#: ``欢乐时光电玩城`` - different venues in different counties - look alike on
#: the strength of ``电玩城`` alone.
_GENERIC_VENUE_WORDS = (
    "家庭娱乐中心", "成人用品店", "儿童乐园", "游乐王国", "电玩城", "游戏城",
    "动漫城", "游艺城", "娱乐城", "娱乐厅", "游乐场", "俱乐部", "购物中心",
    "娱乐中心", "体验馆", "游艺厅", "电玩", "游艺", "乐园", "乐场", "广场",
    "公园", "商场", "商城", "中心", "店",
)


def name_segments(name):
    """A venue name SPLIT on its generic type words, longest pieces first.

    Split rather than delete, because deleting joins two halves that were never
    adjacent: ``街霸电玩台球厅`` minus ``电玩`` reads ``街霸台球厅``, and the
    junction ``霸台`` is a run that appears in neither the name nor any answer.
    Split, it yields ``台球厅`` and ``街霸`` - and ``街霸`` is the distinctive
    half that identifies the venue.
    """
    text = re.sub(r"[（(].*?[)）]", " ", norm(name))
    for word in _GENERIC_VENUE_WORDS:
        text = text.replace(word, " ")
    parts = [re.sub(r"[\s·・,，.。\-]+", "", p) for p in text.split(" ")]
    return sorted((p for p in parts if len(p) >= 2), key=len, reverse=True)


def name_agrees(venue, answer, k=3):
    """Does ``answer`` look like it is about ``venue``? (for NAME queries only)

    A venue-name query is the weakest rung in the ladder and it fails in a way
    the area gate cannot see: Baidu answers ``跳跃者成人室内蹦床公园`` with an
    adult-products shop in the right city, and ``欢乐总动园电玩城`` with a
    DIFFERENT arcade (``欢乐时光电玩城``) in the right prefecture. Both are in
    the right place and neither is the right venue, so the only thing that can
    separate them is the name.

    The comparison is per SEGMENT, never across two of them, and the generic
    half is what gets dropped: matching on ``电玩城`` alone would call every
    arcade in China the same venue. A segment agrees when a ``k``-character run
    of it appears in the answer, or - for a segment too short to have one - when
    the whole segment does. That is what lets ``街霸`` confirm
    ``街霸电玩娱乐厅`` while ``欢乐总动园`` still refuses ``欢乐时光电玩城``.

    A venue whose name is entirely generic has no distinctive segment, so it
    cannot be confirmed and the row keeps its honest centroid.
    """
    answer = norm(answer)
    if not answer:
        return False
    for seg in name_segments(venue):
        if len(seg) < k:
            if seg in answer:
                return True
            continue
        if any(seg[i:i + k] in answer for i in range(len(seg) - k + 1)):
            return True
    return False


def full_name_queries(name, city=None, district=None, province=None):
    """The venue-NAME rungs for one entry, coarse-to-fine. May be empty.

    Split out of ``candidates`` so the caller can tell which queries came from
    the name and hold only those to ``name_agrees``. One definition, so the two
    cannot drift.
    """
    full = re.sub(r"\s+", "", norm(name)) if name else ""
    city, district, province = norm(city), norm(district), norm(province)
    if not full or not (city or province):
        return []
    out, seen = [], set()

    def head(text, deepest=None):
        parts = []
        for tok in (province, city, deepest):
            if tok and tok not in text and tok not in "".join(parts):
                parts.append(tok)
        return "".join(parts)

    if district:
        _add(out, seen, head(full, district) + full)
    _add(out, seen, head(full) + full)
    return out


def _add(out, seen, query):
    """Append a query once, ignoring blanks and duplicates."""
    q = norm(query)
    if len(q) < 4 or q in seen:
        return
    seen.add(q)
    out.append(q)


def candidates(address, city=None, district=None, province=None, name=None):
    """Ordered query strings for one address, best first.

    ``city`` / ``district`` / ``province`` are the administrative names the
    caller resolved (geocode_cn does this against data/china_areas.json). They
    are prepended to every short query, because a bare ``万达广场`` is the one
    thing a geocoder will confidently answer wrong: there are over four hundred
    of them.

    The order, and why each rung exists:

      1. the full cleaned address - has the street number, so it separates two
         malls on the same road. Wins outright when the address is complete.
      2. city + district + landmark - for an address whose number is missing or
         wrong but whose mall is named; the district disambiguates the four
         万达广场 in one city.
      3. city + landmark - same, for an address that names no district.
      4. city + road + number - the address named a number but no building.
      5. city + landmark from the venue NAME - the bemanicn rescue: the shop is
         named after a mall its address never mentions.
      6. city + road - last resort, and street precision at best.
      7. city + the WHOLE venue name - the rung for a row whose address is
         unusable and whose name contains no recognisable mall suffix. Chinese
         arcades are POIs in their own right, so ``齐齐哈尔市街霸电玩台球厅``
         answers when ``碾子山区`` (a bare district, the entire address) cannot.
         It is LAST on purpose: a trading name is the weakest evidence here,
         because chains repeat it in every city, and the city prefix plus
         verify_area are the only things keeping it honest.

    The name rungs always carry the administrative prefix. Measured: the bare
    name ``快乐拾光`` returns a Zhengzhou venue while ``重庆郊县快乐拾光``
    returns the right one in 丰都县, and ``毛毛虫乐场`` alone is ambiguous.
    A bare-name rung is therefore deliberately NOT offered.
    """
    cleaned = strip_noise(address)
    landmark = find_landmark(cleaned) or find_landmark(norm(address))
    road, number = find_road(cleaned)
    nm_landmark = name_landmark(name) if name else None

    city = norm(city)
    district = norm(district)
    province = norm(province)

    def head(text, deepest=None):
        """The administrative tokens ``text`` is missing, in coarse-to-fine
        order. A token already inside the string is not repeated:
        ``广东省深圳市广东省深圳市...`` measurably degrades the match."""
        parts = []
        for tok in (province, city, deepest):
            if tok and tok not in text and tok not in "".join(parts):
                parts.append(tok)
        return "".join(parts)

    out, seen = [], set()
    if cleaned:
        _add(out, seen, head(cleaned) + cleaned)
    if landmark:
        if district:
            _add(out, seen, head(landmark, district) + landmark)
        _add(out, seen, head(landmark) + landmark)
    if road and number:
        _add(out, seen, head(road) + road + number + "号")
    if nm_landmark:
        if district:
            _add(out, seen, head(nm_landmark, district) + nm_landmark)
        _add(out, seen, head(nm_landmark) + nm_landmark)
    if road:
        _add(out, seen, head(road) + road)
    # The whole venue name, last. Only useful with a city in front of it, so a
    # row with no resolved city does not get this rung at all - an unprefixed
    # trading name is exactly the query that resolves to a same-named branch a
    # thousand kilometres away.
    for q in full_name_queries(name, city=city, district=district,
                               province=province):
        _add(out, seen, q)
    if not out and cleaned:
        _add(out, seen, cleaned)
    return out
