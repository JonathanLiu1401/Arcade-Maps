/* Arcade Maps - nearby + location.

   Owns:
     - the crosshair locate control under the zoom buttons
     - the browser geolocation call, the user dot and its accuracy circle
     - the "Nearby arcades" list that takes over the drawer area
     - the "Search this area" pill that re-anchors the list to the map centre

   Everything it ranks goes through AM.markers.isVisible, so the list can never
   offer a store the current game / cab / source filters have hidden. Stores
   with no coordinates are deliberately excluded: they cannot be ranked by
   distance, and guessing from the address is worse than saying nothing. The
   caption line under the list says so.

   Public surface (also the test surface - the real browser permission prompt
   cannot be driven from a test):
     AM.nearby.locate()                  ask the browser where we are
     AM.nearby.showFrom(lat, lng, opts)  anchor the list at a point
     AM.nearby.close()                   close the pane
     AM.nearby.compute(lat, lng, n, opts) ranked [{a, km, deg}], filters applied
                                          opts {excludeId, dedupe} both optional
     AM.nearby.haversineKm / bearingDeg  the maths, standalone
     AM.nearby.onPosition / onError      the geolocation callbacks themselves

   State it reads:  locationEnabled (undefined or anything but false = allowed)
   State it emits:  selectedArcade   {focus: true, source: "nearby"}
   State it hears:  nearbyFrom {lat, lng, id?, label?, fly?} - a place panel
                    asking for "what is near this store". id, when given, is
                    left out of the results: a store is not near itself. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts, U = AM.util;
  var $ = U.$, esc = U.esc;

  var LIMIT = 20;                 /* rows in the list */
  var R_KM = 6371.0088;           /* IUGG mean earth radius, km */
  var LOCATE_ZOOM = 14;
  var TOAST_MS = 5200;
  /* The pill appears once the anchor point leaves the viewport, or the centre
     drifts more than this share of the viewport width away from it. Using a
     share of the viewport rather than a fixed distance keeps the rule sane at
     both z=4 (viewport thousands of km wide) and z=17. */
  var PILL_SHARE = 0.25;

  var map = null;
  var origin = null;              /* {lat, lng, label, user} */
  var results = [];               /* current rows, index-aligned with data-i */
  var userLL = null;
  var dot = null, acc = null;     /* user marker, accuracy circle */
  var btn = null;                 /* the crosshair button */
  var locateCtl = null;           /* the Leaflet control wrapping that button */
  var toastTimer = null;
  var pendingRender = false;

  /* ---------- maths ---------- */

  var RAD = Math.PI / 180;

  function haversineKm(lat1, lng1, lat2, lng2) {
    var p1 = lat1 * RAD, p2 = lat2 * RAD;
    var dp = (lat2 - lat1) * RAD, dl = (lng2 - lng1) * RAD;
    var s1 = Math.sin(dp / 2), s2 = Math.sin(dl / 2);
    var h = s1 * s1 + Math.cos(p1) * Math.cos(p2) * s2 * s2;
    return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  /* Initial great-circle bearing, degrees clockwise from true north. */
  function bearingDeg(lat1, lng1, lat2, lng2) {
    var p1 = lat1 * RAD, p2 = lat2 * RAD, dl = (lng2 - lng1) * RAD;
    var y = Math.sin(dl) * Math.cos(p2);
    var x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
    return (Math.atan2(y, x) / RAD + 360) % 360;
  }

  var POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  var POINT_WORDS = {
    N: "north", NE: "north east", E: "east", SE: "south east",
    S: "south", SW: "south west", W: "west", NW: "north west"
  };

  function compass(deg) { return POINTS[Math.round(deg / 45) % 8]; }

  function fmtDist(km) {
    var m = km * 1000;
    /* Below 999.5 m the metre form is the honest one; at or above it the
       rounded km form reads "1.0 km" rather than "1000 m". */
    if (m < 999.5) return (m < 10 ? m.toFixed(1) : String(Math.round(m))) + " m";
    return km.toFixed(1) + " km";
  }

  /* ---------- ranking ---------- */

  /* "What is near this store" is a question about OTHER stores, so the store
     itself must not head its own list at 0.0 m - and neither must its twin.
     The same venue reaches this data more than once (a ZIv romaji entry and a
     BemaniCN or WAHLAP entry of the same shop), and while the merge collapses
     most of those, a pair the name matcher missed still lands metres apart and
     reads as two arcades in one building. Both are dropped on the same rule:
     same normalised name within a few metres.

     Names are compared with case, spacing, punctuation and full-width forms
     folded away, which is what separates "Round1 Kyoto" from "ROUND1 KYOTO"
     without also merging two genuinely different shops in one mall. */
  var CO_LOCATED_KM = 0.015;   /* 15 m - inside one building, not next door */

  function normName(s) {
    return String(s || "")
      .toLowerCase()
      /* full-width ASCII -> ASCII, so a Japanese-typed name folds onto its
         romaji twin rather than looking like a different string */
      .replace(/[！-～]/g, function (c) {
        return String.fromCharCode(c.charCodeAt(0) - 0xFEE0);
      })
      .replace(/[\s　]+/g, "")
      .replace(/[-_.,'"()\[\]{}·・:;!?&/\\]/g, "");
  }

  /* Nearest n visible, plottable arcades to a point. Filters are read once and
     handed to the predicate so 8k entries cost one state read, not 8k.

     opts.excludeId drops one store outright (the one the list was opened
     from); opts.dedupe collapses co-located same-name rows. Both default off
     so the documented compute(lat, lng, n) contract is unchanged for any
     existing caller and for the tests. */
  function compute(lat, lng, n, opts) {
    var selGames = AM.state.get("selectedGames");
    if (!selGames) return [];
    opts = opts || {};
    var selCabs = AM.state.get("selectedCabs");
    var enabled = AM.state.get("enabledSources");
    var list = AM.data.plottable;
    var skipId = opts.excludeId;
    var skipName = (skipId !== undefined && skipId !== null && AM.data.byId[skipId])
      ? normName(AM.data.byId[skipId].name) : null;
    var out = [];
    for (var i = 0; i < list.length; i++) {
      var a = list[i];
      if (skipId !== undefined && skipId !== null && a.id === skipId) continue;
      if (!AM.markers.isVisible(a, selGames, selCabs, enabled)) continue;
      var km = haversineKm(lat, lng, a.lat, a.lng);
      /* The origin's own duplicate: same name, sitting on top of the origin. */
      if (skipName && km <= CO_LOCATED_KM && normName(a.name) === skipName) continue;
      out.push({ a: a, km: km, deg: 0 });
    }
    out.sort(function (x, y) { return x.km - y.km; });

    if (opts.dedupe) {
      var kept = [];
      for (var j = 0; j < out.length; j++) {
        var r = out[j], dup = false;
        var nm = normName(r.a.name);
        for (var k = 0; k < kept.length; k++) {
          /* Sorted by distance, so a twin is always within CO_LOCATED_KM of an
             entry already kept - comparing the two distances is enough and no
             second haversine is needed. */
          if (normName(kept[k].a.name) === nm &&
              Math.abs(kept[k].km - r.km) <= CO_LOCATED_KM) { dup = true; break; }
        }
        if (!dup) kept.push(r);
        if (kept.length >= (n || LIMIT)) break;
      }
      out = kept;
    } else {
      out = out.slice(0, n || LIMIT);
    }

    out.forEach(function (r) {
      r.deg = bearingDeg(lat, lng, r.a.lat, r.a.lng);
    });
    return out;
  }

  /* ---------- list rendering ---------- */

  var ARROW = '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">' +
    '<path fill="currentColor" d="M8 1.5 12.6 13 8 10.6 3.4 13z"/></svg>';

  function chipsFor(a) {
    var selGames = AM.state.get("selectedGames");
    var selCabs = AM.state.get("selectedCabs");
    var hits = a.games.filter(function (g) {
      return selGames.has(g) && AM.markers.matchesForGame(a, g, selCabs);
    });
    var shown = hits.slice(0, 3);
    /* gameLabelFor, not the raw GAME_LABEL table: a store whose only known
       maimai cabinet is the pre-DX one must not be labelled "maimai DX" here
       when the panel, popup and search rows all call it FiNALE. This list was
       the last surface still printing the raw label, which made the same
       store read as a live DX venue in the one place a phone user scans
       fastest. */
    var h = shown.map(function (g) {
      return '<span class="gc" style="--c:' +
        (C.GAME_COLOR[g] || C.GAME_COLOR.other) + '">' +
        esc(U.gameLabelFor(a, g)) + "</span>";
    }).join("");
    if (hits.length > shown.length) {
      h += '<span class="nb-more tabnum">+' + (hits.length - shown.length) + "</span>";
    }
    return h;
  }

  function rowHtml(r, i) {
    var a = r.a, pt = compass(r.deg);
    var label = a.name + ", " + fmtDist(r.km) + " " + POINT_WORDS[pt];
    return '<button class="nb-row" type="button" data-i="' + i + '" aria-label="' +
      esc(label) + '">' +
      '<span class="nb-arrow" style="transform:rotate(' + r.deg.toFixed(1) +
      'deg)" aria-hidden="true">' + ARROW + "</span>" +
      '<span class="nb-main">' +
      '<span class="nb-name">' + esc(a.name) + "</span>" +
      '<span class="nb-chips">' + chipsFor(a) + "</span>" +
      "</span>" +
      '<span class="nb-dist"><span class="tabnum">' + esc(fmtDist(r.km)) +
      '</span><span class="nb-comp">' + pt + "</span></span>" +
      "</button>";
  }

  function renderList() {
    var box = $("nb-list");
    if (!box || !origin) return;
    results = compute(origin.lat, origin.lng, LIMIT,
      { excludeId: origin.id, dedupe: true });
    if (!results.length) {
      box.innerHTML = '<p class="hint nb-empty">No stores match the current ' +
        "filters. Turn a game or a source back on to see nearby results.</p>";
    } else {
      box.innerHTML = results.map(rowHtml).join("");
    }
    var head = $("nb-origin");
    if (head) {
      head.innerHTML = origin.user
        ? "Nearest to your location" +
          (origin.acc ? ' <span class="nb-acc tabnum">&plusmn;' +
            Math.round(origin.acc) + " m</span>" : "")
        : "Nearest to " + esc(origin.label || "this point") +
          ' <span class="nb-acc tabnum">' + origin.lat.toFixed(3) + ", " +
          origin.lng.toFixed(3) + "</span>";
    }
    var cap = $("nb-caption");
    if (cap) {
      cap.textContent = results.length
        ? "Showing the " + results.length + " nearest stores that match your " +
          "filters. Stores without coordinates are not shown."
        : "Stores without coordinates are not shown.";
    }
  }

  /* A state.batch() flush emits several keys in one go; rebuilding the list per
     key would scan 8k entries twice. Collapse to one render per tick, the way
     markers.js collapses its layer rebuild. */
  function scheduleRender() {
    if (!isOpen() || pendingRender) return;
    pendingRender = true;
    Promise.resolve().then(function () {
      pendingRender = false;
      if (isOpen()) { renderList(); updatePill(); }
    });
  }

  /* ---------- pane ---------- */

  function isOpen() { return document.body.classList.contains("nearby-open"); }

  function openPane() {
    document.body.classList.add("nearby-open");
    if (AM.panel && AM.panel.openDrawer) AM.panel.openDrawer();
  }

  function close() {
    if (!isOpen()) return;
    document.body.classList.remove("nearby-open");
    var pill = $("nb-research");
    if (pill) pill.classList.remove("on");
  }

  function isNarrow() {
    return !!(window.matchMedia && window.matchMedia("(max-width: 760px)").matches);
  }

  /* On a phone the drawer covers the map, so a pick would fly to a store the
     user cannot see. AM.panel has openDrawer but no closeDrawer yet (noted in
     the handover); mirror what the toggle does, minus invalidateSize - the
     panel is position:absolute at this width so the map never resizes, and
     calling it mid-flight only risks disturbing the flyTo. */
  function collapseDrawer() {
    document.body.classList.add("drawer-closed");
    var t = $("drawer-toggle");
    if (t) t.setAttribute("aria-expanded", "false");
  }

  function onRowClick(e) {
    var el = e.target.closest ? e.target.closest(".nb-row") : null;
    if (!el) return;
    var r = results[Number(el.dataset.i)];
    if (!r) return;
    var rows = $("nb-list").querySelectorAll(".nb-row");
    for (var i = 0; i < rows.length; i++) rows[i].classList.remove("on");
    el.classList.add("on");
    /* a.id, not the string off the dataset: ids are numbers in the data and
       search puts numbers into this key. */
    AM.state.set("selectedArcade", r.a.id, { focus: true, source: "nearby" });
    if (isNarrow()) collapseDrawer();
  }

  /* ---------- "search this area" pill ---------- */

  function viewportWidthKm() {
    var b = map.getBounds(), c = map.getCenter();
    return haversineKm(c.lat, b.getWest(), c.lat, b.getEast());
  }

  function updatePill() {
    var pill = $("nb-research");
    if (!pill) return;
    if (!isOpen() || !origin) { pill.classList.remove("on"); return; }
    var b = map.getBounds(), c = map.getCenter();
    var away = haversineKm(c.lat, c.lng, origin.lat, origin.lng);
    var moved = !b.contains(L.latLng(origin.lat, origin.lng)) ||
      away > viewportWidthKm() * PILL_SHARE;
    pill.classList.toggle("on", moved);
  }

  function searchThisArea() {
    var c = map.getCenter();
    /* A fresh anchor with no store behind it: nothing is excluded from here. */
    setOrigin(c.lat, c.lng, "the map centre", false, null, null);
    renderList();
    updatePill();
    var box = $("nb-list");
    if (box) box.scrollTop = 0;
  }

  /* ---------- user position ---------- */

  /* id is carried so the list can leave the store it was opened from out of
     its own results; it is absent for a user position or a map-centre search,
     and every consumer treats that as "exclude nothing". */
  function setOrigin(lat, lng, label, user, accuracy, id) {
    origin = {
      lat: lat, lng: lng, label: label, user: !!user,
      acc: accuracy || 0,
      id: (id === undefined || id === null) ? null : id
    };
  }

  function clearUser() {
    userLL = null;
    if (dot) { map.removeLayer(dot); dot = null; }
    if (acc) { map.removeLayer(acc); acc = null; }
    if (btn) btn.classList.remove("on");
  }

  function showUser(lat, lng, accuracy) {
    clearUser();
    userLL = [lat, lng];
    if (accuracy && isFinite(accuracy) && accuracy > 0) {
      acc = L.circle(userLL, {
        radius: accuracy, pane: "locateAccPane", interactive: false,
        color: "#3ea6ff", weight: 1, opacity: 0.55,
        fillColor: "#3ea6ff", fillOpacity: 0.12
      }).addTo(map);
    }
    dot = L.marker(userLL, {
      pane: "locatePane", interactive: false, keyboard: false,
      icon: L.divIcon({
        className: "nb-user",
        html: '<div class="nb-ping"></div><div class="nb-dot"></div>',
        iconSize: [18, 18], iconAnchor: [9, 9]
      })
    }).addTo(map);
    if (btn) btn.classList.add("on");
  }

  /* ---------- toast ---------- */

  function toast(msg) {
    var t = $("nb-toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove("on"); }, TOAST_MS);
  }

  /* ---------- geolocation ---------- */

  function locationAllowed() {
    /* undefined means no settings module has an opinion yet - allow. Only an
       explicit false blocks. */
    var v = AM.state.get("locationEnabled");
    if (v === undefined || v === null) v = AM.state.readSetting("locationEnabled", true);
    return v !== false;
  }

  /* The Location setting reads "Show the locate button and the list of arcades
     nearest to you", so switching it off has to actually take the control off
     the map - leaving a live crosshair that only ever answers with a refusal
     toast contradicts the switch the user just moved. The control is removed
     and re-added rather than hidden with CSS so it also leaves the tab order.
     locate() keeps its own locationAllowed() guard: the button is not the only
     caller, and a stale state must never reach geolocation. */
  function syncLocateControl() {
    if (!map || !locateCtl) return;
    var want = locationAllowed();
    var on = !!(locateCtl._map);
    if (want === on) return;
    if (want) { map.addControl(locateCtl); }
    else { map.removeControl(locateCtl); btn = null; }
  }

  function setBusy(on) {
    if (!btn) return;
    btn.classList.toggle("busy", !!on);
    btn.disabled = !!on;
  }

  function onPosition(pos) {
    setBusy(false);
    var c = pos && pos.coords;
    if (!c || typeof c.latitude !== "number" || typeof c.longitude !== "number") {
      toast("Your location came back empty. Try again in a moment.");
      return;
    }
    showUser(c.latitude, c.longitude, c.accuracy);
    showFrom(c.latitude, c.longitude, {
      user: true, accuracy: c.accuracy, fly: true
    });
  }

  var ERRORS = {
    1: "Location permission was denied. Allow it for this site in your " +
       "browser settings, then try again.",
    2: "Your location is not available right now. Try again, or search for " +
       "a city instead.",
    3: "Getting your location took too long. Try again."
  };

  function onError(err) {
    setBusy(false);
    var code = err && err.code;
    toast(ERRORS[code] || "Could not get your location.");
  }

  function locate() {
    if (!locationAllowed()) {
      toast("Location is switched off in settings.");
      return;
    }
    if (window.isSecureContext === false) {
      toast("Location needs a secure (https) connection.");
      return;
    }
    if (!navigator.geolocation) {
      toast("This browser cannot report your location.");
      return;
    }
    setBusy(true);
    try {
      navigator.geolocation.getCurrentPosition(onPosition, onError, {
        enableHighAccuracy: true, timeout: 12000, maximumAge: 60000
      });
    } catch (e) {
      setBusy(false);
      toast("Could not get your location.");
    }
  }

  /* ---------- anchoring ---------- */

  function showFrom(lat, lng, opts) {
    if (typeof lat !== "number" || typeof lng !== "number" ||
        !isFinite(lat) || !isFinite(lng)) return false;
    opts = opts || {};
    setOrigin(lat, lng, opts.label || (opts.user ? "your location" : "this point"),
      opts.user, opts.accuracy, opts.id);
    openPane();
    renderList();
    if (opts.fly) {
      var ll = [lat, lng];
      var z = opts.zoom || LOCATE_ZOOM;
      if (C.REDUCED) AM.map.setViewExact(ll, z);
      else map.flyTo(ll, z, { duration: 1.0 });
    }
    updatePill();
    var box = $("nb-list");
    if (box) box.scrollTop = 0;
    return true;
  }

  /* ---------- locate control ---------- */

  var CROSSHAIR =
    '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="4.3" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
    '<circle cx="12" cy="12" r="1.5" fill="currentColor"/>' +
    '<path d="M12 2.2v3.4M12 18.4v3.4M2.2 12h3.4M18.4 12h3.4" fill="none" ' +
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

  var LocateControl = L.Control.extend({
    options: { position: "topleft" },
    onAdd: function () {
      var wrap = L.DomUtil.create("div",
        "leaflet-bar leaflet-control leaflet-control-locate");
      var b = L.DomUtil.create("button", "", wrap);
      b.type = "button";
      b.title = "Show arcades near me";
      b.setAttribute("aria-label", "Show arcades near me");
      b.innerHTML = CROSSHAIR;
      /* Without this a click on the control also reaches the map: pan start,
         and a quick double click would zoom. */
      L.DomEvent.disableClickPropagation(wrap);
      L.DomEvent.disableScrollPropagation(wrap);
      L.DomEvent.on(b, "click", function (e) {
        L.DomEvent.preventDefault(e);
        locate();
      });
      btn = b;
      return wrap;
    }
  });

  /* ---------- wiring ---------- */

  function build() {
    map = AM.map.map;

    /* Accuracy disc under the markers (canvas markers live in overlayPane,
       z 400); the user dot above them but below the search halo at 625. */
    if (!map.getPane("locateAccPane")) {
      map.createPane("locateAccPane");
      map.getPane("locateAccPane").style.zIndex = 350;
      map.getPane("locateAccPane").style.pointerEvents = "none";
    }
    if (!map.getPane("locatePane")) {
      map.createPane("locatePane");
      map.getPane("locatePane").style.zIndex = 615;
      map.getPane("locatePane").style.pointerEvents = "none";
    }

    locateCtl = new LocateControl();
    map.addControl(locateCtl);
    syncLocateControl();

    $("nb-close").addEventListener("click", close);
    $("nb-list").addEventListener("click", onRowClick);

    /* The pill and the toast live inside the map container so they can be
       centred over the tiles; without this their clicks would also start a
       map drag. */
    var pill = $("nb-research"), t = $("nb-toast");
    L.DomEvent.disableClickPropagation(pill);
    L.DomEvent.disableScrollPropagation(pill);
    L.DomEvent.disableClickPropagation(t);
    pill.addEventListener("click", searchThisArea);
    t.addEventListener("click", function () { this.classList.remove("on"); });
    /* Leaving the nearby list via the drawer tabs. */
    ["tab-filters", "tab-china"].forEach(function (id) {
      var t = $(id);
      if (t) t.addEventListener("click", close);
    });
    $("pane-nearby").addEventListener("keydown", function (e) {
      if (e.key === "Escape") { close(); if (btn) btn.focus(); }
    });
  }

  function start() {
    AM.state.on("selectedGames", scheduleRender);
    AM.state.on("selectedCabs", scheduleRender);
    AM.state.on("enabledSources", scheduleRender);

    /* A store with no coordinates routes to the no-coords tab, which this pane
       covers - get out of the way so the user sees the entry. */
    AM.state.on("selectedArcade", function (id, meta) {
      if (!meta || !meta.focus) return;
      var a = AM.data.byId[id];
      if (a && !U.hasCoords(a)) close();
    });

    /* A settings module may revoke location while the dot is on the map. */
    AM.state.on("locationEnabled", function (v) {
      if (v === false) {
        clearUser();
        if (origin && origin.user) close();
      }
      /* Take the crosshair off the map (or put it back) so the control on
         screen always matches the switch in Settings > Location. */
      syncLocateControl();
    });

    /* "What is near this place?" from a detail panel. */
    AM.state.on("nearbyFrom", function (v) {
      if (!v || typeof v.lat !== "number" || typeof v.lng !== "number") return;
      showFrom(v.lat, v.lng, {
        label: v.label || "this place", user: false, fly: !!v.fly, zoom: v.zoom,
        id: v.id
      });
    });

    map.on("moveend", updatePill);
  }

  AM.nearby = {
    build: build,
    start: start,
    locate: locate,
    showFrom: showFrom,
    close: close,
    compute: compute,
    haversineKm: haversineKm,
    bearingDeg: bearingDeg,
    compass: compass,
    fmtDist: fmtDist,
    onPosition: onPosition,
    onError: onError,
    isOpen: isOpen,
    origin: function () { return origin; },
    results: function () { return results.slice(); }
  };
})(window.AM);
