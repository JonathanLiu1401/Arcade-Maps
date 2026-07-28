"""Unit tests for the two Hong Kong / Macau merge tiers in scrapers/merge.py.

Hong Kong is the hardest place in the dataset to dedupe: the official sources
publish English names with coordinates, BemaniCN publishes Chinese names with a
precise address and no coordinate, and the two share no characters. Every case
below is a venue that shipped as two pins, or one the guards exist to keep
apart.

Run: python scrapers/test_hk_merge.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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


def unit(source, name, addr, lat=None, lng=None, country="Hong Kong"):
    return {"source": source, "name": name, "addr": addr, "lat": lat,
            "lng": lng, "games": {"other"}, "cabs": set(), "country": country,
            "pref": None, "ziv_url": None, "notes": [], "coord_system": "wgs84",
            "cn_prov": None, "cn_city": None, "bemanicn_url": None,
            "game_counts": {}, "counts_tallied": False}


def cluster(units):
    """(groups keyed by root, rules fired) for a fabricated unit list."""
    log = []
    groups = merge.cluster_units(units, log)
    return groups, [d.get("rule") for d in log]


def together(units, i, j):
    groups, _ = cluster(units)
    for members in groups.values():
        if i in members and j in members:
            return True
    return False


# ALL.Net files Game Zone under the Argyle Street face of Argyle Centre and
# BemaniCN under the Nathan Road face. Same basement, no shared street number,
# so the whole venue turned on the Latin brand plus the locality.
MONGKOK = [
    unit("allnet", "GAMEZONE(MONG KOK)",
         "BF., ARGYLE CENTRE PHASE I,65 ARGYLE ST, MONGKOK, KOWLOON",
         22.3195, 114.1715),
    unit("ziv", "Game Zone", "B/F 65 Argyle St 旺角 (Mong Kok) 九龍 (Kowloon)",
         22.3195, 114.1714),
    unit("bemanicn", "旺角新之城GAME ZONE游戏天地", "旺角彌敦道688號地底鋪全層"),
]

print("--- hk-locality-brand ---")
groups, rules = cluster(MONGKOK)
check("Mong Kok Game Zone merges into one venue", len(groups) == 1,
      "%d group(s)" % len(groups))
check("and the brand tier is what did it", "hk-locality-brand" in rules,
      repr(rules))

# The locality alias comes from ZIv's own bilingual address, not a hand list.
# Without that row there is no 旺角 -> MONGKOK bridge and the rule must not fire.
no_ziv = [MONGKOK[0], MONGKOK[2]]
check("without ZIv's bilingual address the alias cannot be mined",
      not together(no_ziv, 0, 1))

# Two Game Zones in DIFFERENT localities must stay apart even though the brand
# is identical: that is the whole reason the locality is required.
two_localities = [
    unit("allnet", "GAMEZONE(KWUN TONG PLAZA)",
         "1/F,KWUN TONG PLAZA,68HOI YUEN ROAD, KWUNTONG, KOWLOON",
         22.3112, 114.2260),
    unit("ziv", "GameZone Kwun Tong Plaza",
         "66 Hoi Yuen Road 1/F 觀塘 (Kwun Tong) 九龍 (Kowloon)",
         22.3112, 114.2260),
    unit("bemanicn", "旺角新之城GAME ZONE游戏天地", "旺角彌敦道688號地底鋪全層"),
]
check("a Mong Kok row does not attach to a Kwun Tong venue",
      not together(two_localities, 0, 2))

# Ambiguity blocks rather than guesses: two BemaniCN rows in one locality
# sharing the brand leave the official row alone.
ambiguous = MONGKOK + [
    unit("bemanicn", "旺角另一間GAME ZONE分店", "旺角西洋菜南街100號"),
]
groups, rules = cluster(ambiguous)
check("two candidates in one locality merge neither",
      "hk-locality-brand" not in rules, repr(rules))

# A locality is not a brand. Two unrelated Mong Kok venues share the string
# MONGKOK and nothing else, and must not pair on it.
locality_only = [
    unit("allnet", "GOLDEN ERA GAME CENTRE",
         "2/F, GOLDEN ERA PLAZA, 39SAI YEE STREET, MONGKOK, KOWLOON",
         22.3200, 114.1700),
    unit("ziv", "金雞遊戲機 (Golden Era)",
         "旺角洗衣街39號 2/F, Golden Era Plaza 旺角 (Mong Kok)",
         22.3200, 114.1700),
    unit("bemanicn", "旺角某某遊戲天地", "旺角登打士街50號"),
]
check("a shared locality alone never merges", not together(locality_only, 0, 2))

# Short Latin fragments are not brands either.
short_brand = [
    unit("allnet", "MG(MONG KOK)", "65 ARGYLE ST, MONGKOK, KOWLOON",
         22.3195, 114.1715),
    unit("ziv", "MG", "65 Argyle St 旺角 (Mong Kok)", 22.3195, 114.1714),
    unit("bemanicn", "旺角MG游戏天地", "旺角彌敦道700號"),
]
check("a Latin run under 6 letters cannot pair anything",
      not together(short_brand, 0, 2))

print("\n--- hk-street-number (unchanged behaviour) ---")
# The older tier still owns the case where both sources cite the same number.
plaza = [
    unit("allnet", "HOLLYWOOD GAME ZONE",
         "383, LEVEL 3, PLAZA HOLLYWOODDIAMOND HILL, KOWLOON,",
         22.3407, 114.2021),
    unit("bemanicn", "荷里活遊戲城Game Zone",
         "九龍黃大仙區鑽石山龍蟠街3號荷里活廣場3樓383A號鋪"),
]
groups, rules = cluster(plaza)
check("Plaza Hollywood still merges on 383", len(groups) == 1, repr(rules))

# A unit code is not a street number: SHOP A15 must not bind to street No. 15.
unit_code = [
    unit("allnet", "INTERNATIONAL GAMES CENTRE",
         "SHOP A15, INTERNATIONAL PLAZA, 15 SOMEWHERE RD, KOWLOON",
         22.3000, 114.1800),
    unit("bemanicn", "某某遊戲機中心", "九龍某處A15號鋪"),
]
check("a unit code does not merge on its digits",
      not together(unit_code, 0, 1))

print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
if FAILED:
    print("FAILURES:")
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL TESTS PASSED")
