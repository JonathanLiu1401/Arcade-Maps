# -*- coding: utf-8 -*-
"""Shard every arcade for the deep-research fleet (128 agents, full map).

Priority (researched first within each regional bucket):
  0  ALL.Net-only outside Japan (home installs / closed ghosts)
  1  insert_coin-only
  2  other-only / empty games
  3  single-source
  4  multi-source baseline

Writes:
  data_raw/deep_research/manifest.json
  data_raw/deep_research/shards/deep_000.json ... deep_127.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_raw" / "deep_research"
SHARDS = 128


def risk(a: dict) -> int:
    src = set(a.get("src") or [])
    games = a.get("games") or []
    only_other = not games or games == ["other"]
    single = len(src) == 1
    country = a.get("country") or ""
    if single and "allnet" in src and country not in ("Japan",):
        return 0
    if single and "insert_coin" in src:
        return 1
    if only_other:
        return 2
    if single:
        return 3
    return 4


def slim(a: dict) -> dict:
    links = a.get("links") or {}
    return {
        "id": a.get("id"),
        "sid": a.get("sid"),
        "name": a.get("name"),
        "addr": a.get("addr"),
        "country": a.get("country"),
        "pref": a.get("pref"),
        "lat": a.get("lat"),
        "lng": a.get("lng"),
        "games": a.get("games") or [],
        "src": a.get("src") or [],
        "links": {k: v for k, v in links.items()
                  if k != "also" and v},
        "also": links.get("also") or [],
        "closed": bool(a.get("closed")),
        "notes": (a.get("notes") or "")[:400],
        "risk": risk(a),
    }


def main() -> None:
    data = json.loads((ROOT / "data" / "arcades.json").read_text(encoding="utf-8"))
    arcades = [slim(a) for a in data["arcades"]]
    # Region buckets, then risk, then name - keeps each agent local.
    arcades.sort(key=lambda a: (
        a.get("country") or "ZZZ",
        a.get("pref") or "",
        a["risk"],
        (a.get("name") or "").casefold(),
    ))

    OUT.mkdir(parents=True, exist_ok=True)
    shard_dir = OUT / "shards"
    report_dir = OUT / "reports"
    shard_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)

    n = len(arcades)
    # Even split with remainder in early shards
    base, rem = divmod(n, SHARDS)
    manifest = []
    offset = 0
    for i in range(SHARDS):
        size = base + (1 if i < rem else 0)
        chunk = arcades[offset:offset + size]
        offset += size
        path = shard_dir / ("deep_%03d.json" % i)
        payload = {
            "shard": i,
            "n": len(chunk),
            "risk_hist": {},
            "venues": chunk,
        }
        for a in chunk:
            r = str(a["risk"])
            payload["risk_hist"][r] = payload["risk_hist"].get(r, 0) + 1
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        countries = sorted({a.get("country") or "?" for a in chunk})
        manifest.append({
            "shard": i,
            "file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "n": len(chunk),
            "countries": countries[:12],
            "risk_hist": payload["risk_hist"],
        })

    (OUT / "manifest.json").write_text(
        json.dumps({"shards": SHARDS, "total": n, "manifest": manifest},
                   ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print("deep research shards: %d venues -> %d shards (~%d each)"
          % (n, SHARDS, n // SHARDS))
    print("wrote", OUT / "manifest.json")


if __name__ == "__main__":
    main()
