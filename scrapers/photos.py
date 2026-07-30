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


# ------------------------------------------------------------------- main --


def main():
    ap = argparse.ArgumentParser(
        description="Harvest real ZIv venue photos into data_raw/ziv_photos.json")
    ap.add_argument("--out", default="data_raw",
                    help="output directory (default: data_raw)")
    ap.add_argument("--outfile", default=OUTFILE)
    ap.add_argument("--country", action="append", default=None,
                    help="ZIv country spelling; repeatable. Use USA for the "
                         "United States per-series fetch. Default: a curated "
                         "set that includes Japan and USA.")
    ap.add_argument("--max-images", type=int, default=MAX_IMAGES,
                    help="max picture URLs kept per arcade (default 3)")
    args = ap.parse_args()
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
