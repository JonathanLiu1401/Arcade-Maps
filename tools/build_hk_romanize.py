"""Regenerate data/hk_romanize.json: Chinese character -> Cantonese readings.

Maintenance tool, like tools/build_china_areas.py. Not part of the weekly
pipeline - Cantonese pronunciation does not change weekly.

    python tools/build_hk_romanize.py
    python tools/build_hk_romanize.py --check

Why this file exists: Hong Kong and Macau are the only places in the dataset
where one venue is published under two names that share no characters. ALL.Net
writes "PIK FU GAME CENTRE" on "WO YI HOP ROAD"; BemaniCN writes "碧富遊戲機" on
"和宜合道". They are the same arcade, and the bridge is not translation but
ROMANIZATION - the English name is the Cantonese reading of the Chinese one.
`scrapers/hk_match.py` reconstructs that reading from this table and compares it
to the Latin text loosely enough to survive the spelling drift between Jyutping
and Hong Kong's older government romanisation.

Source: https://github.com/rime/rime-cantonese, jyut6ping3.chars.dict.yaml,
which is CC BY 4.0 (see the project README; maintained by CanCLID). Attribution
is carried in the generated file's `source` block and in README.md.

The file is one `char<TAB>syllable<TAB>weight%` row per reading, sorted by
syllable, so a character appears once per pronunciation. Up to READINGS_KEPT
readings per character survive here, ordered by the weight the source assigns,
because a name can use a rare reading and dropping it silently loses the match.
Tones are dropped: they are not written in any romanized place name.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "hk_romanize.json")

SRC_URL = ("https://raw.githubusercontent.com/rime/rime-cantonese/master/"
           "jyut6ping3.chars.dict.yaml")

READINGS_KEPT = 3

SOURCE_BLOCK = {
    "url": SRC_URL,
    "repo": "https://github.com/rime/rime-cantonese",
    "file": "jyut6ping3.chars.dict.yaml",
    "license": ("CC BY 4.0 - 粵語計算語言學基礎建設組 (CanCLID), "
                "https://creativecommons.org/licenses/by/4.0/"),
    "contents": ("Jyutping readings per Chinese character, tones stripped, "
                 "at most %d per character ordered by the source's weight."
                 % READINGS_KEPT),
    "used_by": "scrapers/hk_match.py (Hong Kong / Macau cross-script merging)",
    "regenerate": "python tools/build_hk_romanize.py",
}

_ROW = re.compile(r"^(\S)\t([a-z]+)([1-6])?(?:\t(\d+)%)?\s*$")


def parse(text):
    """char -> [reading, ...] ordered by source weight, then first-seen."""
    seen = {}
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        char, syl, _tone, pct = m.groups()
        if not ("㐀" <= char <= "鿿"):
            continue        # punctuation and the odd Latin row in the source
        weight = int(pct) if pct else -1
        bucket = seen.setdefault(char, {})
        # Same syllable can appear under several tones; keep the best weight.
        if syl not in bucket or weight > bucket[syl]:
            bucket[syl] = weight
    out = {}
    for char, bucket in seen.items():
        order = sorted(bucket, key=lambda s: (-bucket[s], s))
        out[char] = order[:READINGS_KEPT]
    return out


def check(table):
    problems = []
    # Characters from real venue names in the dataset. If the table cannot
    # read these, the Hong Kong matcher is broken and the tests would only
    # find out via a merge that silently stopped happening.
    for char, want in [("碧", "bik"), ("富", "fu"), ("天", "tin"),
                       ("旺", "wong"), ("角", "gok"), ("荃", "cyun"),
                       ("灣", "waan"), ("沙", "saa"), ("田", "tin"),
                       ("元", "jyun"), ("朗", "long")]:
        if want not in table.get(char, []):
            problems.append("%s should read %s, got %r"
                            % (char, want, table.get(char)))
    if len(table) < 5000:
        problems.append("only %d characters; the source parse looks broken"
                        % len(table))
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--src", help="local copy of the yaml (skips the fetch)")
    ap.add_argument("--check", action="store_true",
                    help="verify the committed table, write nothing")
    args = ap.parse_args()

    if args.check:
        with open(args.out, encoding="utf-8") as fh:
            table = json.load(fh)["readings"]
        problems = check(table)
        print("hk_romanize.json: %d characters" % len(table))
        for p in problems:
            print("  PROBLEM: " + p)
        return 1 if problems else 0

    if args.src:
        with open(args.src, encoding="utf-8") as fh:
            text = fh.read()
    else:
        print("fetching %s" % SRC_URL)
        with urllib.request.urlopen(SRC_URL, timeout=120) as r:
            text = r.read().decode("utf-8")

    table = parse(text)
    problems = check(table)
    if problems:
        for p in problems:
            print("  PROBLEM: " + p, file=sys.stderr)
        raise SystemExit("refusing to write a table with %d problem(s)"
                         % len(problems))

    payload = {"source": SOURCE_BLOCK,
               "readings": {k: table[k] for k in sorted(table)}}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    print("wrote %s: %d characters" % (args.out, len(table)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
