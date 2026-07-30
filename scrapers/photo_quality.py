"""Judge whether a venue photo is worth putting in the place panel.

WHY THIS EXISTS
---------------
The pipeline harvests up to three community photos per arcade and the panel
shows images[0] as a hero banner. Nothing ever asked whether that photo was
worth a reader's attention. The owner's complaint was concrete: the hero for
Round1 Ikebukuro is a blurry close-up of people's legs beside a crane-game
cabinet, and it "seems old and outdated". It is a real photo of that venue,
so the SOURCE was never the problem - the absence of any judgement was.

WHAT THIS CAN AND CANNOT JUDGE (read this before trusting a score)
------------------------------------------------------------------
This repo is stdlib-only: no PIL, no numpy, no decoder. So this module never
looks at a single pixel. It reads the image HEADER (which is a few hundred
bytes at the front of the file) plus the byte length the server reports, and
it reasons from four measurables:

    pixel width x height   real, from the JPEG SOF / PNG IHDR / WebP / GIF header
    byte size              real, from Content-Range or Content-Length
    aspect ratio           derived, w/h
    bytes per pixel        derived, size/(w*h) - a compression proxy ONLY

From those it can honestly answer:

  * "will this upscale into a blurry mess in a 416x148 hero slot?"  YES
  * "will object-fit: cover crop this to a meaningless sliver?"     YES
  * "was this uploaded in 2012 or last year?"                       YES, when
      the filename carries a unix timestamp (ZIv's do; see url_timestamp)
  * "is this a heavily-compressed / low-detail file for its size?"  WEAKLY,
      via bytes-per-pixel, which is a proxy and nothing more

It CANNOT answer, and this module never claims to:

  * "is this photo blurry?"        - needs pixels. Low bytes-per-pixel
      correlates with softness because a blurred image has less high-frequency
      detail to encode, but it correlates just as well with a legitimately
      flat subject (a night shot, a plain wall). It is a hint, never a verdict.
  * "is this a photo of legs / a floor / someone's thumb?" - needs a model.
  * "is this the storefront or the inside of a toilet?"    - needs a model.

So of the owner's two complaints, this module addresses ONE AND A HALF:

  "seems old and outdated"   -> ADDRESSED. Upload date is recoverable from the
                                filename and is a first-class ranking signal.
  "conveys no useful information" -> NOT ADDRESSED, except where low value
                                happens to coincide with low resolution, a
                                punishing crop, or a tiny file. A sharp,
                                large, recent, well-proportioned photo of
                                nothing in particular scores well here. Only
                                a human or a vision model can catch that.

RANK, DO NOT ONLY REJECT
------------------------
Most arcades that have photos have two or three of them (170 have 2, 482 have
3). Throwing images away is the last resort; putting the BEST one in the hero
slot and the rest behind it in the slideshow is the main event. score() emits
a number, a verdict and a human-readable reason list for every image, so a
reviewer can audit the ordering instead of trusting it.

USAGE
-----
    # measure every image in data/enrichment.json, write the sidecar report
    python3 scrapers/photo_quality.py --enrichment data/enrichment.json \\
        --out data_raw/photo_quality.json

    # re-score from the cache without re-fetching (thresholds changed)
    python3 scrapers/photo_quality.py --enrichment data/enrichment.json \\
        --out data_raw/photo_quality.json --offline

    # look at one venue
    python3 scrapers/photo_quality.py --arcade 9073

This module NEVER writes data/enrichment.json. It emits a sidecar keyed by
image URL, and the enrichment step (owned elsewhere) is what applies it.
See apply_to_images() for the one function a caller needs.

Stdlib only, same rule as the rest of scrapers/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

DEFAULT_CACHE = os.path.join("data_raw", "photo_probe_cache.json")
DEFAULT_OUT = os.path.join("data_raw", "photo_quality.json")

# ---------------------------------------------------------------------------
# Thresholds, all derived from the panel's real geometry rather than guessed.
# ---------------------------------------------------------------------------
#
# style.css, the hero slot:
#
#   --panel-w: 416px            the default desktop column width
#   .pl-hero.has-photo          height: 148px      (desktop)
#   @media (max-width: 760px)   height: 62px resting, 132px when expanded
#   .pl-hero-img                object-fit: cover
#
# So the hero box is 416 x 148 CSS px by default. panel.js lets the reader drag
# the column to 0.55 * viewport width, which on a 1600px screen is 880px, and
# every phone worth naming is DPR 2 or 3. The full-fidelity requirement is
# therefore enormous (880 * 2 = 1760px wide) and using it as a floor would
# reject most of the corpus, which is not the goal.
#
# The floor is set at the point where the image starts being UPSCALED in the
# default slot at 1x, because that is where an image visibly stops being a
# photo and starts being a smear:
#
#   width  >= 416   the default hero width
#   height >= 148   the default hero height
#
# and the "no penalty" bar is set at the same slot at DPR 2 (832 x 296), which
# is what a phone or a retina laptop actually asks the browser for.
HERO_W = 416
HERO_H = 148
HERO_AR = HERO_W / float(HERO_H)          # 2.81
CRISP_W = HERO_W * 2                      # 832
CRISP_H = HERO_H * 2                      # 296

# Below this an image cannot fill the default hero without upscaling.
MIN_W = HERO_W
MIN_H = HERO_H
# A hard floor on total pixels catches the pathological case of a 2000x60
# strip that passes MIN_W: 416*148 = 61,568.
MIN_PIXELS = HERO_W * HERO_H

# The owner's "7 KB thumbnail blown up into a hero slot". A JPEG that is
# genuinely 416x148 or larger and still under 12 KB is either a solid-colour
# placeholder or compressed into mush.
MIN_BYTES = 12 * 1024

# Aspect limits are ASYMMETRIC on purpose, because object-fit: cover crops the
# two directions very differently against a 2.81:1 box:
#
#   a 4:3 landscape (1.33) is scaled to width and shows 1.33/2.81 = 47% of its
#     height - the normal, accepted case for this corpus
#   a 3:4 portrait (0.75) shows 27% of its height
#   a 9:16 phone portrait (0.56) shows 20% - a horizontal band through the
#     middle of a photo whose subject is almost certainly above or below it
#   a 4:1 panorama is scaled to height and shows 2.81/4 = 70% of its WIDTH,
#     which is a far gentler loss: you lose the edges, not the subject
#
# So portrait is policed tightly and panorama loosely.
MIN_AR = 0.60      # taller than 3:5 - only ~21% of the height survives
MAX_AR = 5.0       # wider than 5:1 - a letterbox strip, subject unlocatable
GOOD_AR_LO = 1.10  # no aspect penalty inside this band
GOOD_AR_HI = 2.20

# bytes-per-pixel, a COMPRESSION proxy and nothing more. Measured over this
# corpus a normal ZIv JPEG sits around 0.1-0.35 bpp. Below 0.04 the file is
# carrying very little detail for its dimensions. This never rejects on its
# own - it only subtracts score - because a flat or dark subject produces the
# same number as a soft one and this module cannot tell them apart.
LOW_BPP = 0.04
GOOD_BPP = 0.12

# Recency. ZIv filenames embed the unix upload time, so an image's age is
# knowable. The owner's complaint that a photo "seems old and outdated" is a
# real ranking signal: arcades in Japan re-fit their floors constantly and a
# 2012 photo shows machines that left years ago.
RECENT_YEARS = 3.0    # full recency credit
STALE_YEARS = 12.0    # zero recency credit at or beyond this

# Score weights. They sum to 100 before penalties.
W_RESOLUTION = 45
W_ASPECT = 20
W_RECENCY = 25
W_DETAIL = 10

# Verdict bands.
SCORE_GOOD = 60      # >= this is a happy hero
SCORE_WEAK = 35      # below this it is only shown if nothing better exists

TIER_ORDER = {"venue": 0, "chain": 1, "street": 2, "cab": 3}


# ---------------------------------------------------------------------------
# Header parsing. No decoder, no third-party library: just the bytes at the
# front of the file, which is where every one of these formats states its size.
# ---------------------------------------------------------------------------

def parse_jpeg_size(data):
    """(width, height) from a JPEG's SOF marker, or None.

    A JPEG is a chain of 0xFF-prefixed segments. The frame header (SOFn) is the
    only one that carries the picture size, and it can sit a long way in: an
    EXIF thumbnail or an embedded ICC profile easily pushes it past 64 KB. The
    caller is expected to widen its read when this returns None (see probe()).

    SOF0/1/2/3, 5/6/7, 9/10/11, 13/14/15 are all frame headers with the same
    layout. C4 (Huffman table), C8 (JPEG extension) and CC (arithmetic coding
    conditioning) share the 0xCn range and are NOT frame headers, which is the
    bug every naive version of this function has.
    """
    if len(data) < 4 or data[0] != 0xFF or data[1] != 0xD8:
        return None
    i = 2
    n = len(data)
    while i + 3 < n:
        if data[i] != 0xFF:
            # Fill bytes (0xFF padding) are legal between segments; anything
            # else means we have lost sync and guessing further is worse than
            # admitting we do not know.
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        # Standalone markers with no length field.
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xD9:          # EOI
            return None
        if i + 3 >= n:
            return None
        seg_len = (data[i + 2] << 8) | data[i + 3]
        if seg_len < 2:
            return None
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if i + 9 >= n:
                return None
            h = (data[i + 5] << 8) | data[i + 6]
            w = (data[i + 7] << 8) | data[i + 8]
            if w and h:
                return (w, h)
            return None
        if marker == 0xDA:          # start of scan: no SOF was present
            return None
        i += 2 + seg_len
    return None


def parse_png_size(data):
    """(width, height) from a PNG IHDR, or None. IHDR is always first."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if data[12:16] != b"IHDR":
        return None
    w = int.from_bytes(data[16:20], "big")
    h = int.from_bytes(data[20:24], "big")
    return (w, h) if w and h else None


def parse_gif_size(data):
    """(width, height) from a GIF logical screen descriptor, or None."""
    if len(data) < 10 or data[:3] != b"GIF":
        return None
    w = int.from_bytes(data[6:8], "little")
    h = int.from_bytes(data[8:10], "little")
    return (w, h) if w and h else None


def parse_webp_size(data):
    """(width, height) from a WebP, or None. Three sub-formats, three layouts."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    fourcc = data[12:16]
    if fourcc == b"VP8 ":
        # Lossy: 3-byte frame tag, 3-byte start code, then 14-bit w and h.
        if len(data) < 30:
            return None
        if data[23:26] != b"\x9d\x01\x2a":
            return None
        w = int.from_bytes(data[26:28], "little") & 0x3FFF
        h = int.from_bytes(data[28:30], "little") & 0x3FFF
        return (w, h) if w and h else None
    if fourcc == b"VP8L":
        if len(data) < 25 or data[20] != 0x2F:
            return None
        bits = int.from_bytes(data[21:25], "little")
        w = (bits & 0x3FFF) + 1
        h = ((bits >> 14) & 0x3FFF) + 1
        return (w, h)
    if fourcc == b"VP8X":
        if len(data) < 30:
            return None
        w = int.from_bytes(data[24:27], "little") + 1
        h = int.from_bytes(data[27:30], "little") + 1
        return (w, h)
    return None


def parse_size(data):
    """(width, height, format) from any header this module understands."""
    for fn, name in ((parse_png_size, "png"), (parse_gif_size, "gif"),
                     (parse_webp_size, "webp"), (parse_jpeg_size, "jpeg")):
        got = fn(data)
        if got:
            return (got[0], got[1], name)
    return (None, None, None)


# ---------------------------------------------------------------------------
# Upload time from the filename.
# ---------------------------------------------------------------------------

# ZIv publishes pictures under two filename shapes and both carry a unix time:
#
#   833-1365881991[0].jpg   <album-id>-<unix>[<n>].ext   -> 1365881991
#   1473506067.8204.png     <unix>.<fraction>.ext        -> 1473506067
#
# In the first shape the LEADING number is an album id, not a timestamp, which
# is the trap: 833 and 5796 are not dates. Both patterns are anchored so a
# filename that carries neither (SNBETASQ.jpg) yields None rather than a lie.
_TS_DASH = re.compile(r"^\d{1,5}-(\d{9,11})(?:\[\d+\])?\.[a-z0-9]+$", re.I)
_TS_DOT = re.compile(r"^(\d{9,11})\.\d+\.[a-z0-9]+$", re.I)

# Sanity window: 2001-09-09 .. 2033-05-18. A number outside it is not a date
# this corpus could contain, so it is treated as absent rather than believed.
TS_MIN = 1000000000
TS_MAX = 2000000000


def url_timestamp(url):
    """Unix upload time embedded in the filename, or None if it carries none.

    None is a NEUTRAL signal downstream, not "ancient" and not "brand new":
    scoring an unknown as either would invent information. See score().
    """
    if not url:
        return None
    name = url.rstrip("/").split("/")[-1].split("?")[0]
    for pat in (_TS_DASH, _TS_DOT):
        m = pat.match(name)
        if m:
            ts = int(m.group(1))
            if TS_MIN <= ts <= TS_MAX:
                return ts
    return None


def ts_to_date(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def age_years(ts, now=None):
    if ts is None:
        return None
    now = now if now is not None else time.time()
    return max(0.0, (now - ts) / (365.2425 * 86400.0))


# ---------------------------------------------------------------------------
# Probing. One ranged GET per image, cached to disk.
# ---------------------------------------------------------------------------

FIRST_SLICE = 4096          # enough for a PNG IHDR and most JPEG SOFs
WIDE_SLICE = 262143         # re-read when a fat EXIF/ICC pushed SOF past 4 KB


def _http_slice(url, last_byte, timeout=25):
    """(payload, total_bytes, status). Handles a server that ignores Range.

    A 206 gives the true total in Content-Range. A 200 means Range was ignored
    and the whole file arrived, so Content-Length IS the total and the payload
    is complete - both are useful, they just have to be told apart.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Range": "bytes=0-%d" % last_byte,
        "Accept": "image/*,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", None) or resp.getcode()
        raw = resp.read(last_byte + 1)
        total = None
        cr = resp.headers.get("Content-Range")
        if cr:
            m = re.search(r"/(\d+)\s*$", cr)
            if m:
                total = int(m.group(1))
        if total is None:
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                # Only trustworthy as a TOTAL when the server sent the whole
                # thing (200). On a 206 it is the slice length.
                if status == 200:
                    total = int(cl)
        return raw, total, status


def probe(url, sleep=0.15, retries=2):
    """Measure one image. Returns a dict, never raises.

    {url, bytes, width, height, format, ts, probe_status, error}

    probe_status is one of: ok | no_header | http_<code> | error
    """
    rec = {"url": url, "bytes": None, "width": None, "height": None,
           "format": None, "ts": url_timestamp(url),
           "probe_status": "error", "error": None}
    last_err = None
    for attempt in range(retries + 1):
        try:
            raw, total, status = _http_slice(url, FIRST_SLICE - 1)
            w, h, fmt = parse_size(raw)
            # A JPEG whose SOF sits behind a fat EXIF or ICC block needs a
            # wider read. Recording "unknown" here would silently skew the
            # dimension stats for an unknown slice of the corpus.
            if w is None and raw[:2] == b"\xff\xd8":
                time.sleep(sleep)
                raw2, total2, _ = _http_slice(url, WIDE_SLICE)
                if total2:
                    total = total2
                w, h, fmt = parse_size(raw2)
                if fmt is None:
                    fmt = "jpeg"
            if total is None and len(raw) < FIRST_SLICE:
                # The whole file fit inside the slice: its length is the total.
                total = len(raw)
            rec["bytes"] = total
            rec["width"], rec["height"] = w, h
            rec["format"] = fmt
            rec["probe_status"] = "ok" if (w and h) else "no_header"
            time.sleep(sleep)
            return rec
        except urllib.error.HTTPError as e:
            rec["probe_status"] = "http_%d" % e.code
            rec["error"] = str(e)
            # 4xx will not improve on a retry; 5xx might.
            if e.code < 500:
                return rec
            last_err = e
        except (urllib.error.URLError, OSError, ValueError) as e:
            last_err = e
            rec["error"] = "%s: %s" % (type(e).__name__, e)
        time.sleep(min(4.0, 2 ** attempt))
    if rec["probe_status"] == "error" and last_err is not None:
        rec["error"] = "%s: %s" % (type(last_err).__name__, last_err)
    return rec


# ---------------------------------------------------------------------------
# Scoring.
# ---------------------------------------------------------------------------

def _lerp_credit(value, zero_at, full_at):
    """0.0 at zero_at, 1.0 at full_at, linear between, clamped."""
    if value is None:
        return None
    if full_at == zero_at:
        return 1.0
    t = (value - zero_at) / float(full_at - zero_at)
    return max(0.0, min(1.0, t))


def score(rec, now=None):
    """Score one probed image. Returns a NEW dict with the verdict attached.

    Keys added: score (0-100), verdict (good|ok|weak|reject), reasons (list of
    short strings), and the derived measurements the reasons quote.

    A rejected image keeps its score so the pipeline can still order the
    rejects sensibly when an arcade has nothing better.
    """
    out = dict(rec)
    reasons = []
    w, h = rec.get("width"), rec.get("height")
    nbytes = rec.get("bytes")
    ts = rec.get("ts")

    ar = (w / float(h)) if (w and h) else None
    px = (w * h) if (w and h) else None
    bpp = (nbytes / float(px)) if (nbytes and px) else None
    yrs = age_years(ts, now)

    out["aspect"] = round(ar, 3) if ar is not None else None
    out["pixels"] = px
    out["bpp"] = round(bpp, 4) if bpp is not None else None
    out["date"] = ts_to_date(ts)
    out["age_years"] = round(yrs, 1) if yrs is not None else None

    # -- unmeasurable ---------------------------------------------------------
    # An image we could not measure is NOT rejected. A 403 on a probe is a
    # statement about our HTTP client, not about the photo, and dropping a
    # venue's only picture over it would be the filter doing more harm than
    # the thing it was written to prevent. It scores neutrally and sorts
    # after anything we could actually vouch for.
    if rec.get("probe_status") != "ok" or not (w and h):
        out["score"] = 40
        out["verdict"] = "unknown"
        out["reasons"] = ["not measurable (%s) - kept, ranked below measured "
                          "images" % rec.get("probe_status")]
        return out

    # -- hard rejects ---------------------------------------------------------
    hard = []
    if w < MIN_W or h < MIN_H:
        hard.append("too small: %dx%d upscales in the %dx%d hero slot"
                    % (w, h, HERO_W, HERO_H))
    if px < MIN_PIXELS:
        hard.append("too few pixels: %d < %d" % (px, MIN_PIXELS))
    if nbytes is not None and nbytes < MIN_BYTES:
        hard.append("tiny file: %.1f KB" % (nbytes / 1024.0))
    if ar is not None and ar < MIN_AR:
        hard.append("portrait %.2f:1 - cover shows only %d%% of its height"
                    % (ar, round(100 * ar / HERO_AR)))
    if ar is not None and ar > MAX_AR:
        hard.append("panorama %.2f:1 - cover shows only %d%% of its width"
                    % (ar, round(100 * HERO_AR / ar)))

    # -- component scores -----------------------------------------------------
    # Resolution: full credit at DPR-2 hero size, zero at the 1x floor. The
    # limiting dimension governs, because cover scales by whichever runs out
    # first.
    res_w = _lerp_credit(w, MIN_W, CRISP_W)
    res_h = _lerp_credit(h, MIN_H, CRISP_H)
    resolution = min(res_w, res_h)

    # Aspect: full credit inside the comfortable band, tapering to the limits.
    if ar is None:
        aspect = 0.5
    elif GOOD_AR_LO <= ar <= GOOD_AR_HI:
        aspect = 1.0
    elif ar < GOOD_AR_LO:
        aspect = _lerp_credit(ar, MIN_AR, GOOD_AR_LO)
    else:
        aspect = 1.0 - _lerp_credit(ar, GOOD_AR_HI, MAX_AR)

    # Recency: unknown is neutral (0.5), not zero. Guessing "ancient" for a
    # filename shape we do not recognise would demote a fine photo on no
    # evidence at all.
    if yrs is None:
        recency = 0.5
        reasons.append("upload date unknown from filename - neutral recency")
    else:
        recency = 1.0 - _lerp_credit(yrs, RECENT_YEARS, STALE_YEARS)

    # Detail: bytes-per-pixel, the weakest signal here and weighted like it.
    if bpp is None:
        detail = 0.5
    else:
        detail = _lerp_credit(bpp, LOW_BPP, GOOD_BPP)

    raw_score = (W_RESOLUTION * resolution + W_ASPECT * aspect +
                 W_RECENCY * recency + W_DETAIL * detail)

    out["parts"] = {
        "resolution": round(resolution, 3), "aspect": round(aspect, 3),
        "recency": round(recency, 3), "detail": round(detail, 3),
    }

    # -- reasons, in the order a reader would want them ------------------------
    if w >= CRISP_W and h >= CRISP_H:
        reasons.append("%dx%d - crisp at 2x in the hero slot" % (w, h))
    elif resolution >= 0.5:
        reasons.append("%dx%d - fine at 1x, soft on a retina screen" % (w, h))
    else:
        reasons.append("%dx%d - barely covers the %dx%d hero"
                       % (w, h, HERO_W, HERO_H))

    if ar is not None:
        if aspect >= 0.999:
            reasons.append("%.2f:1 crops cleanly" % ar)
        elif ar < GOOD_AR_LO:
            reasons.append("%.2f:1 portrait - cover keeps %d%% of its height"
                           % (ar, round(100 * min(1.0, ar / HERO_AR))))
        else:
            reasons.append("%.2f:1 wide - cover keeps %d%% of its width"
                           % (ar, round(100 * min(1.0, HERO_AR / ar))))

    if yrs is not None:
        reasons.append("uploaded %s (%.1f years old)" % (out["date"], yrs))

    if bpp is not None and bpp < LOW_BPP:
        reasons.append("%.3f bytes/pixel - heavily compressed or low-detail "
                       "(proxy only, not a blur measurement)" % bpp)

    if hard:
        out["score"] = round(min(raw_score, SCORE_WEAK - 1), 1)
        out["verdict"] = "reject"
        out["reasons"] = hard + reasons
        return out

    out["score"] = round(raw_score, 1)
    out["verdict"] = ("good" if raw_score >= SCORE_GOOD
                      else "ok" if raw_score >= SCORE_WEAK else "weak")
    out["reasons"] = reasons
    return out


def rank(scored):
    """Order one arcade's scored images best-first.

    Sort key, in order of precedence:
      1. verdict class - anything not rejected comes before every reject
      2. tier          - a photo of THIS venue beats a chain/street stand-in
      3. score         - the measured judgement
      4. incoming order - ties keep the order they arrived in

    That last rule matters more than it looks. Round1 Ikebukuro's three photos
    are all 480x640, all uploaded within 103 seconds of each other in 2012, and
    they therefore score IDENTICALLY. An earlier version tie-broke on the URL
    string, which silently reordered that venue's hero on no evidence at all
    and would have let this module take credit for a change it did not earn.
    A tie means "this module cannot tell these apart", and the honest
    expression of that is to leave them alone.

    Rejects are kept at the back rather than dropped, because dropping is a
    decision for the caller: an arcade whose only photo is a reject is better
    served by that photo than by the gradient placeholder, and only the caller
    knows whether anything better exists.
    """
    def key(item):
        i, r = item
        rejected = 1 if r.get("verdict") == "reject" else 0
        tier = TIER_ORDER.get(r.get("tier") or "venue", 9)
        return (rejected, tier, -float(r.get("score") or 0), i)
    return [r for _, r in sorted(enumerate(scored), key=key)]


def apply_to_images(images, probes, drop_rejects=True, keep_min=1, now=None):
    """THE function the pipeline calls. Rank an arcade's images[] in place.

    images : the enrichment images[] list (dicts with url/source/credit/... )
    probes : {url: probe_record} from the sidecar report
    drop_rejects : remove rejected images, but never below keep_min entries -
        an arcade with one bad photo keeps it rather than falling back to the
        gradient placeholder, which tells the reader strictly less.

    Returns a NEW list, best first, each entry carrying quality_score /
    quality_verdict / quality_reasons so the result stays auditable.
    """
    scored = []
    for im in images or []:
        url = im.get("url")
        p = probes.get(url) or {"url": url, "probe_status": "unprobed"}
        s = score(dict(p, tier=im.get("tier")), now=now)
        merged = dict(im)
        merged["quality_score"] = s["score"]
        merged["quality_verdict"] = s["verdict"]
        merged["quality_reasons"] = s["reasons"]
        if s.get("width"):
            merged["width"], merged["height"] = s["width"], s["height"]
        if s.get("date"):
            merged["taken_hint"] = s["date"]
        merged["_sort"] = s
        scored.append(merged)

    ordered = rank([dict(m["_sort"], _m=m) for m in scored])
    out = [o["_m"] for o in ordered]
    for o in out:
        o.pop("_sort", None)

    if drop_rejects:
        kept = [o for o in out if o.get("quality_verdict") != "reject"]
        if len(kept) >= keep_min:
            return kept
    return out


# ---------------------------------------------------------------------------
# Cache + CLI
# ---------------------------------------------------------------------------

def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(path, blob):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def images_from_enrichment(path):
    """[(arcade_id, image_dict), ...] for every image in the enrichment file."""
    blob = load_json(path) or {}
    out = []
    for aid, entry in (blob.get("arcades") or {}).items():
        for im in (entry.get("images") or []):
            if isinstance(im, dict) and im.get("url"):
                out.append((aid, im))
            elif isinstance(im, str) and im:
                out.append((aid, {"url": im, "tier": entry.get("image_tier")}))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--enrichment", default=os.path.join("data", "enrichment.json"))
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--arcade", help="probe only this arcade id")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.15)
    ap.add_argument("--offline", action="store_true",
                    help="re-score from the cache, fetch nothing")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the cache and re-probe everything")
    args = ap.parse_args(argv)

    pairs = images_from_enrichment(args.enrichment)
    if args.arcade:
        pairs = [p for p in pairs if str(p[0]) == str(args.arcade)]
    if args.limit:
        pairs = pairs[:args.limit]
    if not pairs:
        print("photo_quality: no images found", file=sys.stderr)
        return 1

    cache = load_json(args.cache, {}) or {}
    urls = []
    seen = set()
    for _, im in pairs:
        u = im["url"]
        if u not in seen:
            seen.add(u)
            urls.append(u)

    todo = [u for u in urls
            if args.refresh or (u not in cache and not args.offline)]
    print("photo_quality: %d images across %d arcades, %d to probe"
          % (len(urls), len(set(a for a, _ in pairs)), len(todo)))

    for i, u in enumerate(todo, 1):
        cache[u] = probe(u, sleep=args.sleep)
        if i % 50 == 0 or i == len(todo):
            print("  probed %d/%d" % (i, len(todo)), flush=True)
            save_json(args.cache, cache)
    if todo:
        save_json(args.cache, cache)

    by_arcade = {}
    for aid, im in pairs:
        by_arcade.setdefault(aid, []).append(im)

    report = {"updated": date.today().isoformat(),
              "hero_box": [HERO_W, HERO_H],
              "thresholds": {
                  "min_w": MIN_W, "min_h": MIN_H, "min_bytes": MIN_BYTES,
                  "min_aspect": MIN_AR, "max_aspect": MAX_AR,
                  "score_good": SCORE_GOOD, "score_weak": SCORE_WEAK,
              },
              "images": {}, "order": {}, "summary": {}}

    counts = {"good": 0, "ok": 0, "weak": 0, "reject": 0, "unknown": 0}
    demoted = 0
    for aid, ims in by_arcade.items():
        ranked = apply_to_images(ims, cache, drop_rejects=False)
        report["order"][aid] = [r["url"] for r in ranked]
        if ims and ranked and ims[0]["url"] != ranked[0]["url"]:
            demoted += 1
        for r in ranked:
            counts[r["quality_verdict"]] = counts.get(r["quality_verdict"], 0) + 1
            report["images"][r["url"]] = {
                "score": r["quality_score"], "verdict": r["quality_verdict"],
                "reasons": r["quality_reasons"],
                "width": r.get("width"), "height": r.get("height"),
                "bytes": (cache.get(r["url"]) or {}).get("bytes"),
                "date": r.get("taken_hint"),
            }
    report["summary"] = {
        "arcades": len(by_arcade), "images": len(report["images"]),
        "verdicts": counts, "arcades_with_new_hero": demoted,
    }
    save_json(args.out, report)
    print("photo_quality: wrote %s" % args.out)
    print("  verdicts: %s" % counts)
    print("  arcades whose hero changes: %d / %d" % (demoted, len(by_arcade)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
