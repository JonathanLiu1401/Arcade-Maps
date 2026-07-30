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

# --------------------------------------------------- evidence-driven counts -
# The rule above decides whether a LISTED tally may be published. These cover
# the second axis added with count_evidence: a quantity a human actually
# stated ("12 machines") is authoritative and must survive, a listed tally is
# a lower bound and must stay marked as one, and a source that publishes no
# quantities at all must never acquire a count.
print("\n--- count evidence: real quantity vs lower bound ---")

check("evidence vocabulary is exactly the three classes",
      merge.COUNT_EVIDENCE == {"ziv_listed", "ziv_comment", "bemanicn_qty"},
      repr(sorted(merge.COUNT_EVIDENCE)))

check("only stated quantities count as REAL",
      merge.REAL_COUNT_EVIDENCE == {"ziv_comment", "bemanicn_qty"},
      "ziv_listed is a floor, not a tally")


def fold(*triples):
    """Run _take_count over (slug, n, evidence) triples -> (counts, evidence)."""
    counts, evidence = {}, {}
    for slug, n, ev in triples:
        merge._take_count(counts, evidence, slug, n, ev)
    return counts, evidence


# The core of the fix: a stated quantity must beat a bigger listed tally.
# A plain per-slug max would publish the 9 and then label it with the
# comment's evidence - a number from one source wearing another's credibility.
c, e = fold(("chunithm", 9, "ziv_listed"), ("chunithm", 3, "ziv_comment"))
check("a stated 3 beats a listed 9", c == {"chunithm": 3},
      "got %r" % c)
check("...and carries the stated evidence", e == {"chunithm": "ziv_comment"})

c, e = fold(("chunithm", 3, "ziv_comment"), ("chunithm", 9, "ziv_listed"))
check("order does not change that", c == {"chunithm": 3} and
      e == {"chunithm": "ziv_comment"}, "got %r %r" % (c, e))

c, e = fold(("iidx", 2, "ziv_comment"), ("iidx", 8, "ziv_comment"))
check("within one evidence class the larger count wins",
      c == {"iidx": 8}, "got %r" % c)

c, e = fold(("popn", 4, "ziv_comment"), ("popn", 2, "bemanicn_qty"))
check("bemanicn 台数 outranks a ZIv comment", c == {"popn": 2} and
      e == {"popn": "bemanicn_qty"}, "got %r %r" % (c, e))

c, e = fold(("ddr", 0, "ziv_comment"), ("ddr", -1, "bemanicn_qty"))
check("a zero or negative count is never published", c == {} and e == {},
      "got %r %r" % (c, e))

# GiGO Akihabara Building 3 is the owner's screenshot: the listing's comments
# say twelve CHUNITHM, eight IIDX LIGHTNING, three maimai and eight SDVX, and
# the map rendered x1. Parsed straight from ziv.py so a parser regression that
# silently stops reading comments fails HERE and not only in a full rebuild.
print("\n--- GiGO Akihabara Building 3 (the owner's screenshot) ---")

for comment, want in [("12x", 12), ("8x", 8), ("3x", 3), ("4x", 4)]:
    check("comment %r parses to %d" % (comment, want),
          ziv.parse_machine_quantity(comment) == want,
          repr(ziv.parse_machine_quantity(comment)))

check("a comment with no quantity stays None",
      ziv.parse_machine_quantity("") is None and
      ziv.parse_machine_quantity(None) is None and
      ziv.parse_machine_quantity("nice cab") is None)

# One commented machine and one bare sibling: the comment is the authority
# and the sibling still exists, so the total is 12 + 1 and the row is a
# stated quantity, not a floor.
counts, evidence, models = ziv._counts_and_evidence_for_machines([
    ("CHUNITHM X-VERSE-X", 506, "12x"),
    ("CHUNITHM NEW", 506, None),
])
check("a stated quantity plus a bare sibling totals 13",
      counts.get("chunithm") == 13, repr(counts))
check("...and is evidenced as a stated quantity",
      evidence.get("chunithm") == "ziv_comment", repr(evidence))

counts, evidence, models = ziv._counts_and_evidence_for_machines([
    ("beatmania IIDX 33 Sparkle Shower (LIGHTNING MODEL)", 2, "8x"),
])
check("a Lightning cab's stated 8 lands in cab_models too",
      models.get("iidx_lm") == 8, repr(models))
check("...and in the game count", counts.get("iidx") == 8, repr(counts))

# The fabrication guard, stated as a property of the vocabulary rather than
# of any one venue: there is no evidence class an official store list could
# ever claim, so ALL.Net / e-amusement / wahlap / round1usa cannot acquire a
# count no matter what else changes.
print("\n--- never fabricate ---")

check("no evidence class exists for a quantity-less source",
      not (merge.COUNT_EVIDENCE & {"allnet", "eagate", "wahlap",
                                   "round1usa", "allnet_qty"}),
      "ALL.Net and e-amusement publish no quantities at all")

counts, evidence, models = ziv._counts_and_evidence_for_machines([
    ("maimai DX PRiSM PLUS", 284, None),
    ("CHUNITHM VERSE", 506, None),
])
check("an uncommented listing yields a floor, never a stated quantity",
      set(evidence.values()) == {"ziv_listed"}, repr(evidence))
check("...and that floor is still only the list length",
      counts == {"maimai_dx": 1, "chunithm": 1}, repr(counts))

# Every cab_models slug must be one the frontend's VARIANTS table knows;
# an unknown slug renders as nothing at all.
print("\n--- cab_models vocabulary ---")

ziv_variants = {v for v, _rx in ziv.CAB_VARIANT_RULES}
check("every variant ziv.py can assert is allowed through merge",
      ziv_variants <= merge.CAB_MODEL_SLUGS,
      repr(sorted(ziv_variants - merge.CAB_MODEL_SLUGS)))

check("every cab model slug knows which game it is a cabinet of",
      all(merge.CAB_MODEL_GAME.get(s) for s in merge.CAB_MODEL_SLUGS),
      "the parent game is what justifies the count")

check("every parent game is a real game slug",
      set(merge.CAB_MODEL_GAME.values()) <= set(merge.GAME_SLUGS),
      repr(sorted(set(merge.CAB_MODEL_GAME.values())
                  - set(merge.GAME_SLUGS))))

# The fabrication this gate exists to stop, restated as data. ziv.py folds
# comment quantities into cab_models but DISCARDS the evidence class while
# doing it, so a bare title with no comment arrives as a 1 meaning "this
# cabinet exists" rather than "there is one of them". Publishing that put
# 1,345 invented "Lightning x1" / "Legacy CRT x1" pills on the map - the
# owner's original complaint, moved from the game chip to the cabinet pill.
print("\n--- cab_models counts obey the same evidence rule ---")

counts, evidence, models = ziv._counts_and_evidence_for_machines([
    ("DanceDanceRevolution EXTREME", None, None),
])
check("ziv still emits a bare 1 for an uncommented variant",
      models.get("ddr_legacy") == 1, repr(models))
check("...while its parent game is only a floor",
      evidence.get("ddr") == "ziv_listed", repr(evidence))
check("so merge must NOT publish that 1 as a number",
      evidence.get("ddr") not in merge.REAL_COUNT_EVIDENCE,
      "an unbacked variant count is published as null instead")

# A stated quantity backs its cabinets: GiGO's "8x" on the Lightning IIDX
# is a real eight, and the pill may show it.
counts, evidence, models = ziv._counts_and_evidence_for_machines([
    ("beatmania IIDX 33 Sparkle Shower (LIGHTNING MODEL)", 2, "8x"),
])
check("a stated quantity DOES back its cabinet count",
      evidence.get(merge.CAB_MODEL_GAME["iidx_lm"])
      in merge.REAL_COUNT_EVIDENCE and models.get("iidx_lm") == 8,
      repr((evidence, models)))

print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
if FAILED:
    print("FAILURES:")
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL PASS")
