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

import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Fields safe to apply as-is once the venue is unambiguously identified.
MECHANICAL = ("hours", "website")
# Applied, but only after validation against the game slug vocabulary,
# the country box, or - for coordinates - independent geographic proof.
VALIDATED = ("games", "game_counts", "location", "status")
# Deliberately NOT applied - see module docstring.
HELD = ("cab_models", "prices", "other", "missing_venue", "images")

# A permanently-closed venue still shown as open is the worst failure
# this map has, because somebody travels to it. But "status" is also the
# field the fleet writes merge proposals and vague notes into, so only a
# plain statement of permanent closure counts, and only from a source
# that is not the community listing the row already came from.
_CLOSED_RE = re.compile(
    r"permanently closed|closed (?:down|for good|permanently)"
    r"|no longer (?:open|in (?:business|operation))|ceased trading"
    r"|out of business|已(?:关闭|停业)|停止营业",
    re.I)
# Temporary states that must NOT be read as closure: a venue being
# refurbished, relocated, or merely offline is still a real venue.
_NOT_CLOSED_RE = re.compile(
    r"reopen|re-open|renovat|refurbish|装修中|筹备|搬迁|temporar"
    r"|network offline|已断网|离线|merge_into|duplicate",
    re.I)

# A coordinate correction must move the pin INTO the place its own
# address names, and by a margin that is not measurement noise. Several
# proposals are confidently wrong in the other direction, so the fleet's
# "certain" is not sufficient on its own.
LOCATION_MIN_GAIN_M = 2000.0

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


_COMMUNITY_HOSTS = ("zenius-i-vanisher.com", "bemanicn.com")


def _host(url):
    m = re.match(r"https?://([^/]+)", str(url or ""), re.I)
    return m.group(1).lower().replace("www.", "") if m else ""


def _is_community_host(host):
    return any(host == h or host.endswith("." + h)
               for h in _COMMUNITY_HOSTS)


def load_places(data_dir):
    """[(name, lat, lng, depth)] of admin areas, for judging coordinates.

    Currently China only (data/china_areas.json, 3,257 districts), which
    is also where most bad pins are. Absent file -> empty list, and every
    coordinate correction then falls back to the country-box test alone.
    """
    path = os.path.join(data_dir, "china_areas.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            areas = json.load(fh).get("areas") or {}
    except (OSError, ValueError):
        return []
    out = []
    for rec in areas.values():
        if rec.get("lat") is not None and len(rec.get("n") or "") >= 3:
            out.append((rec["n"], rec["lat"], rec["lng"], rec.get("d", 0)))
    return out


def _location_ok(arcade, proposed, places, merge_mod):
    """(accept, reason) for one coordinate proposal.

    Two independent checks, because the fleet's confidence is not
    evidence: several "certain" proposals move a pin into the wrong
    COUNTRY, and several others move it further from the district the
    arcade's own address names.
    """
    try:
        lat = float(proposed["lat"])
        lng = float(proposed["lng"])
    except (TypeError, ValueError, KeyError):
        return False, "not_numeric"
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return False, "out_of_range"
    box = merge_mod.bbox_country(lat, lng)
    if box and arcade.get("country") and box != arcade["country"]:
        return False, "wrong_country"
    # Find the deepest admin area this arcade's own address names, and
    # require the proposal to land nearer to it than the current pin.
    hay = (arcade.get("addr") or "") + (arcade.get("name") or "")
    best = None
    for name, plat, plng, depth in places:
        if name in hay and (best is None or depth > best[3]):
            best = (name, plat, plng, depth)
    if best is None:
        # Nothing to check against. Accept only when the arcade has no
        # pin at all, where any plausible coordinate beats none - or
        # when the pin already IS this proposal, which means a previous
        # build applied it and dropping it now would revert the fix.
        if arcade.get("lat") is None:
            return True, "fills_a_gap"
        if merge_mod.haversine_m(lat, lng,
                                 arcade["lat"], arcade["lng"]) < 25.0:
            return True, "already_applied"
        return False, "unjudgeable"
    d_new = merge_mod.haversine_m(lat, lng, best[1], best[2])
    if arcade.get("lat") is None:
        return True, "fills_a_gap"
    # The arcade's CURRENT pin may already be this proposal, because
    # arcades.json is the output of the previous build - the overlay put
    # it there. Dropping it then would un-apply the fix on the next
    # rebuild, which is the same self-erasing bug the no_change filter
    # had. An already-applied coordinate stays applied.
    if merge_mod.haversine_m(lat, lng,
                             arcade["lat"], arcade["lng"]) < 25.0:
        return True, "already_applied"
    d_old = merge_mod.haversine_m(arcade["lat"], arcade["lng"],
                                  best[1], best[2])
    if d_old - d_new < LOCATION_MIN_GAIN_M:
        return False, "no_geographic_gain"
    return True, "closer_to_named_district"


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


def build(raw_dir, arcades, game_slugs, places=None, merge_mod=None):
    if merge_mod is None:
        sys.path.insert(0, HERE)
        import merge as merge_mod       # noqa: F811
    places = [] if places is None else places
    shards = sorted(glob.glob(os.path.join(
        raw_dir, "verify", "corrections", "shard_*.json")))
    by_key, by_name = _index(arcades)
    out = {}
    stats = collections.Counter({
        "shards": len(shards), "proposals": 0, "applied": 0,
        "held_field": 0, "unresolved": 0, "no_change": 0,
        "counts_without_quantity": 0, "unverified": 0, "bad_slug": 0})
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
            elif field == "status":
                blob = "%s %s" % (proposed, corr.get("note") or "")
                if not _CLOSED_RE.search(blob):
                    stats["status_not_a_closure"] += 1
                    continue
                if _NOT_CLOSED_RE.search(blob):
                    # "closed for renovation, reopening October" is not
                    # a closure, and neither is a merge proposal that
                    # happens to use the word.
                    stats["status_temporary"] += 1
                    continue
                if corr.get("confidence") != "certain":
                    stats["status_not_certain"] += 1
                    continue
                # The evidence must not be the same community listing the
                # row already came from - that is not corroboration.
                host = _host(corr.get("evidence_url"))
                if _is_community_host(host):
                    stats["status_community_evidence"] += 1
                    continue
                value = {"closed": True,
                         "reason": str(proposed)[:200]}
            elif field == "location":
                ok, why = _location_ok(arcade, proposed, places, merge_mod)
                if not ok:
                    stats["location_" + why] += 1
                    continue
                value = {"lat": float(proposed["lat"]),
                         "lng": float(proposed["lng"])}
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
                       set(merge_mod.GAME_SLUGS),
                       places=load_places(data_dir), merge_mod=merge_mod)
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
