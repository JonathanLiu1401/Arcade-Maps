"""Named-venue ground truth for cab counts.

Aggregate checks cannot catch a fabricated quantity. This file shipped a panel
that printed "CHUNITHM x1 listed" for GiGO's nine-floor Ikebukuro flagship,
and every summary statistic looked healthy while it did, because the count was
present and well-formed - it was simply not true. So the guard is a handful of
venues whose real inventory is known from the source, asserted by name.

The numbers below are read off the live ZIv machine list for each venue:
an explicit contributor comment ("6x", "8x") is a real quantity, and a title
that appears N times is N cabinets. Both are recorded here. If a scraper
change or a merge-policy change moves one of these, that is a regression in
the data, not in the test - go and look at the venue before editing a number.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# ziv arcade id -> {slug: (count, evidence)}
# evidence "ziv_comment" = a human wrote the quantity down, authoritative.
# evidence "ziv_listed"  = N distinct machine rows, a floor rather than a total.
GROUND_TRUTH = {
    "7530": {                       # GiGO Head Arcade (GiGO総本店), Ikebukuro
        "maimai_dx": (6, "ziv_comment"),      # comment "6x"
        "ongeki": (6, "ziv_comment"),         # comment "6x"
        "polaris_chord": (8, "ziv_comment"),  # comment "8x"
        "ddr": (3, "ziv_listed"),             # 3 x DDR WORLD 20th anniv rows
        "gitadora": (2, "ziv_listed"),        # GuitarFreaks + DrumMania
    },
}


def load_arcades():
    path = os.path.join(ROOT, "data", "arcades.json")
    if not os.path.exists(path):
        return None          # fresh clone, pipeline has not run yet
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["arcades"]


def by_ziv_id(arcades):
    out = {}
    for a in arcades:
        url = (a.get("links") or {}).get("ziv")
        if not url:
            continue
        marker = "id="
        i = str(url).rfind(marker)
        if i != -1:
            out[str(url)[i + len(marker):]] = a
    return out


def main():
    arcades = load_arcades()
    if arcades is None:
        # Skip rather than fail: this asserts against BUILT data, so on a
        # fresh clone there is nothing to be right or wrong about yet.
        print("SKIP (no data/arcades.json - run the pipeline first)")
        return 0
    index = by_ziv_id(arcades)
    failures = []

    for ziv_id, expected in GROUND_TRUTH.items():
        a = index.get(ziv_id)
        if a is None:
            failures.append("ziv id %s is not in arcades.json at all" % ziv_id)
            continue
        counts = a.get("game_counts") or {}
        evidence = a.get("count_evidence") or {}
        for slug, (want_n, want_ev) in expected.items():
            got_n = counts.get(slug)
            got_ev = evidence.get(slug)
            if got_n != want_n:
                failures.append(
                    "%s (%s): %s count is %r, expected %r"
                    % (a.get("name"), ziv_id, slug, got_n, want_n))
            if got_ev != want_ev:
                failures.append(
                    "%s (%s): %s evidence is %r, expected %r"
                    % (a.get("name"), ziv_id, slug, got_ev, want_ev))

    # The rule that the fabricated "x1" violated: a lone ZIv machine row is
    # evidence the game is present, never evidence of how many cabinets there
    # are. Such a count may exist in the data (it is a truthful floor of one
    # listing) but the frontend must not print it, and js/state.js
    # countIsShowable is what enforces that. Assert the shape the frontend
    # depends on, so a scraper change cannot quietly start claiming totals.
    bad_evidence = set()
    for a in arcades:
        for slug, ev in (a.get("count_evidence") or {}).items():
            if ev not in ("ziv_comment", "ziv_listed", "bemanicn_qty"):
                bad_evidence.add(ev)
    if bad_evidence:
        failures.append("unknown count_evidence values: %s"
                        % sorted(bad_evidence))

    if failures:
        print("FAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("ALL PASS (%d venues, %d assertions)"
          % (len(GROUND_TRUTH),
             sum(len(v) * 2 for v in GROUND_TRUTH.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
