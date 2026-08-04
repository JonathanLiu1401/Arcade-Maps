/* Arcade Maps - the marker layer: cluster group, tier icons, and the single
   visibility predicate every filter feeds into.

   Markers are TIERED, not graduated circles. Each store draws one of six
   hand-authored silhouettes chosen by the cabinet count its sources actually
   PUBLISHED (see assets/markers/marker-spec.md and showableCabs below - a
   count nobody stated does not grade a store), tinted with its game colour. Size
   alone was the old encoding and it was rejected: bubble area is genuinely
   hard to compare on a dense map, so the tier is carried by SHAPE first, with
   a mild size ramp left in only as a reinforcing signal.

   Rendering: the artwork is embedded as source strings by js/tier-icons.js
   (generated from assets/markers/*.svg by tools/build_tier_icons.py). Tinting
   is a string replace of currentColor with the game's hex, and the result
   becomes an image/svg+xml data URL handed to L.icon. Each (tier, colour) URL
   is built at most once and shared by every marker that needs it, so the
   browser decodes each of the at most 6 x 19 variants a single time.

   That is why these are L.marker and no longer canvas circleMarkers, and why
   AM.map.renderer is no longer used here: the canvas renderer can only draw
   geometry, and the whole point of the tier set is artwork. Icons are still
   recomputed only on a state change, never per animation frame - a pan or a
   wheel gesture moves existing DOM nodes and does no icon work at all. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts, U = AM.util;
  var F = AM.format;
  var map = AM.map.map;
  var ART = (AM.tierIcons && AM.tierIcons.SRC) || {};

  /* ---------- tiers ---------- */

  /* Range grading, not a continuous curve: the counts are incomplete,
     integer-skewed and small, so a handful of clearly separated steps reads
     better than a smooth ramp nobody can decode.

     px is the rendered width and height of the (square) icon, and these are
     the "Standard" column of the size table in marker-spec.md. The three
     zoom-banded columns in that document are deliberately NOT implemented: a
     band change would mean rebuilding thousands of DOM nodes mid-gesture, and
     the whole marker layer is built around costing the same whatever the map
     is doing. Treat banding as an enhancement to profile, not a todo.

     UNKNOWN IS NOT SMALLEST. Most stores have no counts at all (the official
     ALL.Net and e-amusement listings publish which games a store has, not how
     many cabinets). Drawing them at T1 would assert "this arcade has one cab",
     which the data never said, so TU carries T2/T3 visual weight and reuses
     T2's button-pad silhouette with a "?" in place of the note. */

  var TIER_CLASSES = [
    { id: "1", min: 1,  max: 2,        px: 20, short: "1-2",   label: "1 to 2 cabinets" },
    { id: "2", min: 3,  max: 9,        px: 24, short: "3-9",   label: "3 to 9 cabinets" },
    { id: "3", min: 10, max: 19,       px: 26, short: "10-19", label: "10 to 19 cabinets" },
    { id: "4", min: 20, max: 49,       px: 30, short: "20-49", label: "20 to 49 cabinets", big: true },
    { id: "5", min: 50, max: Infinity, px: 36, short: "50+",   label: "50 or more cabinets (mega arcade)", big: true }
  ];
  var UNKNOWN_TIER = {
    id: "U", min: null, max: null, px: 25, short: "?", label: "Count unknown"
  };

  /* Scaling off: every tier draws at TU's size. The silhouette still carries
     the tier - the toggle turns off the size RAMP, not the encoding. */
  var UNIFORM_PX = UNKNOWN_TIER.px;

  var TIER_BY_ID = { U: UNKNOWN_TIER };
  TIER_CLASSES.forEach(function (t) { TIER_BY_ID[t.id] = t; });

  /* Legend order: the five counted tiers, then unknown. */
  var TIER_LEGEND = TIER_CLASSES.concat([UNKNOWN_TIER]);

  /* Which sources are allowed to put a NUMBER on the map.

     BemaniCN publishes true per-game quantities. ZIv quantities survive into
     the data only where the merge found a repeated machine title, because a
     ZIv page is a list of what is there rather than a census: every game shows
     as "1", and two versions of one game show as "2" (see scrapers/).
     Everything else - the official store lists above all - has no counts at
     all and must land in TU.

     Reading counts_src rather than merely "is game_counts present" keeps that
     policy in ONE place: if a future source starts emitting counts we do not
     trust, it draws as unknown until it is added here on purpose.

     This is a per-SOURCE gate and it is not sufficient on its own. ZIv is
     trusted here, yet most individual ZIv rows are a lone "1" that states
     presence rather than quantity - so the per-GAME gate (U.countIsShowable,
     applied in showableCabs below) still has to run inside a trusted source. */
  var TRUSTED_COUNTS = { bemanicn: true, ziv: true };

  /* Cabs this store's sources actually PUBLISHED, or null when they published
     none. Sums every game the store reports a showable count for, not just the
     ones currently selected: the icon is a property of the arcade, so it must
     not change when a chip is toggled.

     TWO gates, and they answer different questions. TRUSTED_COUNTS asks "is
     this SOURCE allowed to put a number on the map at all"; U.showableCabs
     asks, per game, "did anybody actually state THIS quantity" - a lone ZIv
     machine row is evidence the game is present and no evidence of how many,
     so it contributes nothing here.

     This used to be F.totalCabs(a.game_counts), the RAW sum, and that made the
     marker contradict the panel on 516 stores: KINGPIN MELBOURNE (id 177) drew
     as "3 to 9 cabinets" off a raw sum of 6 while its panel printed one single
     number, because four of its five counts are suppressed lone ZIv rows. The
     panel has honoured countIsShowable since the counts-honesty rule landed;
     the marker did not, so the map asserted a mid-size venue the data never
     described. F.totalCabs still exists and is still the raw sum - it is the
     right answer to a different question, and nothing here wants it. */
  function showableCabs(a) {
    if (!a || !TRUSTED_COUNTS[a.counts_src]) return null;
    return U.showableCabs(a);
  }

  function tierFor(a) {
    var n = showableCabs(a);
    /* The null test comes FIRST and on purpose: null >= 1 is false in JS but
       null < 3 is true, so any numeric comparison reached with a null would
       quietly file every uncounted store into T1. It is also what routes a
       store whose every count is suppressed to TU rather than T1: showableCabs
       returns null (not 0) in that case precisely so this line catches it, and
       "we do not know how big this is" keeps its own symbol. */
    if (n === null || n === undefined || !isFinite(n) || n < 1) return UNKNOWN_TIER;
    for (var i = 0; i < TIER_CLASSES.length; i++) {
      if (n >= TIER_CLASSES[i].min && n <= TIER_CLASSES[i].max) return TIER_CLASSES[i];
    }
    return UNKNOWN_TIER;
  }

  /* Default on. undefined means no settings module has written the key yet, so
     fall back to whatever a past session persisted; only an explicit false
     turns the ramp off. Same shape as nearby.js's locationAllowed. */
  function scalingOn() {
    var v = AM.state.get("markerScaling");
    if (v === undefined || v === null) v = AM.state.readSetting("markerScaling", true);
    return v !== false;
  }

  function pxFor(tier, on) {
    return on ? tier.px : UNIFORM_PX;
  }

  /* ---------- icon cache ---------- */

  /* Two caches, both keyed by strings and both write-once.

     urlCache: tier + colour -> data URL. This is the expensive one (a string
     replace plus encodeURIComponent over ~600-1900 bytes of markup) and it is
     what lets the browser decode each variant once instead of once per marker.

     iconCache: tier + colour + px -> L.Icon. Leaflet is happy to share one
     Icon instance across any number of markers; it builds a fresh <img> per
     marker from the shared options. */

  var urlCache = {}, iconCache = {};

  function tintedUrl(tierId, color) {
    var key = tierId + "|" + color;
    var hit = urlCache[key];
    if (hit) return hit;
    var svg = ART[tierId] || ART.U || "";
    /* split/join, not replace with a regex: a colour is a literal, and a
       string replace would only swap the first occurrence. */
    svg = svg.split("currentColor").join(color);
    /* encodeURIComponent in full rather than the usual "escape only # and
       quotes" shortcut. The short form depends on the markup never containing
       an apostrophe, which is a trap for whoever edits the artwork next. */
    urlCache[key] = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    return urlCache[key];
  }

  /* Anchor is the CENTRE, not a bottom tip: these are symbols, not pins, so no
     point on the artwork claims to be the ground position, and a centre anchor
     keeps the icon visually stable when its size changes. */
  /* `closed` only adds a CSS class, so a permanently-closed venue reads as
     dimmed on the map instead of looking like somewhere you can go tonight.
     The pin is kept rather than removed: a reader searching for a place they
     remember deserves to be told it closed. */
  function iconFor(tierId, color, px, closed) {
    var key = tierId + "|" + color + "|" + px + (closed ? "|x" : "");
    var hit = iconCache[key];
    if (hit) return hit;
    iconCache[key] = L.icon({
      iconUrl: tintedUrl(tierId, color),
      className: "am-tier am-tier-" + tierId + (closed ? " am-closed" : ""),
      iconSize: [px, px],
      iconAnchor: [px / 2, px / 2],
      popupAnchor: [0, -px / 2],
      tooltipAnchor: [0, -px / 2]
    });
    return iconCache[key];
  }

  function colorFor(g) {
    return C.GAME_COLOR[g] || C.GAME_COLOR.other;
  }

  /* The icon a marker should be wearing right now, as a comparable key. Stored
     on the marker so a filter pass can skip setIcon for the (very common) case
     where the colour did not actually change. */
  function iconKey(tierId, color, px, closed) {
    return tierId + "|" + color + "|" + px + (closed ? "|x" : "");
  }

  /* `closed` must be threaded through here too, not just through the initial
     build: without it the first rescale hands back an un-dimmed icon and a
     closed venue quietly starts looking open again on zoom. */
  function setMarkerIcon(m, tierId, color, px, closed) {
    var key = iconKey(tierId, color, px, closed);
    if (m._amIconKey === key) return;
    m._amIconKey = key;
    m.setIcon(iconFor(tierId, color, px, closed));
  }

  /* ---------- cluster group ---------- */

  /* disableClusteringAtZoom is deliberately NOT set. It used to drop clustering
     entirely from z15.5 up, which meant two stores in the same building drew
     exactly on top of each other with no way to reach the one underneath - and
     stacked stores are common (a mall with two operators, an arcade listed by
     two sources under slightly different names). Clustering now runs at every
     zoom with a radius that collapses to 14px up close, so only genuinely
     overlapping pins bundle, and spiderfyOnMaxZoom fans that bundle out at the
     deepest zoom instead of hiding it.

     maxClusterRadius is called per integer zoom while the tree is built, so the
     fractional wheel zoom never re-enters it. */
  var cluster = L.markerClusterGroup({
    chunkedLoading: true,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
    spiderLegPolylineOptions: { weight: 1.5, color: "#8b93a1", opacity: 0.65 },
    maxClusterRadius: function (zoom) {
      return zoom >= 16 ? 14 : zoom >= 13 ? 32 : zoom >= 10 ? 46 : 60;
    },
    /* The badge stays the STORE COUNT: "how many places" is the mental model
       people bring to a cluster, and summing cabs there would quietly conflate
       one 40-cab megastore with twenty small ones. The only thing the cab data
       changes here is a small size bump plus a warmer border when the bubble is
       hiding at least one T4/T5 store, so a big venue is still findable from a
       zoomed-out view instead of vanishing into a generic bubble. */
    iconCreateFunction: function (c) {
      var n = c.getChildCount();
      var size = n < 10 ? 30 : n < 100 ? 36 : 44;
      var big = clusterHasBig(c);
      if (big) size += 6;
      return L.divIcon({
        html: '<div class="cl-ico' + (big ? " cl-big" : "") +
          '" style="width:' + size + "px;height:" + size + 'px">' + n + "</div>",
        className: "", iconSize: [size, size]
      });
    }
  });
  map.addLayer(cluster);

  var markerOf = {};   /* id -> L.marker */

  /* Does this bubble hide at least one T4/T5 store? Answered by walking the
     cluster's own subtree once and caching the answer on the cluster object,
     keyed on its child count so a bubble that gains children re-answers. The
     tree is rebuilt from scratch on every filter change (clearLayers drops
     _topClusterLevel), so no stale flag can outlive its cluster.

     Unlike the old size-class version this does NOT consult the Display
     toggle: "a big venue is hiding in here" is a fact about the data, and the
     toggle only governs the size ramp. Being toggle-independent also means the
     cached answer stays valid across a toggle. */
  function clusterHasBig(c) {
    var n = c.getChildCount();
    if (c._amBigFor === n) return c._amBig;
    var big = false, i;
    if (c._markers && c._childClusters) {
      for (i = 0; i < c._markers.length && !big; i++) {
        big = isBigMarker(c._markers[i]);
      }
      for (i = 0; i < c._childClusters.length && !big; i++) {
        big = clusterHasBig(c._childClusters[i]);
      }
    } else {
      var kids = c.getAllChildMarkers();
      for (i = 0; i < kids.length && !big; i++) big = isBigMarker(kids[i]);
    }
    c._amBigFor = n;
    c._amBig = big;
    return big;
  }

  function isBigMarker(m) {
    return !!(m && m._amTier && TIER_BY_ID[m._amTier] && TIER_BY_ID[m._amTier].big);
  }

  /* ---------- size ramp ---------- */

  /* Called once at build and once per markerScaling change - never per frame.
     Only the icon size changes, so the cluster tree is untouched and there is
     no reason to pay for a full clearLayers + addLayers rebuild. */
  var lastScaling = null;
  function applyScale(force) {
    var on = scalingOn();
    if (!force && on === lastScaling) return;
    lastScaling = on;
    var list = AM.data.plottable;
    for (var i = 0; i < list.length; i++) {
      var m = markerOf[list[i].id];
      if (!m) continue;
      var tierId = m._amTier;
      setMarkerIcon(m, tierId, m._amColor,
        pxFor(TIER_BY_ID[tierId] || UNKNOWN_TIER, on), m._amClosed);
    }
    /* Cluster bubbles do not carry the ramp, but a spiderfied set is laid out
       from icon sizes, so unspiderfy anything currently fanned out. */
    if (typeof cluster.unspiderfy === "function") cluster.unspiderfy();
  }

  /* Rendered size of an arcade's icon right now, for callers that need to
     clear it: the hover tooltip and the search halo both sit on top of the
     marker and would otherwise be sized for a circle that no longer exists. */
  function iconPxFor(a) {
    var m = a && markerOf[a.id];
    var tier = m ? (TIER_BY_ID[m._amTier] || UNKNOWN_TIER) : tierFor(a);
    return pxFor(tier, scalingOn());
  }

  /* ---------- visibility predicate (single source of truth) ---------- */

  /* Does arcade a count as a hit for game g under the current cab filters?

     The cab test reads AM.util.variantsOf, which unions the e-amusement
     cabs[] flags with the cabinet models named in the ZIv machine list, so a
     Lightning Model in Hong Kong is findable. Reading a.cabs directly (as this
     did) restricted every cab filter to Japan, because the e-amusement
     facility search only covers Japan.

     variantsOf is memoised per arcade id. That matters here specifically: this
     predicate runs over all 13,502 rows on every filter toggle and again from
     search.js and nearby.js, so the parse happens once per store for the life
     of the page and this stays a plain object lookup. */
  function matchesForGame(a, g, selCabs) {
    if (a.games.indexOf(g) === -1) return false;
    if (!selCabs || !selCabs.size) return true;
    var have = null;
    for (var i = 0; i < C.CAB_FILTERS.length; i++) {
      var cf = C.CAB_FILTERS[i];
      if (cf.game !== g || !selCabs.has(cf.id)) continue;
      if (have === null) have = U.variantsOf(a);
      var ok = false;
      for (var j = 0; j < cf.slugs.length; j++) {
        if (Object.prototype.hasOwnProperty.call(have, cf.slugs[j])) { ok = true; break; }
      }
      if (!ok) return false;
    }
    return true;
  }

  /* First selected+matching game in the arcade's own games order, or null.
     Doubles as the marker's colour source. */
  function displayGame(a, selGames, selCabs) {
    selGames = selGames || AM.state.get("selectedGames");
    selCabs = selCabs || AM.state.get("selectedCabs");
    if (!selGames) return null;
    for (var i = 0; i < a.games.length; i++) {
      var g = a.games[i];
      if (selGames.has(g) && matchesForGame(a, g, selCabs)) return g;
    }
    return null;
  }

  /* An arcade is on the map when its sources intersect the enabled set AND its
     games intersect the selection AND the cab rule holds for that game. */
  function sourceEnabled(a, enabled) {
    var src = a.src;
    /* An entry with no source recorded is never hidden by a source toggle. */
    if (!src || !src.length) return true;
    for (var i = 0; i < src.length; i++) {
      if (enabled.has(src[i])) return true;
    }
    return false;
  }

  function isVisible(a, selGames, selCabs, enabledSources, selSizes) {
    selGames = selGames || AM.state.get("selectedGames");
    selCabs = selCabs || AM.state.get("selectedCabs");
    enabledSources = enabledSources || AM.state.get("enabledSources");
    selSizes = selSizes || AM.state.get("selectedSizeTiers");
    if (!selGames) return false;
    if (!sourceEnabled(a, enabledSources)) return false;
    /* Size band is a property of the arcade (showable cabinet count), not of
       the selected game. When the set is still null (pre-init) treat every
       tier as allowed so early callers never blank the map. */
    if (selSizes && !selSizes.has(tierFor(a).id)) return false;
    return displayGame(a, selGames, selCabs) !== null;
  }

  /* ---------- popup ---------- */

  function popupHtml(a) {
    var esc = U.esc;
    var h = '<div class="pp-name">' + esc(a.name) + "</div>";
    h += '<div class="pp-addr">' + esc(a.addr || "") +
      (a.pref ? " &middot; " + esc(a.pref) : "") + " &middot; " + esc(a.country) + "</div>";
    /* Cabinet variants ride next to the game they qualify, and a game whose
       only known cabinet is the pre-DX one is not labelled "maimai DX" - the
       popup carries the same honesty rule as the panel, from the same source. */
    var have = U.variantsOf(a);
    h += '<div class="pp-row">';
    a.games.forEach(function (g) {
      var label = U.gameLabelFor(a, g);
      /* Same rule the panel applies: once the chip has been RENAMED to the
         variant, the offline pill only repeats it, so "maimai (FiNALE /
         pre-DX)" would be followed by a "FiNALE / pre-DX" badge saying the
         same thing twice. The badge qualifies a game name; it is dropped
         when it IS the game name. */
      var renamed = label !== (C.GAME_LABEL[g] || g);
      h += '<span class="gc" style="--c:' + (C.GAME_COLOR[g] || C.GAME_COLOR.other) + '">' +
        esc(label) + "</span>";
      (C.VARIANTS_BY_GAME[g] || []).forEach(function (v) {
        if (v.chipOnly || !v.badge) return;
        if (renamed && v.offline) return;
        if (!Object.prototype.hasOwnProperty.call(have, v.id)) return;
        h += '<span class="badge cab' + (v.offline ? " dead" : "") + '">' +
          esc(v.badge) + "</span>";
      });
    });
    h += "</div>";
    if (a.src && a.src.length) {
      h += '<div class="pp-row">';
      a.src.forEach(function (s) {
        var label = esc(C.SRC_LABEL[s] || s);
        if ((s === "ziv" || s === "bemanicn") && a.links && a.links[s]) {
          h += '<a class="badge" target="_blank" rel="noopener" href="' +
            esc(U.safeUrl(a.links[s])) + '">' + label + "</a>";
        } else {
          h += '<span class="badge">' + label + "</span>";
        }
      });
      h += "</div>";
    }
    if (a.notes) h += '<div class="pp-addr">' + esc(a.notes) + "</div>";
    var gm = (a.links && a.links.gmaps) ? a.links.gmaps : U.gmapsSearchUrl(a);
    h += '<a class="pp-gmaps" target="_blank" rel="noopener" href="' + esc(U.safeUrl(gm)) +
      '">Open in Google Maps</a>';
    return h;
  }

  /* ---------- build + apply ---------- */

  function build() {
    var on = scalingOn();
    lastScaling = on;
    AM.data.plottable.forEach(function (a) {
      var tier = tierFor(a);
      var color = colorFor(displayGame(a));
      var px = pxFor(tier, on);
      var m = L.marker([a.lat, a.lng], {
        icon: iconFor(tier.id, color, px, a.closed),
        /* Markers are not tab stops. The old canvas circles never were, and
           making several hundred visible icons focusable would put a long tab
           run between the search box and the rest of the page. The keyboard
           route to a store is the omnibox and the nearby list, both of which
           select the same state. Same reasoning for the empty alt: the icons
           are decorative repeats of data the panel and those lists already
           expose as text. */
        keyboard: false,
        alt: "",
        riseOnHover: false
      });
      m._amTier = tier.id;
      m._amColor = color;
      m._amClosed = !!a.closed;
      m._amIconKey = iconKey(tier.id, color, px, a.closed);
      m.bindPopup(function () { return popupHtml(a); }, { maxWidth: 320 });
      markerOf[a.id] = m;
    });
  }

  function applyFilters() {
    var selGames = AM.state.get("selectedGames");
    if (!selGames) return;
    var selCabs = AM.state.get("selectedCabs");
    var enabled = AM.state.get("enabledSources");
    var selSizes = AM.state.get("selectedSizeTiers");
    var on = scalingOn();
    var plottable = AM.data.plottable;
    var vis = [];
    for (var i = 0; i < plottable.length; i++) {
      var a = plottable[i];
      if (!sourceEnabled(a, enabled)) continue;
      var g = displayGame(a, selGames, selCabs);
      if (!g) continue;
      var m = markerOf[a.id];
      if (!m) continue;
      if (selSizes && !selSizes.has(m._amTier)) continue;
      var color = colorFor(g);
      m._amColor = color;
      setMarkerIcon(m, m._amTier, color,
        pxFor(TIER_BY_ID[m._amTier] || UNKNOWN_TIER, on), m._amClosed);
      vis.push(m);
    }
    cluster.clearLayers();
    if (vis.length) cluster.addLayers(vis);
    AM.state.set("shownCount", vis.length);
  }

  /* Rebuilding the layer means clearLayers + addLayers over several thousand
     markers, so a burst of state changes in one tick (a hashchange that sets
     games and cabs together, a settings panel writing several keys) must
     collapse into a single rebuild rather than one per key. */
  var applyQueued = false;
  function scheduleApply() {
    if (applyQueued) return;
    applyQueued = true;
    Promise.resolve().then(function () {
      applyQueued = false;
      applyFilters();
    });
  }

  /* ---------- search-result highlight halo ---------- */
  /* A pulsing accent ring dropped on the picked store. One at a time: a new
     pick removes the old halo immediately. Lives HALO_HOLD ms, then fades. */

  var HALO_HOLD = 8000, HALO_FADE = 500;
  var haloMarker = null, haloTimers = [], haloStore = null;

  function clearHaloTimers() {
    haloTimers.forEach(clearTimeout);
    haloTimers = [];
  }

  function removeHalo() {
    clearHaloTimers();
    haloStore = null;
    if (haloMarker) { map.removeLayer(haloMarker); haloMarker = null; }
  }

  function showHalo(ll, a) {
    removeHalo();
    haloStore = a;
    /* Sized off the store's own icon plus a margin, so the ring sits OUTSIDE
       the artwork on every tier: a fixed 32px ring cut straight through a
       36px T5 crown. */
    var d = Math.round(iconPxFor(a)) + 14;
    /* .halo-core is the steady ring that always reads in a screenshot;
       .halo-pulse is the echo that expands out of it once per 1.2s. */
    var icon = L.divIcon({
      className: "halo-wrap",
      html: '<div class="halo-pulse"></div><div class="halo-core"></div>',
      iconSize: [d, d],
      iconAnchor: [d / 2, d / 2]
    });
    haloMarker = L.marker(ll, {
      icon: icon, pane: "haloPane", interactive: false, keyboard: false
    }).addTo(map);
    haloTimers.push(setTimeout(function () {
      var el = haloMarker && haloMarker.getElement();
      if (!el) { removeHalo(); return; }
      el.classList.add("halo-out");
      haloTimers.push(setTimeout(removeHalo, HALO_FADE));
    }, HALO_HOLD));
  }

  /* If the dot is still swallowed by a cluster bubble at the arrival zoom,
     ask the cluster group to reveal it. The halo itself is already pinned to
     the store's latlng and tracks the map, so nothing to redraw afterwards.
     zoomToShowLayer dereferences marker.__parent._zoom, so guard on __parent
     (not hasLayer, which can be true with no __parent).

     With clustering now active at every zoom this path matters more than it
     used to: a store sharing a building with another one stays inside a bubble
     even at z16, and zoomToShowLayer spiderfies it into view. */
  function revealHiddenMarker(a) {
    /* A newer pick (or an expiry) may have landed during the flight. */
    if (haloStore !== a) return;
    var marker = markerOf[a.id];
    if (marker && marker._map !== map && marker.__parent &&
        typeof cluster.zoomToShowLayer === "function") {
      cluster.zoomToShowLayer(marker);
    }
  }

  /* Fly to an arcade, open its popup and halo it. Used by search and by any
     module that sets selectedArcade with meta.focus. */
  function focusArcade(a) {
    if (!a || !U.hasCoords(a)) return false;
    var ll = [a.lat, a.lng];
    if (C.REDUCED) AM.map.setViewExact(ll, 16);
    else map.flyTo(ll, 16, { duration: 0.9 });
    L.popup({ maxWidth: 320 }).setLatLng(ll).setContent(popupHtml(a)).openOn(map);
    /* Halo synchronously: the halo is a latlng-anchored layer, so it rides
       the flyTo. Waiting on moveend would race the popup's own autoPan. */
    showHalo(ll, a);
    /* setView with animations off has already fired moveend by now, so a
       once() handler would never fire on arrival and would instead stay
       armed for the user's next map move. Call it directly instead. */
    if (C.REDUCED) revealHiddenMarker(a);
    else map.once("moveend", function () { revealHiddenMarker(a); });
    return true;
  }

  /* ---------- wiring ---------- */
  /* No legend is built here on purpose. settings.js already owns the on-map
     legend chip and the Settings > About legend, and a second control in the
     same corner would just be clutter. TIER_LEGEND and tierIconUrl are
     exported below so that module can render the real artwork and the real
     thresholds rather than a hard-coded copy of either. */

  function start() {
    AM.state.on("selectedGames", scheduleApply);
    AM.state.on("selectedCabs", scheduleApply);
    AM.state.on("enabledSources", scheduleApply);
    AM.state.on("selectedSizeTiers", scheduleApply);
    AM.state.on("markerScaling", function () { applyScale(); });
    AM.state.on("selectedArcade", function (id, meta) {
      if (!meta || !meta.focus) return;
      var a = AM.data.byId[id];
      if (a && U.hasCoords(a)) focusArcade(a);
      else removeHalo();
    });
    applyFilters();
  }

  AM.markers = {
    cluster: cluster,
    markerOf: markerOf,
    build: build,
    start: start,
    applyFilters: applyFilters,
    scheduleApply: scheduleApply,
    isVisible: isVisible,
    displayGame: displayGame,
    matchesForGame: matchesForGame,
    sourceEnabled: sourceEnabled,
    popupHtml: popupHtml,
    focusArcade: focusArcade,
    showHalo: showHalo,
    removeHalo: removeHalo,
    revealHiddenMarker: revealHiddenMarker,
    markerFor: function (id) { return markerOf[id] || null; },
    /* tier icons */
    TIER_CLASSES: TIER_CLASSES,
    UNKNOWN_TIER: UNKNOWN_TIER,
    TIER_LEGEND: TIER_LEGEND,
    UNIFORM_PX: UNIFORM_PX,
    /* Renamed from totalCabs when the tier stopped counting suppressed rows.
       The old name promised a raw total and now returns a showable one, and a
       caller reading `totalCabs` would get a number that is not the total. No
       module outside this file ever called it (checked across js/ and tools/);
       AM.format.totalCabs remains available for a genuine raw sum. */
    showableCabs: showableCabs,
    tierFor: tierFor,
    tierIconUrl: tintedUrl,
    iconPxFor: iconPxFor,
    scalingOn: scalingOn,
    applyScale: applyScale,
    clusterHasBig: clusterHasBig
  };
})(window.AM);
