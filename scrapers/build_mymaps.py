"""Build Google MyMaps import layers (KMZ + CSV) from data/arcades.json.

Twelve layers mirroring the classic map plus Polaris Chord and two
optional extras. Each KMZ holds a single doc.kml with one MyMaps-style
icon style (icon-1637-XXXXXX-labelson, stock blank pin, distinct color
per layer). Layers with more than MAX_FEATURES (1990, margin under
Google's hard limit of 2000 features per layer) are split into _a/_b
parts.

CSVs (name,address,latitude,longitude,games,cabs,source) mirror each
layer and include coordinate-less members (blank lat/lng); KMZ features
require coordinates so coordinate-less entries appear only in the CSVs.
Layer 11 (China) is restricted to entries WITH coordinates;
china_all_addresses.csv lists ALL China entries (wahlap / bemanicn /
ziv, coordinate-less included, source column tells them apart).

The "File manifest" table in mymaps/README.md is regenerated on every
run (between the MANIFEST markers) so it always lists the real files.
"""

import argparse
import os
import sys
import csv
import io
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

ICON_HREF = "https://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png"
MAX_FEATURES = 1990   # margin under Google's 2000-features-per-layer limit

EAGATE_GAMES = ["polaris_chord", "sdvx", "iidx", "ddr", "gitadora", "jubeat",
                "popn", "nostalgia", "drs", "dance_around", "dance_evo",
                "museca", "reflec"]
ALLNET_GAMES = ["maimai_dx", "chunithm", "ongeki", "project_diva"]
OTHER_BEMANI = {"gitadora", "jubeat", "popn", "nostalgia", "museca", "reflec"}
OTHER_DANCE = {"drs", "dance_around", "dance_evo"}
COMMUNITY_SRC = {"ziv", "round1usa", "community"}


def L(slug, color, title, pred, flag_games=None):
    return {"slug": slug, "color": color, "title": title, "pred": pred,
            "flag_games": flag_games or []}


LAYERS = [
    L("01_all_bemani_japan", "DB4436", "All BEMANI (Japan, eagate)",
      lambda a: "eagate" in a["src"], EAGATE_GAMES),
    L("02_sega_gekichumai", "0288D1", "SEGA geki/chu/mai + Project DIVA (ALL.Net)",
      lambda a: "allnet" in a["src"], ALLNET_GAMES),
    L("03_polaris_chord", "9C27B0", "Polaris Chord",
      lambda a: "polaris_chord" in a["games"]),
    L("04_sdvx", "00ACC1", "SOUND VOLTEX",
      lambda a: "sdvx" in a["games"]),
    L("05_valk_and_lm", "3949AB", "SDVX Valkyrie model + IIDX Lightning Model",
      lambda a: {"sdvx_vm", "iidx_lm"} & set(a["cabs"])),
    L("06_iidx", "F9A825", "beatmania IIDX",
      lambda a: "iidx" in a["games"]),
    L("07_ddr", "E65100", "DanceDanceRevolution",
      lambda a: "ddr" in a["games"]),
    L("08_other_bemani", "7CB342", "Other BEMANI (gitadora/jubeat/popn/nostalgia/museca/reflec)",
      lambda a: OTHER_BEMANI & set(a["games"])),
    L("09_other_dance", "C2185B", "Other dance (DANCERUSH/DANCE aROUND/DanceEvolution)",
      lambda a: OTHER_DANCE & set(a["games"])),
    L("10_all3_gekichumai", "546E7A", "All three: maimai DX + CHUNITHM + ONGEKI",
      lambda a: {"maimai_dx", "chunithm", "ongeki"} <= set(a["games"])),
    L("11_china_optional", "FF5252", "China (optional; WGS-84 pins)",
      lambda a: a["country"] == "China" and a["lat"] is not None),
    L("12_community_worldwide_optional", "795548",
      "Community / worldwide (ZIv, Round1 USA, community; optional)",
      lambda a: COMMUNITY_SRC & set(a["src"])),
]


def kml_color(rgb_hex):
    r, g, b = rgb_hex[0:2], rgb_hex[2:4], rgb_hex[4:6]
    return "ff" + (b + g + r).lower()


def placemark(a, style_id, flag_games):
    desc = ["{}".format(escape(a["addr"] or ""))]
    desc.append("games: " + ", ".join(a["games"]))
    if a["cabs"]:
        desc.append("cabs: " + ", ".join(a["cabs"]))
    desc.append("src: " + ", ".join(a["src"]))
    if a["pref"]:
        desc.append("pref: " + escape(a["pref"]))
    if a["links"].get("gmaps"):
        desc.append(escape(a["links"]["gmaps"]))
    if a["links"].get("ziv"):
        desc.append(escape(a["links"]["ziv"]))
    if a["notes"]:
        desc.append(escape(a["notes"]))
    data = [
        ("address", a["addr"] or ""),
        ("games", ", ".join(a["games"])),
        ("cabs", ", ".join(a["cabs"])),
        ("source", ", ".join(a["src"])),
        ("country", a["country"]),
    ]
    for g in flag_games:
        data.append((g, "yes" if g in a["games"] else "no"))
    for c in ("sdvx_vm", "iidx_lm", "ddr_gold"):
        if c in a["cabs"]:
            data.append((c, "yes"))
    ext = "".join(
        '<Data name="%s"><value>%s</value></Data>'
        % (escape(k), escape(str(v))) for k, v in data)
    return (
        "<Placemark>"
        "<name>%s</name>"
        "<description><![CDATA[%s]]></description>"
        "<styleUrl>#%s</styleUrl>"
        "<ExtendedData>%s</ExtendedData>"
        "<Point><coordinates>%.7f,%.7f,0</coordinates></Point>"
        "</Placemark>"
        % (escape(a["name"]), "<br>".join(desc), style_id, ext,
           a["lng"], a["lat"]))


def kml_doc(title, color, marks):
    style_id = "icon-1637-%s-labelson" % color
    head = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        "<Document><name>%s</name>\n"
        '<Style id="%s"><IconStyle><color>%s</color><scale>1</scale>'
        "<Icon><href>%s</href></Icon></IconStyle>"
        "<LabelStyle><scale>1</scale></LabelStyle></Style>\n"
        % (escape(title), style_id, kml_color(color), ICON_HREF))
    return head + "\n".join(marks) + "\n</Document>\n</kml>\n"


def write_kmz(path, title, color, arcades, flag_games):
    style_id = "icon-1637-%s-labelson" % color
    marks = [placemark(a, style_id, flag_games) for a in arcades]
    kml = kml_doc(title, color, marks)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)
    return len(marks), os.path.getsize(path)


def write_csv(path, arcades):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "address", "latitude", "longitude",
                    "games", "cabs", "source"])
        for a in arcades:
            w.writerow([
                a["name"], a["addr"],
                "" if a["lat"] is None else "%.7f" % a["lat"],
                "" if a["lng"] is None else "%.7f" % a["lng"],
                ";".join(a["games"]), ";".join(a["cabs"]),
                ";".join(a["src"]),
            ])


MANIFEST_BEGIN = "<!-- MANIFEST:BEGIN (generated by build_mymaps.py) -->"
MANIFEST_END = "<!-- MANIFEST:END -->"


def update_readme(out_dir, manifest):
    """Regenerate the file-manifest table between the MANIFEST markers
    in mymaps/README.md from what was actually written."""
    path = os.path.join(out_dir, "README.md")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        text = f.read()
    b, e = text.find(MANIFEST_BEGIN), text.find(MANIFEST_END)
    if b == -1 or e == -1 or e < b:
        print("mymaps/README.md: MANIFEST markers not found; "
              "manifest NOT regenerated", file=sys.stderr)
        return
    lines = ["| File | Layer | KMZ features | CSV rows |",
             "|---|---|---|---|"]
    for slug, title, files, csv_rows in manifest:
        for i, (fname, n) in enumerate(files):
            lines.append("| `%s` | %s | %s | %s |" % (
                fname,
                title if i == 0 else "(part %s)" % fname[-5],
                "{:,}".format(n),
                "{:,} (`%s.csv`)".format(csv_rows) % slug if i == 0
                else ""))
    table = "%s\n%s\n%s" % (MANIFEST_BEGIN, "\n".join(lines), MANIFEST_END)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text[:b] + table + text[e + len(MANIFEST_END):])
    print("mymaps/README.md: manifest regenerated", file=sys.stderr)


def run(data_dir, out_dir):
    doc = common.load_json(os.path.join(data_dir, "arcades.json"))
    arcades = doc["arcades"]
    os.makedirs(out_dir, exist_ok=True)
    report = []
    manifest = []
    for layer in LAYERS:
        members = [a for a in arcades if layer["pred"](a)]
        with_coords = [a for a in members if a["lat"] is not None]
        # split into <=MAX_FEATURES parts
        parts = [with_coords[i:i + MAX_FEATURES]
                 for i in range(0, len(with_coords), MAX_FEATURES)] or [[]]
        files = []
        for pi, part in enumerate(parts):
            if len(parts) == 1:
                fname = layer["slug"] + ".kmz"
                title = layer["title"]
            else:
                fname = "%s_%s.kmz" % (layer["slug"], chr(ord("a") + pi))
                title = "%s (part %s)" % (layer["title"], chr(ord("a") + pi))
            path = os.path.join(out_dir, fname)
            n, size = write_kmz(path, title, layer["color"], part,
                                layer["flag_games"])
            report.append((fname, n, size))
            files.append((fname, n))
        write_csv(os.path.join(out_dir, layer["slug"] + ".csv"), members)
        manifest.append((layer["slug"], layer["title"], files,
                         len(members)))
        skipped = len(members) - len(with_coords)
        print("%-40s %5d members (%d without coords -> CSV only), %d part(s)"
              % (layer["slug"], len(members), skipped, len(parts)),
              file=sys.stderr)
    # china_all_addresses.csv: every China entry (wahlap / bemanicn /
    # ziv), coordinate-less included; source column tells them apart
    china = [a for a in arcades if a["country"] == "China"]
    write_csv(os.path.join(out_dir, "china_all_addresses.csv"), china)
    print("china_all_addresses.csv: %d entries" % len(china), file=sys.stderr)

    update_readme(out_dir, manifest)

    bad = [(f, n, s) for f, n, s in report
           if n > MAX_FEATURES or s > 5 * 1024 * 1024]
    for f, n, s in report:
        print("%-44s %5d features %8.1f KB" % (f, n, s / 1024.0),
              file=sys.stderr)
    if bad:
        raise SystemExit("KMZ over limits: %r" % bad)
    return report


def main():
    ap = argparse.ArgumentParser(description="build MyMaps KMZ/CSV layers")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="mymaps")
    args = ap.parse_args()
    run(args.data, args.out)


if __name__ == "__main__":
    main()
