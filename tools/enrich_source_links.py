# -*- coding: utf-8 -*-
"""Patch data/arcades.json links so every provenance source has a page URL.

Does not re-run the full merge. Matches raw rows to arcades by name+addr
(and coord fallback), then writes links.<source> for each match.

ALL.Net: https://location.am-all.net/alm/shop?sid=...
Community schema: row.source_url when it is a human-openable page.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scrapers"))
from merge import (  # noqa: E402
    ALLNET_FILES,
    OPTIONAL_COMMUNITY_SOURCES,
    allnet_shop_url,
    is_useful_source_url,
)

RAW = ROOT / "data_raw"
ARC = ROOT / "data" / "arcades.json"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return s


def load_list(path: Path):
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in ("arcades", "rows", "venues", "places", "stores"):
            if isinstance(payload.get(k), list):
                return payload[k]
    return []


def add_index(idx: dict, keys, source: str, url: str) -> None:
    if not url or not is_useful_source_url(url):
        return
    for key in keys:
        if not key:
            continue
        bucket = idx.setdefault(key, {})
        cur = bucket.get(source)
        if not cur:
            bucket[source] = url
        elif cur != url:
            also = bucket.setdefault("_also", [])
            if url not in also and url != cur:
                also.append(url)


def main() -> int:
    data = json.loads(ARC.read_text(encoding="utf-8"))
    arcades = data["arcades"]

    # key -> {source: url, _also?: [url]}
    by_name_addr: dict[str, dict] = {}
    by_coord: dict[str, dict] = {}

    # ALL.Net game scrapes
    for fn in ALLNET_FILES:
        rows = load_list(RAW / (fn + ".json"))
        for row in rows:
            if not isinstance(row, dict):
                continue
            url = allnet_shop_url(row.get("sid"))
            if not url:
                continue
            name, addr = row.get("name") or "", row.get("address") or ""
            add_index(by_name_addr, [norm(name) + "|" + norm(addr)],
                      "allnet", url)
            lat, lng = row.get("lat"), row.get("lng")
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                add_index(by_coord,
                          ["%.4f|%.4f" % (float(lat), float(lng))],
                          "allnet", url)

    # Community-schema files (including ziv / bemanicn / optionals)
    community_files = [
        ("ziv", "ziv"),
        ("china_bemanicn", "bemanicn"),
        ("community", None),  # use row.source
        ("round1usa", "round1usa"),
    ]
    for slug in OPTIONAL_COMMUNITY_SOURCES:
        community_files.append((slug, slug))

    for fn, default_src in community_files:
        rows = load_list(RAW / (fn + ".json"))
        for row in rows:
            if not isinstance(row, dict):
                continue
            src = default_src or row.get("source") or "community"
            url = row.get("source_url") or row.get("url")
            if src == "allnet" and not url and row.get("sid"):
                url = allnet_shop_url(row.get("sid"))
            if not is_useful_source_url(url):
                continue
            name, addr = row.get("name") or "", row.get("address") or ""
            add_index(by_name_addr, [norm(name) + "|" + norm(addr)],
                      src, url)
            lat, lng = row.get("lat"), row.get("lng")
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                add_index(by_coord,
                          ["%.4f|%.4f" % (float(lat), float(lng))],
                          src, url)

    n_added = 0
    n_arcades_touched = 0
    for a in arcades:
        links = dict(a.get("links") or {})
        also = list(links.get("also") or [])
        srcs = list(a.get("src") or [])
        name_key = norm(a.get("name") or "") + "|" + norm(a.get("addr") or "")
        buckets = []
        if name_key in by_name_addr:
            buckets.append(by_name_addr[name_key])
        lat, lng = a.get("lat"), a.get("lng")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            ck = "%.4f|%.4f" % (float(lat), float(lng))
            if ck in by_coord:
                buckets.append(by_coord[ck])

        before = json.dumps(links, sort_keys=True)
        for bucket in buckets:
            for src, url in bucket.items():
                if src == "_also":
                    for u in url:
                        if u not in also and u not in links.values():
                            also.append(u)
                            n_added += 1
                    continue
                if src not in srcs and src not in ("ziv", "bemanicn"):
                    # Only attach URLs for sources the arcade claims,
                    # except always allow ziv/bemanicn if matched (already in srcs if used).
                    if src not in srcs:
                        continue
                if not links.get(src):
                    links[src] = url
                    n_added += 1
                elif links[src] != url and url not in also:
                    also.append(url)
                    n_added += 1

        # Ensure each claimed source gets a chance: if we have src allnet
        # but no link, try name-only allnet match from name_key variants.
        for s in srcs:
            if links.get(s):
                continue
            for bucket in buckets:
                if bucket.get(s):
                    links[s] = bucket[s]
                    n_added += 1
                    break

        if also:
            links["also"] = also
        elif "also" in links:
            del links["also"]
        # Drop null / empty placeholders (legacy ziv:null / bemanicn:null).
        links = {k: v for k, v in links.items()
                 if v is not None and v != "" and v != []}
        a["links"] = links
        if json.dumps(links, sort_keys=True) != before:
            n_arcades_touched += 1

    ARC.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                   + "\n", encoding="utf-8")
    print("enrich_source_links: touched %d arcades, added %d link values"
          % (n_arcades_touched, n_added))

    # Report coverage
    from collections import Counter
    have = Counter()
    need = Counter()
    for a in arcades:
        links = a.get("links") or {}
        for s in a.get("src") or []:
            need[s] += 1
            if links.get(s):
                have[s] += 1
    print("coverage (have/need):")
    for s in sorted(need, key=lambda k: -need[k]):
        print("  %s: %d / %d (%.0f%%)"
              % (s, have[s], need[s],
                 100.0 * have[s] / need[s] if need[s] else 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
