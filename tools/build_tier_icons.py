#!/usr/bin/env python3
"""Generate js/tier-icons.js from assets/markers/tier*.svg.

The marker layer needs the SVG source as a JavaScript string, not as a file it
fetches: the artwork is tinted per game by string-replacing currentColor with a
hex colour, and the result is handed to L.icon as a data URL. Doing that from a
fetch would make marker construction asynchronous and would break the
load-bearing script order in index.html (markers.js captures AM.format and
AM.map at parse time), so the six files are embedded instead.

Embedding means the same artwork exists in two places, so it is GENERATED, not
hand-copied. Edit the SVGs under assets/markers/ and re-run:

    python3 tools/build_tier_icons.py

Stdlib only, same rule as scrapers/. Verifies the invariants the marker layer
depends on before writing anything:

  * viewBox is "0 0 32 32" (the render sizes in marker-spec.md assume one box)
  * at least one fill="currentColor" exists (otherwise the tint is a no-op)
  * the root <svg> carries no color= or style="color:..." (a value there is a
    presentation attribute on the element itself, so it would beat the inherited
    tint and lock every marker on the map to one colour)
"""

import os
import re
import sys
import xml.etree.ElementTree as ET

TIERS = ["1", "2", "3", "4", "5", "U"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "assets", "markers")
OUT = os.path.join(ROOT, "js", "tier-icons.js")

HEADER = """/* Arcade Maps - tier marker artwork, embedded as source strings.

   GENERATED FILE - do not edit by hand.
   Source of truth: assets/markers/tier{1,2,3,4,5,U}.svg
   Regenerate with:  python3 tools/build_tier_icons.py

   Why the artwork is embedded rather than fetched: markers.js tints each icon
   by replacing currentColor with the store's game colour and hands the result
   to L.icon as a data URL, and it does that synchronously inside build(). A
   fetch would make marker construction asynchronous and would not survive the
   fixed script order in index.html. Comments and indentation are stripped
   here; the readable originals with their design notes stay in assets/markers/.

   An externally referenced SVG (<img src="tier4.svg">) cannot be used: it is a
   separate document and inherits nothing from the host page, so currentColor
   would resolve to black. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

"""

FOOTER = """
  AM.tierIcons = { SRC: SRC, TIERS: TIERS };
})(window.AM);
"""


def minify(svg):
    """Strip XML comments and collapse inter-tag whitespace.

    Only whitespace between tags and inside tags is touched. None of the six
    files carries text content (the "?" on tierU is a path, deliberately, so it
    does not depend on the viewer's fonts), so there is no text node to damage.
    """
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"<\?xml.*?\?>", "", svg, flags=re.S)
    svg = re.sub(r"\s+", " ", svg)
    svg = re.sub(r">\s+<", "><", svg)
    return svg.strip()


def check(tier, raw, mini):
    """Return a list of problems; empty means the file is usable."""
    problems = []
    try:
        root = ET.fromstring(mini)
    except ET.ParseError as e:
        return ["tier%s.svg is not well-formed XML: %s" % (tier, e)]

    if root.tag != "{http://www.w3.org/2000/svg}svg":
        problems.append("tier%s.svg root element is %s, expected <svg>" % (tier, root.tag))
    if root.get("viewBox") != "0 0 32 32":
        problems.append('tier%s.svg viewBox is %r, expected "0 0 32 32"'
                        % (tier, root.get("viewBox")))
    if "currentColor" not in mini:
        problems.append("tier%s.svg has no fill=\"currentColor\": nothing would take "
                        "the game colour" % tier)
    if root.get("color") is not None:
        problems.append("tier%s.svg root carries color=%r; that beats the inherited "
                        "tint and locks every marker to one colour" % (tier, root.get("color")))
    style = root.get("style") or ""
    if re.search(r"(^|;)\s*color\s*:", style):
        problems.append("tier%s.svg root style sets color; same problem as a color= "
                        "attribute" % tier)
    # The text-content check is cheap insurance: a <text> glyph would render
    # with whatever font the viewer happens to have.
    if root.iter("{http://www.w3.org/2000/svg}text") and \
            list(root.iter("{http://www.w3.org/2000/svg}text")):
        problems.append("tier%s.svg contains a <text> element; convert it to a path "
                        "so it does not depend on the viewer's fonts" % tier)
    return problems


def js_string(s):
    """Double-quoted JS string literal. The SVGs are ASCII, so this is enough."""
    out = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + out + '"'


def main():
    parts, problems, total_raw, total_min = [], [], 0, 0

    for tier in TIERS:
        path = os.path.join(SRC_DIR, "tier%s.svg" % tier)
        if not os.path.exists(path):
            problems.append("missing %s" % path)
            continue
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        mini = minify(raw)
        problems.extend(check(tier, raw, mini))
        total_raw += len(raw)
        total_min += len(mini)
        parts.append((tier, mini))

    if problems:
        sys.stderr.write("tier icon build FAILED:\n")
        for p in problems:
            sys.stderr.write("  - %s\n" % p)
        return 1

    body = ["  var TIERS = [%s];\n\n" % ", ".join('"%s"' % t for t, _ in parts)]
    body.append("  var SRC = {\n")
    for i, (tier, mini) in enumerate(parts):
        comma = "," if i < len(parts) - 1 else ""
        body.append('    "%s": %s%s\n' % (tier, js_string(mini), comma))
    body.append("  };\n")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(HEADER)
        fh.write("".join(body))
        fh.write(FOOTER)

    print("wrote %s" % os.path.relpath(OUT, ROOT))
    print("  %d tiers, %s raw -> %s embedded (%.0f%% smaller)"
          % (len(parts), "{:,}".format(total_raw), "{:,}".format(total_min),
             100.0 * (1 - float(total_min) / total_raw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
