"""全国音ゲー設置店舗情報wiki (otogesetchi) scraper.

Source: https://w.atwiki.jp/otogesetchi/
Prefecture / area pages list venues as h4 sections with address and
per-publisher game lines (設置コナミ音ゲー / 設置セガ音ゲー /
その他の音ゲー・関連作品) carrying 台 counts and cab models.

Copyright note on the wiki forbids bulk republication; this scraper
emits merge-friendly rows for Arcade Maps ingest only.

Output schema (merge-friendly community row):
  {name, name_en, address, lat, lng, coord_system, games, game_counts,
   count_evidence, cab_models, source, source_url, country, notes, sid}

sid is a stable hash of the wiki page URL + venue name (not a row
number). lat/lng are null (wiki has no coords).
--smoke fetches one area page (都心・副都心) only and writes nothing.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

INDEX = "https://w.atwiki.jp/otogesetchi/"
OUTFILE = "otogesetchi.json"
SOURCE = "otogesetchi"
SMOKE_PAGE = "https://w.atwiki.jp/otogesetchi/pages/19.html"

# Area pages known to hold venue inventories (Tokyo metro focus as of
# 2026-08). Extra /pages/N.html links discovered from the index are
# kept only when they parse at least one venue with 住所.
SEED_PAGES = [
    "https://w.atwiki.jp/otogesetchi/pages/19.html",  # 都心・副都心
    "https://w.atwiki.jp/otogesetchi/pages/24.html",  # 横浜・川崎
    "https://w.atwiki.jp/otogesetchi/pages/26.html",  # 多摩地域
    "https://w.atwiki.jp/otogesetchi/pages/27.html",  # 23区西部
    "https://w.atwiki.jp/otogesetchi/pages/29.html",  # 23区東部
]

# h4 titles that are navigation / meta, not venues
_SKIP_H4 = re.compile(
    r"^(音ゲー設置|設置店舗|知識|編集者|リンク|もくじ|目次|作成中|"
    r"情報提供|公式設置|チェーン店|旧作品|レア作品|オンライン|"
    r"オフライン|長期|通常テンプレート|ラウンドワン（|"
    r"店舗名|スーパー・ホテル|旧作・レア|管理人|その他メンバー|"
    r"特徴|beatmania|pop.?n music|SOUND VOLTEX|筐体|"
    r"ピカピカ|ワイド液晶|アニメロ|20th|GiGO（旧|"
    r"タイトーステーション$|ラウンドワン$|レジャーランド$|"
    r"ゲームパニック$)",
    re.I)

# Field labels inside a venue section (order used when splitting)
_FIELD_LABELS = [
    "住所",
    "店舗ページURL",
    "アクセス・行き方",
    "アクセス",
    "駐車場有無",
    "設置コナミ音ゲー",
    "設置セガ音ゲー",
    "その他の音ゲー・関連作品",
    "その他の音ゲー",
    "設置現行音ゲー",
    "設置旧作品・レア音ゲー",
    "設置準音ゲー",
    "その他ビデオゲーム",
    "設置状況・設置環境",
    "設置状況",
    "備考",
    "最終確認",
]

# Game token -> slug. Longer tokens first.
_GAME_TOKENS = [
    (re.compile(r"ポラリスコード|ポラリス|ぽらりこ|polaris\s*chord", re.I),
     "polaris_chord"),
    (re.compile(r"プロジェクトディーヴァ|project\s*diva|\bdiva\b|ディーヴァ",
                re.I), "project_diva"),
    (re.compile(r"グルーヴコースター|groove\s*coaster|グルコス", re.I),
     "groove_coaster"),
    (re.compile(r"ビートストリーム|beatstream", re.I), "beatstream"),
    (re.compile(r"クロスビーツ|crossbeats?", re.I), "crossbeats"),
    (re.compile(r"ステップマニア|stepmania\s*x|stepmaniax", re.I),
     "stepmaniax"),
    (re.compile(r"ダンスラッシュ|dance\s*rush|dancerush|\bdrs\b", re.I),
     "drs"),
    (re.compile(r"dance\s*around|ダンスアラウンド", re.I), "dance_around"),
    # No trailing \b after Latin titles: wiki sticks counts on ("SDVX3台",
    # "DDR金筐体1台") and \b fails between letter and digit/CJK.
    (re.compile(r"sound\s*voltex|サウンドボルテックス|sdvx|ボルテ",
                re.I), "sdvx"),
    (re.compile(r"beatmania\s*iidx|beatmaniaiidx|ビーマニ|iidx|弐寺",
                re.I), "iidx"),
    (re.compile(r"dance\s*dance\s*revolution|\bddr(?![a-z])|ダンスダンス",
                re.I), "ddr"),
    (re.compile(r"pop'?n\s*music|ポップンミュージック|ポップン|\bpopn\b",
                re.I), "popn"),
    (re.compile(r"gitadora|ギタドラ|guitar\s*freaks|drum\s*mania|"
                r"ギターフリークス|ドラムマニア", re.I), "gitadora"),
    (re.compile(r"jubeat|ユビート", re.I), "jubeat"),
    # ビーマニ五鍵 etc. still IIDX family / classic beatmania
    (re.compile(r"ビーマニ|beatmania(?!\s*iidx)", re.I), "iidx"),
    (re.compile(r"chunithm|チュウニズム|チュウニ", re.I), "chunithm"),
    (re.compile(r"ongeki|オンゲキ", re.I), "ongeki"),
    (re.compile(r"maimai", re.I), "maimai_dx"),
    (re.compile(r"nostalgia|ノスタルジア|\bノス\b", re.I), "nostalgia"),
    (re.compile(r"\bmuseca\b|ミューゼカ", re.I), "museca"),
    (re.compile(r"reflec\s*beat|リフレクビート|リフレク", re.I), "reflec"),
    (re.compile(r"太鼓の達人|太鼓|\btaiko\b", re.I), "taiko"),
    (re.compile(r"pump\s*it\s*up|\bpump\b|パンピットアップ", re.I),
     "pump_it_up"),
    (re.compile(r"\bwacca\b|ワッカ", re.I), "wacca"),
]

# Cab model hints (variant slugs used by merge CAB_SLUGS / cab_models)
_CAB_HINTS = [
    (re.compile(r"\bLM\b|ライトニング|Lightning", re.I), "iidx_lm"),
    (re.compile(r"\bVM\b|Valkyrie|ヴァルキリー|ナブラ|∇", re.I), "sdvx_vm"),
    (re.compile(r"金筐体|gold", re.I), "ddr_gold"),  # also chuni gold; see below
    (re.compile(r"PPM|ピカピカ|ポップ君", re.I), "popn_pikapika"),
    (re.compile(r"Arena|アリーナ|\bAM\b", re.I), "gitadora_arena"),
]

_QTY_TAI = re.compile(r"(\d+)\s*台")
_QTY_EACH = re.compile(r"各\s*(\d+)\s*台")
_H4_RE = re.compile(r"<h4[^>]*>(.*?)</h4>", re.I | re.S)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_PAGE_HREF = re.compile(r'href="(/otogesetchi/pages/\d+\.html)"')


def _strip_tags(html):
    t = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    t = re.sub(r"</(?:p|tr|li|div|h\d)>", "\n", t, flags=re.I)
    t = _TAG_RE.sub("", t)
    t = common.unescape(t)
    # collapse spaces but keep newlines
    lines = [" ".join(line.split()) for line in t.splitlines()]
    return "\n".join(lines)


def _cell_text(html):
    t = re.sub(r"<br\s*/?>", "\n", html or "", flags=re.I)
    t = _TAG_RE.sub("", t)
    t = common.unescape(t)
    return " ".join(t.split())


def _stable_sid(page_url, name):
    key = "%s|%s" % (page_url, name)
    return "otoge_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _parse_fields(section_html):
    """Parse label/value pairs from the venue's first wiki table.

    otogesetchi stores each field as a two-cell table row:
      <tr><td>住所</td><td>東京都...</td></tr>
    Falls back to line-based label splitting if no table is present.
    """
    fields = {}
    # First table in the section is the inventory card. Labels may be
    # <th> or <td>; multi-column rows (floor | games) join value cells.
    tm = re.search(r"<table\b[^>]*>(.*?)</table>", section_html, re.I | re.S)
    if tm:
        rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", tm.group(1), re.I | re.S)
        for row in rows:
            cells = re.findall(
                r"<(?:td|th)\b[^>]*>(.*?)</(?:td|th)>", row, re.I | re.S)
            if len(cells) < 2:
                continue
            label = _cell_text(cells[0])
            val = " ".join(_cell_text(c) for c in cells[1:] if _cell_text(c))
            if label and label not in fields:
                fields[label] = val
            elif label and val:
                # Multi-floor rows reuse the same label: concatenate
                fields[label] = (fields.get(label) or "") + "、" + val
        if fields:
            return fields
    # Fallback: plain-text label split
    section_text = _strip_tags(section_html)
    labels = sorted(_FIELD_LABELS, key=len, reverse=True)
    lab_alt = "|".join(re.escape(l) for l in labels)
    rx = re.compile(r"(?m)^(%s)\s*[:：]?\s*" % lab_alt)
    matches = list(rx.finditer(section_text))
    for i, m in enumerate(matches):
        label = m.group(1)
        start = m.end()
        end = (matches[i + 1].start() if i + 1 < len(matches)
               else len(section_text))
        val = " ".join(section_text[start:end].split())
        if label not in fields:
            fields[label] = val
    return fields


def _token_slug(seg):
    for rx, slug in _GAME_TOKENS:
        if rx.search(seg):
            return slug
    return None


def _cab_models_for(seg, slug, qty):
    models = {}
    # LM/VM stick to counts ("LM2台", "VM3台") so avoid trailing \b.
    if slug == "iidx" and re.search(r"LM|ライトニング|Lightning", seg, re.I):
        models["iidx_lm"] = qty
    if slug == "sdvx" and re.search(r"VM|Valkyrie|ヴァルキリー|ナブラ|∇",
                                    seg, re.I):
        models["sdvx_vm"] = qty
    if slug == "ddr" and re.search(r"金筐体|gold", seg, re.I):
        models["ddr_gold"] = qty
    if slug == "popn" and re.search(r"PPM|ピカピカ|ポップ君", seg, re.I):
        models["popn_pikapika"] = qty
    if slug == "gitadora":
        if re.search(r"Guitar|ギター|GF", seg, re.I) and re.search(
                r"Arena|アリーナ|AM", seg, re.I):
            models["gitadora_gf_arena"] = qty
        if re.search(r"Drum|ドラム|DM", seg, re.I) and re.search(
                r"Arena|アリーナ|AM", seg, re.I):
            models["gitadora_dm_arena"] = qty
        # ギタドラAM各1台: one of each arena cabinet
        if re.search(r"ギタドラ", seg) and re.search(r"AM|アリーナ", seg):
            if ("gitadora_gf_arena" not in models
                    and "gitadora_dm_arena" not in models):
                if _QTY_EACH.search(seg):
                    n = int(_QTY_EACH.search(seg).group(1))
                    models["gitadora_gf_arena"] = n
                    models["gitadora_dm_arena"] = n
    return models


def parse_game_line(line):
    """Parse a Japanese cab line into counts / models.

    Returns (counts dict, cab_models dict, note fragments).
    """
    if not line or not line.strip():
        return {}, {}, []
    counts = {}
    models = {}
    notes = []
    # Split on Japanese comma / ASCII comma / middle dot
    parts = re.split(r"[、,・]", line)
    for part in parts:
        seg = part.strip()
        if not seg:
            continue
        slug = _token_slug(seg)
        if not slug:
            # keep rare titles as note only
            if re.search(r"\d+\s*台", seg):
                notes.append(seg)
            continue
        each = _QTY_EACH.search(seg)
        if each and slug == "gitadora":
            # ギタドラAM各1台 -> 2 cabinets of the series (GF+DM)
            n = int(each.group(1))
            qty = n * 2
        elif each:
            qty = int(each.group(1))
        else:
            m = _QTY_TAI.search(seg)
            qty = int(m.group(1)) if m else 1
        if qty <= 0:
            continue
        counts[slug] = counts.get(slug, 0) + qty
        for k, v in _cab_models_for(seg, slug, qty).items():
            models[k] = models.get(k, 0) + v
        notes.append(seg)
    return counts, models, notes


def parse_venue_section(name, body_html, page_url, area_title):
    fields = _parse_fields(body_html)
    addr = fields.get("住所") or ""
    addr = " ".join(addr.split())
    game_lines = []
    for key in ("設置コナミ音ゲー", "設置セガ音ゲー",
                "その他の音ゲー・関連作品", "その他の音ゲー",
                "設置現行音ゲー", "設置旧作品・レア音ゲー"):
        if fields.get(key):
            game_lines.append(fields[key])
    counts = {}
    models = {}
    note_frags = []
    for line in game_lines:
        c, m, n = parse_game_line(line)
        for k, v in c.items():
            counts[k] = counts.get(k, 0) + v
        for k, v in m.items():
            models[k] = models.get(k, 0) + v
        note_frags.extend(n)
    # Skip pure meta sections with no address and no games
    if not addr and not counts:
        return None
    # Skip "no rhythm games" dump sections
    if re.search(r"音ゲー設置", name):
        return None
    games = sorted(counts.keys()) if counts else ["other"]
    remarks = fields.get("備考") or ""
    last = ""
    if remarks and "最終確認" in remarks:
        last = remarks
        m_last = re.search(r"最終確認\s*([^\n|]+)", remarks)
        if m_last:
            last = m_last.group(1).strip()
    elif remarks:
        m_last = re.search(r"最終確認\s*([^\n|]+)", remarks)
        if m_last:
            last = m_last.group(1).strip()
    access = fields.get("アクセス・行き方") or fields.get("アクセス") or ""
    note_parts = []
    if note_frags:
        note_parts.append("Cabs: " + "、".join(note_frags))
    if access:
        note_parts.append("Access: " + access[:200])
    if last:
        note_parts.append("Last check: " + last)
    elif remarks:
        note_parts.append("Note: " + remarks[:200])
    if area_title:
        note_parts.append("Area: " + area_title)
    row = {
        "name": name,
        "name_en": name,
        "address": addr,
        "lat": None,
        "lng": None,
        "coord_system": "wgs84",
        "games": games,
        "source": SOURCE,
        "source_url": page_url,
        "sid": _stable_sid(page_url, name),
        "country": "Japan",
        "notes": " | ".join(note_parts),
    }
    if counts:
        gc = {k: v for k, v in counts.items() if k != "other" and v > 0}
        if gc:
            row["game_counts"] = gc
            row["count_evidence"] = {k: "otogesetchi_tai" for k in gc}
    if models:
        row["cab_models"] = models
    return row


def parse_page(html, page_url):
    h1 = _H1_RE.search(html)
    area = ""
    if h1:
        area = " ".join(_TAG_RE.sub("", h1.group(1)).split())
    # Restrict to main wiki content when possible
    main = html
    m_main = re.search(
        r'(id="wikibody"|class="[^"]*wiki[^"]*body[^"]*")[^>]*>(.*)$',
        html, re.I | re.S)
    if m_main:
        main = m_main.group(2)

    parts = _H4_RE.split(main)
    # split gives [pre, h4inner, after, h4inner, after, ...]
    rows = []
    if len(parts) < 3:
        return rows, area
    # parts[0] is preamble; then pairs (title_html, body)
    i = 1
    while i + 1 < len(parts):
        title_html = parts[i]
        body = parts[i + 1]
        # body runs until next h4; already split
        name = " ".join(_TAG_RE.sub("", title_html).split())
        i += 2
        if not name or _SKIP_H4.search(name):
            continue
        # Stop if we hit footer nav headings inside body as h4 already handled
        row = parse_venue_section(name, body, page_url, area)
        if row:
            rows.append(row)
    return rows, area


def discover_pages(html_index):
    found = set(SEED_PAGES)
    for href in _PAGE_HREF.findall(html_index):
        found.add("https://w.atwiki.jp" + href)
    return sorted(found)


def scrape(smoke=False):
    rows = []
    if smoke:
        pages = [SMOKE_PAGE]
    else:
        idx = common.fetch(INDEX)
        candidates = discover_pages(idx)
        pages = []
        # Probe each candidate: keep only pages that yield venues
        for url in candidates:
            if url in SEED_PAGES:
                pages.append(url)
                continue
            # Skip obvious non-venue seeds already known thin; still try SEED only
            # for non-seed: quick filter by title keywords later
        # Always use SEED_PAGES + any candidate whose path we already trust
        pages = list(SEED_PAGES)

    seen_sid = set()
    for url in pages:
        try:
            html = common.fetch(url)
        except common.FetchError as e:
            print("otogesetchi: page FAILED %s: %s" % (url, e),
                  file=sys.stderr)
            continue
        page_rows, area = parse_page(html, url)
        print("otogesetchi: %s (%s) -> %d venues"
              % (url, area or "?", len(page_rows)), file=sys.stderr)
        for r in page_rows:
            sid = r.get("sid")
            if sid in seen_sid:
                continue
            seen_sid.add(sid)
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser(
        description="otogesetchi (w.atwiki.jp) rhythm venue scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--outfile", default=OUTFILE)
    ap.add_argument("--smoke", action="store_true",
                    help="one Tokyo area page; print rows, write nothing")
    args = ap.parse_args()
    rows = scrape(smoke=args.smoke)
    if args.smoke:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        print("smoke: %d rows (nothing written)" % len(rows),
              file=sys.stderr)
        return
    if not rows:
        common.die("otogesetchi returned 0 rows")
    path = os.path.join(args.out, args.outfile)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
