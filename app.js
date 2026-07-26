/* Arcade Maps - static Leaflet front end. No build step, all deps vendored. */
(function () {
  "use strict";

  var DATA_URL = "data/arcades.json";
  var REPO_URL = "https://github.com/JonathanLiu1401/Arcade-Maps";

  /* Canonical game order, labels, marker colors (distinct on light tiles). */
  var GAMES = [
    ["maimai_dx", "maimai DX", "#E4007F"],
    ["chunithm", "CHUNITHM", "#F7A400"],
    ["ongeki", "O.N.G.E.K.I.", "#9B59B6"],
    ["project_diva", "Project DIVA", "#39C5BB"],
    ["sdvx", "SOUND VOLTEX", "#1E88E5"],
    ["iidx", "beatmania IIDX", "#546E7A"],
    ["ddr", "DDR", "#F4511E"],
    ["polaris_chord", "Polaris Chord", "#4FC3F7"],
    ["gitadora", "GITADORA", "#8D6E63"],
    ["jubeat", "jubeat", "#43A047"],
    ["popn", "pop'n music", "#EC407A"],
    ["nostalgia", "NOSTALGIA", "#B39DDB"],
    ["drs", "DANCERUSH", "#26C6DA"],
    ["dance_around", "DANCE aROUND", "#FFB300"],
    ["dance_evo", "Dance Evolution", "#9CCC65"],
    ["museca", "MUSECA", "#7E57C2"],
    ["reflec", "REFLEC BEAT", "#EF5350"],
    ["taiko", "Taiko no Tatsujin", "#D32F2F"],
    ["other", "Other", "#9E9E9E"]
  ];
  var GAME_LABEL = {}, GAME_COLOR = {}, GAME_ORDER = [];
  GAMES.forEach(function (g, i) {
    GAME_ORDER.push(g[0]); GAME_LABEL[g[0]] = g[1]; GAME_COLOR[g[0]] = g[2];
  });

  /* Cab-variant filters: id, label, game restricted, matching cab slugs. */
  var CAB_FILTERS = [
    { id: "sdvx_vm", label: "Valkyrie model", game: "sdvx", slugs: ["sdvx_vm"] },
    { id: "iidx_lm", label: "Lightning model", game: "iidx", slugs: ["iidx_lm"] },
    { id: "ddr_gold", label: "DDR gold cab", game: "ddr", slugs: ["ddr_gold"] },
    { id: "gitadora_arena", label: "GITADORA Arena", game: "gitadora",
      slugs: ["gitadora_gf_arena", "gitadora_dm_arena"] },
    { id: "popn_pikapika", label: "pop'n Pikapika", game: "popn", slugs: ["popn_pikapika"] }
  ];
  var CAB_BADGE = {
    sdvx_vm: "Valkyrie", iidx_lm: "Lightning", ddr_gold: "DDR gold",
    gitadora_gf_arena: "GF Arena", gitadora_dm_arena: "DM Arena",
    popn_pikapika: "Pikapika"
  };
  var SRC_LABEL = {
    allnet: "ALL.Net", eagate: "e-amusement", wahlap: "WAHLAP", ziv: "ZIv",
    round1usa: "Round1 USA", bemanicn: "BemaniCN", community: "community"
  };

  var REDUCED = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- state ---------- */
  var arcades = [];          /* all entries */
  var plottable = [];        /* entries with usable coords */
  var coordless = [];        /* no-coords-list entries */
  var markerOf = {};         /* id -> L.circleMarker */
  var selGames = null;       /* Set of selected game slugs */
  var selCabs = new Set();   /* Set of checked CAB_FILTERS ids */
  var gamesInData = [];      /* game slugs present, canonical order */
  var shownCount = 0;

  var $ = function (id) { return document.getElementById(id); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function hasCoords(a) {
    return typeof a.lat === "number" && typeof a.lng === "number" &&
      !(a.lat === 0 && a.lng === 0);
  }
  function gmapsSearchUrl(a) {
    return "https://www.google.com/maps/search/?api=1&query=" +
      encodeURIComponent(a.name + " " + (a.addr || ""));
  }

  /* ---------- map ---------- */
  var map = L.map("map", {
    zoomControl: true,
    worldCopyJump: true,
    fadeAnimation: !REDUCED,
    zoomAnimation: !REDUCED,
    markerZoomAnimation: !REDUCED
  });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  var renderer = L.canvas({ padding: 0.5 });
  var cluster = L.markerClusterGroup({
    chunkedLoading: true,
    disableClusteringAtZoom: 16,
    spiderfyOnMaxZoom: false,
    showCoverageOnHover: false,
    maxClusterRadius: function (zoom) {
      return zoom >= 13 ? 32 : zoom >= 10 ? 46 : 60;
    },
    iconCreateFunction: function (c) {
      var n = c.getChildCount();
      var size = n < 10 ? 30 : n < 100 ? 36 : 44;
      return L.divIcon({
        html: '<div class="cl-ico" style="width:' + size + "px;height:" + size + 'px">' + n + "</div>",
        className: "", iconSize: [size, size]
      });
    }
  });
  map.addLayer(cluster);

  /* ---------- filter logic ---------- */
  /* Does arcade a count as a hit for game g under the current cab filters? */
  function matchesForGame(a, g) {
    if (a.games.indexOf(g) === -1) return false;
    for (var i = 0; i < CAB_FILTERS.length; i++) {
      var cf = CAB_FILTERS[i];
      if (cf.game !== g || !selCabs.has(cf.id)) continue;
      var ok = false;
      for (var j = 0; j < cf.slugs.length; j++) {
        if (a.cabs && a.cabs.indexOf(cf.slugs[j]) !== -1) { ok = true; break; }
      }
      if (!ok) return false;
    }
    return true;
  }
  /* First selected+matching game in the arcade's own games order, or null. */
  function displayGame(a) {
    for (var i = 0; i < a.games.length; i++) {
      var g = a.games[i];
      if (selGames.has(g) && matchesForGame(a, g)) return g;
    }
    return null;
  }

  function applyFilters() {
    var vis = [];
    for (var i = 0; i < plottable.length; i++) {
      var a = plottable[i];
      var g = displayGame(a);
      if (!g) continue;
      var m = markerOf[a.id];
      var color = GAME_COLOR[g] || GAME_COLOR.other;
      if (m.options.fillColor !== color) m.setStyle({ fillColor: color });
      vis.push(m);
    }
    cluster.clearLayers();
    if (vis.length) cluster.addLayers(vis);
    shownCount = vis.length;
    $("meta-count").textContent = shownCount.toLocaleString("en-US") + " shown";
    updateChipStates();
    scheduleHashUpdate();
  }

  function updateChipStates() {
    var chips = $("game-chips").children;
    for (var i = 0; i < chips.length; i++) {
      var slug = chips[i].dataset.g;
      chips[i].classList.toggle("on", selGames.has(slug));
      chips[i].setAttribute("aria-pressed", selGames.has(slug) ? "true" : "false");
    }
  }

  /* ---------- popup ---------- */
  function popupHtml(a) {
    var h = '<div class="pp-name">' + esc(a.name) + "</div>";
    h += '<div class="pp-addr">' + esc(a.addr || "") +
      (a.pref ? " · " + esc(a.pref) : "") + " · " + esc(a.country) + "</div>";
    h += '<div class="pp-row">';
    a.games.forEach(function (g) {
      h += '<span class="gc" style="--c:' + (GAME_COLOR[g] || GAME_COLOR.other) + '">' +
        esc(GAME_LABEL[g] || g) + "</span>";
    });
    h += "</div>";
    if (a.cabs && a.cabs.length) {
      h += '<div class="pp-row">';
      a.cabs.forEach(function (c) {
        h += '<span class="badge cab">' + esc(CAB_BADGE[c] || c) + "</span>";
      });
      h += "</div>";
    }
    if (a.src && a.src.length) {
      h += '<div class="pp-row">';
      a.src.forEach(function (s) {
        var label = esc(SRC_LABEL[s] || s);
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
    var gm = (a.links && a.links.gmaps) ? a.links.gmaps : gmapsSearchUrl(a);
    h += '<a class="pp-gmaps" target="_blank" rel="noopener" href="' + esc(gm) +
      '">Open in Google Maps</a>';
    return h;
  }

  /* ---------- data load ---------- */
  fetch(DATA_URL)
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + " loading " + DATA_URL);
      return r.json();
    })
    .then(init)
    .catch(function (e) {
      $("meta-count").textContent = "data load failed";
      $("meta-count").title = String(e);
      console.error("Arcade Maps: data load failed", e);
      map.setView([30, 135], 3);
    });

  function init(data) {
    arcades = data.arcades || [];
    $("meta-updated").textContent = "updated " + (data.updated || "?");

    var present = new Set();
    arcades.forEach(function (a) {
      if (!a.games || !a.games.length) a.games = ["other"];
      a.games.forEach(function (g) { present.add(g); });
      if (hasCoords(a)) plottable.push(a); else coordless.push(a);
    });
    gamesInData = GAME_ORDER.filter(function (g) { return present.has(g); });
    /* Any non-canonical slugs go last so their stores stay reachable. */
    present.forEach(function (g) {
      if (gamesInData.indexOf(g) === -1) gamesInData.push(g);
    });

    /* markers */
    plottable.forEach(function (a) {
      var m = L.circleMarker([a.lat, a.lng], {
        renderer: renderer, radius: 7, weight: 1.5, color: "#ffffff",
        opacity: 0.9, fillColor: GAME_COLOR.other, fillOpacity: 0.92
      });
      m.bindPopup(function () { return popupHtml(a); }, { maxWidth: 320 });
      markerOf[a.id] = m;
    });

    var st = parseHash();
    selGames = st.games || new Set(gamesInData);
    selCabs = st.cabs || new Set();
    if (st.view) map.setView([st.view.lat, st.view.lng], st.view.z);
    else if (plottable.length) {
      map.fitBounds(L.latLngBounds(plottable.map(function (a) {
        return [a.lat, a.lng];
      })), { padding: [30, 30], maxZoom: 7 });
    } else map.setView([30, 135], 3);

    buildChips();
    buildCabFilters();
    buildChinaList();
    buildFooter(data);
    buildSearch();
    applyFilters();
    map.on("moveend", scheduleHashUpdate);
  }

  /* ---------- UI: game chips ---------- */
  function buildChips() {
    var counts = {};
    arcades.forEach(function (a) {
      a.games.forEach(function (g) { counts[g] = (counts[g] || 0) + 1; });
    });
    var box = $("game-chips");
    gamesInData.forEach(function (g) {
      var b = document.createElement("button");
      b.className = "chip";
      b.dataset.g = g;
      b.style.setProperty("--c", GAME_COLOR[g] || GAME_COLOR.other);
      b.innerHTML = '<span class="dot"></span>' + esc(GAME_LABEL[g] || g) +
        ' <span class="n tabnum">' + (counts[g] || 0).toLocaleString("en-US") + "</span>";
      b.addEventListener("click", function () {
        if (selGames.has(g)) selGames.delete(g); else selGames.add(g);
        applyFilters();
      });
      box.appendChild(b);
    });
    $("games-all").addEventListener("click", function () {
      selGames = new Set(gamesInData); applyFilters();
    });
    $("games-none").addEventListener("click", function () {
      selGames = new Set(); applyFilters();
    });
  }

  /* ---------- UI: cab filters ---------- */
  function buildCabFilters() {
    var box = $("cab-filters");
    CAB_FILTERS.forEach(function (cf) {
      var lab = document.createElement("label");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selCabs.has(cf.id);
      cb.addEventListener("change", function () {
        if (cb.checked) selCabs.add(cf.id); else selCabs.delete(cf.id);
        applyFilters();
      });
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(" " + cf.label + " "));
      var tag = document.createElement("span");
      tag.className = "cabgame";
      tag.textContent = GAME_LABEL[cf.game] || cf.game;
      lab.appendChild(tag);
      lab.dataset.cab = cf.id;
      box.appendChild(lab);
    });
  }

  /* ---------- UI: no-coords list (grouped country + province) ---------- */
  function buildChinaList() {
    var box = $("china-list");
    if (!coordless.length) {
      box.innerHTML = '<p class="hint">No entries without coordinates.</p>';
      return;
    }
    var byProv = {};
    coordless.forEach(function (a) {
      var p = (a.country || "Unknown") +
        (a.pref ? " · " + a.pref : "");
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
        h += '<div class="cn-item" id="cn-' + a.id + '">' +
          '<div class="nm">' + esc(a.name) + "</div>" +
          '<div class="ad">' + esc(a.addr || "") + "</div>" +
          '<div class="gchips">' + a.games.map(function (g) {
            return '<span class="gc" style="--c:' +
              (GAME_COLOR[g] || GAME_COLOR.other) + '">' +
              esc(GAME_LABEL[g] || g) + "</span>";
          }).join("") + "</div>" +
          '<a target="_blank" rel="noopener" href="' + esc(gmapsSearchUrl(a)) +
          '">Search in Google Maps</a></div>';
      });
    });
    box.innerHTML = h;
  }

  function showChinaEntry(a) {
    openDrawer();
    switchTab("china");
    var el = $("cn-" + a.id);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: REDUCED ? "auto" : "smooth" });
    document.querySelectorAll(".cn-item.flash").forEach(function (n) {
      n.classList.remove("flash");
    });
    el.classList.add("flash");
  }

  /* ---------- UI: footer ---------- */
  function buildFooter(data) {
    var counts = {};
    arcades.forEach(function (a) {
      (a.src || []).forEach(function (s) { counts[s] = (counts[s] || 0) + 1; });
    });
    var order = ["allnet", "eagate", "wahlap", "ziv", "round1usa", "bemanicn", "community"];
    Object.keys(counts).forEach(function (s) {
      if (order.indexOf(s) === -1) order.push(s);
    });
    $("src-counts").innerHTML = order.filter(function (s) { return counts[s]; })
      .map(function (s) {
        return "<span>" + esc(SRC_LABEL[s] || s) + " " +
          counts[s].toLocaleString("en-US") + "</span>";
      }).join("") +
      "<span>" + arcades.length.toLocaleString("en-US") + " stores total</span>";
  }

  /* ---------- search ---------- */
  var searchIndex = [];
  function buildSearch() {
    searchIndex = arcades.map(function (a) {
      return { a: a, hay: (a.name + " " + (a.addr || "")).toLowerCase() };
    });
    var input = $("search"), list = $("search-results");
    var results = [], selIdx = -1, tmr = null;

    function close() {
      list.hidden = true; input.setAttribute("aria-expanded", "false");
      selIdx = -1;
    }
    function render() {
      if (!results.length) {
        list.innerHTML = '<li class="r-none">No matches</li>';
        list.hidden = false; input.setAttribute("aria-expanded", "true");
        return;
      }
      list.innerHTML = results.map(function (r, i) {
        return '<li role="option" data-i="' + i + '"' +
          (i === selIdx ? ' class="sel"' : "") + ">" +
          '<span class="r-name">' + esc(r.a.name) + "</span>" +
          '<span class="r-addr">' + esc(r.a.addr || "") + "</span>" +
          '<span class="r-country">' + esc(r.a.country || "?") + "</span></li>";
      }).join("");
      list.hidden = false; input.setAttribute("aria-expanded", "true");
    }
    function run() {
      var q = input.value.trim().toLowerCase();
      if (!q) { close(); return; }
      results = [];
      for (var i = 0; i < searchIndex.length && results.length < 20; i++) {
        if (searchIndex[i].hay.indexOf(q) !== -1) results.push(searchIndex[i]);
      }
      selIdx = -1;
      render();
    }
    function pick(i) {
      var a = results[i] && results[i].a;
      if (!a) return;
      close();
      input.blur();
      if (hasCoords(a)) {
        var ll = [a.lat, a.lng];
        if (REDUCED) map.setView(ll, 16); else map.flyTo(ll, 16, { duration: 0.9 });
        L.popup({ maxWidth: 320 }).setLatLng(ll).setContent(popupHtml(a)).openOn(map);
      } else {
        showChinaEntry(a);
      }
    }
    input.addEventListener("input", function () {
      clearTimeout(tmr); tmr = setTimeout(run, 120);
    });
    input.addEventListener("keydown", function (e) {
      if (list.hidden) return;
      if (e.key === "ArrowDown") { selIdx = Math.min(selIdx + 1, results.length - 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { selIdx = Math.max(selIdx - 1, 0); render(); e.preventDefault(); }
      else if (e.key === "Enter") { pick(selIdx >= 0 ? selIdx : 0); e.preventDefault(); }
      else if (e.key === "Escape") { close(); }
    });
    list.addEventListener("mousedown", function (e) {
      var li = e.target.closest("li[data-i]");
      if (li) { pick(+li.dataset.i); e.preventDefault(); }
    });
    document.addEventListener("click", function (e) {
      if (!$("searchwrap").contains(e.target)) close();
    });
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
  $("tab-filters").addEventListener("click", function () { switchTab("filters"); });
  $("tab-china").addEventListener("click", function () { switchTab("china"); });

  function openDrawer() {
    document.body.classList.remove("drawer-closed");
    $("drawer-toggle").setAttribute("aria-expanded", "true");
  }
  $("drawer-toggle").addEventListener("click", function () {
    var closed = document.body.classList.toggle("drawer-closed");
    this.setAttribute("aria-expanded", closed ? "false" : "true");
    map.invalidateSize();
  });
  if (window.matchMedia && window.matchMedia("(max-width: 760px)").matches) {
    document.body.classList.add("drawer-closed");
    $("drawer-toggle").setAttribute("aria-expanded", "false");
  }

  /* ---------- URL hash state ---------- */
  /* Format: #z/lat/lng/games=a,b/cabs=x,y (games absent = all selected). */
  var hashTimer = null, applyingHash = false;
  function scheduleHashUpdate() {
    if (applyingHash) return;
    clearTimeout(hashTimer);
    hashTimer = setTimeout(writeHash, 250);
  }
  function writeHash() {
    if (!selGames) return;
    var c = map.getCenter();
    var parts = [
      map.getZoom(), c.lat.toFixed(5), c.lng.toFixed(5)
    ];
    if (selGames.size !== gamesInData.length) {
      parts.push("games=" + gamesInData.filter(function (g) {
        return selGames.has(g);
      }).join(","));
    }
    if (selCabs.size) {
      parts.push("cabs=" + CAB_FILTERS.filter(function (cf) {
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
  window.addEventListener("hashchange", function () {
    if (!selGames) return;
    applyingHash = true;
    var st = parseHash();
    selGames = st.games || new Set(gamesInData);
    selCabs = st.cabs || new Set();
    if (st.view) map.setView([st.view.lat, st.view.lng], st.view.z);
    document.querySelectorAll("#cab-filters input").forEach(function (cb) {
      cb.checked = selCabs.has(cb.parentElement.dataset.cab);
    });
    applyFilters();
    applyingHash = false;
  });

  /* exposed for testing */
  window.__arcadeMaps = {
    get shownCount() { return shownCount; },
    get selGames() { return selGames; },
    get selCabs() { return selCabs; },
    cluster: cluster, map: map
  };
})();
