"""Street-level / Commons venue-photo harvest for Arcade Maps.

STATUS (2026-07-31): NOT VIABLE. This module intentionally writes an EMPTY
image index. Recon (data_raw/streetlevel_imagery_probe.json) measured every
candidate source against a fixed-seed stratified sample of 210 arcades and
rejected all five for storefront use. This module re-loads that recon, re-
confirms the live APIs still answer, walks the full data/arcades.json
population for coverage denominators, and writes data_raw/street_photos.json
with zero image records plus the full rejection rationale.

Why empty (the number that matters)
-----------------------------------
KartaView is the only keyless street-level source with non-zero radius hits.
Of the best-case candidates (photo within 60 m AND camera heading within 60
degrees of the bearing to the venue), 0 of 7 inspected JPEGs showed an
arcade. All were road-forward windshield dashcam frames of asphalt, traffic
and dashboard. Radius hit rate overstates usable storefront coverage by
roughly an order of magnitude. Dashcams point down the road, not at shops.

Sources considered and their recon verdict
------------------------------------------
  kartaview   REJECT - usable storefront yield 0 of 7 inspected (camera-
              facing <=60 m hit rate only 5.2% overall; Japan/China ~0-3%)
  mapillary   BLOCKED - token-gated; same dashcam capture model even if
              unblocked. Token must never be committed to this public repo.
  commons     REJECT - 50.5% raw-minus-noise is tourist/transport geography,
              not venues. No hit was confirmed to be the arcade.
  osm_tags    REJECT - image=* on nearby arcade objects: 0 of 210 sample,
              global ceiling 24 of ~8880 mapped arcades (0.27%), and those
              24 point at unmirrorable third-party hosts.
  wikidata    REJECT - class Q260676 has 32 items with P18 worldwide
              (0.24% ceiling). Brand-level P18 is actively harmful
              (corporate HQ photos on every chain branch).

Licence position (for if any source is ever re-opened)
------------------------------------------------------
KartaView imagery is CC BY-SA 4.0. Mirroring into this MIT repo does NOT
relicense the JPEGs; they stay BY-SA. Any shipped record must carry author,
licence name, licence_url and page_url. Mapillary additionally requires a
visible Mapillary logo (Terms s11) and forbids committing a shared token
(Terms s2a). This module does not mirror anything today.

Output: data_raw/street_photos.json
-----------------------------------
  {
    "updated": "YYYY-MM-DD",
    "status": "rejected_empty",
    "source": "streetphotos",
    "by_arcade_id": {},          # arcade_id str -> [image records]
    "coverage": {country: {...}, ...},
    "distance_distribution": {},
    "rejection": { ... },
    "verification": { ... }      # live smoke of APIs at run time
  }

Each image record (schema reserved for a future viable source) would be:
  {
    "url": "...", "file": null, "source": "kartaview|commons|...",
    "credit": "author / username",
    "license": "CC BY-SA 4.0",
    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "page_url": "https://...",
    "distance_m": 12.4,
    "tier": "street_near|street_far|reject"
  }

This module never touches scrapers/merge.py, scrapers/run_all.py,
data_raw/ziv.json or data/arcades.json (read-only). It does not write
data/enrichment.json; the manager wires the index in when a source is
actually shippable.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCADES_PATH = os.path.join(ROOT, "data", "arcades.json")
PROBE_PATH = os.path.join(ROOT, "data_raw", "streetlevel_imagery_probe.json")
OUT_PATH = os.path.join(ROOT, "data_raw", "street_photos.json")
MIRROR_DIR = os.path.join(ROOT, "assets", "venues", "street")

# ---------------------------------------------------------------------------
# Policy: which sources are allowed to ship images
# ---------------------------------------------------------------------------
# Recon gate: a source may ship for a country only if measured usable
# storefront coverage in that country is >= 5%. Radius hits alone do not
# count. Visual inspection of KartaView best-case frames was 0 of 7, so
# no source clears the gate today. Keep the allow-list empty.

SHIP_ALLOW = {
    # "kartaview": set(),   # empty set => no country
    # "commons": set(),
    # "mapillary": set(),   # blocked pending owner token; still same dashcam model
    # "osm_tags": set(),
    # "wikidata": set(),
}

# Hard minimums that would re-open a source if a future recon remeasures.
# Kept here so the next agent does not re-litigate numbers from scratch.
RECON_GATES = {
    "kartaview": {
        "min_usable_storefront_pct": 5.0,
        "measured_usable_storefront_pct": 0.0,  # 0 of 7 inspected
        "measured_camera_facing_60m_pct": 5.2,
        "note": "Camera-facing is not usable. Inspected frames are asphalt.",
    },
    "commons": {
        "min_confirmed_venue_pct": 5.0,
        "measured_confirmed_venue_pct": 0.0,  # none confirmed; title-level only
        "measured_raw_minus_noise_pct": 50.5,
        "note": "Hits are transport/landmarks; no venue confirmed.",
    },
    "osm_tags": {
        "min_image_tag_pct": 5.0,
        "measured_image_tag_pct": 0.0,
        "global_ceiling_objects": 24,
        "note": "image=* is 0 of 210 sample; global ceiling 0.27%.",
    },
    "wikidata": {
        "min_p18_pct": 5.0,
        "measured_p18_ceiling_pct": 0.24,
        "note": "32 P18 images worldwide; brand-level images are wrong building.",
    },
    "mapillary": {
        "status": "blocked_unmeasured",
        "note": "Token-gated. Same dashcam model as KartaView. Do not commit token.",
    },
}

CC_BY_SA_40 = "CC BY-SA 4.0"
CC_BY_SA_40_URL = "https://creativecommons.org/licenses/by-sa/4.0/"

KARTAVIEW_API = "https://api.openstreetcam.org/2.0/photo/"
KARTAVIEW_PAGE = "https://kartaview.org/details/%s/%s"  # sequenceId / photo id
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

USER_AGENT = "ArcadeMaps-streetphotos/1.0 (+https://github.com; research; no bulk mirror)"


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def haversine_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres between two WGS-84 points."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1, lng1, lat2, lng2):
    """Initial bearing from point 1 to point 2, degrees [0, 360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    y = math.sin(dl) * math.cos(p2)
    x = (math.cos(p1) * math.sin(p2)
         - math.sin(p1) * math.cos(p2) * math.cos(dl))
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def heading_delta(h1, h2):
    """Smallest absolute difference between two headings in degrees."""
    d = abs((h1 - h2) % 360.0)
    return d if d <= 180.0 else 360.0 - d


def tier_for_distance(distance_m, facing=False):
    """Distance / facing tier. Nothing here is a storefront certainty.

    street_near  - within 30 m and camera facing venue (still NOT proven shop)
    street_far   - within 60 m (or facing within 60 m)
    reject       - farther / not facing; do not ship
    """
    if distance_m is None:
        return "reject"
    if distance_m <= 30.0 and facing:
        return "street_near"
    if distance_m <= 60.0:
        return "street_far"
    return "reject"


# ---------------------------------------------------------------------------
# Image record schema (reserved; not populated while sources are rejected)
# ---------------------------------------------------------------------------


def image_record(url, source, credit, license, license_url, page_url,
                 distance_m, tier, file_path=None, extra=None):
    """One self-describing street-photo record.

    Attribution fields are mandatory for CC BY-SA: credit (author), license,
    license_url, page_url. distance_m is required so a 120 m hit can be
    dropped later without re-querying.
    """
    if not url and not file_path:
        return None
    rec = {
        "url": url,
        "file": file_path,
        "source": source,
        "credit": credit,
        "license": license,
        "license_url": license_url,
        "page_url": page_url,
        "distance_m": None if distance_m is None else round(float(distance_m), 1),
        "tier": tier,
    }
    if extra:
        for k, v in extra.items():
            if k not in rec and v is not None:
                rec[k] = v
    return rec


# ---------------------------------------------------------------------------
# KartaView (implemented, hard-gated off)
# ---------------------------------------------------------------------------


def _kv_get(lat, lng, radius_m, timeout=30):
    """Query KartaView photos near a point. Returns list of raw photo dicts."""
    qs = urllib.parse.urlencode({
        "lat": "%.7f" % lat,
        "lng": "%.7f" % lng,
        "radius": int(radius_m),
    })
    url = KARTAVIEW_API + "?" + qs
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            http.client.HTTPException) as e:
        raise common.FetchError("kartaview %s: %s" % (url, e))
    time.sleep(0.15)  # politeness; full-scale harvest is gated off anyway
    try:
        body = json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError as e:
        raise common.FetchError("kartaview bad json: %s" % e)
    status = (body.get("status") or {})
    # apiCode 600 = success with data; 601 = empty result (also success)
    api_code = status.get("apiCode")
    if api_code not in (600, 601, "600", "601"):
        raise common.FetchError(
            "kartaview apiCode=%s msg=%s" % (api_code, status.get("apiMessage")))
    result = body.get("result") or {}
    data = result.get("data") if isinstance(result, dict) else None
    if not data:
        return []
    return data if isinstance(data, list) else []


def _kv_photo_to_record(photo, arcade_lat, arcade_lng, max_distance_m=60.0):
    """Convert one KartaView photo dict into an image_record, or None.

    Does not apply the ship gate; caller decides whether to keep it.
    """
    def _coord(d, *keys):
        for k in keys:
            if k in d and d[k] is not None and d[k] != "":
                return d[k]
        return None

    try:
        # Do not use `or` here: lat/lng of 0.0 is valid (Gulf of Guinea) and
        # would be treated as missing.
        plat = float(_coord(photo, "lat", "latitude"))
        plng = float(_coord(photo, "lng", "longitude"))
    except (TypeError, ValueError):
        return None
    dist = haversine_m(arcade_lat, arcade_lng, plat, plng)
    if dist > max_distance_m:
        return None

    # Do not use `or`: heading 0.0 (due north) is valid and must not fall through.
    heading_raw = _coord(photo, "heading", "headers")
    try:
        heading = float(heading_raw) if heading_raw is not None else None
    except (TypeError, ValueError):
        heading = None

    facing = False
    if heading is not None:
        brg = bearing_deg(plat, plng, arcade_lat, arcade_lng)
        facing = heading_delta(heading, brg) <= 60.0

    is_360 = (str(photo.get("imagePartProjection") or "").upper() == "SPHERE"
              or str(photo.get("projection") or "").upper() == "SPHERE")

    # Prefer processed full URL; fall back through the CDN fields.
    url = (photo.get("fileurlProc")
           or photo.get("imageProcUrl")
           or photo.get("fileurl")
           or photo.get("imageLthUrl"))
    if url and "{{sizeprefix}}" in str(url):
        url = str(url).replace("{{sizeprefix}}", "proc")
    if not url:
        return None

    pid = photo.get("id")
    seq = photo.get("sequenceId") or photo.get("sequence_id") or photo.get("from")
    page = None
    if seq is not None and pid is not None:
        page = KARTAVIEW_PAGE % (seq, pid)
    elif pid is not None:
        page = "https://kartaview.org/details/-/%s" % pid

    author = (photo.get("username")
              or photo.get("user")
              or photo.get("author")
              or "KartaView contributor")
    if isinstance(author, dict):
        author = author.get("username") or author.get("name") or "KartaView contributor"

    tier = tier_for_distance(dist, facing=facing)
    # 360s see sideways; keep the distance tier but flag them.
    extra = {
        "photo_id": str(pid) if pid is not None else None,
        "sequence_id": str(seq) if seq is not None else None,
        "heading": heading,
        "facing_venue": facing,
        "is_360": is_360,
        "shot_lat": plat,
        "shot_lng": plng,
    }
    return image_record(
        url=url,
        source="kartaview",
        credit="%s via KartaView" % author,
        license=CC_BY_SA_40,
        license_url=CC_BY_SA_40_URL,
        page_url=page,
        distance_m=dist,
        tier=tier,
        extra=extra,
    )


def harvest_kartaview_for_arcade(arcade, radius_m=60.0):
    """Return candidate records near one arcade. Ship gate is NOT applied."""
    lat, lng = arcade.get("lat"), arcade.get("lng")
    if lat is None or lng is None:
        return []
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return []
    photos = _kv_get(lat, lng, radius_m)
    out = []
    for p in photos:
        rec = _kv_photo_to_record(p, lat, lng, max_distance_m=radius_m)
        if rec is not None:
            out.append(rec)
    out.sort(key=lambda r: (r.get("distance_m") is None, r.get("distance_m") or 1e9))
    return out


# ---------------------------------------------------------------------------
# Loaders / coverage math
# ---------------------------------------------------------------------------


def load_arcades(path=ARCADES_PATH):
    data = common.load_json(path)
    arcs = data.get("arcades") if isinstance(data, dict) else data
    if not isinstance(arcs, list):
        common.die("arcades.json has no arcades[] list")
    return arcs


def load_probe(path=PROBE_PATH):
    if not os.path.isfile(path):
        return None
    return common.load_json(path)


def country_denominators(arcades):
    """Count arcades with coordinates, per country (and overall)."""
    by = Counter()
    with_coords = Counter()
    for a in arcades:
        c = a.get("country") or "Unknown"
        by[c] += 1
        if a.get("lat") is not None and a.get("lng") is not None:
            with_coords[c] += 1
    return by, with_coords


def empty_coverage(by_country, with_coords):
    """Build a coverage block showing 0 images shipped for every country."""
    out = {}
    for c, n in sorted(by_country.items(), key=lambda kv: (-kv[1], kv[0])):
        out[c] = {
            "arcades": n,
            "with_coords": with_coords.get(c, 0),
            "with_photos": 0,
            "pct": 0.0,
            "by_source": {},
            "by_tier": {},
        }
    total_a = sum(by_country.values())
    total_c = sum(with_coords.values())
    out["_overall"] = {
        "arcades": total_a,
        "with_coords": total_c,
        "with_photos": 0,
        "pct": 0.0,
        "by_source": {},
        "by_tier": {},
    }
    return out


def distance_distribution(by_arcade_id):
    """Bucket shipped distances. Empty when nothing is shipped."""
    buckets = {
        "0_15m": 0,
        "15_30m": 0,
        "30_60m": 0,
        "60_120m": 0,
        "over_120m": 0,
        "unknown": 0,
    }
    for recs in by_arcade_id.values():
        for r in recs:
            d = r.get("distance_m")
            if d is None:
                buckets["unknown"] += 1
            elif d <= 15:
                buckets["0_15m"] += 1
            elif d <= 30:
                buckets["15_30m"] += 1
            elif d <= 60:
                buckets["30_60m"] += 1
            elif d <= 120:
                buckets["60_120m"] += 1
            else:
                buckets["over_120m"] += 1
    return buckets


# ---------------------------------------------------------------------------
# Live verification (smoke, not harvest)
# ---------------------------------------------------------------------------


def verify_kartaview_live(sample_points):
    """Hit KartaView for a few known points. Returns a small report.

    Confirms the API still answers. Does NOT claim usable storefronts.
    """
    report = {
        "endpoint": KARTAVIEW_API,
        "points_tried": 0,
        "points_with_any_photo_60m": 0,
        "points_with_facing_60m": 0,
        "errors": 0,
        "samples": [],
    }
    for label, lat, lng in sample_points:
        report["points_tried"] += 1
        try:
            photos = _kv_get(lat, lng, 60)
        except common.FetchError as e:
            report["errors"] += 1
            report["samples"].append({
                "label": label, "lat": lat, "lng": lng, "error": str(e),
            })
            continue
        facing_n = 0
        for p in photos:
            rec = _kv_photo_to_record(p, lat, lng, max_distance_m=60.0)
            if rec and rec.get("facing_venue"):
                facing_n += 1
        if photos:
            report["points_with_any_photo_60m"] += 1
        if facing_n:
            report["points_with_facing_60m"] += 1
        report["samples"].append({
            "label": label,
            "lat": lat,
            "lng": lng,
            "n_photos_raw": len(photos),
            "n_facing": facing_n,
            "shipped": 0,  # hard gate
            "note": "API alive; records not shipped (usable storefront yield 0%)",
        })
    return report


def verify_commons_live(lat, lng, radius_m=100):
    """One Commons geosearch smoke. Licence is per-file; we do not ship."""
    qs = urllib.parse.urlencode({
        "action": "query",
        "list": "geosearch",
        "gscoord": "%s|%s" % (lat, lng),
        "gsradius": int(radius_m),
        "gsnamespace": 6,
        "gslimit": 5,
        "format": "json",
    })
    url = COMMONS_API + "?" + qs
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError,
            http.client.HTTPException) as e:
        return {"ok": False, "error": str(e), "n": 0}
    hits = ((body.get("query") or {}).get("geosearch")) or []
    titles = [h.get("title") for h in hits[:5]]
    return {
        "ok": True,
        "n": len(hits),
        "sample_titles": titles,
        "shipped": 0,
        "note": "Commons geosearch alive; titles are geography not venues; not shipped",
    }


def pick_verification_points(arcades, per_country=1):
    """One coordinate per high-interest country for the live smoke."""
    want = [
        "Singapore", "United States", "United Kingdom", "Japan",
        "Philippines", "Taiwan", "China",
    ]
    found = {}
    for a in arcades:
        c = a.get("country")
        if c not in want or c in found:
            continue
        if a.get("lat") is None or a.get("lng") is None:
            continue
        found[c] = (c, float(a["lat"]), float(a["lng"]))
        if len(found) >= len(want):
            break
    # Prefer a known dense Singapore corridor if present, else first hit.
    return [found[c] for c in want if c in found]


# ---------------------------------------------------------------------------
# Main harvest (gated: always empty while SHIP_ALLOW is empty)
# ---------------------------------------------------------------------------


def sources_allowed_anywhere():
    return {s for s, countries in SHIP_ALLOW.items() if countries}


def harvest(arcades, allow_live_smoke=True):
    """Produce the street_photos payload.

    With the current SHIP_ALLOW (empty), this never queries bulk street
    imagery. It does:
      1. Load recon probe if present and embed its headline.
      2. Compute full-population coverage denominators (all countries).
      3. Optionally smoke-test KartaView + Commons on a few points.
      4. Write by_arcade_id = {} and pct = 0 everywhere.
    """
    by_country, with_coords = country_denominators(arcades)
    coverage = empty_coverage(by_country, with_coords)
    by_arcade_id = {}

    probe = load_probe()
    rejection = {
        "verdict": "rejected_empty",
        "reason": (
            "No street-level or Commons source measured a usable storefront "
            "yield >= 5% in any country. KartaView best-case visual inspection "
            "was 0 of 7 frames. Japan and China (majority of the dataset) are "
            "0-3% on every source. Shipping radius hits would put asphalt and "
            "bus-station photos on arcade pins."
        ),
        "gates": RECON_GATES,
        "ship_allow": {k: sorted(v) for k, v in SHIP_ALLOW.items()},
        "probe_path": os.path.relpath(PROBE_PATH, ROOT).replace("\\", "/")
                      if os.path.isfile(PROBE_PATH) else None,
        "probe_headline": (probe or {}).get("headline") if probe else None,
        "what_would_reopen": (
            "A new recon that measures CONFIRMED storefront yield "
            "(downloaded JPEGs inspected, not radius hits) at >=5% in a "
            "country, with per-image attribution fields available from the "
            "API, and a licence that permits MIT-repo publication or "
            "hotlink with credit. Per-venue operator photos (ZIv, bemanicn, "
            "chain store pages) remain the correct path to 80% coverage."
        ),
    }

    verification = {
        "live_smoke": allow_live_smoke,
        "kartaview": None,
        "commons": None,
        "full_scale_bulk_queries": 0,
        "note": (
            "Bulk harvest disabled. Live smoke only confirms APIs still "
            "answer; it does not re-inspect storefront usability."
        ),
    }

    if allow_live_smoke:
        points = pick_verification_points(arcades)
        # Force a known Singapore-ish dense corridor as first point if we have SG.
        print("streetphotos: live smoke on %d points ..." % len(points),
              file=sys.stderr)
        verification["kartaview"] = verify_kartaview_live(points)
        # One Commons smoke on the first point with coords.
        if points:
            label, lat, lng = points[0]
            print("streetphotos: commons smoke at %s ..." % label, file=sys.stderr)
            verification["commons"] = verify_commons_live(lat, lng)
        print("streetphotos: smoke done "
              "(kv_errors=%s commons_ok=%s)"
              % ((verification["kartaview"] or {}).get("errors"),
                 (verification["commons"] or {}).get("ok")),
              file=sys.stderr)

    # Full-population accounting: every arcade is a denominator, zero photos.
    n_total = len(arcades)
    n_coords = sum(1 for a in arcades
                   if a.get("lat") is not None and a.get("lng") is not None)

    dist = distance_distribution(by_arcade_id)

    payload = {
        "updated": date.today().isoformat(),
        "status": "rejected_empty",
        "source": "streetphotos",
        "max_images_per_arcade": 1,
        "mirror_dir": None,  # nothing mirrored
        "totals": {
            "arcades": n_total,
            "with_coords": n_coords,
            "with_photos": 0,
            "pct": 0.0,
            "ids_with_records": 0,
            "bulk_api_queries": 0,
        },
        "coverage": coverage,
        "distance_distribution": dist,
        "rejection": rejection,
        "verification": verification,
        "schema": {
            "by_arcade_id": (
                "map of str(arcade_id) -> list of image records. Empty while "
                "status=rejected_empty. Record fields: url, file, source, "
                "credit, license, license_url, page_url, distance_m, tier."
            ),
            "tier_values": [
                "street_near ( <=30 m and camera facing; still not proven shop )",
                "street_far  ( <=60 m )",
                "reject      ( farther / not facing; never ship )",
                "venue       ( reserved for true per-venue operator photos )",
            ],
            "attribution": (
                "CC BY-SA requires per-image credit (author), license name, "
                "license_url and page_url. Share-alike means mirrored JPEGs "
                "stay BY-SA inside this MIT repo."
            ),
        },
        "by_arcade_id": by_arcade_id,
    }
    return payload


def print_report(payload):
    """Human summary to stderr/stdout for the run proof."""
    lines = []
    t = payload["totals"]
    lines.append("=== streetphotos run %s ===" % payload["updated"])
    lines.append("status: %s" % payload["status"])
    lines.append("arcades: %d  with_coords: %d  with_photos: %d  (%.2f%%)"
                 % (t["arcades"], t["with_coords"], t["with_photos"], t["pct"]))
    lines.append("bulk_api_queries: %d" % t["bulk_api_queries"])
    lines.append("distance_distribution: %s" % payload["distance_distribution"])
    lines.append("")
    lines.append("coverage by country (top 15 by arcade count):")
    cov = payload["coverage"]
    rows = [(c, v) for c, v in cov.items() if c != "_overall"]
    rows.sort(key=lambda kv: -kv[1]["arcades"])
    for c, v in rows[:15]:
        lines.append(
            "  %-22s arcades=%5d coords=%5d photos=%5d  pct=%5.1f%%"
            % (c, v["arcades"], v["with_coords"], v["with_photos"], v["pct"]))
    if "_overall" in cov:
        v = cov["_overall"]
        lines.append(
            "  %-22s arcades=%5d coords=%5d photos=%5d  pct=%5.1f%%"
            % ("OVERALL", v["arcades"], v["with_coords"], v["with_photos"], v["pct"]))
    lines.append("")
    lines.append("rejection: %s" % payload["rejection"]["verdict"])
    lines.append("reason: %s" % payload["rejection"]["reason"])
    ver = payload.get("verification") or {}
    kv = ver.get("kartaview") or {}
    if kv:
        lines.append(
            "live smoke kartaview: tried=%s any60m=%s facing60m=%s errors=%s shipped=0"
            % (kv.get("points_tried"), kv.get("points_with_any_photo_60m"),
               kv.get("points_with_facing_60m"), kv.get("errors")))
    cm = ver.get("commons") or {}
    if cm:
        lines.append(
            "live smoke commons: ok=%s n=%s shipped=%s titles=%s"
            % (cm.get("ok"), cm.get("n"), cm.get("shipped"),
               (cm.get("sample_titles") or [])[:3]))
    lines.append("=== end streetphotos ===")
    text = "\n".join(lines)
    # Avoid Windows cp1252 crashes on any future CJK country names.
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Street-level photo index (currently rejected_empty).")
    ap.add_argument("--arcades", default=ARCADES_PATH,
                    help="path to data/arcades.json")
    ap.add_argument("--out", default=OUT_PATH,
                    help="path to data_raw/street_photos.json")
    ap.add_argument("--no-smoke", action="store_true",
                    help="skip live API smoke tests")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute payload but do not write the output file")
    args = ap.parse_args(argv)

    print("streetphotos: loading %s" % args.arcades, file=sys.stderr)
    arcades = load_arcades(args.arcades)
    print("streetphotos: %d arcades" % len(arcades), file=sys.stderr)

    if sources_allowed_anywhere():
        print("streetphotos: WARNING ship_allow is non-empty: %s"
              % sources_allowed_anywhere(), file=sys.stderr)
    else:
        print("streetphotos: SHIP_ALLOW empty - writing rejected_empty index",
              file=sys.stderr)

    payload = harvest(arcades, allow_live_smoke=not args.no_smoke)
    report = print_report(payload)

    if args.dry_run:
        print("streetphotos: dry-run, not writing %s" % args.out, file=sys.stderr)
        return 0

    common.save_json(args.out, payload)
    print("streetphotos: wrote %s (%d arcade keys)"
          % (args.out, len(payload["by_arcade_id"])), file=sys.stderr)
    # Keep a short proof sidecar next to the index is unnecessary; the index
    # itself embeds verification + coverage. Report text is on stdout.
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
