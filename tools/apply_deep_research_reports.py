# -*- coding: utf-8 -*-
"""Apply deep_research reports into owner_attested.json + live arcades.json.

Only confidence=certain findings with evidence_url are applied.
exclude removes the pin from arcades.json (and records owner_attested).
closed marks the pin; does not re-add already excluded venues.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scrapers"))
import build_corrections  # noqa: E402

REPORTS = ROOT / "data_raw" / "deep_research" / "reports"
OWNER = ROOT / "data" / "owner_attested.json"
ARCADES = ROOT / "data" / "arcades.json"
STATS = ROOT / "data" / "stats.json"

VALID_GAMES = {
    "maimai_dx", "chunithm", "ongeki", "project_diva", "sdvx", "iidx", "ddr",
    "polaris_chord", "gitadora", "jubeat", "popn", "nostalgia", "drs",
    "dance_around", "dance_evo", "museca", "reflec", "taiko", "wacca",
    "groove_coaster", "crossbeats", "beatstream", "pump_it_up", "stepmaniax",
    "other",
}


def load_reports():
    out = []
    if not REPORTS.exists():
        return out
    for p in sorted(REPORTS.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print("skip bad report", p.name, e)
            continue
        if not isinstance(d, dict):
            continue
        for f in d.get("findings") or []:
            if not isinstance(f, dict):
                continue
            f["_shard"] = d.get("shard")
            f["_file"] = p.name
            out.append(f)
    return out


def resolve_key(venues, arcade):
    for k in build_corrections.venue_keys(arcade):
        if k in venues:
            return k
    return build_corrections.venue_key(arcade)


def main() -> int:
    data = json.loads(ARCADES.read_text(encoding="utf-8"))
    arcades = data["arcades"]
    by_sid = {a.get("sid"): a for a in arcades if a.get("sid")}
    by_id = {a.get("id"): a for a in arcades}

    oa = json.loads(OWNER.read_text(encoding="utf-8"))
    venues = oa.setdefault("venues", {})

    stats = {
        "closed": 0, "exclude": 0, "add_games": 0, "remove_games": 0,
        "skip": 0, "patch_live": 0, "removed_live": 0,
    }
    exclude_sids = set()
    exclude_ids = set()

    for f in load_reports():
        if f.get("confidence") != "certain":
            stats["skip"] += 1
            continue
        if not f.get("evidence_url"):
            stats["skip"] += 1
            continue

        arcade = None
        if f.get("sid") and f["sid"] in by_sid:
            arcade = by_sid[f["sid"]]
        elif f.get("id") is not None and f["id"] in by_id:
            arcade = by_id[f["id"]]
        if not arcade:
            stats["skip"] += 1
            continue

        key = resolve_key(venues, arcade)
        existing = venues.get(key) or {}
        if existing.get("attested_by") == "owner" and (
                existing.get("exclude") or existing.get("closed")):
            stats["skip"] += 1
            continue
        # Never demote an exclude to closed
        if existing.get("exclude") and f.get("verdict") == "closed":
            stats["skip"] += 1
            continue

        verdict = f.get("verdict")
        rec = dict(existing)
        rec["name"] = f.get("name") or arcade.get("name")
        rec["attested_by"] = "research-fleet"
        rec["attested_at"] = f.get("checked_at") or "2026-08-04"
        rec["evidence_url"] = f.get("evidence_url")
        note = f.get("note") or f.get("evidence_quote") or ""
        if note:
            rec["note"] = ("deep-research fleet: " + note)[:900]

        if verdict == "exclude":
            rec["exclude"] = True
            rec.pop("closed", None)
            exclude_sids.add(arcade.get("sid"))
            exclude_ids.add(arcade.get("id"))
            stats["exclude"] += 1
            venues[key] = rec
            continue

        if verdict == "closed":
            rec["closed"] = True
            rec["closed_reason"] = (
                f.get("closed_reason") or note or "fleet closed")
            arcade["closed"] = True
            arcade["closed_reason"] = rec["closed_reason"]
            arcade["closed_source"] = rec.get("evidence_url")
            stats["closed"] += 1
            stats["patch_live"] += 1
            venues[key] = rec
            continue

        if verdict == "add_games":
            games = [g for g in (f.get("games") or [])
                     if g in VALID_GAMES and g != "other"]
            if not games:
                stats["skip"] += 1
                continue
            prev = set(rec.get("add_games") or [])
            rec["add_games"] = sorted(prev | set(games))
            arcade["games"] = sorted(
                set(arcade.get("games") or []) | set(games))
            stats["add_games"] += 1
            stats["patch_live"] += 1
            venues[key] = rec
            continue

        if verdict == "remove_games":
            games = [g for g in (f.get("games") or []) if g in VALID_GAMES]
            if not games:
                stats["skip"] += 1
                continue
            prev = set(rec.get("remove_games") or [])
            rec["remove_games"] = sorted(prev | set(games))
            arcade["games"] = sorted(
                set(arcade.get("games") or []) - set(games))
            if not arcade["games"]:
                arcade["games"] = ["other"]
            stats["remove_games"] += 1
            stats["patch_live"] += 1
            venues[key] = rec
            continue

        stats["skip"] += 1

    # Drop excluded from live map
    if exclude_ids or exclude_sids:
        kept = []
        for a in arcades:
            if a.get("id") in exclude_ids or a.get("sid") in exclude_sids:
                stats["removed_live"] += 1
                sid = a.get("sid")
                if sid:
                    sp = ROOT / "s" / (sid + ".html")
                    if sp.exists():
                        sp.unlink()
                continue
            kept.append(a)
        data["arcades"] = kept
        arcades = kept

    OWNER.write_text(json.dumps(oa, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    ARCADES.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")

    if STATS.exists():
        try:
            st = json.loads(STATS.read_text(encoding="utf-8"))
            if isinstance(st.get("counts"), dict):
                st["counts"]["total"] = len(arcades)
                STATS.write_text(
                    json.dumps(st, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
        except (OSError, ValueError):
            pass

    print("apply_deep_research:", stats)
    print("arcades now:", len(arcades))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
