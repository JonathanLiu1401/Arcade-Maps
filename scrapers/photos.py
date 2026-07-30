"""Real venue photo harvest for Arcade Maps enrichment.

Why this module exists
----------------------
The weekly ZIv crawl keeps `skip_pictures=1` so `data_raw/ziv.json` ships with
zero picture URLs, and `data/enrichment.json` therefore had no `images`. The
place panel fell through to generic `assets/cabs/<game>.jpg` stock shots and
presented them as if they were photos of that arcade. That is the defect.

This module is the picture-only harvest path. It does NOT rewrite the bulk
ZIv crawl (that lives in ziv.py, owned elsewhere). It:

  1. Queries Zenius-I-Vanisher WITHOUT skip_pictures for selected countries.
  2. Stores up to MAX_IMAGES absolutePaths per arcade, keyed by ZIv arcade id.
  3. Forces http -> https so GitHub Pages does not block mixed content.
  4. Never mirrors the JPEG tree into the repo (no licence grant for that).

BemaniCN `image_thumb` is also shaped here when a raw row already carries it
(re-signed OSS URL from the weekly bemanicn detail crawl). This module does
not re-crawl all of China; signed thumbs expire and must come from a fresh
bemanicn detail fetch.

Output file (default): data_raw/ziv_photos.json

    {
      "updated": "YYYY-MM-DD",
      "source": "ziv",
      "max_images": 3,
      "coverage": {"Japan": {"arcades": N, "with_pics": M}, ...},
      "by_ziv_id": {
        "88": [
          {
            "url": "https://zenius-i-vanisher.com/pictures/....jpg",
            "source": "ziv",
            "credit": "Community photo via Zenius-I-Vanisher",
            "license": null,
            "page_url": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=88",
            "tier": "venue",
            "picture_id": 51434
          }
        ]
      }
    }

enrich.py reads this file (or an explicit path) and joins on the merged
entry's `links.ziv` arcade id. See enrich.image_record / entry_from_rows.

Licence / courtesy (not legal advice)
-------------------------------------
ZIv publishes no public photo licence or hotlink policy. AbsolutePaths are
publicly reachable today. Prefer lazy load of at most 1-3 images when a
detail panel opens, always show the credit line, and deep-link the ZIv
arcade page. Do not bulk-hotlink every pin on map load. Do not rehost the
picture tree on GitHub Pages without written permission from ZIv.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
# NOTE: do NOT import ziv or enrich at module top-level. ziv.py imports
# enrich, and enrich imports this module - a cycle would leave photos_mod
# half-initialised. USA series ids and the query URL are duplicated below
# (stable API surface; keep in sync with scrapers/ziv.py if it changes).

OUTFILE = "ziv_photos.json"
MAX_IMAGES = 3

API = "https://zenius-i-vanisher.com/api/arcades.php"

# Mirror of ziv.USA_SERIES + USA_EXTRA_SERIES (US per-series fetch only).
# Kept local to avoid the enrich <-> ziv import cycle.
_USA_SERIES_IDS = sorted({
    1, 2, 3, 4, 5, 7, 8, 12, 18, 173, 267, 284, 506, 549, 643, 694,
    766, 1281, 1366, 1536, 1556,
})

# Countries to harvest by default when --country is omitted. Spellings are
# ZIv's own; "USA" is the per-series United States sentinel (unsegmented
# country=United States returns HTTP 500).
DEFAULT_COUNTRIES = [
    "Japan",
    "USA",
    "Philippines",
    "United Kingdom",
    "China",
    "Thailand",
    "Canada",
    "Singapore",
    "Spain",
    "Australia",
]

ZIV_ARCADE_URL = "https://zenius-i-vanisher.com/v5.2/arcade.php?id=%s"
ZIV_CREDIT = "Community photo via Zenius-I-Vanisher"
BEMANICN_CREDIT = "Photo: BemaniCN community map"


def _query_url(country, pictures=True, series_id=None):
    """ZIv country query URL. Pictures are ON by default in this module."""
    import urllib.parse
    url = (API + "?action=query&country=" + urllib.parse.quote(country)
           + "&skip_visitors=1&skip_comments=1")
    if not pictures:
        url += "&skip_pictures=1"
    if series_id is not None:
        url += "&series_id=%d" % series_id
    return url

_ZIV_ID_RE = re.compile(r"arcade\.php\?id=(\d+)", re.I)
_BEMANICN_ID_RE = re.compile(r"map\.bemanicn\.com/s/(\d+)", re.I)


# -------------------------------------------------------------- URL helpers --


def force_https(url):
    """Upgrade http:// to https://. Leaves other schemes / relative paths alone.

    GitHub Pages is served over HTTPS; an http image URL is mixed content and
    the browser blocks it. Live check 2026-07-30: ZIv picture paths return
    200 image/jpeg over https.
    """
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    if u.startswith("http://"):
        return "https://" + u[7:]
    return u


def ziv_id_from_url(source_url):
    """Parse the numeric arcade id out of a ZIv arcade.php URL, or None."""
    if not source_url:
        return None
    m = _ZIV_ID_RE.search(str(source_url))
    return m.group(1) if m else None


def bemanicn_id_from_url(source_url):
    if not source_url:
        return None
    m = _BEMANICN_ID_RE.search(str(source_url))
    return m.group(1) if m else None


def image_record(url, source, credit, page_url, license=None, tier="venue",
                 picture_id=None):
    """One self-describing photo record for enrichment.images[].

    tier is one of:
      venue  - a real photo of THIS arcade
      chain  - chain storefront / logo, NOT this branch
      game   - representative cabinet photo, NOT this venue
      none   - no photo (normally omitted rather than emitted)
    """
    https_url = force_https(url)
    if not https_url:
        return None
    rec = {
        "url": https_url,
        "source": source,
        "credit": credit,
        "license": license,
        "page_url": page_url,
        "tier": tier,
    }
    if picture_id is not None:
        rec["picture_id"] = picture_id
    return rec


def ziv_image_records(ziv_id, pictures_raw, max_images=MAX_IMAGES):
    """Build up to max_images venue records from a ZIv pictures[] payload.

    Accepts either the live API shape (list of {id, absolutePath}) or a plain
    list of URL strings (as ziv.py --enrich already normalises).
    """
    if not ziv_id or not pictures_raw:
        return []
    page = ZIV_ARCADE_URL % ziv_id
    out, seen = [], set()
    for p in pictures_raw:
        pic_id = None
        if isinstance(p, dict):
            url = p.get("absolutePath") or p.get("url")
            pic_id = p.get("id")
        else:
            url = p
        rec = image_record(
            url, source="ziv", credit=ZIV_CREDIT, page_url=page,
            license=None, tier="venue", picture_id=pic_id,
        )
        if rec is None or rec["url"] in seen:
            continue
        seen.add(rec["url"])
        out.append(rec)
        if len(out) >= max_images:
            break
    return out


def bemanicn_image_record(thumb_url, shop_id):
    """Shape a bemanicn signed thumb into a venue image record.

    The OSS URL carries token + e= expiry and must be re-fetched weekly.
    UI must fail soft on 401/403.
    """
    if not thumb_url:
        return None
    page = None
    if shop_id is not None:
        page = "https://map.bemanicn.com/s/%s" % shop_id
    return image_record(
        thumb_url, source="bemanicn", credit=BEMANICN_CREDIT,
        page_url=page, license=None, tier="venue",
    )


# -------------------------------------------------------------- ZIv harvest --


def _pictures_from_payload(payload):
    """{ziv_id_str: [raw picture entries...]} from one API response body."""
    out = {}
    arcades = payload.get("arcades") if isinstance(payload, dict) else payload
    if isinstance(arcades, dict):
        arcades = list(arcades.values())
    if not isinstance(arcades, list):
        return out
    for a in arcades:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("id") or a.get("arcadeid") or "")
        if not aid:
            continue
        pics = a.get("pictures") or []
        if not pics:
            # still count the arcade for coverage; empty list means no pics
            out.setdefault(aid, [])
            continue
        bucket = out.setdefault(aid, [])
        for p in pics:
            bucket.append(p)
    return out


def harvest_country(country):
    """Live ZIv query with pictures enabled. Returns
    (by_id_raw_pictures, n_arcades, n_with_pics).

    country is ZIv's spelling. Use 'USA' for the per-series United States
    path (same reason as ziv.fetch_usa).
    """
    if country.upper() == "USA" or country == "United States":
        return _harvest_usa()
    url = _query_url(country, pictures=True)
    payload = json.loads(common.fetch(url, timeout=120))
    by_id = _pictures_from_payload(payload)
    n_arcades = len(by_id)
    n_with = sum(1 for pics in by_id.values() if pics)
    return by_id, n_arcades, n_with


def _harvest_usa():
    """Per-series United States picture harvest (country query 500s)."""
    merged = {}
    for sid in _USA_SERIES_IDS:
        url = _query_url("United States", pictures=True, series_id=sid)
        try:
            payload = json.loads(common.fetch(url, timeout=120))
        except common.FetchError as e:
            print("photos USA series %s failed: %s" % (sid, e),
                  file=sys.stderr)
            continue
        part = _pictures_from_payload(payload)
        for aid, pics in part.items():
            bucket = merged.setdefault(aid, [])
            for p in pics:
                # de-dupe by absolutePath / bare url
                if isinstance(p, dict):
                    key = p.get("absolutePath") or p.get("url") or p.get("id")
                else:
                    key = p
                existing_keys = set()
                for q in bucket:
                    if isinstance(q, dict):
                        existing_keys.add(
                            q.get("absolutePath") or q.get("url") or q.get("id"))
                    else:
                        existing_keys.add(q)
                if key not in existing_keys:
                    bucket.append(p)
    n_arcades = len(merged)
    n_with = sum(1 for pics in merged.values() if pics)
    return merged, n_arcades, n_with


def harvest(countries=None, max_images=MAX_IMAGES):
    """Harvest pictures for many countries. Returns the ziv_photos payload."""
    countries = list(countries or DEFAULT_COUNTRIES)
    by_ziv_id = {}
    coverage = {}
    for country in countries:
        label = "United States" if country.upper() == "USA" else country
        print("photos: harvesting %s ..." % label, file=sys.stderr)
        try:
            raw_by_id, n_arcades, n_with = harvest_country(country)
        except common.FetchError as e:
            print("photos: %s FAILED: %s" % (label, e), file=sys.stderr)
            coverage[label] = {
                "arcades": 0, "with_pics": 0, "error": str(e),
            }
            continue
        for aid, pics in raw_by_id.items():
            recs = ziv_image_records(aid, pics, max_images=max_images)
            if not recs:
                continue
            # merge across countries only if same id reappears (should not)
            existing = by_ziv_id.get(aid) or []
            seen = {r["url"] for r in existing}
            for r in recs:
                if r["url"] not in seen and len(existing) < max_images:
                    existing.append(r)
                    seen.add(r["url"])
            if existing:
                by_ziv_id[aid] = existing
        coverage[label] = {
            "arcades": n_arcades,
            "with_pics": n_with,
            "pct": round(100.0 * n_with / n_arcades, 1) if n_arcades else 0.0,
        }
        print("photos: %s -> %d arcades, %d with pics (%.1f%%)"
              % (label, n_arcades, n_with,
                 coverage[label]["pct"]), file=sys.stderr)
    total_a = sum(c.get("arcades", 0) for c in coverage.values())
    total_p = sum(c.get("with_pics", 0) for c in coverage.values())
    return {
        "updated": date.today().isoformat(),
        "source": "ziv",
        "max_images": max_images,
        "coverage": coverage,
        "totals": {
            "arcades": total_a,
            "with_pics": total_p,
            "pct": round(100.0 * total_p / total_a, 1) if total_a else 0.0,
            "ids_with_records": len(by_ziv_id),
        },
        "by_ziv_id": {k: by_ziv_id[k] for k in sorted(by_ziv_id, key=lambda x: int(x) if x.isdigit() else x)},
    }


def load_photos_index(path):
    """Load a previously written ziv_photos.json, or {} on miss/bad file."""
    if not path or not os.path.exists(path):
        return {}
    try:
        doc = common.load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    by_id = doc.get("by_ziv_id") if isinstance(doc, dict) else None
    return by_id if isinstance(by_id, dict) else {}


def photos_for_ziv_url(source_url, photos_index):
    """Look up structured image records for a ZIv source_url."""
    if not photos_index:
        return []
    aid = ziv_id_from_url(source_url)
    if not aid:
        return []
    recs = photos_index.get(aid) or photos_index.get(str(aid)) or []
    return list(recs) if isinstance(recs, list) else []


# ============================================================================
# MERGED PHOTO INDEX  (data_raw/photo_index.json)
# ============================================================================
#
# Everything below is additive. The ZIv functions above keep their exact
# signatures because enrich.py imports load_photos_index, photos_for_ziv_url,
# image_record, ziv_image_records, force_https, ziv_id_from_url and
# bemanicn_id_from_url. Nothing above this line changed.
#
# The merged index unifies four harvests into one file keyed by ARCADE ID:
#
#   data_raw/ziv_photos.json      keyed by ZIv arcade id  -> join via links.ziv
#   data_raw/chain_photos.json    keyed by arcade id      (superset of ziv_photos
#                                                          for US/UK/PH/SG/JP)
#   data_raw/bemanicn_photos.json keyed by BemaniCN shop id -> carries arcade_id
#   data_raw/street_photos.json   keyed by arcade id      (currently empty:
#                                                          status rejected_empty)
#
# Output shape:
#
#   {
#     "updated": "YYYY-MM-DD",
#     "snapshot": {"arcades_path": ..., "sha256": ..., "arcades": 13534, ...},
#     "sources": {...per-source provenance and licence...},
#     "counts": {...},
#     "coverage": {...per-country before/after...},
#     "link_outs": {"<arcade_id>": [ {page_url, ...} ]},
#     "by_arcade_id": {
#       "<arcade_id>": {
#         "images": [ {url|file, source, credit, license, license_url,
#                      page_url, tier, distance_m?, w?, h?}, ... ],
#         "best_tier": "venue" | "chain" | null,
#         "join": {"ziv_id": "1110", "bemanicn_shop_id": "42"}
#       }
#     }
#   }
#
# Conventions the consumer (enrich.py) can rely on:
#   - MIRRORED images carry `file` (repo-relative path) and NO `url`.
#   - HOTLINKED images carry `url` (absolute https) and NO `file`.
#     bemanicn_photos.json sets both to the same repo path; we normalise to
#     `file` only, so a renderer never treats a repo path as a remote URL.
#   - link_outs live in their own top-level key. They have no url and no file
#     and MUST NOT be merged into images[]: enrich.py mirrors images[0].url
#     into entry["image"] and the panel renders whatever string it finds.
#   - best_tier is "venue" or null. "chain" is in the enum because the brief
#     asks for it, but no chain-tier image is licence-clean, so nothing emits
#     it today. street tier is likewise empty (rejected_empty upstream).

PHOTO_INDEX_FILE = "photo_index.json"

# Tier precedence: a real venue photo beats a street-level frontage beats a
# chain image. Lower number wins.
TIER_RANK = {
    "venue": 0,
    "street_near": 1,
    "street_far": 2,
    "chain": 3,
}
# Tiers that are allowed into images[] at all. "reject" never ships.
SHIPPABLE_TIERS = ("venue", "street_near", "street_far", "chain")

# Within venue tier, prefer the source that gives the biggest usable picture.
# ziv/commons are full-size hotlinks; bemanicn is a 150-200px thumbnail.
SOURCE_RANK = {
    "wikimedia_commons": 0,
    "ziv": 1,
    "bemanicn": 2,
    "kartaview": 3,
    "mapillary": 3,
}

MERGE_INPUTS = (
    "chain_photos.json",
    "ziv_photos.json",
    "bemanicn_photos.json",
    "street_photos.json",
)

# The repo's own hero gate, mirrored from data_raw/photo_quality.json
# thresholds so "hero capable" here means the same thing it means there.
HERO_MIN_W = 416
HERO_MIN_H = 148

# Any "scheme:" prefix. Used to reject ftp:/data:/javascript: rather than
# silently treating them as repo-relative file paths.
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def _read_json(path):
    """load_json that returns None instead of raising on a missing/bad file."""
    if not path or not os.path.exists(path):
        return None
    try:
        return common.load_json(path)
    except (OSError, ValueError):
        return None


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def arcade_snapshot(arcades_path):
    """Read data/arcades.json ONCE and return (records, meta).

    Every count in the merged index is derived from this single snapshot.
    Another agent may be rewriting arcades.json concurrently; the meta block
    records size + sha256 + mtime so the numbers are reproducible against a
    known byte state rather than "whatever the file said at some point".
    """
    doc = common.load_json(arcades_path)
    arcades = doc.get("arcades") if isinstance(doc, dict) else doc
    st = os.stat(arcades_path)
    meta = {
        "arcades_path": arcades_path.replace("\\", "/"),
        "arcades": len(arcades),
        "bytes": st.st_size,
        "mtime": _datetime.datetime.fromtimestamp(
            st.st_mtime, _datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": _sha256_file(arcades_path),
        "updated_field": doc.get("updated") if isinstance(doc, dict) else None,
    }
    return arcades, meta


def _norm_record(rec, source_default=None):
    """Normalise one harvested record to the merged-index field contract.

    Returns None when the record has neither a url nor a file (a link-out
    smuggled into an images list, for example).
    """
    if not isinstance(rec, dict):
        # A bare URL string is accepted for tolerance with older files.
        u = force_https(rec)
        if not u:
            return None
        rec = {"url": u}
    out = {}
    url = (rec.get("url") or "").strip() if isinstance(
        rec.get("url"), str) else rec.get("url")
    fil = (rec.get("file") or "").strip() if isinstance(
        rec.get("file"), str) else rec.get("file")
    # bemanicn sets url == file == repo-relative path. A repo path is not a
    # URL; collapse those to `file` so a renderer never hotlinks a local path.
    # Anything carrying some OTHER scheme (ftp:, data:, javascript:) is not a
    # repo path either and must be dropped, never demoted to a file.
    if url and not str(url).lower().startswith(("http://", "https://", "//")):
        if _SCHEME_RE.match(str(url)):
            return None
        fil = fil or url
        url = None
    if fil:
        out["file"] = str(fil).replace("\\", "/")
    elif url:
        u = force_https(url)
        if not u:
            return None
        if u.startswith("//"):          # protocol-relative is mixed content
            u = "https:" + u
        if not u.startswith("https://"):
            return None
        out["url"] = u
    else:
        return None
    out["source"] = rec.get("source") or source_default
    out["credit"] = rec.get("credit")
    out["license"] = rec.get("license")
    if rec.get("license_url"):
        out["license_url"] = rec["license_url"]
    out["page_url"] = rec.get("page_url") or rec.get("source_url")
    tier = rec.get("tier") or "venue"
    if tier not in SHIPPABLE_TIERS:
        return None                     # "reject" / "link_out" never ship
    out["tier"] = tier
    for opt in ("distance_m", "w", "h", "picture_id", "sha256", "bytes",
                "artist", "commons_file", "extreme_aspect", "dup_count"):
        if rec.get(opt) is not None:
            out[opt] = rec[opt]
    # ziv/commons carry width/height under other names in some files
    if "w" not in out and rec.get("width") is not None:
        out["w"] = rec["width"]
    if "h" not in out and rec.get("height") is not None:
        out["h"] = rec["height"]
    return out


def _dedup_key(rec):
    """URL/file identity for dedup."""
    return ("f:" + rec["file"]) if rec.get("file") else ("u:" + rec["url"])


# Quality verdicts from data_raw/photo_quality.json, worst last. A "reject"
# must never become images[0] while a "good" sibling exists: enrich.py mirrors
# images[0] into entry["image"] and the panel renders it as the hero.
VERDICT_RANK = {"good": 0, "ok": 1, "unknown": 2, None: 2, "weak": 3,
                "reject": 4}


def _sort_key(rec):
    """Ordering within one arcade. MUST run AFTER quality annotation, or the
    verdict and the ziv w/h (which only photo_quality.json supplies) are
    invisible here and ordering collapses to arbitrary string order."""
    return (
        TIER_RANK.get(rec.get("tier"), 9),
        VERDICT_RANK.get(rec.get("quality_verdict"), 2),
        -(rec.get("quality_score") if rec.get("quality_score") is not None
          else -1),
        SOURCE_RANK.get(rec.get("source"), 8),
        # bigger picture first within a source
        -(rec.get("w") or 0) * (rec.get("h") or 0),
        _dedup_key(rec),
    )


def _annotate_quality(rec, qmap):
    """Fold photo_quality.json fields onto a record, in place."""
    q = qmap.get(rec.get("url") or "")
    if not q:
        return rec
    if q.get("verdict"):
        rec["quality_verdict"] = q["verdict"]
    if q.get("score") is not None:
        rec["quality_score"] = q["score"]
    if "w" not in rec and q.get("width"):
        rec["w"] = q["width"]
    if "h" not in rec and q.get("height"):
        rec["h"] = q["height"]
    return rec


def build_photo_index(raw_dir="data_raw", arcades_path="data/arcades.json",
                      quality_path=None, max_images=MAX_IMAGES):
    """Merge every photo harvest in raw_dir into one arcade-id-keyed index.

    Pure function of what is on disk: no network. Returns the payload dict.
    """
    arcades, snap = arcade_snapshot(arcades_path)
    by_id = {}
    ziv_to_arcade = {}
    bemani_to_arcade = {}
    for a in arcades:
        if not isinstance(a, dict) or a.get("id") is None:
            continue
        aid = str(a["id"])
        by_id[aid] = a
        links = a.get("links") or {}
        z = ziv_id_from_url(links.get("ziv"))
        if z:
            ziv_to_arcade[z] = aid
        b = bemanicn_id_from_url(links.get("bemanicn"))
        if b:
            bemani_to_arcade[b] = aid

    merged = {}          # arcade_id -> list of normalised records
    join = {}            # arcade_id -> {"ziv_id":..., "bemanicn_shop_id":...}
    link_outs = {}
    dangling = {"chain": [], "ziv": [], "bemanicn": [], "street": []}
    src_meta = {}

    def _add(aid, rec):
        merged.setdefault(aid, []).append(rec)

    # --- chain_photos.json (venue tier only; supersedes ziv_photos overlap) --
    doc = _read_json(os.path.join(raw_dir, "chain_photos.json"))
    if doc:
        src_meta["chain_photos"] = {
            "file": "data_raw/chain_photos.json",
            "updated": doc.get("updated"),
            "arcades_with_images": len(doc.get("images") or {}),
            "records": sum(len(v) for v in (doc.get("images") or {}).values()),
            "records_by_source": (doc.get("totals") or {}).get(
                "records_by_source"),
            "link_out_arcades": len(doc.get("link_outs") or {}),
            "licence": "ziv: no published photo licence, hotlink + credit + "
                       "deep link, never rehosted. wikimedia_commons: CC/PD "
                       "with per-file attribution.",
        }
        for k, recs in (doc.get("images") or {}).items():
            aid = str(k)
            if aid not in by_id:
                dangling["chain"].append(aid)
                continue
            for r in recs or []:
                n = _norm_record(r, source_default="ziv")
                if n:
                    _add(aid, n)
        for k, recs in (doc.get("link_outs") or {}).items():
            aid = str(k)
            if aid not in by_id:
                dangling["chain"].append(aid)
                continue
            keep = []
            for r in recs or []:
                if not isinstance(r, dict) or not r.get("page_url"):
                    continue
                if r.get("url") or r.get("file"):
                    # defensive: a link-out must never carry a renderable src
                    r = dict(r)
                    r.pop("url", None)
                    r.pop("file", None)
                keep.append(r)
            if keep:
                link_outs[aid] = keep

    # --- ziv_photos.json (keyed by ZIv id; join through links.ziv) ----------
    doc = _read_json(os.path.join(raw_dir, "ziv_photos.json"))
    if doc:
        bz = doc.get("by_ziv_id") or {}
        src_meta["ziv_photos"] = {
            "file": "data_raw/ziv_photos.json",
            "updated": doc.get("updated"),
            "ziv_ids": len(bz),
            "records": sum(len(v) for v in bz.values()),
            "licence": "ZIv publishes no photo licence; hotlink with visible "
                       "credit and a deep link home, never rehosted.",
        }
        for zid, recs in bz.items():
            aid = ziv_to_arcade.get(str(zid))
            if aid is None:
                dangling["ziv"].append(str(zid))
                continue
            join.setdefault(aid, {})["ziv_id"] = str(zid)
            for r in recs or []:
                n = _norm_record(r, source_default="ziv")
                if n:
                    _add(aid, n)

    # --- bemanicn_photos.json (keyed by shop id; carries arcade_id) ---------
    doc = _read_json(os.path.join(raw_dir, "bemanicn_photos.json"))
    if doc:
        ph = doc.get("photos") or {}
        src_meta["bemanicn_photos"] = {
            "file": "data_raw/bemanicn_photos.json",
            "updated": doc.get("updated"),
            "shops_with_photo": len(ph),
            "asset_dir": doc.get("asset_dir"),
            "bytes_on_disk": (doc.get("counts") or {}).get("bytes_on_disk"),
            "licence": doc.get("license"),
            "licence_note": doc.get("license_note"),
            "thumbnail_only": True,
        }
        for shop_id, rec in ph.items():
            if not isinstance(rec, dict):
                continue
            aid = rec.get("arcade_id")
            aid = str(aid) if aid is not None else bemani_to_arcade.get(
                str(shop_id))
            if aid is None or aid not in by_id:
                dangling["bemanicn"].append(str(shop_id))
                continue
            join.setdefault(aid, {})["bemanicn_shop_id"] = str(shop_id)
            n = _norm_record(rec, source_default="bemanicn")
            if n:
                _add(aid, n)

    # --- street_photos.json (arcade-id keyed; empty while rejected) ---------
    doc = _read_json(os.path.join(raw_dir, "street_photos.json"))
    if doc:
        ba = doc.get("by_arcade_id") or {}
        src_meta["street_photos"] = {
            "file": "data_raw/street_photos.json",
            "updated": doc.get("updated"),
            "status": doc.get("status"),
            "arcades_with_images": len(ba),
            "rejection": (doc.get("rejection") or {}).get("reason"),
            "licence": "CC BY-SA when shipped; share-alike survives the MIT "
                       "repo, so per-image author + licence_url are required.",
        }
        for k, recs in ba.items():
            aid = str(k)
            if aid not in by_id:
                dangling["street"].append(aid)
                continue
            for r in recs or []:
                n = _norm_record(r, source_default="streetphotos")
                if n and n.get("tier") in SHIPPABLE_TIERS:
                    _add(aid, n)

    # --- optional quality annotations (data_raw/photo_quality.json) ---------
    qmap = {}
    if quality_path is None:
        quality_path = os.path.join(raw_dir, "photo_quality.json")
    qdoc = _read_json(quality_path)
    if qdoc and isinstance(qdoc.get("images"), dict):
        qmap = qdoc["images"]
        src_meta["photo_quality"] = {
            "file": "data_raw/photo_quality.json",
            "updated": qdoc.get("updated"),
            "images_scored": len(qmap),
            "thresholds": qdoc.get("thresholds"),
        }

    # --- dedup, order, cap -------------------------------------------------
    out = {}
    dup_url = 0
    dup_hash = 0
    for aid, recs in merged.items():
        # Pass 1: annotate BEFORE sorting, so the verdict, the score and the
        # ziv w/h are all visible to _sort_key. Sorting first would rank on
        # fields that are not populated yet and can leave a "reject" at [0].
        for r in recs:
            _annotate_quality(r, qmap)
        # Pass 2: rank, dedup, cap.
        seen_key, seen_hash, keep = set(), set(), []
        for r in sorted(recs, key=_sort_key):
            k = _dedup_key(r)
            if k in seen_key:
                dup_url += 1
                continue
            h = r.get("sha256")
            if h and h in seen_hash:
                dup_hash += 1
                continue
            seen_key.add(k)
            if h:
                seen_hash.add(h)
            keep.append(r)
            if len(keep) >= max_images:
                break
        if not keep:
            continue
        best = min(TIER_RANK.get(r.get("tier"), 9) for r in keep)
        best_tier = None
        for name, rank in TIER_RANK.items():
            if rank == best:
                best_tier = "venue" if name == "venue" else (
                    "chain" if name == "chain" else "street")
                break
        entry = {"images": keep, "best_tier": best_tier}
        j = join.get(aid)
        if j:
            entry["join"] = j
        out[aid] = entry

    payload = {
        "updated": date.today().isoformat(),
        "schema": {
            "keyed_by": "arcade id from data/arcades.json (the snapshot below)",
            "mirrored": "record has `file` (repo-relative) and no `url`",
            "hotlinked": "record has `url` (absolute https) and no `file`",
            "link_outs": "separate top-level key; no url and no file; these "
                         "count as ZERO photo coverage and must never be "
                         "merged into images[]",
            "best_tier": ["venue", "street", "chain", None],
            "best_tier_note": "the brief names venue/chain/null. 'street' is "
                              "reachable in code if street_photos ever ships, "
                              "but street_photos.json is rejected_empty today "
                              "so only 'venue' is ever emitted.",
            "join": "stable natural keys so the manager can re-join if "
                    "merge.py renumbers arcade ids",
        },
        "snapshot": snap,
        "sources": src_meta,
        "counts": {
            "arcades_total": snap["arcades"],
            "arcades_with_image": len(out),
            "images": sum(len(v["images"]) for v in out.values()),
            "by_best_tier": _count_by(out, "best_tier"),
            "dedup_dropped_by_url": dup_url,
            "dedup_dropped_by_hash": dup_hash,
            "link_out_arcades": len(link_outs),
            "dangling_keys": {k: len(v) for k, v in dangling.items()},
        },
        "link_outs": {k: link_outs[k] for k in sorted(link_outs, key=_intkey)},
        "by_arcade_id": {k: out[k] for k in sorted(out, key=_intkey)},
    }
    payload["counts"]["dangling_samples"] = {
        k: v[:10] for k, v in dangling.items() if v
    }
    return payload


def _intkey(s):
    try:
        return (0, int(s))
    except (TypeError, ValueError):
        return (1, str(s))


def _count_by(out, field):
    counts = {}
    for v in out.values():
        counts[v.get(field)] = counts.get(v.get(field), 0) + 1
    return {("null" if k is None else k): counts[k] for k in counts}


# ------------------------------------------------------------------ loader --


def load_photo_index(path):
    """Load data_raw/photo_index.json -> {arcade_id_str: entry}, {} on miss.

    Companion to the older load_photos_index (ZIv-keyed); both stay available
    because enrich.py still joins ZIv photos by ZIv id.
    """
    doc = _read_json(path)
    if not isinstance(doc, dict):
        return {}
    idx = doc.get("by_arcade_id")
    return idx if isinstance(idx, dict) else {}


def load_photo_index_doc(path):
    """Full merged-index document (meta + link_outs + by_arcade_id), or {}."""
    doc = _read_json(path)
    return doc if isinstance(doc, dict) else {}


def photos_for_arcade_id(arcade_id, photo_index):
    """Image records for one arcade id from a merged index. [] on miss."""
    if not photo_index or arcade_id is None:
        return []
    entry = photo_index.get(str(arcade_id))
    if not isinstance(entry, dict):
        return []
    imgs = entry.get("images")
    return list(imgs) if isinstance(imgs, list) else []


def best_tier_for_arcade_id(arcade_id, photo_index):
    """"venue" / "chain" / "street" / None for one arcade id."""
    if not photo_index or arcade_id is None:
        return None
    entry = photo_index.get(str(arcade_id))
    if not isinstance(entry, dict):
        return None
    return entry.get("best_tier")


def link_outs_for_arcade_id(arcade_id, photo_index_doc):
    """Official-store-page link-outs for one arcade. NOT photo coverage."""
    if not photo_index_doc or arcade_id is None:
        return []
    lo = photo_index_doc.get("link_outs")
    if not isinstance(lo, dict):
        return []
    recs = lo.get(str(arcade_id))
    return list(recs) if isinstance(recs, list) else []


def is_hero_capable(rec, min_w=HERO_MIN_W, min_h=HERO_MIN_H):
    """True when this record's pixels clear the repo's existing hero gate.

    Unknown dimensions return None (not False): a ZIv hotlink whose size was
    never probed is undetermined, not disqualified.
    """
    w, h = rec.get("w"), rec.get("h")
    if not w or not h:
        return None
    return w >= min_w and h >= min_h


# ------------------------------------------------------------------- main --


def main():
    ap = argparse.ArgumentParser(
        description="Harvest real ZIv venue photos into data_raw/ziv_photos.json, "
                    "or (--merge) unify every harvest into data_raw/photo_index.json")
    ap.add_argument("--out", default="data_raw",
                    help="output directory (default: data_raw)")
    ap.add_argument("--outfile", default=OUTFILE)
    ap.add_argument("--country", action="append", default=None,
                    help="ZIv country spelling; repeatable. Use USA for the "
                         "United States per-series fetch. Default: a curated "
                         "set that includes Japan and USA.")
    ap.add_argument("--max-images", type=int, default=MAX_IMAGES,
                    help="max picture URLs kept per arcade (default 3)")
    ap.add_argument("--merge", action="store_true",
                    help="offline: merge existing harvests in --out into "
                         "photo_index.json (no network)")
    ap.add_argument("--arcades", default="data/arcades.json",
                    help="arcade snapshot for --merge (read once, hashed)")
    args = ap.parse_args()

    if args.merge:
        payload = build_photo_index(
            raw_dir=args.out, arcades_path=args.arcades,
            max_images=args.max_images)
        path = os.path.join(args.out, PHOTO_INDEX_FILE)
        common.save_json(path, payload)
        c = payload["counts"]
        print("wrote %s" % path)
        print("%d of %d arcades have an image (%.1f%%)"
              % (c["arcades_with_image"], c["arcades_total"],
                 100.0 * c["arcades_with_image"] / c["arcades_total"]))
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return

    payload = harvest(args.country, max_images=args.max_images)
    path = os.path.join(args.out, args.outfile)
    common.save_json(path, payload)
    print("wrote %s (%d arcade ids with photos)"
          % (path, payload["totals"]["ids_with_records"]))
    print(json.dumps({
        "coverage": payload["coverage"],
        "totals": payload["totals"],
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
