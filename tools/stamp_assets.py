#!/usr/bin/env python3
"""Stamp a content hash onto every local CSS/JS URL in index.html.

WHY THIS EXISTS

The site is plain static files on GitHub Pages, so every asset lives at a
stable URL: `js/markers.js`, `style.css`. Pages serves those with a
cache lifetime, and it serves `index.html` with a much shorter one. A returning
visitor therefore gets a FRESH index.html and a STALE script, which is worse
than getting a stale page:

  index.html (new)  ->  loads js/tier-icons.js  (new URL, fetched fresh)
                    ->  loads js/markers.js     (SAME URL, served from cache)

The old markers.js knows nothing about AM.tierIcons, so it ignores the artwork
and draws the previous marker style. The visitor sees a half-updated site with
no error in the console, and a hard refresh is the only cure. That is exactly
how the tier-icon release looked "not updated" after it went live.

Appending `?v=<hash of the file>` makes the URL change whenever the bytes
change, so the cache is bypassed precisely when it must be and honoured the
rest of the time. It is the smallest thing that fixes this without a build
step: the files keep their real names on disk, nothing is renamed, and the
query string is invisible to everything except the cache key.

Data files are deliberately NOT stamped. They are rewritten weekly by the
Action, and their URLs are built in JavaScript rather than in the markup;
js/app-init.js, js/panel.js and js/format.js fetch them with
`cache: "no-cache"` instead, which revalidates and takes a cheap 304 when
nothing changed.

USAGE

    python3 tools/stamp_assets.py           # rewrite index.html in place
    python3 tools/stamp_assets.py --check   # exit 1 if any stamp is stale

Run it after changing anything under js/ or style.css, the same way
tools/build_tier_icons.py is run after changing the marker SVGs. --check is
what CI should call so a forgotten stamp fails loudly rather than shipping a
half-cached site.

Stdlib only, same rule as scrapers/.
"""

import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")

# href="..." on <link rel=stylesheet>, src="..." on <script>. Captures any
# existing ?v= so re-running is idempotent rather than stacking query strings.
ASSET_RE = re.compile(
    r'(?P<attr>\b(?:href|src)=")(?P<path>[^"?#]+\.(?:css|js))(?P<query>\?v=[0-9a-f]+)?(?P<tail>")'
)


def short_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def stamp(html, check_only=False):
    """Return (new_html, changes, missing)."""
    changes, missing = [], []

    def repl(m):
        rel = m.group("path")
        # Only local files get stamped; an absolute or protocol-relative URL is
        # someone else's cache to manage.
        if rel.startswith(("http://", "https://", "//")):
            return m.group(0)
        abs_path = os.path.join(ROOT, rel)
        if not os.path.exists(abs_path):
            missing.append(rel)
            return m.group(0)
        want = "?v=" + short_hash(abs_path)
        have = m.group("query") or ""
        if have != want:
            changes.append((rel, have or "(none)", want))
        return m.group("attr") + rel + want + m.group("tail")

    return ASSET_RE.sub(repl, html), changes, missing


def main():
    check_only = "--check" in sys.argv

    with open(INDEX, "r", encoding="utf-8") as fh:
        html = fh.read()

    new_html, changes, missing = stamp(html, check_only)

    if missing:
        sys.stderr.write("stamp_assets: index.html references files that do not exist:\n")
        for rel in missing:
            sys.stderr.write("  - %s\n" % rel)
        return 2

    if check_only:
        if changes:
            sys.stderr.write(
                "stamp_assets: %d asset stamp(s) are stale. Run "
                "`python3 tools/stamp_assets.py` and commit index.html.\n" % len(changes))
            for rel, have, want in changes:
                sys.stderr.write("  %-28s %s -> %s\n" % (rel, have, want))
            return 1
        print("stamp_assets: all asset stamps current")
        return 0

    if not changes:
        print("stamp_assets: no change, all stamps current")
        return 0

    with open(INDEX, "w", encoding="utf-8") as fh:
        fh.write(new_html)

    print("stamp_assets: updated %d asset URL(s) in index.html" % len(changes))
    for rel, have, want in changes:
        print("  %-28s %s -> %s" % (rel, have, want))
    return 0


if __name__ == "__main__":
    sys.exit(main())
