"""Rights-cleared venue imagery + honest link-out inventory for Arcade Maps.

WHAT THIS FILE IS NOT
---------------------
Despite the name (fixed by the task brief), this module does NOT harvest chain
store photos. Two recon passes measured that chain store pages (GiGO, Taito,
Round1, namco, APINA, Timezone, Dave & Buster's, Cineplex, Tom's World) are
technically easy to scrape (95-100% extraction) and legally unusable: every one
of those chains publishes all-rights-reserved terms, Taito and namco explicitly
restrict copying/transmitting, and namco asks that you not deep-link image
files at all. Hotlinking their CDN from a public GitHub Pages map is exactly
the transmit/embed pattern those terms forbid. So this module emits ZERO chain
imagery. Those chains appear only as link_outs, which count as ZERO coverage.

WHAT IT DOES DO
---------------
Three sources, in descending order of how much coverage they buy:

1. ZIv full-country picture sweep  (the big win)
   scrapers/photos.py only queries 10 countries. ZIv actually carries community
   photos for 68. Sweeping every country in data/arcades.json roughly doubles
   real venue-photo coverage and is the ONLY source that moves China at all
   (0 -> 155). Same hotlink+credit policy the project already runs for ZIv:
   no rehost of the picture tree.

2. Wikimedia Commons  (small, but the only mirrorable source)
   Category-walked (not geosearched - geosearch is the 59%-noise trap that
   data_raw/streetlevel_imagery_probe.json warns about), then intersected with
   our pins by coordinate, then EVERY surviving image was downloaded and looked
   at by eye. The allowlist below is the reviewed result: candidates showing a
   neighbouring business, the containing mall, or a bare cabinet closeup were
   dropped, not demoted. CC/PD only, per-file attribution carried.

3. GiGO link-out repair  (licence-free, no imagery)
   206 Japanese rows point at tempo.gendagigo.jp/am/{slug}, which now 301s every
   slug to a generic renewal hub. Resolving to www.gigo.co.jp/shops/{slug} makes
   137 of them real store pages again. No photo is fetched or stored.

TIERING RULE (from the brief, enforced here)
--------------------------------------------
A chain logo is not a photo of that arcade, and neither is a photo of the mall
it sits in or a closeup of one cabinet. Only tier "venue" counts toward
coverage. This module emits no "chain" tier records at all, because it never
found chain imagery it was allowed to ship.

SCHEMA HAZARD - read before changing the output shape
-----------------------------------------------------
scrapers/enrich.py does `entry["image"] = images[0]["url"]` and the panel
renders any string it finds. A record carrying a `url` key is therefore a
DISPLAY path no matter what its `tier` says. So link_outs live under their own
top-level key and carry `page_url` ONLY - never `url`, never `file`. Do not
merge link_outs into images[].

Output: data_raw/chain_photos.json
Usage:
    python scrapers/chain_photos.py --all
    python scrapers/chain_photos.py --ziv-sweep --commons     # skip link-outs
    python scrapers/chain_photos.py --all --limit-countries Japan,China
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

OUTFILE = "chain_photos.json"
MAX_IMAGES = 3

ZIV_API = "https://zenius-i-vanisher.com/api/arcades.php"
ZIV_ARCADE_URL = "https://zenius-i-vanisher.com/v5.2/arcade.php?id=%s"
ZIV_CREDIT = "Community photo via Zenius-I-Vanisher"

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_UA = ("ArcadeMapsBot/0.1 (https://github.com/ ; contact via repo "
              "issues) stdlib-urllib")

GIGO_NEW = "https://www.gigo.co.jp/shops/%s"
GIGO_DEAD_MARK = "/renewal"

# ZIv's unsegmented United States query returns HTTP 500 (payload too large),
# so the US is fetched per rhythm-game series. Mirrors scrapers/ziv.py.
USA_SERIES_IDS = sorted({
    1, 2, 3, 4, 5, 7, 8, 12, 18, 173, 267, 284, 506, 549, 643, 694,
    766, 1281, 1366, 1536, 1556,
})

_ZIV_ID_RE = re.compile(r"arcade\.php\?id=(\d+)", re.I)
_TAG_RE = re.compile(r"<[^>]+>")

# Licences we are willing to mirror/hotlink from Commons. Anything else
# (non-free tags, "used with permission", fair use) is dropped.
OK_LICENCE_PREFIXES = ("CC BY", "CC0", "CC-Zero", "Public domain", "PD")


# --------------------------------------------------------------- COMMONS ---
# Reviewed allowlist. Built by: walking the Commons amusement-arcade category
# tree (92 categories, 1488 files), keeping the 410 files that carry their OWN
# coordinates, intersecting those with our pins at 150 m (168 candidates across
# 81 arcades), then DOWNLOADING ALL 168 AND LOOKING AT THEM.
#
# Rejected on sight, with reasons, so nobody re-derives them:
#   - wrong business at the same spot: "GiGO Akihabara UFO catcher" pinned to
#     Hey; "namco TOKYO" pinned to GiGO Kabukicho; ADORES pinned to Plasa
#     Capcom Kichijoji; pachinko Espace pinned to Shinjuku Sportsland;
#     "smart game" pinned to JUMBO GAME; Don Quijote pinned to Rakuichi;
#     Free Play Arlington pinned to Tokyo Station; Sega Park Bargate pinned to
#     High Score Southampton; New Palace pinned to Riverside Bowl; Monte Carlo
#     pinned to Electric Avenue; Quicksilver pinned to Roxy; Super Amusement
#     Dream Games pinned to Molly Fantasy.
#   - the containing MALL, not the arcade: Grandberry Park central court,
#     Springfield Town Center panorama, Stockland/SEIYU/Seiyu Teine exteriors.
#   - a single CABINET, not the venue: DDR/MUSECA/Synchronica/claw crane /
#     coin pusher / Skee ball closeups. Same rule as "a chain logo is not a
#     photo of that arcade".
#   - "The Deluxe" x10 pinned to Playland: that is the Hippodrome building,
#     a different arcade on the same Hastings seafront.
# Format: arcade_id -> [Commons file titles, storefront/exterior first].
COMMONS_ALLOW = {
    257: ["File:StocklandRockhamptonInternal6.jpg"],
    610: ["File:Rose Bowl - Montreal (26259012566).jpg"],
    4142: ["File:SZ 深圳 Shenzhen 寶安 壹方城"
           "購物中心 Bao'An Uniwalk Mall 星際"
           "傳奇 Meland Club Amusement arcades May 2023 Px3 01.jpg",
           "File:SZ 深圳 Shenzhen 寶安 壹方城"
           "購物中心 Bao'An Uniwalk Mall 星際"
           "傳奇 Meland Club Amusement arcades May 2023 Px3 02.jpg"],
    7467: ["File:Automathal (5974930044).jpg"],
    7627: ["File:中環 Central 租庇利街 Jubilee "
           "Street 創聲遊戲機中心 Chon Shing "
           "Game Centre 霓虹燈招牌 Neon Sign, 2019.jpg"],
    8686: ["File:Ishigakijima seen from bus 11 6.jpg"],
    8763: ["File:Taito Station (2812431296).jpg",
           "File:Virtual horse races - Inside Taito Station.jpg"],
    8779: ["File:Taito Station, denden-town - panoramio.jpg"],
    8781: ["File:Hondori Street in Hiroshima.jpg"],
    8783: ["File:Taito Station in Shinjuku, Tokyo, Japan, 2024 May.jpg"],
    9191: ["File:BukuroMikado-201812.png",
           "File:Ikebukuro Gesen Mikado 2023-02-08.jpg"],
    9218: ["File:BabaMikado-1F-1.png", "File:BabaMikado-1F-2.png",
           "File:BabaMikado-1F-3.png"],
    9500: ["File:NAMCO LaLaport Kadoma.jpg"],
    9583: ["File:20260714 Yurakucho.jpg"],
    10453: ["File:World of Fun at SM City Consolacion (12-22-2022).jpg"],
    11332: ["File:Great Yarmouth - panoramio (27).jpg"],
    11371: ["File:Weymouth - The Electric Palace - geograph.org.uk - "
            "1099493.jpg"],
    11426: ["File:Amusement arcade at Clacton-on-Sea, Essex - geograph.org.uk "
            "- 246333.jpg"],
    11467: ["File:Bournemouth, Happyland Amusements - geograph.org.uk - "
            "1091459.jpg"],
    11471: ["File:Dawlish , Piermont Road Pedestrian Crossing - "
            "geograph.org.uk - 1345889.jpg"],
    11586: ["File:Kino Amusements (55198949385).jpg"],
    11789: ["File:Funland at Southport - geograph.org.uk - 941758.jpg",
            "File:Funland at Southport - geograph.org.uk - 3562161.jpg"],
    11893: ["File:New Brighton indoor funfair-by-Duncan-Grant.jpg"],
    12174: ["File:Chinatown Fair storefront.jpg",
            "File:Chinatown Fair – interior from entranceway "
            "– 2020.jpg"],
    12200: ["File:Cidercade 1 2023-11-16.jpg",
            "File:Cidercade 2 2023-11-16.jpg"],
    12356: ["File:Dave & Buster entrance, Springfield Town Center.jpg"],
    12429: ["File:\"Medicine Show\" Arcade at Port Orleans Riverside Walt "
            "Disney World.jpg"],
    12455: ["File:Portland, Oregon (July 26, 2022) - 035.jpg",
            "File:Portland, Oregon (July 26, 2022) - 041.jpg",
            "File:Portland, Oregon (July 26, 2022) - 046.jpg"],
    12561: ["File:2025-09-10 18 53 00 The entrance of the Game Box Arcade "
            "within the Oxford Valley Mall in Middletown Township, Bucks "
            "County, Pennsylvania.jpg",
            "File:2025-09-10 18 54 44 Interior of the Game Box Arcade within "
            "the Oxford Valley Mall in Middletown Township, Bucks County, "
            "Pennsylvania.jpg",
            "File:2025-09-10 18 54 17 Interior of the Game Box Arcade within "
            "the Oxford Valley Mall in Middletown Township, Bucks County, "
            "Pennsylvania.jpg"],
    12706: ["File:Las Vegas, Nevada - John's Incredible Pizza at 3700 S "
            "Maryland Parkway.jpg"],
    12996: ["File:Quarterworld at Alhambra Theater Portland Oregon - face "
            "view.jpg",
            "File:Quarterworld at Alhambra Theater Portland Oregon - quarter "
            "view.jpg"],
    13306: ["File:Menomonee Falls June 2026 70 (The Garcade).jpg"],
    13354: ["File:Tilted 10 in Willow Grove Park Mall.jpeg"],
    13433: ["File:Yestercades, Somerville, NJ 5 3 15 (17178181217).jpg",
            "File:Yestercades, Somerville, NJ 5 3 15 (17383659032).jpg"],
}


# ------------------------------------------------------------- utilities ---


def force_https(url):
    """http -> https. GitHub Pages blocks mixed content."""
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    return "https://" + u[7:] if u.startswith("http://") else u


def strip_html(text):
    """Commons extmetadata Artist/Credit are HTML fragments."""
    if not text:
        return None
    return common.unescape(_TAG_RE.sub(" ", text)) or None


def fetch_json(url, headers=None, retries=3, timeout=60):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers=headers or {"User-Agent": common.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:           # noqa: BLE001 - retry everything
            last = e
            time.sleep(2 ** i)
    raise common.FetchError("%s: %s" % (url, last))


def head(url, timeout=30):
    """(status, final_url). status None means the request itself failed."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": common.USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, url
    except Exception as e:               # noqa: BLE001
        return None, str(e)


def load_arcades(repo_root):
    path = os.path.join(repo_root, "data", "arcades.json")
    return common.load_json(path)["arcades"]


def ziv_index(arcades):
    """{ziv_arcade_id: arcade_row} from links.ziv. Verified 1:1, 6984 rows."""
    out = {}
    for a in arcades:
        u = (a.get("links") or {}).get("ziv")
        if not u:
            continue
        m = _ZIV_ID_RE.search(u)
        if m:
            out[m.group(1)] = a
    return out


def image_record(url, source, credit, page_url, license=None, tier="venue",
                 **extra):
    """One photo record. Only tier 'venue' ever counts toward coverage."""
    https = force_https(url)
    if not https:
        return None
    rec = {"url": https, "source": source, "credit": credit,
           "license": license, "page_url": page_url, "tier": tier}
    rec.update({k: v for k, v in extra.items() if v is not None})
    return rec


# ------------------------------------------------------------ ZIv sweep ----


def _ziv_query(country, series_id=None):
    u = (ZIV_API + "?action=query&country=" + urllib.parse.quote(country)
         + "&skip_visitors=1&skip_comments=1")
    if series_id is not None:
        u += "&series_id=%d" % series_id
    return u


def _ziv_rows(payload):
    ar = payload.get("arcades") if isinstance(payload, dict) else payload
    if isinstance(ar, dict):
        ar = list(ar.values())
    return ar or []


def ziv_sweep(countries, sleep=0.6, verbose=True):
    """{ziv_id: [raw picture entries]} for every country given.

    photos.py only queries 10 countries; ZIv has pictures in 68. This is the
    single biggest coverage lever in the project.
    """
    pics, stats = {}, {}
    for c in countries:
        got = {}
        try:
            if c == "United States":
                for sid in USA_SERIES_IDS:
                    try:
                        for a in _ziv_rows(fetch_json(
                                _ziv_query("United States", sid))):
                            aid = str(a.get("id") or "")
                            if aid:
                                got[aid] = a.get("pictures") or []
                    except Exception as e:      # noqa: BLE001
                        print("  US series %d failed: %s" % (sid, e),
                              file=sys.stderr)
                    time.sleep(0.4)
            else:
                for a in _ziv_rows(fetch_json(_ziv_query(c))):
                    aid = str(a.get("id") or "")
                    if aid:
                        got[aid] = a.get("pictures") or []
        except Exception as e:                  # noqa: BLE001
            print("FAIL %s: %s" % (c, e), file=sys.stderr)
            stats[c] = {"error": str(e)}
            continue
        n = sum(1 for v in got.values() if v)
        stats[c] = {"arcades": len(got), "with_pics": n}
        for k, v in got.items():
            if v:
                pics[k] = v
        if verbose:
            print("%-24s arcades=%5d with_pics=%5d" % (c, len(got), n),
                  flush=True)
        time.sleep(sleep)
    return pics, stats


def ziv_records(ziv_id, raw, max_images=MAX_IMAGES):
    page = ZIV_ARCADE_URL % ziv_id
    out, seen = [], set()
    for p in raw:
        if isinstance(p, dict):
            url, pid = p.get("absolutePath") or p.get("url"), p.get("id")
        else:
            url, pid = p, None
        rec = image_record(url, "ziv", ZIV_CREDIT, page, license=None,
                           tier="venue", picture_id=pid)
        if rec is None or rec["url"] in seen:
            continue
        seen.add(rec["url"])
        out.append(rec)
        if len(out) >= max_images:
            break
    return out


# -------------------------------------------------------------- Commons ----


def commons_fileinfo(titles):
    """{title: page} with imageinfo + extmetadata, batched 50 at a time."""
    info = {}
    titles = list(titles)
    for i in range(0, len(titles), 50):
        q = urllib.parse.urlencode({
            "action": "query", "format": "json",
            "titles": "|".join(titles[i:i + 50]),
            "prop": "imageinfo", "iiprop": "url|extmetadata",
            "iiurlwidth": "1024",
        })
        d = fetch_json(COMMONS_API + "?" + q,
                       headers={"User-Agent": COMMONS_UA})
        for _pid, p in d.get("query", {}).get("pages", {}).items():
            info[p.get("title")] = p
        time.sleep(0.2)
    return info


def commons_records(allow=None, max_images=MAX_IMAGES):
    """Reviewed Commons allowlist -> {arcade_id: [venue records]}.

    Licence is read per file and anything not CC/PD is dropped, so a file whose
    licence is retagged upstream falls out of the index on the next run rather
    than silently shipping.
    """
    allow = COMMONS_ALLOW if allow is None else allow
    wanted = [t for v in allow.values() for t in v]
    info = commons_fileinfo(wanted)
    out, dropped = {}, []
    for aid, titles in allow.items():
        recs = []
        for t in titles:
            p = info.get(t)
            if not p or "missing" in p:
                dropped.append((t, "missing on Commons"))
                continue
            ii = (p.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata") or {}

            def meta(k, _em=em):
                v = _em.get(k)
                return v.get("value") if isinstance(v, dict) else None

            lic = meta("LicenseShortName")
            if not lic or not str(lic).startswith(OK_LICENCE_PREFIXES):
                dropped.append((t, "licence not mirrorable: %s" % lic))
                continue
            artist = strip_html(meta("Artist")) or "Wikimedia Commons"
            rec = image_record(
                ii.get("thumburl") or ii.get("url"),
                source="wikimedia_commons",
                credit="%s / %s via Wikimedia Commons" % (artist, lic),
                page_url=ii.get("descriptionurl"),
                license=lic, tier="venue",
                license_url=meta("LicenseUrl"),
                artist=artist,
                commons_file=t,
                full_url=force_https(ii.get("url")),
            )
            if rec:
                recs.append(rec)
            if len(recs) >= max_images:
                break
        if recs:
            out[str(aid)] = recs
    return out, dropped


# ------------------------------------------------------------- link-outs ---


def gigo_slug(url):
    m = re.search(r"tempo\.gendagigo\.jp/am/([^/?#]+)", url or "")
    if m:
        return m.group(1)
    m = re.search(r"gigo\.co\.jp/shops/([^/?#]+)", url or "")
    return m.group(1) if m else None


def gigo_linkouts(repo_root, arcades, sleep=0.35, verbose=True):
    """Repair the 206 dead tempo.gendagigo.jp store links.

    NO IMAGE IS FETCHED OR STORED. GiGO store photos are all-rights-reserved;
    this only checks whether the store PAGE exists on the new host so the UI
    can offer an honest "official store page" link instead of a dead one.
    """
    enr = common.load_json(os.path.join(repo_root, "data", "enrichment.json"))
    byid = {str(a["id"]): a for a in arcades}
    rows = []
    for k, v in enr.get("arcades", {}).items():
        a = byid.get(k)
        if not a or a.get("country") != "Japan":
            continue
        w = v.get("website") or ""
        host = urllib.parse.urlparse(w).netloc.lower()
        if "gendagigo" not in host and "gigo.co.jp" not in host:
            continue
        s = gigo_slug(w)
        if s:
            rows.append((a, w, s))
    out = {}
    live = dead = repaired = already = 0
    for i, (a, old, slug) in enumerate(rows):
        new = GIGO_NEW % slug
        st, final = head(new)
        ok = (st == 200 and GIGO_DEAD_MARK not in (final or ""))
        if ok:
            live += 1
            rec = {
                "page_url": new,
                "source": "gigo",
                "label": "Official store page",
                "credit": "GENDA GiGO Entertainment",
                "license": "all-rights-reserved",
                "tier": "link_out",
                "note": ("store photos on this page are ARR and are NOT "
                         "mirrored or hotlinked"),
            }
            # Only the stale tempo.gendagigo.jp rows are actually REPAIRED.
            # Rows already on www.gigo.co.jp were merely confirmed live, and
            # claiming to have fixed them would inflate the win.
            if old and old != new:
                rec["replaces"] = old
                rec["repaired"] = True
                repaired += 1
            else:
                rec["repaired"] = False
                already += 1
            out[str(a["id"])] = [rec]
        else:
            dead += 1
        if verbose and i % 25 == 0:
            print("  gigo %d/%d live=%d dead=%d"
                  % (i, len(rows), live, dead), flush=True)
        time.sleep(sleep)
    if verbose:
        print("gigo link-outs live %d/%d (repaired stale %d, already live %d,"
              " dead %d)" % (live, len(rows), repaired, already, dead))
    return out, {
        "candidates": len(rows),
        "live": live,
        "repaired_from_dead_slug": repaired,
        "already_live": already,
        "dead": dead,
        "why": ("tempo.gendagigo.jp/am/{slug} now 301s every slug to a "
                "generic /renewal hub, so those link-outs were dead; "
                "repaired_from_dead_slug counts the ones this run actually "
                "fixed by resolving to www.gigo.co.jp/shops/{slug}"),
    }


# ---------------------------------------------------------------- driver ---


def coverage_report(index, arcades, key="images"):
    """Per-country venue-tier coverage. Only tier=='venue' is counted."""
    byid = {str(a["id"]): a for a in arcades}
    tot = collections.Counter(a.get("country") or "?" for a in arcades)
    hit = collections.Counter()
    for aid, recs in index.items():
        if not any(r.get("tier") == "venue" for r in recs):
            continue
        a = byid.get(str(aid))
        if a:
            hit[a.get("country") or "?"] += 1
    rows = {}
    for c in sorted(tot):
        if hit[c]:
            rows[c] = {"arcades": tot[c], "with_photo": hit[c],
                       "pct": round(100.0 * hit[c] / tot[c], 1)}
    return rows, sum(hit.values()), len(arcades)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None, help="output path")
    ap.add_argument("--all", action="store_true",
                    help="run every source (ziv sweep + commons + link-outs)")
    ap.add_argument("--ziv-sweep", action="store_true")
    ap.add_argument("--commons", action="store_true")
    ap.add_argument("--linkouts", action="store_true")
    ap.add_argument("--limit-countries", default=None,
                    help="comma-separated country filter for the ZIv sweep")
    args = ap.parse_args(argv)

    if args.all:
        args.ziv_sweep = args.commons = args.linkouts = True
    if not (args.ziv_sweep or args.commons or args.linkouts):
        common.die("pick at least one of --all/--ziv-sweep/--commons/"
                   "--linkouts")

    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    out_path = args.out or os.path.join(repo, "data_raw", OUTFILE)

    arcades = load_arcades(repo)
    z2a = ziv_index(arcades)
    images = collections.defaultdict(list)
    sources = {}

    if args.ziv_sweep:
        countries = sorted({a["country"] for a in arcades if a.get("country")})
        if args.limit_countries:
            keep = {c.strip() for c in args.limit_countries.split(",")}
            countries = [c for c in countries if c in keep]
        print("== ZIv picture sweep over %d countries ==" % len(countries))
        pics, stats = ziv_sweep(countries)
        joined = 0
        for zid, raw in pics.items():
            a = z2a.get(zid)
            if not a:
                continue
            recs = ziv_records(zid, raw)
            if recs:
                images[str(a["id"])].extend(recs)
                joined += 1
        sources["ziv_sweep"] = {
            "countries_queried": len(countries),
            "ziv_ids_with_pictures": len(pics),
            "joined_to_arcades": joined,
            "per_country": stats,
            "licence": ("ZIv publishes no photo licence; project policy is "
                        "hotlink + visible credit + deep link, never rehost"),
            "content_mix": {
                "_warning": ("NOT every ZIv picture is a photo of the venue. "
                             "ZIv is a rhythm-game site and a large share of "
                             "uploads are single-cabinet closeups, which are "
                             "not a picture of the arcade any more than a "
                             "chain logo is. Coverage counts arcades with a "
                             "ZIv photo, not arcades with a verified "
                             "storefront."),
                "method": ("first picture of each sampled arcade downloaded "
                           "and hand-classified by eye"),
                "new_countries": {"n": 48, "storefront": 13, "interior": 10,
                                  "cabinet_closeup": 24, "other": 1,
                                  "shows_venue_pct": 48},
                "already_shipped_countries": {"n": 24, "storefront": 6,
                                              "interior": 5,
                                              "cabinet_closeup": 12,
                                              "other": 1,
                                              "shows_venue_pct": 46},
                "conclusion": ("48% vs 46% - the newly swept countries are "
                               "statistically indistinguishable from the "
                               "corpus already shipping, so this expands "
                               "existing coverage at the same quality rather "
                               "than diluting it"),
            },
        }

    if args.commons:
        print("== Wikimedia Commons (reviewed allowlist) ==")
        crecs, dropped = commons_records()
        # PREPEND, do not append. Commons records are the ones with verified
        # per-file attribution AND confirmed venue identity (every one was
        # downloaded and looked at), whereas roughly half of ZIv leads are
        # single-cabinet closeups. Appending would let ZIv fill the 3-record
        # cap and silently discard reviewed Commons files on the 9 arcades
        # that have both sources.
        for aid, recs in crecs.items():
            images[aid][:0] = recs
        print("commons arcades=%d files=%d dropped=%d"
              % (len(crecs), sum(len(v) for v in crecs.values()),
                 len(dropped)))
        for t, why in dropped:
            print("  dropped %s (%s)" % (t, why))
        sources["wikimedia_commons"] = {
            "arcades": len(crecs),
            "files": sum(len(v) for v in crecs.values()),
            "dropped": [{"file": t, "reason": w} for t, w in dropped],
            "method": ("category tree walk (not geosearch), coordinate "
                       "intersect at 150 m, then every candidate downloaded "
                       "and visually reviewed"),
            "licence": "CC/PD only, per-file attribution carried in credit",
        }

    link_outs = {}
    if args.linkouts:
        print("== GiGO link-out repair (no imagery) ==")
        link_outs, gstats = gigo_linkouts(repo, arcades)
        sources["gigo_link_outs"] = dict(
            gstats,
            licence=("all-rights-reserved; link-out only, counts as ZERO "
                     "photo coverage"))

    # Cap at MAX_IMAGES per arcade. Commons already sits first (see above), so
    # a reviewed Commons file is never the one that gets cut. Count what the
    # cap discards per source so the loss is visible instead of silent.
    final = {}
    capped = collections.Counter()
    for aid, recs in images.items():
        recs = [r for r in recs if r.get("tier") == "venue"]
        if not recs:
            continue
        for r in recs[MAX_IMAGES:]:
            capped[r["source"]] += 1
        final[aid] = recs[:MAX_IMAGES]
    if capped:
        print("records beyond the %d-image cap (not shipped): %s"
              % (MAX_IMAGES, dict(capped)))

    byid = {str(a["id"]): a for a in arcades}
    for aid, recs in final.items():
        a = byid.get(aid)
        if a:
            for r in recs:
                r.setdefault("arcade_name", a["name"])
                r.setdefault("country", a["country"])

    cov, total_hit, n_arcades = coverage_report(final, arcades)
    by_source = collections.Counter(
        r["source"] for recs in final.values() for r in recs)

    payload = {
        "_comment": (
            "Rights-cleared venue imagery for Arcade Maps. Despite the "
            "filename this file contains NO chain store photos: GiGO, Taito, "
            "Round1, namco, APINA, Timezone, Dave & Buster's and the rest "
            "publish all-rights-reserved terms and are link-out only. "
            "images[] holds ONLY tier 'venue' records that count toward "
            "coverage. link_outs[] is a separate key whose records carry "
            "page_url and NO url/file key - they must NEVER be merged into "
            "images[], because enrich.py mirrors images[0].url into "
            "entry['image'] and the panel renders any string it finds. "
            "OVERLAP: this file supersedes data_raw/ziv_photos.json on "
            "US/UK/PH/SG/JP - both are the same ZIv source and a merge "
            "should prefer this file, not union the two. See "
            "sources.ziv_sweep.content_mix before quoting the headline "
            "percentage: about half of ZIv pictures are cabinet closeups "
            "rather than pictures of the venue."),
        "updated": date.today().isoformat(),
        "max_images": MAX_IMAGES,
        "tiers": {
            "venue": "a real photo of THIS arcade; the only tier that counts",
            "link_out": ("official store page for venues whose photos are "
                         "all-rights-reserved; counts as ZERO coverage"),
        },
        "sources": sources,
        "coverage_venue_tier": cov,
        "totals": {
            "arcades": n_arcades,
            "arcades_with_venue_photo": total_hit,
            "pct": round(100.0 * total_hit / n_arcades, 1),
            "records_by_source": dict(by_source),
            "link_out_arcades": len(link_outs),
            "link_out_counts_as_coverage": 0,
        },
        "images": final,
        "link_outs": link_outs,
    }
    common.save_json(out_path, payload)
    print("\nwrote %s" % out_path)
    print("venue-tier: %d/%d arcades = %.1f%%"
          % (total_hit, n_arcades, 100.0 * total_hit / n_arcades))
    print("link-outs (zero coverage): %d arcades" % len(link_outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
