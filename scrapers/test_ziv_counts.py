"""Unit tests for ZIv comment quantity parsing and cab-variant mapping.

Covers parse_machine_quantity (positives AND negatives), the per-arcade
game_counts / count_evidence fold, maimai classic/DX split, and hardware
variant extraction. A false count is worse than none - negatives are the
load-bearing half of this file.

Run: python scrapers/test_ziv_counts.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ziv

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # pragma: no cover
    pass

FAILED = []
RAN = []


def check(label, cond, detail=""):
    print("%s  %s%s" % ("PASS" if cond else "FAIL", label,
                        ("  <- " + detail) if detail else ""))
    RAN.append(label)
    if not cond:
        FAILED.append(label)


# ------------------------------------------------------------------ qty +
print("--- parse_machine_quantity: positives ---")

POSITIVES = [
    ("12 machines", 12),
    ("3 cabinets", 3),
    ("8 LIGHTNING MODEL machines", 8),
    ("4 cabinets linked.", 4),
    ("Version 5.20, 4 cabinets", 4),
    ("2 machines in the basement of the manga kissa", 2),
    ("x2", 2),
    ("X4", 4),
    ("2 cabs", 2),
    ("2 Cabs", 2),
    ("2台", 2),
    ("4台設置", 4),
    ("2台置いてある", 2),
    ("4x", 4),
    ("2x", 2),
    ("10x", 10),
    ("4x, Ver. 5.20", 4),
    ("2x, Ver. 5.20", 2),
    ("Ver 5.20, 2x", 2),
    ("2x HG cabinet", 2),
    ("4x HG cabinets", 4),
    ("10x HG and 2x normal cabinets", 12),
    ("3x normal and 2x HG cabinet", 5),
    ("1x at 2F, 6x at 3F", 7),
    ("2 sets of 4 linked cabinets each", 8),
    ("2 sets of 4 linked cabinets.", 8),
    ("6 machines HD cabinet.", 6),
    ("There are 5 cabs available to play.", 5),
    ("8 cabs (gold)", 8),
    ("5 Cabs. NOTE: Non-LIGHTNING Model", 5),
    ("4 cabinets in total.", 4),
    ("12 HG cabinets in total.", 12),
    ("JPN Version. 4 machines", 4),
    ("4 linked side-by-side cabs.", 4),
    ("2 cabinets linked.", 2),
    ("3 HD cabinets", 3),
    ("5 Taiko", 5),
    ("1 silver cab, 3 gold", 4),
    ("1x", 1),
    ("6 machines", 6),
    ("16 machines", 16),
    ("新筐体2台ノーマルタイプ1台", 3),
    ("A side-by-side pair of 4 linked side-by-side cabs.", 8),
    ("4 linked side-by-side cabs, as well as another pair of "
     "linked side-by-side cabs next to them.", 6),
    ("6 Cabs", 6),
    ("4 Units", 4),
    ("3x, offline", 3),
    ("4x, one of which is out of order.", 4),
    ("4 Machines", 4),
    ("4 machines", 4),
]

for text, want in POSITIVES:
    got = ziv.parse_machine_quantity(text)
    check("qty+ %r -> %d" % (text, want), got == want,
          "got %r" % (got,))


# ------------------------------------------------------------------ qty -
print("\n--- parse_machine_quantity: negatives (must NOT become counts) ---")

NEGATIVES = [
    None,
    "",
    "   ",
    "100 yen",
    "Version 5.20",
    "Ver. 5.20",
    "2 songs",
    "2P",
    "1P",
    "2F",
    "7F",
    "3F",
    "Cabinet 1",
    "Cabinet 2",
    "Cabinet 3",
    "Cabinet 1 - First generation Lightning Cabinet, Dim monitor",
    "X2 cabinet.",
    "XG2 cabinet.",
    "XG cabinet, 2F",
    "X2 cabinet, Doubles Premium, fan.",
    "50g switches",
    "2013 cabinet",
    "Japanese 4P Unit",
    "Japanese version 1P",
    "In a 2 in 1 cab with dancing eyes.",
    "JPN Version V5.66",
    "1st gen cabinet",
    "The 1st gen cabinet",
    "P2 side off",
    "Online, connected to e-amusement (as of 2025-12-23)",
    "Densha de Go! 2 Kosoku-hen",
    "This is an 6 player cab",
    "3 screen cab",
    "2 screen cab",
    "BT buttons are 100g, and FX buttons are 20g.",
    "Part of the 4 cabinets in the back-right corner that has ~120g switches",
    "Perfect",
    "Will be removed from tbe arcade after Sunday, July 19, 2026",
    "Not working as of September 6, 2025",
    "Astro City Cabinet",
    "JPN Version",
    "Has 1P/2P adjustable headphone jacks.",
    "1P and 2P both in great condition as of Apr 2025",
    "P1 Turnable is scuffed but still very usable.",
]

for text in NEGATIVES:
    got = ziv.parse_machine_quantity(text)
    check("qty- %r -> None" % (text,), got is None, "got %r" % (got,))


# ------------------------------------------------------ fold / evidence
print("\n--- game_counts + count_evidence fold ---")

counts, evidence, cab_models = ziv._counts_and_evidence_for_machines([
    ("beatmania IIDX 33 Sparkle Shower (LIGHTNING MODEL)", 2,
     "8 LIGHTNING MODEL machines"),
    ("CHUNITHM X-VERSE-X", 506, "12 machines"),
    ("maimai でらっくす CiRCLE PLUS", 284, "3 machines"),
    ("SOUND VOLTEX ∇ (Valkyrie model)", 173, "8 machines"),
    ("pop'n music High☆Cheers", 3, None),
    ("jubeat beyond the Ave.", 5, ""),
    ("Time Crisis 5", None, "4x"),  # non-rhythm: no slug, not counted
])

check("GiGO-style iidx count is 8", counts.get("iidx") == 8,
      repr(counts))
check("GiGO-style iidx evidence is ziv_comment",
      evidence.get("iidx") == "ziv_comment")
check("GiGO-style chunithm count is 12", counts.get("chunithm") == 12)
check("GiGO-style maimai_dx count is 3", counts.get("maimai_dx") == 3)
check("GiGO-style sdvx count is 8", counts.get("sdvx") == 8)
check("bare popn is ziv_listed 1",
      counts.get("popn") == 1 and evidence.get("popn") == "ziv_listed")
check("bare jubeat is ziv_listed 1",
      counts.get("jubeat") == 1 and evidence.get("jubeat") == "ziv_listed")
check("non-rhythm Time Crisis is not counted", "other" not in counts
      and "time_crisis" not in counts)
check("iidx_lm cab model is 8", cab_models.get("iidx_lm") == 8,
      repr(cab_models))
# Deliberately NOT 8, and the contrast with iidx_lm above is the whole rule.
# The Lightning row's comment says "8 LIGHTNING MODEL machines", which names
# the cabinet model, so 8 is that model's number. The Valkyrie row's comment
# says only "8 machines", which counts the venue's SDVX cabinets - some of
# which are Valkyrie and some of which are not. Taking it anyway is what made
# Round1 Ikebukuro print "VALKYRIE x11" from one cabinet, and left 230 of 317
# numbered pills byte-identical to their parent game's count.
check("sdvx_vm gets no number from a comment that does not name it",
      cab_models.get("sdvx_vm") == 1, repr(cab_models))

# Mixed: one entry with comment qty, one without for the same slug.
counts2, evidence2, _ = ziv._counts_and_evidence_for_machines([
    ("DanceDanceRevolution WORLD (20th anniversary model)", 1, "2x"),
    ("DanceDanceRevolution WORLD", 1, None),
])
check("mixed comment+listed sums 2+1=3", counts2.get("ddr") == 3,
      repr(counts2))
check("mixed still ziv_comment", evidence2.get("ddr") == "ziv_comment")
check("ddr_gold variant from 20th anniv title",
      ziv.cab_variants_for_title(
          "DanceDanceRevolution WORLD (20th anniversary model)")
      == {"ddr_gold"})


# two bare entries of same slug => listed lower bound 2
counts3, evidence3, _ = ziv._counts_and_evidence_for_machines([
    ("DANCERUSH STARDOM", 694, None),
    ("DANCERUSH STARDOM", 694, ""),
])
check("two bare list entries => ziv_listed 2",
      counts3.get("drs") == 2 and evidence3.get("drs") == "ziv_listed")


# ------------------------------------------------------ maimai classic/DX
print("\n--- maimai classic vs DX slug split ---")

check("maimai FiNALE -> classic",
      ziv.slugs_for_title("maimai FiNALE") == {"maimai"})
check("maimai (bare) -> classic",
      ziv.slugs_for_title("maimai") == {"maimai"})
check("maimaiPLUS -> classic",
      ziv.slugs_for_title("maimaiPLUS") == {"maimai"})
check("maimai ORANGE -> classic",
      ziv.slugs_for_title("maimai ORANGE") == {"maimai"})
check("maimai でらっくす CiRCLE PLUS -> dx",
      ziv.slugs_for_title("maimai でらっくす CiRCLE PLUS") == {"maimai_dx"})
check("maimai DX CiRCLE -> dx",
      ziv.slugs_for_title("maimai DX CiRCLE") == {"maimai_dx"})
check("舞萌DX 2026 (maimai DX PRiSM PLUS) contains both tokens; DX fires",
      "maimai_dx" in ziv.slugs_for_title(
          "舞萌DX 2026 (maimai DX PRiSM PLUS)"))
check("seriesID 284 + classic title stays classic",
      ziv._machine_slugs("maimai FiNALE", 284) == {"maimai"})
check("seriesID 284 + DX title is dx",
      ziv._machine_slugs("maimai でらっくす PRiSM PLUS", 284)
      == {"maimai_dx"})


# ------------------------------------------------------ cab variants
print("\n--- cab_variants_for_title ---")

check("IIDX Lightning",
      ziv.cab_variants_for_title(
          "beatmania IIDX 33 Sparkle Shower (LIGHTNING MODEL)")
      == {"iidx_lm"})
check("IIDX bare is NOT Lightning",
      ziv.cab_variants_for_title("beatmania IIDX 33 Sparkle Shower")
      == set())
check("SDVX Valkyrie",
      ziv.cab_variants_for_title(
          "SOUND VOLTEX EXCEED GEAR (Valkyrie model)")
      == {"sdvx_vm"})
check("SDVX NEMSYS",
      ziv.cab_variants_for_title(
          "SOUND VOLTEX EXCEED GEAR (NEMSYS model)")
      == {"sdvx_nemsys"})
check("DDR 20th anniv gold",
      ziv.cab_variants_for_title(
          "DanceDanceRevolution WORLD (20th anniversary model)")
      == {"ddr_gold"})
check("DDR Universal",
      ziv.cab_variants_for_title(
          "DanceDanceRevolution A3 (Universal model)")
      == {"ddr_universal"})
check("DDR bare WORLD is unknown (not white)",
      ziv.cab_variants_for_title("DanceDanceRevolution WORLD") == set())
check("DDR SuperNOVA legacy",
      "ddr_legacy" in ziv.cab_variants_for_title(
          "DanceDanceRevolution SuperNOVA"))
check("DDR Solo legacy",
      "ddr_legacy" in ziv.cab_variants_for_title(
          "Dance Dance Revolution Solo 2000"))
check("taiko asia fullwidth paren",
      ziv.cab_variants_for_title("太鼓の達人 ニジイロVer.（アシア版）")
      == {"taiko_asia"}
      or ziv.cab_variants_for_title("太鼓の達人 ニジイロVer.(アシア版）")
      == {"taiko_asia"})
check("taiko jp bare nijiiro",
      ziv.cab_variants_for_title("太鼓の達人 ニジイロVer.") == {"taiko_jp"})


# ------------------------------------------------------ promoted slugs
print("\n--- promoted game slugs (out of other) ---")

for title, want in [
        ("Pump It Up Phoenix", "pump_it_up"),
        ("StepManiaX (65\" Deluxe Cabinet)", "stepmaniax"),
        ("WACCA REVERSE", "wacca"),
        ("华卡音舞", "wacca"),
        ("Groove Coaster 4MAX: Diamond Galaxy", "groove_coaster"),
        ("crossbeats REV. Sunrise", "crossbeats"),
        ("BeatStream", "beatstream"),
]:
    check("%s -> %s" % (title, want),
          want in ziv.slugs_for_title(title),
          repr(sorted(ziv.slugs_for_title(title))))


# ---------------------------------------- signed / range quantities
# A leading hyphen used to be stripped and the magnitude published, so
# "-1 machines" became a confident 1, and a stated RANGE lost its lower
# half ("1-2 machines" -> 2). Both are claims the comment does not make.
print("\n--- signed and range quantities are not counts ---")

for text in ["-1 machines", "-3 cabs", "there are -2 machines",
             "1-2 machines", "2-4 cabinets", "-2 台"]:
    check("%r yields no count" % text,
          ziv.parse_machine_quantity(text) is None,
          repr(ziv.parse_machine_quantity(text)))

# The same sweep must not cost any real total: hyphens appear in ordinary
# cab prose ("side-by-side"), and those still have to parse.
for text, want in [("2 machines", 2), ("8 machines", 8),
                   ("12 cabinets in total", 12), ("there are 5 machines", 5),
                   ("3 台設置", 3), ("8 LIGHTNING MODEL machines", 8),
                   ("2 sets of 4", 8),
                   ("a side-by-side pair of 4 linked cabinets", 8)]:
    check("%r still parses as %d" % (text, want),
          ziv.parse_machine_quantity(text) == want,
          repr(ziv.parse_machine_quantity(text)))


# ------------------------------------------- zero is a real coordinate
# lat/lng were read with `or`, which treats 0.0 as absent: a venue on the
# equator or the prime meridian lost that axis. Ghana sits on both.
print("\n--- 0.0 lat/lng survives parsing ---")

for lat, lng in [(0, 10), (10, 0), (0, 0)]:
    got = ziv._parse_arcades(
        {"arcades": [{"id": "1", "name": "Equator Arcade",
                      "latitude": lat, "longitude": lng}]}, "Ghana")["1"]
    check("lat=%r lng=%r kept as a coordinate" % (lat, lng),
          got["lat"] == float(lat) and got["lng"] == float(lng),
          "got lat=%r lng=%r" % (got["lat"], got["lng"]))

# A genuinely absent axis must still read as absent, not as 0.
_absent = ziv._parse_arcades(
    {"arcades": [{"id": "1", "name": "No Coords", "latitude": None,
                  "longitude": None}]}, "Ghana")["1"]
check("missing lat/lng stays None",
      _absent["lat"] is None and _absent["lng"] is None,
      "got lat=%r lng=%r" % (_absent["lat"], _absent["lng"]))


# ------------------------------------------------------ end
print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
if FAILED:
    print("FAILURES:")
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL PASS")
