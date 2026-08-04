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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Canonical public origin. og:image MUST be absolute HTTPS for Discord.
SITE_BASE = "https://jonathanliu1401.github.io/Arcade-Maps"

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

    # No meta-refresh: crawlers that follow redirects would unfurl the
    # destination (the generic index) instead of this page. JS redirect
    # only runs in real browsers; Discordbot never executes it.
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
<meta property="og:image:alt" content="%(img_alt)s">
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
  .hero { width: 100%%; aspect-ratio: 1.91 / 1; object-fit: cover; display: block;
          background: #111; }
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
</style>
</head>
<body>
<article class="card">
  <img class="hero" src="%(image)s" alt="%(img_alt)s" width="1200" height="630">
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
/* Real browsers land on the map. Crawlers never run this. */
(function () {
  try {
    var ua = navigator.userAgent || "";
    if (/Discordbot|Twitterbot|facebookexternalhit|Slackbot|LinkedInBot|WhatsApp/i.test(ua)) return;
    location.replace(%(map_rel_js)s);
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
        "closed_html": ('<p class="closed">Permanently closed</p>' if closed else ""),
        "where": _esc(" - ".join(x for x in [country, addr] if x) or "Rhythm game arcade"),
        "games_li": games_li,
        "map_rel": _esc(map_rel),
        "map_url": _esc(map_url),
        "img_note": _esc(img_note),
        "map_rel_js": json.dumps(map_rel),
    }


def build(data_dir=None, out_dir=None, clean=True):
    data_dir = data_dir or os.path.join(ROOT, "data")
    out_dir = out_dir or os.path.join(ROOT, "s")

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
    for a in arcades:
        sid = a.get("sid")
        if not sid or not _SID_OK.match(sid):
            continue
        en = enrich_by_id.get(str(a.get("id"))) or enrich_by_id.get(a.get("id"))
        page = render_page(a, en, cab_manifest)
        path = os.path.join(out_dir, sid + ".html")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(page)
        n += 1
        if en and (en.get("image") or en.get("images")):
            n_venue_img += 1

    # Directory index so /s/ is not a naked listing failure on some hosts.
    index = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><title>Arcade Maps - share links</title>
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0;url=../">
</head><body>
<p><a href="../">Arcade Maps</a> – per-venue share pages live at
<code>s/&lt;sid&gt;.html</code> (for example
<a href="z195.html">s/z195.html</a>).</p>
</body></html>
"""
    with open(os.path.join(out_dir, "index.html"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(index)

    print("build_share_pages: wrote %d pages under %s (%d with venue photos)"
          % (n, out_dir, n_venue_img), file=sys.stderr)
    return n


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--out", default=os.path.join(ROOT, "s"))
    ap.add_argument("--no-clean", action="store_true",
                    help="do not delete share pages for sids that no longer exist")
    args = ap.parse_args()
    build(args.data, args.out, clean=not args.no_clean)


if __name__ == "__main__":
    main()
