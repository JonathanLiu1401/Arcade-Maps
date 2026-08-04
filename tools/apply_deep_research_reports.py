# -*- coding: utf-8 -*-
"""Apply data_raw/deep_research/reports/deep_*.json into owner_attested.json.

Only confidence=certain findings with evidence_url are applied.
Actions: closed | exclude | add_games | remove_games | note_only (skipped for write).
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
    for p in sorted(REPORTS.glob("deep_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print("skip bad report", p, e)
            continue
        for f in d.get("findings") or []:
            f["_shard"] = d.get("shard")
            out.append(f)
    return out


def main() -> int:
    data = json.loads(ARCADES.read_text(encoding="utf-8"))
    by_sid = {a.get("sid"): a for a in data["arcades"] if a.get("sid")}
    by_id = {a.get("id"): a for a in data["arcades"]}

    oa = json.loads(OWNER.read_text(encoding="utf-8"))
    venues = oa.setdefault("venues", {})

    stats = {"closed": 0, "exclude": 0, "add_games": 0, "remove_games": 0,
             "skip": 0, "patch_live": 0}

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

        # Prefer existing owner key
        key = build_corrections.lookup(venues, arcade)
        if key is None:
            # use preferred key string
            key = build_corrections.venue_key(arcade)
        else:
            # lookup returns the record; find actual key
            key = None
            for k in build_corrections.venue_keys(arcade):
                if k in venues:
                    key = k
                    break
            if key is None:
                key = build_corrections.venue_key(arcade)

        existing = venues.get(key) or {}
        if existing.get("attested_by") == "owner" and (
                existing.get("exclude") or existing.get("closed")):
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

        if verdict == "closed":
            rec["closed"] = True
            rec["closed_reason"] = f.get("closed_reason") or note or "fleet closed"
            # live patch
            arcade["closed"] = True
            arcade["closed_reason"] = rec["closed_reason"]
            arcade["closed_source"] = rec.get("evidence_url")
            stats["closed"] += 1
            stats["patch_live"] += 1
        elif verdict == "exclude":
            rec["exclude"] = True
            stats["exclude"] += 1
        elif verdict == "add_games":
            games = [g for g in (f.get("games") or []) if g in VALID_GAMES and g != "other"]
            if not games:
                stats["skip"] += 1
                continue
            prev = set(rec.get("add_games") or [])
            rec["add_games"] = sorted(prev | set(games))
            # live patch games union
            arcade["games"] = sorted(set(arcade.get("games") or []) | set(games))
            stats["add_games"] += 1
            stats["patch_live"] += 1
        elif verdict == "remove_games":
            games = [g for g in (f.get("games") or []) if g in VALID_GAMES]
            if not games:
                stats["skip"] += 1
                continue
            prev = set(rec.get("remove_games") or [])
            rec["remove_games"] = sorted(prev | set(games))
            arcade["games"] = sorted(set(arcade.get("games") or []) - set(games))
            stats["remove_games"] += 1
            stats["patch_live"] += 1
        else:
            stats["skip"] += 1
            continue

        venues[key] = rec

    OWNER.write_text(json.dumps(oa, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    ARCADES.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")
    print("apply_deep_research:", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
