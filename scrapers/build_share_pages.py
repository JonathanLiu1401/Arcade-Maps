"""Build static per-arcade share pages with Open Graph tags for Discord/etc.

WHY

Discord, Slack, iMessage and every other link unfurl crawler fetch the URL
and read <meta property="og:*"> tags from the FIRST HTML response. They do
not run JavaScript and they strip the #fragment before the request.

So a link like:
  https://.../Arcade-Maps/#16.69/10.67/122.94/arcade=z195
is fetched as:
  https://.../Arcade-Maps/
and always unfurls the generic site card.

These pages live at s/<sid>.html with venue-specific og:title / description
/ image. Humans get a one-click open into the map (JS redirect). Crawlers
never run JS and only see the meta tags.

Keyed on sid (z195, b2744, ...), never on the row-number id - ids reshuffle
every merge.

Run after merge writes data/arcades.json + data/enrichment.json:

  python scrapers/build_share_pages.py
  python -m scrapers.run_all --skip-scrape   # also calls this
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Canonical public origin. og:image MUST be absolute HTTPS for Discord.
SITE_BASE = "https://jonathanliu1401.github.io/Arcade-Maps"

# Free OSM static map (no API key). City/prefecture zoom, not street-level.
# If the service is down, the HTML map <img> hides itself via onerror.
# See: https://staticmap.openstreetmap.de/
STATIC_MAP_BASE = "https://staticmap.openstreetmap.de/staticmap.php"
STATIC_MAP_ZOOM = 11  # ~city/prefecture (10-12); deep-link zoom stays 16
STATIC_MAP_SIZE = "600x400"

# Keep in sync with js/state.js GAMES labels (display only).
GAME_LABELS = {
    "maimai_dx": "maimai DX",
    "chunithm": "CHUNITHM",
    "ongeki": "O.N.G.E.K.I.",
    "project_diva": "Project DIVA",
    "sdvx": "SOUND VOLTEX",
    "iidx": "beatmania IIDX",
    "ddr": "DDR",
    "polaris_chord": "Polaris Chord",
    "gitadora": "GITADORA",
    "jubeat": "jubeat",
    "popn": "pop'n music",
    "nostalgia": "NOSTALGIA",
    "drs": "DANCERUSH",
    "dance_around": "DANCE aROUND",
    "dance_evo": "Dance Evolution",
    "museca": "MUSECA",
    "reflec": "REFLEC BEAT",
    "taiko": "Taiko no Tatsujin",
    "pump_it_up": "Pump It Up",
    "stepmaniax": "StepManiaX",
    "wacca": "WACCA",
    "groove_coaster": "GROOVE COASTER",
    "crossbeats": "crossbeats",
    "beatstream": "BeatStream",
    "other": "Other",
}

# sid must be a safe single path segment (z195, b2744, h...).
_SID_OK = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def _abs_url(path_or_url):
    """Make an absolute HTTPS URL suitable for og:image."""
    if not path_or_url:
        return None
    u = str(path_or_url).strip()
    if u.startswith("https://") or u.startswith("http://"):
        return u
    if u.startswith("//"):
        return "https:" + u
    u = u.lstrip("/")
    return SITE_BASE + "/" + u


def _game_labels(games):
    labels = []
    for g in games or []:
        if g == "other":
            continue
        labels.append(GAME_LABELS.get(g, g))
    return labels


def _pick_image(arcade, enrich, cab_manifest):
    """Best image for the card, highest quality first.

    1. Venue photo from enrichment (url or mirrored file)
    2. Stock cabinet photo for the first known game
    3. Site brand mark (always available on our domain)
    """
    if enrich:
        for im in enrich.get("images") or []:
            if not isinstance(im, dict):
                continue
            if im.get("url"):
                return _abs_url(im["url"]), "venue"
            if im.get("file"):
                return _abs_url(im["file"]), "venue"
        if enrich.get("image"):
            return _abs_url(enrich["image"]), "venue"

    for g in arcade.get("games") or []:
        m = cab_manifest.get(g) or {}
        f = m.get("file")
        if f:
            return _abs_url("assets/cabs/" + f), "cabinet"

    return _abs_url("assets/apple-touch-icon.png"), "brand"


def _map_hash(arcade):
    lat, lng = arcade.get("lat"), arcade.get("lng")
    sid = arcade.get("sid") or ""
    if lat is None or lng is None:
        return "arcade=" + sid
    # Zoom 16 matches a typical "open this venue" deep link.
    return "16/%.5f/%.5f/arcade=%s" % (float(lat), float(lng), sid)


def _coords(arcade):
    """Return (lat, lng) floats or None if missing/invalid."""
    lat, lng = arcade.get("lat"), arcade.get("lng")
    if lat is None or lng is None:
        return None
    try:
        lat_f, lng_f = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
        return None
    return lat_f, lng_f


def _static_map_url(lat, lng, zoom=STATIC_MAP_ZOOM, size=STATIC_MAP_SIZE):
    """OSM staticmap URL with a red pin. No API key.

    Format per staticmap.openstreetmap.de:
      center=LAT,LNG&zoom=N&size=WxH&maptype=mapnik&markers=LAT,LNG,red-pushpin
    """
    lat_s = "%.5f" % float(lat)
    lng_s = "%.5f" % float(lng)
    # Commas and marker style are part of the API; quote the query values.
    center = quote("%s,%s" % (lat_s, lng_s), safe=",")
    markers = quote("%s,%s,red-pushpin" % (lat_s, lng_s), safe=",")
    return (
        "%s?center=%s&zoom=%d&size=%s&maptype=mapnik&markers=%s"
        % (STATIC_MAP_BASE, center, int(zoom), quote(str(size), safe="x"), markers)
    )


def _map_caption(arcade):
    """Country / pref caption for the map column."""
    country = (arcade.get("country") or "").strip()
    pref = (arcade.get("pref") or "").strip()
    parts = []
    if country:
        parts.append(country)
    if pref and pref not in country:
        parts.append(pref)
    return " / ".join(parts) if parts else "Location"


def _description(arcade, labels):
    parts = []
    country = (arcade.get("country") or "").strip()
    pref = (arcade.get("pref") or "").strip()
    addr = (arcade.get("addr") or "").strip()
    if country:
        parts.append(country)
    if pref and pref not in country:
        parts.append(pref)
    if addr:
        # Keep Discord description under ~200 chars of useful text.
        short = addr if len(addr) <= 100 else addr[:97] + "..."
        parts.append(short)
    where = " - ".join(parts) if parts else "Rhythm game arcade"
    if labels:
        games = ", ".join(labels[:8])
        if len(labels) > 8:
            games += " +" + str(len(labels) - 8) + " more"
        return "%s. Games: %s." % (where, games)
    return where + "."


def render_page(arcade, enrich, cab_manifest):
    sid = arcade.get("sid") or ""
    name = (arcade.get("name") or "Arcade").strip() or "Arcade"
    labels = _game_labels(arcade.get("games"))
    desc = _description(arcade, labels)
    image, image_kind = _pick_image(arcade, enrich, cab_manifest)
    page_url = SITE_BASE + "/s/" + sid + ".html"
    map_hash = _map_hash(arcade)
    map_url = SITE_BASE + "/#" + map_hash
    # Relative open for local file:// / preview servers
    map_rel = "../#" + map_hash

    closed = bool(arcade.get("closed"))
    if closed:
        desc = "Permanently closed. " + desc

    games_li = "".join("<li>%s</li>" % _esc(g) for g in labels) or (
        "<li>No listed music games</li>")

    addr = (arcade.get("addr") or "").strip()
    country = (arcade.get("country") or "").strip()
    img_note = {
        "venue": "Photo of this venue",
        "cabinet": "Representative cabinet photo (not this venue)",
        "brand": "Arcade Maps",
    }.get(image_kind, "")

    coords = _coords(arcade)
    static_map = _static_map_url(*coords) if coords else None
    map_cap = _map_caption(arcade) if coords else ""

    # Primary og:image stays the venue/cab photo (Discord shows one image).
    # Second og:image points at the static map when coords exist; some clients
    # pick it up, and the HTML dual card always shows both for humans.
    og_image_extra = ""
    if static_map:
        og_image_extra = (
            '\n<meta property="og:image" content="%s">'
            '\n<meta property="og:image:alt" content="%s">'
        ) % (_esc(static_map), _esc("Map pin - " + map_cap))

    if static_map:
        # Two-column media strip: left photo, right map pin at city zoom.
        # Built separately then inserted as a dict value (values may contain %
        # from URLs; only the outer template string is scanned for %).
        media_html = """
  <div class="media">
    <div class="media-col">
      <img class="hero" src="%(image)s" alt="%(img_alt)s" width="600" height="400"
           loading="eager">
      <p class="media-cap">%(photo_cap)s</p>
    </div>
    <div class="media-col media-map">
      <img class="hero map" src="%(static_map)s" alt="%(map_alt)s" width="600" height="400"
           loading="eager"
           onerror="this.closest('.media-map').style.display='none';var m=this.closest('.media');if(m)m.classList.add('no-map');">
      <p class="media-cap">%(map_cap)s</p>
    </div>
  </div>""" % {
            "image": _esc(image),
            "img_alt": _esc(name if image_kind == "venue" else name + " - " + img_note),
            "photo_cap": _esc(img_note or "Photo"),
            "static_map": _esc(static_map),
            "map_alt": _esc("Map pin - " + map_cap),
            "map_cap": _esc(map_cap),
        }
        card_class = "card card-wide"
    else:
        media_html = (
            '  <img class="hero" src="%s" alt="%s" width="1200" height="630">'
            % (_esc(image),
               _esc(name if image_kind == "venue" else name + " - " + img_note))
        )
        card_class = "card"

    # No meta-refresh: crawlers that follow redirects would unfurl the
    # destination (the generic index) instead of this page. JS redirect
    # only runs in real browsers after a short delay so humans can see the
    # dual card; Discordbot/Twitterbot/etc. never execute it. ?go=1 opens
    # immediately for people who want to skip the preview.
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s - Arcade Maps</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(page_url)s">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Arcade Maps">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(page_url)s">
<meta property="og:image" content="%(image)s">
<meta property="og:image:alt" content="%(img_alt)s">%(og_image_extra)s
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="%(title)s">
<meta name="twitter:description" content="%(desc)s">
<meta name="twitter:image" content="%(image)s">
<meta name="theme-color" content="#E4007F">
<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">
<style>
  :root { color-scheme: dark; }
  body { margin: 0; font: 16px/1.45 system-ui, sans-serif; background: #0f1115;
         color: #e8eaed; min-height: 100vh; display: flex; align-items: center;
         justify-content: center; padding: 24px; }
  .card { max-width: 420px; width: 100%%; background: #1a1d24; border-radius: 14px;
          overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,.45);
          border: 1px solid #2a2f3a; }
  .card-wide { max-width: 720px; }
  .media { display: grid; grid-template-columns: 1fr 1fr; gap: 0;
           background: #111; }
  .media.no-map { grid-template-columns: 1fr; }
  .media-col { min-width: 0; position: relative; }
  .media-map { border-left: 1px solid #2a2f3a; }
  .hero { width: 100%%; aspect-ratio: 1.5 / 1; object-fit: cover; display: block;
          background: #111; }
  .card:not(.card-wide) .hero { aspect-ratio: 1.91 / 1; }
  .media-cap { margin: 0; padding: 6px 10px; font-size: .72rem; color: #9aa0a6;
               background: #14171e; border-top: 1px solid #2a2f3a;
               white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .body { padding: 16px 18px 20px; }
  h1 { font-size: 1.25rem; margin: 0 0 6px; line-height: 1.25; }
  .sub { color: #9aa0a6; font-size: .9rem; margin: 0 0 12px; }
  .closed { color: #f28b82; font-weight: 600; margin: 0 0 8px; font-size: .85rem; }
  ul { margin: 0 0 16px; padding-left: 1.1em; color: #c4c7ce; }
  .btn { display: inline-block; background: #E4007F; color: #fff; text-decoration: none;
         font-weight: 600; padding: 10px 16px; border-radius: 8px; }
  .btn:hover { filter: brightness(1.08); }
  .foot { margin-top: 14px; font-size: .75rem; color: #6b7280; }
  .foot a { color: #9aa0a6; }
  @media (max-width: 560px) {
    .media { grid-template-columns: 1fr; }
    .media-map { border-left: 0; border-top: 1px solid #2a2f3a; }
    .card-wide { max-width: 420px; }
  }
</style>
</head>
<body>
<article class="%(card_class)s">
%(media_html)s
  <div class="body">
    %(closed_html)s
    <h1>%(title)s</h1>
    <p class="sub">%(where)s</p>
    <ul>%(games_li)s</ul>
    <a class="btn" id="open" href="%(map_rel)s">Open on Arcade Maps</a>
    <p class="foot">%(img_note)s - <a href="%(map_url)s">direct map link</a></p>
  </div>
</article>
<script>
/* Real browsers land on the map after a short delay so the dual card is
   visible. Crawlers never run this. ?go=1 skips the delay. */
(function () {
  try {
    var ua = navigator.userAgent || "";
    if (/Discordbot|Twitterbot|facebookexternalhit|Slackbot|LinkedInBot|WhatsApp|Applebot|bingbot|Googlebot/i.test(ua)) return;
    var dest = %(map_rel_js)s;
    var q = (location.search || "").replace(/^\\?/, "");
    var params = {};
    q.split("&").forEach(function (p) {
      var i = p.indexOf("=");
      if (i >= 0) params[decodeURIComponent(p.slice(0, i))] = decodeURIComponent(p.slice(i + 1));
      else if (p) params[decodeURIComponent(p)] = "";
    });
    var delay = (params.go === "1" || params.go === "true") ? 0 : 2000;
    if (delay === 0) { location.replace(dest); return; }
    setTimeout(function () { location.replace(dest); }, delay);
  } catch (e) {}
})();
</script>
</body>
</html>
""" % {
        "title": _esc(name),
        "desc": _esc(desc),
        "page_url": _esc(page_url),
        "image": _esc(image),
        "img_alt": _esc(name if image_kind == "venue" else name + " - " + img_note),
        "og_image_extra": og_image_extra,
        "card_class": card_class,
        "media_html": media_html,
        "closed_html": ('<p class="closed">Permanently closed</p>' if closed else ""),
        "where": _esc(" - ".join(x for x in [country, addr] if x) or "Rhythm game arcade"),
        "games_li": games_li,
        "map_rel": _esc(map_rel),
        "map_url": _esc(map_url),
        "img_note": _esc(img_note),
        "map_rel_js": json.dumps(map_rel),
    }


def build(data_dir=None, out_dir=None, clean=True, only_sids=None):
    """Write share pages.

    only_sids: optional set/list of sids to regenerate (e.g. for quick proofs).
    When set, clean is forced off and the directory index is left untouched.
    """
    data_dir = data_dir or os.path.join(ROOT, "data")
    out_dir = out_dir or os.path.join(ROOT, "s")
    only = set(only_sids) if only_sids else None
    if only:
        clean = False

    with open(os.path.join(data_dir, "arcades.json"), encoding="utf-8") as fh:
        doc = json.load(fh)
    arcades = doc.get("arcades") or []
    enrich_path = os.path.join(data_dir, "enrichment.json")
    enrich_by_id = {}
    if os.path.exists(enrich_path):
        with open(enrich_path, encoding="utf-8") as fh:
            enrich_by_id = (json.load(fh).get("arcades") or {})

    cab_manifest = {}
    man_path = os.path.join(ROOT, "assets", "cabs", "manifest.json")
    if os.path.exists(man_path):
        with open(man_path, encoding="utf-8") as fh:
            cab_manifest = json.load(fh)

    os.makedirs(out_dir, exist_ok=True)

    # Drop stale share pages from removed sids so dead links 404 cleanly
    # rather than showing last week's wrong venue under the same file name.
    # (sid is stable; a gone sid should disappear.)
    if clean:
        keep = set()
        for a in arcades:
            sid = a.get("sid")
            if sid and _SID_OK.match(sid):
                keep.add(sid + ".html")
        for name in os.listdir(out_dir):
            if name.endswith(".html") and name not in keep and name != "index.html":
                try:
                    os.remove(os.path.join(out_dir, name))
                except OSError:
                    pass

    n = 0
    n_venue_img = 0
    n_map = 0
    for a in arcades:
        sid = a.get("sid")
        if not sid or not _SID_OK.match(sid):
            continue
        if only is not None and sid not in only:
            continue
        en = enrich_by_id.get(str(a.get("id"))) or enrich_by_id.get(a.get("id"))
        page = render_page(a, en, cab_manifest)
        path = os.path.join(out_dir, sid + ".html")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(page)
        n += 1
        if en and (en.get("image") or en.get("images")):
            n_venue_img += 1
        if _coords(a):
            n_map += 1

    if only is None:
        # Directory index so /s/ is not a naked listing failure on some hosts.
        index = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><title>Arcade Maps - share links</title>
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0;url=../">
</head><body>
<p><a href="../">Arcade Maps</a> - per-venue share pages live at
<code>s/&lt;sid&gt;.html</code> (for example
<a href="z195.html">s/z195.html</a>).</p>
</body></html>
"""
        with open(os.path.join(out_dir, "index.html"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(index)

    print("build_share_pages: wrote %d pages under %s (%d with venue photos, %d with map)"
          % (n, out_dir, n_venue_img, n_map), file=sys.stderr)
    return n


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--out", default=os.path.join(ROOT, "s"))
    ap.add_argument("--no-clean", action="store_true",
                    help="do not delete share pages for sids that no longer exist")
    ap.add_argument("--only", nargs="+", metavar="SID",
                    help="regenerate only these sids (implies --no-clean)")
    args = ap.parse_args()
    build(args.data, args.out, clean=not args.no_clean, only_sids=args.only)


if __name__ == "__main__":
    main()
