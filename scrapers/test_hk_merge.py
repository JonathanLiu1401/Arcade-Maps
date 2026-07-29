"""Unit tests for the Hong Kong / Macau cross-script tier.

Hong Kong is the hardest place in the dataset to dedupe: the official sources
publish English names with coordinates, BemaniCN publishes Chinese names with a
precise address and no coordinate, and the two share no characters. Every case
below is either a venue that shipped as two pins, or a pair the guards exist to
keep apart.

Run: python scrapers/test_hk_merge.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hk_match as hm
import merge

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


# ------------------------------------------------------- romanization ------
# The bridge the whole tier rests on. Jyutping and Hong Kong's government
# romanisation disagree constantly, so these all have to survive the fold.
print("--- Cantonese reading ---")
for cjk, latin, want in [
        ("碧富", "PIK FU GAME CENTRE", "碧富"),
        ("天天", "TIN TIN GAME CENTRE", "天天"),
        ("和宜合道", "26-30 WO YI HOP ROAD, KWAI CHUNG", "和宜合"),
        ("青柏徑", "5 TSING PAK PATH, TUEN MUN", "青柏"),
        ("旺角", "MONGKOK, KOWLOON", "旺角"),
        ("荃灣", "TSUEN WAN N.T", "荃灣"),
        ("天水圍", "TIN SHUI WAI, N.T.", "天水圍"),
        ("大埔", "TAI PO,N.T", "大埔"),
        ("洗衣街", "39SAI YEE STREET", "洗衣"),
        ("油麻地", "YAU MA TEI, KOWLOON", "油麻地"),
        ("沙田", "SHA TIN ,NT.", "沙田"),
        ("元朗", "Yuen Long, N.T.", "元朗"),
]:
    hits = hm.romanization_matches(cjk, latin)
    check("%s reads as %s" % (cjk, latin.split(",")[0][:22]), want in hits,
          repr(sorted(hits)))

check("an unrelated pair does not read alike",
      not hm.romanization_matches("觀塘", "TIN SHUI WAI"))

# ------------------------------------------------------------ addresses ----
print("\n--- street extraction ---")
for cn, en, street, num in [
        ("旺角洗衣街39-55號金雞廣場二樓",
         "2/F, GOLDEN ERA PLAZA, 39SAI YEE STREET, MONGKOK", "saiyi", (39, 39)),
        ("屯門新墟青柏徑5號 四寶大廈",
         "SHOP B, G/F., SAI BO BUILDING, 5 TSING PAK PATH, TUEN MUN, NT",
         "cingpak", (5, 5)),
        ("觀塘牛頭角道300-302號裕民中心地下54-58號鋪",
         "GIF YUE MAN SHOPPING CENTRE 300-302 NGAU TAU KOK RD. KWUN TONG",
         "ngautaukok", (300, 302)),
]:
    streets, numbers = hm.street_match(hm.street_refs(cn), hm.street_refs(en))
    check("%s -> %s %s" % (cn[:14], street, num),
          street in streets and num in numbers,
          "%r %r" % (sorted(streets)[:3], sorted(numbers)))

# 39-55 and 39 are one address. An equality test on the tokens sees two, which
# is why Golden Era stayed split for as long as it did.
check("a range contains a bare number",
      (39, 39) in hm.street_match(hm.street_refs("洗衣街39-55號"),
                                  hm.street_refs("39 SAI YEE STREET"))[1])

# 旧大街 is "Old Main Street" translated, not romanized, and 旧 is not even in
# the readings table. The number still has to come out.
check("a number survives an unreadable street name",
      (82, 82) in hm.street_numbers("香港仔旧大街82号地库")
      and (82, 82) in hm.street_numbers("BASEMENT, 82 OLD MAIN STREET"))
check("a typo'd road word does not lose the number",
      (63, 63) in hm.street_numbers("UNIT NO.23  LG/F,HOUSTON CENTRE,"
                                    "NO.63 MODY DOAD,KLN. HKG"))

# ------------------------------------------------------------- evidence ----
print("\n--- evidence and vetoes ---")


def ev(addr_a, name_a, addr_b, name_b):
    return hm.evidence(addr_a, name_a, addr_b, name_b)


types, veto = ev("BF., ARGYLE CENTRE PHASE I,65 ARGYLE ST, MONGKOK, KOWLOON "
                 "B/F 65 Argyle St 旺角 (Mong Kok) 九龍 (Kowloon)",
                 "GAMEZONE(MONG KOK) Game Zone",
                 "旺角彌敦道688號地底鋪全層", "旺角新之城GAME ZONE游戏天地")
check("Game Zone Mong Kok: brand plus locality",
      not veto and set(types) == {"brand", "place"}, repr(sorted(types)))

# Two buildings on one road. Every other kind of evidence would have called
# these one arcade.
types, veto = ev("觀塘觀塘道418號創紀之城五期商場11樓", "FUN @ APM",
                 "觀塘道410號地庫1舖", "觀塘金沙遊戲機")
check("same road, different numbers, vetoed", veto, repr(sorted(types)))

types, veto = ev("九龍太子彌敦道聯合廣場地下G15-17 G/F, 760 Nathan Rd., Kowloon",
                 "太子 (Prince Game Centre)",
                 "旺角彌敦道688號地底鋪全層", "旺角新之城GAME ZONE游戏天地")
check("760 Nathan Road is not 688 Nathan Road", veto, repr(sorted(types)))

# A locality is not a brand.
types, _ = ev("5 TSING PAK PATH, TUEN MUN, NT", "TIN TIN GAME CENTRE(TUEN MUN)",
              "新界屯門仁政街13-15號屯門中心大廈", "屯門威水 (Smart TV Game Centre)")
check("TUENMUN in both names is not a shared brand",
      "brand" not in types, repr(sorted(types)))
check("and the pair has only its locality", set(types) <= {"place"},
      repr(sorted(types)))

# Single digits are shop and floor numbers in Hong Kong and pair half the
# territory; a bare one must not corroborate anything.
types, _ = ev("B,TAI PO SPORTS ASSOCIATION 2ON CHEUNG RD.,TAI PO,N.T",
              "IGAME(TAI PO)", "佐敦吳松街2號地底鋪", "佐敦Game Zone")
check("a shared 2 on unrelated streets is not evidence",
      "number" not in types, repr(sorted(types)))

types, _ = ev("BASEMENT, 82 OLD MAIN STREET,ABERDEEN, HONG KONG,", "JUMBO GAME",
              "香港岛香港仔香港仔旧大街82号地库", "珍宝游戏机中心")
check("Aberdeen plus 82 is enough when nothing romanizes",
      set(types) == {"place", "number"}, repr(sorted(types)))

# ------------------------------------------------------------ clustering ---
print("\n--- clustering ---")


def unit(source, name, addr, lat=None, lng=None, country="Hong Kong"):
    return {"source": source, "name": name, "addr": addr, "lat": lat,
            "lng": lng, "games": {"other"}, "cabs": set(), "country": country,
            "pref": None, "ziv_url": None, "notes": [], "coord_system": "wgs84",
            "cn_prov": None, "cn_city": None, "bemanicn_url": None,
            "game_counts": {}, "counts_tallied": False}


def together(units, i, j):
    groups = merge.cluster_units(units, [])
    return any(i in m and j in m for m in groups.values())


MONGKOK = [
    unit("allnet", "GAMEZONE(MONG KOK)",
         "BF., ARGYLE CENTRE PHASE I,65 ARGYLE ST, MONGKOK, KOWLOON",
         22.3195, 114.1715),
    unit("ziv", "Game Zone", "B/F 65 Argyle St 旺角 (Mong Kok) 九龍 (Kowloon)",
         22.3195, 114.1714),
    unit("bemanicn", "旺角新之城GAME ZONE游戏天地", "旺角彌敦道688號地底鋪全層"),
]
check("Mong Kok Game Zone merges into one venue", together(MONGKOK, 0, 2))

# The locality reading is what tells the branches apart: without it GAMEZONE
# alone pairs all six Hong Kong branches with each other.
kwuntong = [
    unit("allnet", "GAMEZONE(KWUN TONG PLAZA)",
         "1/F,KWUN TONG PLAZA,68HOI YUEN ROAD, KWUNTONG, KOWLOON",
         22.3112, 114.2260),
    unit("bemanicn", "旺角新之城GAME ZONE游戏天地", "旺角彌敦道688號地底鋪全層"),
]
check("a Mong Kok row does not attach to a Kwun Tong venue",
      not together(kwuntong, 0, 1))

# Mutual best with a margin. 佐敦Game Zone is a candidate for Kwun Tong Plaza
# on brand and a locality reading, and plain uniqueness let it block the real
# pair; the better-evidenced partner has to win instead.
contested = [
    unit("allnet", "GAMEZONE(KWUN TONG PLAZA)",
         "1/F,KWUN TONG PLAZA,68HOI YUEN ROAD, KWUNTONG, KOWLOON",
         22.3112, 114.2260),
    unit("bemanicn", "觀塘廣場GAMEZONE", "開源道68號觀塘廣場1樓117-121"),
    unit("bemanicn", "佐敦Game Zone", "佐敦吳松街2號地底鋪"),
]
check("the better-evidenced partner wins", together(contested, 0, 1))
check("and the weaker candidate stays out", not together(contested, 0, 2))

# Pik Fu is the case that needed the reading: no shared number, no shared
# script, nothing but 碧富 = Pik Fu and 和宜合 = Wo Yi Hop.
pikfu = [
    unit("allnet", "PIK FU GAME CENTRE",
         "SHOP LG1,26-30 WO YI HOP ROAD, KWAI CHUNG,N.T", 22.3658, 114.1372),
    unit("bemanicn", "碧富遊戲機", "和宜合道"),
]
check("Pik Fu merges on the Cantonese reading alone", together(pikfu, 0, 1))

# A genuine tie must still refuse: this BemaniCN row names two arcades that
# share one building, and picking either would be a guess.
tie = [
    unit("ziv", "兒童王國", "澳門永華街3-91 號僑光大廈", 22.2105, 113.5525,
         country="Macau"),
    unit("ziv", "新遊戲", "永華街57號僑光工業大廈地下H舖", 22.2104, 113.5522,
         country="Macau"),
    unit("bemanicn", "新遊戲/兒童王國", "永華街57號僑光大廈地下H鋪", country="Macau"),
]
check("a tie between two equally-evidenced venues refuses",
      not together(tie, 0, 2) and not together(tie, 1, 2))

print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
if FAILED:
    print("FAILURES:")
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL TESTS PASSED")
