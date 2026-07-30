/* Arcade Maps - the Leaflet map, tiles, panes and URL hash state.
   Owns map motion (smooth fractional wheel zoom) and the shared canvas
   renderer; marker content lives in markers.js. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts;
  var REDUCED = C.REDUCED;

  /* ---------- map ---------- */
  /* zoomSnap is 0, which means NO zoom level is ever rounded to a grid.
     It used to be 0.25, and that quarter-level grid was the "chunky zoom" the
     owner reported on a phone. The wheel handler was never snapped, so desktop
     looked fine and the defect hid there, but PINCH is a different code path:
     Leaflet's TouchZoom ends with _animateZoom(center, _limitZoom(zoom)), and
     _limitZoom rounds to zoomSnap. A measured pinch ran smoothly up to z14.864
     and then jumped BACKWARDS to z14.75 the instant the fingers lifted - a
     0.114-level recoil at the end of every single pinch. Snapping to 0 makes
     the gesture end exactly where the fingers left it, which is what Google
     Maps does and what the owner is asking for.

     zoomDelta 0.5 is what still gives the +/- buttons, the keyboard and
     double-click a definite step (0.5 levels per press) now that no grid does.
     Those are RELATIVE steps, so from a fractional 13.37 the + button lands on
     13.87 rather than the old grid's 13.75.

     smoothSensitivity is the single wheel-speed knob: zoom levels per unit of
     L.DomEvent.getWheelDelta, applied as delta * 0.003 * sensitivity. Chrome
     reports getWheelDelta 50 for one 100 px notch, so 0.003 * 50 * 3 = 0.45
     levels per notch - a touch under half a level, matching the research's
     "slightly slower, finer" target (wheelPxPerZoomLevel 80 equivalent). */
  var map = L.map("map", {
    zoomControl: true,
    worldCopyJump: true,
    fadeAnimation: !REDUCED,
    zoomAnimation: !REDUCED,
    markerZoomAnimation: !REDUCED,
    zoomSnap: 0,
    zoomDelta: 0.5,
    wheelPxPerZoomLevel: 80,
    wheelDebounceTime: 20,
    /* Reduced motion keeps Leaflet's built-in, non-animated wheel zoom. With
       zoomSnap 0 that path is no longer snapped to a grid either (Leaflet only
       rounds the wheel delta when zoomSnap is non-zero), so it stays a plain
       un-animated jump per notch, which is the point for reduced motion. */
    scrollWheelZoom: REDUCED,
    smoothWheelZoom: !REDUCED,
    smoothSensitivity: 3
  });

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  var renderer = L.canvas({ padding: 0.5 });

  /* pane for the search-result highlight halo: above markers (600), below popups (700) */
  map.createPane("haloPane");
  map.getPane("haloPane").style.zIndex = 625;
  map.getPane("haloPane").style.pointerEvents = "none";

  /* ---------- view helpers ---------- */

  /* setView applies _limitZoom, which snaps to zoomSnap. Restoring a shared
     link captured mid-gesture (say z=12.37) would otherwise land on 12.25, so
     the snap is suspended for the duration of the restore.

     With zoomSnap now 0 this is a no-op, and it is kept deliberately: it is
     the guarantee that an exact zoom survives, not a consequence of the
     current option value. If a future change reintroduces a snap grid, shared
     links keep round-tripping without anyone having to rediscover this. */
  function setViewExact(latlng, zoom, options) {
    var snap = map.options.zoomSnap;
    map.options.zoomSnap = 0;
    try { map.setView(latlng, zoom, options); }
    finally { map.options.zoomSnap = snap; }
    return map;
  }

  /* The opening view when the URL carries no #z/lat/lng.

     fitBounds alone is honest but unreadable on a phone: the data bbox spans
     lat -54.8..69.7 / lng -158.0..176.9, which is 93% of the world's width and
     only 46% of its Mercator height. Fitting that into a 390x713 map column
     solves for the WIDTH and lands on z0.47 (which the old zoomSnap 0.25
     rounded to 0.25), so the world is drawn 355px tall inside a 713px box -
     245px of dead grey above it and 217px below. The map reads as broken
     before a single store is legible.

     The floor below is computed, not snapped, so it is unaffected by zoomSnap
     being 0: the opening view was measured at z1.576 both before and after
     that change.

     So the fit is kept, then floored: below the zoom at which the world fills
     the container's HEIGHT there is nothing but empty grey to gain, so that
     value is the floor. It is computed from the live container rather than
     hard-coded because the collapsing footer changes #map's height (713px
     with the footer expanded, ~764px collapsed) and either literal would be
     wrong for one of the two states.

     The floor self-disables wherever the natural fit already clears it: a
     1280x822 desktop map fits at z2.36 against a floor of 1.68, so desktop
     takes the fitBounds branch and needs no media query. (Measured at
     1600x900: the fit is z2.2766 with zoomSnap 0 where it was z2.25 on the
     old quarter grid, a 0.027-level difference, and the opening view still
     contains the whole data bbox.)

     The floored view has to be re-centred: the bbox centre (16.1N, 9.5E) is
     the middle of Africa, and at the tighter zoom that frames the Atlantic and
     leaves 32.8% of stores on screen.

     The latitude is 0 on purpose, and it is not a compromise. At exactly the
     height-fill zoom the world is the same height as the container, so any
     other centre latitude slides it off one edge and reintroduces the grey
     band this fix exists to remove - the first attempt centred on the stores'
     Mercator-mean (30.6N) and measured 68px of grey back at the top. Equator-
     centred, the world's full latitude range is on screen, so EVERY store is
     within the vertical extent and only longitude can exclude one.

     The longitude is then free, and 83E is its measured optimum: the view is
     390px of a 763px world, so it shows 51% of the world's longitudes, and
     that window holds 11,041 of 13,460 plottable stores (82.0%) - it spans
     Western Europe through Japan, which is where the data actually lives
     (China 6,357, Japan 1,644, UK 722). The runner-up centres scored 81.8%
     (69E) and 74.2% (100E). */
  var FIT_CENTER = [0, 83];

  function heightFillZoom() {
    var h = map.getSize().y;
    /* 256px is Leaflet's tile size: the whole world is 256 * 2^z px tall. */
    return h > 0 ? Math.log(h / 256) / Math.LN2 : 0;
  }

  /* Exactly ONE view command is issued, whichever branch wins.

     The first version of this fitBounds'd and then corrected the result with a
     second setView when it fell under the floor. That worked on a cold load
     with no hash but broke the #arcade=<id> deep link about two boots in three:
     panel.start() fires the focus flyTo a few hundred ms later, and the extra
     queued view command raced it - the flight was measured reaching z6.8 and
     then collapsing back to the opening view (z1.58 at -2.36/82.80 instead of
     z16 on the store). Deciding first and moving once removes the race, and on
     desktop the else-branch is the original call unchanged. */
  function fitToPoints(points) {
    if (!points || !points.length) {
      map.setView([30, 135], 3);
      return;
    }
    var bounds = L.latLngBounds(points);
    var fitZoom = Math.min(map.getBoundsZoom(bounds, false, L.point(30, 30)), 7);
    var floor = heightFillZoom();
    if (fitZoom < floor) setViewExact(FIT_CENTER, floor);
    else map.fitBounds(bounds, { padding: [30, 30], maxZoom: 7 });
  }

  /* ---------- URL hash state ---------- */
  /* Format: #z/lat/lng/games=a,b/cabs=x,y (games absent = all selected).
     Sources are deliberately NOT in the hash: they are a per-device setting,
     so a shared link never hides half the map for the recipient. */

  var hashTimer = null, applyingHash = false, hashReady = false;

  function scheduleHashUpdate() {
    if (applyingHash || !hashReady) return;
    clearTimeout(hashTimer);
    hashTimer = setTimeout(writeHash, 250);
  }

  function trimZoom(z) {
    /* Fractional wheel zoom produces values like 12.37; keep two decimals and
       drop trailing zeros so integer zooms still read as "13". */
    return String(parseFloat(Number(z).toFixed(2)));
  }

  /* "Is everything selected?", which is what lets writeHash omit the games
     segment entirely. Matching on SIZE alone would be set equality only if the
     selection were guaranteed to be a subset of gamesInData, and it is not:
     parseHash accepts whatever slugs the URL carries and applyHashState installs
     them verbatim. A link with as many unknown slugs as there are real games
     therefore looked like "all games" to the old test, and the next write
     dropped the segment - silently converting a filtered link into an
     unfiltered one. Unknown slugs match no arcade, so they are harmless until
     they are counted. */
  function isAllGames(selGames, gamesInData) {
    if (selGames.size !== gamesInData.length) return false;
    for (var i = 0; i < gamesInData.length; i++) {
      if (!selGames.has(gamesInData[i])) return false;
    }
    return true;
  }

  function writeHash() {
    var selGames = AM.state.get("selectedGames");
    if (!selGames) return;
    var selCabs = AM.state.get("selectedCabs");
    var gamesInData = AM.data.gamesInData;
    var c = map.getCenter();
    var parts = [trimZoom(map.getZoom()), c.lat.toFixed(5), c.lng.toFixed(5)];
    if (!isAllGames(selGames, gamesInData)) {
      parts.push("games=" + gamesInData.filter(function (g) {
        return selGames.has(g);
      }).join(","));
    }
    if (selCabs.size) {
      parts.push("cabs=" + C.CAB_FILTERS.filter(function (cf) {
        return selCabs.has(cf.id);
      }).map(function (cf) { return cf.id; }).join(","));
    }
    var h = "#" + parts.join("/");
    if (location.hash !== h) history.replaceState(null, "", h);
  }

  function parseHash() {
    var out = { view: null, games: null, cabs: null };
    var raw = location.hash.replace(/^#/, "");
    if (!raw) return out;
    var segs = raw.split("/");
    if (segs.length >= 3) {
      var z = parseFloat(segs[0]), lat = parseFloat(segs[1]), lng = parseFloat(segs[2]);
      if (isFinite(z) && isFinite(lat) && isFinite(lng)) {
        out.view = { z: z, lat: lat, lng: lng };
      }
    }
    segs.forEach(function (s) {
      if (s.indexOf("games=") === 0) {
        out.games = new Set(s.slice(6).split(",").filter(Boolean));
      } else if (s.indexOf("cabs=") === 0) {
        out.cabs = new Set(s.slice(5).split(",").filter(Boolean));
      }
    });
    return out;
  }

  /* Applied on hashchange: rebuild filter state from the URL in one batch so
     the marker layer is rebuilt once, not once per key. */
  function applyHashState() {
    var selGames = AM.state.get("selectedGames");
    if (!selGames) return;
    applyingHash = true;
    /* try/finally, because everything between here and the reset can throw on
       hostile input: batch() runs listeners from five modules and rethrows, and
       setViewExact hands Leaflet numbers taken verbatim from the URL. A throw
       that skipped the reset would leave applyingHash true for the life of the
       page, and scheduleHashUpdate's first line would then silently discard
       every later URL update - the map would stop being shareable with no
       visible symptom. */
    try {
      var st = parseHash();
      AM.state.batch(function () {
        AM.state.set("selectedGames", st.games || new Set(AM.data.gamesInData));
        AM.state.set("selectedCabs", st.cabs || new Set());
      });
      if (st.view) setViewExact([st.view.lat, st.view.lng], st.view.z);
    } finally {
      applyingHash = false;
    }
  }

  function startHashSync() {
    hashReady = true;
    map.on("moveend", scheduleHashUpdate);
    window.addEventListener("hashchange", applyHashState);
    AM.state.on("selectedGames", scheduleHashUpdate);
    AM.state.on("selectedCabs", scheduleHashUpdate);
    /* Write the opening view straight away, as the pre-refactor build did. */
    scheduleHashUpdate();
  }

  AM.map = {
    map: map,
    renderer: renderer,
    parseHash: parseHash,
    writeHash: writeHash,
    scheduleHashUpdate: scheduleHashUpdate,
    startHashSync: startHashSync,
    setViewExact: setViewExact,
    fitToPoints: fitToPoints,
    isApplyingHash: function () { return applyingHash; }
  };
})(window.AM);
