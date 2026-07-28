"""Unit tests for the ZIv counts-honesty gate in scrapers/merge.py.

The rule these guard is easy to get subtly wrong, and getting it wrong puts
invented cabinet numbers on the map. See rule (m) in merge.py.

Run: python scrapers/test_counts_honesty.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge
import ziv

# Japanese/Chinese cab titles in test output die on the cp1252 console.
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


def note(*titles):
    """A ZIv row's notes field: the machine list, de-duplicated and sorted,
    which is exactly the shape ziv.py writes."""
    return "Cabs: " + "; ".join(sorted(set(titles)))


# ------------------------------------------------------------ the core rule -
print("--- placeholder vs real tally ---")

check("one of each game is not a tally",
      not merge._ziv_counts_tallied(
          note("maimai DX PRiSM", "CHUNITHM VERSE"),
          {"maimai_dx": 1, "chunithm": 1}))

check("a repeated title IS a tally",
      merge._ziv_counts_tallied(
          note("maimai DX PRiSM", "CHUNITHM VERSE"),
          {"maimai_dx": 5, "chunithm": 1}),
      "5 machines, 1 title")

check("two versions of one game are not a tally",
      not merge._ziv_counts_tallied(
          note("DanceDanceRevolution A3", "DanceDanceRevolution WORLD"),
          {"ddr": 2}),
      "2 machines, 2 titles")

# The bug this file exists for: GAMEZONE(MONG KOK) drew gitadora x2 off one
# GuitarFreaks cabinet and one DrumMania cabinet.
check("two titles under one slug are not a tally",
      not merge._ziv_counts_tallied(
          note("GuitarFreaksV7", "DrumManiaV7", "jubeat beyond the Ave."),
          {"gitadora": 2, "jubeat": 1}),
      "GuitarFreaks + DrumMania -> gitadora")

check("one tallied slug vouches for the whole row",
      merge._ziv_counts_tallied(
          note("pop'n music Sunny Park", "pop'n music 20 fantasia",
               "beatmania IIDX 21 SPADA", "beatmania IIDX 19 Lincle"),
          {"popn": 3, "iidx": 2}),
      "popn 3 > 2 titles, so iidx 2 is trusted as well")

# ------------------------------------------------------------------- guards -
print("\n--- guards ---")

check("a slug no title maps to is not evidence",
      not merge._ziv_counts_tallied(
          note("Speed Rider 3DX", "Time Crisis 5"), {"gitadora": 2}),
      "0 titles matched, so 2 > 0 must NOT count")

check("no counts, no decision", not merge._ziv_counts_tallied(note("X"), {}))
check("no note, no decision", not merge._ziv_counts_tallied(None, {"ddr": 4}))
check("a note that is not a cab list is not parsed",
      not merge._ziv_counts_tallied("region: 香港", {"ddr": 4}))

# ------------------------------------------------- title -> slug resolution -
# _ziv_counts_tallied reads titles WITHOUT the seriesID that ziv.py normally
# leans on, so a regional or alternate spelling missing from GAME_PATTERNS
# reads as an unmapped title. That undercounts the titles behind a slug and
# turns two separate cabinets into a phantom tally, which is how
# "GUITARFREAKS + PercussionFreaks" used to survive as gitadora x2.
print("\n--- title-only slug lookup ---")

for title, want in [
        ("PercussionFreaks 5thMIX", "gitadora"),
        ("狂熱鼓手V7", "gitadora"),
        ("Dancing Stage EuroMIX2", "ddr"),
        ("Wadaiko Master", "taiko"),
        ("ノスタルジア Op.3", "nostalgia"),
        ("MÚSECA 1+1/2", "museca"),
        ("舞萌DX 2024", "maimai_dx"),
        ("UBeat", "jubeat"),
        ("ポラリスコード", "polaris_chord"),
]:
    check("%s -> %s" % (title, want), want in ziv.slugs_for_title(title),
          repr(sorted(ziv.slugs_for_title(title))))

check("an unrelated cab maps to nothing",
      ziv.slugs_for_title("Time Crisis 5") == set())

check("GuitarFreaks and PercussionFreaks are two titles, one slug",
      ziv.slugs_for_title("GUITARFREAKS") ==
      ziv.slugs_for_title("PercussionFreaks") == {"gitadora"})

print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
if FAILED:
    print("FAILURES:")
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL PASS")
