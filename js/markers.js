/* Arcade Maps - the marker layer: cluster group, circle markers, popups and
   the single visibility predicate every filter feeds into.

   Markers are also graduated: circle area carries the store's total cab count
   (see the SIZE_CLASSES block below), hue stays the game colour, and only the
   two biggest classes add a soft glow. Size is recomputed on a state change,
   never per animation frame - Leaflet's canvas renderer redraws from the
   cached options.radius while panning and zooming, so a pan costs exactly the
   same with scaling on or off. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts, U = AM.util;
  var F = AM.format;
  var map = AM.map.map;

  /* disableClusteringAtZoom is compared against Math.round(map.getZoom()) by
     markercluster (_zoomEnd sets this._zoom = Math.round(map._zoom), and
     _generateInitialClusters caps its grids at disableClusteringAtZoom - 1).
     The integer comparison therefore still works with fractional zoom - the
     effective threshold simply lands on the rounding boundary, so markers
     un-cluster from z >= 15.5 rather than exactly 16. */
  var cluster = L.markerClusterGroup({
    chunkedLoading: true,
    disableClusteringAtZoom: 16,
    spiderfyOnMaxZoom: false,
    showCoverageOnHover: false,
    maxClusterRadius: function (zoom) {
      return zoom >= 13 ? 32 : zoom >= 10 ? 46 : 60;
    },
    /* The badge stays the STORE COUNT: "how many places" is the mental model
       people bring to a cluster, and summing cabs there would quietly conflate
       one 40-cab megastore with twenty small ones. The only thing the cab data
       changes here is a small size bump plus a warmer border when the bubble is
       hiding at least one XL/XXL store, so a big venue is still findable from a
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

  var markerOf = {};   /* id -> L.circleMarker */

  /* ---------- graduated sizing ---------- */
  /* Range grading, not a continuous Flannery curve: the counts are incomplete,
     integer-skewed and small, so a handful of clearly separated steps reads
     better than a smooth ramp nobody can decode.

     UNKNOWN IS NOT SMALLEST. Most stores have no game_counts at all (official
     ALL.Net / e-amusement lists publish presence, not quantities). Drawing them
     at the S size would tell the reader "this arcade has one cab", which the
     data never said. They take the M size instead - the same size the whole map
     uses when scaling is switched off - so an unknown store looks ordinary
     rather than tiny.

     Radii are screen pixels and deliberately zoom-independent: a fractional
     zoom of 12.84 draws the same 8.5 px dot as 13 does, which is what keeps a
     wheel gesture from turning into thousands of geometry recalculations. */

  /* Declared before the cluster group because iconCreateFunction calls it.
     Function declarations hoist, so the group's option can name it safely. */

  /* Does this bubble hide at least one XL/XXL store? Answered by walking the
     cluster's own subtree once and caching the answer on the cluster object,
     keyed on its child count so a bubble that gains children re-answers. The
     tree is rebuilt from scratch on every filter change (clearLayers drops
     _topClusterLevel), so no stale flag can outlive its cluster. */
  function clusterHasBig(c) {
    if (!scalingOn()) return false;
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
    return !!(m && m._amClass && m._amClass.glow);
  }

  var UNIFORM_R = 6;   /* scaling off, and the unknown-count default */

  var SIZE_CLASSES = [
    { id: "s",   label: "S",   min: 1,  max: 2,        r: 4,    glow: false },
    { id: "m",   label: "M",   min: 3,  max: 6,        r: 6,    glow: false },
    { id: "l",   label: "L",   min: 7,  max: 12,       r: 8.5,  glow: false },
    { id: "xl",  label: "XL",  min: 13, max: 24,       r: 11,   glow: true },
    { id: "xxl", label: "XXL", min: 25, max: Infinity, r: 14,   glow: true }
  ];
  var UNKNOWN_CLASS = {
    id: "u", label: "Unknown", min: null, max: null, r: UNIFORM_R, glow: false
  };

  /* Total cabs, or null when the data does not say. Sums every game the store
     reports a count for, not just the ones currently selected: the dot's size
     is a property of the arcade, so it must not jump when a chip is toggled. */
  function totalCabs(a) {
    return F.totalCabs(a && a.game_counts);
  }

  function classFor(a) {
    var n = totalCabs(a);
    if (n === null) return UNKNOWN_CLASS;
    for (var i = 0; i < SIZE_CLASSES.length; i++) {
      if (n >= SIZE_CLASSES[i].min && n <= SIZE_CLASSES[i].max) return SIZE_CLASSES[i];
    }
    /* n < 1 with a game_counts key present: treat as unknown, never as zero. */
    return UNKNOWN_CLASS;
  }

  /* Default on. undefined means no settings module has written the key yet, so
     fall back to whatever a past session persisted; only an explicit false
     turns scaling off. Same shape as nearby.js's locationAllowed. */
  function scalingOn() {
    var v = AM.state.get("markerScaling");
    if (v === undefined || v === null) v = AM.state.readSetting("markerScaling", true);
    return v !== false;
  }

  /* Push one arcade's size class onto its marker. setRadius keeps _radius,
     options.radius and the pixel bounds in step and redraws only if the marker
     is actually on the map, so the off-screen 99% cost nothing. */
  function styleSize(a, on) {
    var m = markerOf[a.id];
    if (!m) return;
    var cls = classFor(a);
    m._amClass = cls;
    var r = on ? cls.r : UNIFORM_R;
    m.options.amGlow = !!(on && cls.glow);
    if (m.options.radius !== r) m.setRadius(r);
  }

  /* Called once at build and once per markerScaling change - never per frame.
     Leaflet redraws canvas circles from the cached options.radius while panning
     and zooming, so a gesture does no sizing work at all. */
  var lastScaling = null;
  function applyScale(force) {
    var on = scalingOn();
    if (!force && on === lastScaling) return;
    lastScaling = on;
    var list = AM.data.plottable;
    for (var i = 0; i < list.length; i++) styleSize(list[i], on);
    /* Cluster bubbles carry the same signal, so their icons are stale now. */
    if (typeof cluster.refreshClusters === "function") cluster.refreshClusters();
  }

  /* ---------- glow ring for the two biggest classes ---------- */
  /* Leaflet's canvas renderer draws exactly one arc per circleMarker, so the
     soft outer ring is added by wrapping the renderer's private circle drawing
     rather than by adding a second layer per store: extra layers would double
     the hit-test list, and a separate glow pane would keep glowing under a
     cluster bubble that has swallowed the store.

     Only AM.map.renderer is wrapped, never L.Canvas.prototype, so any other
     canvas layer on the page is untouched. Markers without options.amGlow take
     the original code path unchanged.

     Two concentric translucent rings in the marker's own game colour: no new
     hue, and no ctx.shadowBlur (blur is the slowest thing a 2d context does). */

  var GLOW_RINGS = [
    { pad: 1.5, weight: 3, alpha: 0.30 },
    { pad: 4.0, weight: 5, alpha: 0.14 }
  ];
  /* How far the outermost ring reaches past the circle edge: pad + weight / 2. */
  var GLOW_PAD = 6.5;

  (function patchRenderer(renderer) {
    if (!renderer || renderer._amGlowPatched) return;
    renderer._amGlowPatched = true;
    var baseCircle = renderer._updateCircle;
    var baseExtend = renderer._extendRedrawBounds;

    renderer._updateCircle = function (layer) {
      if (layer.options.amGlow && this._drawing && !layer._empty()) {
        /* Recorded where the ring is actually painted, so the clip below can
           still cover those pixels once options.amGlow has gone back to false. */
        layer._amGlowEver = true;
        var ctx = this._ctx, p = layer._point;
        var r = Math.max(Math.round(layer._radius), 1);
        ctx.save();
        ctx.strokeStyle = layer.options.fillColor || layer.options.color;
        for (var i = 0; i < GLOW_RINGS.length; i++) {
          var g = GLOW_RINGS[i];
          ctx.globalAlpha = g.alpha;
          ctx.lineWidth = g.weight;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r + g.pad, 0, 2 * Math.PI, false);
          ctx.stroke();
        }
        ctx.restore();
      }
      baseCircle.call(this, layer);
    };

    /* A partial redraw (one marker restyled) clips to the layer's pixel bounds
       plus its stroke weight. The glow lives outside those bounds, so without
       this the ring would survive as a stale halo after a colour change.

       The test is _amGlowEver, not the current options.amGlow: turning the glow
       OFF is exactly the case that must repaint the old ring's pixels, and by
       the time this runs options.amGlow is already false. A marker that has
       glowed at any point therefore keeps the padded clip for good - it costs a
       slightly larger clear rectangle and nothing else. */
    renderer._extendRedrawBounds = function (layer) {
      baseExtend.call(this, layer);
      if (layer.options.amGlow) layer._amGlowEver = true;
      if (layer._amGlowEver && layer._pxBounds && this._redrawBounds) {
        this._redrawBounds.extend(layer._pxBounds.min.subtract([GLOW_PAD, GLOW_PAD]));
        this._redrawBounds.extend(layer._pxBounds.max.add([GLOW_PAD, GLOW_PAD]));
      }
    };
  })(AM.map.renderer);

  /* ---------- visibility predicate (single source of truth) ---------- */

  /* Does arcade a count as a hit for game g under the current cab filters? */
  function matchesForGame(a, g, selCabs) {
    if (a.games.indexOf(g) === -1) return false;
    for (var i = 0; i < C.CAB_FILTERS.length; i++) {
      var cf = C.CAB_FILTERS[i];
      if (cf.game !== g || !selCabs.has(cf.id)) continue;
      var ok = false;
      for (var j = 0; j < cf.slugs.length; j++) {
        if (a.cabs && a.cabs.indexOf(cf.slugs[j]) !== -1) { ok = true; break; }
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

  function isVisible(a, selGames, selCabs, enabledSources) {
    selGames = selGames || AM.state.get("selectedGames");
    selCabs = selCabs || AM.state.get("selectedCabs");
    enabledSources = enabledSources || AM.state.get("enabledSources");
    if (!selGames) return false;
    if (!sourceEnabled(a, enabledSources)) return false;
    return displayGame(a, selGames, selCabs) !== null;
  }

  /* ---------- popup ---------- */

  function popupHtml(a) {
    var esc = U.esc;
    var h = '<div class="pp-name">' + esc(a.name) + "</div>";
    h += '<div class="pp-addr">' + esc(a.addr || "") +
      (a.pref ? " &middot; " + esc(a.pref) : "") + " &middot; " + esc(a.country) + "</div>";
    h += '<div class="pp-row">';
    a.games.forEach(function (g) {
      h += '<span class="gc" style="--c:' + (C.GAME_COLOR[g] || C.GAME_COLOR.other) + '">' +
        esc(C.GAME_LABEL[g] || g) + "</span>";
    });
    h += "</div>";
    if (a.cabs && a.cabs.length) {
      h += '<div class="pp-row">';
      a.cabs.forEach(function (c) {
        h += '<span class="badge cab">' + esc(C.CAB_BADGE[c] || c) + "</span>";
      });
      h += "</div>";
    }
    if (a.src && a.src.length) {
      h += '<div class="pp-row">';
      a.src.forEach(function (s) {
        var label = esc(C.SRC_LABEL[s] || s);
        if ((s === "ziv" || s === "bemanicn") && a.links && a.links[s]) {
          h += '<a class="badge" target="_blank" rel="noopener" href="' +
            esc(a.links[s]) + '">' + label + "</a>";
        } else {
          h += '<span class="badge">' + label + "</span>";
        }
      });
      h += "</div>";
    }
    if (a.notes) h += '<div class="pp-addr">' + esc(a.notes) + "</div>";
    var gm = (a.links && a.links.gmaps) ? a.links.gmaps : U.gmapsSearchUrl(a);
    h += '<a class="pp-gmaps" target="_blank" rel="noopener" href="' + esc(gm) +
      '">Open in Google Maps</a>';
    return h;
  }

  /* ---------- build + apply ---------- */

  function build() {
    var on = scalingOn();
    lastScaling = on;
    AM.data.plottable.forEach(function (a) {
      var cls = classFor(a);
      var m = L.circleMarker([a.lat, a.lng], {
        renderer: AM.map.renderer, radius: on ? cls.r : UNIFORM_R,
        weight: 1.5, color: "#ffffff",
        opacity: 0.9, fillColor: C.GAME_COLOR.other, fillOpacity: 0.92,
        amGlow: on && cls.glow
      });
      m._amClass = cls;
      m.bindPopup(function () { return popupHtml(a); }, { maxWidth: 320 });
      markerOf[a.id] = m;
    });
  }

  function applyFilters() {
    var selGames = AM.state.get("selectedGames");
    if (!selGames) return;
    var selCabs = AM.state.get("selectedCabs");
    var enabled = AM.state.get("enabledSources");
    var plottable = AM.data.plottable;
    var vis = [];
    for (var i = 0; i < plottable.length; i++) {
      var a = plottable[i];
      if (!sourceEnabled(a, enabled)) continue;
      var g = displayGame(a, selGames, selCabs);
      if (!g) continue;
      var m = markerOf[a.id];
      var color = C.GAME_COLOR[g] || C.GAME_COLOR.other;
      if (m.options.fillColor !== color) m.setStyle({ fillColor: color });
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
    /* .halo-core is the steady ring that always reads in a screenshot;
       .halo-pulse is the echo that expands out of it once per 1.2s. */
    var icon = L.divIcon({
      className: "halo-wrap",
      html: '<div class="halo-pulse"></div><div class="halo-core"></div>',
      iconSize: [32, 32],
      iconAnchor: [16, 16]
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
     (not hasLayer, which can be true with no __parent). */
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
     same corner would just be clutter. SIZE_CLASSES is exported below so that
     module can render the real thresholds rather than a hard-coded copy. */

  function start() {
    AM.state.on("selectedGames", scheduleApply);
    AM.state.on("selectedCabs", scheduleApply);
    AM.state.on("enabledSources", scheduleApply);
    /* Resizing every marker in place is enough - the cluster tree is unchanged,
       so there is no reason to pay for a full clearLayers + addLayers rebuild.
       refreshClusters inside applyScale redraws the bubbles that changed. */
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
    /* graduated sizing */
    SIZE_CLASSES: SIZE_CLASSES,
    UNKNOWN_CLASS: UNKNOWN_CLASS,
    UNIFORM_R: UNIFORM_R,
    totalCabs: totalCabs,
    classFor: classFor,
    scalingOn: scalingOn,
    applyScale: applyScale,
    clusterHasBig: clusterHasBig
  };
})(window.AM);
