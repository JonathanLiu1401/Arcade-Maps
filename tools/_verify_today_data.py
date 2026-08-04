#!/usr/bin/env python3
"""Adversarial data probes for today's IC gate + map rebuild."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS: list[str] = []
OKS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print("FAIL:", msg)


def ok(msg: str) -> None:
    OKS.append(msg)
    print("OK:", msg)


def main() -> int:
    data = json.loads((ROOT / "data" / "arcades.json").read_text(encoding="utf-8"))
    arcades = data["arcades"]
    ok(f"total arcades = {len(arcades)}")

    # IC Adores ghost (sid 0197113f... / empty-street Ikebukuro centroid).
    # Official allnet/eagate/ziv Adores chain halls may still appear; those
    # are not the IC city-centroid failure mode.
    def srcs_early(a):
        s = a.get("sources") or a.get("src") or a.get("source") or []
        if isinstance(s, dict):
            s = list(s.keys())
        if isinstance(s, str):
            s = [s]
        return [str(x).lower() for x in s]

    def is_ic_src(s: str) -> bool:
        return s in ("ic", "insert_coin", "insert-coin") or (
            "insert" in s and "coin" in s
        )

    adores_ic = []
    adores_all = []
    for a in arcades:
        nm = ((a.get("name") or "") + " " + (a.get("name_ja") or "")).lower()
        if "adores" not in nm and "アドアーズ" not in (a.get("name") or ""):
            continue
        adores_all.append(a)
        ss = srcs_early(a)
        if ss and all(is_ic_src(s) for s in ss):
            adores_ic.append(a)
        # also any insert_coin provenance with bare "Adores" + JP
        if any(is_ic_src(s) for s in ss) and (a.get("country") or "") in (
            "Japan",
            "JP",
        ):
            if a not in adores_ic:
                adores_ic.append(a)
    if adores_ic:
        for a in adores_ic:
            print(
                "  ADOR IC hit:",
                a.get("name"),
                a.get("country") or a.get("cc"),
                srcs_early(a),
                a.get("lat"),
                a.get("lon"),
            )
        fail(
            f"IC-sourced Adores still present ({len(adores_ic)}) - "
            "closed IC ghost should be gone"
        )
    else:
        ok(
            f"No IC-sourced Adores ghosts "
            f"({len(adores_all)} official/ZIv Adores remain, expected)"
        )
    # Exact sid from DATA_SOURCES failure-mode example
    blob = json.dumps(arcades, ensure_ascii=False)
    if "0197113f-6c78-78ae-b45a-f7409af2c190" in blob:
        fail("IC Adores sid 0197113f still in arcades.json")
    else:
        ok("IC Adores sid 0197113f absent from arcades.json")

    # Insert Coin provenance
    def srcs(a):
        return srcs_early(a)

    ic_any = [a for a in arcades if any(is_ic_src(s) for s in srcs(a))]

    # Sample source field shapes
    sample_src = Counter()
    for a in arcades[:500]:
        sample_src[tuple(srcs(a)[:5])] += 1
    print("sample source shapes (first 500):")
    for k, v in sample_src.most_common(8):
        print(" ", v, k)

    ic_only = [a for a in arcades if srcs(a) and all(is_ic_src(s) for s in srcs(a))]
    print(f"ic_any={len(ic_any)} ic_only={len(ic_only)}")

    dense = {
        "JP",
        "CN",
        "TW",
        "KR",
        "HK",
        "MO",
        "Japan",
        "China",
        "Taiwan",
        "Korea",
        "South Korea",
        "Hong Kong",
        "Macau",
        "Macao",
    }
    dense_ic_only = []
    dense_ic_any = []
    for a in arcades:
        cc = (a.get("country") or a.get("cc") or a.get("region") or "").strip()
        dense_here = cc in dense or cc.upper() in {
            x.upper() for x in dense if len(x) == 2
        }
        for key in ("country_code", "iso2", "cc"):
            v = (a.get(key) or "").upper()
            if v in {"JP", "CN", "TW", "KR", "HK", "MO"}:
                dense_here = True
        if not dense_here:
            continue
        ss = srcs(a)
        if any(is_ic_src(s) for s in ss):
            dense_ic_any.append(a)
        if ss and all(is_ic_src(s) for s in ss):
            dense_ic_only.append(a)

    if dense_ic_only:
        for a in dense_ic_only[:15]:
            print(
                "  DENSE IC-ONLY:",
                a.get("name"),
                a.get("country") or a.get("cc"),
                srcs(a),
            )
        fail(f"IC-only venues in dense official countries: {len(dense_ic_only)}")
    else:
        ok("No IC-only pins in JP/CN/TW/KR/HK/MO")

    if dense_ic_any:
        for a in dense_ic_any[:10]:
            print(
                "  DENSE IC-ANY:",
                a.get("name"),
                a.get("country"),
                srcs(a),
            )
        fail(
            f"insert_coin provenance in dense official countries: "
            f"{len(dense_ic_any)} (scraper should block entirely today)"
        )
    else:
        ok("No insert_coin provenance in JP/CN/TW/KR/HK/MO")

    # closed flags
    closed = [
        a
        for a in arcades
        if a.get("isOpen") is False
        or a.get("closed") is True
        or str(a.get("status") or "").lower() in ("closed", "permanently_closed")
    ]
    print(f"venues with closed-ish flag: {len(closed)}")

    # Raw IC dump quality
    ic_path = ROOT / "data_raw" / "insert_coin.json"
    if ic_path.exists():
        raw = json.loads(ic_path.read_text(encoding="utf-8"))
        items = (
            raw
            if isinstance(raw, list)
            else raw.get("arcades")
            or raw.get("venues")
            or raw.get("items")
            or []
        )
        if isinstance(raw, dict) and not items:
            for k, v in raw.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    items = v
                    print(f"raw IC list key={k}")
                    break
        print(f"raw insert_coin items: {len(items)}")
        ok(f"raw IC dump present ({len(items)} items)")
        dense_raw = [
            r
            for r in items
            if (r.get("country") or "")
            in {
                "Japan",
                "China",
                "Taiwan",
                "South Korea",
                "Hong Kong",
                "Macau",
            }
        ]
        if dense_raw:
            fail(f"raw IC still has dense-country rows: {len(dense_raw)}")
        else:
            ok("raw IC has zero JP/CN/TW/KR/HK/MO rows")
        no_street = [r for r in items if not (r.get("street") or "").strip()]
        if no_street:
            fail(f"raw IC rows missing street: {len(no_street)}")
        else:
            ok("raw IC every row has street")
    else:
        fail("data_raw/insert_coin.json missing")

    # Raw nearcade: no is_open=false should remain (scraper drops them)
    nc_path = ROOT / "data_raw" / "nearcade.json"
    if nc_path.exists():
        nc = json.loads(nc_path.read_text(encoding="utf-8"))
        nc_closed = [
            r
            for r in nc
            if r.get("is_open") is False
            or r.get("isOpen") is False
            or "isopen=false" in (r.get("notes") or "").lower()
        ]
        if nc_closed:
            fail(f"raw nearcade still has closed rows: {len(nc_closed)}")
        else:
            ok(f"raw nearcade has zero closed rows ({len(nc)} open)")
        # no nearcade-only open pin that is a known pre-gate closed sid
        nc_sids_on_map = 0
        for a in arcades:
            ss = srcs(a)
            if ss == ["nearcade"] or (ss and all(s == "nearcade" for s in ss)):
                nc_sids_on_map += 1
        print(f"nearcade-only map pins: {nc_sids_on_map}")
    else:
        fail("data_raw/nearcade.json missing")

    # Unit: scrapers still enforce gates
    sys.path.insert(0, str(ROOT / "scrapers"))
    import insert_coin as ic  # noqa: E402
    import nearcade as ncmod  # noqa: E402

    r = ic.quality_reject_reason(
        {
            "address": {
                "address": "",
                "city": "Toshima City",
                "postcode": "170-0013",
                "country": "JP",
            }
        },
        ["maimai PLUS", "Sound Voltex II"],
        "Japan",
    )
    if r != "no_street_address":
        fail(f"IC empty-street JP reject expected no_street_address got {r}")
    else:
        ok("IC unit: empty street JP -> no_street_address")

    r = ic.quality_reject_reason(
        {"address": {"address": "1-1 Main", "country": "JP"}},
        ["maimai DX"],
        "Japan",
    )
    if r != "dense_official_country":
        fail(f"IC street JP reject expected dense_official_country got {r}")
    else:
        ok("IC unit: street JP -> dense_official_country")

    r = ic.quality_reject_reason(
        {"address": {"address": "12 Main St", "country": "AU"}},
        ["maimai PLUS", "Sound Voltex II", "jubeat saucer"],
        "Australia",
    )
    if r != "vintage_software_only":
        fail(f"IC vintage AU reject expected vintage_software_only got {r}")
    else:
        ok("IC unit: vintage AU -> vintage_software_only")

    closed_shop = {
        "id": 1,
        "name": "Closed Test",
        "isOpen": False,
        "address": {"detailed": "x", "region": [{"id": "CN"}], "general": []},
        "location": {"coordinates": [121.0, 31.0]},
        "games": [{"titleId": 1, "name": "maimai", "quantity": 1}],
    }
    if ncmod.shop_row(closed_shop) is not None:
        fail("nearcade shop_row(isOpen=false) did not return None")
    else:
        ok("nearcade unit: isOpen=false -> None")

    # Stats
    stats = json.loads((ROOT / "data" / "stats.json").read_text(encoding="utf-8"))
    print("stats total:", stats.get("counts", {}).get("total"))
    print("stats insert_coin:", stats.get("counts", {}).get("by_source", {}).get(
        "insert_coin"
    ))
    print("stats nearcade:", stats.get("counts", {}).get("by_source", {}).get(
        "nearcade"
    ))

    print("\n=== SUMMARY ===")
    print(f"OK={len(OKS)} FAIL={len(FAILS)}")
    for f in FAILS:
        print(" -", f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
