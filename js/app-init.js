/* Arcade Maps - boot: fetch the data, seed state, build the UI, wire events. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts, U = AM.util;
  var $ = U.$;

  function ingest(data) {
    var D = AM.data;
    D.raw = data;
    D.arcades = data.arcades || [];

    var gamesPresent = new Set(), srcPresent = new Set();
    var gameCounts = {}, srcCounts = {};

    D.arcades.forEach(function (a) {
      if (!a.games || !a.games.length) a.games = ["other"];
      /* gameCounts is what the filter chips and the settings source list
         label themselves with, and both sit next to the map. Counting every
         row made the chip say "SOUND VOLTEX 1,097" while the omnibox row for
         the same game said 1,087: the omnibox counts what can actually be
         plotted (search.js visibleCountForGame walks AM.data.plottable), the
         chip counted the 221 coordless rows too. Same label, two numbers.
         Counting plottable rows only makes the chip agree with the omnibox in
         the default state; the coordless rows stay reachable through the
         no-coords tab, which carries its own counts. */
      var plot = U.hasCoords(a);
      a.games.forEach(function (g) {
        gamesPresent.add(g);
        if (plot) gameCounts[g] = (gameCounts[g] || 0) + 1;
      });
      (a.src || []).forEach(function (s) {
        srcPresent.add(s);
        srcCounts[s] = (srcCounts[s] || 0) + 1;
      });
      D.byId[a.id] = a;
      /* sid is the share-safe identity: derived from the venue's own source
         page url, so it survives the id renumbering every rebuild performs. */
      if (a.sid) D.bySid[a.sid] = a;
      if (U.hasCoords(a)) D.plottable.push(a); else D.coordless.push(a);
    });

    /* Canonical order first; any non-canonical slug goes last so its stores
       stay reachable rather than silently dropping out of the UI. */
    D.gamesInData = C.GAME_ORDER.filter(function (g) { return gamesPresent.has(g); });
    gamesPresent.forEach(function (g) {
      if (D.gamesInData.indexOf(g) === -1) D.gamesInData.push(g);
    });
    D.srcInData = C.SRC_ORDER.filter(function (s) { return srcPresent.has(s); });
    srcPresent.forEach(function (s) {
      if (D.srcInData.indexOf(s) === -1) D.srcInData.push(s);
    });

    D.gameCounts = gameCounts;
    D.srcCounts = srcCounts;
  }

  /* ---------- footer strip ---------- */

  /* The footer is a permanent flex row of seven source counts. At 390px wide
     that wraps to three lines and takes 79px off a 844px viewport - 9% of the
     phone screen, spent on provenance the visitor did not ask for, forever.

     Under 760px CSS collapses it to a single line and this adds the control
     that expands it. The button is created here rather than in index.html so
     the markup stays owned by one place, and it carries aria-expanded so the
     state is not conveyed by the caret glyph alone.

     Expanding changes #map's height, so Leaflet is told to re-measure or the
     tiles keep the old size and the markers drift off them. */
  function buildFooterToggle() {
    var foot = document.getElementById("foot");
    if (!foot) return;
    var btn = document.createElement("button");
    btn.id = "foot-toggle";
    btn.type = "button";
    btn.className = "foot-toggle";
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-label", "Show data source counts");
    btn.innerHTML = '<span class="ft-lb">sources</span>' +
      '<svg class="ft-cv" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">' +
      '<path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" ' +
      'stroke-linejoin="round" d="M6 15l6-6 6 6"/></svg>';
    btn.addEventListener("click", function () {
      var open = document.body.classList.toggle("foot-open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.setAttribute("aria-label",
        open ? "Hide data source counts" : "Show data source counts");
      /* The map column just changed height. */
      if (AM.map && AM.map.map) AM.map.map.invalidateSize();
    });
    foot.insertBefore(btn, foot.firstChild);
  }

  /* ---------- empty state ---------- */

  /* "0 shown" in the header is the only signal when every game filter is off,
     and on a phone the header count is easy to miss next to an empty map that
     looks like a failed tile load. A centred on-map hint says which of the two
     it is. It is CSS-drawn off this body class (see style.css .am-empty) so it
     cannot intercept map gestures.

     Toggled only from the state EVENT, never from the initial value: markers
     seed shownCount at 0 before the first applyFilters, and reacting to that
     would flash the hint on every cold load. */
  function watchEmptyState() {
    AM.state.on("shownCount", function (n) {
      document.body.classList.toggle("am-empty", n === 0);
    });
  }

  /* The event alone is not enough for one real case. shownCount is SEEDED at
     0, and state.set is a no-op when the value has not changed, so a cold load
     that legitimately shows nothing - "#3/0/0/games=", the link somebody
     shares after turning every game off - writes 0 over 0, emits nothing, and
     leaves the hint off. The map then looks exactly like failed tiles, which
     is the single case the hint was added for. Reconciled once, after the
     first applyFilters has run, so the flash-on-every-load the listener
     comment warns about still cannot happen: by this point the count is the
     real one, not the seed. */
  function reconcileEmptyState() {
    document.body.classList.toggle("am-empty",
      AM.state.get("shownCount") === 0);
  }

  function init(data) {
    ingest(data);
    $("meta-updated").textContent = "updated " + (data.updated || "?");

    /* Seed defaults (all games, all sources), then let the URL override the
       shareable parts. Sources are per-device and never come from the hash. */
    AM.state.initFromData(AM.data);
    var st = AM.map.parseHash();
    AM.state.batch(function () {
      if (st.games) AM.state.set("selectedGames", st.games);
      if (st.cabs) AM.state.set("selectedCabs", st.cabs);
    });

    if (st.view) {
      AM.map.setViewExact([st.view.lat, st.view.lng], st.view.z);
    } else {
      AM.map.fitToPoints(AM.data.plottable.map(function (a) {
        return [a.lat, a.lng];
      }));
    }

    AM.markers.build();
    AM.panel.build();
    AM.search.build();
    AM.settings.build();
    AM.nearby.build();

    /* After panel.build(), which fills #src-counts. */
    buildFooterToggle();
    watchEmptyState();

    AM.markers.start();
    AM.panel.start();
    AM.settings.start();
    AM.nearby.start();

    /* After markers.start(), which runs the first applyFilters. */
    reconcileEmptyState();

    AM.map.startHashSync();
  }

  function fail(e) {
    $("meta-count").textContent = "data load failed";
    $("meta-count").title = String(e);
    AM.map.map.setView([30, 135], 3);
  }

  /* cache: "no-cache" REVALIDATES, it does not skip the cache: the browser
     still sends the conditional request and a 304 costs nothing, but a stale
     copy can never be served silently. This file is rewritten by the weekly
     Action, and without this a returning visitor kept last week's arcades for
     as long as the CDN's max-age said they could. */
  fetch(C.DATA_URL, { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + " loading " + C.DATA_URL);
      return r.json();
    })
    .then(init)
    .catch(fail);

  /* exposed for testing */
  window.__arcadeMaps = {
    get shownCount() { return AM.state.get("shownCount"); },
    get selGames() { return AM.state.get("selectedGames"); },
    get selCabs() { return AM.state.get("selectedCabs"); },
    get enabledSources() { return AM.state.get("enabledSources"); },
    cluster: AM.markers.cluster,
    map: AM.map.map,
    AM: AM
  };
})(window.AM);
