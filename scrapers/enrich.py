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
    images         list  structured photo records, max 3. Each record is
                         {url, source, credit, license, page_url, tier}
                         with tier in {venue, chain}. http is forced to
                         https. Generic assets/cabs stock shots are NEVER
                         written here (those are frontend-only "game" tier).
    image          str   plain https URL of images[0] (compat mirror for
                         panel.js photoUrl, which reads image/photo fields
                         and only accepts string images[] entries today)
    image_tier     str   winning tier of images[0] ("venue" / "chain"), so
                         the UI does not have to guess
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

import json
import os
import re
import sys
from datetime import date
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_corrections as corrections_mod
import common
import photo_quality
import photos as photos_mod
import prices

OUTFILE = "enrichment.json"
MAX_IMAGES = 3            # per arcade; keeps the file small
MAX_TEXT = 1200           # per free-text field, characters
MAX_PRICE_TEXT = 300      # per per-game price string

# Photo harvest index written by scrapers/photos.py (ZIv pictures without
# skip_pictures). Joined on links.ziv arcade id inside build_enrichment.
PHOTOS_INDEX_FILE = "ziv_photos.json"
QUALITY_CACHE_FILE = "photo_probe_cache.json"

# Honest image tiers (emitted on every image record; never invent a venue
# photo from a stock cabinet shot):
#   venue - real photo of THIS arcade (ZIv pictures, bemanicn thumb)
#   chain - chain storefront/logo, labelled as not this branch (optional)
#   game  - representative cabinet (assets/cabs only; frontend, not here)
#   none  - no photo (entry simply has no images key)
IMAGE_TIER_VENUE = "venue"
IMAGE_TIER_CHAIN = "chain"
IMAGE_TIER_GAME = "game"
IMAGE_TIER_NONE = "none"


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

_HOURS_RANGE_RE = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")


def _clean_hours_text(text):
    """Drop an opening-hours string that only encodes "no hours recorded".

    ZIv returns ["00:00", "00:00", false] for every day of a venue whose hours
    nobody has filled in, which is indistinguishable from real data to a
    truthiness check - and 1,730 raw rows (24.8% of the ZIv set) carried the
    resulting "Mon-Sun 00:00-00:00" into the panel as if it were published
    opening hours. The same default is now rejected at the source in ziv.py;
    this is the belt to that pair of braces, and it also cleans rows already
    sitting in data_raw/ from an earlier crawl.

    Cleaning is per SEGMENT, not per string, because ziv.py drops individual
    zero-length DAYS and this has to agree with it. Dropping only all-zero
    strings would leave 100 entries like
    "Mon 10:00-22:00; Tue-Sun 00:00-00:00" - one real day plus six days of
    default - still asserting hours for the other six. Segment-level dropping
    keeps the Monday and discards the rest, which is what a fresh crawl now
    produces.

    Exact parity with a fresh crawl is not reachable from a formatted string:
    ziv.py collapses consecutive identical days into runs BEFORE formatting, so
    removing days here can leave labels like "Tue-Thu" that a fresh crawl would
    have grouped differently. The output is always a truthful subset of what
    the source published, and the next crawl regenerates it properly.

    A segment with no parseable range at all (a "closed" marker, or some future
    free-text format) is passed through untouched rather than guessed at, and
    the whole string is dropped when nothing but those markers survives - the
    point is to stop asserting hours nobody published, not to invent a second
    opinion about what the source meant.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    # No parseable range anywhere: a bare "Mon-Sun closed", or a free-text
    # format some future crawl invents. Not ours to judge, so hand it back.
    if not _HOURS_RANGE_RE.search(text):
        return text
    kept = []
    for segment in text.split(";"):
        seg = segment.strip()
        if not seg:
            continue
        ranges = _HOURS_RANGE_RE.findall(seg)
        if ranges and all(open_ == close for open_, close in ranges):
            continue              # a zero-length day is not opening hours
        kept.append(seg)
    # Only "closed" markers left standing means every day that claimed to be
    # open was a default, so the venue published nothing usable.
    if not any(_HOURS_RANGE_RE.search(seg) for seg in kept):
        return None
    return "; ".join(kept)


def _put(entry, key, value, source):
    """Set entry[key] from `source` if `value` is present and the key is
    not already filled by a higher-priority source."""
    if value in (None, "", [], {}):
        return
    if key in entry:
        return
    entry[key] = value
    entry["sources"][key] = source


def _as_image_record(item, default_source, default_page_url=None):
    """Normalise a raw picture value into a structured image record.

    Accepts:
      - already-structured dicts from photos.py / prior enrichment
      - plain URL strings (legacy ziv.py --enrich pictures list)
      - bemanicn image_thumb URL strings
    Always forces https. Returns None when nothing usable is present.
    """
    if isinstance(item, dict) and item.get("url"):
        url = photos_mod.force_https(item.get("url"))
        if not url:
            return None
        tier = item.get("tier") or IMAGE_TIER_VENUE
        # Never promote a game/cab stock shot into enrichment as a venue photo.
        if tier == IMAGE_TIER_GAME:
            return None
        return {
            "url": url,
            "source": item.get("source") or default_source,
            "credit": item.get("credit") or (
                photos_mod.ZIV_CREDIT if default_source == "ziv"
                else photos_mod.BEMANICN_CREDIT if default_source == "bemanicn"
                else None),
            "license": item.get("license"),
            "page_url": item.get("page_url") or default_page_url,
            "tier": tier,
        }
    if isinstance(item, str) and item.strip():
        url = photos_mod.force_https(item)
        if not url:
            return None
        credit = (photos_mod.ZIV_CREDIT if default_source == "ziv"
                  else photos_mod.BEMANICN_CREDIT if default_source == "bemanicn"
                  else None)
        return {
            "url": url,
            "source": default_source,
            "credit": credit,
            "license": None,
            "page_url": default_page_url,
            "tier": IMAGE_TIER_VENUE,
        }
    return None


def _collect_images(bemanicn_rows, ziv_rows, photos_index=None):
    """Build the honest venue-photo list for one arcade (max MAX_IMAGES).

    Ranked chain (research 2026-07-30):
      1. ZIv real venue photos (photos index first, then raw row.pictures)
      2. BemaniCN signed image_thumb (expires; UI must fail soft on 401/403)

    Generic assets/cabs/*.jpg stock cabinets are NEVER emitted here. Those
    remain a frontend-only "game" tier, labelled representative-cabinet, and
    must not stand in as a photo of this venue.
    """
    images = []
    seen = set()
    lead_source = None

    def _add(rec, source_name):
        nonlocal lead_source
        if rec is None:
            return
        url = rec.get("url")
        if not url or url in seen:
            return
        if len(images) >= MAX_IMAGES:
            return
        seen.add(url)
        images.append(rec)
        if lead_source is None:
            lead_source = source_name

    # --- tier 1: ZIv venue photos -----------------------------------------
    # Prefer the dedicated harvest index (skip_pictures dropped). Fall back
    # to any pictures already sitting on the raw ziv row (ziv.py --enrich).
    for row in ziv_rows:
        z_url = row.get("source_url")
        page = z_url
        if photos_index:
            for rec in photos_mod.photos_for_ziv_url(z_url, photos_index):
                _add(_as_image_record(rec, "ziv", page), "ziv")
        for p in (row.get("pictures") or []):
            # row.pictures may be URL strings or already-structured records
            if isinstance(p, dict):
                _add(_as_image_record(p, "ziv", page), "ziv")
            else:
                aid = photos_mod.ziv_id_from_url(z_url)
                recs = photos_mod.ziv_image_records(aid, [p]) if aid else []
                if recs:
                    _add(recs[0], "ziv")
                else:
                    _add(_as_image_record(p, "ziv", page), "ziv")

    # --- tier 2: BemaniCN signed thumbs -----------------------------------
    for row in bemanicn_rows:
        thumb = row.get("image_thumb")
        if not thumb:
            continue
        shop_id = photos_mod.bemanicn_id_from_url(row.get("source_url"))
        if isinstance(thumb, dict) and thumb.get("url"):
            rec = photos_mod.bemanicn_image_record(thumb.get("url"), shop_id)
        elif isinstance(thumb, str):
            rec = photos_mod.bemanicn_image_record(thumb, shop_id)
        else:
            rec = None
        _add(rec, "bemanicn")

    return images, lead_source


def entry_from_rows(bemanicn_rows, ziv_rows, photos_index=None,
                    quality_probes=None, merged_images=None):
    """Build one enrichment entry from the raw rows that merged into a
    single arcade. Returns None when nothing enrichable is present.

    Precedence when several rows of the same source merged: first row
    that carries a given field wins (rows arrive in merge order).

    photos_index: optional {ziv_id: [image_record, ...]} from photos.py
    (data_raw/ziv_photos.json). When present, real venue photos are joined
    even if the bulk ziv crawl kept skip_pictures=1.
    """
    entry = {"sources": {}}
    for row in bemanicn_rows:
        for out_key, row_key in _BEMANICN_FIELDS:
            _put(entry, out_key, row.get(row_key), "bemanicn")
    for row in ziv_rows:
        for out_key, row_key in _ZIV_FIELDS:
            value = row.get(row_key)
            if out_key == "hours_text":
                value = _clean_hours_text(value)
            _put(entry, out_key, value, "ziv")

    images, lead = _collect_images(bemanicn_rows, ziv_rows, photos_index)
    # The merged index (photos.build_photo_index) has already deduplicated
    # across every source and picked a best tier, so when it has an answer for
    # this arcade it supersedes the per-source collection rather than being
    # appended to it. It also carries the mirrored-file records that no
    # URL-keyed join can reach.
    if merged_images:
        images = list(merged_images)
        lead = images[0].get("source") or lead
    if images:
        # Rank before anything downstream reads images[0]. A venue's photos
        # arrive in whatever order the source listed them, which is upload
        # order, so the oldest and worst-shaped shot routinely won the hero
        # slot: Round1 Ikebukuro led with a 2012 photo of the backs of
        # players' heads. photo_quality scores what it can actually measure
        # from the file header (real pixel size, aspect against the hero box,
        # and the upload timestamp ZIv embeds in its filenames) and reorders
        # in place, so the panel needs no change and neither does the
        # slideshow: both already read images[] in order.
        # It never sees a pixel, so it cannot judge blur or subject. It moves
        # the small, the badly proportioned and the decade-old down the list,
        # and records why on each entry.
        if quality_probes:
            images = photo_quality.apply_to_images(images, quality_probes)
        entry["images"] = images
        # Self-describing winning tier so the UI does not guess. Only venue
        # (and optionally chain) records are emitted by this module; game-tier
        # stock cabinets live in assets/cabs and are never written here.
        entry["image_tier"] = images[0].get("tier") or IMAGE_TIER_VENUE
        # Plain string mirror of images[0].url so today's panel.js photoUrl()
        # (which only accepts string images[] / image / photo fields) can show
        # a real venue photo without a frontend change. Structured images[] is
        # still the canonical form (credit, page_url, tier).
        if images[0].get("url"):
            entry["image"] = images[0]["url"]
            entry["sources"]["image"] = lead or images[0].get("source") or "ziv"
        entry["sources"]["images"] = lead or images[0].get("source") or "ziv"
        entry["sources"]["image_tier"] = entry["sources"]["images"]

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


def build_enrichment(arcades, raw_dir, updated=None, photos_index=None,
                     photos_path=None):
    """Build the enrichment payload for already-merged, already-id'd
    arcades. Pure read of raw_dir + the merged list; `arcades` is NOT
    mutated, so arcades.json stays lean.

    photos_index / photos_path: optional ZIv picture harvest from
    scrapers/photos.py. When neither is given, raw_dir/ziv_photos.json is
    loaded if present. Without a photos index (and without pictures on the
    raw ziv rows), image coverage stays zero - that is the pre-fix state.
    """
    bemanicn_idx, ziv_idx = _index_raw(raw_dir)
    # Absent-tolerant like every other sidecar here: a fresh clone that
    # has never run build_corrections.py just gets the scraped values.
    corrections = {}
    _cpath = os.path.join(os.path.dirname(raw_dir), "data",
                          "corrections.json")
    if os.path.exists(_cpath):
        try:
            with open(_cpath, encoding="utf-8") as _fh:
                corrections = json.load(_fh).get("venues") or {}
        except (OSError, ValueError):
            corrections = {}
    if photos_index is None:
        path = photos_path or os.path.join(raw_dir, PHOTOS_INDEX_FILE)
        photos_index = photos_mod.load_photos_index(path)
    # Optional and absent-tolerant, like every other sidecar here: the report
    # is produced by a separate crawl (photo_quality.py probes each image's
    # header over a ranged GET), so a fresh clone that has never run it simply
    # keeps source order rather than failing the build.
    # Read the raw PROBE CACHE, not the published report. The report stores
    # each image already scored (verdict, reasons) and drops probe_status and
    # ts on the way out, and score() treats a missing probe_status as "could
    # not measure" - so feeding it the report scores every image "unknown" and
    # silently disables the ranking while looking like it works.
    quality_probes = photo_quality.load_json(
        os.path.join(raw_dir, QUALITY_CACHE_FILE), {}) or {}
    photo_index = photos_mod.load_photo_index(
        os.path.join(raw_dir, photos_mod.PHOTO_INDEX_FILE))
    # Re-key the index off each record's own source page rather than trusting
    # the arcade ids it was written with. Those ids are reassigned on every
    # merge, so an index built one build ago silently hands photos to the
    # wrong venues (3,138 of them, at last count).
    photos_by_source = photos_mod.index_by_source_url(photo_index)
    out = {}
    used_b, used_z = set(), set()
    image_arcades = 0
    image_by_source = {}
    for a in arcades:
        links = a.get("links") or {}
        b_url, z_url = links.get("bemanicn"), links.get("ziv")
        b_rows = bemanicn_idx.get(b_url, []) if b_url else []
        z_rows = ziv_idx.get(z_url, []) if z_url else []
        # The merged index is keyed by ARCADE ID rather than by a source URL,
        # which is the only key that works for China: those photos are
        # mirrored files, not ZIv rows, so a URL join cannot see them. Without
        # this branch 3,210 mirrored China venue photos sit on disk and never
        # reach the site.
        merged_imgs = photos_mod.photos_for_arcade(a, photos_by_source)
        # Even with no raw enrichment fields, a photo alone is enough to emit
        # an entry for this arcade.
        if not b_rows and not z_rows and not merged_imgs and not (
                photos_index and z_url
                and photos_mod.photos_for_ziv_url(z_url, photos_index)):
            continue
        # When the photos index has a hit but raw ziv row is missing (or the
        # bulk crawl dropped pictures), synthesise a minimal ziv row so
        # entry_from_rows can still attach images via source_url.
        if not z_rows and z_url and photos_index and \
                photos_mod.photos_for_ziv_url(z_url, photos_index):
            z_rows = [{"source_url": z_url}]
        entry = entry_from_rows(b_rows, z_rows, photos_index=photos_index,
                                quality_probes=quality_probes,
                                merged_images=merged_imgs)
        # Hand-verified corrections (data/corrections.json, built by
        # scrapers/build_corrections.py from the verification fleet's
        # reports) override the scraped value, and say so: each one
        # carries the url and quote it was read from, so a wrong entry
        # can be traced to its source rather than argued about.
        fixes = (corrections.get(corrections_mod.venue_key(a))
                 or {}).get("fields") if corrections else None
        if fixes:
            if entry is None:
                entry = {"sources": {}}
            for field, rec in sorted(fixes.items()):
                if field not in ("hours", "website"):
                    continue      # games/game_counts live on arcades.json
                key = "hours_text" if field == "hours" else field
                entry[key] = rec["value"]
                entry.setdefault("sources", {})[key] = "verified"
                entry.setdefault("verified", {})[key] = {
                    "url": rec.get("evidence_url"),
                    "quote": rec.get("evidence_quote"),
                    "checked_at": rec.get("checked_at"),
                }
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
        if (z_rows or z_url) and "ziv" in contributed:
            used_z.add(z_url)
        if entry.get("images"):
            image_arcades += 1
            src = entry["sources"].get("images") or "unknown"
            image_by_source[src] = image_by_source.get(src, 0) + 1
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
        # honest photo coverage (venue tier only; cabs are not counted)
        "arcades_with_venue_photos": image_arcades,
        "venue_photos_by_source": dict(sorted(image_by_source.items())),
        "photos_index_ids": len(photos_index or {}),
    }
    payload_date = updated or date.today().isoformat()
    # Measured per-country per-game prices, derived from the quoted prices the
    # rows above just contributed (scrapers/prices.py). The guessed
    # PRICE_DEFAULTS table stays only as a last resort for countries the
    # measurement cannot reach: a hand-written "HKD 8-15/play typical" was
    # wrong by the repo's own data, which quotes HK$6.00 for maimai and
    # CHUNITHM without variance. Measured figures win wherever they exist.
    arcade_countries = {}
    for a in arcades:
        if a.get("country"):
            arcade_countries[str(a["id"])] = a["country"]
    price_table = prices.build_price_table(out, arcade_countries,
                                           as_of=payload_date)
    return {
        "updated": payload_date,
        "prices": price_table,
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
    ap.add_argument("--photos", default=None,
                    help="ziv_photos.json from scrapers/photos.py "
                         "(default: <raw>/ziv_photos.json if present)")
    args = ap.parse_args()
    arc_path = args.arcades or os.path.join(args.out, "arcades.json")
    doc = common.load_json(arc_path)
    arcades = doc["arcades"] if isinstance(doc, dict) else doc
    payload = build_enrichment(
        arcades, args.raw,
        updated=doc.get("updated") if isinstance(doc, dict) else None,
        photos_path=args.photos,
    )
    path = os.path.join(args.out, OUTFILE)
    common.save_json(path, payload)
    print("wrote %s" % path)
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
