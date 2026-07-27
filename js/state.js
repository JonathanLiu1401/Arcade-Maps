/* Arcade Maps - shared constants, helpers, loaded data and the state store.
   Every module reads user-facing state from here and re-renders off state
   events. No module calls another module's render function directly. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  /* ---------- constants ---------- */

  var DATA_URL = "data/arcades.json";
  var REPO_URL = "https://github.com/JonathanLiu1401/Arcade-Maps";
  var STORAGE_KEY = "am_settings_v1";

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
  GAMES.forEach(function (g) {
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
  /* Display order for source lists; unknown sources are appended at runtime. */
  var SRC_ORDER = ["allnet", "eagate", "wahlap", "ziv", "round1usa", "bemanicn", "community"];

  var REDUCED = !!(window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  AM.consts = {
    DATA_URL: DATA_URL,
    REPO_URL: REPO_URL,
    STORAGE_KEY: STORAGE_KEY,
    GAMES: GAMES,
    GAME_ORDER: GAME_ORDER,
    GAME_LABEL: GAME_LABEL,
    GAME_COLOR: GAME_COLOR,
    CAB_FILTERS: CAB_FILTERS,
    CAB_BADGE: CAB_BADGE,
    SRC_LABEL: SRC_LABEL,
    SRC_ORDER: SRC_ORDER,
    REDUCED: REDUCED
  };

  /* ---------- small helpers ---------- */

  function $(id) { return document.getElementById(id); }

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

  function num(n) { return Number(n || 0).toLocaleString("en-US"); }

  /* Total cabs for a game, or null when the data does not say.
     game_counts is optional in the schema and absent from some sources. */
  function gameCount(a, game) {
    if (!a || !a.game_counts) return null;
    var v = a.game_counts[game];
    return typeof v === "number" && isFinite(v) ? v : null;
  }

  AM.util = {
    $: $,
    esc: esc,
    hasCoords: hasCoords,
    gmapsSearchUrl: gmapsSearchUrl,
    num: num,
    gameCount: gameCount
  };

  /* ---------- loaded data (filled by app-init) ---------- */

  AM.data = {
    raw: null,        /* the parsed arcades.json */
    arcades: [],      /* all entries */
    plottable: [],    /* entries with usable coords */
    coordless: [],    /* no-coords-list entries */
    byId: {},         /* id -> arcade */
    gamesInData: [],  /* game slugs present, canonical order first */
    srcInData: [],    /* source slugs present, canonical order first */
    gameCounts: {},   /* game slug -> number of arcades */
    srcCounts: {}     /* source slug -> number of arcades */
  };

  /* ---------- persistence ---------- */
  /* Only keys listed here are mirrored to localStorage. Sources persist as
     the DISABLED set, never the enabled set: a source that first appears in a
     later data refresh must then default to visible rather than be silently
     hidden by an old stored list. */

  var PERSIST = {
    disabledSources: {
      read: function (store) {
        return Array.isArray(store.disabledSources) ? store.disabledSources : [];
      }
    }
  };

  function loadStore() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return {};
      var parsed = JSON.parse(raw);
      return (parsed && typeof parsed === "object") ? parsed : {};
    } catch (e) {
      /* Private mode, disabled storage or corrupt JSON: run with defaults. */
      return {};
    }
  }

  function saveStore(store) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    } catch (e) { /* storage unavailable or full: state stays in memory */ }
  }

  var store = loadStore();

  /* ---------- the store ---------- */

  var values = {
    /* Set of selected game slugs. Null until data has been loaded. */
    selectedGames: null,
    /* Set of checked CAB_FILTERS ids. */
    selectedCabs: new Set(),
    /* Set of enabled source slugs. Defaults to every source in the data,
       minus anything the user explicitly turned off in a past session. */
    enabledSources: new Set(),
    /* Currently focused arcade id, or null. */
    selectedArcade: null,
    /* Count of markers currently on the map. */
    shownCount: 0
  };

  var listeners = {};
  var batching = 0;
  var pending = [];

  function eq(a, b) {
    if (a === b) return true;
    if (a instanceof Set && b instanceof Set) {
      if (a.size !== b.size) return false;
      var same = true;
      a.forEach(function (v) { if (!b.has(v)) same = false; });
      return same;
    }
    return false;
  }

  function emit(key, value, meta) {
    var subs = listeners[key];
    if (!subs) return;
    /* Copy first: a listener may unsubscribe during dispatch. */
    subs.slice().forEach(function (cb) { cb(value, meta || {}); });
  }

  function flush() {
    var queue = pending;
    pending = [];
    queue.forEach(function (item) { emit(item[0], item[1], item[2]); });
  }

  var state = {

    /* Read a value. Sets are returned by reference: treat them as read-only
       and go through set() to change them. */
    get: function (key) { return values[key]; },

    /* Write a value and notify listeners. meta is an opaque object passed to
       every listener; markers.js honours meta.focus to fly to an arcade.
       Writing an equal value is normally a no-op so listeners never see false
       churn - but meta.focus is a command ("show me this store"), not a state
       change, so re-picking the store you are already on must still fly, open
       the popup and re-halo. Only the equality guard is bypassed. */
    set: function (key, val, meta) {
      if (eq(values[key], val) && !(meta && meta.focus)) return values[key];
      values[key] = val;
      if (key === "enabledSources") persistSources();
      if (batching) pending.push([key, val, meta]);
      else emit(key, val, meta);
      return val;
    },

    /* Force listeners to run even if the value did not change - used when a
       Set is mutated in place is NOT allowed, but a rebuild produced an equal
       Set and dependent modules still need to redraw. */
    touch: function (key, meta) {
      if (batching) pending.push([key, values[key], meta]);
      else emit(key, values[key], meta || {});
    },

    /* Subscribe. Returns an unsubscribe function. */
    on: function (key, cb) {
      (listeners[key] = listeners[key] || []).push(cb);
      return function () { state.off(key, cb); };
    },

    off: function (key, cb) {
      var subs = listeners[key];
      if (!subs) return;
      var i = subs.indexOf(cb);
      if (i !== -1) subs.splice(i, 1);
    },

    /* Coalesce several set() calls into one round of notifications. Used by
       the hash handler so 6k markers are not rebuilt twice in a row. */
    batch: function (fn) {
      batching++;
      try { fn(); } finally {
        batching--;
        if (!batching) {
          /* Collapse to the last write per key, preserving first-write order. */
          var seen = {}, ordered = [];
          pending.forEach(function (item) {
            if (!(item[0] in seen)) { seen[item[0]] = item; ordered.push(item[0]); }
            else { seen[item[0]][1] = item[1]; seen[item[0]][2] = item[2]; }
          });
          pending = ordered.map(function (k) { return seen[k]; });
          flush();
        }
      }
    },

    /* Convenience toggles used by the filter UI. */
    toggleGame: function (game) {
      var next = new Set(values.selectedGames);
      if (next.has(game)) next.delete(game); else next.add(game);
      state.set("selectedGames", next);
    },

    toggleCab: function (id) {
      var next = new Set(values.selectedCabs);
      if (next.has(id)) next.delete(id); else next.add(id);
      state.set("selectedCabs", next);
    },

    toggleSource: function (src) {
      var next = new Set(values.enabledSources);
      if (next.has(src)) next.delete(src); else next.add(src);
      state.set("enabledSources", next);
    },

    /* Seed defaults once the data is known. Stored per-device source choices
       are applied here; anything not explicitly disabled starts enabled. */
    initFromData: function (data) {
      if (values.selectedGames === null) {
        values.selectedGames = new Set(data.gamesInData);
      }
      var disabled = PERSIST.disabledSources.read(store);
      var enabled = new Set();
      data.srcInData.forEach(function (s) {
        if (disabled.indexOf(s) === -1) enabled.add(s);
      });
      values.enabledSources = enabled;
    },

    /* The persisted settings blob, for settings.js to extend. Unknown keys
       are preserved so one module cannot clobber another's saved values. */
    readSetting: function (key, fallback) {
      return (key in store) ? store[key] : fallback;
    },

    writeSetting: function (key, val) {
      store[key] = val;
      saveStore(store);
    }
  };

  function persistSources() {
    var enabled = values.enabledSources;
    var disabled = AM.data.srcInData.filter(function (s) { return !enabled.has(s); });
    store.disabledSources = disabled;
    saveStore(store);
  }

  AM.state = state;
})(window.AM);
