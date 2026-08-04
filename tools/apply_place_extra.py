# -*- coding: utf-8 -*-
"""Apply tools/place_extra_seed.json into each locale place:{} block in i18n.js.

Uses brace-counting so strings containing {src} do not truncate the block.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "js" / "i18n.js"
SEED = Path(__file__).with_name("place_extra_seed.json")

LANGS = [
    "en", "zh-Hans", "zh-Hant", "ja", "ko", "id", "ms", "th", "vi",
    "fil", "es", "fr", "de", "pt", "it", "ru",
]


def find_lang(text: str, code: str):
    m = re.search(r'["\']' + re.escape(code) + r'["\']\s*:\s*\{', text)
    if not m:
        m = re.search(r"\b" + re.escape(code) + r":\s*\{", text)
    return m


def extract_brace_block(text: str, open_brace_index: int) -> tuple[int, int]:
    """Return [start, end) of {...} starting at open_brace_index."""
    assert text[open_brace_index] == "{"
    depth = 0
    i = open_brace_index
    in_str = False
    esc = False
    quote = ""
    while i < len(text):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        else:
            if ch in ("'", '"'):
                in_str = True
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return open_brace_index, i + 1
        i += 1
    raise ValueError("unbalanced braces")


def strip_extras(body: str) -> str:
    body = re.sub(r",\s*tap_to_copy:[\s\S]*$", "", body)
    body = re.sub(r'(copy_failed:\s*"[^"]*")(\s*)$', r"\1,\2", body, count=1)
    return body


def main() -> None:
    EXTRA = json.loads(SEED.read_text(encoding="utf-8"))
    text = I18N.read_text(encoding="utf-8")

    for code in LANGS:
        if code not in EXTRA:
            print("skip missing EXTRA", code)
            continue
        lm = find_lang(text, code)
        if not lm:
            print("no lang", code)
            continue
        # find place: { after language start
        search_from = lm.end()
        # next language start bound
        bounds = []
        for other in LANGS:
            if other == code:
                continue
            om = find_lang(text[search_from:], other)
            if om:
                bounds.append(search_from + om.start())
        lang_end = min(bounds) if bounds else len(text)
        segment = text[search_from:lang_end]
        pm = re.search(r"place:\s*\{", segment)
        if not pm:
            print("no place", code)
            continue
        brace_open = search_from + pm.end() - 1  # points at {
        b0, b1 = extract_brace_block(text, brace_open)
        body = text[b0 + 1 : b1 - 1]
        body = strip_extras(body)
        keys = EXTRA[code]
        add = "".join(
            "\n        %s: %s," % (k, json.dumps(v, ensure_ascii=False))
            for k, v in keys.items()
        )
        new_place = "place: {" + body.rstrip() + add + "\n      }"
        # replace from "place:" start
        place_start = search_from + pm.start()
        text = text[:place_start] + new_place + text[b1:]
        print("ok", code)

    I18N.write_text(text, encoding="utf-8", newline="\n")
    t2 = I18N.read_text(encoding="utf-8")
    # Orphan corruption put bare text after a closed place object:
    #   }, may be outdated{date}",
    # without a key name before it. A normal community_from string has
    # {src} before that phrase, so require a newline-ish junk form.
    if re.search(r'\n\s*\}, may be outdated', t2):
        raise SystemExit("corruption marker still present")
    # Brace-count extract ja place and check for Japanese tap string.
    jm = re.search(r"\bja:\s*\{", t2)
    if jm:
        # find place within ja block roughly
        rest = t2[jm.start() :]
        pm = re.search(r"place:\s*\{", rest)
        if pm:
            b0 = jm.start() + pm.end() - 1
            _, b1 = extract_brace_block(t2, b0)
            body = t2[b0:b1]
            print("verify ja tap", "\u30bf\u30c3\u30d7" in body)
            print("verify ja filters", "\u30d5\u30a3\u30eb\u30bf\u30fc" in body)
    print("file bytes", len(t2.encode("utf-8")))


if __name__ == "__main__":
    main()
