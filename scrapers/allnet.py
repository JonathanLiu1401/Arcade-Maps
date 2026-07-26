"""SEGA ALL.Net location scraper (location.am-all.net).

JP games:   https://location.am-all.net/alm/location?gm={gm}&lang=ja&ct=1000&at={0..46}
            (ct=1000 is REQUIRED, otherwise the landing form is returned)
Intl games: https://location.am-all.net/alm/location?gm={gm}&lang=en&ct={1000..1015}

Rows: <span class="store_name">NAME</span> <span class="store_address">ADDR</span>
Coordinates live in the GoogleMap button onclick: maps.google.com/maps?q=NAME@LAT,LNG
Store id (sid) lives in the details button onclick: shop?gm=..&sid=NNN
No pagination (verified during recon).

Output schema per row (matches the existing scratch data):
{name, address, lat, lng, region_code, region_label[, sid]}
lat/lng are null when the row has no map button.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

BASE = "https://location.am-all.net/alm/location"

# gm -> (slug, mode). Verified live during recon 2026-07-27.
GAMES = {
    96:  ("maimai_jp",     "jp"),
    98:  ("maimai_intl",   "intl"),
    109: ("chunithm_jp",   "jp"),
    104: ("chunithm_intl", "intl"),
    88:  ("ongeki",        "jp"),
    34:  ("project_diva",  "jp"),
}

_ROW_RE = re.compile(
    r'<span class="store_name">(.*?)</span>\s*'
    r'<span class="store_address">(.*?)</span>(.*?)</li>',
    re.S)
_COORD_RE = re.compile(r'maps\.google\.com/maps\?q=[^@\']*@(-?[\d.]+),(-?[\d.]+)')
_SID_RE = re.compile(r'[?&;]sid=(\d+)')
_AREA_RE = re.compile(r'<h3>[^<]*<span>([^<]*)</span>[^<]*<span>[^<]*</span>')


def parse_page(html_text, region_code, region_label_fallback):
    m = _AREA_RE.search(html_text)
    region_label = common.unescape(m.group(1)) if m else region_label_fallback
    rows = []
    for name, addr, rest in _ROW_RE.findall(html_text):
        row = {
            "name": common.unescape(name),
            "address": common.unescape(addr),
            "lat": None,
            "lng": None,
            "region_code": region_code,
            "region_label": region_label,
        }
        cm = _COORD_RE.search(rest)
        if cm:
            row["lat"] = float(cm.group(1))
            row["lng"] = float(cm.group(2))
        sm = _SID_RE.search(rest)
        if sm:
            row["sid"] = sm.group(1)
        rows.append(row)
    return rows


def scrape_game(gm, mode, sleep=common.DEFAULT_SLEEP, smoke=False):
    """Scrape one game. smoke=True probes a single region only:
    Tokyo (at=12) for jp mode, the first ct for intl mode."""
    out = []
    if mode == "jp":
        areas = [(str(at),
                  "%s?gm=%d&lang=ja&ct=1000&at=%d" % (BASE, gm, at))
                 for at in range(47)]
    elif mode == "intl":
        areas = [(str(ct),
                  "%s?gm=%d&lang=en&ct=%d" % (BASE, gm, ct))
                 for ct in range(1000, 1016)]
    else:
        raise ValueError("mode must be jp or intl")
    if smoke:
        areas = areas[12:13] if mode == "jp" else areas[:1]
    for region_code, url in areas:
        text = common.fetch(url, sleep=sleep)
        if 'store_name' not in text and 'content_box' not in text:
            # landing form or unexpected page: treat as empty area but log it
            print("allnet gm=%d area=%s: no store list markup"
                  % (gm, region_code), file=sys.stderr)
        rows = parse_page(text, region_code, region_code)
        print("allnet gm=%d area=%s: %d stores" % (gm, region_code, len(rows)),
              file=sys.stderr)
        out.extend(rows)
    return out


def main():
    ap = argparse.ArgumentParser(description="ALL.Net location scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--gm", type=int, action="append",
                    help="game id(s); default: all known")
    args = ap.parse_args()
    gms = args.gm or sorted(GAMES)
    wrote = 0
    for gm in gms:
        if gm not in GAMES:
            common.die("unknown gm=%d (known: %s)" % (gm, sorted(GAMES)))
        slug, mode = GAMES[gm]
        rows = scrape_game(gm, mode)
        if not rows:
            common.die("allnet gm=%d (%s) returned 0 rows; refusing to write "
                       "an empty file" % (gm, slug))
        common.save_json(os.path.join(args.out, slug + ".json"), rows)
        print("wrote %s (%d rows)" % (os.path.join(args.out, slug + ".json"),
                                      len(rows)))
        wrote += 1
    if not wrote:
        common.die("nothing scraped")


if __name__ == "__main__":
    main()
