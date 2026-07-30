#!/usr/bin/env python3
"""Run the China address geocode refresh, and report what it achieved.

``geocode_cn.run`` fills the cache. This wraps it with the two things a human
actually needs when deciding whether the run was any good:

  * a **before/after simulation** of what the next merge will do. It loads the
    built ``data/arcades.json``, throws away the coordinate on every China row
    that is only there because ``china_place`` guessed a centroid, replays
    ``geocode_cn.apply_cache`` over them, and counts distinct coordinates and
    the worst pile-up on both sides. That is the number the bug report was
    about - "30 arcades in one building" - and it is measurable without
    running merge. Running merge here would be wrong anyway: it rewrites
    arcades.json and merge_log.json, which this tool has no business touching.

  * a **precision-tier breakdown**, because a hit rate on its own is a lie.
    An "address"-level pin is the mall the address names; a "street" one is
    the road it is on; everything else stayed a centroid and is still flagged
    approximate. Only the first is what the owner asked for.

    python tools/refresh_china_geocode.py --limit 50      # try it out
    python tools/refresh_china_geocode.py                 # the full pass
    python tools/refresh_china_geocode.py --report-only   # no network at all
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scrapers"))

import china_place                                   # noqa: E402
import cn_address                                    # noqa: E402
import common                                        # noqa: E402
import geocode_cn                                    # noqa: E402


def eligible(arcades):
    """The rows this cache is allowed to move: China, not Taiwan, approximate.

    Exactly geocode_cn.addresses_for's guards, applied to entries rather than
    to addresses, because the simulation needs the rows themselves.
    """
    out = []
    for e in arcades:
        if (e.get("country") or "") not in china_place.PLACEABLE_COUNTRIES:
            continue
        if china_place.is_taiwan(e):
            continue
        if e.get("lat") is not None and not e.get("approx"):
            continue
        out.append(e)
    return out


def _shares_token(needle, haystack, k=3):
    """Loose containment: exact, or any k-character shingle in common.

    Chinese mall names vary between sources in ways that are not errors:
    ``龙之梦城市生活广场`` and ``龙之梦城市生活中心`` are the same building, and
    ``万达广场`` is printed as ``万达广场(沈阳全运店)``. An exact-substring test
    calls all of those wrong, so the comparison has to tolerate the suffix.
    """
    if not needle or not haystack:
        return False
    if needle in haystack:
        return True
    return any(needle[i:i + k] in haystack
               for i in range(max(1, len(needle) - k + 1)))


def audit_hits(cache):
    """Independent quality check on every cached hit. Returns a dict of counts.

    Neither number here is the hit rate, which is the statistic that lies:
    the keyless provider answers essentially everything, so "100% answered"
    would be true and meaningless. These are the two checks that can actually
    disagree with a returned coordinate, both run against the answer's OWN
    formatted address rather than against anything this module chose:

      * **landmark** - does the mall named in the address appear in the answer?
      * **road + number** - does the street number in the address match the
        street number in the answer?

    Both under-report. A mall whose entrance is on a different road than the
    address gives (very common) fails the road check while being exactly
    right, and a venue whose address names only its own trading name has no
    landmark to test. So these are floors on the accuracy, not estimates of
    it, and they are reported as such.
    """
    out = collections.Counter()
    disagreements = []
    for addr, rec in cache.items():
        if not isinstance(rec, dict) or rec.get("miss"):
            continue
        out["hits"] += 1
        got = rec.get("formatted") or ""
        cleaned = cn_address.strip_noise(addr)

        mark = cn_address.find_landmark(cleaned)
        if not mark:
            out["landmark_untestable"] += 1
        elif _shares_token(mark, got):
            out["landmark_ok"] += 1
        else:
            out["landmark_differs"] += 1

        road, num = cn_address.find_road(cleaned)
        groad, gnum = cn_address.find_road(got)
        if not (road and num and groad and gnum):
            out["road_untestable"] += 1
        elif num == gnum and (_shares_token(road, got)
                              or _shares_token(groad, addr)):
            out["road_ok"] += 1
        else:
            out["road_differs"] += 1
            disagreements.append((addr, "%s%s" % (road, num),
                                  "%s%s" % (groad, gnum), got))
    return out, disagreements


def stacked_hits(cache):
    """Cache hits sharing a coordinate. Returns (all stacks, suspect stacks).

    The distinct-coordinate count answers "did the centroid piles break up",
    which is the headline, and it is not the whole question. Two arcades in
    one mall SHOULD share a point - that is correct, and the owner would
    expect it: 天津南开大悦城 legitimately holds four of them.

    A stack is only flagged when the two addresses name buildings that do not
    look like each other at all, which is what a substitution looks like:
    ``南湖路3007号国贸广场(二期)`` answered with ``国贸商业大厦 南湖路3005号``,
    the mall next door on the same road in the same district. The area gate
    cannot see that by construction - it checks the city and never the street
    - so it is measured here and reported rather than folded into the distinct
    count.
    """
    by_point = collections.defaultdict(list)
    for addr, rec in cache.items():
        if not isinstance(rec, dict) or rec.get("miss"):
            continue
        by_point[(round(rec["lat"], 5), round(rec["lng"], 5))].append(
            (addr, rec))
    stacks = [v for v in by_point.values() if len(v) > 1]
    suspect = []
    for group in stacks:
        marks = []
        for addr, _rec in group:
            mark = cn_address.find_landmark(cn_address.strip_noise(addr))
            if mark:
                marks.append(mark)
        if len(marks) < 2:
            continue
        # Only suspect when NO pair of the names resembles any other, so
        # "万达广场" next to "四平万达广场" is not reported as a substitution.
        if any(_shares_token(a, b) or _shares_token(b, a)
               for i, a in enumerate(marks) for b in marks[i + 1:]):
            continue
        suspect.append((group, sorted(set(marks))))
    return stacks, suspect


def coord_stats(arcades):
    """(placed, distinct coordinates, worst pile-up) for a set of rows.

    Rounded to 5 dp (about a metre) before counting, which is what makes two
    rows on one centroid count as one point - the whole subject of the bug.
    """
    pts = collections.Counter()
    for e in arcades:
        if e.get("lat") is None or e.get("lng") is None:
            continue
        pts[(round(float(e["lat"]), 5), round(float(e["lng"]), 5))] += 1
    if not pts:
        return 0, 0, 0, None
    worst, n = pts.most_common(1)[0]
    return sum(pts.values()), len(pts), n, worst


def simulate(arcades_path, cache):
    """What the next merge will look like, without running merge.

    The rows are deep-copied and the centroid-derived coordinates stripped, so
    apply_cache sees the same coordinate-less rows merge hands it. Nothing on
    disk is touched.
    """
    blob = common.load_json(arcades_path)
    arcades = blob.get("arcades") or []
    china = [e for e in arcades
             if (e.get("country") or "") in china_place.PLACEABLE_COUNTRIES
             and not china_place.is_taiwan(e)]
    before = coord_stats(china)

    rows = [dict(e) for e in china]
    for e in rows:
        if e.get("approx"):
            e["lat"] = e["lng"] = None
            e.pop("approx", None)
            e.pop("approx_level", None)
    log = geocode_cn.apply_cache(rows, cache=cache)
    # china_place then places whatever the cache could not answer, exactly as
    # merge does, so the after-picture is the real one and not a cache-only
    # subset that would flatter the numbers.
    china_place.place_arcades(rows)
    after = coord_stats(rows)
    levels = collections.Counter(e.get("approx_level") for e in rows)
    return before, after, log, levels, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--limit", type=int, default=None,
                    help="max NEW addresses to geocode this run")
    ap.add_argument("--sleep", type=float, default=None)
    ap.add_argument("--provider", default=None)
    ap.add_argument("--report-only", action="store_true",
                    help="skip the network entirely; just report what the "
                         "committed cache already achieves")
    ap.add_argument("--reject-log", default=None)
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):    # pragma: no cover
            pass

    arcades_path = os.path.join(args.data, "arcades.json")
    blob = common.load_json(arcades_path)
    arcades = blob.get("arcades") or []
    rows = eligible(arcades)
    print("refresh: %d China rows eligible (of %d arcades)"
          % (len(rows), len(arcades)), file=sys.stderr)

    if args.report_only:
        cache = geocode_cn.load_cache(
            os.path.join(args.data, geocode_cn.OUTFILE))
    else:
        addresses, queries = geocode_cn.addresses_for(rows, with_queries=True)
        print("refresh: %d distinct qualified address(es)" % len(addresses),
              file=sys.stderr)
        rejections = []
        cache = geocode_cn.run(addresses, out_dir=args.data, limit=args.limit,
                               provider=args.provider, sleep=args.sleep,
                               queries=queries, reject_log=rejections)
        if args.reject_log and rejections:
            common.save_json(args.reject_log, rejections)
            print("refresh: %d rejection(s) -> %s"
                  % (len(rejections), args.reject_log), file=sys.stderr)

    resolved = {k: v for k, v in cache.items()
                if isinstance(v, dict) and not v.get("miss")}
    tiers = collections.Counter(v.get("precision") for v in resolved.values())
    print("\n=== cache ===")
    print("entries        %d" % len(cache))
    print("with coords    %d (%.1f%%)"
          % (len(resolved), 100.0 * len(resolved) / max(1, len(cache))))
    for tier, n in sorted(tiers.items(), key=lambda kv: -kv[1]):
        print("  %-10s %d" % (tier, n))

    before, after, log, levels, _rows = simulate(arcades_path, cache)
    print("\n=== China pins: what the next merge produces ===")
    print("               placed  distinct  worst pile-up")
    for label, s in (("before", before), ("after", after)):
        print("%-14s %6d  %8d  %d @ %s" % (label, s[0], s[1], s[2], s[3]))
    print("\ngeocode placed %d row(s) at a real address" % len(log))
    for level, n in sorted(levels.items(), key=lambda kv: -kv[1]):
        print("  approx_level %-9s %d" % (level, n))

    audit, disagreements = audit_hits(cache)
    print("\n=== independent quality audit (floors, not estimates) ===")

    def pct(ok, differs):
        total = ok + differs
        return (100.0 * ok / total) if total else 0.0

    print("landmark named in the address appears in the answer")
    print("  agree %d, differ %d, untestable %d  -> %.1f%% of testable"
          % (audit["landmark_ok"], audit["landmark_differs"],
             audit["landmark_untestable"],
             pct(audit["landmark_ok"], audit["landmark_differs"])))
    print("street number in the address matches the answer's")
    print("  agree %d, differ %d, untestable %d  -> %.1f%% of testable"
          % (audit["road_ok"], audit["road_differs"],
             audit["road_untestable"],
             pct(audit["road_ok"], audit["road_differs"])))
    for addr, want, got, formatted in disagreements[:5]:
        print("  number differs: %s vs %s" % (want, got))
        print("     %s" % addr[:70])
        print("  -> %s" % formatted[:70])

    # The residual the distinct count cannot show: hits that landed on top of
    # each other despite naming unrelated buildings.
    stacks, suspect = stacked_hits(cache)
    print("\n=== residual stacking among cache hits ===")
    print("coordinates shared by 2+ hits          %d" % len(stacks))
    print("  of those, the addresses name unrelated")
    print("  buildings (likely a substitution)      %d" % len(suspect))
    for group, marks in suspect[:6]:
        pt = (group[0][1]["lat"], group[0][1]["lng"])
        print("  %.5f,%.5f  %s" % (pt[0], pt[1], " vs ".join(marks)))
        for addr, rec in group:
            print("      %-44s -> %s" % (addr[:42], rec["formatted"][:42]))


if __name__ == "__main__":
    main()
