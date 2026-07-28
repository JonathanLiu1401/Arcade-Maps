# Tiered marker icons - integration spec

Six hand-authored SVGs replace the size-graduated circles. Size alone was the
old encoding and it was rejected: bubble area is genuinely hard to compare on a
dense map. Each tier is now a **different silhouette**, so the tier is readable
from shape alone, with a mild size ramp left in as a *reinforcing* signal only.
Do not strip the size ramp back out, and do not re-flatten the shapes.

All six are `viewBox="0 0 32 32"`, including T5. See "Why T5 is not 40x40".

| File | Tier | Total cabinets | Silhouette |
| --- | --- | --- | --- |
| `tier1.svg` | T1 | 1-2 | single eighth note |
| `tier2.svg` | T2 | 3-9 | rounded button pad + note glyph |
| `tier3.svg` | T3 | 10-19 | five-point star |
| `tier4.svg` | T4 | 20-49 | chibi girl, cat-ear headphones, on a colour disc |
| `tier5.svg` | T5 | 50+ ("mega arcade") | chibi idol, gold crown + sparkles, on a colour disc |
| `tierU.svg` | TU | unknown | button pad + "?" chip |

The old ceiling was `25+`. Japanese megastores routinely run 50+ cabinets, so
the top of the range was compressing genuinely different venues into one class.
T4 (20-49) and T5 (50+) split that.

## Tier boundaries

Inclusive on both ends, and every integer >= 1 is covered.

| Tier | Lower | Upper | Legend copy |
| --- | --- | --- | --- |
| T1 | 1 | 2 | `1-2 cabs` |
| T2 | 3 | 9 | `3-9` |
| T3 | 10 | 19 | `10-19` |
| T4 | 20 | 49 | `20-49` |
| T5 | 50 | - | `50+ mega arcade` |
| TU | - | - | `count unknown` |

These replace `SIZE_CLASSES` and `UNKNOWN_CLASS` in `js/markers.js`. Reuse the
existing `F.totalCabs(a.game_counts)`, which already returns `null` when the
data has no counts - that `null` is the TU branch, and it must be tested
*before* any numeric comparison.

**Also update `clusterHasBig()`.** It currently keys on the `"xl"` / `"xxl"`
class ids to decide the cluster bubble's size bump and warmer border. Those ids
disappear with `SIZE_CLASSES`, so map that test onto T4 / T5 or the cluster
path silently stops flagging big venues.

```js
function tierOf(a) {
  var n = F.totalCabs(a && a.game_counts);
  if (n === null || n === undefined) return "U";   // must come first
  if (n >= 50) return "5";
  if (n >= 20) return "4";
  if (n >= 10) return "3";
  if (n >= 3)  return "2";
  return "1";
}
```

### Unknown is NOT the smallest

Most stores land in TU: the official ALL.Net and e-amusement listings publish
*which* games a store has, not *how many* cabinets. Drawing those at T1 would
assert "this arcade has one cab", which the data never said.

TU therefore carries **T2/T3 visual weight** - it renders at 25px against T2's
24px and T3's 26px, and it reuses T2's button-pad silhouette with a "?" in
place of the note. It reads as "a normal arcade, count not published", never as
"a tiny arcade". The existing note in Settings > About already explains this to
users; keep that copy.

## Render size per tier

`px` is the rendered width and height of the (square) icon.

| Zoom band | T1 | T2 | T3 | TU | T4 | T5 |
| --- | --- | --- | --- | --- | --- | --- |
| **Compact** z <= 10 | 16 | 19 | 21 | 20 | 26 | 30 |
| **Standard** z 11-14 | 20 | 24 | 26 | 25 | 30 | 36 |
| **Close** z >= 15 | 22 | 27 | 29 | 28 | 34 | 40 |

**Ship the Standard column alone as v1.** A single fixed size per tier is the
safe implementation. The existing marker code is deliberately zoom-independent
so that a pan or wheel gesture costs the same either way, and with divIcons a
band change means rebuilding thousands of DOM nodes at once. Treat the three
band columns as an enhancement to add only after profiling, and recompute on
band change only - never per animation frame.

### The 26px detail threshold

Verified on the proof sheet, not assumed:

- **>= 26px** - T4's cat ears and headphone cups, and T5's crown points, are
  all individually resolvable. Full character read.
- **20-25px** - the faces still read as *faces* (eyes and mouth survive), and
  T4-vs-T5 stays separable because the silhouette cue is the headgear mass, not
  the facial detail: T4 breaks the circle with two separate ear points, T5 with
  one wide gold crown.
- **< 20px** - the faces become texture. They are still distinguishable from
  T1/T2/T3 as "a busy round thing", and the tier ordering survives, but do not
  expect a viewer to identify the character.

Because T4/T5 only appear at 26px+ in every band except Compact, and Compact
puts them at 26/30, **no simplified fallback artwork is required**. The single
file per tier serves every band. If a future band goes below 20px for T4/T5,
revisit this rather than just scaling down.

## Colour: how `currentColor` tinting works

The map colours markers by game. Every icon has exactly one tinted region
filled `fill="currentColor"`, which resolves to the inherited CSS `color` of
whatever element the SVG is inlined into.

**The shipped SVGs deliberately carry no `color=` or `style="color:..."` on their
root `<svg>` element.** A value there would be a *presentation attribute on the
element itself*, which beats an inherited value, and every marker on the map
would silently render in that one colour. If you add one for a test, remove it.

### Required integration: inline the SVG

The shipped files carry `width="32" height="32"`. **Do not string-replace those
attributes** - size the icon with CSS instead, so the files stay editable
without breaking the caller:

```css
.am-marker      { display: block; }
.am-marker > svg{ width: 100%; height: 100%; display: block; }
```

```js
L.divIcon({
  html: '<span class="am-marker" style="color:' + gameColor +
        ';width:' + px + 'px;height:' + px + 'px">'
      + tierSvgSource + '</span>',       // raw <svg> text, inlined
  className: "",
  iconSize:   [px, px],
  iconAnchor: [px / 2, px / 2],
  popupAnchor:[0, -px / 2]
});
```

CSS `width` beats the `width=` presentation attribute, so the SVG scales to the
wrapper. Verified in Chrome: with the files untouched, all six tiers measured
exactly their target px (20/24/26/25/30/36) while `width` was still `"32"`, and
`getComputedStyle(...).fill` returned a different colour per wrapper. Without
the CSS rule the artwork would paint at 32px while Leaflet positioned it as
`px`, leaving every anchor off by `(32 - px) / 2`.

`<img src="tier4.svg">` and `background-image: url(tier4.svg)` **cannot work**.
An externally-referenced SVG is a separate document and inherits nothing from
the host page, so `currentColor` would fall back to black.

A CSS `mask-image` + `background-color` would tint an external file, but it
discards all colour information and would flatten the faces into solid
silhouettes, destroying the eyes, crown and headphones. Rejected for that
reason; inline the markup instead.

### What is tinted and what is fixed

| Tier | Tinted (currentColor) | Fixed |
| --- | --- | --- |
| T1 | the note | white gloss |
| T2, TU | the button pad | dark note / "?" glyph, white gloss |
| T3 | the star | white gloss |
| T4, T5 | **the disc behind the head** | the entire character |

T4 and T5 invert the obvious approach on purpose. A multicolour chibi face
cannot itself be tinted - recolouring skin and hair per game would produce
green-skinned characters and destroy the art. So the character is a **fixed
palette** (cream skin, plum hair, dark ink, teal headphones, gold crown) and
the game colour is the **disc behind it**.

That disc is deliberately fat. An earlier revision let the hair mass cover most
of the ring and measured only **2.5% tinted pixels at 20px** - the game colour,
which is the map's primary encoding, had effectively vanished. The shipped
geometry (head r=7.4-7.6 inside a disc r=13.0) measures **22-30% of opaque
pixels reading as the tint**, averaged over all four game colours. If anyone
enlarges the head or the hair, re-measure; below roughly 20% the game colour
stops being legible at a glance.

Fixed palette: skin `#FFE8D2`, hair `#9B5DE5`, ink `#2A1B3D`, headphones
`#3FD9D0`, crown `#FFD93B`, blush `#FF7BB8`.

Accent colours were picked to survive all four game tints:

- **Hair is candy violet `#9B5DE5`.** Violet is the one bold hue absent from
  the four game tints, so it stays separable from every disc colour. An earlier
  darker plum (`#5B3A78`) read as muddy on the orange disc and as a flat dark
  cap on the pink one - it lost the bold-coloured-hair look entirely.
- **Headphones are teal `#3FD9D0`, not dark ink.** Dark ink sat invisibly on
  the dark bangs and the whole headset collapsed into an undifferentiated
  cap. Teal separates from violet hair, cream skin, pink blush and all four
  tints.
- **Interior glyphs on T2/TU are dark, not white.** White on `#F7A400` orange
  is about 2:1 contrast and disappears. Dark ink holds over every tint.
- Gold `#FFD93B` on orange is only 1.48:1, so the crown always carries its own
  `#2A1B3D` outline (11.5:1 against the gold) rather than relying on tint
  contrast. Same for the teal headphones.

Every shape carries a dark `#2A1B3D` contour for legibility on light OSM tiles.
That contour is **a light-tile device**: against a dark basemap it is roughly
1.1:1 and does nothing. The brief only required light tiles, so this is not a
defect, but a dark basemap would need a light halo instead - untested.

## Anchor

**Centre**, not bottom-tip. These are symbols, not pins - there is no point on
the artwork that claims to be the ground position, so the centre is the honest
anchor, and it keeps the icon visually stable as the size changes across zoom
bands.

`iconAnchor: [px/2, px/2]`, `popupAnchor: [0, -px/2]`.

## Legend

`js/settings.js` builds two legends and both need updating. Neither reads the
SVGs today; both call a local `sampleDot(d)` helper that draws a circle.

- **Settings > About** - `buildAboutPane`, the `.sd-sizes` block. Replace the
  `SIZE_CLASSES.forEach` loop and its hardcoded `sampleDot(14)` unknown row
  with the six tiers. Swap `S / M / L / XL / XXL` for the legend copy in the
  boundaries table. The heading `"Dot size: total cabinets at the store"`
  should become something like `"Icon: total cabinets at the store"`.
- **On-map legend chip** - `buildLegendChip`, the `.legend-sizes` block. It
  currently shows three ticks indexed into `SIZE_CLASSES` (`[[0,"1"],[2,"5-9"],
  [4,"20+"]]`) plus a `?`. Those indices break with the new table. Suggested
  ticks: T1 `1-2`, T3 `10-19`, T5 `50+`, plus TU `?`.

Render legend swatches with the same inline-SVG technique, at a fixed 24px, so
the legend and the map cannot drift apart.

## Why T5 is not 40x40

T5 was authored in the same 32x32 box as every other tier, on purpose. In a
40-box, T5 at 36px is 0.90 px per viewBox unit, while T4 at 30px in a 32-box is
0.94 - the "bigger" tier would render with *smaller* features, and matching T4
would have needed 37.5px just to break even. One box everywhere means the px
numbers in the table above are directly comparable. T5's sparkle rays live
inside its 32-box, tucked into the corners the disc does not occupy.

## Verified / not verified

Verified by rendering and inspecting `proof.png` (and pixel-sampling the
output):

- Six distinct silhouettes at 20px in a single colour, with no colour crutch.
- Tint works across `#E4007F`, `#F7A400`, `#1E88E5`, `#43A047` on light and
  dark backgrounds.
- Tinted-pixel fraction per tier (the check that caught the 2.5% failure).
- Mouth and eye pixels are true ink rather than antialiased grey.
- `currentColor` inheritance through an inlined `<svg>` in Chrome - screenshot
  confirmed all four tints on the real integration path, not just in the
  rasteriser.
- The CSS sizing rule above, measured in Chrome: every tier's rendered box
  equals its target px while the file's `width` attribute is still `"32"`.
- T5's sparkle extents sit inside the 32-unit viewBox with stroke allowed for,
  so nothing clips against the UA `overflow:hidden` on an inline `<svg>`.

Not verified:

- Rendering inside actual Leaflet / markercluster, on a real basemap, at real
  marker density. The dense-map panel in `proof.png` is a simulation.
- Performance of inline SVG divIcons versus the current canvas `circleMarker`
  path. This is a real change in rendering strategy - divIcons are DOM nodes,
  and the existing code chose canvas deliberately for pan/zoom cost. **Profile
  this at full dataset size before shipping**; if it regresses, the fallback is
  to pre-rasterize the six tiers per game colour into sprite PNGs and use
  `L.icon`, which keeps the artwork but loses runtime tinting.
- Retina / devicePixelRatio 2+ output (SVG should scale cleanly, untested).
- No colour-blindness simulation was run on the four game tints.
