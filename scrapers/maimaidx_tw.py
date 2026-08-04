"""Taiwan SEGA store lists: maimaidx.tw + chunithm.tw.

Fan mirrors of ALL.Net Taiwan shop locations (author IFYU). Each homepage
embeds a JS array:

  let store_data = JSON.parse('[{\"id\":\"...\",\"sid\":\"...\", ...}]');

Fields: id (site id), sid (ALL.Net sid), name_ch, name_en, name_net,
addr_ch, addr_pid (Google place id), lat, lon, city_ch, city_en.

Rows from both sites are merged by ALL.Net sid (or lat/lng+name if no sid)
so a shop with both maimai and CHUNITHM becomes one venue with both games.

Output is merge-friendly community family. Does NOT invent cab counts
(source has none). Overlaps ALL.Net Taiwan; value is Chinese display names,
Google place ids, and a single easy structured scrape.

Music Game Map (mgm.wind-chime.info) is higher-value for multi-title cabs
but returns 403 to plain HTTP clients; not implemented here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

SOURCES = [
    {
        "url": "https://maimaidx.tw/",
        "game": "maimai_dx",
        "store_base": "https://maimaidx.tw/store/",
        "label": "maimaidx.tw",
    },
    {
        "url": "https://chunithm.tw/",
        "game": "chunithm",
        "store_base": "https://chunithm.tw/store/",
        "label": "chunithm.tw",
    },
]
SOURCE = "maimaidx_tw"


def _as_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract_store_data(html):
    """Parse let store_data = JSON.parse('...'); from homepage HTML."""
    m = re.search(r"store_data\s*=\s*JSON\.parse\(\s*'", html)
    if not m:
        raise common.FetchError("store_data JSON.parse not found in HTML")
    start = m.end()
    out = []
    j = start
    n = len(html)
    while j < n:
        ch = html[j]
        if ch == "\\":
            if j + 1 >= n:
                break
            nxt = html[j + 1]
            if nxt == '"':
                out.append('"')
            elif nxt == "'":
                out.append("'")
            elif nxt == "\\":
                out.append("\\")
            elif nxt == "/":
                out.append("/")
            elif nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "u" and j + 5 < n:
                try:
                    out.append(chr(int(html[j + 2 : j + 6], 16)))
                except ValueError:
                    out.append(nxt)
                    j += 2
                    continue
                j += 6
                continue
            else:
                out.append(nxt)
            j += 2
            continue
        if ch == "'":
            break
        out.append(ch)
        j += 1
    s = "".join(out)
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise common.FetchError("store_data JSON decode failed: %s" % e)
    if not isinstance(data, list):
        raise common.FetchError("store_data is not a list")
    return data


def fetch_site(spec):
    html = common.fetch(spec["url"], retries=3, sleep=0.5, timeout=30)
    stores = extract_store_data(html)
    return stores


def _key_for(store):
    sid = str(store.get("sid") or "").strip()
    if sid:
        return "sid:" + sid
    # fallback: site-local id + name
    site_id = str(store.get("id") or "").strip()
    name = common.unescape(str(store.get("name_ch") or store.get("name_en") or ""))
    lat = store.get("lat")
    lon = store.get("lon")
    return "fb:%s|%s|%s|%s" % (site_id, name, lat, lon)


def scrape(smoke=False):
    """Return merged venue rows for Taiwan maimai_dx + chunithm."""
    # key -> accumulator
    acc = {}
    for spec in SOURCES:
        try:
            stores = fetch_site(spec)
        except common.FetchError as e:
            print("maimaidx_tw: %s FAILED: %s" % (spec["label"], e),
                  file=sys.stderr)
            continue
        print("maimaidx_tw: %s -> %d stores" % (spec["label"], len(stores)),
              file=sys.stderr)
        if smoke:
            stores = stores[:3]
        for st in stores:
            if not isinstance(st, dict):
                continue
            k = _key_for(st)
            if k not in acc:
                acc[k] = {
                    "store": st,
                    "games": [],
                    "urls": [],
                    "labels": [],
                }
            entry = acc[k]
            game = spec["game"]
            if game not in entry["games"]:
                entry["games"].append(game)
            site_id = str(st.get("id") or "").strip()
            if site_id:
                entry["urls"].append(spec["store_base"] + site_id)
            entry["labels"].append(spec["label"])
            # prefer row that has more filled fields
            cur = entry["store"]
            for field in ("name_ch", "name_en", "name_net", "addr_ch",
                          "addr_pid", "lat", "lon", "sid", "city_ch"):
                if not cur.get(field) and st.get(field):
                    cur[field] = st[field]

    rows = []
    for k, entry in acc.items():
        st = entry["store"]
        name = common.unescape(
            str(st.get("name_ch") or st.get("name_en") or st.get("name_net") or "")
        )
        if not name:
            continue
        name_en = common.unescape(str(st.get("name_en") or "")) or None
        name_net = common.unescape(str(st.get("name_net") or "")) or None
        address = common.unescape(str(st.get("addr_ch") or "")) or None
        lat = _as_float(st.get("lat"))
        lng = _as_float(st.get("lon"))
        sid = str(st.get("sid") or "").strip() or None
        city = common.unescape(str(st.get("city_ch") or st.get("city_en") or ""))
        addr_pid = str(st.get("addr_pid") or "").strip() or None

        note_parts = []
        if city:
            note_parts.append("city: " + city)
        if name_net:
            note_parts.append("ALL.Net name: " + name_net)
        if sid:
            note_parts.append("allnet_sid: " + sid)
        if addr_pid:
            note_parts.append("google_place: " + addr_pid)
        note_parts.append("from: " + ", ".join(sorted(set(entry["labels"]))))

        # prefer maimaidx store url when present, else first
        source_url = entry["urls"][0] if entry["urls"] else SOURCES[0]["url"]
        for u in entry["urls"]:
            if "maimaidx.tw" in u:
                source_url = u
                break

        row = {
            "name": name,
            "name_en": name_en,
            "address": address,
            "lat": lat,
            "lng": lng,
            "coord_system": "wgs84",
            "games": list(entry["games"]),
            "source": SOURCE,
            "source_url": source_url,
            "country": "Taiwan",
            "notes": "; ".join(note_parts),
        }
        if sid:
            row["sid"] = sid
        if addr_pid:
            row["google_place_id"] = addr_pid
        rows.append(row)

    # stable order: by name then lat
    rows.sort(key=lambda r: (r.get("name") or "", r.get("lat") or 0))
    return rows


def main():
    ap = argparse.ArgumentParser(
        description="maimaidx.tw + chunithm.tw Taiwan store scraper"
    )
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--outfile", default="maimaidx_tw.json")
    ap.add_argument("--smoke", action="store_true",
                    help="fetch full pages but keep ~few rows per site")
    args = ap.parse_args()

    rows = scrape(smoke=args.smoke)
    if not rows:
        common.die("maimaidx_tw returned 0 stores")

    out_name = "smoke_maimaidx_tw.json" if args.smoke else args.outfile
    path = os.path.join(args.out, out_name)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
