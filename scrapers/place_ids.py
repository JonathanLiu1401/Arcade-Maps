"""Resolve arcades to Google place IDs, and cache them (data/place_ids.json).

WHY THIS FILE EXISTS, AND WHY IT ONLY STORES AN ID
--------------------------------------------------
Photo coverage is ~7.5% overall (Japan ~3%, China ~0%). Google has a photo
for most of these venues. We are allowed to show one; we are not allowed to
keep one.

Google Maps Platform terms split the two things cleanly:

  place ID   "Place IDs are exempt from the caching restrictions stated in
             Section 3.2.3(b) of the Google Maps Platform Terms of Service."
             ... "You can therefore store place ID values indefinitely."
             Google recommends refreshing IDs older than 12 months, which is
             free (see --refresh below).

  photo      "You cannot cache a photo name. Also, the name can expire."

So the ONLY durable artifact is the ID. This script resolves it once, offline,
and writes data/place_ids.json. The photo itself is fetched in the browser when
a panel opens and is never written anywhere (js/gphotos.js). No photo name, no
photo URL and no photo bytes are ever committed to this repo.

MATCH VERIFICATION IS THE POINT
-------------------------------
A wrong place ID means the site confidently shows a photo of the wrong
building. That is worse than showing nothing, and it is the exact failure mode
this project has already had to fix three times in the coordinate data.

So a Text Search answer is only accepted when it is BOTH:

  near      merge.haversine_m(our pin, Google's location) within MAX_DIST_M
  named     name_match.similarity(our name, Google's displayName) high enough

Neither alone is sufficient. A shopping mall has a dozen tenants inside 50 m,
so distance alone picks the wrong one; and a chain like GiGO or Round1 has
identically named branches in other cities, so name alone picks the wrong city.
Every accepted match records dist_m, name_sim and a confidence grade, and every
rejection is written to the file with its reason so a bad threshold is
auditable rather than invisible. js/gphotos.js refuses to use anything below
MIN_CONFIDENCE.

OPT-IN, AND SILENT WITHOUT A KEY
--------------------------------
With no GOOGLE_MAPS_API_KEY in the environment this module makes no request,
writes no file and exits 0. That is the same contract scrapers/fx.py and
scrapers/geocode_cn.py follow, and it is what keeps the weekly GitHub Action
(which has no key, and must never have one) passing. This script is NOT wired
into run_all.py: it is a manual, occasional, owner-run tool.

COST, HONESTLY (verified against Google's published list 2026-07-30)
--------------------------------------------------------------------
Resolution needs id + displayName + formattedAddress + location. displayName,
formattedAddress and location are all above the free "IDs Only" tier, so the
call bills at Text Search Pro:

    Places API Text Search Pro   $32.00 / 1,000    5,000 free calls / month

There is a free "Text Search Essentials (IDs Only)" SKU, but it returns only
the place ID and no name, address or location - which is to say, nothing to
verify against. Using it would mean storing unverified IDs, which is the one
thing this file exists to prevent. So the Pro call is the honest cost of not
being wrong.

13,534 arcades in one sitting is therefore about 8,534 billable calls, roughly
USD 273. The free pool refills monthly, so ~4,500 a month costs nothing and
finishes the whole dataset in three months. That is why --limit defaults to a
small number and why resolving everything at once requires --all --yes: this
CLI is deliberately incapable of spending hundreds of dollars by accident.

    python scrapers/place_ids.py                        # 200 rows, ~$0
    python scrapers/place_ids.py --country Japan --limit 1400
    python scrapers/place_ids.py --all --yes            # prints the bill first
    python scrapers/place_ids.py --refresh              # free, IDs Only SKU

Stdlib only, same rule as the rest of scrapers/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import merge          # haversine_m only; do not reimplement it here
import name_match     # similarity() / substring_match(): the shared comparer

ENV_KEY = "GOOGLE_MAPS_API_KEY"

OUTFILE = "place_ids.json"
ARCADES_FILE = "arcades.json"
ENRICH_FILE = "enrichment.json"

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/%s"

# Billed at Text Search Pro. Every field here is load-bearing for verification:
# location gives the distance test, displayName gives the name test, and
# formattedAddress is recorded so a human can audit a questionable match later.
SEARCH_MASK = ("places.id,places.displayName,places.formattedAddress,"
               "places.location")

# Free: Place Details Essentials (IDs Only). Used only by --refresh.
REFRESH_MASK = "id"

SLEEP = 0.25          # polite gap between calls; Google's QPS is far higher
TIMEOUT = 30
RETRIES = 3

SAVE_EVERY = 25       # incremental write cadence, so a crash keeps its work

# Cost of one Text Search Pro call, USD, in the first volume band. Only used
# to print an estimate before spending the owner's money.
TEXT_SEARCH_PRO_USD_PER_1K = 32.00
TEXT_SEARCH_PRO_FREE_PER_MONTH = 5000

DEFAULT_LIMIT = 200

# ------------------------------------------------------------ verification --

# A Google answer further than this from our pin is not our venue, whatever it
# is called. 300 m is deliberately generous: our own coordinates come from
# several sources of differing precision (an official store geocode, a ZIv
# community pin, a Baidu POI hit), and a large mall's registered point can sit
# a couple of hundred metres from the arcade inside it. It is still tight
# enough that the next arcade over almost never qualifies.
MAX_DIST_M = 300.0

# An `approx` row is a district or city centroid - it is not a position, it is
# an admin area. Distance against it means nothing, so those rows are skipped
# unless --include-approx is passed, and then they must clear a much higher
# name bar with no distance credit at all. Their confidence is capped at
# "medium" so the grade always says the pin was never really verified.
APPROX_MAX_DIST_M = {"district": 30000.0, "city": 80000.0}
APPROX_MIN_SIM = 0.80

# WHY A SIMILARITY SCORE ALONE IS NOT A NAME TEST
# ------------------------------------------------
# name_match.similarity() was built for the merge proximity tier, where both
# names come from arcade listings. Here one side is whatever Google calls the
# nearest business, and that breaks the score in a specific, measured way: it
# rewards the SHARED LOCATION SUFFIX that almost every venue name in Japan
# ends with. Measured on real name shapes (2026-07-30):
#
#     GiGO Shinjuku          vs Namco Shinjuku            0.696   DIFFERENT
#     Taito Station Ikebukuro vs Round1 Ikebukuro          0.581   DIFFERENT
#     Club Sega Akihabara    vs GiGO Akihabara 3          0.552   DIFFERENT
#     GiGO Akihabara 1       vs GiGO                      0.375   SAME
#     GiGO Akihabara 3       vs ギーゴ秋葉原3号館            0.273   SAME
#
# The distributions do not merely overlap, they INVERT: in the 0.27-0.70 band
# the high scorers are the wrong venue and the low scorers are the right one.
# No single threshold on this score can separate them, so a threshold alone
# would systematically prefer the neighbouring arcade over the actual store.
#
# What does separate them is the BRAND HEAD - the front of the name, before
# the branch/location part. Two arcades in one district share a suffix and
# differ at the front; one arcade written two ways shares the front and differs
# after it. So a name is accepted only when the score clears MIN_NAME_SIM AND
# the brand heads agree. On the 18 adversarial pairs in test_place_ids.py that
# combination accepts 0 of 12 different-venue pairs while keeping the
# same-venue ones - neither gate alone manages that.
MIN_NAME_SIM = 0.55

# Compact-form prefix length for brand agreement. 4 characters is long enough
# that "namco" and "namba" part ways, and short enough to survive romanization
# wobble ("round1"/"rond1", "taitoo"/"taito"). Shorter forms than this are not
# compared at all: a 2-3 character head matches half the world.
BRAND_PREFIX = 4

CONFIDENCE_ORDER = ["high", "medium", "low", "reject"]


def _brand_forms(s):
    """Every compact reading of a name, long-vowel-folded, BRAND_PREFIX+ long.

    Uses name_match's own readings/compact/fold_long so kana, romaji and mixed
    spellings all arrive at comparable strings. Nothing here re-implements the
    comparer; it only looks at the FRONT of what the comparer produces.
    """
    out = set()
    for r in name_match.readings(s or ""):
        c = name_match.compact(r)
        if not c:
            continue
        out.add(c)
        out.add(name_match.fold_long(c))
    return {x for x in out if len(x) >= BRAND_PREFIX}


def brand_agrees(a, b, prefix=BRAND_PREFIX):
    """Do these two names start with the same brand?

    True when some reading of one is a prefix of some reading of the other
    (truncation: "GiGO" vs "GiGO Akihabara 1"), or when they share their first
    `prefix` characters (branch suffix differs: "Round1 Sakai" vs "Round1
    Stadium Sakai").
    """
    A, B = _brand_forms(a), _brand_forms(b)
    for x in A:
        for y in B:
            if x.startswith(y) or y.startswith(x):
                return True
            if x[:prefix] == y[:prefix]:
                return True
    return False


def classify(dist_m, name_sim, approx_level=None, brand_ok=None):
    """Grade one candidate. Returns (confidence, reason).

    confidence is one of high / medium / low / reject. Anything below
    js/gphotos.js MIN_CONFIDENCE is stored but never used to fetch a photo:
    the record exists so a threshold change can be evaluated against real
    rejections instead of guessed at.

    `brand_ok` is brand_agrees() for the pair. It defaults to None meaning
    "not supplied", in which case only the score is used - callers inside this
    module always pass it, because on its own the score cannot tell a
    neighbouring arcade from this one (see MIN_NAME_SIM above).
    """
    if dist_m is None:
        # No coordinate on our side means no distance test exists, and a name
        # alone is not enough to bet a photo on.
        return "reject", "no_coordinates"

    named = name_sim >= MIN_NAME_SIM and (brand_ok is not False)

    if approx_level:
        limit = APPROX_MAX_DIST_M.get(approx_level, APPROX_MAX_DIST_M["city"])
        if dist_m > limit:
            return "reject", "too_far_from_%s_centroid" % approx_level
        if brand_ok is False:
            return "reject", "approx_brand_mismatch"
        if name_sim < APPROX_MIN_SIM:
            return "reject", "approx_needs_name>=%.2f" % APPROX_MIN_SIM
        # Cleared the strict name bar, but the coordinate never corroborated
        # anything, so this never grades "high".
        return "medium", "approx_name_only"

    if dist_m > MAX_DIST_M:
        return "reject", "too_far"

    # A high score with a DIFFERENT brand head is the dangerous case: it is
    # what "GiGO Shinjuku" vs "Namco Shinjuku" (0.696) looks like. Refuse it
    # outright rather than let distance promote it.
    if brand_ok is False and name_sim >= MIN_NAME_SIM:
        return "reject", "brand_mismatch"

    if named and name_sim >= 0.80:
        return "high", "name_strong"
    if named and dist_m <= 150.0:
        return "high", "name_good_and_close"
    if named:
        return "medium", "name_good"

    # Below the score threshold, a matching brand head is NOT enough to accept
    # on, and this is a deliberate, tested decision rather than an oversight.
    #
    # A short brand head collides freely: "Sega"/"Segafredo Cafe",
    # "Round1"/"Roundabout Cafe", "Silk Hat"/"Silky Cafe" and "Game
    # Panic"/"Game Fantasia" all agree on their first four characters and all
    # score 0.38-0.50, which is the SAME band as genuine cross-script pairs
    # like "GiGO Akihabara 3" / "ギーゴ秋葉原3号館" (0.273). Nothing in the two
    # signals separates them, so accepting the band would mean accepting a
    # coffee shop as an arcade some fraction of the time.
    #
    # The cost of refusing is a MISS: the panel shows no Google photo and falls
    # back exactly as it does today. The cost of accepting would be a confident
    # photo of the wrong building. Those are not symmetric, so this fails safe
    # and the pair is recorded at "low" for a human to look at.
    #
    # Practical consequence, stated plainly: our romanizer handles kana but not
    # kanji, so a Japanese venue we hold in romaji and Google names in kanji
    # ("ラウンドワン スタジアム 町田店" vs "Round1 Stadium Machida", 0.158) will
    # usually miss. Those show up in the misses map, not as wrong photos.
    return "low", "name_weak"


def score_name(ours, theirs):
    """Name agreement in [0, 1], from the shared comparer.

    Deliberately NOT adjusted here. An earlier version floored the score when
    name_match.substring_match() fired, which quietly promoted "Round1" over
    "Roundabout Cafe"; truncation is now handled by brand_agrees(), which is
    checked separately so the raw score stays honest in the stored record.
    """
    if not ours or not theirs:
        return 0.0
    return name_match.similarity(ours, theirs)


def best_candidate(arcade, places):
    """Pick the best-graded Google result for one arcade.

    Returns (chosen_or_None, rejects). `chosen` carries the grade; `rejects`
    lists every candidate that did not win, with why, for the miss log.
    """
    lat, lng = arcade.get("lat"), arcade.get("lng")
    approx_level = arcade.get("approx_level") if arcade.get("approx") else None
    scored, rejects = [], []

    for p in places or []:
        pid = p.get("id")
        if not pid:
            continue
        disp = ((p.get("displayName") or {}).get("text") or "").strip()
        addr = (p.get("formattedAddress") or "").strip()
        loc = p.get("location") or {}
        plat, plng = loc.get("latitude"), loc.get("longitude")

        dist = None
        if lat is not None and lng is not None and \
                plat is not None and plng is not None:
            dist = merge.haversine_m(float(lat), float(lng),
                                     float(plat), float(plng))

        sim = score_name(arcade.get("name"), disp)
        brand = brand_agrees(arcade.get("name"), disp)
        conf, reason = classify(dist, sim, approx_level, brand_ok=brand)
        rec = {
            "place_id": pid,
            "matched_name": disp or None,
            "matched_addr": addr or None,
            "dist_m": round(dist, 1) if dist is not None else None,
            "name_sim": round(sim, 3),
            "brand_match": brand,
            "confidence": conf,
            "reason": reason,
        }
        if conf == "reject":
            rejects.append(rec)
        else:
            scored.append(rec)

    if not scored:
        return None, rejects

    # Best grade first, then closest, then best name. Distance breaks the tie
    # before name does: within one grade the candidates are all plausibly named
    # and the nearer one is the one our pin is actually standing on.
    def key(r):
        return (CONFIDENCE_ORDER.index(r["confidence"]),
                r["dist_m"] if r["dist_m"] is not None else 1e9,
                -r["name_sim"])

    scored.sort(key=key)
    chosen = scored[0]
    rejects = rejects + scored[1:]
    return chosen, rejects


# --------------------------------------------------------------- transport --

class ApiError(RuntimeError):
    """A Google API call that failed in a way worth stopping for."""

    def __init__(self, msg, status=None):
        RuntimeError.__init__(self, msg)
        self.status = status


def _request(url, key, mask, body=None):
    """One Places API call with retries. Returns parsed JSON.

    POST when `body` is given (Text Search), GET otherwise (ID refresh).
    Raises ApiError on a 4xx that retrying cannot fix, so a bad key stops the
    run instead of quietly burning through the whole file.
    """
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    headers = {
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": mask,
        "User-Agent": common.USER_AGENT,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"

    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, data=data, headers=headers,
                                         method="POST" if data else "GET")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
            time.sleep(SLEEP)
            return json.loads(raw.decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:400]
            except Exception:      # pragma: no cover - best effort only
                pass
            # 400/401/403 will not get better on retry: bad key, wrong
            # restriction, API not enabled, or billing off. Stop loudly.
            if e.code in (400, 401, 403):
                raise ApiError("HTTP %d from %s: %s" % (e.code, url, detail),
                               status=e.code)
            last = e
            if e.code == 404:
                return None
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e
        wait = 2 ** attempt
        print("place_ids: attempt %d/%d failed (%s); retry in %ds"
              % (attempt + 1, RETRIES, last, wait), file=sys.stderr)
        time.sleep(wait)
    raise ApiError("giving up on %s after %d attempts: %s"
                   % (url, RETRIES, last))


def search_text(key, arcade, radius_m=3000.0):
    """Text Search for one arcade. Returns the raw places[] list."""
    q = " ".join([x for x in (arcade.get("name"), arcade.get("addr")) if x])
    body = {"textQuery": q, "pageSize": 5}

    lat, lng = arcade.get("lat"), arcade.get("lng")
    if lat is not None and lng is not None:
        # Bias, not restrict: a restriction would drop the correct venue when
        # our own pin is the one that is slightly off, which is precisely the
        # case we are trying to fix. The distance gate in classify() is what
        # actually enforces proximity.
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": float(lat), "longitude": float(lng)},
                "radius": float(radius_m),
            }
        }
    region = COUNTRY_REGION.get(arcade.get("country"))
    if region:
        body["regionCode"] = region

    blob = _request(SEARCH_URL, key, SEARCH_MASK, body=body)
    return (blob or {}).get("places") or []


def refresh_id(key, place_id):
    """Free ID-refresh call. Returns the current id, or None if obsolete."""
    blob = _request(DETAILS_URL % urllib_quote(place_id), key, REFRESH_MASK)
    if not blob:
        return None
    return blob.get("id") or None


def urllib_quote(s):
    import urllib.parse
    return urllib.parse.quote(str(s), safe="")


# CLDR region codes, for the countries this dataset actually has volume in.
# regionCode only formats and nudges results; an absent country is fine.
COUNTRY_REGION = {
    "Japan": "JP", "China": "CN", "Hong Kong": "HK", "Macau": "MO",
    "Taiwan": "TW", "South Korea": "KR", "Singapore": "SG",
    "Malaysia": "MY", "Indonesia": "ID", "Thailand": "TH",
    "Philippines": "PH", "Vietnam": "VN", "United States": "US",
    "Canada": "CA", "Mexico": "MX", "Brazil": "BR", "Australia": "AU",
    "New Zealand": "NZ", "United Kingdom": "GB", "France": "FR",
    "Germany": "DE", "Spain": "ES", "Italy": "IT", "Netherlands": "NL",
}


# ------------------------------------------------------------------- store --

def empty_store():
    return {
        "updated": None,
        "source": "google-places-textsearch",
        "note": ("Place IDs only. Google's terms exempt place IDs from the "
                 "no-caching rule; photo names and photo bytes are NOT "
                 "exempt and are never stored here or anywhere else in this "
                 "repo. js/gphotos.js fetches photos live in the browser."),
        "thresholds": {
            "max_dist_m": MAX_DIST_M,
            "approx_min_sim": APPROX_MIN_SIM,
        },
        "places": {},
        "misses": {},
    }


def load_store(path):
    if not os.path.isfile(path):
        return empty_store()
    try:
        blob = common.load_json(path)
    except (ValueError, OSError) as e:
        print("place_ids: WARNING could not read %s (%s); starting fresh"
              % (path, e), file=sys.stderr)
        return empty_store()
    if not isinstance(blob, dict):
        return empty_store()
    base = empty_store()
    base.update(blob)
    base["places"] = blob.get("places") or {}
    base["misses"] = blob.get("misses") or {}
    return base


def save_store(path, store):
    store["updated"] = date.today().isoformat()
    common.save_json(path, store)


def stale(resolved_at, months=12):
    """True when an ISO date is older than `months` months (Google's advice)."""
    if not resolved_at:
        return True
    try:
        then = datetime.strptime(str(resolved_at)[:10], "%Y-%m-%d").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - then).days > months * 30


# ----------------------------------------------------------------- selection --

# MUST mirror js/panel.js imageRecords(), which is what actually decides
# whether a Google photo is ever asked for at runtime. That function reads an
# images[] array AND four single-field spellings, on both the arcade row and
# the enrichment entry. If this list is narrower than that one, we pay for a
# Text Search on an arcade the frontend will never show a Google photo for -
# the ID is resolved, then the panel finds a photo it already had and never
# calls Google. Real money for nothing.
#
# Today every photographed entry uses images[] (1,013 of them, 0 single-field),
# so the extra fields are currently a no-op. They are here because the BemaniCN
# harvest shapes `image_thumb`, and the day one lands without an images[] array
# is the day this silently starts billing.
PHOTO_FIELDS = ("image_thumb", "image", "photo", "photo_url")


def _has_photo(entry):
    if not isinstance(entry, dict):
        return False
    if entry.get("images"):
        return True
    return any(entry.get(f) for f in PHOTO_FIELDS)


def photo_ids_from_enrichment(enrich_path, arcades=None):
    """Arcade ids that already have a real venue photo of our own.

    Ours is licence-clean and free, so Google is only ever asked to fill a
    gap. Resolving an ID for a store we can already illustrate is money spent
    on a photo js/gphotos.js will never show.
    """
    out = set()

    # The arcade row itself can carry a photo field, and panel.js checks it
    # first, so it counts as "already photographed" too.
    for a in (arcades or []):
        if _has_photo(a):
            out.add(str(a.get("id")))

    if not os.path.isfile(enrich_path):
        return out
    try:
        blob = common.load_json(enrich_path)
    except (ValueError, OSError):
        return out
    for k, v in (blob.get("arcades") or {}).items():
        if _has_photo(v):
            out.add(str(k))
    return out


def select_arcades(arcades, store, args, have_photo):
    """The rows this run should spend money on, in a stable order."""
    todo = []
    for a in arcades:
        aid = str(a.get("id"))
        if args.country and a.get("country") != args.country:
            continue
        if aid in store["places"] and not args.redo:
            continue
        if aid in store["misses"] and not args.retry_misses:
            continue
        if a.get("lat") is None or a.get("lng") is None:
            # No coordinate means no distance test, and classify() would
            # reject it anyway. Skipping costs nothing and saves a Pro call.
            continue
        if a.get("approx") and not args.include_approx:
            continue
        if args.missing_photos_only and aid in have_photo:
            continue
        todo.append(a)
    return todo


# -------------------------------------------------------------------- runs --

def run_resolve(key, args):
    out_path = os.path.join(args.out, OUTFILE)
    store = load_store(out_path)

    arcades = common.load_json(os.path.join(args.out, ARCADES_FILE))["arcades"]
    have_photo = (photo_ids_from_enrichment(
                      os.path.join(args.out, ENRICH_FILE), arcades)
                  if args.missing_photos_only else set())

    todo = select_arcades(arcades, store, args, have_photo)
    total_candidates = len(todo)

    if args.all:
        limit = total_candidates
    else:
        limit = min(args.limit, total_candidates)
    todo = todo[:limit]

    billable = max(0, len(todo) - TEXT_SEARCH_PRO_FREE_PER_MONTH)
    est = billable * TEXT_SEARCH_PRO_USD_PER_1K / 1000.0
    print("place_ids: %d arcade(s) need resolving; this run will make %d Text "
          "Search Pro call(s)" % (total_candidates, len(todo)), file=sys.stderr)
    print("place_ids: cost if the monthly %d-call free pool is untouched: "
          "USD %.2f (%d billable @ $%.2f/1k)"
          % (TEXT_SEARCH_PRO_FREE_PER_MONTH, est, billable,
             TEXT_SEARCH_PRO_USD_PER_1K), file=sys.stderr)

    if args.dry_run:
        print("place_ids: --dry-run, no requests made")
        for a in todo[:10]:
            print("  would resolve %s  %s  (%s)"
                  % (a.get("id"), a.get("name"), a.get("country")))
        return 0

    if args.all and not args.yes:
        print("place_ids: --all resolves everything and can bill real money. "
              "Re-run with --all --yes once the estimate above is acceptable.",
              file=sys.stderr)
        return 1

    if not todo:
        print("place_ids: nothing to do")
        return 0

    done = 0
    graded = {"high": 0, "medium": 0, "low": 0, "reject": 0}
    try:
        for a in todo:
            aid = str(a.get("id"))
            try:
                places = search_text(key, a, radius_m=args.radius)
            except ApiError as e:
                if e.status in (400, 401, 403):
                    print("place_ids: FATAL %s" % e, file=sys.stderr)
                    print("place_ids: check the key, that Places API (New) is "
                          "enabled, and that billing is on. Nothing further "
                          "was requested.", file=sys.stderr)
                    break
                print("place_ids: %s failed: %s" % (aid, e), file=sys.stderr)
                continue

            chosen, rejects = best_candidate(a, places)
            done += 1

            if chosen is None:
                graded["reject"] += 1
                store["misses"][aid] = {
                    "name": a.get("name"),
                    "country": a.get("country"),
                    "checked_at": date.today().isoformat(),
                    "reason": "no_candidate_passed" if places else "no_results",
                    "candidates": rejects[:3],
                }
                store["places"].pop(aid, None)
                print("  MISS %-6s %-40.40s  %s"
                      % (aid, a.get("name") or "",
                         rejects[0]["reason"] if rejects else "no results"))
            else:
                graded[chosen["confidence"]] += 1
                rec = dict(chosen)
                rec["name"] = a.get("name")
                rec["country"] = a.get("country")
                rec["resolved_at"] = date.today().isoformat()
                if a.get("approx"):
                    rec["via_approx"] = a.get("approx_level") or True
                store["places"][aid] = rec
                store["misses"].pop(aid, None)
                print("  %-6s %-6s %-32.32s -> %-32.32s  %sm sim=%.2f"
                      % (chosen["confidence"], aid, a.get("name") or "",
                         chosen["matched_name"] or "",
                         chosen["dist_m"], chosen["name_sim"]))

            if done % SAVE_EVERY == 0:
                save_store(out_path, store)
    finally:
        save_store(out_path, store)

    print("place_ids: wrote %s (%d resolved this run: %d high, %d medium, "
          "%d low, %d miss; %d stored total)"
          % (out_path, done, graded["high"], graded["medium"], graded["low"],
             graded["reject"], len(store["places"])), file=sys.stderr)
    return 0


def run_refresh(key, args):
    """Re-verify IDs older than 12 months. Free (Essentials IDs Only SKU)."""
    out_path = os.path.join(args.out, OUTFILE)
    store = load_store(out_path)

    old = [(aid, rec) for aid, rec in sorted(store["places"].items())
           if stale(rec.get("resolved_at"), args.months)]
    if args.all:
        limit = len(old)
    else:
        limit = min(args.limit, len(old))
    old = old[:limit]

    print("place_ids: %d stored ID(s), %d older than %d months; refreshing %d "
          "(free: Place Details Essentials IDs Only)"
          % (len(store["places"]), len(old), args.months, len(old)),
          file=sys.stderr)

    if args.dry_run or not old:
        return 0

    changed = gone = ok = 0
    try:
        for i, (aid, rec) in enumerate(old, 1):
            try:
                now_id = refresh_id(key, rec.get("place_id"))
            except ApiError as e:
                # 401/403 are KEY problems (bad key, wrong restriction, API
                # off) and every remaining call would fail the same way, so
                # stop. A 400 is INVALID_REQUEST for THIS id - a truncated or
                # malformed stored place_id - and that must not abort the
                # batch: refresh is free and re-runnable, and one bad row
                # would otherwise poison every future --refresh --all run.
                if e.status in (401, 403):
                    print("place_ids: FATAL %s" % e, file=sys.stderr)
                    break
                if e.status == 400:
                    gone += 1
                    store["misses"][aid] = {
                        "name": rec.get("name"),
                        "country": rec.get("country"),
                        "checked_at": date.today().isoformat(),
                        "reason": "place_id_invalid",
                        "was": rec.get("place_id"),
                    }
                    store["places"].pop(aid, None)
                    print("  BAD  %-6s %s (invalid place_id, dropped)"
                          % (aid, rec.get("name") or ""))
                    continue
                print("place_ids: refresh %s failed: %s" % (aid, e),
                      file=sys.stderr)
                continue

            if now_id is None:
                # NOT_FOUND: the place is obsolete (closed, moved, or the Maps
                # database reissued it). Drop it rather than keep pointing the
                # site at a dead ID; a later resolve run can find the new one.
                gone += 1
                store["misses"][aid] = {
                    "name": rec.get("name"),
                    "country": rec.get("country"),
                    "checked_at": date.today().isoformat(),
                    "reason": "place_id_obsolete",
                    "was": rec.get("place_id"),
                }
                store["places"].pop(aid, None)
                print("  GONE %-6s %s" % (aid, rec.get("name") or ""))
            else:
                if now_id != rec.get("place_id"):
                    changed += 1
                    rec["place_id"] = now_id
                    print("  MOVED %-6s -> %s" % (aid, now_id))
                else:
                    ok += 1
                rec["resolved_at"] = date.today().isoformat()
                store["places"][aid] = rec

            if i % SAVE_EVERY == 0:
                save_store(out_path, store)
    finally:
        save_store(out_path, store)

    print("place_ids: refresh done (%d unchanged, %d reissued, %d obsolete)"
          % (ok, changed, gone), file=sys.stderr)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Resolve arcades to Google place IDs (opt-in, needs "
                    "GOOGLE_MAPS_API_KEY). Photos are NEVER stored.")
    ap.add_argument("--out", default="data", help="data directory")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="max arcades this run (default %d)" % DEFAULT_LIMIT)
    ap.add_argument("--all", action="store_true",
                    help="ignore --limit; requires --yes because it bills")
    ap.add_argument("--yes", action="store_true",
                    help="confirm a billable --all run")
    ap.add_argument("--country", help="only this country")
    ap.add_argument("--radius", type=float, default=3000.0,
                    help="location bias radius in metres (default 3000)")
    ap.add_argument("--redo", action="store_true",
                    help="re-resolve arcades that already have an ID")
    ap.add_argument("--retry-misses", action="store_true",
                    help="re-try arcades previously recorded as a miss")
    ap.add_argument("--include-approx", action="store_true",
                    help="also try centroid-placed rows (strict name gate)")
    ap.add_argument("--missing-photos-only", dest="missing_photos_only",
                    action="store_true", default=True,
                    help="skip arcades that already have our own venue photo "
                         "(default)")
    ap.add_argument("--include-photographed", dest="missing_photos_only",
                    action="store_false",
                    help="also resolve arcades we already have a photo for")
    ap.add_argument("--refresh", action="store_true",
                    help="re-verify stored IDs older than --months (free)")
    ap.add_argument("--months", type=int, default=12,
                    help="staleness window for --refresh (default 12)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be requested, request nothing")
    args = ap.parse_args(argv)

    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        # THE NO-KEY CONTRACT. No request, no file, exit 0. The weekly Action
        # has no key and must keep passing; see fx.py / geocode_cn.py.
        print("place_ids: %s is not set; nothing to do (this tool is opt-in "
              "and makes no request without a key). See docs/GOOGLE_PHOTOS.md."
              % ENV_KEY, file=sys.stderr)
        return 0

    if args.refresh:
        return run_refresh(key, args)
    return run_resolve(key, args)


if __name__ == "__main__":
    sys.exit(main())
