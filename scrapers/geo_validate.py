"""Source-aware coordinate / country consistency checks.

Runs after country resolution on every merged arcade that has coordinates.
Rules (official vs community):

  allnet / eagate / wahlap  - address/country is authoritative; when the
      embedded geocode falls outside the labeled country's bounding box,
      null the coords (no re-geocoding) and note the rejection. The entry
      then correctly lands in the no-coords list instead of a wrong pin.

  ziv / round1usa / community - the coordinate pin is community-verified
      truth; when it falls outside the labeled country but inside another
      known country's box, correct the country field from the coords.

Ambiguous (outside every known box):
  official  -> null coords
  community -> keep coords, append a flag note
"""

from __future__ import annotations

import urllib.parse

# Keep in sync with scrapers/merge.py SRC_PRIORITY / OFFICIAL /
# OPTIONAL_COMMUNITY_SOURCES / COMMUNITY_SOURCES.
OFFICIAL_SOURCES = frozenset({"allnet", "eagate", "wahlap"})
COMMUNITY_SOURCES = frozenset({
    "ziv", "round1usa", "community",
    # Optional community scrapers (defensive loaders in merge.py).
    "nearcade", "hkrgm2", "hkarcade", "mgm_tw",
    "musecat", "otogesetchi", "timezone", "insert_coin",
})

# Imported lazily / by caller so this module can also run standalone
# against a frozen arcades.json without loading the full merge pipeline.
# COUNTRY_BOXES is the ordered multi-box table in merge.py.


def _boxes_for(country_boxes, country):
    return [b for b in country_boxes if b[0] == country]


def in_country_bbox(lat, lng, country, country_boxes):
    """True if (lat, lng) sits in any bounding box labeled `country`."""
    if lat is None or lng is None or not country:
        return False
    for name, la1, la2, lo1, lo2 in country_boxes:
        if name == country and la1 <= lat <= la2 and lo1 <= lng <= lo2:
            return True
    return False


def countries_containing(lat, lng, country_boxes):
    """Distinct countries (in table order) whose box contains the point."""
    out = []
    seen = set()
    for name, la1, la2, lo1, lo2 in country_boxes:
        if la1 <= lat <= la2 and lo1 <= lng <= lo2 and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def primary_bbox_country(lat, lng, country_boxes):
    """First matching country in table order (small / enclosed regions first)."""
    hits = countries_containing(lat, lng, country_boxes)
    return hits[0] if hits else None


def _is_official(entry):
    srcs = set(entry.get("src") or [])
    if srcs & OFFICIAL_SOURCES:
        return True
    # bemanicn is China-scoped and coordinate-less in practice; treat as
    # address-trusting only when no community source is present either.
    if srcs and not (srcs & COMMUNITY_SOURCES):
        return True
    return False


def _append_note(entry, note):
    existing = entry.get("notes")
    if not existing:
        entry["notes"] = note
        return
    if note in existing:
        return
    entry["notes"] = existing + " | " + note


def _gmaps_for(entry):
    lat, lng = entry.get("lat"), entry.get("lng")
    if lat is not None and lng is not None:
        return ("https://www.google.com/maps/search/?api=1&query=%.7f,%.7f"
                % (lat, lng))
    q = urllib.parse.quote(
        ("%s %s" % (entry.get("name") or "", entry.get("addr") or "")).strip())
    return "https://www.google.com/maps/search/?api=1&query=" + q


def _null_coords(entry, reason_note):
    before = {"lat": entry.get("lat"), "lng": entry.get("lng")}
    entry["lat"] = None
    entry["lng"] = None
    _append_note(entry, reason_note)
    links = entry.get("links") or {}
    links["gmaps"] = _gmaps_for(entry)
    entry["links"] = links
    return before


def validate_entry(entry, country_boxes):
    """Validate one arcade dict in place.

    Returns an action dict for the merge log, or None if untouched.
    """
    lat, lng = entry.get("lat"), entry.get("lng")
    if lat is None or lng is None:
        return None
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None

    labeled = entry.get("country") or "Unknown"
    if labeled != "Unknown" and in_country_bbox(lat, lng, labeled, country_boxes):
        return None

    hits = countries_containing(lat, lng, country_boxes)
    primary = hits[0] if hits else None
    official = _is_official(entry)
    base = {
        "id": entry.get("id"),
        "name": entry.get("name"),
        "src": list(entry.get("src") or []),
        "labeled_country": labeled,
        "lat": lat,
        "lng": lng,
        "bbox_hits": hits,
    }

    # ---- official / address-trusting sources ----
    if official:
        before = _null_coords(
            entry,
            "source geocode rejected (outside country); coordinates removed")
        action = dict(base)
        action.update({
            "action": "null_coords",
            "reason": "outside_labeled_country" if labeled != "Unknown"
                      else "outside_all_boxes",
            "previous_lat": before["lat"],
            "previous_lng": before["lng"],
        })
        return action

    # ---- community / coord-trusting sources ----
    if primary and primary != labeled:
        prev = labeled
        entry["country"] = primary
        _append_note(entry, "country corrected from coordinates (%s -> %s)"
                     % (prev, primary))
        action = dict(base)
        action.update({
            "action": "fix_country",
            "from_country": prev,
            "to_country": primary,
        })
        return action

    # Ambiguous: coords outside every known box (or only match labeled which
    # we already ruled out above - so no hits).
    _append_note(entry,
                 "coords outside all known country bboxes; left unchanged")
    action = dict(base)
    action.update({
        "action": "flag_ambiguous",
        "reason": "outside_all_boxes",
    })
    return action


def validate_arcades(arcades, country_boxes=None):
    """Run validation over a list of arcade dicts. Mutates in place.

    Returns the list of action records (also suitable for merge_log.json
    under the "geo_validation" key).
    """
    if country_boxes is None:
        # Local import avoids a circular import at module load time when
        # merge.py does `import geo_validate`.
        from merge import COUNTRY_BOXES
        country_boxes = COUNTRY_BOXES
    log = []
    for entry in arcades:
        action = validate_entry(entry, country_boxes)
        if action is not None:
            log.append(action)
    return log
