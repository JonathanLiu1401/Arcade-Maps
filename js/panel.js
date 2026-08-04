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

  /* UI chrome only - game brand names stay untranslated. */
  function tr(key, vars) {
    return (AM.i18n && AM.i18n.t) ? AM.i18n.t(key, vars) : key;
  }

  /* Cab-variant filter / badge label. Official model codenames stay in the
     English source string; locales may gloss "model" / "standard" around them. */
  function cabLabel(cf) {
    var key = "cabs." + cf.id;
    var s = tr(key);
    return (s && s !== key) ? s : (cf.label || cf.id);
  }

  function gameChipLabel(g) {
    if (g === "other") {
      var s = tr("cabs.other_game");
      return (s && s !== "cabs.other_game") ? s : (C.GAME_LABEL.other || "Other");
    }
    return C.GAME_LABEL[g] || g;
  }

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

  /* The number on a chip is "how many stores land on the map if I pick this
     game", so it has to be computed under the SOURCE and CAB filters that are
     live right now. AM.data.gameCounts is a build-time total that knows about
     neither, and printing it meant the chip and the map disagreed out loud:
     with only ZIv enabled and only SDVX picked, the chip read 1,031 while the
     header and the omnibox both read 877. search.js already computes the
     honest number for the omnibox rows and caches it, so all three surfaces
     now read it from there rather than keeping a second, staler tally. */
  function chipCount(g) {
    if (AM.search && AM.search.visibleCountForGame) {
      return AM.search.visibleCountForGame(g);
    }
    return (AM.data.gameCounts || {})[g] || 0;
  }

  function syncChipCounts() {
    var box = $("game-chips");
    if (!box) return;
    var chips = box.children;
    for (var i = 0; i < chips.length; i++) {
      var n = chips[i].querySelector(".n");
      if (n) n.textContent = U.num(chipCount(chips[i].dataset.g));
    }
  }

  function buildChips() {
    var box = $("game-chips");
    AM.data.gamesInData.forEach(function (g) {
      var b = document.createElement("button");
      b.className = "chip";
      b.dataset.g = g;
      b.type = "button";
      b.style.setProperty("--c", C.GAME_COLOR[g] || C.GAME_COLOR.other);
      b.innerHTML = '<span class="dot"></span>' + esc(gameChipLabel(g)) +
        ' <span class="n tabnum">' + U.num(chipCount(g)) + "</span>";
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

  function rebuildCabFilters() {
    var box = $("cab-filters");
    if (!box) return;
    box.innerHTML = "";
    buildCabFilters();
    syncCabFilters();
  }

  function rebuildGameChips() {
    var box = $("game-chips");
    if (!box) return;
    box.innerHTML = "";
    buildChips();
    syncChips();
  }

  function rebuildSizeChips() {
    var box = $("size-chips");
    if (!box) return;
    box.innerHTML = "";
    buildSizeChips();
    syncSizeChips();
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
      head.textContent = gameChipLabel(g);
      box.appendChild(head);
      byGame[g].forEach(function (cf) {
        var lab = document.createElement("label");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = sel.has(cf.id);
        cb.addEventListener("change", function () { AM.state.toggleCab(cf.id); });
        lab.appendChild(cb);
        lab.appendChild(document.createTextNode(" " + cabLabel(cf) + " "));
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

  /* ---------- arcade size chips ---------- */

  /* Same bands as markers.js TIER_LEGEND: T1 1-2 ... T5 50+, TU unknown.
     Chip counts are plottable arcades in that tier (tierFor uses showable
     cabinet counts, not the raw sum). */
  function sizeTierCounts() {
    var counts = {};
    var list = AM.data.plottable;
    for (var i = 0; i < list.length; i++) {
      var id = AM.markers.tierFor(list[i]).id;
      counts[id] = (counts[id] || 0) + 1;
    }
    return counts;
  }

  function buildSizeChips() {
    var box = $("size-chips");
    if (!box || !AM.markers || !AM.markers.TIER_LEGEND) return;
    var counts = sizeTierCounts();
    AM.markers.TIER_LEGEND.forEach(function (t) {
      var b = document.createElement("button");
      b.className = "chip size-chip";
      b.dataset.tier = t.id;
      b.type = "button";
      var sizeKey = "ui.size_" + t.id;
      var sizeTitle = tr(sizeKey);
      if (!sizeTitle || sizeTitle === sizeKey) sizeTitle = t.label;
      b.title = sizeTitle;
      b.innerHTML = '<span class="dot"></span>' + esc(t.short) +
        ' <span class="n tabnum">' + U.num(counts[t.id] || 0) + "</span>";
      b.addEventListener("click", function () { AM.state.toggleSizeTier(t.id); });
      box.appendChild(b);
    });
    var allBtn = $("size-all");
    var noneBtn = $("size-none");
    if (allBtn && !allBtn._amSizeBound) {
      allBtn._amSizeBound = true;
      allBtn.addEventListener("click", function () {
        var ids = AM.markers.TIER_LEGEND.map(function (t) { return t.id; });
        AM.state.set("selectedSizeTiers", new Set(ids));
      });
    }
    if (noneBtn && !noneBtn._amSizeBound) {
      noneBtn._amSizeBound = true;
      noneBtn.addEventListener("click", function () {
        AM.state.set("selectedSizeTiers", new Set());
      });
    }
  }

  function syncSizeChips() {
    var sel = AM.state.get("selectedSizeTiers");
    var box = $("size-chips");
    if (!sel || !box) return;
    var chips = box.children;
    for (var i = 0; i < chips.length; i++) {
      var on = sel.has(chips[i].dataset.tier);
      chips[i].classList.toggle("on", on);
      chips[i].setAttribute("aria-pressed", on ? "true" : "false");
    }
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
          '">' + esc(tr("place.search_gmaps")) + '</a></div>';
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
    $("meta-count").textContent = tr("ui.shown", {
      n: U.num(AM.state.get("shownCount"))
    });
  }

  function buildFooter() {
    var counts = AM.data.srcCounts;
    $("src-counts").innerHTML = AM.data.srcInData.map(function (s) {
      return "<span>" + esc(C.SRC_LABEL[s] || s) + " " + U.num(counts[s]) + "</span>";
    }).join("") +
      "<span>" + esc(tr("ui.stores_total", {
        n: U.num(AM.data.arcades.length)
      })) + "</span>";
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
    chevL: '<path d="M14.5 5.5 8 12l6.5 6.5"/>',
    chevR: '<path d="M9.5 5.5 16 12l-6.5 6.5"/>',
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
  function safePhotoUrl(v) {
    if (typeof v !== "string") return null;
    v = v.trim();
    if (!v) return null;
    if (/^https?:\/\//i.test(v)) return v;
    if (/^data:image\//i.test(v)) return v;
    /* No scheme at all: a same-origin relative path. */
    if (!/^[a-z][a-z0-9+.-]*:/i.test(v)) return v;
    return null;
  }

  function photoUrl(a) {
    var v = firstField(a, ["image_thumb", "image", "photo", "photo_url"]);
    if (!v && Array.isArray(a.images) && typeof a.images[0] === "string") v = a.images[0];
    return safePhotoUrl(v);
  }

  /* ================= enrichment (lazy, one fetch each) =================

     data/enrichment.json is 8.2 MB raw (about 1.1 MB gzipped, which is what
     GitHub Pages actually sends) and only the place panel ever needs it, so
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

  /* Round a measured figure the way the currency is actually quoted: whole
     units for yen and won, two decimals elsewhere, and no trailing ".00". */
  function fmtMeasured(v, cur) {
    if (cur === "JPY" || cur === "KRW" || cur === "IDR" || cur === "VND") {
      return String(Math.round(v));
    }
    var s = v.toFixed(2);
    return s.replace(/\.00$/, "");
  }

  /* What a play costs here, in priority order:
       1. a MEASURED figure for this country and this game, derived from real
          quoted prices in the listings (scrapers/prices.py). n >= 5 prints as
          a definite figure; 2 to 4 prints with a "based on N listings" caveat.
       2. the country's measured overall, same rules.
       3. the hand-written PRICE_DEFAULTS table, last resort only.
     Tier "unknown" deliberately renders NOTHING rather than a guess: the old
     table claimed "HKD 8-15/play typical" for Hong Kong, where every listing
     we hold quotes HK$6.00 for maimai and CHUNITHM with no variance at all. */
  function typicalPrice(a) {
    if (!enrich || !a || !a.country) return null;
    var m = measuredPrice(a);
    if (m) return m;
    var iso = (enrich.country_to_code || {})[a.country];
    var def = iso && (enrich.price_defaults || {})[iso];
    if (!def || typeof def.display !== "string") return null;
    return {
      display: def.display, notes: def.notes || null,
      as_of: def.as_of || null, tier: "guess"
    };
  }

  function measuredPrice(a) {
    var table = enrich && enrich.prices;
    var entry = table && table.countries && table.countries[a.country];
    if (!entry) return null;

    var cell = null, slug = null, games = entry.games || {}, i;
    var ordered = orderedGames(a);
    for (i = 0; i < ordered.length; i++) {
      var c = games[ordered[i]];
      if (c && c.tier !== "unknown" && typeof c.value === "number") {
        cell = c; slug = ordered[i];
        break;                         /* the arcade's own headline game wins */
      }
    }
    if (!cell) {
      var o = entry.overall;
      if (o && o.tier !== "unknown" && typeof o.value === "number") cell = o;
    }
    if (!cell) return null;

    var cur = cell.currency || entry.currency || "";
    var display = (cur ? cur + " " : "") + fmtMeasured(cell.value, cur) +
      " " + tr("ui.per_credit");
    var label = slug ? (C.GAME_LABEL[slug] || slug) : null;
    var notes;
    if (cell.tier === "measured") {
      notes = tr("ui.price_median", {
        game: label || "",
        n: String(cell.n),
        country: a.country || ""
      });
    } else {
      notes = tr("ui.price_sparse", {
        n: String(cell.n),
        country: a.country || "",
        for_game: label ? tr("ui.for_game", { game: label }) : ""
      });
    }
    return {
      display: display, notes: notes, as_of: cell.as_of || table.as_of || null,
      tier: cell.tier, measured: true
    };
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
    /* Discord, Slack, iMessage etc. strip the #fragment before they fetch,
       so a hash deep link always unfurls the GENERIC site card. Share pages
       under s/<sid>.html carry per-venue Open Graph tags (title, games,
       address, image) that crawlers can actually read. Humans who open the
       link are JS-redirected onto the map. See scrapers/build_share_pages.py.

       Prefer sid over the row-number id: ids reshuffle every merge, which is
       how #arcade=6072 went from a Hong Kong venue to an Indonesian one. */
    var sid = a && (a.sid || a.id);
    if (!sid) {
      return location.href.split("#")[0];
    }
    var path = location.pathname || "/";
    /* index.html and trailing slash both resolve to the site root folder. */
    path = path.replace(/index\.html$/i, "");
    if (path.slice(-1) !== "/") path += "/";
    return location.origin + path + "s/" + encodeURIComponent(String(sid)) + ".html";
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

  /* ---------- photo gallery ----------

     The enrichment file carries up to three photos per store (170 stores have
     two, 482 have three), and the panel used to show exactly one of them and
     silently discard the rest. This builds the Google-Maps-style strip: one
     photo at a time, swipe or arrow to the next, a dot per slide.

     Three shapes come out of the data and all three are accepted, because the
     pipeline is still moving and a panel that only understands one of them
     would go blank the week the schema changes:

       images: [{url, credit, license, page_url, tier}, ...]   the real one
       images: ["https://...", ...]                            older mirror
       image / photo / image_thumb: "https://..."              single-field

     Everything is normalised into the same record so the renderer below has
     exactly one case to handle. */

  var MAX_SLIDES = 8;   /* the pipeline caps at 3; this is a sanity bound */

  function imageRecords(a) {
    var e = enrichOf(a) || {};
    var out = [], seen = {};

    function push(url, meta) {
      var u = safePhotoUrl(url);
      if (!u || seen[u] || out.length >= MAX_SLIDES) return;
      seen[u] = 1;
      meta = meta || {};
      out.push({
        url: u,
        /* ZIv publishes no licence for community uploads, so credit is often
           the only attribution string there is. It is still shown: naming the
           source is the minimum courtesy for a photo we hotlink, and where a
           licence IS recorded (CC BY / BY-SA) showing it is an obligation. */
        credit: typeof meta.credit === "string" ? meta.credit : null,
        license: typeof meta.license === "string" ? meta.license : null,
        page: U.safeUrl(meta.page_url || meta.source || "") || null,
        kind: "own"
      });
    }

    /* Arcade row first, then enrichment: same precedence field() uses. */
    [a, e].forEach(function (src) {
      if (!src) return;
      var list = src.images;
      if (Array.isArray(list)) {
        list.forEach(function (im) {
          if (typeof im === "string") push(im, { credit: src.image_credit });
          /* A venue photo arrives one of two ways. Hotlinked records carry an
             absolute `url`; MIRRORED ones carry a repo-relative `file` and no
             url at all, because the source serves signed links that expire
             within the hour (BemaniCN's OSS thumbnails) and a stored link
             would be dead before anyone loaded the page. Reading only `url`
             silently skipped 3,202 mirrored files that were sitting in the
             repo, which is every China venue photo. */
          else if (im && typeof im === "object") push(im.url || im.file, im);
        });
      }
      push(firstField(src, ["image_thumb", "image", "photo", "photo_url"]),
           { credit: src.image_credit });
    });

    return out;
  }

  /* The cab fallback, as a one-entry gallery so the renderer stays single-path.
     A cab shot is a stock photo of the MACHINE rather than of this venue, so it
     is flagged and labelled - see .pl-hero-kind. */
  function cabRecords(a) {
    var cab = cabPhoto(a);
    if (!cab) return [];
    /* CC BY and BY-SA both require author + licence next to the work. CC0 does
       not, but the same line is rendered for it anyway: one code path is
       harder to get wrong than two, and crediting is never wrong. */
    return [{
      url: cab.url,
      credit: (cab.author || cab.license)
        ? "photo: " + (cab.author || "unknown") +
          (cab.license ? " / " + cab.license : "")
        : null,
      license: null,
      page: U.safeUrl(cab.source || "") || null,
      kind: "cab",
      label: gameLabelFor(a, cab.game) + " cabinet"
    }];
  }

  function creditHtml(rec) {
    var txt = rec.credit || "";
    if (rec.license && txt.indexOf(rec.license) === -1) {
      txt = txt ? txt + " / " + rec.license : rec.license;
    }
    if (!txt) return "";
    return rec.page
      ? '<a class="pl-hero-credit" href="' + esc(rec.page) +
        '" target="_blank" rel="noopener">' + esc(txt) + "</a>"
      : '<span class="pl-hero-credit">' + esc(txt) + "</span>";
  }

  /* One slide. Only slide 0 gets a real src; the rest carry data-src and are
     promoted by loadSlide() when the reader actually engages.

     loading="lazy" is NOT enough on its own here. Every slide is inside the
     hero box and positioned by transform, so all of them are "in the viewport"
     as far as the browser is concerned and it will happily fetch all three the
     moment the panel opens. With 13.5k stores in memory and the panel opening
     on every marker click, that is two wasted third-party requests per click,
     against a host we are already only tolerated on. Hence data-src. */
  function slideHtml(rec, i) {
    var srcAttr = i === 0
      ? 'src="' + esc(rec.url) + '"'
      : 'data-src="' + esc(rec.url) + '"';
    return '<div class="pl-slide' + (i === 0 ? " on" : "") + '" data-i="' + i +
      '" role="group" aria-roledescription="slide" ' +
      'aria-label="Photo ' + (i + 1) + '" ' + (i === 0 ? "" : 'aria-hidden="true" ') +
      '>' +
      '<img class="pl-hero-img" ' + srcAttr + ' alt="" decoding="async" ' +
      'loading="lazy" data-hero="' + rec.kind + '">' +
      '<div class="pl-hero-veil"></div>' +
      '<div class="pl-hero-foot">' +
      (rec.label ? '<span class="pl-hero-kind">' + esc(rec.label) + "</span>" : "") +
      /* Attribution rides on the SLIDE, not on the gallery, so it changes with
         the photo. A credit line that stayed put while the image moved would
         be crediting the wrong person, which for a CC BY work is worse than
         showing nothing. */
      creditHtml(rec) + "</div></div>";
  }

  /* Media header, best available of three:
       1. photos of THIS store, from enrichment - a gallery when there is more
          than one, a plain hero when there is exactly one
       2. a photo of a cabinet it has, from assets/cabs - a stock shot of the
          machine, not of the venue, so it says so on its face and carries the
          licence line its CC terms require
       3. the game-tinted gradient banner
     Only the FIRST photo is requested when the panel opens, so a session that
     never opens a store downloads no images at all and a session that opens a
     hundred downloads a hundred, not three hundred. */
  function heroHtml(a) {
    var g = dominantGame(a);
    var color = C.GAME_COLOR[g] || C.GAME_COLOR.other;

    var recs = imageRecords(a);
    /* Google fills the gap, it never replaces what works: our own venue photo
       is licence-clean and free, so it always wins. A Google photo is tried
       only when we have none, and it outranks the cab shot because a cab shot
       is a stock photo of a MACHINE and this is a photo of the venue. See
       js/gphotos.js - a no-op when no API key is configured. */
    if (!recs.length && AM.gphotos) recs = AM.gphotos.records(a);
    if (!recs.length) recs = cabRecords(a);

    if (!recs.length) {
      return '<div class="pl-hero" style="--c:' + color + '">' +
        '<div class="pl-hero-art"></div>' +
        '<div class="pl-hero-tag">' + esc(gameLabelFor(a, g)) + "</div></div>";
    }

    var isCab = recs[0].kind === "cab";
    var cls = "pl-hero has-photo" + (isCab ? " is-cab" : "") +
      (recs.length > 1 ? " has-gallery" : "");

    /* One photo: exactly the old markup and the old behaviour. No dots, no
       arrows, no swipe handling, nothing extra to fetch or to get wrong. */
    if (recs.length === 1) {
      return '<div class="' + cls + '" style="--c:' + color + '">' +
        slideHtml(recs[0], 0) + "</div>";
    }

    var slides = recs.map(slideHtml).join("");

    var dots = recs.map(function (r, i) {
      return '<button type="button" class="pl-dot' + (i === 0 ? " on" : "") +
        '" data-act="photo-go" data-i="' + i + '" ' +
        'aria-label="Photo ' + (i + 1) + ' of ' + recs.length + '"' +
        (i === 0 ? ' aria-current="true"' : "") + "></button>";
    }).join("");

    /* tabindex + the roles make the strip one keyboard stop that announces
       itself, and the arrow keys are handled only while focus is inside it -
       the map and the search combobox both use arrows and neither may lose
       them to a photo strip. */
    return '<div class="' + cls + '" style="--c:' + color + '" ' +
      'data-gallery="1" data-n="' + recs.length + '" tabindex="0" ' +
      'role="group" aria-roledescription="carousel" ' +
      'aria-label="Photos of this arcade, ' + recs.length + ' images">' +
      '<div class="pl-slides">' + slides + "</div>" +
      '<button type="button" class="pl-nav prev" data-act="photo-prev" ' +
      'aria-label="Previous photo">' + ico("chevL") + "</button>" +
      '<button type="button" class="pl-nav next" data-act="photo-next" ' +
      'aria-label="Next photo">' + ico("chevR") + "</button>" +
      '<div class="pl-count tabnum" aria-hidden="true">1 / ' + recs.length + "</div>" +
      '<div class="pl-dots" role="tablist" aria-label="Choose photo">' + dots + "</div>" +
      /* The live region is how a screen reader learns the slide changed. It is
         separate from the visible counter because that one is aria-hidden: a
         counter that announced itself on every keypress would be noise. */
      '<div class="pl-sr" role="status" aria-live="polite"></div>' +
      "</div>";
  }

  /* ---------- gallery behaviour ----------

     State lives in a plain variable rather than in the DOM because renderPlace
     replaces bodyEl.innerHTML wholesale, and refreshWhenEnriched calls it again
     a moment after the panel opens (once the enrichment fetch lands). Anything
     kept only in the markup is destroyed by that second render - which is
     exactly when the gallery first appears, since the photos come FROM the
     enrichment file. So the index is restored after a re-render, the same way
     that code already restores scrollTop. */

  var galleryIndex = 0;

  function galleryEl() {
    return bodyEl && bodyEl.querySelector("[data-gallery]");
  }

  /* Promote data-src to src. Called for the slide being shown and for its
     immediate neighbour, so the next swipe is instant without the panel ever
     fetching a photo nobody asked to see. */
  function loadSlide(gal, i) {
    var s = gal.querySelector('.pl-slide[data-i="' + i + '"]');
    if (!s) return;
    var img = s.querySelector("img");
    if (img && !img.getAttribute("src") && img.dataset.src) {
      img.src = img.dataset.src;
      img.removeAttribute("data-src");
    }
  }

  function showSlide(i, opts) {
    var gal = galleryEl();
    if (!gal) return;
    var n = parseInt(gal.dataset.n, 10) || 1;
    /* Clamped, not wrapped. A strip of three photos that jumps from the last
       back to the first hides the fact that it ended; the disabled arrow says
       so plainly. */
    i = Math.max(0, Math.min(n - 1, i));
    galleryIndex = i;

    var slides = gal.querySelectorAll(".pl-slide");
    for (var k = 0; k < slides.length; k++) {
      var on = k === i;
      slides[k].classList.toggle("on", on);
      if (on) slides[k].removeAttribute("aria-hidden");
      else slides[k].setAttribute("aria-hidden", "true");
    }

    var dots = gal.querySelectorAll(".pl-dot");
    for (var d = 0; d < dots.length; d++) {
      dots[d].classList.toggle("on", d === i);
      if (d === i) dots[d].setAttribute("aria-current", "true");
      else dots[d].removeAttribute("aria-current");
    }

    var strip = gal.querySelector(".pl-slides");
    if (strip) strip.style.transform = "translate3d(" + (-100 * i) + "%,0,0)";

    var count = gal.querySelector(".pl-count");
    if (count) count.textContent = (i + 1) + " / " + n;

    var prev = gal.querySelector(".pl-nav.prev");
    var next = gal.querySelector(".pl-nav.next");
    if (prev) prev.disabled = i === 0;
    if (next) next.disabled = i === n - 1;

    loadSlide(gal, i);
    loadSlide(gal, i + 1);

    /* Only announce a change the user drove. The restore after a re-render
       calls this too, and announcing "photo 2 of 3" because a background fetch
       landed would be a screen reader talking about nothing. */
    if (opts && opts.announce) {
      var sr = gal.querySelector(".pl-sr");
      if (sr) sr.textContent = "Photo " + (i + 1) + " of " + n;
    }
  }

  /* Put the strip back where the reader left it after renderPlace wiped the
     DOM. Never announces, never re-fetches anything already loaded. */
  function restoreGallery() {
    var gal = galleryEl();
    if (!gal) { galleryIndex = 0; return; }
    var n = parseInt(gal.dataset.n, 10) || 1;
    showSlide(Math.min(galleryIndex, n - 1));
  }

  function stepSlide(delta) {
    showSlide(galleryIndex + delta, { announce: true });
  }

  /* Touch swipe.

     Bound once to bodyEl and filtered to the gallery, so it survives every
     innerHTML swap. Two things it must not break:

       - .pl-body scrolls vertically, and the gallery sits inside it. So
         touch-action is pan-y (CSS) and preventDefault is called only after a
         gesture has proved itself horizontal. A gallery that swallowed
         vertical drags would make the panel unscrollable exactly where the
         reader's thumb naturally lands.
       - the mobile sheet's drag-to-resize is bound to #pl-grip alone, which is
         a different element, so the two gestures cannot collide.

     Pointer events cover touch, pen and mouse-drag in one path. */
  function startGalleryDrag() {
    var id = null, x0 = 0, y0 = 0, dx = 0, horiz = false, gal = null, strip = null;

    function reset() {
      if (strip) strip.style.transition = "";
      id = null; gal = null; strip = null; horiz = false; dx = 0;
    }

    bodyEl.addEventListener("pointerdown", function (e) {
      if (id !== null || e.button > 0) return;
      var g = e.target.closest ? e.target.closest("[data-gallery]") : null;
      if (!g) return;
      /* An arrow or a dot is a tap target, not a swipe surface. */
      if (e.target.closest("button, a")) return;
      id = e.pointerId; gal = g; strip = g.querySelector(".pl-slides");
      x0 = e.clientX; y0 = e.clientY; dx = 0; horiz = false;
    });

    bodyEl.addEventListener("pointermove", function (e) {
      if (e.pointerId !== id || !strip) return;
      dx = e.clientX - x0;
      var dy = e.clientY - y0;
      if (!horiz) {
        if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
        /* First real movement decides the gesture, once. A drag that started
           vertical stays vertical (the panel scrolls) even if the thumb
           wanders sideways later. */
        if (Math.abs(dx) <= Math.abs(dy)) { reset(); return; }
        horiz = true;
        strip.style.transition = "none";
      }
      /* Rubber-band at the two ends so the strip visibly resists rather than
         sliding into blank space. */
      var n = parseInt(gal.dataset.n, 10) || 1;
      var d = dx;
      if ((galleryIndex === 0 && d > 0) || (galleryIndex === n - 1 && d < 0)) d *= 0.3;
      var w = gal.clientWidth || 1;
      strip.style.transform =
        "translate3d(" + (-100 * galleryIndex + (d / w) * 100) + "%,0,0)";
      e.preventDefault();
    }, { passive: false });

    function end(e) {
      if (e.pointerId !== id) return;
      var wasHoriz = horiz, moved = dx, g = gal, s = strip;
      reset();
      if (!wasHoriz || !g) return;
      if (s) s.style.transition = "";
      /* 40px, not a fraction of the width: on a 390px phone a third of the
         width is 130px, which is further than a thumb travels comfortably. */
      if (moved <= -40) stepSlide(1);
      else if (moved >= 40) stepSlide(-1);
      else showSlide(galleryIndex);
    }

    bodyEl.addEventListener("pointerup", end);
    bodyEl.addEventListener("pointercancel", end);
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

  /* Does this store show a single real quantity? Counts the chips the reader
     will actually SEE, not the keys in game_counts: a store whose every entry
     is a lone unqualified ZIv row now prints no numbers at all, so it needs
     the same "we do not know" caption as a store with no counts at all.
     Judging by the raw keys let 1,536 suppressed chips masquerade as counted. */
  function hasCounts(a) {
    if (!a || !a.game_counts) return false;
    for (var k in a.game_counts) {
      if (Object.prototype.hasOwnProperty.call(a.game_counts, k) &&
          typeof a.game_counts[k] === "number" && isFinite(a.game_counts[k]) &&
          U.countIsShowable(a, k)) return true;
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
    orderedGames(a).forEach(function (g) {
      var n = U.gameCount(a, g);
      var cnt = "";
      if (n !== null && U.countIsShowable(a, g)) {
        cnt = ' <b class="cnt tabnum">x' + n + "</b>" +
          (U.countIsQualified(a, g, src)
            ? ' <i class="cnt-q">' + esc(tr("ui.listed")) + "</i>"
            : "");
      }
      /* The grey "Other" chip covers 7,491 stores and names nothing. Pump It
         Up alone sits in 1,481 of them. The merge has no slug for these yet,
         but the titles are right there in the listing, so the chip says what
         it is instead of being a black box. */
      var label = (g === "other") ? gameChipLabel("other") : gameLabelFor(a, g);
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
      '<span class="act-lb">' + esc(tr("place.directions")) + '</span></a>';
    if (U.hasCoords(a)) {
      h += '<button type="button" class="act" data-act="nearby">' +
        '<span class="act-ico">' + ico("nearby") + '</span>' +
        '<span class="act-lb">' + esc(tr("place.nearby")) + '</span></button>';
    }
    h += '<button type="button" class="act" data-act="share">' +
      '<span class="act-ico">' + ico("share") + '</span>' +
      '<span class="act-lb">' + esc(tr("place.share")) + '</span></button>';
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
    /* A re-checked field said "community data from verified, may be
       outdated", which is nonsense. What it should say depends on WHERE
       it was re-checked: 80% of the verification evidence is BemaniCN or
       ZIv - the same community listings - so only the ~20% read from an
       operator's own site earns the caveat being dropped. Saying
       "verified" over a community re-read would be exactly the kind of
       overclaim the approx-flag comment in merge.py refuses to make. */
    if (who === "verified") {
      var rec = (e && e.verified && e.verified[fieldName]) || {};
      var host = "";
      if (rec.url) {
        var m = String(rec.url).match(/^https?:\/\/([^/]+)/i);
        host = m ? m[1].replace(/^www\./, "") : "";
      }
      var community = /(^|\.)(?:zenius-i-vanisher\.com|bemanicn\.com)$/i
        .test(host);
      var cap = community
        ? tr("place.rechecked_community", { host: host })
        : (host
            ? tr("place.checked_operator", { host: host })
            : tr("place.checked_operator_generic"));
      if (rec.checked_at) cap += " (" + rec.checked_at + ")";
      cap = esc(cap);
      return rec.url
        ? '<a href="' + esc(rec.url) + '" target="_blank" rel="noopener' +
          ' noreferrer">' + cap + "</a>"
        : cap;
    }
    var label = who ? (C.SRC_LABEL[who] || who) : tr("place.community_listings");
    var when = enrichedAt(a, e);
    var datePart = when ? " (" + when + ")" : "";
    return esc(tr("place.community_from", { src: label, date: datePart }));
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
        ? esc(tr("place.price_common", { n: String(vp.games) })) + " " +
          communityCaption(a, e, "machine_prices")
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
        esc(tr("place.per_machine")) + " " + communityCaption(a, e, "machine_prices"));
    }

    /* Only when the store itself says nothing: a country typical is context,
       not a quote, and must never stand in for a real price. */
    if (!vp && !per.length) {
      var tp = typicalPrice(a);
      if (tp) {
        var cap = tp.notes && tp.measured
          ? esc(tp.notes)
          : esc(tr("ui.typical_country", { country: a.country || "" }));
        h += row("price", esc(tp.display),
          cap + (tp.as_of ? " (" + esc(tp.as_of) + ")" : ""), "muted");
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
      h += row("alert",
        esc(dead.join(", ") + " - " +
          (dead.length > 1 ? tr("ui.offline_cabs") : tr("ui.offline_cab"))),
        esc(tr("ui.offline_cap")),
        "warn");
    }
    /* Only worth saying where a cabinet variant actually exists to be missed,
       and only when nothing is known about this store's. */
    if (!known) {
      var couldVary = (a.games || []).some(function (g) {
        return (C.VARIANTS_BY_GAME[g] || []).length > 0;
      });
      if (couldVary) {
        h += row("info", esc(tr("ui.cab_model_unpublished")),
          esc(tr("ui.cab_model_unpublished_cap")),
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
        '<span class="rc">' + esc(tr("place.tap_to_copy")) + '</span></span></button>';
    }

    if (!U.hasCoords(a)) {
      h += row("info", esc(tr("place.no_map_position")),
        esc(tr("place.no_map_position_cap")), "muted");
    } else if (a.approx) {
      /* Name the level the merge actually reached. "City level" was printed for
         every approximate pin even after most of them moved to their district,
         which understates a 10 km improvement and, worse, reads as a promise
         the district-level pins do not need to make. An address- or
         street-level pin came from geocoding the published address, so it is
         about the building: still derived, no longer a guess at an area. */
      var level = a.approx_level || "city";
      if (["address", "street", "district", "city"].indexOf(level) === -1) {
        level = "city";
      }
      h += row("alert",
        esc(tr("place.approx_" + level)),
        esc(tr("place.approx_" + level + "_cap")),
        "warn");
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
      if (a.counts_src === null || a.game_counts) {
        h += row("info", esc(tr("place.machine_list_no_counts")),
          esc(tr("place.machine_list_no_counts_cap")), "muted");
      } else {
        h += row("info", esc(tr("place.cab_counts_unavailable")),
          esc(tr("place.cab_counts_unavailable_cap")), "muted");
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
      h += row("layers", '<span class="rbadges">' + badges + "</span>",
        esc(tr("place.listed_by")));
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

  /* A permanently-closed venue drawn as open is the worst failure this map
     has, because somebody travels to it. The row is deliberately KEPT rather
     than deleted - a reader who searches for a place they remember deserves
     to be told it closed, and a silently vanishing pin cannot explain
     itself - so the panel has to say so loudly, above the games and the
     directions button, and link the source that says it. */
  function closedHtml(a) {
    if (!a || !a.closed) return "";
    /* The reason text is written by the researcher and usually already
       opens with "permanently closed ...", so printing the heading and
       the reason verbatim read "Permanently closed. closed (permanently
       closed after 26 April 2026)". Strip that leading restatement and
       keep whatever detail follows - the date is the useful part. */
    var why = String(a.closed_reason || "");
    why = why.replace(/^[\s(]*(?:permanently\s+)?closed\b[\s:;,-]*/i, "")
             .replace(/^\((.*)\)$/, "$1")
             .trim();
    var srcLabel = a.closed_source
      ? ' <a href="' + esc(a.closed_source) + '" target="_blank"' +
        ' rel="noopener noreferrer">' + esc(tr("ui.source")) + "</a>"
      : "";
    return '<div class="pl-closed"><strong>' + esc(tr("ui.permanently_closed")) +
      "</strong>" +
      (why ? " " + esc(why.charAt(0).toUpperCase() + why.slice(1)) : "") +
      srcLabel + "</div>";
  }

  var renderedVersion = -1;

  function renderPlace(a, keepScroll) {
    var sub = [a.pref, a.country].filter(Boolean).join(" · ");
    bodyEl.innerHTML = heroHtml(a) +
      '<div class="pl-head"><h2 class="pl-name">' + esc(a.name) + "</h2>" +
      (sub ? '<div class="pl-sub">' + esc(sub) + "</div>" : "") + "</div>" +
      closedHtml(a) +
      chipsHtml(a) + actionsHtml(a) + rowsHtml(a);
    renderedVersion = dataVersion;
    /* keepScroll marks a re-render of the SAME store (the enrichment fetch
       landing), where the reader may already be on slide 2. A fresh store
       starts at its first photo. */
    if (!keepScroll) { galleryIndex = 0; bodyEl.scrollTop = 0; }
    restoreGallery();
  }

  /* The enrichment file is megabytes and the panel must not wait for it, so
     the first open paints from whatever is cached and this re-paints once the
     fetches land. current.id is re-checked because the reader may already have
     moved to another store by then, and the scroll position is preserved so a
     late arrival never yanks the page out from under them. */
  function refreshWhenEnriched(a) {
    ensureEnrichData().then(function () {
      if (!current || current.id !== a.id || !isPlaceOpen()) return;
      /* Only once the enrichment file has landed do we know whether this store
         has a photo of its own, and a Google photo is a billed request we must
         not make for a store we can already illustrate. So the ask happens
         HERE rather than in openPlace: by this point imageRecords(a) is
         answerable. A no-op without an API key. */
      if (AM.gphotos && !imageRecords(a).length) AM.gphotos.request(a);
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
    return nearbyOpen ? tr("place.nearby") : tr("place.filters");
  }

  /* Keep the back button's wording in step with what is actually behind the
     panel. Called whenever the panel opens and whenever the nearby list is
     opened or closed underneath it. */
  function syncBackLabel() {
    var span = placeEl && placeEl.querySelector("#pl-back span");
    if (!span) return;
    var label = surfaceBehind();
    span.textContent = label;
    $("pl-back").setAttribute("aria-label", tr("place.back_to", { label: label }));
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
      if (legacyCopy(text)) toast(okMsg); else toast(tr("place.copy_failed"));
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
    placeEl.setAttribute("aria-label", tr("place.details"));
    placeEl.innerHTML =
      '<div id="pl-grip" class="pl-grip" aria-hidden="true"><span></span></div>' +
      '<div class="pl-bar">' +
        '<button type="button" id="pl-back" class="pl-back">' +
          ico("back") + "<span>" + esc(tr("place.filters")) + "</span></button>" +
        '<button type="button" id="pl-close" class="pl-close" aria-label="' +
          esc(tr("place.close")) + '">' +
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
      /* The gallery controls are delegated through this same handler on
         purpose. renderPlace replaces bodyEl.innerHTML, so a listener bound to
         a freshly-created arrow button is orphaned the moment the enrichment
         fetch lands and the panel re-renders - which is precisely when the
         gallery appears. Delegation costs nothing and cannot go stale. */
      if (act === "photo-next") { stepSlide(1); return; }
      if (act === "photo-prev") { stepSlide(-1); return; }
      if (act === "photo-go") {
        showSlide(parseInt(el.dataset.i, 10) || 0, { announce: true });
        return;
      }
      if (act === "copy-addr") {
        copyText(current.addr || "", tr("place.address_copied"));
      } else if (act === "share") {
        copyText(shareUrl(current), tr("place.link_copied"));
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

    /* Arrow keys move the photo strip, but ONLY while focus is inside it.
       Scoped to bodyEl and gated on closest("[data-gallery]") because the map
       pans with arrows and the search combobox walks its result list with
       them - a document-level handler would steal both. Escape is deliberately
       NOT handled here: the panel's own Escape (below) must keep closing the
       panel, and a gallery that swallowed it would leave the reader with a
       key that does nothing.

       Home/End are included because a three-slide strip is exactly the case
       where "jump to the end" is one key instead of two. */
    bodyEl.addEventListener("keydown", function (e) {
      var gal = e.target.closest && e.target.closest("[data-gallery]");
      if (!gal) return;
      var n = parseInt(gal.dataset.n, 10) || 1;
      var handled = true;
      if (e.key === "ArrowRight") stepSlide(1);
      else if (e.key === "ArrowLeft") stepSlide(-1);
      else if (e.key === "Home") showSlide(0, { announce: true });
      else if (e.key === "End") showSlide(n - 1, { announce: true });
      else handled = false;
      /* Only swallow the keys actually used. Tab must still leave the strip -
         nothing here traps focus. */
      if (handled) { e.preventDefault(); e.stopPropagation(); }
    });

    startGalleryDrag();

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
    var key = decodeId(found);
    if (key === null) key = found;
    /* sid first, ALWAYS. A link minted before stable ids carries a bare row
       number, and resolving that against today's byId opens whichever venue
       now sits in that row - silently, and on the other side of the world.
       Numeric-looking keys are therefore only honoured when they also match
       a sid; an unrecognised one opens nothing, which is the honest outcome
       for a link whose target can no longer be identified. */
    if (AM.data.bySid && AM.data.bySid[key]) return AM.data.bySid[key];
    if (!/^[0-9]+$/.test(key) && AM.data.byId[key]) return AM.data.byId[key];
    return null;
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
    buildSizeChips();
    buildCoordlessList();
    buildFooter();
    buildPlace();
    retirePopups();
  }

  function start() {
    AM.state.on("selectedGames", syncChips);
    AM.state.on("selectedCabs", syncCabFilters);
    AM.state.on("selectedSizeTiers", syncSizeChips);
    /* Re-render open place panel and back label when language changes.
       data-i18n covers static chrome; this surface is built in JS. */
    if (AM.i18n && AM.i18n.on) {
      AM.i18n.on(function () {
        if (placeEl) {
          placeEl.setAttribute("aria-label", tr("place.details"));
          var closeBtn = $("pl-close");
          if (closeBtn) closeBtn.setAttribute("aria-label", tr("place.close"));
        }
        /* Filter drawer is built once; rebuild labels that use tr(). */
        try { rebuildGameChips(); } catch (e) {}
        try { rebuildCabFilters(); } catch (e) {}
        try { rebuildSizeChips(); } catch (e) {}
        syncCount();
        /* CSS content for notes expand/collapse. */
        try {
          document.documentElement.style.setProperty(
            "--am-show-more", '"' + tr("ui.show_more").replace(/"/g, '\\"') + '"');
          document.documentElement.style.setProperty(
            "--am-show-less", '"' + tr("ui.show_less").replace(/"/g, '\\"') + '"');
        } catch (e2) {}
        if (AM.search && AM.search.syncPlaceholder) {
          try { AM.search.syncPlaceholder(); } catch (e3) {}
        }
        syncBackLabel();
        if (current && isPlaceOpen()) {
          var top = bodyEl ? bodyEl.scrollTop : 0;
          renderPlace(current, true);
          if (bodyEl) bodyEl.scrollTop = top;
          fitSheet();
        }
      });
    }
    /* Source and cab changes move what a chip's number would be, so the
       numbers are re-read whenever they do. search.js subscribes to the same
       two keys to clear its count cache, and it registers during
       AM.search.build(), which app-init runs before any start() - so by the
       time these listeners fire the cache is already empty and they read a
       freshly computed number rather than the previous filter's answer. */
    AM.state.on("enabledSources", syncChipCounts);
    AM.state.on("selectedCabs", syncChipCounts);
    AM.state.on("shownCount", syncCount);
    /* A Google photo arrives after the panel has already painted, so it needs
       the same late-arrival re-render the enrichment fetch gets. Bumping
       dataVersion reuses that machinery rather than adding a second one. */
    if (AM.gphotos) {
      AM.gphotos.onPhoto(function (arcadeId) {
        dataVersion++;
        if (!current || current.id !== arcadeId || !isPlaceOpen()) return;
        var top = bodyEl.scrollTop;
        renderPlace(current, true);
        bodyEl.scrollTop = top;
        fitSheet();
      });
    }
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
    syncSizeChips();
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
