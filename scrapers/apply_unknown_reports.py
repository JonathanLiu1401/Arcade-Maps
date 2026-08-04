#!/usr/bin/env python3
"""Apply data_raw/unknown/reports/unk_*.json findings into owner_attested.json.

Idempotent. Safety over coverage: wrong game list is worse than missing.

Rules (v2):
  has_games  - confidence certain|likely; evidence_url + evidence_quote required;
               games = GAME_SLUGS intersect finding.games, minus pure-other-only
               unless note is strong (default: skip pure-other-only).
               Merge add_games with any existing research-fleet entry.
               Never wipe exclude unless has_games certain with real games.
  closed     - confidence certain; evidence required -> closed:true
  confirmed_none - confidence certain; evidence NOT circular ZIv-empty only;
               only if current arcade games are a subset of {other} -> exclude:true

Keyed by source URL via build_corrections.venue_key (never by row id).
Join findings to data/arcades.json by sid.

Usage:
  python scrapers/apply_unknown_reports.py
  python scrapers/apply_unknown_reports.py --dry-run
  python scrapers/apply_unknown_reports.py --no-rebuild
"""

from __future__ import annotations

import argparse
import collections
import datetime as _dt
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_corrections  # noqa: E402
from merge import GAME_SLUGS  # noqa: E402

ATTESTED_BY = "research-fleet"
REPORT_GLOB = os.path.join(ROOT, "data_raw", "unknown", "reports", "unk_*.json")
ARCADES_PATH = os.path.join(ROOT, "data", "arcades.json")
OWNER_PATH = os.path.join(ROOT, "data", "owner_attested.json")
PLAN_V2_PATH = os.path.join(ROOT, "data_raw", "unknown", "apply_plan_v2.json")
INTEGRATE_REPORT = os.path.join(
    ROOT, "data_raw", "integrate", "apply_unknown_report.json"
)

REAL_GAME_SLUGS = frozenset(g for g in GAME_SLUGS if g != "other")
OTHER_ONLY = frozenset({"other"})

# Positive non-rhythm / venue-type signals that make confirmed_none safe
# even when the evidence page is ZIv (inventory, venue type, removal note).
_POSITIVE_NONE_RE = re.compile(
    r"claw|crane|redemption|pinball|racing|bowl|museum|kidd(?:y|ie)|"
    r"kids?\s*only|soft[-\s]?play|pusher|ticket|foosball|air\s*hockey|"
    r"removed|gone|formerly|no dance|no rhythm|inventory|mostly|"
    r"cinema|cinescape|xscape|\bVR\b|fighter|shooter|classic|retro|"
    r"pool\b|FEC|amusement|gambling|AGC|retail|shop|console|"
    r"bar\b|brewery|restaurant|pizza|tenpin|bowling|theme park|"
    r"soft play|play centre|no video game|no arcade|"
    r"no music game|no music games|not a music|"
    r"only\s+(?:claw|crane|racing|redemption|pinball|kids)|"
    r"games?\s*(?:list|inventory)\s*(?:only|:)|"
    r"explicit|positive",
    re.I,
)

# Bare ZIv silence without a positive non-rhythm description.
_BARE_EMPTY_RE = re.compile(
    r"no music game available|"
    r"no games at this location|"
    r"0\s*machines|"
    r"games?\s*(?:section\s*)?(?:is\s*)?empty|"
    r"no music games(?:\s+are\s+currently\s+available)?",
    re.I,
)

def _today():
    return _dt.date.today().isoformat()


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def load_findings():
    """All findings from unk_*.json, tagged with shard number."""
    out = []
    paths = sorted(glob.glob(REPORT_GLOB))
    for path in paths:
        try:
            data = _load_json(path)
        except (OSError, ValueError) as e:
            print("warn: skip %s: %s" % (path, e), file=sys.stderr)
            continue
        shard = data.get("shard")
        for f in data.get("findings") or []:
            if not isinstance(f, dict):
                continue
            row = dict(f)
            row["_shard"] = shard
            row["_report"] = os.path.basename(path)
            out.append(row)
    return out, paths


def load_arcades_by_sid():
    raw = _load_json(ARCADES_PATH)
    rows = raw["arcades"] if isinstance(raw, dict) and "arcades" in raw else raw
    by_sid = {}
    for a in rows:
        sid = a.get("sid")
        if sid:
            by_sid[sid] = a
    return by_sid, rows


def real_games(finding):
    """Valid non-other game slugs from a finding."""
    games = finding.get("games") or []
    return sorted({g for g in games if g in REAL_GAME_SLUGS})


def has_evidence(finding):
    url = (finding.get("evidence_url") or "").strip()
    quote = (finding.get("evidence_quote") or "").strip()
    return bool(url) and bool(quote)


def is_circular_ziv_empty(finding):
    """True when the only 'proof' is ZIv silence (empty / no music), with
    no positive description of what the venue actually is.

    Positive inventory, removal notes, venue-type labels, or a non-ZIv
    evidence URL all make the finding non-circular.
    """
    url = finding.get("evidence_url") or ""
    quote = finding.get("evidence_quote") or ""
    note = finding.get("note") or ""
    text = "%s %s" % (quote, note)
    if "zenius-i-vanisher" not in url:
        return False
    if _POSITIVE_NONE_RE.search(text):
        return False
    if _BARE_EMPTY_RE.search(quote) or _BARE_EMPTY_RE.search(note):
        return True
    # Very short ZIv quotes with no inventory detail are also weak.
    if len(quote.strip()) < 40 and not _POSITIVE_NONE_RE.search(text):
        return True
    return False


def _clip(s, n=220):
    s = re.sub(r"\s+", " ", (s or "").strip())
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "..."


def make_note(finding, prefix):
    quote = _clip(finding.get("evidence_quote") or "", 200)
    note = _clip(finding.get("note") or "", 180)
    if note:
        return "%s: %s | %s" % (prefix, quote, note)
    return "%s: %s" % (prefix, quote)


def arcade_games_set(arcade):
    return set(arcade.get("games") or [])


def find_existing_key(venues, arcade):
    """Return the key already used in owner_attested for this arcade, if any."""
    for key in build_corrections.venue_keys(arcade):
        if key in venues:
            return key
    return None


def preferred_key(arcade):
    return build_corrections.venue_key(arcade)


def synthetic_key_from_sid(sid):
    """Build owner_attested key from zNNNN / bNNNN when arcade row is gone."""
    if sid and sid.startswith("z") and sid[1:].isdigit():
        return ("ziv|https://zenius-i-vanisher.com/v5.2/"
                "arcade.php?id=%s" % sid[1:])
    if sid and sid.startswith("b") and sid[1:].isdigit():
        return "bemanicn|https://map.bemanicn.com/s/%s" % sid[1:]
    return None


def decide(finding, arcade, existing_rec):
    """Return (action, payload_or_none, skip_reason_or_none).

    action in: apply_add_games | apply_closed | apply_exclude | skip
    """
    verdict = finding.get("verdict")
    conf = finding.get("confidence")

    if verdict == "unknown":
        return "skip", None, "verdict_unknown"

    if not has_evidence(finding):
        return "skip", None, "missing_evidence"

    if verdict == "has_games":
        if conf not in ("certain", "likely"):
            return "skip", None, "has_games_low_confidence"
        real = real_games(finding)
        # Pure-other-only is a no-op for map chips (venue already shows
        # other) and first-pass policy skipped it. Safety > coverage:
        # never write add_games=["other"] alone.
        if not real:
            return "skip", None, "has_games_other_only_or_empty"
        # Protect existing exclude unless certain + real non-other games
        if existing_rec and existing_rec.get("exclude"):
            if conf != "certain":
                return "skip", None, "exclude_protected"
            # certain has_games with real games: may lift exclude
        # Protect owner-attested entries from research-fleet overwrite
        # unless we only merge add_games onto a non-exclude owner row.
        if existing_rec and existing_rec.get("attested_by") == "owner":
            if existing_rec.get("exclude") or existing_rec.get("closed"):
                if conf != "certain":
                    return "skip", None, "owner_protected"
            # merge add_games is OK for owner rows that already have games
        payload = {
            "kind": "add_games",
            "games": real,
            "confidence": conf,
            "evidence_url": finding.get("evidence_url"),
            "note": make_note(finding, "unknown-games fleet"),
            "name": finding.get("name") or (arcade or {}).get("name"),
        }
        return "apply_add_games", payload, None

    if verdict == "closed":
        if conf != "certain":
            return "skip", None, "closed_low_confidence"
        if existing_rec and existing_rec.get("attested_by") == "owner":
            return "skip", None, "owner_protected"
        if existing_rec and existing_rec.get("exclude"):
            # already dropped; closed is weaker / redundant
            return "skip", None, "already_excluded"
        payload = {
            "kind": "closed",
            "closed_reason": _clip(
                finding.get("note")
                or finding.get("evidence_quote")
                or "Permanently closed (research-fleet)",
                200,
            ),
            "evidence_url": finding.get("evidence_url"),
            "name": finding.get("name") or (arcade or {}).get("name"),
            "note": make_note(finding, "closed"),
        }
        return "apply_closed", payload, None

    if verdict == "confirmed_none":
        if conf != "certain":
            return "skip", None, "confirmed_none_low_confidence"
        if is_circular_ziv_empty(finding):
            return "skip", None, "circular_ziv_empty"
        if existing_rec and existing_rec.get("attested_by") == "owner":
            return "skip", None, "owner_protected"
        if existing_rec and existing_rec.get("exclude"):
            # Already excluded (arcade row may be gone after rebuild).
            # Still return apply_exclude so the plan counts it as already.
            payload = {
                "kind": "exclude",
                "evidence_url": existing_rec.get("evidence_url")
                or finding.get("evidence_url"),
                "note": existing_rec.get("note")
                or make_note(finding, "confirmed_none"),
                "name": existing_rec.get("name")
                or finding.get("name"),
            }
            return "apply_exclude", payload, None
        if arcade is None:
            return "skip", None, "sid_not_in_arcades"
        games = arcade_games_set(arcade)
        if not games <= OTHER_ONLY:
            return "skip", None, "has_non_other_games"
        if existing_rec and existing_rec.get("add_games"):
            # research already claimed games; do not exclude
            prior_real = [g for g in (existing_rec.get("add_games") or [])
                          if g != "other"]
            if prior_real:
                return "skip", None, "prior_add_games"
        payload = {
            "kind": "exclude",
            "evidence_url": finding.get("evidence_url"),
            "note": make_note(finding, "confirmed_none"),
            "name": finding.get("name") or arcade.get("name"),
        }
        return "apply_exclude", payload, None

    return "skip", None, "unknown_verdict"


def merge_entry(existing, action, payload, attested_at):
    """Build the new owner_attested record for a venue."""
    if action == "apply_add_games":
        games = list(payload["games"])
        if existing and existing.get("add_games"):
            games = sorted(set(existing["add_games"]) | set(games))
        # Lift exclude when certain real games override
        rec = {
            "name": payload.get("name") or (existing or {}).get("name"),
            "attested_by": ATTESTED_BY,
            "attested_at": attested_at,
            "add_games": games,
            "evidence_url": payload.get("evidence_url")
            or (existing or {}).get("evidence_url"),
            "note": payload.get("note") or (existing or {}).get("note"),
        }
        # Preserve owner identity if we are merging onto an owner row
        if existing and existing.get("attested_by") == "owner":
            rec["attested_by"] = "owner"
            if existing.get("note") and payload.get("note"):
                rec["note"] = existing["note"] + " | fleet: " + payload["note"]
            elif existing.get("note"):
                rec["note"] = existing["note"]
            # keep any prior owner add_games already merged above
        return rec

    if action == "apply_closed":
        rec = {
            "name": payload.get("name") or (existing or {}).get("name"),
            "closed": True,
            "closed_reason": payload.get("closed_reason"),
            "evidence_url": payload.get("evidence_url"),
            "attested_by": ATTESTED_BY,
            "attested_at": attested_at,
        }
        # Prefer not to carry stale add_games on a closed pin; leave them
        # only if existing research-fleet had them (historical presence).
        if existing and existing.get("add_games"):
            rec["add_games"] = list(existing["add_games"])
            if existing.get("note"):
                rec["note"] = existing["note"]
        return rec

    if action == "apply_exclude":
        return {
            "name": payload.get("name") or (existing or {}).get("name"),
            "exclude": True,
            "evidence_url": payload.get("evidence_url"),
            "note": payload.get("note"),
            "attested_by": ATTESTED_BY,
            "attested_at": attested_at,
        }

    raise ValueError("bad action %s" % action)


def entry_effectively_same(old, new):
    """Semantic equality for idempotency.

    Notes and attested_at churn must NOT count as a change. Only flags and
    game sets matter for whether owner_attested needs a rewrite.
    """
    if not old:
        return False
    if bool(old.get("exclude")) != bool(new.get("exclude")):
        return False
    if bool(old.get("closed")) != bool(new.get("closed")):
        return False
    if sorted(old.get("add_games") or []) != sorted(new.get("add_games") or []):
        return False
    # closed_reason: only care when newly closing or reason was empty
    if new.get("closed") and not old.get("closed"):
        return False
    return True


def count_other_only(rows):
    n = 0
    for a in rows:
        g = set(a.get("games") or [])
        if g == OTHER_ONLY:
            n += 1
    return n


def apply(dry_run=False, rebuild=True):
    findings, report_paths = load_findings()
    by_sid, arcade_rows = load_arcades_by_sid()
    owner = _load_json(OWNER_PATH)
    venues = owner.get("venues") or {}
    if not isinstance(venues, dict):
        raise SystemExit("owner_attested.json venues must be an object")

    before_n_attested = len(venues)
    before_other_only = count_other_only(arcade_rows)
    before_total = len(arcade_rows)

    metrics = collections.Counter()
    metrics["findings_total"] = len(findings)
    metrics["reports"] = len(report_paths)
    plan = {
        "add_games": [],
        "closed": [],
        "exclude": [],
        "skipped": collections.Counter(),
    }

    # Prefer higher-confidence / more specific findings per sid.
    # Order: process all findings; last write wins within same action after
    # merge. For competing verdicts, rank has_games > closed > confirmed_none.
    rank = {"has_games": 3, "closed": 2, "confirmed_none": 1, "unknown": 0}
    conf_rank = {"certain": 3, "likely": 2, "unverified": 1}

    # Group by sid, pick best finding per sid for apply candidates.
    by_finding_sid = collections.defaultdict(list)
    for f in findings:
        sid = f.get("sid")
        if not sid:
            metrics["skip_no_sid"] += 1
            plan["skipped"]["no_sid"] += 1
            continue
        by_finding_sid[sid].append(f)

    chosen = []
    for sid, group in sorted(by_finding_sid.items()):
        group_sorted = sorted(
            group,
            key=lambda f: (
                rank.get(f.get("verdict"), 0),
                conf_rank.get(f.get("confidence"), 0),
                1 if has_evidence(f) else 0,
                len(real_games(f)),
            ),
            reverse=True,
        )
        chosen.append(group_sorted[0])
        if len(group_sorted) > 1:
            metrics["duplicate_sids"] += 1

    attested_at = _today()
    changes = []  # (sid, action, key)

    for finding in chosen:
        sid = finding["sid"]
        arcade = by_sid.get(sid)
        metrics["verdict_%s" % (finding.get("verdict") or "none")] += 1

        existing_key = None
        existing_rec = None
        synth = synthetic_key_from_sid(sid)
        if arcade is not None:
            existing_key = find_existing_key(venues, arcade)
            if existing_key:
                existing_rec = venues[existing_key]
        if existing_rec is None and synth and synth in venues:
            existing_key = synth
            existing_rec = venues[synth]

        action, payload, reason = decide(finding, arcade, existing_rec)
        if action == "skip":
            metrics["skipped"] += 1
            metrics["skip_%s" % reason] += 1
            plan["skipped"][reason] += 1
            continue

        if arcade is None:
            # Arcade row missing (often already excluded on a prior run).
            # decide() already allowed apply_exclude when existing_rec has
            # exclude:true; has_games/closed may still write via synth key.
            key = existing_key or synth
            if not key:
                metrics["skipped"] += 1
                metrics["skip_sid_not_in_arcades"] += 1
                plan["skipped"]["sid_not_in_arcades"] += 1
                continue
            if action == "apply_exclude" and not (
                    existing_rec and existing_rec.get("exclude")):
                # New exclude without a live row: cannot verify games subset.
                metrics["skipped"] += 1
                metrics["skip_sid_not_in_arcades"] += 1
                plan["skipped"]["sid_not_in_arcades"] += 1
                continue
        else:
            key = existing_key or preferred_key(arcade)

        new_rec = merge_entry(existing_rec, action, payload, attested_at)
        if entry_effectively_same(existing_rec, new_rec):
            metrics["unchanged"] += 1
            metrics["unchanged_%s" % action] += 1
            # still record in plan as already applied
            plan_row = {
                "sid": sid,
                "name": new_rec.get("name"),
                "key": key,
                "status": "already",
            }
            if action == "apply_add_games":
                plan_row["games"] = new_rec.get("add_games")
                plan_row["conf"] = finding.get("confidence")
                plan_row["url"] = new_rec.get("evidence_url")
                plan["add_games"].append(plan_row)
            elif action == "apply_closed":
                plan_row["url"] = new_rec.get("evidence_url")
                plan["closed"].append(plan_row)
            elif action == "apply_exclude":
                plan_row["url"] = new_rec.get("evidence_url")
                plan["exclude"].append(plan_row)
            continue

        # Applying a change
        metrics["applied"] += 1
        metrics["applied_%s" % action] += 1
        if existing_rec is None:
            metrics["inserted"] += 1
        else:
            metrics["updated"] += 1

        plan_row = {
            "sid": sid,
            "name": new_rec.get("name"),
            "key": key,
            "status": "new" if existing_rec is None else "updated",
        }
        if action == "apply_add_games":
            plan_row["games"] = new_rec.get("add_games")
            plan_row["conf"] = finding.get("confidence")
            plan_row["url"] = new_rec.get("evidence_url")
            plan["add_games"].append(plan_row)
        elif action == "apply_closed":
            plan_row["url"] = new_rec.get("evidence_url")
            plan_row["closed_reason"] = new_rec.get("closed_reason")
            plan["closed"].append(plan_row)
        elif action == "apply_exclude":
            plan_row["url"] = new_rec.get("evidence_url")
            plan["exclude"].append(plan_row)

        changes.append((sid, action, key))
        if not dry_run:
            venues[key] = new_rec

    # Summaries for plan v2
    plan_out = {
        "version": 2,
        "generated_at": attested_at,
        "dry_run": dry_run,
        "n_add_games": len(plan["add_games"]),
        "n_closed": len(plan["closed"]),
        "n_exclude": len(plan["exclude"]),
        "n_add_games_new": sum(
            1 for r in plan["add_games"] if r.get("status") != "already"),
        "n_closed_new": sum(
            1 for r in plan["closed"] if r.get("status") != "already"),
        "n_exclude_new": sum(
            1 for r in plan["exclude"] if r.get("status") != "already"),
        "skipped": dict(plan["skipped"]),
        "metrics": dict(metrics),
        "add_games": plan["add_games"],
        "closed": plan["closed"],
        "exclude": plan["exclude"],
        "before": {
            "owner_attested": before_n_attested,
            "arcades": before_total,
            "other_only": before_other_only,
        },
    }

    changed = bool(changes)
    if dry_run:
        print("DRY RUN: no files written (%d would-change)" % len(changes))
    else:
        if changed:
            owner["venues"] = venues
            _save_json(OWNER_PATH, owner)
            print("wrote %s (%d venues, %+d change ops)"
                  % (OWNER_PATH, len(venues), len(changes)))
        else:
            print("owner_attested unchanged (%d venues)" % len(venues))

    _save_json(PLAN_V2_PATH, plan_out)
    print("wrote %s" % PLAN_V2_PATH)

    after_n_attested = len(venues)
    after_total = before_total
    after_other_only = before_other_only
    rebuild_ran = False
    rebuild_ok = None

    if changed and rebuild and not dry_run:
        print("rebuilding data/arcades.json via run_all --skip-scrape ...")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-m", "scrapers.run_all", "--skip-scrape"],
            cwd=ROOT,
            env=env,
        )
        rebuild_ran = True
        rebuild_ok = proc.returncode == 0
        if rebuild_ok:
            by_sid2, rows2 = load_arcades_by_sid()
            after_total = len(rows2)
            after_other_only = count_other_only(rows2)
            print("rebuild ok: arcades %d -> %d, other-only %d -> %d"
                  % (before_total, after_total,
                     before_other_only, after_other_only))
        else:
            print("rebuild FAILED rc=%s" % proc.returncode, file=sys.stderr)

    plan_out["after"] = {
        "owner_attested": after_n_attested,
        "arcades": after_total,
        "other_only": after_other_only,
    }
    plan_out["rebuild_ran"] = rebuild_ran
    plan_out["rebuild_ok"] = rebuild_ok
    # rewrite plan with after stats
    if not dry_run:
        _save_json(PLAN_V2_PATH, plan_out)

    report = {
        "slug": "apply_unknown",
        "files_changed": (
            [os.path.relpath(OWNER_PATH, ROOT).replace("\\", "/"),
             os.path.relpath(PLAN_V2_PATH, ROOT).replace("\\", "/")]
            + ([os.path.relpath(ARCADES_PATH, ROOT).replace("\\", "/")]
               if rebuild_ran and rebuild_ok else [])
            + [os.path.relpath(os.path.join(ROOT, "scrapers",
                                            "apply_unknown_reports.py"),
                               ROOT).replace("\\", "/")]
        ),
        "summary": (
            "Idempotent apply of unknown-games fleet reports into "
            "owner_attested.json. Applied has_games (certain|likely, "
            "non-other), closed (certain), confirmed_none (certain, "
            "non-circular, other-only venues). Safety over coverage."
        ),
        "how_to_verify": [
            "python scrapers/apply_unknown_reports.py --dry-run",
            "python scrapers/apply_unknown_reports.py --no-rebuild",
            "python -m scrapers.run_all --skip-scrape",
            "Check data_raw/unknown/apply_plan_v2.json metrics",
            "grep research-fleet data/owner_attested.json | measure counts",
        ],
        "risks": [
            "confirmed_none excludes drop pins; circular ZIv-empty is "
            "filtered but agent notes can still be wrong.",
            "has_games pure-other-only is always skipped (map chip is already "
            "other; writing add_games=['other'] is noise).",
            "sid join depends on current arcades.json; missing sids after "
            "a prior exclude are not re-created.",
            "Owner-attested entries are protected from research-fleet "
            "overwrite except certain real-game lifts.",
        ],
        "metrics": {
            **dict(metrics),
            "changes": len(changes),
            "before_owner_attested": before_n_attested,
            "after_owner_attested": after_n_attested,
            "before_arcades": before_total,
            "after_arcades": after_total,
            "before_other_only": before_other_only,
            "after_other_only": after_other_only,
            "n_add_games": plan_out["n_add_games"],
            "n_closed": plan_out["n_closed"],
            "n_exclude": plan_out["n_exclude"],
            "n_add_games_new": plan_out["n_add_games_new"],
            "n_closed_new": plan_out["n_closed_new"],
            "n_exclude_new": plan_out["n_exclude_new"],
            "rebuild_ran": rebuild_ran,
            "rebuild_ok": rebuild_ok,
            "dry_run": dry_run,
        },
    }
    _save_json(INTEGRATE_REPORT, report)
    print("wrote %s" % INTEGRATE_REPORT)

    # Human metrics dump
    print("--- metrics ---")
    for k in sorted(metrics):
        print("  %s: %s" % (k, metrics[k]))
    print("  changes: %d" % len(changes))
    print("  owner_attested: %d -> %d" % (before_n_attested, after_n_attested))
    print("  arcades: %d -> %d" % (before_total, after_total))
    print("  other_only: %d -> %d" % (before_other_only, after_other_only))
    if changes[:20]:
        print("--- sample changes ---")
        for sid, action, key in changes[:20]:
            print("  %s %s %s" % (action, sid, key[:70]))

    return 0 if (rebuild_ok is not False) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute plan without writing owner_attested")
    ap.add_argument("--no-rebuild", action="store_true",
                    help="Skip run_all --skip-scrape even if owner_attested changed")
    args = ap.parse_args(argv)
    return apply(dry_run=args.dry_run, rebuild=not args.no_rebuild)


if __name__ == "__main__":
    sys.exit(main())
