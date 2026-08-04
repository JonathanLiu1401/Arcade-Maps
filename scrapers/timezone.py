"""Timezone (timezonegames.com) official chain locator scraper.

Covers TEEG Timezone country sites with consistent list-card HTML:
  AU  https://www.timezonegames.com/en-au/venues/
  NZ  https://www.timezonegames.com/en-nz/locations/
  SG  https://www.timezonegames.com/en-sg/locations/
  PH  https://www.timezonegames.com/en-ph/locations/
  ID  https://www.timezonegames.com/en-id/locations/

List pages publish name, short address, amenity tags (Games / Music Games /
Bowling / VR / ...). They do NOT publish per-venue rhythm cabinet titles.
Optional per-venue detail pages carry a Google Maps place link with lat/lng.

Output schema (merge-friendly optional community row):
  {name, name_en, address, lat, lng, coord_system, games, source,
   source_url, sid, country, notes}

sid is the stable path slug (e.g. au/nsw/timezone-haymarket), never a
row number. games is always ["other"] because the locator has no cab list
(merge treats timezone as address/status, not inventory).

--smoke: AU list only, first few venues, no detail fetches, write nothing.
"""

import argparse
import html as html_lib
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

OUTFILE = "timezone.json"
SOURCE = "timezone"
BASE = "https://www.timezonegames.com"

# (region_key, country_label, list_url, href_prefix)
REGIONS = [
    ("au", "Australia",
     "https://www.timezonegames.com/en-au/venues/",
     "/en-au/venues/"),
    ("nz", "New Zealand",
     "https://www.timezonegames.com/en-nz/locations/",
     "/en-nz/locations/"),
    ("sg", "Singapore",
     "https://www.timezonegames.com/en-sg/locations/",
     "/en-sg/locations/"),
    ("ph", "Philippines",
     "https://www.timezonegames.com/en-ph/locations/",
     "/en-ph/locations/"),
    ("id", "Indonesia",
     "https://www.timezonegames.com/en-id/locations/",
     "/en-id/locations/"),
]

SMOKE_LIMIT = 5

_CARD_SPLIT = re.compile(r'class="venue-details"', re.I)
_HREF = re.compile(r'href="([^"]+)"', re.I)
_SUBURB = re.compile(
    r'class="venue-suburb"[^>]*>\s*([\s\S]*?)\s*</', re.I)
_ADDR = re.compile(
    r'class="venue-address"[^>]*>\s*([\s\S]*?)\s*</div>', re.I)
_TOOLTIP = re.compile(
    r'class="tooltip"\s*>\s*([\s\S]*?)\s*</span>', re.I)
_MAPS_3D4D = re.compile(
    r'!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)', re.I)
_MAPS_AT = re.compile(
    r'/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)', re.I)
_STRIP_TAGS = re.compile(r"<[^>]+>")

# Rough country bounding boxes (south, west, north, east) used only to
# reject clearly-wrong Google Maps pins that some venue templates embed
# (shared HQ / sibling-store coordinates).
_BBOX = {
    "Australia": (-44.0, 112.0, -10.0, 154.0),
    "New Zealand": (-48.0, 166.0, -33.0, 179.5),
    "Singapore": (1.15, 103.6, 1.48, 104.1),
    "Philippines": (4.5, 116.0, 21.5, 127.0),
    "Indonesia": (-11.5, 94.5, 6.5, 141.5),
}


def _clean(text):
    if text is None:
        return ""
    text = _STRIP_TAGS.sub(" ", text)
    text = html_lib.unescape(text)
    return common.unescape(text)


def _in_bbox(lat, lng, country):
    box = _BBOX.get(country)
    if not box or lat is None or lng is None:
        return False
    south, west, north, east = box
    return south <= lat <= north and west <= lng <= east


def sid_from_path(path, region_key):
    """Stable sid from URL path, e.g. au/nsw/timezone-haymarket."""
    path = path.split("?")[0].split("#")[0].strip("/")
    # drop en-xx/(venues|locations)/ prefix
    parts = path.split("/")
    if len(parts) >= 3 and parts[0].startswith("en-"):
        rest = parts[2:]  # after en-xx / venues|locations
        return region_key + "/" + "/".join(rest)
    return region_key + "/" + path.replace("/", "-")


def parse_list_page(html, region_key, country, href_prefix):
    """Parse venue cards from a country list page."""
    rows = []
    seen = set()
    blocks = _CARD_SPLIT.split(html)
    for block in blocks[1:]:
        hrefs = _HREF.findall(block)
        path = None
        for h in hrefs:
            # normalize absolute -> path
            if h.startswith("http"):
                parsed = urllib.parse.urlparse(h)
                hpath = parsed.path or ""
            else:
                hpath = h
            if href_prefix.rstrip("/") in hpath or hpath.startswith(
                    href_prefix):
                # skip bare region index like /en-au/venues/nsw/
                segs = [s for s in hpath.strip("/").split("/") if s]
                # need at least en-xx / venues|locations / region / slug
                if len(segs) >= 4:
                    path = hpath
                    break
                # ID style: en-id/locations/jakarta/slug (also 4)
                # SG: en-sg/locations/north/timezone-... (4)
        if not path:
            continue
        if not path.startswith("/"):
            path = "/" + path
        if path in seen:
            continue
        seen.add(path)

        name_m = _SUBURB.search(block)
        name = _clean(name_m.group(1) if name_m else "")
        if not name:
            # fallback: last path segment title-cased
            slug = path.rstrip("/").split("/")[-1]
            name = "Timezone " + slug.replace("-", " ").replace(
                "timezone ", "").title()
            if not name.lower().startswith("timezone"):
                name = "Timezone " + name

        addr_m = _ADDR.search(block)
        address = _clean(addr_m.group(1) if addr_m else "")
        activities = []
        for tm in _TOOLTIP.finditer(block):
            a = _clean(tm.group(1))
            if a and a not in activities:
                activities.append(a)

        page_url = BASE + path
        sid = sid_from_path(path, region_key)
        note_parts = []
        if activities:
            note_parts.append("Activities: " + ", ".join(activities))
        note_parts.append("Official Timezone locator (no cab list)")
        rows.append({
            "name": name,
            "name_en": name,
            "address": address,
            "lat": None,
            "lng": None,
            "coord_system": "wgs84",
            "games": ["other"],
            "source": SOURCE,
            "source_url": page_url,
            "sid": sid,
            "country": country,
            "notes": " | ".join(note_parts),
            "_path": path,
            "_activities": activities,
        })
    return rows


_MAPS_URL = re.compile(
    r'https?://(?:www\.)?google\.com/maps/place/[^\"\'\s<>]+', re.I)


def fetch_coords(page_url, country=None, name_hint=None):
    """Pull lat/lng from Google Maps place links on a venue detail page.

    Prefers pin coords (!3d/!4d) over map-center (/@lat,lng). Only
    considers maps/place URLs that look venue-related (contain
    'timezone' or a token from the venue name). Rejects candidates
    outside the venue country bbox when country is known.
    """
    html = common.fetch(page_url)
    tokens = []
    if name_hint:
        raw = re.sub(r"[^a-z0-9]+", " ", name_hint.lower())
        tokens = [t for t in raw.split()
                  if t not in ("timezone", "zone", "bowling", "the", "and")
                  and len(t) >= 4]

    def url_ok(u):
        ul = html_lib.unescape(u).lower()
        if "timezone" in ul or "time+zone" in ul:
            return True
        return any(t in ul for t in tokens)

    # Prefer coords embedded in venue-matching maps URLs
    candidates = []
    for m in _MAPS_URL.finditer(html):
        u = m.group(0)
        if not url_ok(u):
            continue
        pin = _MAPS_3D4D.search(u)
        if pin:
            candidates.append((float(pin.group(1)), float(pin.group(2)), 0))
            continue
        at = _MAPS_AT.search(u)
        if at:
            candidates.append((float(at.group(1)), float(at.group(2)), 1))
    # Fallback: any pin on the page (still country-checked)
    if not candidates:
        for m in _MAPS_3D4D.finditer(html):
            candidates.append((float(m.group(1)), float(m.group(2)), 2))
    candidates.sort(key=lambda t: t[2])
    for lat, lng, _rank in candidates:
        if country and not _in_bbox(lat, lng, country):
            continue
        return lat, lng
    return None, None


def scrape(regions=None, smoke=False, fetch_detail=False, max_venues=None):
    """Scrape Timezone locators.

    regions: list of region keys (au, nz, sg, ph, id). None = all.
    fetch_detail: hit each venue page for lat/lng. Off by default because
    many CMS pages embed sibling-store or shared pins that fail a country
    check or land hundreds of km away. List addresses are the reliable
    signal; merge matches Timezone rows primarily by name + country.
    """
    wanted = None
    if regions:
        wanted = {r.lower() for r in regions}
    selected = [r for r in REGIONS
                if wanted is None or r[0] in wanted]
    if smoke:
        selected = [r for r in selected if r[0] == "au"] or selected[:1]
        fetch_detail = False

    all_rows = []
    for region_key, country, list_url, href_prefix in selected:
        print("timezone: list %s" % list_url, file=sys.stderr)
        html = common.fetch(list_url)
        rows = parse_list_page(html, region_key, country, href_prefix)
        print("timezone: %s parsed %d venues" % (region_key, len(rows)),
              file=sys.stderr)
        all_rows.extend(rows)

    if smoke:
        all_rows = all_rows[:SMOKE_LIMIT]
    elif max_venues is not None:
        all_rows = all_rows[:max_venues]

    if fetch_detail:
        got = 0
        for i, row in enumerate(all_rows):
            url = row["source_url"]
            try:
                lat, lng = fetch_coords(
                    url, country=row.get("country"),
                    name_hint=row.get("name"))
                row["lat"] = lat
                row["lng"] = lng
                if lat is not None:
                    got += 1
            except common.FetchError as e:
                print("timezone: detail FAILED %s: %s" % (url, e),
                      file=sys.stderr)
            if (i + 1) % 20 == 0:
                print("timezone: detail %d/%d (%d with coords)"
                      % (i + 1, len(all_rows), got), file=sys.stderr)
        print("timezone: coords resolved for %d/%d"
              % (got, len(all_rows)), file=sys.stderr)

    # strip private keys
    out = []
    for row in all_rows:
        clean = {k: v for k, v in row.items() if not k.startswith("_")}
        out.append(clean)
    out.sort(key=lambda r: (r.get("country") or "", r.get("name") or "",
                            r.get("sid") or ""))
    print("timezone: done %d venues" % len(out), file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description="Timezone chain locator scraper")
    ap.add_argument("--out", default="data_raw", help="output directory")
    ap.add_argument("--outfile", default=OUTFILE)
    ap.add_argument("--smoke", action="store_true",
                    help="AU list only, first few venues; write nothing")
    ap.add_argument("--regions", default=None,
                    help="comma-separated region keys: au,nz,sg,ph,id")
    ap.add_argument("--detail", action="store_true",
                    help="fetch per-venue pages for Google Maps lat/lng "
                         "(sparse; many pages lack a reliable pin)")
    ap.add_argument("--max", type=int, default=None,
                    help="cap venues after list parse")
    args = ap.parse_args()
    regions = None
    if args.regions:
        regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    rows = scrape(regions=regions, smoke=args.smoke,
                  fetch_detail=args.detail,
                  max_venues=args.max)
    if args.smoke:
        import json
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        print("smoke: %d rows (nothing written)" % len(rows),
              file=sys.stderr)
        return
    if not rows:
        common.die("timezone returned 0 rows")
    path = os.path.join(args.out, args.outfile)
    common.save_json(path, rows)
    print("wrote %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
