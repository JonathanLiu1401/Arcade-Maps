/* Arcade Maps - the settings modal (gear button -> native <dialog>) and the
   small on-map legend chip.

   Owns: source toggles, display + location preferences, the legend.

   Every user-facing value lives in AM.state, so other modules react through
   state events and never call in here. Two of those keys are ours alone and
   state.js does not auto-persist them, so each write goes through the pair
   set() + writeSetting(); enabledSources is the exception, state.js mirrors
   it to localStorage itself (as the disabled list) whenever it is set.

   This module builds its own DOM: index.html carries no settings markup. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts, U = AM.util;
  var $ = U.$, esc = U.esc;

  /* Long-form source names and the one-line explanation each row shows.
     C.SRC_LABEL is the short badge text used on markers and in the footer;
     this is the prose version, and it stays local to the settings UI. */
  var SRC_INFO = {
    allnet: {
      name: "ALL.Net",
      desc: "Official SEGA store locator: maimai DX, CHUNITHM, O.N.G.E.K.I."
    },
    eagate: {
      name: "e-amusement",
      desc: "Official KONAMI store locator: IIDX, SOUND VOLTEX, DDR and other Bemani."
    },
    wahlap: {
      name: "WAHLAP",
      desc: "Official SEGA distributor for mainland China. Addresses only, no coordinates."
    },
    bemanicn: {
      name: "BemaniCN",
      desc: "Community-run map of Bemani cabinets in mainland China."
    },
    ziv: {
      name: "Zenius-I-Vanisher",
      desc: "Community arcade database with worldwide coverage."
    },
    round1usa: {
      name: "Round1 USA",
      desc: "Official Round1 venue list for the United States."
    },
    community: {
      name: "Community",
      desc: "Entries curated by hand in this repository."
    }
  };

  /* Our own persisted keys and their defaults. Location features default on:
     nothing asks the browser for a position until the user acts, so the
     toggle hides the feature rather than gating a permission prompt. */
  var PREFS = [
    { key: "markerScaling", def: true },
    { key: "locationEnabled", def: true }
  ];

  /* Marker size classes are read from markers.js (which exports SIZE_CLASSES
     and UNKNOWN_CLASS for exactly this) rather than copied here: a legend that
     states its own thresholds silently starts lying the moment the marker
     layer retunes them, and this legend had already drifted (it read "2 to 4"
     and "5 to 9" against real bands of 3-6 and 7-12).
     Diameter is 2x the canvas radius. Unknown is deliberately the middle
     size, never the smallest. */
  function sizeClasses() {
    var src = (AM.markers && AM.markers.SIZE_CLASSES) || [];
    return src.map(function (c) {
      var lo = c.min, hi = c.max;
      var label;
      if (!isFinite(hi)) label = lo + " or more cabinets";
      else if (lo === hi) label = lo + (lo === 1 ? " cabinet" : " cabinets");
      else label = lo + " to " + hi + " cabinets";
      return { d: c.r * 2, label: label, glow: !!c.glow };
    });
  }

  function unknownDiameter() {
    var u = AM.markers && AM.markers.UNKNOWN_CLASS;
    return u ? u.r * 2 : 12;
  }

  var SECTIONS = [
    { id: "sources", label: "Sources" },
    { id: "display", label: "Display" },
    { id: "location", label: "Location" },
    { id: "about", label: "About" }
  ];

  var gearBtn = null, dlg = null, currentSection = "sources";
  var legendWrap = null, legendBtn = null, legendBody = null, legendOpen = false;

  /* ---------- small builders ---------- */

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  /* One settings row: label, one-line description, switch on the right.
     The whole row is a <label> wrapping a real checkbox, so pointer, keyboard
     and screen-reader behaviour all come from the native control. */
  function switchRow(opts) {
    var row = el("label", "sd-row");
    var text = el("span", "sd-row-text");
    var head = el("span", "sd-row-label");
    head.appendChild(document.createTextNode(opts.label));
    if (opts.count != null) {
      var n = el("span", "sd-count tabnum", U.num(opts.count));
      n.title = "stores from this source, including entries without coordinates";
      head.appendChild(n);
    }
    text.appendChild(head);
    text.appendChild(el("span", "sd-row-desc", opts.desc));

    var sw = el("span", "sd-switch");
    var input = document.createElement("input");
    input.type = "checkbox";
    input.checked = !!opts.checked;
    if (opts.name) input.dataset.pref = opts.name;
    input.addEventListener("change", function () { opts.onChange(input.checked); });
    sw.appendChild(input);
    sw.appendChild(el("span", "sd-track"));

    row.appendChild(text);
    row.appendChild(sw);
    return { row: row, input: input };
  }

  function sectionHead(title, note) {
    var wrap = el("div", "sd-sec-head");
    wrap.appendChild(el("h3", null, title));
    if (note) wrap.appendChild(el("p", "sd-sec-note", note));
    return wrap;
  }

  /* A sample marker dot at a given diameter, drawn like the map markers. */
  function sampleDot(d) {
    var dot = el("span", "sd-dot");
    dot.style.width = d + "px";
    dot.style.height = d + "px";
    return dot;
  }

  /* ---------- panes ---------- */

  var srcInputs = {};

  function buildSourcesPane(pane) {
    pane.appendChild(sectionHead("Data sources",
      "Turn a source off to hide its stores. A store listed by more than one source stays on the map while any of them is on."));

    var enabled = AM.state.get("enabledSources") || new Set();
    var counts = AM.data.srcCounts || {};
    AM.data.srcInData.forEach(function (s) {
      var info = SRC_INFO[s] || { name: C.SRC_LABEL[s] || s, desc: "Additional data source." };
      var r = switchRow({
        label: info.name,
        desc: info.desc,
        count: counts[s],
        checked: enabled.has(s),
        onChange: function () { AM.state.toggleSource(s); }
      });
      srcInputs[s] = r.input;
      pane.appendChild(r.row);
    });

    var live = el("p", "sd-live");
    live.id = "sd-shown";
    pane.appendChild(live);
    syncShown();
  }

  function buildDisplayPane(pane) {
    pane.appendChild(sectionHead("Display"));
    pane.appendChild(prefRow("markerScaling", "Marker size by cabinet count",
      "Draw busier stores as larger dots. Stores with no published count stay medium, never smallest.").row);
  }

  function buildLocationPane(pane) {
    pane.appendChild(sectionHead("Location"));
    pane.appendChild(prefRow("locationEnabled", "Enable location features",
      "Show the locate button and the list of arcades nearest to you.").row);
    var note = el("p", "sd-note");
    note.appendChild(el("strong", null, "Your location never leaves the browser."));
    note.appendChild(document.createTextNode(
      " It is read only after you ask for it, used on this page to sort stores by distance, and is never uploaded, stored or shared. This site has no server and no analytics."));
    pane.appendChild(note);
  }

  function prefRow(key, label, desc) {
    var r = switchRow({
      label: label,
      desc: desc,
      name: key,
      checked: !!AM.state.get(key),
      onChange: function (on) { setPref(key, on); }
    });
    return r;
  }

  function buildAboutPane(pane) {
    pane.appendChild(sectionHead("Legend"));

    /* marker sizes */
    pane.appendChild(el("p", "sd-sub", "Dot size: total cabinets at the store"));
    var sizes = el("div", "sd-sizes");
    sizeClasses().forEach(function (sc) {
      var item = el("div", "sd-size");
      item.appendChild(sampleDot(sc.d));
      item.appendChild(el("span", null, sc.label));
      sizes.appendChild(item);
    });
    var unknown = el("div", "sd-size");
    unknown.appendChild(sampleDot(unknownDiameter()));
    unknown.appendChild(el("span", null, "Count unknown (drawn medium)"));
    sizes.appendChild(unknown);
    pane.appendChild(sizes);
    pane.appendChild(el("p", "sd-note",
      "Most official listings publish which games a store has but not how many cabinets, so an unknown count is drawn at the middle size rather than the smallest. Sizing follows the Display setting."));

    /* game colours */
    pane.appendChild(el("p", "sd-sub", "Dot colour: game at the store"));
    pane.appendChild(el("p", "sd-note",
      "A store with several games takes the colour of the first selected game it has, in the order below."));
    var grid = el("div", "sd-colors");
    AM.data.gamesInData.forEach(function (g) {
      var item = el("div", "sd-color");
      var sw = el("span", "sd-swatch");
      sw.style.background = C.GAME_COLOR[g] || C.GAME_COLOR.other;
      item.appendChild(sw);
      item.appendChild(el("span", "sd-color-name", C.GAME_LABEL[g] || g));
      item.appendChild(el("span", "sd-count tabnum", U.num((AM.data.gameCounts || {})[g] || 0)));
      grid.appendChild(item);
    });
    pane.appendChild(grid);

    /* source badges */
    pane.appendChild(el("p", "sd-sub", "Badges in a store popup"));
    var badges = el("div", "sd-badges");
    AM.data.srcInData.forEach(function (s) {
      var info = SRC_INFO[s] || { name: C.SRC_LABEL[s] || s, desc: "" };
      var item = el("div", "sd-badge-row");
      item.appendChild(el("span", "badge", C.SRC_LABEL[s] || s));
      item.appendChild(el("span", "sd-badge-txt", info.name + ". " + info.desc));
      badges.appendChild(item);
    });
    var cabBadge = el("div", "sd-badge-row");
    cabBadge.appendChild(el("span", "badge cab", "Lightning"));
    cabBadge.appendChild(el("span", "sd-badge-txt",
      "Yellow badges mark special cabinet variants: Valkyrie, Lightning, DDR gold, GITADORA Arena, pop'n Pikapika."));
    badges.appendChild(cabBadge);
    pane.appendChild(badges);

    /* data + links */
    pane.appendChild(sectionHead("About this map"));
    var upd = (AM.data.raw && AM.data.raw.updated) ? AM.data.raw.updated : "unknown";
    var stats = el("p", "sd-note tabnum");
    stats.textContent = U.num(AM.data.arcades.length) + " stores, " +
      U.num(AM.data.plottable.length) + " with coordinates. Data updated " + upd + ".";
    pane.appendChild(stats);

    var links = el("p", "sd-links");
    links.innerHTML =
      '<a href="' + esc(C.REPO_URL) + '" target="_blank" rel="noopener">Source code on GitHub</a>' +
      '<a href="' + esc(C.REPO_URL) + '/tree/main/docs" target="_blank" rel="noopener">Data sources</a>' +
      '<a href="' + esc(C.REPO_URL) + '/blob/main/LICENSE" target="_blank" rel="noopener">MIT licence</a>';
    pane.appendChild(links);
    pane.appendChild(el("p", "sd-note",
      "Map data (c) OpenStreetMap contributors, ODbL. Store listings belong to their respective sources and are aggregated here for convenience. Chinese coordinates are converted from GCJ-02 and are approximate."));
  }

  /* ---------- preferences ---------- */

  /* state.set alone does not persist an arbitrary key: state.js only mirrors
     enabledSources by itself. Every preference write must do both. */
  function setPref(key, val) {
    AM.state.set(key, val);
    AM.state.writeSetting(key, val);
  }

  function seedPrefs() {
    PREFS.forEach(function (p) {
      var stored = AM.state.readSetting(p.key, p.def);
      AM.state.set(p.key, stored === true || stored === false ? stored : p.def);
    });
  }

  /* ---------- the dialog ---------- */

  function buildDialog() {
    dlg = document.createElement("dialog");
    dlg.id = "settings-dialog";
    dlg.setAttribute("aria-labelledby", "sd-title");

    var inner = el("div", "sd-inner");

    var head = el("div", "sd-head");
    var h2 = el("h2", null, "Settings");
    h2.id = "sd-title";
    head.appendChild(h2);
    var close = el("button", "sd-close");
    close.type = "button";
    close.setAttribute("aria-label", "Close settings");
    close.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M18.3 5.71 12 12l6.3 6.29-1.41 1.42L10.59 13.4 4.3 19.71 2.88 18.3 9.17 12 2.88 5.71 4.3 4.29l6.29 6.3 6.3-6.3z"/></svg>';
    close.addEventListener("click", function () { closeDialog(); });
    head.appendChild(close);
    inner.appendChild(head);

    var body = el("div", "sd-body");
    var nav = el("div", "sd-nav");
    nav.setAttribute("role", "tablist");
    nav.setAttribute("aria-label", "Settings sections");
    var panes = el("div", "sd-panes");

    SECTIONS.forEach(function (sec, i) {
      var tab = el("button", "sd-tab", sec.label);
      tab.type = "button";
      tab.id = "sd-tab-" + sec.id;
      tab.dataset.sec = sec.id;
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", "sd-pane-" + sec.id);
      tab.setAttribute("aria-selected", i === 0 ? "true" : "false");
      if (i === 0) { tab.classList.add("on"); tab.autofocus = true; }
      tab.addEventListener("click", function () { showSection(sec.id); });
      nav.appendChild(tab);

      var pane = el("div", "sd-pane");
      pane.id = "sd-pane-" + sec.id;
      pane.setAttribute("role", "tabpanel");
      pane.setAttribute("aria-labelledby", tab.id);
      pane.hidden = i !== 0;
      panes.appendChild(pane);
    });

    nav.addEventListener("keydown", onNavKey);
    body.appendChild(nav);
    body.appendChild(panes);
    inner.appendChild(body);
    dlg.appendChild(inner);
    document.body.appendChild(dlg);

    buildSourcesPane($("sd-pane-sources"));
    buildDisplayPane($("sd-pane-display"));
    buildLocationPane($("sd-pane-location"));
    buildAboutPane($("sd-pane-about"));

    /* Click on the dialog element itself means the backdrop: the whole visible
       card is .sd-inner and the dialog has no padding of its own. */
    dlg.addEventListener("click", function (e) {
      if (e.target === dlg) closeDialog();
    });
    /* Esc fires cancel then close; restoring focus on close covers both. */
    dlg.addEventListener("close", function () {
      if (gearBtn) gearBtn.focus();
    });
  }

  function onNavKey(e) {
    var k = e.key;
    if (k !== "ArrowDown" && k !== "ArrowRight" && k !== "ArrowUp" && k !== "ArrowLeft") return;
    var idx = -1;
    for (var i = 0; i < SECTIONS.length; i++) {
      if (SECTIONS[i].id === currentSection) { idx = i; break; }
    }
    if (idx === -1) return;
    var step = (k === "ArrowDown" || k === "ArrowRight") ? 1 : -1;
    var next = SECTIONS[(idx + step + SECTIONS.length) % SECTIONS.length].id;
    e.preventDefault();
    showSection(next);
    var btn = $("sd-tab-" + next);
    if (btn) btn.focus();
  }

  function showSection(id) {
    currentSection = id;
    SECTIONS.forEach(function (sec) {
      var on = sec.id === id;
      var tab = $("sd-tab-" + sec.id), pane = $("sd-pane-" + sec.id);
      if (tab) {
        tab.classList.toggle("on", on);
        tab.setAttribute("aria-selected", on ? "true" : "false");
      }
      if (pane) {
        pane.hidden = !on;
        if (on) pane.scrollTop = 0;
      }
    });
  }

  function openDialog() {
    if (!dlg || dlg.open) return;
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
    showSection(currentSection);
  }

  function closeDialog() {
    if (!dlg || !dlg.open) return;
    if (typeof dlg.close === "function") dlg.close();
    else {
      dlg.removeAttribute("open");
      if (gearBtn) gearBtn.focus();
    }
  }

  function buildGear() {
    gearBtn = el("button", "sd-gear");
    gearBtn.id = "settings-btn";
    gearBtn.type = "button";
    gearBtn.title = "Settings";
    gearBtn.setAttribute("aria-label", "Settings");
    gearBtn.setAttribute("aria-haspopup", "dialog");
    gearBtn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M19.14 12.94a7.6 7.6 0 0 0 0-1.88l2.03-1.58a.5.5 0 0 0 .12-.62l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.3 7.3 0 0 0-1.62-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54c-.58.24-1.12.55-1.62.94l-2.39-.96a.5.5 0 0 0-.6.22L2.67 8.86a.5.5 0 0 0 .12.62l2.03 1.58a7.6 7.6 0 0 0 0 1.88l-2.03 1.58a.5.5 0 0 0-.12.62l1.92 3.32c.12.22.38.3.6.22l2.39-.96c.5.39 1.04.7 1.62.94l.36 2.54c.04.24.25.42.5.42h3.84c.25 0 .46-.18.5-.42l.36-2.54c.58-.24 1.12-.55 1.62-.94l2.39.96c.22.08.48 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.62zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z"/></svg>';
    gearBtn.addEventListener("click", openDialog);
    var anchor = $("repo-link");
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(gearBtn, anchor);
    else document.getElementById("topbar").appendChild(gearBtn);
  }

  /* ---------- on-map legend chip ---------- */
  /* A collapsed pill in the map's bottom-left corner. Its expanded state is
     deliberately not persisted: it is a glance, not a preference. */

  function buildLegendChip() {
    legendWrap = el("div", "legend-chip");

    legendBtn = el("button", "legend-toggle");
    legendBtn.type = "button";
    legendBtn.id = "legend-toggle";
    legendBtn.setAttribute("aria-expanded", "false");
    legendBtn.setAttribute("aria-controls", "legend-body");
    legendBtn.innerHTML = '<span class="legend-key" aria-hidden="true"></span>Legend';
    legendBtn.addEventListener("click", function () { toggleLegend(); });

    legendBody = el("div", "legend-body");
    legendBody.id = "legend-body";
    legendBody.hidden = true;

    legendBody.appendChild(el("p", "legend-sub", "Size: cabinets at the store"));
    var sizes = el("div", "legend-sizes");
    /* Three ticks (smallest, middle, largest) sampled from the real class
       table, so the short labels cannot drift from the bands the map draws.
       Full ranges live in Settings > About. */
    var all = sizeClasses();
    var raw = (AM.markers && AM.markers.SIZE_CLASSES) || [];
    var ticks = all.length ? [0, Math.floor((all.length - 1) / 2), all.length - 1] : [];
    ticks.forEach(function (i, n) {
      if (n > 0 && ticks[n - 1] === i) return;   /* very short tables */
      var sc = all[i], c = raw[i];
      var short = !isFinite(c.max) ? c.min + "+"
        : (c.min === c.max ? String(c.min) : c.min + "-" + c.max);
      var item = el("div", "legend-size");
      item.appendChild(sampleDot(sc.d));
      item.appendChild(el("span", null, short));
      item.title = sc.label;
      sizes.appendChild(item);
    });
    var unk = el("div", "legend-size");
    unk.appendChild(sampleDot(unknownDiameter()));
    unk.appendChild(el("span", null, "?"));
    unk.title = "count unknown, drawn medium";
    sizes.appendChild(unk);
    legendBody.appendChild(sizes);

    legendBody.appendChild(el("p", "legend-sub", "Colour: game"));
    var grid = el("div", "legend-colors");
    AM.data.gamesInData.forEach(function (g) {
      var item = el("div", "legend-color");
      var sw = el("span", "sd-swatch");
      sw.style.background = C.GAME_COLOR[g] || C.GAME_COLOR.other;
      item.appendChild(sw);
      item.appendChild(el("span", null, C.GAME_LABEL[g] || g));
      grid.appendChild(item);
    });
    legendBody.appendChild(grid);

    var more = el("button", "legend-more", "Full legend in Settings");
    more.type = "button";
    more.addEventListener("click", function () {
      collapseLegend();
      currentSection = "about";
      openDialog();
    });
    legendBody.appendChild(more);

    legendWrap.appendChild(legendBody);
    legendWrap.appendChild(legendBtn);

    var Ctl = L.Control.extend({
      options: { position: "bottomleft" },
      onAdd: function () { return legendWrap; }
    });
    AM.map.map.addControl(new Ctl());
    /* Without these the pill drags/zooms the map underneath it. */
    L.DomEvent.disableClickPropagation(legendWrap);
    L.DomEvent.disableScrollPropagation(legendWrap);

    /* disableClickPropagation only stops mousedown/touchstart/dblclick/
       contextmenu (it flags the element so Leaflet ignores the click); the
       click event itself still bubbles to the document. Without the contains
       check the chip's own opening click would immediately close it again. */
    document.addEventListener("click", function (e) {
      if (legendOpen && !legendWrap.contains(e.target)) collapseLegend();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && legendOpen) {
        collapseLegend();
        legendBtn.focus();
      }
    });
  }

  function toggleLegend() {
    if (legendOpen) collapseLegend(); else expandLegend();
  }

  function expandLegend() {
    legendOpen = true;
    legendBody.hidden = false;
    legendWrap.classList.add("open");
    legendBtn.setAttribute("aria-expanded", "true");
  }

  function collapseLegend() {
    legendOpen = false;
    legendBody.hidden = true;
    legendWrap.classList.remove("open");
    legendBtn.setAttribute("aria-expanded", "false");
  }

  /* ---------- syncing ---------- */

  function syncSources() {
    var enabled = AM.state.get("enabledSources") || new Set();
    Object.keys(srcInputs).forEach(function (s) {
      var want = enabled.has(s);
      if (srcInputs[s].checked !== want) srcInputs[s].checked = want;
    });
  }

  function syncPrefs() {
    PREFS.forEach(function (p) {
      var input = dlg && dlg.querySelector('input[data-pref="' + p.key + '"]');
      if (!input) return;
      var want = !!AM.state.get(p.key);
      if (input.checked !== want) input.checked = want;
    });
  }

  function syncShown() {
    var live = $("sd-shown");
    if (!live) return;
    live.textContent = U.num(AM.state.get("shownCount")) + " of " +
      U.num(AM.data.plottable.length) + " mappable stores shown with the current filters.";
  }

  /* ---------- wiring ---------- */

  function build() {
    seedPrefs();
    buildGear();
    buildDialog();
    buildLegendChip();
  }

  function start() {
    AM.state.on("enabledSources", syncSources);
    AM.state.on("shownCount", syncShown);
    PREFS.forEach(function (p) { AM.state.on(p.key, syncPrefs); });
    syncSources();
    syncPrefs();
    syncShown();
  }

  AM.settings = {
    build: build,
    start: start,
    open: openDialog,
    close: closeDialog,
    showSection: showSection,
    expandLegend: expandLegend,
    collapseLegend: collapseLegend,
    isLegendOpen: function () { return legendOpen; },
    dialog: function () { return dlg; }
  };
})(window.AM);
