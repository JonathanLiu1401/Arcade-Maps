"""Konami e-amusement gate facility search scraper (p.eagate.573.jp).

URL: https://p.eagate.573.jp/game/facility/search/p/list.html
     ?finder=area&gkey={KEY}&pref=JP-{01..47}&paselif=false&page={n}
Cookie: facility_dspcount=50 (50 rows per page)
Rows are div.cl_shop_bloc with data-name / data-address /
data-latitude / data-longitude attributes; PASELI support shows as an
ico_paseli image inside the block. Zero results marker text:
店舗が見つかりませんでした. Follow page=2.. until no rows.

Output schema per row (matches the existing scratch data):
{name, address, lat, lng, region_code, region_label, paseli}
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

BASE = "https://p.eagate.573.jp/game/facility/search/p/list.html"
NO_RESULTS = "店舗が見つかりませんでした"

# gkey -> output slug (slug doubles as the raw filename).
GKEYS = {
    "PLRS":        "polaris_chord",
    "SDVX":        "sdvx",
    "SDVX_VM":     "sdvx_vm",
    "IIDX":        "iidx",
    "IIDX_LN":     "iidx_lm",
    "DDR":         "ddr",
    "DDR20TH":     "ddr_gold",
    "GITADORAGF":  "gitadora_gf",
    "GITADORADM":  "gitadora_dm",
    "GITADORAGFA": "gitadora_gf_arena",
    "GITADORADMA": "gitadora_dm_arena",
    "JUBEAT":      "jubeat",
    "PMSP":        "popn",
    "PMPM":        "popn_pikapika",
    "NOSTALGIA":   "nostalgia",
    "DAN":         "drs",
    "DANCEAROUND": "dance_around",
    "DANEVOAC":    "dance_evo",
    "MUSECA":      "museca",
    "REFLECC":     "reflec",
}

PREF_EN = {
    1: "Hokkaido", 2: "Aomori", 3: "Iwate", 4: "Miyagi", 5: "Akita",
    6: "Yamagata", 7: "Fukushima", 8: "Ibaraki", 9: "Tochigi", 10: "Gunma",
    11: "Saitama", 12: "Chiba", 13: "Tokyo", 14: "Kanagawa", 15: "Niigata",
    16: "Toyama", 17: "Ishikawa", 18: "Fukui", 19: "Yamanashi", 20: "Nagano",
    21: "Gifu", 22: "Shizuoka", 23: "Aichi", 24: "Mie", 25: "Shiga",
    26: "Kyoto", 27: "Osaka", 28: "Hyogo", 29: "Nara", 30: "Wakayama",
    31: "Tottori", 32: "Shimane", 33: "Okayama", 34: "Hiroshima",
    35: "Yamaguchi", 36: "Tokushima", 37: "Kagawa", 38: "Ehime", 39: "Kochi",
    40: "Fukuoka", 41: "Saga", 42: "Nagasaki", 43: "Kumamoto", 44: "Oita",
    45: "Miyazaki", 46: "Kagoshima", 47: "Okinawa",
}

_BLOC_RE = re.compile(r'<div class="cl_shop_bloc"(.*?)(?=<div class="cl_shop_bloc"|<hr\s*/>\s*</div>|$)', re.S)
_ATTR_RE = re.compile(r'data-(name|address|latitude|longitude)="([^"]*)"')
_COUNT_RE = re.compile(r'(\d+)件の店舗が見つかりました')


def parse_page(html_text, region_code, region_label):
    rows = []
    for bloc in _BLOC_RE.findall(html_text):
        attrs = dict(_ATTR_RE.findall(bloc))
        if "name" not in attrs:
            continue
        lat = lng = None
        try:
            if attrs.get("latitude") not in (None, ""):
                lat = float(attrs["latitude"])
            if attrs.get("longitude") not in (None, ""):
                lng = float(attrs["longitude"])
        except ValueError:
            lat = lng = None
        rows.append({
            "name": common.unescape(attrs.get("name", "")),
            "address": common.unescape(attrs.get("address", "")),
            "lat": lat,
            "lng": lng,
            "region_code": region_code,
            "region_label": region_label,
            "paseli": "ico_paseli" in bloc,
        })
    return rows


def scrape_game(gkey, sleep=common.DEFAULT_SLEEP, smoke=False):
    """Scrape one game. smoke=True probes Tokyo (JP-13) only."""
    out = []
    headers = {"Cookie": "facility_dspcount=50"}
    for p in ([13] if smoke else range(1, 48)):
        region_code = "JP-%02d" % p
        region_label = PREF_EN[p]
        page = 1
        pref_rows = []
        expected = None
        seen = set()
        # NOTE: the server CLAMPS page beyond the last page and returns the
        # final page again (verified live), so "until no rows" would loop
        # forever; stop as soon as a page adds no NEW rows (cap 50 pages).
        while page <= 50:
            url = ("%s?finder=area&gkey=%s&pref=%s&paselif=false&page=%d"
                   % (BASE, gkey, region_code, page))
            text = common.fetch(url, extra_headers=headers, sleep=sleep)
            if NO_RESULTS in text:
                break
            m = _COUNT_RE.search(text)
            if m:
                expected = int(m.group(1))
            rows = parse_page(text, region_code, region_label)
            new = [r for r in rows
                   if (r["name"], r["address"]) not in seen]
            if not new:
                break
            seen.update((r["name"], r["address"]) for r in new)
            pref_rows.extend(new)
            if expected is not None and len(pref_rows) >= expected:
                break
            page += 1
        if expected is not None and expected != len(pref_rows):
            print("WARNING eagate %s %s: page said %d stores, parsed %d"
                  % (gkey, region_code, expected, len(pref_rows)),
                  file=sys.stderr)
        out.extend(pref_rows)
    return out


def main():
    ap = argparse.ArgumentParser(description="eagate facility scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--gkey", action="append",
                    help="game key(s); default: all known")
    ap.add_argument("--allow-empty", action="store_true",
                    help="write a file even when 0 rows were found "
                         "(for tiny near-dead games)")
    args = ap.parse_args()
    keys = args.gkey or sorted(GKEYS)
    for gkey in keys:
        if gkey not in GKEYS:
            common.die("unknown gkey=%s (known: %s)" % (gkey, sorted(GKEYS)))
        slug = GKEYS[gkey]
        rows = scrape_game(gkey)
        print("eagate %s (%s): %d rows" % (gkey, slug, len(rows)),
              file=sys.stderr)
        if not rows and not args.allow_empty:
            common.die("eagate %s returned 0 rows; pass --allow-empty if the "
                       "game really has no locations" % gkey)
        common.save_json(os.path.join(args.out, slug + ".json"), rows)
        print("wrote %s (%d rows)" % (os.path.join(args.out, slug + ".json"),
                                      len(rows)))


if __name__ == "__main__":
    main()
