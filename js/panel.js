/* Arcade Maps - the left column. Two surfaces share it:

     1. the filter drawer  (tabs, game chips, cab checkboxes, no-coords list)
     2. the PLACE PANEL    (details for one store)

   Selecting a store swaps surface 2 over surface 1; the back arrow swaps it
   back with the drawer untouched underneath. Under 760px the place panel is a
   bottom sheet instead, so the map stays usable above it.

   The panel's DOM is built here rather than in index.html: nothing else needs
   to know about it, and it keeps this feature to one file. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts, U = AM.util;
  var $ = U.$, esc = U.esc;

  var SHEET_PEEK = 0.45;   /* mobile resting height, fraction of the map column */
  var SHEET_FULL = 0.88;   /* mobile expanded height */
  var DISMISS_PX = 90;     /* drag past this and the sheet is dismissed */
  var ANIM_MS = 190;

  /* Desktop column width. --panel-w in style.css is the single source of truth
     for BOTH the filter drawer and the place panel (they share the column), so
     the drag handle only ever writes this one property. */
  var PANEL_W = 416;       /* default, matches --panel-w in style.css */
  var PANEL_MIN = 280;
  var PANEL_MAX_VW = 0.55;
  var WIDTH_KEY = "panelWidth";

  /* ---------- game chips ---------- */

  function buildChips() {
    var box = $("game-chips");
    var counts = AM.data.gameCounts;
    AM.data.gamesInData.forEach(function (g) {
      var b = document.createElement("button");
      b.className = "chip";
      b.dataset.g = g;
      b.type = "button";
      b.style.setProperty("--c", C.GAME_COLOR[g] || C.GAME_COLOR.other);
      b.innerHTML = '<span class="dot"></span>' + esc(C.GAME_LABEL[g] || g) +
        ' <span class="n tabnum">' + U.num(counts[g] || 0) + "</span>";
      b.addEventListener("click", function () { AM.state.toggleGame(g); });
      box.appendChild(b);
    });
    $("games-all").addEventListener("click", function () {
      AM.state.set("selectedGames", new Set(AM.data.gamesInData));
    });
    $("games-none").addEventListener("click", function () {
      AM.state.set("selectedGames", new Set());
    });
  }

  function syncChips() {
    var sel = AM.state.get("selectedGames");
    if (!sel) return;
    var chips = $("game-chips").children;
    for (var i = 0; i < chips.length; i++) {
      var on = sel.has(chips[i].dataset.g);
      chips[i].classList.toggle("on", on);
      chips[i].setAttribute("aria-pressed", on ? "true" : "false");
    }
  }

  /* ---------- cab filters ---------- */

  /* Cab-variant checkboxes, GROUPED BY GAME.

     Thirteen variants in one flat list is thirteen rows of "<name> <game>"
     where the game repeats and the eye has to re-read it every line. Grouped,
     the game is stated once as a heading and each row is just the cabinet, so
     the list is shorter to scan and much shorter on a 390px screen. The
     heading takes the game's own colour, matching the chips directly above.

     The live count next to each variant is the number of PLOTTABLE stores that
     variant would leave on the map. Without it a user ticks "NEMSYS
     (standard)", watches the map empty out, and cannot tell whether the filter
     is broken or the answer is genuinely 2. */
  function variantStoreCount(cf) {
    var n = 0, list = AM.data.plottable;
    for (var i = 0; i < list.length; i++) {
      var a = list[i];
      /* Count only what ticking the box would actually leave on the map. The
         filter is applied per GAME, so a store carrying the cabinet but not
         the game slug is never a hit - counting it would print a number the
         map cannot deliver. Every variant currently agrees on both, and this
         guard keeps the sidebar honest if a later data refresh files a title
         under a different slug. */
      if (a.games.indexOf(cf.game) === -1) continue;
      var have = U.variantsOf(a);
      for (var j = 0; j < cf.slugs.length; j++) {
        if (Object.prototype.hasOwnProperty.call(have, cf.slugs[j])) { n++; break; }
      }
    }
    return n;
  }

  function buildCabFilters() {
    var box = $("cab-filters");
    var sel = AM.state.get("selectedCabs");
    var byGame = {}, order = [];
    C.CAB_FILTERS.forEach(function (cf) {
      if (!byGame[cf.game]) { byGame[cf.game] = []; order.push(cf.game); }
      byGame[cf.game].push(cf);
    });
    /* Canonical game order, so this list reads in the same order as the chips. */
    order.sort(function (x, y) {
      return C.GAME_ORDER.indexOf(x) - C.GAME_ORDER.indexOf(y);
    });
    order.forEach(function (g) {
      var head = document.createElement("div");
      head.className = "cabgrp";
      head.style.setProperty("--c", C.GAME_COLOR[g] || C.GAME_COLOR.other);
      head.textContent = C.GAME_LABEL[g] || g;
      box.appendChild(head);
      byGame[g].forEach(function (cf) {
        var lab = document.createElement("label");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = sel.has(cf.id);
        cb.addEventListener("change", function () { AM.state.toggleCab(cf.id); });
        lab.appendChild(cb);
        lab.appendChild(document.createTextNode(" " + cf.label + " "));
        var tag = document.createElement("span");
        tag.className = "cabgame tabnum";
        tag.textContent = U.num(variantStoreCount(cf));
        lab.appendChild(tag);
        lab.dataset.cab = cf.id;
        var def = C.VARIANT_BY_ID[cf.slugs[0]];
        if (def && def.note) lab.title = def.note;
        box.appendChild(lab);
      });
    });
  }

  function syncCabFilters() {
    var sel = AM.state.get("selectedCabs");
    document.querySelectorAll("#cab-filters input").forEach(function (cb) {
      var want = sel.has(cb.parentElement.dataset.cab);
      if (cb.checked !== want) cb.checked = want;
    });
  }

  /* ---------- no-coords list (grouped country + province) ---------- */

  function buildCoordlessList() {
    var box = $("china-list");
    var coordless = AM.data.coordless;
    if (!coordless.length) {
      box.innerHTML = '<p class="hint">No entries without coordinates.</p>';
      return;
    }
    var byProv = {};
    coordless.forEach(function (a) {
      var p = (a.country || "Unknown") + (a.pref ? " · " + a.pref : "");
      (byProv[p] = byProv[p] || []).push(a);
    });
    var provs = Object.keys(byProv).sort(function (x, y) {
      return x.localeCompare(y, "zh-Hans-CN");
    });
    var h = "";
    provs.forEach(function (p) {
      var list = byProv[p];
      h += '<div class="cn-prov">' + esc(p) + ' <span class="n tabnum">' +
        list.length + "</span></div>";
      list.forEach(function (a) {
        /* The row itself opens the place panel; the link still opens Maps. */
        /* a.id is an integer today, but it arrives from the data file and this
           is the one attribute interpolation in the frontend that was not
           escaped; every other one either escapes or uses a local loop index. */
        h += '<div class="cn-item" id="cn-' + esc(a.id) + '" data-id="' + esc(a.id) +
          '" role="button" tabindex="0">' +
          '<div class="nm">' + esc(a.name) + "</div>" +
          '<div class="ad">' + esc(a.addr || "") + "</div>" +
          '<div class="gchips">' + a.games.map(function (g) {
            return '<span class="gc" style="--c:' +
              (C.GAME_COLOR[g] || C.GAME_COLOR.other) + '">' +
              esc(gameLabelFor(a, g)) + "</span>";
          }).join("") + "</div>" +
          '<a target="_blank" rel="noopener" href="' + esc(U.gmapsSearchUrl(a)) +
          '">Search in Google Maps</a></div>';
      });
    });
    box.innerHTML = h;

    function openRow(el) {
      var a = AM.data.byId[el.dataset.id];
      if (a) AM.state.set("selectedArcade", a.id, { source: "coordless-list" });
    }
    box.addEventListener("click", function (e) {
      if (e.target.closest("a")) return;
      var row = e.target.closest(".cn-item");
      if (row) openRow(row);
    });
    box.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      if (e.target.tagName === "A") return;
      var row = e.target.closest(".cn-item");
      if (row) { openRow(row); e.preventDefault(); }
    });
  }

  /* Open the drawer on the no-coords tab and flash the entry. Kept for any
     caller that wants the list row rather than the place panel. */
  function showCoordlessEntry(a) {
    closePlace();
    openDrawer();
    switchTab("china");
    var el = $("cn-" + a.id);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: C.REDUCED ? "auto" : "smooth" });
    document.querySelectorAll(".cn-item.flash").forEach(function (n) {
      n.classList.remove("flash");
    });
    el.classList.add("flash");
  }

  /* ---------- header count + footer ---------- */

  function syncCount() {
    $("meta-count").textContent = U.num(AM.state.get("shownCount")) + " shown";
  }

  function buildFooter() {
    var counts = AM.data.srcCounts;
    $("src-counts").innerHTML = AM.data.srcInData.map(function (s) {
      return "<span>" + esc(C.SRC_LABEL[s] || s) + " " + U.num(counts[s]) + "</span>";
    }).join("") +
      "<span>" + U.num(AM.data.arcades.length) + " stores total</span>";
  }

  /* ---------- tabs + drawer ---------- */

  function switchTab(which) {
    var fil = which === "filters";
    $("tab-filters").classList.toggle("active", fil);
    $("tab-filters").setAttribute("aria-selected", fil);
    $("tab-china").classList.toggle("active", !fil);
    $("tab-china").setAttribute("aria-selected", !fil);
    $("pane-filters").hidden = !fil;
    $("pane-china").hidden = fil;
  }

  function openDrawer() {
    if (!document.body.classList.contains("drawer-closed")) return;
    document.body.classList.remove("drawer-closed");
    $("drawer-toggle").setAttribute("aria-expanded", "true");
    AM.map.map.invalidateSize();
  }

  /* ---------- drawer width + drag-to-resize (desktop only) ----------

     The drawer and the place panel share one column, so both read a single
     --panel-w custom property and this is the only thing that writes it. On a
     phone the column is a full-width overlay and a bottom sheet, so a stored
     desktop width must not reach it: every path here is gated on the same
     min-width query the layout uses. */

  function isWide() {
    return !!(window.matchMedia && window.matchMedia("(min-width: 761px)").matches);
  }

  function clampWidth(px) {
    var max = Math.max(PANEL_MIN, Math.round(window.innerWidth * PANEL_MAX_VW));
    return Math.round(Math.min(max, Math.max(PANEL_MIN, px)));
  }

  function storedWidth() {
    var v = AM.state.readSetting(WIDTH_KEY, null);
    return (typeof v === "number" && isFinite(v) && v > 0) ? v : null;
  }

  /* Write the width to the document, or clear it so the stylesheet default
     applies again (mobile, and after a double-click reset). */
  function applyWidth(px) {
    var root = document.documentElement;
    if (px === null) root.style.removeProperty("--panel-w");
    else root.style.setProperty("--panel-w", clampWidth(px) + "px");
  }

  /* Re-run on resize: a stored 600px is legal on a 1600px screen and illegal
     on a 900px one, and the viewport can cross 760px without a reload. */
  function syncPanelWidth() {
    if (!isWide()) { applyWidth(null); return; }
    var w = storedWidth();
    applyWidth(w === null ? PANEL_W : w);
  }

  /* A grab strip on the column's right edge. Pointer events rather than mouse
     ones so a stylus or a tablet touch drags it too; the pointer is captured
     so a fast drag that outruns the 6px strip keeps tracking. */
  function buildResizer() {
    var grip = document.createElement("div");
    grip.id = "panel-grip";
    grip.className = "panel-grip";
    grip.setAttribute("role", "separator");
    grip.setAttribute("aria-orientation", "vertical");
    grip.setAttribute("aria-label", "Resize panel (double-click to reset)");
    grip.title = "Drag to resize - double-click to reset";
    $("layout").appendChild(grip);

    var dragging = false, startX = 0, startW = 0, raf = 0, latest = 0;

    /* Leaflet recomputes its size from the container, so it has to be told the
       column moved. Doing that per pointermove would relayout the map on every
       pixel, so live updates are coalesced to one per frame and the final,
       authoritative call happens once on release. */
    function pump() {
      raf = 0;
      applyWidth(latest);
      if (AM.map && AM.map.map) AM.map.map.invalidateSize({ pan: false });
    }

    function onMove(e) {
      if (!dragging) return;
      latest = startW + (e.clientX - startX);
      if (!raf) raf = requestAnimationFrame(pump);
      e.preventDefault();
    }

    function onUp() {
      if (!dragging) return;
      dragging = false;
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      document.body.classList.remove("resizing-panel");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      var final = clampWidth(latest);
      applyWidth(final);
      AM.state.writeSetting(WIDTH_KEY, final);
      if (AM.map && AM.map.map) AM.map.map.invalidateSize();
    }

    grip.addEventListener("pointerdown", function (e) {
      if (!isWide() || e.button > 0) return;
      dragging = true;
      startX = e.clientX;
      startW = $("panel").getBoundingClientRect().width;
      latest = startW;
      document.body.classList.add("resizing-panel");
      try { grip.setPointerCapture(e.pointerId); } catch (err) { /* older UA */ }
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
      e.preventDefault();
    });

    grip.addEventListener("dblclick", function () {
      if (!isWide()) return;
      applyWidth(PANEL_W);
      AM.state.writeSetting(WIDTH_KEY, PANEL_W);
      if (AM.map && AM.map.map) AM.map.map.invalidateSize();
    });

    /* Keyboard parity: the strip is focusable, so it must also be operable. */
    grip.tabIndex = 0;
    grip.addEventListener("keydown", function (e) {
      if (!isWide()) return;
      var step = e.shiftKey ? 40 : 12, w = $("panel").getBoundingClientRect().width;
      if (e.key === "ArrowLeft") w -= step;
      else if (e.key === "ArrowRight") w += step;
      else if (e.key === "Home") w = PANEL_W;
      else return;
      e.preventDefault();
      var next = clampWidth(w);
      applyWidth(next);
      AM.state.writeSetting(WIDTH_KEY, next);
      if (AM.map && AM.map.map) AM.map.map.invalidateSize();
    });
  }

  function buildShell() {
    $("tab-filters").addEventListener("click", function () { switchTab("filters"); });
    $("tab-china").addEventListener("click", function () { switchTab("china"); });
    $("drawer-toggle").addEventListener("click", function () {
      /* With the place panel up, the toggle means "back to whatever the panel
         is covering" - the same destination the panel's own back arrow uses. */
      if (isPlaceOpen()) { backToFilters(); return; }
      var closed = document.body.classList.toggle("drawer-closed");
      this.setAttribute("aria-expanded", closed ? "false" : "true");
      AM.map.map.invalidateSize();
    });
    if (window.matchMedia && window.matchMedia("(max-width: 760px)").matches) {
      document.body.classList.add("drawer-closed");
      $("drawer-toggle").setAttribute("aria-expanded", "false");
    }
  }

  /* ================= place panel ================= */

  var placeEl = null, bodyEl = null, toastEl = null;
  var closeTimer = null, toastTimer = null, current = null;

  function isMobile() {
    return !!(window.matchMedia && window.matchMedia("(max-width: 760px)").matches);
  }

  function canHover() {
    return !!(window.matchMedia && window.matchMedia("(hover: hover)").matches);
  }

  function isPlaceOpen() {
    return !!placeEl && !placeEl.hidden;
  }

  /* ---------- icons (stroked, 24px grid, currentColor) ---------- */

  var ICONS = {
    back: '<path d="M15 5l-7 7 7 7"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>',
    directions: '<path d="M3.5 11.2 20.5 3.5 13 20.5l-2-7.2z"/>',
    nearby: '<circle cx="12" cy="12" r="4.5"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/>',
    share: '<circle cx="17.5" cy="5.5" r="2.5"/><circle cx="6" cy="12" r="2.5"/>' +
      '<circle cx="17.5" cy="18.5" r="2.5"/><path d="M8.3 10.8 15.2 6.8M8.3 13.2l6.9 4"/>',
    link: '<path d="M14 4h6v6M20 4l-8.5 8.5M18 14.5V19a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4.5"/>',
    pin: '<path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    alert: '<path d="M12 3.8 20.7 19H3.3z"/><path d="M12 9.5v4M12 16.4h.01"/>',
    train: '<path d="M6.5 4h11v9.5a3 3 0 0 1-3 3h-5a3 3 0 0 1-3-3z"/>' +
      '<path d="M6.5 9.5h11M9.5 20.5l1.8-2.6M14.5 20.5l-1.8-2.6M9.5 13.2h.01M14.5 13.2h.01"/>',
    price: '<circle cx="12" cy="12" r="8.5"/><path d="M9 10.2h6M9 13h6M12 8.4v7.2"/>',
    layers: '<path d="M12 3.5 20.5 8 12 12.5 3.5 8z"/><path d="M3.5 13 12 17.5l8.5-4.5"/>',
    note: '<path d="M6 3.8h8l4.2 4.2v12H6z"/><path d="M14 3.8V8h4.2M9 12.5h6M9 16h4"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11.2v5M12 8.2h.01"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.2V12l3.2 1.9"/>',
    globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/>' +
      '<path d="M12 3.5c2.2 2.4 3.3 5.3 3.3 8.5S14.2 18.1 12 20.5c-2.2-2.4-3.3-5.3-3.3-8.5S9.8 5.9 12 3.5z"/>'
  };

  function ico(name) {
    return '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
      (ICONS[name] || "") + "</svg>";
  }

  /* ---------- content helpers ---------- */

  /* Canonical order first so the panel reads the same way as the filter chips,
     then anything the data carries that we have no canonical slot for. */
  function orderedGames(a) {
    var own = a.games || [];
    var out = C.GAME_ORDER.filter(function (g) { return own.indexOf(g) !== -1; });
    own.forEach(function (g) { if (out.indexOf(g) === -1) out.push(g); });
    return out;
  }

  /* Colour source for the header banner: the game the marker is drawn in,
     preferring anything more specific than the catch-all "other". */
  function dominantGame(a) {
    var order = orderedGames(a);
    var d = AM.markers && AM.markers.displayGame ? AM.markers.displayGame(a) : null;
    if (d && d !== "other") return d;
    for (var i = 0; i < order.length; i++) {
      if (order[i] !== "other") return order[i];
    }
    return d || order[0] || "other";
  }

  /* Enrichment is delivered later and under names we do not control yet, so
     every optional field is read through a tolerant lookup. */
  function firstField(a, names) {
    for (var i = 0; i < names.length; i++) {
      var v = a[names[i]];
      if (typeof v === "string" && v.trim()) return v.trim();
    }
    return null;
  }

  /* Enrichment may deliver a photo as an absolute URL, an inline data URI or a
     path relative to the site. All three are fine; anything carrying some
     other scheme (javascript:, blob:, ...) is dropped rather than fed to an
     <img>, which would at best be a console error and at worst a hazard. */
  function photoUrl(a) {
    var v = firstField(a, ["image_thumb", "image", "photo", "photo_url"]);
    if (!v && Array.isArray(a.images) && typeof a.images[0] === "string") v = a.images[0];
    if (!v) return null;
    if (/^https?:\/\//i.test(v)) return v;
    if (/^data:image\//i.test(v)) return v;
    /* No scheme at all: a same-origin relative path. */
    if (!/^[a-z][a-z0-9+.-]*:/i.test(v)) return v;
    return null;
  }

  /* ================= enrichment (lazy, one fetch each) =================

     data/enrichment.json is 3.4 MB and only the place panel ever needs it, so
     nothing is fetched until the first panel opens. The panel renders straight
     away from whatever is already cached and re-renders once when a fetch
     lands - never blocking the open on a megabyte of JSON.

     Every field below is optional in the schema and several are not populated
     by the pipeline yet, so each is read through a tolerant lookup rather than
     assumed present. */

  var ENRICH_URL = "data/enrichment.json";
  var CABS_URL = "assets/cabs/manifest.json";

  var enrich = null;        /* the parsed file, or {} once a fetch failed */
  var cabs = null;          /* the parsed cab manifest, or {} */
  var dataVersion = 0;      /* bumped whenever a lazy fetch lands */
  var enrichPromise = null, cabsPromise = null, fxPromise = null;

  function fetchJson(url) {
    return new Promise(function (resolve) {
      if (typeof fetch !== "function") { resolve(null); return; }
      /* Revalidate rather than trust the cache: enrichment and the cab
         manifest are both rewritten by the weekly Action. See app-init.js. */
      fetch(url, { cache: "no-cache" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(resolve)
        .catch(function () { resolve(null); });
    });
  }

  function ensureEnrichment() {
    if (!enrichPromise) {
      enrichPromise = fetchJson(ENRICH_URL).then(function (blob) {
        enrich = (blob && typeof blob === "object") ? blob : {};
        dataVersion++;
        return enrich;
      });
    }
    return enrichPromise;
  }

  function ensureCabs() {
    if (!cabsPromise) {
      cabsPromise = fetchJson(CABS_URL).then(function (blob) {
        cabs = (blob && typeof blob === "object") ? blob : {};
        dataVersion++;
        return cabs;
      });
    }
    return cabsPromise;
  }

  /* FX only matters once a price has actually been parsed, but the fetch is
     tiny and starting it with the others keeps the panel to a single re-render
     rather than one per arriving file. */
  function ensureFx() {
    if (!fxPromise) {
      fxPromise = (AM.format && AM.format.ensureFxRates
        ? AM.format.ensureFxRates()
        : Promise.resolve(null)).then(function (r) { dataVersion++; return r; });
    }
    return fxPromise;
  }

  function ensureEnrichData() {
    return Promise.all([ensureEnrichment(), ensureCabs(), ensureFx()]);
  }

  /* The enrichment entry for a store, or null. Keys are strings in the file
     and ids are numbers in the data, so the lookup is done on both. */
  function enrichOf(a) {
    if (!enrich || !a || !enrich.arcades) return null;
    var e = enrich.arcades[a.id];
    if (!e && a.id !== undefined) e = enrich.arcades[String(a.id)];
    return (e && typeof e === "object") ? e : null;
  }

  /* Merged view of the two places a field can live: the arcade row itself
     (already downloaded) wins, the enrichment file fills the gaps. */
  function field(a, e, names) {
    var v = firstField(a, names);
    if (v) return v;
    return e ? firstField(e, names) : null;
  }

  function enrichedAt(a, e) {
    return field(a, e, ["enriched_at", "scraped_at", "updated"]);
  }

  /* ---------- cab photos ---------- */

  /* The first of this store's games that the manifest actually has a file for.
     Entries exist for games with no acceptably-licensed photo (file: null), so
     presence of a key is not presence of an image. */
  /* A stock photo of a cabinet the store has. The manifest is keyed by GAME,
     which is only safe while the game implies the machine - and for maimai it
     does not: the DX photo over a store that only has a pre-DX cabinet shows a
     machine that is not there, captioned as if it were. Games whose cabinet
     this store contradicts are skipped, and the next game's photo is used. */
  function photoWrongFor(a, g) {
    if (g !== "maimai_dx") return false;
    var have = U.variantsOf(a);
    return !!(have.maimai_classic && !have.maimai_dx_cab);
  }

  function cabPhoto(a) {
    if (!cabs) return null;
    var order = orderedGames(a);
    for (var i = 0; i < order.length; i++) {
      if (photoWrongFor(a, order[i])) continue;
      var m = cabs[order[i]];
      if (m && typeof m.file === "string" && m.file) {
        return {
          game: order[i],
          url: "assets/cabs/" + m.file,
          author: m.author || null,
          license: m.license || null,
          source: m.source_url || null
        };
      }
    }
    return null;
  }

  /* ---------- price ---------- */

  /* Scraped price strings name their currency with anything from an ISO code
     to a bare glyph, so the tokens are matched longest-first and a token that
     does not identify ONE currency is never guessed at. A lone "$" is ten
     currencies and a lone yen sign is two (JPY and CNY both use it), so those
     resolve only against the store's own country and are dropped without one -
     a wrong conversion is worse than no conversion. */
  /* Glyphs are written as \u escapes for the same reason format.js does it:
     this file is served as UTF-8, but any tool that reads it as ANSI would
     corrupt a literal yen sign, and a corrupted currency token silently
     mis-prices a store rather than failing loudly. */
  var YEN = "\u00A5", YEN_W = "\uFFE5";   /* yen/yuan sign, full-width form */

  var CUR_TOKENS = [
    ["CN" + YEN, "CNY"], ["CN" + YEN_W, "CNY"],
    ["JP" + YEN, "JPY"], ["JP" + YEN_W, "JPY"],
    ["US$", "USD"], ["HKD$", "HKD"], ["HK$", "HKD"], ["NT$", "TWD"], ["AUD$", "AUD"],
    ["A$", "AUD"], ["CA$", "CAD"], ["S$", "SGD"], ["MOP$", "MOP"], ["MX$", "MXN"],
    ["R$", "BRL"], ["Rp.", "IDR"], ["Rp", "IDR"], ["RM", "MYR"],
    ["USD", "USD"], ["JPY", "JPY"], ["CNY", "CNY"], ["HKD", "HKD"], ["TWD", "TWD"],
    ["KRW", "KRW"], ["PHP", "PHP"], ["Php", "PHP"], ["THB", "THB"], ["IDR", "IDR"],
    ["VND", "VND"], ["SGD", "SGD"], ["MYR", "MYR"], ["AUD", "AUD"], ["NZD", "NZD"],
    ["GBP", "GBP"], ["EUR", "EUR"], ["CAD", "CAD"],
    ["\u20A9", "KRW"], ["\uFFE6", "KRW"],   /* won, full-width won */
    ["\u00A3", "GBP"], ["\u20AC", "EUR"],   /* pound, euro */
    ["\u20B1", "PHP"], ["\u0E3F", "THB"],   /* peso, baht */
    ["\u20AB", "VND"], ["\u0111", "VND"]    /* dong sign, dong letter */
  ];

  var CUR_CODE = {}, CUR_RE = null;
  var BARE_RE = new RegExp(
    "(?:^|[^A-Za-z$])([$" + YEN + YEN_W + "])\\s*([0-9][0-9,.]*)");

  function curRe() {
    if (CUR_RE) return CUR_RE;
    var toks = CUR_TOKENS.slice().sort(function (x, y) {
      return y[0].length - x[0].length;
    });
    var alts = toks.map(function (t) {
      CUR_CODE[t[0]] = t[1];
      return t[0].replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    });
    CUR_RE = new RegExp("(" + alts.join("|") + ")\\s*([0-9][0-9,. ]*[0-9]|[0-9])", "g");
    return CUR_RE;
  }

  var ZERO_DEC = { JPY: 1, KRW: 1, VND: 1, IDR: 1 };

  /* "1,320.00" -> 1320, "6,90" -> 6.9 (decimal comma), "15.000" VND -> 15000
     (thousands dot in a currency that has no minor unit). */
  function toAmount(raw, code) {
    var s = String(raw).trim().replace(/[\s]/g, "").replace(/[.,]+$/, "");
    if (/,\d{1,2}$/.test(s) && s.indexOf(".") === -1) s = s.replace(",", ".");
    else s = s.replace(/,/g, "");
    if (ZERO_DEC[code] && /\.\d{3}$/.test(s)) s = s.replace(/\./g, "");
    var v = parseFloat(s);
    return (isFinite(v) && v > 0) ? v : null;
  }

  /* The currency this store most likely prices in, from the enrichment file's
     own country table. Used to resolve an ambiguous glyph, never to invent a
     currency for a price that named one. */
  function localCurrency(a) {
    if (!enrich || !a || !a.country) return null;
    var iso = (enrich.country_to_code || {})[a.country];
    var def = iso && (enrich.price_defaults || {})[iso];
    return (def && typeof def.currency === "string") ? def.currency : null;
  }

  function parsePrice(text, local) {
    if (typeof text !== "string" || !text) return null;
    var re = curRe();
    re.lastIndex = 0;
    var hits = [], m;
    while ((m = re.exec(text)) !== null) {
      var code = CUR_CODE[m[1]];
      if (code) hits.push([code, m[2]]);
    }
    /* A price in the store's own currency beats an aside quoting another. */
    var i;
    if (local) {
      for (i = 0; i < hits.length; i++) {
        if (hits[i][0] === local) {
          var v = toAmount(hits[i][1], local);
          if (v) return { amount: v, currency: local };
        }
      }
    }
    var bare = BARE_RE.exec(text);
    if (bare) {
      if (!local) return null;      /* ambiguous glyph, no country: refuse */
      var bv = toAmount(bare[2], local);
      return bv ? { amount: bv, currency: local } : null;
    }
    for (i = 0; i < hits.length; i++) {
      var av = toAmount(hits[i][1], hits[i][0]);
      if (av) return { amount: av, currency: hits[i][0] };
    }
    return null;
  }

  /* {slug: "JPY 100 for 3 songs"} from either source, canonical order. */
  function perGamePrices(a, e) {
    var src = (e && (e.machine_prices || e.game_prices)) ||
      a.machine_prices || a.game_prices;
    if (!src || typeof src !== "object") return [];
    var out = [], seen = {};
    function push(g) {
      var t = src[g];
      if (seen[g] || typeof t !== "string" || !t.trim()) return;
      seen[g] = true;
      out.push({ game: g, text: t.trim() });
    }
    orderedGames(a).forEach(push);
    Object.keys(src).forEach(push);
    return out;
  }

  /* The store's own headline price, in priority order:
       1. an explicit venue price field (BemaniCN price_text)
       2. the most common amount across its per-game prices - real data from
          this store, so it is labelled as derived rather than quoted
     Returns null when nothing parses; the country default is a separate row
     and is never mixed in here. */
  function venuePrice(a, e) {
    var local = localCurrency(a);
    var explicit = field(a, e, ["price_text", "price", "venue_price"]);
    if (explicit) {
      var p = parsePrice(explicit, local);
      if (p) { p.text = explicit; p.derived = false; return p; }
      return { text: explicit, derived: false };
    }
    var rows = perGamePrices(a, e);
    if (!rows.length) return null;
    var tally = {}, best = null, bestN = 0;
    rows.forEach(function (r) {
      var q = parsePrice(r.text, local);
      if (!q) return;
      var k = q.currency + " " + q.amount;
      tally[k] = (tally[k] || 0) + 1;
      if (tally[k] > bestN) { bestN = tally[k]; best = q; }
    });
    if (!best) return null;
    best.derived = true;
    best.games = rows.length;
    return best;
  }

  /* The country-level "typical" figure the enrichment file ships. Always a
     display fallback and always labelled as typical - never quoted as this
     store's price. */
  function typicalPrice(a) {
    if (!enrich || !a || !a.country) return null;
    var iso = (enrich.country_to_code || {})[a.country];
    var def = iso && (enrich.price_defaults || {})[iso];
    if (!def || typeof def.display !== "string") return null;
    return { display: def.display, notes: def.notes || null, as_of: def.as_of || null };
  }

  function directionsUrl(a) {
    if (a.links && a.links.gmaps) return a.links.gmaps;
    if (U.hasCoords(a)) {
      return "https://www.google.com/maps/search/?api=1&query=" +
        encodeURIComponent(a.lat + "," + a.lng);
    }
    return U.gmapsSearchUrl(a);
  }

  function sourcePage(a) {
    if (!a.links) return null;
    if (a.links.ziv) return { url: a.links.ziv, label: C.SRC_LABEL.ziv || "ZIv" };
    if (a.links.bemanicn) {
      return { url: a.links.bemanicn, label: C.SRC_LABEL.bemanicn || "BemaniCN" };
    }
    return null;
  }

  /* The id rides in a "/"-delimited hash, so anything in it that could be read
     as a separator (or as a percent escape on the way back in) has to be
     escaped on the way out. encodeURIComponent leaves the ASCII ids this data
     uses untouched and makes the round trip total for anything else. */
  function shareUrl(a) {
    var base = location.href.split("#")[0];
    var raw = location.hash.replace(/^#/, "");
    var segs = raw ? raw.split("/").filter(function (s) {
      return s && s.indexOf("arcade=") !== 0;
    }) : [];
    segs.push("arcade=" + encodeURIComponent(a.id));
    return base + "#" + segs.join("/");
  }

  /* Drop the arcade= segment from the URL without touching the rest of it.
     mapcore.js owns the hash format, so the segment list is filtered rather
     than rebuilt, and replaceState is used so this does not fire hashchange
     and re-enter applyHashArcade. */
  function scrubHashArcade() {
    var raw = location.hash.replace(/^#/, "");
    if (!raw || raw.indexOf("arcade=") === -1) return;
    var segs = raw.split("/").filter(function (s) {
      return s && s.indexOf("arcade=") !== 0;
    });
    var next = segs.length ? "#" + segs.join("/") : location.pathname + location.search;
    try { history.replaceState(null, "", next); } catch (e) { /* file:// */ }
  }

  /* ---------- rendering ---------- */

  /* Media header, best available of three:
       1. a photo of THIS store, from enrichment
       2. a photo of a cabinet it has, from assets/cabs - a stock shot of the
          machine, not of the venue, so it says so on its face and carries the
          licence line its CC terms require
       3. the game-tinted gradient banner
     Only the chosen one is requested, and only when the panel opens, so a
     session that never opens a store downloads no images at all. */
  function heroHtml(a) {
    var g = dominantGame(a);
    var color = C.GAME_COLOR[g] || C.GAME_COLOR.other;

    var own = photoUrl(a) || photoUrl(enrichOf(a) || {});
    if (own) {
      return '<div class="pl-hero has-photo" style="--c:' + color + '">' +
        '<img class="pl-hero-img" src="' + esc(own) + '" alt="" ' +
        'loading="lazy" decoding="async" data-hero="own">' +
        '<div class="pl-hero-veil"></div></div>';
    }

    var cab = cabPhoto(a);
    if (cab) {
      /* CC BY and BY-SA both require author + licence next to the work. CC0
         does not, but the same line is rendered for it anyway: one code path
         is harder to get wrong than two, and crediting is never wrong. */
      var credit = "";
      if (cab.author || cab.license) {
        var txt = "photo: " + (cab.author || "unknown") +
          (cab.license ? " / " + cab.license : "");
        credit = cab.source
          ? '<a class="pl-hero-credit" href="' + esc(U.safeUrl(cab.source)) +
            '" target="_blank" rel="noopener">' + esc(txt) + "</a>"
          : '<span class="pl-hero-credit">' + esc(txt) + "</span>";
      }
      return '<div class="pl-hero has-photo is-cab" style="--c:' + color + '">' +
        '<img class="pl-hero-img" src="' + esc(cab.url) + '" alt="" ' +
        'loading="lazy" decoding="async" data-hero="cab">' +
        '<div class="pl-hero-veil"></div>' +
        '<div class="pl-hero-foot">' +
        '<span class="pl-hero-kind">' +
        esc(gameLabelFor(a, cab.game)) + " cabinet</span>" +
        credit + "</div></div>";
    }

    return '<div class="pl-hero" style="--c:' + color + '">' +
      '<div class="pl-hero-art"></div>' +
      '<div class="pl-hero-tag">' + esc(gameLabelFor(a, g)) + "</div></div>";
  }

  /* How much a cab count can be trusted, from the data itself.

     A number on a chip reads as fact, so it only gets to look like one when
     the source stands behind it. counts_src records which listing the count
     came from: BemaniCN publishes per-title quantities and is quoted plainly;
     ZIv counts what community members have listed, which floors rather than
     totals, so it is qualified with "listed". A count with no recorded source
     is shown bare (it is real data - most of this file's counts predate the
     field) and a store with no counts at all gets a plain chip plus a row
     saying so, rather than a silence a reader would fill in as "one cab". */
  function countsSrc(a) {
    var v = a && (a.counts_src || a.count_src || a.counts_source);
    return typeof v === "string" ? v : null;
  }

  function hasCounts(a) {
    if (!a || !a.game_counts) return false;
    for (var k in a.game_counts) {
      if (Object.prototype.hasOwnProperty.call(a.game_counts, k) &&
          typeof a.game_counts[k] === "number" && isFinite(a.game_counts[k])) return true;
    }
    return false;
  }

  /* One game chip, plus whatever the data actually knows about the CABINET.

     Three rules, and they are the whole point of this section:

     1. A chip must never name a machine the store does not have. A store whose
        only maimai is a FiNALE cab said "maimai DX" until now - 226 stores
        advertising a game that has been impossible to play online since 2020.
        When the only known variant REPLACES the game (maimai classic), the
        chip is renamed rather than badged, so the chip itself stops lying.

     2. Additive variants (Lightning, Valkyrie, gold cab) get a pill next to
        their game chip, not a free-floating badge at the end of the row. A row
        of five yellow pills with no attachment to a game is unreadable on a
        phone, and it is the game they qualify that makes them mean anything.

     3. A count only appears when a source published one. `cab_models` carries
        real per-variant quantities when the scrape provides them; ZIv titles
        do not, and inventing "x1" from the presence of a title would be the
        same fabrication the counts-honesty rule exists to stop. */
  function variantPillsHtml(a, g) {
    var vs = U.variantsForGame(a, g);
    var h = "";
    /* When the chip has already been RENAMED to the variant, the pill would
       just repeat it - "maimai (FiNALE / pre-DX)" followed by a "FiNALE /
       pre-DX" badge. The badge exists to add a cabinet to a game name, so it
       is dropped when it is the game name. */
    var renamed = gameLabelFor(a, g) !== (C.GAME_LABEL[g] || g);
    vs.forEach(function (v) {
      if (v.def.chipOnly || !v.def.badge) return;
      if (renamed && v.def.offline) return;
      var n = (v.ev && typeof v.ev.n === "number" && v.ev.n > 0) ? v.ev.n : null;
      var cnt = n !== null ? ' <b class="tabnum">x' + n + "</b>" : "";
      h += '<span class="badge cab' + (v.def.offline ? " dead" : "") + '"' +
        (v.def.note ? ' title="' + esc(v.def.note) + '"' : "") + ">" +
        esc(v.def.badge) + cnt + "</span>";
    });
    return h;
  }

  /* The game's name at THIS store - see AM.util.gameLabelFor, which owns the
     rule so the map popup and the nearby list tell the same story. Declared as
     a function, not `var f = U.gameLabelFor`, because callers appear earlier in
     this file than this line and only a declaration is hoisted. */
  function gameLabelFor(a, g) { return U.gameLabelFor(a, g); }

  function chipsHtml(a) {
    var h = "";
    var src = countsSrc(a);
    var qualify = src === "ziv";
    orderedGames(a).forEach(function (g) {
      var n = U.gameCount(a, g);
      var cnt = "";
      if (n !== null) {
        cnt = ' <b class="cnt tabnum">x' + n + "</b>" +
          (qualify ? ' <i class="cnt-q">listed</i>' : "");
      }
      /* The grey "Other" chip covers 7,491 stores and names nothing. Pump It
         Up alone sits in 1,481 of them. The merge has no slug for these yet,
         but the titles are right there in the listing, so the chip says what
         it is instead of being a black box. */
      var label = gameLabelFor(a, g);
      if (g === "other") {
        var og = U.otherGamesOf(a);
        if (og.length) {
          label = og.slice(0, 3).map(function (x) { return x.label; }).join(", ") +
            (og.length > 3 ? " +" + (og.length - 3) : "");
        }
      }
      h += '<span class="gc" style="--c:' + (C.GAME_COLOR[g] || C.GAME_COLOR.other) + '">' +
        esc(label) + cnt + "</span>" + variantPillsHtml(a, g);
    });
    return h ? '<div class="pl-chips">' + h + "</div>" : "";
  }

  function actionsHtml(a) {
    var h = '<div class="pl-acts">';
    /* directionsUrl can hand back a.links.gmaps, which is a scraped value.
       esc() is no defence against "javascript:..." - it contains none of the
       characters esc escapes - so the scheme is checked, not just the markup. */
    h += '<a class="act" href="' + esc(U.safeUrl(directionsUrl(a))) + '" target="_blank" rel="noopener">' +
      '<span class="act-ico">' + ico("directions") + '</span>' +
      '<span class="act-lb">Directions</span></a>';
    if (U.hasCoords(a)) {
      h += '<button type="button" class="act" data-act="nearby">' +
        '<span class="act-ico">' + ico("nearby") + '</span>' +
        '<span class="act-lb">Nearby</span></button>';
    }
    h += '<button type="button" class="act" data-act="share">' +
      '<span class="act-ico">' + ico("share") + '</span>' +
      '<span class="act-lb">Share</span></button>';
    var sp = sourcePage(a);
    if (sp) {
      h += '<a class="act" href="' + esc(U.safeUrl(sp.url)) + '" target="_blank" rel="noopener">' +
        '<span class="act-ico">' + ico("link") + '</span>' +
        '<span class="act-lb">' + esc(sp.label) + "</span></a>";
    }
    return h + "</div>";
  }

  function row(icon, valueHtml, captionHtml, cls) {
    return '<div class="pl-row' + (cls ? " " + cls : "") + '">' +
      '<span class="ri">' + ico(icon) + "</span>" +
      '<span class="rt"><span class="rv">' + valueHtml + "</span>" +
      (captionHtml ? '<span class="rc">' + captionHtml + "</span>" : "") +
      "</span></div>";
  }

  /* "community data from BemaniCN, may be outdated (2026-07-28)" - the
     provenance line that has to sit under anything scraped from a community
     map. `sources` in the enrichment file records which listing each field
     came from, so the name in the caption is the real one. */
  function communityCaption(a, e, fieldName) {
    var who = e && e.sources && e.sources[fieldName];
    var label = who ? (C.SRC_LABEL[who] || who) : "community listings";
    var when = enrichedAt(a, e);
    return "community data from " + esc(label) + ", may be outdated" +
      (when ? " (" + esc(when) + ")" : "");
  }

  function priceRowsHtml(a, e) {
    var h = "";
    var vp = venuePrice(a, e);
    var fx = AM.format && AM.format.getFxRates ? AM.format.getFxRates() : null;

    if (vp && vp.amount) {
      /* fmtPrice returns the local amount alone whenever the table cannot
         convert it, so a missing or partial fx file never shows a wrong
         number - it just shows fewer. */
      var line = AM.format.fmtPrice(vp.amount, vp.currency, fx);
      var cap = vp.derived
        ? "Most common price across " + vp.games + " listed machine" +
          (vp.games === 1 ? "" : "s") + " here. " + communityCaption(a, e, "machine_prices")
        : communityCaption(a, e, "price_text");
      h += row("price", esc(line), cap);
    } else if (vp && vp.text) {
      h += row("price", esc(vp.text), communityCaption(a, e, "price_text"));
    }

    var per = perGamePrices(a, e);
    if (per.length) {
      var items = per.map(function (r) {
        var g = r.game;
        return '<li><span class="pp-g gc" style="--c:' +
          (C.GAME_COLOR[g] || C.GAME_COLOR.other) + '">' +
          esc(gameLabelFor(a, g)) + "</span>" +
          '<span class="pp-v">' + esc(r.text) + "</span></li>";
      }).join("");
      h += row("layers", '<ul class="pl-prices">' + items + "</ul>",
        "Per machine, as listed. " + communityCaption(a, e, "machine_prices"));
    }

    /* Only when the store itself says nothing: a country typical is context,
       not a quote, and must never stand in for a real price. */
    if (!vp && !per.length) {
      var tp = typicalPrice(a);
      if (tp) {
        h += row("price", esc(tp.display),
          "Typical for " + esc(a.country) + " - not this store's own price" +
          (tp.as_of ? " (" + esc(tp.as_of) + ")" : ""), "muted");
      }
    }
    return h;
  }

  /* Cabinet rows: what the variant pills cannot say in two words.

     The offline warning is the one that matters. A maimai FiNALE or a CRT-era
     DDR is a machine you can stand in front of and play, and which will not
     save a single score - every one of those networks is dead. Showing it with
     the same weight as a live cab is how someone ends up driving across a city
     for nothing, so it gets a warning row of its own and names the cabinet.

     The second row is a limit, not a feature. Cab flags from e-amusement only
     ever cover Japan, so "no Lightning badge" outside Japan means "nobody
     published a cabinet model", never "standard cab". Saying so where a reader
     would otherwise infer the negative is the whole three-state requirement. */
  function cabinetRowsHtml(a) {
    var have = U.variantsOf(a);
    var h = "", dead = [], known = false, k;
    for (k in have) {
      if (!Object.prototype.hasOwnProperty.call(have, k)) continue;
      known = true;
      var def = C.VARIANT_BY_ID[k];
      if (def && def.offline) dead.push(def.label);
    }
    if (dead.length) {
      h += row("alert", esc(dead.join(", ")) + " - offline cabinet" +
        (dead.length > 1 ? "s" : ""),
        "This cabinet's network has shut down. It can still be played, but "
        + "nothing is saved: no score history, no online play, no unlocks.",
        "warn");
    }
    /* Only worth saying where a cabinet variant actually exists to be missed,
       and only when nothing is known about this store's. */
    if (!known) {
      var couldVary = (a.games || []).some(function (g) {
        return (C.VARIANTS_BY_GAME[g] || []).length > 0;
      });
      if (couldVary) {
        h += row("info", "Cabinet model not published",
          "No listing says which cabinet this store runs. Official cab data "
          + "covers Japan only, and community listings record the model just "
          + "when someone noted it - so this is \"unknown\", not \"standard\".",
          "muted");
      }
    }
    return h;
  }

  function rowsHtml(a) {
    var e = enrichOf(a);
    var h = '<div class="pl-rows">';

    if (a.addr) {
      h += '<button type="button" class="pl-row pl-row-btn" data-act="copy-addr">' +
        '<span class="ri">' + ico("pin") + "</span>" +
        '<span class="rt"><span class="rv">' + esc(a.addr) + "</span>" +
        '<span class="rc">Tap to copy</span></span></button>';
    }

    if (!U.hasCoords(a)) {
      h += row("info", "No map position for this store",
        "Published as an address only. Use Directions to search it.", "muted");
    } else if (a.approx) {
      /* Name the level the merge actually reached. "City level" was printed for
         every approximate pin even after most of them moved to their district,
         which understates a 10 km improvement and, worse, reads as a promise
         the district-level pins do not need to make. An address- or
         street-level pin came from geocoding the published address, so it is
         about the building: still derived, no longer a guess at an area. */
      var APPROX_TEXT = {
        address: ["Position from the address",
          "The source publishes no coordinates, so this pin was geocoded from "
          + "the printed address."],
        street: ["Position from the address - street level",
          "Geocoded to the road rather than the building, so expect to be a "
          + "door or two out."],
        district: ["Position approximate - district level",
          "The source publishes no coordinates, so this pin is the centre of "
          + "the district named in the address, not the store."],
        city: ["Position approximate - city level",
          "The source publishes no coordinates and the address names no "
          + "district, so this pin is the centre of the city."]
      };
      var t = APPROX_TEXT[a.approx_level] || APPROX_TEXT.city;
      h += row("alert", t[0], t[1], "warn");
    }

    var transit = field(a, e, ["transport", "transit", "access"]);
    if (transit) {
      h += row("train", esc(transit), communityCaption(a, e, "transport"));
    }

    var hours = field(a, e, ["hours_text", "hours", "opening_hours"]);
    if (hours) {
      h += row("clock", esc(hours), communityCaption(a, e, "hours_text"));
    }

    h += priceRowsHtml(a, e);

    /* A count of zero cabs is never printed as a fact, so when nothing counted
       this store the panel says who did not, rather than leaving a reader to
       infer a number from the absence of one.

       Two different absences, and conflating them was wrong: counts_src null
       means a source DID list this store's machines and the merge declined to
       read that list as a census, which reads as a flat lie next to the "Cabs:"
       line printing those very machines. Say which one it is and point at the
       list. */
    if (!hasCounts(a)) {
      if (a.counts_src === null) {
        h += row("info", "Machine list, but no cab counts",
          "The community listing names the machines below without saying how "
          + "many of each, so the list is a floor and not a tally.", "muted");
      } else {
        h += row("info", "Cab counts unavailable",
          "The listings this store comes from do not publish how many machines it has.",
          "muted");
      }
    }

    h += cabinetRowsHtml(a);

    var site = field(a, e, ["website", "url", "homepage"]);
    if (site && /^https?:\/\//i.test(site)) {
      h += row("globe", '<a href="' + esc(site) + '" target="_blank" rel="noopener">' +
        esc(site.replace(/^https?:\/\//i, "").replace(/\/$/, "")) + "</a>",
        communityCaption(a, e, "website"));
    }

    if (a.src && a.src.length) {
      var badges = a.src.map(function (s) {
        var label = esc(C.SRC_LABEL[s] || s);
        if ((s === "ziv" || s === "bemanicn") && a.links && a.links[s]) {
          return '<a class="badge" target="_blank" rel="noopener" href="' +
            esc(U.safeUrl(a.links[s])) + '">' + label + "</a>";
        }
        return '<span class="badge">' + label + "</span>";
      }).join("");
      h += row("layers", '<span class="rbadges">' + badges + "</span>", "Listed by");
    }

    /* Notes are the one unbounded field: a ZIv cab dump runs to hundreds of
       characters and would push everything else off screen. Short ones show
       whole; long ones clamp to a few lines behind a native disclosure. */
    var notes = a.notes;
    var info = e && typeof e.info_text === "string" ? e.info_text.trim() : "";
    if (info && (!notes || notes.indexOf(info) === -1)) {
      notes = notes ? notes + " / " + info : info;
    }
    if (notes) {
      var n = esc(notes);
      if (notes.length <= 150) {
        h += row("note", n, null, "notes");
      } else {
        /* One copy of the text, inside the summary: CSS clamps it while the
           details is closed and unclamps it when open, so there is nothing to
           keep in sync and the toggle label always sits under the text. */
        h += '<div class="pl-row notes">' +
          '<span class="ri">' + ico("note") + "</span>" +
          '<span class="rt"><details class="pl-more"><summary>' +
          '<span class="rv clamp">' + n + "</span>" +
          '<span class="pl-more-lb"></span>' +
          "</summary></details></span></div>";
      }
    }

    return h + "</div>";
  }

  var renderedVersion = -1;

  function renderPlace(a, keepScroll) {
    var sub = [a.pref, a.country].filter(Boolean).join(" · ");
    bodyEl.innerHTML = heroHtml(a) +
      '<div class="pl-head"><h2 class="pl-name">' + esc(a.name) + "</h2>" +
      (sub ? '<div class="pl-sub">' + esc(sub) + "</div>" : "") + "</div>" +
      chipsHtml(a) + actionsHtml(a) + rowsHtml(a);
    renderedVersion = dataVersion;
    if (!keepScroll) bodyEl.scrollTop = 0;
  }

  /* The enrichment file is megabytes and the panel must not wait for it, so
     the first open paints from whatever is cached and this re-paints once the
     fetches land. current.id is re-checked because the reader may already have
     moved to another store by then, and the scroll position is preserved so a
     late arrival never yanks the page out from under them. */
  function refreshWhenEnriched(a) {
    ensureEnrichData().then(function () {
      if (!current || current.id !== a.id || !isPlaceOpen()) return;
      if (renderedVersion === dataVersion) return;
      var top = bodyEl.scrollTop;
      renderPlace(current, true);
      bodyEl.scrollTop = top;
      fitSheet();
    });
  }

  /* ---------- open / close ---------- */

  /* The whole point of the resting height is that the action row is reachable
     without a drag, and the content above it is not a fixed height: a photo
     header, a long wrapped name and a chip row all vary. So the sheet is sized
     to fit the actions rather than pinned to a guessed fraction - clamped so
     it never shrinks below the 45% design height or grows past the full one. */
  function fitSheet() {
    if (!isMobile()) return;
    /* An expanded sheet is pinned to a pixel height computed from the OLD
       viewport, so a rotate or a browser-chrome collapse leaves it the wrong
       size (and on a shrink, taller than the screen). Re-pin it rather than
       return: the expanded state is still what the user asked for. */
    if (placeEl.classList.contains("expanded")) {
      placeEl.style.setProperty("--sh", sheetPx(SHEET_FULL) + "px");
      return;
    }
    var acts = bodyEl.querySelector(".pl-acts");
    if (!acts) return;
    var peek = sheetPx(SHEET_PEEK), full = sheetPx(SHEET_FULL);

    /* The sheet's height is a CSS transition, so the OUTER box is still the
       old size for ~190ms after anything changes it. Measuring against that
       box reported "the actions already fit" on a viewport shrink and the
       function returned having set nothing - leaving the sheet at the 45%
       default with the action row 91px below the fold, which is the exact
       thing it exists to prevent.

       So the measurement is taken inside the scroll body instead: how far the
       action row sits from the top of the scrolled CONTENT, plus the fixed
       chrome above it. Neither depends on the animating outer height, so this
       reads the same mid-transition as it does at rest. */
    var chrome = placeEl.clientHeight - bodyEl.clientHeight;
    var contentBottom = acts.getBoundingClientRect().bottom -
      bodyEl.getBoundingClientRect().top + bodyEl.scrollTop;
    var need = Math.round(chrome + contentBottom + 10);

    if (need <= peek) placeEl.style.removeProperty("--sh");
    else placeEl.style.setProperty("--sh", Math.min(full, need) + "px");
  }

  /* fitSheet measures against the viewport, so its answer expires the moment
     the viewport changes - a rotate, a keyboard opening, or the mobile browser
     chrome collapsing on scroll. Without this the sheet keeps a height sized
     for the old screen and the action row it exists to protect ends up under
     the fold. One listener for the life of the page, guarded on the panel
     being open; debounced because a rotate fires a burst of resize events and
     each one costs a layout read. */
  var fitTimer = null;

  function onViewportChange() {
    clearTimeout(fitTimer);
    fitTimer = setTimeout(function () {
      if (isPlaceOpen()) fitSheet();
      syncPanelWidth();
    }, 120);
  }

  function openPlace(a, meta) {
    current = a;
    clearTimeout(closeTimer);
    renderPlace(a);
    hideToast();
    var wasOpen = isPlaceOpen();
    if (!wasOpen) {
      placeEl.style.removeProperty("--sh");
      placeEl.classList.remove("expanded");
      placeEl.hidden = false;
      document.body.classList.add("place-open");
      if (C.REDUCED) placeEl.classList.add("on");
      else requestAnimationFrame(function () { placeEl.classList.add("on"); });
      /* Move focus into the panel only when the user asked for it. A panel
         opened by the URL on load must leave focus alone: the reader has not
         interacted yet, tab order should still start at the top of the page,
         and stealing focus mid-load also races other modules' autofocus. */
      if (!meta || meta.source !== "hash") $("pl-back").focus({ preventScroll: true });
    }
    syncBackLabel();
    fitSheet();
    keepInView(a, meta);
    refreshWhenEnriched(a);
  }

  function closePlace() {
    if (!placeEl || placeEl.hidden) return;
    current = null;
    placeEl.classList.remove("on");
    document.body.classList.remove("place-open");
    hideToast();
    var finish = function () { placeEl.hidden = true; };
    if (C.REDUCED) finish();
    else { clearTimeout(closeTimer); closeTimer = setTimeout(finish, ANIM_MS); }
  }

  /* What the left column will show once this panel closes. #pane-nearby
     overlays #pane-filters in that same column (body.nearby-open), so the
     surface underneath is the nearby list whenever it is open, and the filter
     chips otherwise. The back control is labelled from this so it never
     promises a destination the user will not land on. */
  function surfaceBehind() {
    var nearbyOpen = !!(AM.nearby && AM.nearby.isOpen && AM.nearby.isOpen());
    return nearbyOpen ? "Nearby" : "Filters";
  }

  /* Keep the back button's wording in step with what is actually behind the
     panel. Called whenever the panel opens and whenever the nearby list is
     opened or closed underneath it. */
  function syncBackLabel() {
    var span = placeEl && placeEl.querySelector("#pl-back span");
    if (!span) return;
    var label = surfaceBehind();
    span.textContent = label;
    $("pl-back").setAttribute("aria-label", "Back to " + label);
  }

  /* Back arrow: drop the selection (which closes the panel) and make sure the
     surface the user came from is on screen again. Its tab, scroll position
     and checkboxes were never touched. */
  function backToFilters() {
    AM.state.set("selectedArcade", null, { source: "place-back" });
    openDrawer();
    $("drawer-toggle").focus({ preventScroll: true });
  }

  /* Where the panel WILL sit, in viewport coordinates, ignoring the slide-in
     transform. getBoundingClientRect() would report the off-screen start of
     the animation on a first open (the .on class is applied a frame later),
     so the untransformed offset box is used instead - it is already final on
     the frame the element becomes visible. */
  function placeBox() {
    var host = placeEl.offsetParent || placeEl.parentElement;
    var hr = host.getBoundingClientRect();
    return {
      left: hr.left + placeEl.offsetLeft,
      top: hr.top + placeEl.offsetTop,
      right: hr.left + placeEl.offsetLeft + placeEl.offsetWidth,
      bottom: hr.top + placeEl.offsetTop + placeEl.offsetHeight
    };
  }

  /* The panel covers part of the map (its left edge on desktop, its lower half
     on a phone), so a store selected behind it gets nudged into the clear.
     Measured from the two boxes rather than assumed: with the filter drawer
     open the panel sits over the drawer and hides no map at all. */
  function keepInView(a, meta) {
    if (!U.hasCoords(a)) return;
    var run = function () {
      var map = AM.map.map;
      var mr = map.getContainer().getBoundingClientRect();
      var pr = placeBox();
      var p = map.latLngToContainerPoint([a.lat, a.lng]);
      var pad = 44, dx = 0, dy = 0;
      if (isMobile()) {
        var top = pr.top - mr.top - pad;
        if (top > 0 && p.y > top) dy = p.y - top;
      } else {
        var left = pr.right - mr.left + pad;
        if (left > pad && p.x < left) dx = p.x - left;
      }
      if (dx || dy) map.panBy([dx, dy], { animate: !C.REDUCED, duration: 0.35 });
    };
    /* A focused selection is already flying somewhere; measure on arrival.

       Except under reduced motion, where markers.js has already moved the map
       with setViewExact before this runs (its selectedArcade listener is
       registered first, in app-init) and moveend has therefore ALREADY fired.
       A once() armed now would never see it, and would instead stay armed and
       fire on the user's next pan - scrolling the map to the PREVIOUS store.
       markers.js guards its own arrival callback the same way. */
    if (meta && meta.focus && !C.REDUCED) AM.map.map.once("moveend", run);
    else run();
  }

  /* ---------- toast ---------- */

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, 1900);
  }

  function hideToast() {
    clearTimeout(toastTimer);
    if (toastEl) toastEl.classList.remove("on");
  }

  /* execCommand is retired but still the only synchronous copy path when the
     async Clipboard API is missing (file://) or refused. */
  function legacyCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:-1000px;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  function copyText(text, okMsg) {
    var fail = function () {
      if (legacyCopy(text)) toast(okMsg); else toast("Copy failed");
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast(okMsg); }, fail);
    } else {
      fail();
    }
  }

  /* ---------- mobile bottom sheet drag ---------- */

  function sheetPx(frac) {
    var host = placeEl.parentElement;
    return Math.round((host ? host.clientHeight : window.innerHeight) * frac);
  }

  function startDrag() {
    var grip = $("pl-grip");
    var dragging = false, startY = 0, startH = 0, peek = 0, full = 0, shift = 0;

    function onDown(e) {
      if (!isMobile() || e.button > 0) return;
      dragging = true;
      shift = 0;
      startY = e.clientY;
      peek = sheetPx(SHEET_PEEK);
      full = sheetPx(SHEET_FULL);
      startH = placeEl.getBoundingClientRect().height;
      placeEl.classList.add("dragging");
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
      e.preventDefault();
    }

    /* One expression covers both directions: the wanted height is the start
       height minus the drag. Above `full` it stops growing; below `peek` the
       leftover becomes a downward slide, which is the dismiss gesture. */
    function onMove(e) {
      if (!dragging) return;
      var want = startH - (e.clientY - startY);
      var h = Math.max(peek, Math.min(full, want));
      shift = Math.max(0, h - want);
      placeEl.style.setProperty("--sh", h + "px");
      placeEl.style.setProperty("--dy", shift + "px");
    }

    function onUp() {
      if (!dragging) return;
      dragging = false;
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      placeEl.classList.remove("dragging");
      placeEl.style.removeProperty("--dy");
      if (shift > DISMISS_PX) {
        placeEl.style.removeProperty("--sh");
        AM.state.set("selectedArcade", null, { source: "sheet-dismiss" });
        return;
      }
      var h = placeEl.getBoundingClientRect().height;
      var expanded = h > (peek + full) / 2;
      placeEl.classList.toggle("expanded", expanded);
      if (expanded) placeEl.style.setProperty("--sh", full + "px");
      /* Collapsing goes back through fitSheet, not straight to peek, so the
         action row stays reachable for tall content here too. */
      else { placeEl.style.setProperty("--sh", peek + "px"); fitSheet(); }
    }

    grip.addEventListener("pointerdown", onDown);
  }

  /* ---------- shell + wiring ---------- */

  function buildPlace() {
    placeEl = document.createElement("aside");
    placeEl.id = "place";
    placeEl.hidden = true;
    placeEl.setAttribute("aria-label", "Place details");
    placeEl.innerHTML =
      '<div id="pl-grip" class="pl-grip" aria-hidden="true"><span></span></div>' +
      '<div class="pl-bar">' +
        '<button type="button" id="pl-back" class="pl-back">' +
          ico("back") + "<span>Filters</span></button>" +
        '<button type="button" id="pl-close" class="pl-close" aria-label="Close place details">' +
          ico("close") + "</button>" +
      "</div>" +
      '<div id="pl-body" class="pl-body"></div>' +
      '<div id="pl-toast" class="pl-toast" role="status" aria-live="polite"></div>';
    $("map").parentElement.appendChild(placeEl);
    bodyEl = $("pl-body");
    toastEl = $("pl-toast");

    $("pl-back").addEventListener("click", backToFilters);
    $("pl-close").addEventListener("click", function () {
      AM.state.set("selectedArcade", null, { source: "place-close" });
    });

    bodyEl.addEventListener("click", function (e) {
      var el = e.target.closest("[data-act]");
      if (!el || !current) return;
      var act = el.dataset.act;
      if (act === "copy-addr") {
        copyText(current.addr || "", "Address copied");
      } else if (act === "share") {
        copyText(shareUrl(current), "Link copied");
      } else if (act === "nearby") {
        /* Contract from nearby.js: {lat, lng, label?, fly?}. It is optional -
           if that module never loads, nothing listens and nothing breaks. */
        AM.state.set("nearbyFrom", {
          id: current.id, lat: current.lat, lng: current.lng, label: current.name
        }, { source: "place" });
        /* The nearby list draws into #pane-nearby, inside the SAME left column
           this panel covers, so leaving the panel up would hide the very list
           the tap just asked for. Drop the selection: the panel closes and the
           nearby pane becomes the visible surface. Same mutual exclusion the
           back arrow already enforces between place and filters. */
        AM.state.set("selectedArcade", null, { source: "place-nearby" });
        openDrawer();
        /* The panel this click was inside is now gone, so focus would fall to
           <body> and a keyboard user would have to tab from the top of the
           page to reach the list they just asked for. Hand focus to the pane
           that replaced it, the same way the back arrow hands it to the drawer
           toggle. Deferred a frame because nearby.js renders the pane in
           response to the state writes above. */
        requestAnimationFrame(function () {
          var target = $("nb-close") || $("pane-nearby");
          if (target && target.offsetParent !== null) {
            target.focus({ preventScroll: true });
          }
        });
      }
    });

    /* Escape dismisses exactly one layer: the topmost one. The settings
       <dialog> is a modal in the browser's top layer and closes itself on
       Escape natively, so if it is open this panel must keep its hands off -
       otherwise a single press tore down both the dialog AND the place panel
       the user was reading underneath it, and the second press had nothing
       left to close. Same for the omnibox, which clears its own query. */
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || !isPlaceOpen()) return;
      if (e.target && e.target.id === "search") return;
      var dlg = AM.settings && AM.settings.dialog && AM.settings.dialog();
      if (dlg && dlg.open) return;
      AM.state.set("selectedArcade", null, { source: "escape" });
    });

    startDrag();

    /* orientationchange still fires on iOS where a rotate does not always
       produce a resize in the same tick; both funnel into the same debounce
       so a device that fires both only re-measures once. */
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("orientationchange", onViewportChange);
  }

  /* Markers used to carry a popup. The place panel is the detail surface now,
     so the popup is retired: every binding is dropped, and the one popup
     markers.js still opens on a focused pick is closed in the same tick it
     opens, before the browser can paint it. A name-only hover tooltip takes
     its place on pointer devices.

     Marker events are taken off the cluster group, not off each marker:
     markercluster makes itself the event parent of its members, so three
     handlers cover the whole layer instead of three per store. */
  function retirePopups() {
    var map = AM.map.map;
    map.on("popupopen", function (e) { map.closePopup(e.popup); });

    AM.data.plottable.forEach(function (a) {
      var m = AM.markers.markerOf[a.id];
      if (!m) return;
      m.__amId = a.id;
      if (m.unbindPopup) m.unbindPopup();
    });

    var tip = canHover() ? L.tooltip({
      direction: "top", offset: [0, -11], className: "am-tip", opacity: 1
    }) : null;

    function hit(e) {
      var l = e.layer || e.propagatedFrom || e.target;
      return (l && l.__amId !== undefined) ? AM.data.byId[l.__amId] : null;
    }

    AM.markers.cluster.on("click", function (e) {
      var a = hit(e);
      if (!a) return;
      if (tip) map.closeTooltip(tip);
      AM.state.set("selectedArcade", a.id, { source: "marker" });
    });

    if (!tip) return;
    AM.markers.cluster.on("mouseover", function (e) {
      var a = hit(e);
      if (!a) return;
      /* Markers are centre-anchored tier symbols between 20px and 36px tall,
         so one fixed offset cannot clear them all: -11 sat on top of a T5
         crown and floated well above a T1 note. Ask the marker layer what it
         is drawing and clear that, plus a 5px gap for the callout tip.
         A standalone tooltip has no layer anchor to add, so options.offset is
         the whole position adjustment, and setLatLng below re-reads it. */
      if (AM.markers.iconPxFor) {
        tip.options.offset = [0, -(Math.round(AM.markers.iconPxFor(a) / 2) + 5)];
      }
      tip.setLatLng([a.lat, a.lng]).setContent(esc(a.name));
      map.openTooltip(tip);
    });
    AM.markers.cluster.on("mouseout", function () { map.closeTooltip(tip); });
  }

  /* ---------- deep link ---------- */

  /* #arcade=<id> rides alongside the existing #z/lat/lng/games/cabs segments.
     mapcore.js rewrites the hash from map + filter state, so the segment is
     read here and never written back: the Share button composes it on demand
     instead of the URL carrying a selection that outlives the panel. */
  /* The hash is user-supplied text: "#arcade=%" is a malformed escape and
     decodeURIComponent THROWS URIError on it. This runs inside app-init's
     fetch().then() chain, where a throw is swallowed by the trailing .catch()
     and silently truncates the whole boot - every start() after panel's never
     runs, and the only visible trace is the count reading "data load failed".
     So the decode is guarded and a hash that cannot be decoded is simply not
     a selection: the raw text is still tried, since an id needing no escaping
     is the normal case and must keep working. */
  function decodeId(s) {
    try { return decodeURIComponent(s); } catch (e) { return null; }
  }

  function hashArcade() {
    var raw = location.hash.replace(/^#/, "");
    if (!raw) return null;
    var found = null;
    raw.split("/").forEach(function (s) {
      if (s.indexOf("arcade=") === 0) found = s.slice(7);
    });
    if (!found) return null;
    var id = decodeId(found);
    if (id !== null && AM.data.byId[id]) return AM.data.byId[id];
    return AM.data.byId[found] || null;
  }

  function applyHashArcade() {
    var a = hashArcade();
    if (!a) return;
    if (current && current.id === a.id) return;
    AM.state.set("selectedArcade", a.id, { focus: true, source: "hash" });
  }

  /* ---------- wiring ---------- */

  function build() {
    buildShell();
    syncPanelWidth();
    buildResizer();
    buildChips();
    buildCabFilters();
    buildCoordlessList();
    buildFooter();
    buildPlace();
    retirePopups();
  }

  function start() {
    AM.state.on("selectedGames", syncChips);
    AM.state.on("selectedCabs", syncCabFilters);
    AM.state.on("shownCount", syncCount);
    AM.state.on("selectedArcade", function (id, meta) {
      var a = id === null || id === undefined ? null : AM.data.byId[id];
      if (!a) {
        /* Every dismissal - X, back arrow, Escape, sheet drag - lands here, so
           the URL is cleaned in one place rather than at four call sites. Left
           behind, arcade= outlives the panel and a reload silently re-opens a
           store the user closed. */
        scrubHashArcade();
        closePlace();
        /* The halo is drawn from two places - markers.js for a focused pick,
           the branch below for a plain marker click - but neither owns the
           teardown: markers.js's listener returns early unless meta.focus is
           set, and every dismissal path writes null without it. So a ring
           stayed pinned to the store for the rest of its 8s life after the
           panel that explained it had gone. */
        if (AM.markers && AM.markers.removeHalo) AM.markers.removeHalo();
        return;
      }
      /* markers.js flies and halos focused picks; a plain marker click stays
         where it is, so ring the store here instead. */
      if ((!meta || !meta.focus) && U.hasCoords(a) && AM.markers.showHalo) {
        AM.markers.showHalo([a.lat, a.lng], a);
      }
      openPlace(a, meta);
    });
    window.addEventListener("hashchange", applyHashArcade);

    /* nearby.js signals its pane with a body class rather than a state key,
       and on a phone the place sheet only covers the lower half, so that pane
       can be opened or closed while the sheet is still up. Watch the class so
       the back label keeps matching the surface underneath. Observing the
       attribute is cheaper than polling and keeps the two modules uncoupled. */
    if (window.MutationObserver) {
      var wasNearby = document.body.classList.contains("nearby-open");
      new MutationObserver(function () {
        var now = document.body.classList.contains("nearby-open");
        if (now === wasNearby) return;
        wasNearby = now;
        if (isPlaceOpen()) syncBackLabel();
      }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
    }

    syncChips();
    syncCabFilters();
    syncCount();
    applyHashArcade();
  }

  AM.panel = {
    build: build,
    start: start,
    switchTab: switchTab,
    openDrawer: openDrawer,
    showCoordlessEntry: showCoordlessEntry,
    syncCount: syncCount,
    buildFooter: buildFooter,
    openPlace: openPlace,
    closePlace: closePlace,
    backToFilters: backToFilters,
    isPlaceOpen: isPlaceOpen,
    shareUrl: shareUrl,
    /* test seams: the hash guard, the price parser and the enrichment cache
       are all pure enough to assert on without driving the UI. */
    hashArcade: hashArcade,
    scrubHashArcade: scrubHashArcade,
    parsePrice: parsePrice,
    ensureEnrichData: ensureEnrichData,
    panelWidth: function () { return $("panel").getBoundingClientRect().width; },
    setEnrichment: function (blob, manifest) {
      if (blob) { enrich = blob; enrichPromise = Promise.resolve(blob); }
      if (manifest) { cabs = manifest; cabsPromise = Promise.resolve(manifest); }
      dataVersion++;
      if (current && isPlaceOpen()) renderPlace(current);
    }
  };
})(window.AM);
