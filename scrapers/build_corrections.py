"""Turn the verification fleet's shard reports into a reviewable overlay.

The fleet (data_raw/verify/corrections/shard_*.json) researches each
arcade against live sources and proposes corrections with an evidence
url and quote. This script filters those proposals down to the ones that
are safe to apply mechanically and writes data/corrections.json, which
merge.py applies to built entries.

Two rules do most of the work here, and both exist because a plausible
correction is not the same as a true one:

  * A COUNT is only a count when the evidence QUOTES a quantity.
    Measured over the fleet's own output: 202 of 282 game_counts
    proposals quote no number at all - they are the agent counting rows
    on a ZIv page, which is the placeholder tier that produced the "x1
    everywhere" bug. Row-counting is recorded as ziv_listed (renders no
    number), never as a published quantity.

  * Free-text fields are NOT applied. cab_models is {slug: int|None}
    validated against CAB_MODEL_SLUGS, and the fleet writes prose into
    it ("DX PRiSM PLUS (x3)", "controller/sim (maimoller)"); prices is a
    measured per-country table built by prices.py. Both need a
    translation step that does not exist yet, so they are held rather
    than half-applied.

Entries are keyed on the venue's SOURCE PAGE url where it has one, and
on (country, name, addr) otherwise. Never on the arcade id: merge
reassigns ids 1..N every build, and using an id as a key has already put
3,138 photos and two hand-researched coordinates on the wrong venues.
The key is also always the ORIGINAL name/addr, never the corrected
value, so re-running the pipeline does not stop the overlay matching
itself.

For the same reason this script does NOT skip proposals that match the
current data. It reads data/arcades.json, which is the ALREADY-CORRECTED
output of the previous build, so "the value is already right" usually
means "the overlay put it there". Dropping those would shrink the
overlay on every rebuild until the corrections silently reverted.
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Fields safe to apply as-is once the venue is unambiguously identified.
MECHANICAL = ("hours", "website")
# Applied, but only after validation against the game slug vocabulary.
VALIDATED = ("games", "game_counts")
# Deliberately NOT applied - see module docstring.
HELD = ("cab_models", "prices", "other", "missing_venue", "status",
        "location", "images")

# A quantity in the evidence: "4 cabinets", "(x2)", "12 machines", "3台".
_QTY_RE = re.compile(
    r"\b\d+\s*(?:machines?|cabs?|cabinets?|units?|seats?)\b"
    r"|\b(?:machines?|cabs?|cabinets?)\s*[:\-]?\s*\d+"
    r"|\(\s*[x×]\s*\d+\s*\)"
    r"|\b[x×]\s*\d+\b"
    r"|\d+\s*(?:台|個|台数)",
    re.I)


def quotes_a_quantity(quote):
    return bool(_QTY_RE.search(quote or ""))


def venue_key(arcade):
    """Stable identity for one arcade. Source page first, address last."""
    links = arcade.get("links") or {}
    for src in ("ziv", "bemanicn"):
        if links.get(src):
            return src + "|" + links[src]
    return "addr|%s|%s|%s" % (arcade.get("country") or "",
                              (arcade.get("name") or "").strip(),
                              (arcade.get("addr") or "").strip())


def _index(arcades):
    """{key: arcade}, plus a name index used only when it is unambiguous."""
    by_key = {}
    by_name = {}
    for a in arcades:
        by_key[venue_key(a)] = a
        by_name.setdefault((a.get("country"), a.get("name")), []).append(a)
    return by_key, by_name


def resolve(corr, arcades, by_key, by_name):
    """The arcade a correction refers to, or None when ambiguous.

    Ambiguity is a refusal, not a coin flip: writing a correction to the
    wrong one of two same-named venues is exactly the failure the id
    joins produced twice.
    """
    cur = corr.get("current") if isinstance(corr.get("current"), dict) else {}
    name = (corr.get("name") or cur.get("name") or "").strip()
    if not name:
        return None
    addr = (cur.get("addr") or "").strip()
    exact = [a for a in arcades
             if a.get("name") == name and (a.get("addr") or "").strip() == addr]
    if len(exact) == 1:
        return exact[0]
    for country_name, rows in by_name.items():
        if country_name[1] == name and len(rows) == 1:
            return rows[0]
    return None


def build(raw_dir, arcades, game_slugs):
    shards = sorted(glob.glob(os.path.join(
        raw_dir, "verify", "corrections", "shard_*.json")))
    by_key, by_name = _index(arcades)
    out = {}
    stats = {"shards": len(shards), "proposals": 0, "applied": 0,
             "held_field": 0, "unresolved": 0, "no_change": 0,
             "counts_without_quantity": 0, "unverified": 0,
             "bad_slug": 0}
    for path in shards:
        try:
            with open(path, encoding="utf-8") as fh:
                shard = json.load(fh)
        except (OSError, ValueError):
            continue
        for corr in (shard.get("corrections") or []):
            if not isinstance(corr, dict):
                continue
            stats["proposals"] += 1
            field = corr.get("field")
            if field in HELD or field not in (MECHANICAL + VALIDATED):
                stats["held_field"] += 1
                continue
            if corr.get("confidence") == "unverified":
                stats["unverified"] += 1
                continue
            if not corr.get("evidence_url"):
                stats["unverified"] += 1
                continue
            arcade = resolve(corr, arcades, by_key, by_name)
            if arcade is None:
                stats["unresolved"] += 1
                continue
            proposed = corr.get("proposed")
            if field == "games":
                if not isinstance(proposed, list):
                    stats["held_field"] += 1
                    continue
                games = sorted({g for g in proposed if g in game_slugs})
                if not games:
                    stats["bad_slug"] += 1
                    continue
                value = games
            elif field == "game_counts":
                if not isinstance(proposed, dict):
                    stats["held_field"] += 1
                    continue
                # A count is a count only when a human wrote the number.
                if not quotes_a_quantity(corr.get("evidence_quote")):
                    stats["counts_without_quantity"] += 1
                    continue
                counts = {k: v for k, v in proposed.items()
                          if k in game_slugs and isinstance(v, int) and v > 0}
                if not counts:
                    stats["bad_slug"] += 1
                    continue
                value = counts
            else:
                if not isinstance(proposed, str) or not proposed.strip():
                    stats["held_field"] += 1
                    continue
                value = proposed.strip()
            key = venue_key(arcade)
            rec = out.setdefault(key, {"name": arcade.get("name"),
                                       "fields": {}})
            rec["fields"][field] = {
                "value": value,
                "evidence_url": corr.get("evidence_url"),
                "evidence_quote": (corr.get("evidence_quote") or "")[:400],
                "confidence": corr.get("confidence"),
                "checked_at": corr.get("checked_at"),
            }
            stats["applied"] += 1
    return out, stats


def main():
    sys.path.insert(0, HERE)
    import merge as merge_mod

    data_dir = os.path.join(ROOT, "data")
    with open(os.path.join(data_dir, "arcades.json"), encoding="utf-8") as fh:
        arcades = json.load(fh)["arcades"]
    out, stats = build(os.path.join(ROOT, "data_raw"), arcades,
                       set(merge_mod.GAME_SLUGS))
    dest = os.path.join(data_dir, "corrections.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump({"venues": out, "stats": stats}, fh,
                  ensure_ascii=False, indent=1, sort_keys=True)
    print("build_corrections: %d shards, %d proposals -> %d applied "
          "across %d venues" % (stats["shards"], stats["proposals"],
                                stats["applied"], len(out)))
    for k in sorted(stats):
        if k not in ("shards", "proposals", "applied"):
            print("  %-26s %d" % (k, stats[k]))


if __name__ == "__main__":
    main()
