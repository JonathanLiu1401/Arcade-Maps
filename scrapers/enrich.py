"""Enrichment layer: optional per-arcade extras kept OUT of arcades.json.

`data/arcades.json` stays lean (it is the file every visitor downloads).
Everything that is nice-to-have but bulky - transit prose, coin/credit
pricing, photo URLs, opening hours, venue websites - lands in a separate
`data/enrichment.json` that the frontend fetches on demand (research
section G / RECOMMENDATION items 1, 2, 4).

Output shape (`build_enrichment` -> written by merge.py):

    {
      "updated": "2026-07-27",
      "price_defaults": {ISO2: {...}},        # country fallback table
      "country_to_code": {"Japan": "JP", ...},# merge.py's exact strings
      "counts": {...},
      "arcades": {"<merged id>": {...entry...}}
    }

Per-arcade entry keys (every one optional; an arcade with nothing to
say gets no entry at all):

    transport      str   public-transit directions prose (bemanicn)
    price_text     str   venue-level coin/credit price (bemanicn)
    pay_type       int   bemanicn payment-mode enum (kept raw)
    hours          str   "10:00-22:00" / "10:00-02:00 (+1d)" (bemanicn)
    hours_text     str   7-day opening times, Mon-first (ziv)
    images         list  photo URLs, max 3
    fav_count      int   bemanicn community favourites (NOT a rating)
    game_prices    dict  {slug: "5 coins/play (~CNY 5.00)"} (bemanicn)
    game_versions  dict  {slug: "舞萌DX2025"} (bemanicn)
    machine_prices dict  {slug: "PHP 40.00 for 3 songs"} (ziv)
    website        str   venue website (ziv)
    info_text      str   venue free-text information (ziv)
    sources        dict  {field: source} provenance for every key above
    enriched_at    str   ISO date the enrichment was built

Join key: the merged entry's `links.bemanicn` / `links.ziv` URLs, which
are the raw rows' own `source_url` values. That is a stable source-native
identity, so this module needs no hook inside merge.py's clustering -
only a call after the merged ids are assigned.

Measured round-trip on the 2026-07-27 data: 3802/3812 bemanicn rows
(99.7%) and 6960/6985 ziv rows (99.6%) reach a merged entry, and every
`links.*` URL resolves to a raw row (no dangling links in either
direction). The unreachable remainder is rows that DID merge but whose
URL lost a tie: `merged_entry` keeps only the first member's
`bemanicn_url` / `ziv_url`, so when two same-source rows land in one
cluster (verified cause: several 噜彼熊电玩嘉年华 branches merging on
exact-name rules) only the winner's URL is exposed, and within-source
dedupe likewise collapses identical (name, address) pairs to one URL.
Those ~0.4% of rows contribute no enrichment; the surviving member of
the same cluster still does, so no arcade loses its entry - it may just
miss a second listing's extras. Fixing this properly would need a
member-URL list in merged_entry, which is outside this module's
delimited merge.py section.

Text handling: source prose is kept verbatim apart from HTML stripping
and whitespace collapsing. `common.unescape` is deliberately NOT used -
it rewrites en/em dashes, and this is source data (same rule as
bemanicn.py's local _clean).
"""

import os
import sys
from datetime import date
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

OUTFILE = "enrichment.json"
MAX_IMAGES = 3            # per arcade; keeps the file small
MAX_TEXT = 1200           # per free-text field, characters
MAX_PRICE_TEXT = 300      # per per-game price string


# ----------------------------------------------------------- HTML stripping -

class _Stripper(HTMLParser):
    """Tag-stripping parser. <br>/<p>/<div>/<li> become newlines so that
    ZIv's "\\r<br />\\n" price lists and bemanicn's HTML comment blocks do
    not collapse into unreadable run-on text."""

    BREAKS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"}

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BREAKS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        return "".join(self.parts)


def strip_html(text, limit=MAX_TEXT):
    """HTML -> plain text: tags removed, entities decoded, block tags to
    newlines, runs of blank space collapsed. Returns None for anything
    that is empty once stripped. Never raises on malformed markup."""
    if text is None:
        return None
    s = str(text)
    if not s.strip():
        return None
    if "<" in s or "&" in s:
        p = _Stripper()
        try:
            p.feed(s)
            p.close()
            s = p.text()
        except Exception:
            # malformed markup: fall back to the raw string rather than
            # dropping the field
            pass
    # collapse whitespace per line, drop blank lines, join with " / "
    lines = [" ".join(ln.split()) for ln in s.replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln]
    out = " / ".join(lines)
    if not out:
        return None
    if limit and len(out) > limit:
        out = out[:limit - 3].rstrip() + "..."
    return out


def clean_text(text, limit=MAX_TEXT):
    """Whitespace-collapse only (no HTML assumptions), verbatim otherwise."""
    if text is None:
        return None
    out = " ".join(str(text).split())
    if not out:
        return None
    if limit and len(out) > limit:
        out = out[:limit - 3].rstrip() + "..."
    return out


# ------------------------------------------------------- price defaults -----
#
# Community norms, NOT quoted prices. Every entry carries typical:true and
# is displayed as "typical / community / may be outdated" (research
# section 4: no global structured cost-per-play API exists, so country
# defaults are the documented fallback under real per-arcade data).
#
# Merge priority the frontend should apply:
#   1. ziv machine_prices  (per game, community-edited free text)
#   2. bemanicn game_prices/price_text (China coin economy)
#   3. these country defaults, always labelled typical
#
# Keyed by ISO-3166-1 alpha-2. merge.py emits full country NAMES, so
# COUNTRY_TO_CODE below maps its exact strings onto these keys.

PRICE_DEFAULTS_AS_OF = "2026-07-27"

PRICE_DEFAULTS = {
    "JP": {"currency": "JPY", "display": "100 yen/credit typical",
           "notes": "Long-standing game-centre norm; premium starts and "
                    "some titles run 200 yen. Many shops sell cheaper "
                    "multi-credit cards."},
    "US": {"currency": "USD", "display": "USD 1.00-2.00/credit typical",
           "notes": "Card/tap systems (Round1, Dave & Buster's) price in "
                    "chips rather than coins; imports often cost more."},
    "CN": {"currency": "CNY", "display": "varies by store, token-based "
                                         "typical (~1-2 CNY/token, "
                                         "4-6 tokens/play)",
           "notes": "Chinese arcades sell tokens; per-play cost is "
                    "token price x coins per play. bemanicn per-shop "
                    "price + per-title coin data supersedes this."},
    "TW": {"currency": "TWD", "display": "NT$10-30/play typical",
           "notes": "Token or card; rhythm titles at the upper end."},
    "KR": {"currency": "KRW", "display": "500-1000 won/credit typical",
           "notes": "Card systems common; premium modes cost more."},
    "SG": {"currency": "SGD", "display": "SGD 1.00-2.00/credit typical",
           "notes": "Mostly stored-value cards rather than coins."},
    "MY": {"currency": "MYR", "display": "RM 2-4/credit typical",
           "notes": "Card systems standard in mall arcades."},
    "TH": {"currency": "THB", "display": "THB 20-40/credit typical",
           "notes": "Card systems standard in mall arcades."},
    "PH": {"currency": "PHP", "display": "PHP 20-50/play typical "
                                         "(token systems common)",
           "notes": "Quantum and similar chains price in tokens; ZIv "
                    "per-machine displayPrice is far more accurate."},
    "ID": {"currency": "IDR", "display": "IDR 5,000-15,000/play typical",
           "notes": "Card systems standard in mall arcades."},
    "HK": {"currency": "HKD", "display": "HKD 8-15/play typical",
           "notes": "Coin or stored-value card depending on operator."},
    "AU": {"currency": "AUD", "display": "AUD 2-4/credit typical",
           "notes": "Card systems standard; imports often cost more."},
    "GB": {"currency": "GBP", "display": "GBP 1.00-2.00/credit typical",
           "notes": "Rhythm cabs are rare and often priced above "
                    "general-arcade rates."},
    "CA": {"currency": "CAD", "display": "CAD 1.50-2.50/credit typical",
           "notes": "Card/chip systems (Round1 Canada) common."},
}

# merge.py's exact country strings (taken from data/stats.json by_country)
# -> the ISO keys above. Countries absent here simply have no default.
COUNTRY_TO_CODE = {
    "Japan": "JP", "United States": "US", "China": "CN", "Taiwan": "TW",
    "South Korea": "KR", "Singapore": "SG", "Malaysia": "MY",
    "Thailand": "TH", "Philippines": "PH", "Indonesia": "ID",
    "Hong Kong": "HK", "Australia": "AU", "United Kingdom": "GB",
    "Canada": "CA",
}


def price_defaults_table(as_of=None):
    """The PRICE_DEFAULTS table with the typical/source/as_of flags that
    the frontend must surface, ready to serialize."""
    as_of = as_of or PRICE_DEFAULTS_AS_OF
    out = {}
    for code, d in sorted(PRICE_DEFAULTS.items()):
        e = dict(d)
        e["typical"] = True             # never an exact quoted price
        e["source"] = "country_default"
        e["as_of"] = as_of
        out[code] = e
    return out


def price_default_for(country, as_of=None):
    """Country-default price entry for one merge.py country string, or
    None when that country has no curated default."""
    code = COUNTRY_TO_CODE.get(country)
    if code is None:
        return None
    return price_defaults_table(as_of).get(code)


# --------------------------------------------------------- row extraction ---

_BEMANICN_FIELDS = (
    ("transport", "transport"), ("price_text", "price_text"),
    ("pay_type", "pay_type"), ("hours", "hours"),
    ("fav_count", "fav_count"), ("game_prices", "game_prices"),
    ("game_versions", "game_versions"),
)

_ZIV_FIELDS = (
    ("machine_prices", "machine_prices"), ("website", "website"),
    ("hours_text", "hours_text"), ("info_text", "info_text"),
)


def _put(entry, key, value, source):
    """Set entry[key] from `source` if `value` is present and the key is
    not already filled by a higher-priority source."""
    if value in (None, "", [], {}):
        return
    if key in entry:
        return
    entry[key] = value
    entry["sources"][key] = source


def entry_from_rows(bemanicn_rows, ziv_rows):
    """Build one enrichment entry from the raw rows that merged into a
    single arcade. Returns None when nothing enrichable is present.

    Precedence when several rows of the same source merged: first row
    that carries a given field wins (rows arrive in merge order)."""
    entry = {"sources": {}}
    images = []
    for row in bemanicn_rows:
        for out_key, row_key in _BEMANICN_FIELDS:
            _put(entry, out_key, row.get(row_key), "bemanicn")
        thumb = row.get("image_thumb")
        if thumb and thumb not in images:
            images.append(thumb)
    for row in ziv_rows:
        for out_key, row_key in _ZIV_FIELDS:
            _put(entry, out_key, row.get(row_key), "ziv")
        for url in (row.get("pictures") or []):
            if url and url not in images:
                images.append(url)
    if images:
        entry["images"] = images[:MAX_IMAGES]
        # bemanicn thumbs are signed OSS URLs that EXPIRE (an "e=" epoch
        # in the query string, days-to-weeks after the crawl), so
        # consumers must tolerate a 403; ziv pictures are plain hotlinks.
        # When both sources contribute, the bemanicn thumb sorts first
        # and the label names that first source - so treat this as "who
        # led", not "who supplied every URL" (URLs are distinguishable by
        # host: oss.bemanicn.com vs zenius-i-vanisher.com).
        entry["sources"]["images"] = (
            "bemanicn" if any(r.get("image_thumb") for r in bemanicn_rows)
            else "ziv")
    if not entry["sources"]:
        return None
    entry["enriched_at"] = date.today().isoformat()
    return entry


def _index_raw(raw_dir):
    """{source_url: [raw row, ...]} for the two enrichable sources.

    Mirrors merge.py rule (h): a fresh ziv.json supersedes community.json's
    bundled ziv rows, so the fresh file is preferred and community.json is
    only consulted for ziv rows when ziv.json is absent."""
    def path(fn):
        return os.path.join(raw_dir, fn + ".json")

    bemanicn, ziv = {}, {}
    if os.path.exists(path("china_bemanicn")):
        for row in common.load_json(path("china_bemanicn")):
            u = row.get("source_url")
            if u:
                bemanicn.setdefault(u, []).append(row)
    if os.path.exists(path("ziv")):
        for row in common.load_json(path("ziv")):
            u = row.get("source_url")
            if u:
                ziv.setdefault(u, []).append(row)
    elif os.path.exists(path("community")):
        for row in common.load_json(path("community")):
            if (row.get("source") or "") == "ziv" and row.get("source_url"):
                ziv.setdefault(row["source_url"], []).append(row)
    return bemanicn, ziv


def build_enrichment(arcades, raw_dir, updated=None):
    """Build the enrichment payload for already-merged, already-id'd
    arcades. Pure read of raw_dir + the merged list; `arcades` is NOT
    mutated, so arcades.json stays lean."""
    bemanicn_idx, ziv_idx = _index_raw(raw_dir)
    out = {}
    used_b, used_z = set(), set()
    for a in arcades:
        links = a.get("links") or {}
        b_url, z_url = links.get("bemanicn"), links.get("ziv")
        b_rows = bemanicn_idx.get(b_url, []) if b_url else []
        z_rows = ziv_idx.get(z_url, []) if z_url else []
        if not b_rows and not z_rows:
            continue
        entry = entry_from_rows(b_rows, z_rows)
        if entry is None:
            continue
        out[str(a["id"])] = entry
        # count a raw row as "contributing" only when it actually supplied
        # a field: an arcade can carry a link to a row that has no
        # enrichment at all (e.g. a China ziv row merged into a bemanicn
        # shop), and counting those would overstate coverage
        contributed = set(entry["sources"].values())
        if b_rows and "bemanicn" in contributed:
            used_b.add(b_url)
        if z_rows and "ziv" in contributed:
            used_z.add(z_url)
    field_counts = {}
    for e in out.values():
        for k in e["sources"]:
            field_counts[k] = field_counts.get(k, 0) + 1
    counts = {
        "arcades_enriched": len(out),
        "of_total": len(arcades),
        "by_field": dict(sorted(field_counts.items())),
        # "contributed" = the row supplied at least one enrichment field
        "bemanicn_rows_contributed": len(used_b),
        "bemanicn_rows_available": len(bemanicn_idx),
        "ziv_rows_contributed": len(used_z),
        "ziv_rows_available": len(ziv_idx),
    }
    return {
        "updated": updated or date.today().isoformat(),
        "price_defaults": price_defaults_table(),
        "country_to_code": dict(sorted(COUNTRY_TO_CODE.items())),
        "counts": counts,
        "arcades": {k: out[k] for k in sorted(out, key=int)},
    }


def main():
    """Standalone rebuild: reads an existing data/arcades.json rather than
    re-merging, so enrichment can be regenerated without a full merge."""
    import argparse
    import json
    ap = argparse.ArgumentParser(
        description="build data/enrichment.json from raw rows + merged ids")
    ap.add_argument("--raw", default="data_raw")
    ap.add_argument("--out", default="data")
    ap.add_argument("--arcades", default=None,
                    help="merged arcades.json (default: <out>/arcades.json)")
    args = ap.parse_args()
    arc_path = args.arcades or os.path.join(args.out, "arcades.json")
    doc = common.load_json(arc_path)
    arcades = doc["arcades"] if isinstance(doc, dict) else doc
    payload = build_enrichment(arcades, args.raw, doc.get("updated")
                               if isinstance(doc, dict) else None)
    path = os.path.join(args.out, OUTFILE)
    common.save_json(path, payload)
    print("wrote %s" % path)
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
