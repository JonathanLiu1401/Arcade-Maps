"""Mirror BemaniCN per-shop venue photos into assets/venues/cn/.

Why the bytes must be mirrored (not linked)
-------------------------------------------
`GET https://map.bemanicn.com/s/<shop_id>` with the Inertia headers returns
`props.shop.image_thumb = {id, filename, url, shop_id}`. That `url` is a
SIGNED OSS link: it carries `?e=<unix_expiry>&token=<...>` and is scoped to
the exact `...jpg-thumbnail` path. Measured behaviour (2026-07-30/31):

  * the token expires within the hour,
  * stripping the query -> HTTP 401,
  * stripping the `-thumbnail` suffix -> HTTP 401,
  * `-large` / `-medium` / `-origin` / `-big` / `-preview` / `-w800` -> 401,
  * Qiniu `imageView2` resize params -> 401.

So a weekly JSON of remote URLs would ship 100% dead images. The only way
this source produces a working photo is to fetch the bytes while the token
is live and store them in the repo.

Only one photo per shop is publicly reachable. `props.images_count` says a
shop may have several, but `/shop/<id>/image`, `/api/miniapp/shop/<id>/image`
and the `images` Inertia partial are all login-walled (HTTP 401 or null).
No larger variant exists on the keyless surface. Expect ~150-200 px on the
long side and 7-10 KB per file: these are PANEL THUMBNAILS, not heroes, and
`data_raw/bemanicn_photos.json` records real pixel dimensions so the
frontend can refuse to upscale one into a hero slot.

Licence / courtesy (not legal advice)
-------------------------------------
BemaniCN publishes no ToS, no CC grant, and no photo licence page; the site
meta carries "(c) BEMANICN" and the photos are community uploads. We mirror
only because (a) the source already publishes this exact thumb for venue
identification on a public map, (b) signed URLs make linking impossible, and
(c) every file ships with attribution, a deep link to the shop page, and a
takedown path. See assets/venues/ATTRIBUTION.md. If BemaniCN objects, delete
assets/venues/cn/ and degrade to link-out only.

Outputs
-------
  assets/venues/cn/<shop_id>.jpg   original bytes, never re-encoded
  data_raw/bemanicn_photos.json    shop_id -> {file, w, h, bytes, sha256,
                                   fetched_at, credit, source_url, ...}

The crawl is resumable: every shop result is appended to a JSONL journal
(`data_raw/tmp_bemanicn_photos.jsonl`, gitignored via `data_raw/tmp*`) as it
completes, and a rerun skips any shop already recorded there. The index is
rebuilt from the journal, so a crash costs at most one shop.

Usage
-----
  python scrapers/bemanicn_photos.py --limit 25      # smoke test
  python scrapers/bemanicn_photos.py                 # full crawl
  python scrapers/bemanicn_photos.py --ids-file x.json
  python scrapers/bemanicn_photos.py --rebuild-index # journal -> index only

A serial full crawl of ~3,800 shops takes about 4.5 hours (latency-bound, not
rate-limited). Splitting the id list across 3 processes with one journal each
finishes in ~75 minutes and still holds the origin under ~0.8 req/s. Rebuild
the single canonical index afterwards from ALL the journals, passing the FULL
id list so every record still resolves its arcade_id and country:

  python scrapers/bemanicn_photos.py --rebuild-index \
      --ids-file all_shop_ids.json \
      --journal data_raw/tmp_bemanicn_shard0.jsonl \
      --extra-journal data_raw/tmp_bemanicn_shard1.jsonl \
      --extra-journal data_raw/tmp_bemanicn_shard2.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
# Import ONLY common. bemanicn.py pulls in enrich -> photos, which other
# agents edit; an unrelated syntax error there must not kill a 2 hour crawl.

BASE = "https://map.bemanicn.com"
INERTIA_HDRS = {"X-Inertia": "true", "X-Inertia-Version": "",
                "Accept": "application/json"}

SLEEP = 0.4          # politeness pause, map.bemanicn.com only
RETRIES = 3
IMG_RETRIES = 2      # signed-URL fetch attempts (each re-signs the URL)

CREDIT = "Photo: BemaniCN community map"
SOURCE = "bemanicn"
LICENSE = None       # no public licence grant found; see ATTRIBUTION.md

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(REPO, "assets", "venues", "cn")
INDEX_PATH = os.path.join(REPO, "data_raw", "bemanicn_photos.json")
JOURNAL_PATH = os.path.join(REPO, "data_raw", "tmp_bemanicn_photos.jsonl")
ARCADES_PATH = os.path.join(REPO, "data", "arcades.json")

# Status values recorded in the journal.
OK = "ok"                    # bytes mirrored
NO_PHOTO = "no_photo"        # shop exists, image_thumb is null
GONE = "gone"                # shop id 404s
IMAGE_GONE = "image_gone"    # shop lists a thumb, but OSS 404s the object
ERROR = "error"              # transient/unexpected failure, retried next run
# Statuses a resume treats as settled. IMAGE_GONE is included: the row exists
# in BemaniCN's DB but the file is missing from OSS, so re-signing the URL on
# a later run cannot conjure it back.
PERMANENT = (OK, NO_PHOTO, GONE, IMAGE_GONE)


# --------------------------------------------------------------------------
# image sniffing (stdlib only, no PIL)
# --------------------------------------------------------------------------

def sniff_format(data):
    """Return 'jpg' / 'png' / 'webp' / 'gif' / None from magic bytes."""
    if data[:2] == b"\xff\xd8":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def jpeg_size(data):
    """(width, height) from a JPEG's SOF marker, or (None, None).

    Walks the marker chain. Any SOF marker counts (SOF0 baseline, SOF2
    progressive, SOF1/3/5..7/9..15), excluding 0xC4 DHT, 0xC8 JPG and
    0xCC DAC which share the 0xCn range but are not frame headers.
    """
    if data[:2] != b"\xff\xd8":
        return (None, None)
    i = 2
    n = len(data)
    while i + 3 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xFF, 0x01) or 0xD0 <= marker <= 0xD9:
            i += 2
            continue
        seglen = (data[i + 2] << 8) | data[i + 3]
        if seglen < 2:
            return (None, None)
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if i + 9 > n:
                return (None, None)
            h = (data[i + 5] << 8) | data[i + 6]
            w = (data[i + 7] << 8) | data[i + 8]
            return (w, h)
        i += 2 + seglen
    return (None, None)


def png_size(data):
    if len(data) < 24 or data[12:16] != b"IHDR":
        return (None, None)
    w = int.from_bytes(data[16:20], "big")
    h = int.from_bytes(data[20:24], "big")
    return (w, h)


def webp_size(data):
    """VP8 / VP8L / VP8X dimensions, or (None, None)."""
    if len(data) < 30:
        return (None, None)
    chunk = data[12:16]
    try:
        if chunk == b"VP8X":
            w = int.from_bytes(data[24:27], "little") + 1
            h = int.from_bytes(data[27:30], "little") + 1
            return (w, h)
        if chunk == b"VP8 ":
            w = int.from_bytes(data[26:28], "little") & 0x3FFF
            h = int.from_bytes(data[28:30], "little") & 0x3FFF
            return (w, h)
        if chunk == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    except (IndexError, ValueError):
        pass
    return (None, None)


def gif_size(data):
    if len(data) < 10:
        return (None, None)
    return (int.from_bytes(data[6:8], "little"),
            int.from_bytes(data[8:10], "little"))


def image_size(fmt, data):
    return {"jpg": jpeg_size, "png": png_size,
            "webp": webp_size, "gif": gif_size}.get(
                fmt, lambda _d: (None, None))(data)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def fetch_shop(shop_id):
    """Inertia detail JSON for one shop. None when the shop 404s.

    Raises common.FetchError after RETRIES transient failures.
    """
    url = "%s/s/%s" % (BASE, shop_id)
    headers = {"User-Agent": common.USER_AGENT}
    headers.update(INERTIA_HDRS)
    last_err = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            time.sleep(SLEEP)
            return json.loads(raw.decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                time.sleep(SLEEP)
                return None
            last_err = e
        except (urllib.error.URLError, OSError, ValueError) as e:
            last_err = e
        wait = 2 ** attempt
        print("  shop %s attempt %d/%d failed: %s (retry in %ds)"
              % (shop_id, attempt + 1, RETRIES, last_err, wait),
              file=sys.stderr)
        time.sleep(wait)
    raise common.FetchError("giving up on %s after %d attempts: %s"
                            % (url, RETRIES, last_err))


def fetch_bytes(url):
    """GET a signed OSS URL. Returns bytes. No sleep: different host."""
    req = urllib.request.Request(url, headers={"User-Agent": common.USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def thumb_of(payload):
    shop = ((payload or {}).get("props") or {}).get("shop") or {}
    thumb = shop.get("image_thumb")
    if isinstance(thumb, dict) and thumb.get("url"):
        return thumb
    return None


# --------------------------------------------------------------------------
# journal
# --------------------------------------------------------------------------

def load_journals(paths):
    """Merge several journals. Later files win on a duplicate shop id.

    A long crawl can be sharded across processes (one journal each) to keep
    the wall clock sane; the canonical index is then rebuilt from all of them.
    """
    out = {}
    for p in paths:
        out.update(load_journal(p))
    return out


def load_journal(path):
    """{shop_id: record} from the JSONL journal. Tolerates a torn last line."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue  # torn write from a kill; the shop is simply redone
            sid = rec.get("shop_id")
            if sid:
                out[str(sid)] = rec
    return out


def append_journal(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# --------------------------------------------------------------------------
# crawl
# --------------------------------------------------------------------------

def shop_ids_from_arcades(path=ARCADES_PATH):
    """[{shop_id, arcade_id, country}] from data/arcades.json. READ ONLY.

    Prefer --ids-file for long crawls: another agent owns arcades.json and a
    mid-run read of a partial write would kill the job.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out, seen = [], set()
    for row in data.get("arcades") or []:
        link = (row.get("links") or {}).get("bemanicn")
        if not link:
            continue
        m = re.search(r"/s/(\d+)", str(link))
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        out.append({"shop_id": m.group(1), "arcade_id": row.get("id"),
                    "country": row.get("country")})
    out.sort(key=lambda r: int(r["shop_id"]))
    return out


def mirror_one(shop_id, asset_dir):
    """Fetch + mirror one shop's thumb. Returns a journal record.

    The signed URL dies within the hour, so a failed byte fetch re-fetches
    the detail JSON to mint a fresh token rather than reusing the dead one.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = {"shop_id": shop_id, "fetched_at": now,
            "source_url": "%s/s/%s" % (BASE, shop_id)}

    last_err = None
    for attempt in range(IMG_RETRIES):
        payload = fetch_shop(shop_id)
        if payload is None:
            return dict(base, status=GONE)
        thumb = thumb_of(payload)
        if not thumb:
            return dict(base, status=NO_PHOTO,
                        images_count=(payload.get("props") or {}).get(
                            "images_count"))
        try:
            data = fetch_bytes(thumb["url"])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # The shop row still points at an object OSS no longer has.
                # A fresh token will 404 too, so stop rather than retry.
                return dict(base, status=IMAGE_GONE,
                            remote_filename=thumb.get("filename"),
                            error="image 404 on OSS")
            last_err = e
            print("  shop %s image attempt %d/%d failed: %s"
                  % (shop_id, attempt + 1, IMG_RETRIES, e), file=sys.stderr)
            time.sleep(1 + attempt)
            continue
        except (urllib.error.URLError, OSError) as e:
            last_err = e
            print("  shop %s image attempt %d/%d failed: %s"
                  % (shop_id, attempt + 1, IMG_RETRIES, e), file=sys.stderr)
            time.sleep(1 + attempt)
            continue

        fmt = sniff_format(data)
        if not fmt:
            # An HTML error page or a truncated body. Never write it as .jpg.
            last_err = "not an image (%d bytes, starts %r)" % (
                len(data), data[:16])
            print("  shop %s: %s" % (shop_id, last_err), file=sys.stderr)
            time.sleep(1 + attempt)
            continue

        w, h = image_size(fmt, data)
        fname = "%s.%s" % (shop_id, fmt)
        os.makedirs(asset_dir, exist_ok=True)
        tmp = os.path.join(asset_dir, fname + ".part")
        with open(tmp, "wb") as f:
            f.write(data)          # original bytes, never re-encoded
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, os.path.join(asset_dir, fname))

        return dict(base, status=OK,
                    file="assets/venues/cn/" + fname,
                    format=fmt, w=w, h=h, bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    remote_filename=thumb.get("filename"),
                    image_id=thumb.get("id"),
                    images_count=(payload.get("props") or {}).get(
                        "images_count"),
                    credit=CREDIT, license=LICENSE, source=SOURCE)

    return dict(base, status=ERROR, error=str(last_err)[:200])


def build_index(journal, meta_by_shop, out_path):
    """Rebuild data_raw/bemanicn_photos.json from the journal.

    Records a `dup_count` per photo: identical sha256 across shops means a
    chain logo reused across branches, not N distinct venue photos.
    """
    hash_counts = {}
    for rec in journal.values():
        if rec.get("status") == OK and rec.get("sha256"):
            hash_counts[rec["sha256"]] = hash_counts.get(rec["sha256"], 0) + 1

    photos, misses = {}, {}
    for sid, rec in journal.items():
        meta = meta_by_shop.get(sid) or {}
        status = rec.get("status")
        if status == OK:
            w, h = rec.get("w"), rec.get("h")
            # A very tall/wide sliver is a screenshot of a price list or a
            # poster, not a photo of the venue. Flag it so the UI can demote
            # it rather than letterboxing it into a photo slot.
            aspect = None
            if w and h:
                aspect = round(max(w, h) / float(min(w, h)), 2)
            photos[sid] = {
                # `url` is the same relative path as `file`. panel.js's
                # safePhotoUrl() accepts a scheme-less same-origin path, so an
                # image record can be handed to the UI unchanged.
                "url": rec.get("file"),
                "file": rec.get("file"),
                "format": rec.get("format"),
                "w": w,
                "h": h,
                "aspect": aspect,
                "extreme_aspect": bool(aspect and aspect >= 2.5),
                "bytes": rec.get("bytes"),
                "sha256": rec.get("sha256"),
                "dup_count": hash_counts.get(rec.get("sha256"), 1),
                "fetched_at": rec.get("fetched_at"),
                "credit": CREDIT,
                "license": LICENSE,
                "source": SOURCE,
                "source_url": rec.get("source_url"),
                # `page_url` is the canonical name used by photos.py /
                # enrich.py image records; kept identical to source_url so a
                # record can be consumed by either without a translation step.
                "page_url": rec.get("source_url"),
                "tier": "venue",
                "arcade_id": meta.get("arcade_id"),
                "country": meta.get("country"),
            }
        elif status in (NO_PHOTO, GONE, IMAGE_GONE, ERROR):
            misses[sid] = {"status": status, "country": meta.get("country")}

    by_country = {}
    for sid, p in photos.items():
        by_country[p.get("country") or "?"] = by_country.get(
            p.get("country") or "?", 0) + 1

    dup_top = sorted(((c, h) for h, c in hash_counts.items() if c > 1),
                     reverse=True)[:20]

    doc = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": SOURCE,
        "credit": CREDIT,
        "license": LICENSE,
        "license_note": (
            "No public licence or ToS found on map.bemanicn.com. Community-"
            "uploaded venue covers, site meta '(c) BEMANICN'. Mirrored with "
            "attribution + per-shop deep link + takedown path because the "
            "signed OSS URLs expire within the hour and cannot be linked. "
            "See assets/venues/ATTRIBUTION.md."),
        "asset_dir": "assets/venues/cn",
        "note": (
            "Thumbnails only (~150-200px long edge, 7-10KB). The full-size "
            "image and the multi-photo gallery are login-walled. Use w/h to "
            "avoid upscaling these into a hero slot."),
        "counts": {
            "shops_recorded": len(journal),
            "photos": len(photos),
            "no_photo": sum(1 for r in journal.values()
                            if r.get("status") == NO_PHOTO),
            "gone": sum(1 for r in journal.values()
                        if r.get("status") == GONE),
            "image_gone": sum(1 for r in journal.values()
                              if r.get("status") == IMAGE_GONE),
            "error": sum(1 for r in journal.values()
                         if r.get("status") == ERROR),
            "bytes_on_disk": sum(p.get("bytes") or 0
                                 for p in photos.values()),
            "distinct_images": len(hash_counts),
            "reused_images": sum(1 for c in hash_counts.values() if c > 1),
            "extreme_aspect": sum(1 for p in photos.values()
                                  if p.get("extreme_aspect")),
        },
        "by_country": by_country,
        "top_duplicates": [{"sha256": h, "shops": c} for c, h in dup_top],
        "misses": misses,
        "photos": photos,
    }
    common.save_json(out_path, doc)
    return doc


def crawl(shops, asset_dir, journal_path, index_path, limit=None,
          checkpoint=50, retry_errors=True):
    journal = load_journal(journal_path)
    meta_by_shop = {s["shop_id"]: s for s in shops}

    def is_done(sid):
        rec = journal.get(sid)
        if not rec:
            return False
        if rec.get("status") in PERMANENT:
            return True
        # ERROR rows are transient: retried by default, held with --skip-errors
        return not retry_errors

    todo = [s for s in shops if not is_done(s["shop_id"])]
    if limit:
        todo = todo[:limit]

    print("shops known: %d | already recorded: %d | attempting now: %d"
          % (len(shops), len(journal), len(todo)))

    done = 0
    for i, shop in enumerate(todo, 1):
        sid = shop["shop_id"]
        try:
            rec = mirror_one(sid, asset_dir)
        except common.FetchError as e:
            rec = {"shop_id": sid, "status": ERROR, "error": str(e)[:200],
                   "fetched_at": datetime.now(timezone.utc).strftime(
                       "%Y-%m-%dT%H:%M:%SZ"),
                   "source_url": "%s/s/%s" % (BASE, sid)}
        except KeyboardInterrupt:
            print("\ninterrupted; journal keeps %d shops" % len(journal))
            break
        append_journal(journal_path, rec)
        journal[sid] = rec
        done += 1
        if rec.get("status") == OK:
            print("[%d/%d] shop %s -> %s (%dx%s, %d B)"
                  % (i, len(todo), sid, rec.get("file"), rec.get("w") or 0,
                     rec.get("h") or 0, rec.get("bytes") or 0))
        else:
            print("[%d/%d] shop %s -> %s" % (i, len(todo), sid,
                                             rec.get("status")))
        if checkpoint and done % checkpoint == 0:
            build_index(journal, meta_by_shop, index_path)
            print("  -- checkpoint: index rebuilt at %d shops --" % len(journal))

    doc = build_index(journal, meta_by_shop, index_path)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=None,
                    help="attempt at most N not-yet-recorded shops")
    ap.add_argument("--ids-file", default=None,
                    help="JSON list of {shop_id, arcade_id, country}; "
                         "avoids reading data/arcades.json mid-crawl")
    ap.add_argument("--journal", default=JOURNAL_PATH,
                    help="journal this process appends to")
    ap.add_argument("--extra-journal", action="append", default=[],
                    help="additional journal(s) to fold into the index; "
                         "repeatable. Use to merge sharded crawls.")
    ap.add_argument("--index", default=INDEX_PATH)
    ap.add_argument("--asset-dir", default=ASSET_DIR)
    ap.add_argument("--checkpoint", type=int, default=50)
    ap.add_argument("--skip-errors", action="store_true",
                    help="do not re-attempt shops recorded as transient "
                         "errors (default is to retry them)")
    ap.add_argument("--rebuild-index", action="store_true",
                    help="rebuild the index from the journal; no network")
    args = ap.parse_args()

    if args.ids_file:
        with open(args.ids_file, encoding="utf-8") as f:
            shops = json.load(f)
        shops = [{"shop_id": str(s["shop_id"]),
                  "arcade_id": s.get("arcade_id"),
                  "country": s.get("country")} for s in shops]
    else:
        shops = shop_ids_from_arcades()

    if args.rebuild_index:
        journal = load_journals([args.journal] + args.extra_journal)
        doc = build_index(journal, {s["shop_id"]: s for s in shops},
                          args.index)
    else:
        doc = crawl(shops, args.asset_dir, args.journal, args.index,
                    limit=args.limit, checkpoint=args.checkpoint,
                    retry_errors=not args.skip_errors)

    c = doc["counts"]
    print("\nphotos=%d no_photo=%d gone=%d image_gone=%d error=%d | %.1f MB | "
          "distinct=%d reused=%d extreme_aspect=%d"
          % (c["photos"], c["no_photo"], c["gone"], c["image_gone"],
             c["error"], c["bytes_on_disk"] / 1048576.0,
             c["distinct_images"], c["reused_images"], c["extreme_aspect"]))
    print("by country: %s" % json.dumps(doc["by_country"], ensure_ascii=False))
    print("index: %s" % args.index)


if __name__ == "__main__":
    main()
