#!/usr/bin/env python3
"""Refuse to commit a freshly built dataset that lost a lot of ground.

WHY THIS EXISTS

The weekly Action scrapes, rebuilds `data/`, commits to `main`, and GitHub
Pages serves the result minutes later. There is no human between a bad crawl
and the live map. The existing guards are per-source and per-country and catch
the loud failures well: `run_all.py` dies when a source returns nothing, and it
dies when any configured ZIv country returns zero arcades, which is how a
drifted country spelling gets caught.

What none of them catch is a QUIET shrink. A source that answers every request
but returns a third of its usual rows, an upstream that starts paginating and
silently truncates, a parser that stops matching after a markup change: each of
those produces a smaller, perfectly well-formed dataset that sails through
every existing check and overwrites good data on `main`.

This compares what was just built against what is already committed and exits
nonzero when the drop is too large to be plausible, so the Action fails with
nothing committed and last week's data stays live.

WHAT IT DOES NOT DO

It does not judge whether the new data is CORRECT, only whether it is
suspiciously smaller. Growth is never blocked. An arcade genuinely closing is
normal; a fifth of Japan vanishing in a week is not.

USAGE

    python3 scrapers/guard_regression.py                    # compare vs HEAD
    python3 scrapers/guard_regression.py --baseline old.json
    python3 scrapers/guard_regression.py --force            # log and pass

Thresholds are deliberately loose. They exist to catch a collapse, not to
police week-to-week churn, and a false alarm costs one re-run while a missed
collapse ships to every visitor.

Stdlib only, same rule as the rest of scrapers/.
"""

import argparse
import json
import os
import subprocess
import sys

DEFAULT_DATA = os.path.join("data", "arcades.json")

# A drop bigger than this fails the run. Per-source is looser than the total
# because one source moving is normal churn, while the total moving that far
# means several went at once.
TOTAL_DROP_PCT = 5.0
SOURCE_DROP_PCT = 25.0
# Below this many rows a percentage is noise, so only vanishing matters.
SMALL_SOURCE = 50


def counts(blob):
    """(total, {source: n}) from an arcades.json payload."""
    arcades = blob.get("arcades") or []
    by_source = {}
    for a in arcades:
        for s in (a.get("src") or []):
            by_source[s] = by_source.get(s, 0) + 1
    return len(arcades), by_source


def load_committed(path):
    """The version of `path` in HEAD, or None when there is no baseline."""
    try:
        out = subprocess.run(
            ["git", "show", "HEAD:%s" % path.replace(os.sep, "/")],
            capture_output=True, check=True)
        return json.loads(out.stdout)
    except (subprocess.CalledProcessError, ValueError):
        return None


def pct_drop(old, new):
    if old <= 0:
        return 0.0
    return 100.0 * (old - new) / float(old)


def row_count(blob):
    """Rows in a data_raw payload, which is a list in every current file."""
    if isinstance(blob, list):
        return len(blob)
    if isinstance(blob, dict):
        for key in ("rows", "arcades", "stores", "items"):
            if isinstance(blob.get(key), list):
                return len(blob[key])
    return None


def ziv_countries(blob):
    if not isinstance(blob, list):
        return None
    return {r.get("country") for r in blob if isinstance(r, dict)}


def check_raw(raw_dir, source_drop, problems):
    """Compare every committed data_raw file against the rebuilt one.

    This is the check that actually bites. The merged arcade count is a poor
    proxy for crawl health: dedupe folds most community rows into official
    entries, so losing 2,119 raw ZIv rows (a 30% collapse, 42 countries gone)
    moved the merged total by only 0.5% and slipped under every threshold
    above. The raw layer is where a quiet shrink is visible, so it is checked
    on its own terms.
    """
    listing = subprocess.run(
        ["git", "ls-tree", "--name-only", "HEAD", raw_dir + "/"],
        capture_output=True, text=True)
    committed = [p for p in listing.stdout.split("\n") if p.endswith(".json")]
    if not committed:
        print("guard: no committed %s baseline, skipping raw checks" % raw_dir)
        return

    print("\nguard: raw source files")
    for path in sorted(committed):
        try:
            out = subprocess.run(["git", "show", "HEAD:%s" % path],
                                 capture_output=True, check=True)
            old_rows = row_count(json.loads(out.stdout))
        except (subprocess.CalledProcessError, ValueError):
            continue
        local = os.path.join(*path.split("/"))
        if not os.path.exists(local):
            problems.append("raw file %s disappeared from the build" % path)
            continue
        try:
            with open(local, "r", encoding="utf-8") as fh:
                new_blob = json.load(fh)
        except ValueError:
            problems.append("raw file %s is not valid JSON after the build" % path)
            continue
        new_rows = row_count(new_blob)
        if old_rows is None or new_rows is None:
            continue

        d = pct_drop(old_rows, new_rows)
        flag = "  (%+.1f%%)" % -d
        print("       %-34s %7s -> %-7s%s"
              % (os.path.basename(path), "{:,}".format(old_rows),
                 "{:,}".format(new_rows), flag))
        # A file that still parses but holds nothing is a total loss whatever
        # its size, so it is refused before the percentage rule gets a say.
        # SMALL_SOURCE exists because a percentage of a handful of rows is
        # noise - but it was also letting a SMALL file go to zero unremarked:
        # museca ships 6 rows and dance_evo 12, so both could be emptied by a
        # broken parser and still sail through as "too small to judge". The
        # existing disappearance check does not cover it either, since the file
        # is still on disk and still valid JSON. Vanishing coverage is exactly
        # what this guard is for, and it is the one judgement that does not
        # need a threshold.
        if old_rows > 0 and new_rows == 0:
            problems.append("raw %s is empty after the build (was %s rows)"
                            % (path, "{:,}".format(old_rows)))
        elif old_rows >= SMALL_SOURCE and d > source_drop:
            problems.append("raw %s fell %.1f%% (%s -> %s rows), limit %.1f%%"
                            % (path, d, "{:,}".format(old_rows),
                               "{:,}".format(new_rows), source_drop))

        # ZIv is queried country by country, so coverage is the sharpest
        # signal it has: rows can drift, a whole country going missing cannot.
        if os.path.basename(path) == "ziv.json":
            try:
                old_c = ziv_countries(json.loads(
                    subprocess.run(["git", "show", "HEAD:%s" % path],
                                   capture_output=True, check=True).stdout))
                new_c = ziv_countries(new_blob)
            except (subprocess.CalledProcessError, ValueError):
                old_c = new_c = None
            if old_c and new_c is not None:
                lost = sorted(c for c in old_c - new_c if c)
                print("       %-34s %7d -> %-7d  countries"
                      % ("ziv country coverage", len(old_c), len(new_c)))
                if lost:
                    problems.append(
                        "ZIv lost %d of %d countries entirely: %s%s"
                        % (len(lost), len(old_c), ", ".join(lost[:8]),
                           " ..." if len(lost) > 8 else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=DEFAULT_DATA,
                    help="freshly built arcades.json (default: %s)" % DEFAULT_DATA)
    ap.add_argument("--baseline",
                    help="compare against this file instead of the committed version")
    # argparse percent-expands help text itself, so a literal percent sign has
    # to survive as "%%" all the way into add_argument. Interpolating with the
    # % operator here collapsed it to a single "%" first, and argparse then read
    # "% d" (from "% drop") as an int conversion: TypeError, re-raised by
    # Python 3.14 as "badly formed help string" at add_argument time, which
    # made the whole regression gate unrunnable on 3.14 and broke --help
    # everywhere. .format() fills the default without touching the percent.
    ap.add_argument("--total-drop", type=float, default=TOTAL_DROP_PCT,
                    help="max tolerated %% drop in total arcades "
                         "(default: {:.1f})".format(TOTAL_DROP_PCT))
    ap.add_argument("--source-drop", type=float, default=SOURCE_DROP_PCT,
                    help="max tolerated %% drop per source "
                         "(default: {:.1f})".format(SOURCE_DROP_PCT))
    ap.add_argument("--raw-dir", default="data_raw",
                    help="per-source raw directory to check (default: data_raw)")
    ap.add_argument("--skip-raw", action="store_true",
                    help="only check the merged dataset")
    ap.add_argument("--force", action="store_true",
                    help="report findings but exit 0 (intentional shrink)")
    args = ap.parse_args()

    if not os.path.exists(args.data):
        sys.stderr.write("guard: %s does not exist - did the build run?\n" % args.data)
        return 2
    with open(args.data, "r", encoding="utf-8") as fh:
        new_blob = json.load(fh)

    if args.baseline:
        with open(args.baseline, "r", encoding="utf-8") as fh:
            old_blob = json.load(fh)
    else:
        old_blob = load_committed(args.data)

    new_total, new_src = counts(new_blob)

    if old_blob is None:
        print("guard: no committed baseline for %s, nothing to compare "
              "(new build has %s arcades)" % (args.data, "{:,}".format(new_total)))
        return 0

    old_total, old_src = counts(old_blob)
    problems = []

    drop = pct_drop(old_total, new_total)
    if drop > args.total_drop:
        problems.append(
            "total arcades fell %.1f%% (%s -> %s), limit %.1f%%"
            % (drop, "{:,}".format(old_total), "{:,}".format(new_total), args.total_drop))

    for src in sorted(old_src):
        was, now = old_src[src], new_src.get(src, 0)
        if now == 0:
            problems.append("source %r vanished entirely (was %s)"
                            % (src, "{:,}".format(was)))
            continue
        if was < SMALL_SOURCE:
            continue          # too small for a percentage to mean anything
        d = pct_drop(was, now)
        if d > args.source_drop:
            problems.append("source %r fell %.1f%% (%s -> %s), limit %.1f%%"
                            % (src, d, "{:,}".format(was), "{:,}".format(now),
                               args.source_drop))

    print("guard: total %s -> %s (%+.1f%%)"
          % ("{:,}".format(old_total), "{:,}".format(new_total), -drop))
    for src in sorted(set(old_src) | set(new_src)):
        was, now = old_src.get(src, 0), new_src.get(src, 0)
        flag = "" if was == 0 else "  (%+.1f%%)" % -pct_drop(was, now)
        print("       %-12s %7s -> %-7s%s"
              % (src, "{:,}".format(was), "{:,}".format(now), flag))

    if not args.skip_raw and not args.baseline:
        check_raw(args.raw_dir, args.source_drop, problems)

    if not problems:
        print("\nguard: no regression, safe to commit")
        return 0

    sys.stderr.write("\nguard: REFUSING to commit, the new build lost too much:\n")
    for p in problems:
        sys.stderr.write("  - %s\n" % p)
    sys.stderr.write(
        "\nNothing has been committed; the previously committed data is still live.\n"
        "If this shrink is real and intended, re-run with --force, or raise\n"
        "--total-drop / --source-drop for this run.\n")
    return 0 if args.force else 1


if __name__ == "__main__":
    sys.exit(main())
