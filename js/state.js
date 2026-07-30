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
    /* Six titles that scrapers/ziv.py slugs out of the `other` bucket and that
       merge.py's GAME_SLUGS now keeps (it used to revert every one, which is
       why 1,541 real rhythm-game venues rendered as an unnamed grey chip).
       Live counts in the current data: pump_it_up 1558, stepmaniax 596,
       wacca 252, groove_coaster 224, crossbeats 50, beatstream 8.
       They are declared here so the chip, the filter, the colour, the
       legend and the per-game price lookup all light up the moment it does,
       rather than the frontend becoming the second half of a two-part fix.

       maimai CLASSIC IS DELIBERATELY NOT HERE, even though ziv.py promotes it
       alongside these six and the raw file carries 266 rows. It is already
       modelled as the maimai_classic CAB_VARIANT, which is the more accurate
       shape: a FiNALE cabinet is a maimai DX store's OTHER CABINET, not a
       separate venue category, and the variant carries the offline warning
       that matters (every maimai network closed in 2020). Giving it a game
       slug too would double-name the same machine - 46 stores in the current
       data have both a classic and a DX cabinet and would show a "maimai"
       chip AND a "FiNALE / pre-DX" badge on their maimai DX chip, which is the
       one state this must not produce. Six rows, not seven; see the merge.py
       note in the handoff.

       Colours are chosen against the light OSM basemap and measured, not
       eyeballed: the tightest CIEDE2000 distance between any new colour and
       any of the 19 above is dE 15.05 (pump_it_up vs museca), against dE 4.40
       for the existing palette's own closest pair (chunithm vs dance_around).
       They are not all mutually distinguishable at 20px - 25 categorical hues
       cannot be - but marker colour comes from the first SELECTED game, so a
       reader sees a handful at a time, and no new colour is a worse neighbour
       than pairs the map already ships. */
    ["pump_it_up", "Pump It Up", "#303F9F"],
    ["stepmaniax", "StepManiaX", "#00897B"],
    ["wacca", "WACCA", "#880E4F"],
    ["groove_coaster", "Groove Coaster", "#827717"],
    ["crossbeats", "crossbeats", "#5D4037"],
    ["beatstream", "BeatStream", "#33691E"],
    /* Stays last: the catch-all must sort after every named game. */
    ["other", "Other", "#9E9E9E"]
  ];
  var GAME_LABEL = {}, GAME_COLOR = {}, GAME_ORDER = [];
  GAMES.forEach(function (g) {
    GAME_ORDER.push(g[0]); GAME_LABEL[g[0]] = g[1]; GAME_COLOR[g[0]] = g[2];
  });

  /* ---------- cabinet variants ----------

     A rhythm game is not one machine. maimai DX and maimai FiNALE are
     different games on incompatible hardware; an IIDX Lightning Model runs
     charts a standard LDJ cab cannot unlock; a DDR gold cab has Dan courses
     the white cab does not. Which cabinet a store has is often the whole
     reason to travel to it, so the map has to say.

     WHERE THE EVIDENCE COMES FROM, and why it is not just `cabs[]`:

     `cabs[]` is assigned by the merge from KONAMI e-amusement facility
     files, and that search only covers JAPAN. Every one of the six flags in
     the current data file is 100% Japanese, so a cab filter built on `cabs[]`
     alone silently means "in Japan" - a Hong Kong player ticking "Lightning
     model" loses every Hong Kong store that has one.

     ZIv carries the same information worldwide, in the `Cabs:` list this
     file already ships inside `notes` ("beatmania IIDX 33 Sparkle Shower
     (LIGHTNING MODEL)"). Parsing that recovers 111 non-Japan Lightning cabs
     and 112 non-Japan Valkyrie cabs that `cabs[]` cannot see. So evidence is
     the UNION of the two, with per-source provenance kept so the UI can be
     honest about which is which.

     ONE eagate flag is dropped outright. data_raw/sdvx.json and
     data_raw/sdvx_vm.json are byte-identical (md5 35d3e6a0...): the upstream
     SDVX_VM facility key returns the plain SDVX result set, so the merge
     flagged all 551 Japanese SDVX stores as Valkyrie. That claim is false and
     a veteran spots it instantly, so `sdvx_vm` is sourced from ZIv only. The
     sibling pairs were checked the same way and all differ (iidx 6417600a vs
     df58b585, ddr 197ec818 vs ab1d9b80, popn 84443f6d vs b0bd6301, gitadora
     gf 32c8fd49 vs 541a566e, dm a328e0a0 vs a165a76f), so those five flags
     are trusted.

     THREE-STATE, NOT TWO. ZIv's silence is "unknown", never "standard": a
     bare `DanceDanceRevolution WORLD` line appears 160 times against 156 that
     name the gold cab, and reading the bare ones as white would assert a
     cabinet nobody recorded. Nothing here ever renders an absence as a
     variant. e-amusement CAN produce a negative inside Japan (a store in DDR
     but absent from DDR20TH really has no gold cab) and that is the only
     negative this file will state. */

  /* Variant slugs. `game` ties the variant to the game chip it qualifies,
     `badge` is the compact panel/popup pill, `chipOnly` variants rename the
     game chip instead of adding a pill (used where a badge on 7,656 stores
     would be noise), and `offline` marks a cabinet whose network is dead -
     you can play it, it cannot save a score. */
  var CAB_VARIANTS = [
    { id: "maimai_classic", game: "maimai_dx", label: "maimai (FiNALE / pre-DX)",
      badge: "FiNALE / pre-DX", offline: true,
      note: "Pre-DX cabinet. Every maimai network closed in 2020, so these run "
        + "offline: no score saving, no maimai-NET, Utage locked." },
    { id: "maimai_dx_cab", game: "maimai_dx", label: "maimai DX", chipOnly: true },
    { id: "iidx_lm", game: "iidx", label: "Lightning model", badge: "Lightning",
      note: "120Hz DisplayPort panel, touchscreen Premium Area, consistent "
        + "offset between cabs, and Kiwami Class charts a standard cab cannot unlock." },
    { id: "sdvx_vm", game: "sdvx", label: "Valkyrie model", badge: "Valkyrie",
      note: "43\" 120Hz portrait screen plus touch subscreen, better knobs, "
        + "S-CRITICAL judgement and Valkyrie-exclusive songs." },
    { id: "sdvx_nemsys", game: "sdvx", label: "NEMSYS (standard)", badge: "NEMSYS",
      note: "Standard 60Hz cabinet. The only one that can use Card Generator / "
        + "Card Connect, but it is being retired and stays on EXCEED GEAR." },
    { id: "ddr_gold", game: "ddr", label: "Gold cab (20th anniversary)", badge: "Gold cab",
      note: "BIO2 board, gold UI theme, and gold-only content: Dan courses "
        + "and the Legend Licenses Dancemania remixes." },
    { id: "ddr_universal", game: "ddr", label: "Universal Model (EU/NA)", badge: "Universal",
      note: "2026 Uniana-built platinum cabinet, EU and NA only. European "
        + "units ship with online removed and a reduced songlist." },
    { id: "ddr_legacy", game: "ddr", label: "Legacy CRT cabinet", badge: "Legacy CRT",
      offline: true,
      note: "Pre-LCD cabinet capped at old software - DDR WORLD dropped CRT "
        + "support entirely. Offline, no e-amusement." },
    { id: "popn_pikapika", game: "popn", label: "Pikapika model", badge: "Pikapika",
      note: "First new pop'n cabinet in 15 years: 43\" 120fps screen, two "
        + "large Dekka Pop-kun buttons and a touchscreen." },
    { id: "gitadora_gf_arena", game: "gitadora", label: "GuitarFreaks Arena model",
      badge: "GF Arena",
      note: "2025 four-screen chassis, physical buttons replaced by a touchscreen." },
    { id: "gitadora_dm_arena", game: "gitadora", label: "DrumMania Arena model",
      badge: "DM Arena",
      note: "2025 four-screen chassis with silicone snare and tom pads." },
    /* Taiko's axis is the regional BUILD, not the cabinet: the Asia, Japan and
       USA versions carry different songlists and are separated in the source.
       Labelled generically because the Asia bucket holds older Asia releases
       (Taiko 11/12 Asia) alongside Nijiiro, and naming Nijiiro would overclaim. */
    { id: "taiko_asia", game: "taiko", label: "Asia build", badge: "Asia build" },
    { id: "taiko_jp", game: "taiko", label: "Japan build (Nijiiro)", badge: "JP build" },
    { id: "taiko_us", game: "taiko", label: "USA build (Nijiiro)", badge: "USA build" }
  ];
  var VARIANT_BY_ID = {}, VARIANTS_BY_GAME = {};
  CAB_VARIANTS.forEach(function (v) {
    VARIANT_BY_ID[v.id] = v;
    (VARIANTS_BY_GAME[v.game] = VARIANTS_BY_GAME[v.game] || []).push(v);
  });

  /* Cab-variant filters: id, label, game restricted, matching variant slugs.

     The FIVE ORIGINAL IDS ARE FROZEN. mapcore.js serialises the checked set
     into the URL as `cabs=<id>,<id>` by iterating this list, so renaming
     sdvx_vm or gitadora_arena would break every link anyone has already
     shared. New variants are appended; nothing is renamed. */
  var CAB_FILTERS = [
    { id: "sdvx_vm", label: "Valkyrie model", game: "sdvx", slugs: ["sdvx_vm"] },
    { id: "iidx_lm", label: "Lightning model", game: "iidx", slugs: ["iidx_lm"] },
    { id: "ddr_gold", label: "Gold cab (20th anniv.)", game: "ddr", slugs: ["ddr_gold"] },
    { id: "gitadora_arena", label: "Arena model", game: "gitadora",
      slugs: ["gitadora_gf_arena", "gitadora_dm_arena"] },
    { id: "popn_pikapika", label: "Pikapika model", game: "popn", slugs: ["popn_pikapika"] },
    /* There is deliberately NO "maimai DX" checkbox, even though the variant
       exists and the chip logic depends on it. Every other box here selects a
       cabinet somebody positively identified; a DX box would select "DX, where
       a source happened to record it" and silently drop the 2,313 stores whose
       cabinet is merely unrecorded - which for maimai is almost always a DX
       cab. That is unknown being rendered as absent, the exact error the
       three-state rule exists to prevent, and it would hide more stores than
       any other filter on this list. FiNALE is the useful filter and it is a
       positive claim, so it is the one that ships. */
    { id: "maimai_classic", label: "maimai FiNALE / pre-DX", game: "maimai_dx",
      slugs: ["maimai_classic"] },
    { id: "sdvx_nemsys", label: "NEMSYS (standard)", game: "sdvx", slugs: ["sdvx_nemsys"] },
    { id: "ddr_universal", label: "Universal Model (EU/NA)", game: "ddr",
      slugs: ["ddr_universal"] },
    { id: "ddr_legacy", label: "Legacy CRT cab", game: "ddr", slugs: ["ddr_legacy"] },
    { id: "taiko_asia", label: "Nijiiro - Asia build", game: "taiko", slugs: ["taiko_asia"] },
    { id: "taiko_jp", label: "Nijiiro - Japan build", game: "taiko", slugs: ["taiko_jp"] },
    { id: "taiko_us", label: "Nijiiro - USA build", game: "taiko", slugs: ["taiko_us"] }
  ];
  var CAB_BADGE = {};
  CAB_VARIANTS.forEach(function (v) { if (v.badge) CAB_BADGE[v.id] = v.badge; });
  /* Legacy slugs that may still arrive in a data file's cabs[]. */
  CAB_BADGE.gitadora_gf_arena = "GF Arena";
  CAB_BADGE.gitadora_dm_arena = "DM Arena";
  var SRC_LABEL = {
    allnet: "ALL.Net", eagate: "e-amusement", wahlap: "WAHLAP", ziv: "ZIv",
    round1usa: "Round1 USA", bemanicn: "BemaniCN", community: "community"
  };
  /* Display order for source lists; unknown sources are appended at runtime. */
  var SRC_ORDER = ["allnet", "eagate", "wahlap", "ziv", "round1usa", "bemanicn", "community"];

  var REDUCED = !!(window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  /* Rhythm titles the merge drops into the `other` bucket. 7,491 stores carry
     `other` and the chip says nothing, yet Pump It Up alone is in 1,481 of
     them - on a worldwide map that is a bigger omission than any cab badge.
     Re-slugging them belongs in the scraper; naming them in the UI does not,
     so the panel reads the titles back out of the ZIv list and the search box
     indexes them. Anchored to the title token, never to a bare parenthetical. */
  var OTHER_GAMES = [
    { id: "pump_it_up", label: "Pump It Up", re: /pump\s*it\s*up|펌프/i },
    { id: "stepmaniax", label: "StepManiaX", re: /step\s*mania\s*x|stepmania/i },
    { id: "wacca", label: "WACCA", re: /\bwacca\b|华卡音舞/i },
    { id: "groove_coaster", label: "Groove Coaster", re: /groove\s*coaster|音炫轨道/i },
    { id: "crossbeats", label: "crossbeats", re: /crossbeats/i },
    { id: "beatstream", label: "BeatStream", re: /beatstream/i },
    { id: "beat_saber", label: "Beat Saber", re: /beat\s*saber/i },
    { id: "dance_evo_other", label: "DanceEvolution", re: /dance\s*evolution/i }
  ];

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
    CAB_VARIANTS: CAB_VARIANTS,
    VARIANT_BY_ID: VARIANT_BY_ID,
    VARIANTS_BY_GAME: VARIANTS_BY_GAME,
    OTHER_GAMES: OTHER_GAMES,
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

  /* A URL that is safe to put in an href, or "" when it is not.

     Every link on a store comes from a third-party scrape, and esc() does not
     help here: "javascript:alert(1)" contains none of the characters it
     escapes, so it survives HTML escaping intact and runs on click. Only http
     and https are allowed through, resolved against the document so a relative
     value is judged by what it actually becomes. javascript:, data:, vbscript:
     and friends yield "", and the caller renders a dead link rather than a live
     weapon. Obfuscation does not help an attacker either: the URL parser folds
     case and strips the embedded tab in "java&#9;script:" before the check.

     This is a scheme filter, not a destination filter. A protocol-relative
     "//other.example/x" resolves to https://other.example/x and is allowed, as
     is any scraped https host - these links are meant to point at ZIv, BemaniCN
     and Google Maps, so the DESTINATION is untrusted by design and every one of
     them already carries target="_blank" rel="noopener". What is being stopped
     here is a URL that executes instead of navigating. */
  function safeUrl(u) {
    if (typeof u !== "string" || !u) return "";
    var abs;
    try { abs = new URL(u, document.baseURI); }
    catch (e) { return ""; }
    if (abs.protocol !== "http:" && abs.protocol !== "https:") return "";
    return abs.href;
  }

  /* Total cabs for a game, or null when the data does not say.
     game_counts is optional in the schema and absent from some sources. */
  function gameCount(a, game) {
    if (!a || !a.game_counts) return null;
    var v = a.game_counts[game];
    return typeof v === "number" && isFinite(v) ? v : null;
  }

  /* Whether a count may be PRINTED AS A NUMBER.

     The rule exists because of one specific lie. ZIv lists machines, and for
     most titles it lists exactly one row whether the store has one cabinet or
     twelve: GiGO総本店 is a nine-floor flagship whose CHUNITHM row is a single
     entry, and the panel rendered that as "CHUNITHM x1 listed". Across the
     data that produced 1,536 chips asserting a quantity nobody published, in
     every country, and it is worse than showing nothing - a reader who sees
     "x1" believes it.

     So a lone ZIv row is treated as what it is: evidence the game is HERE,
     and no evidence at all of how many. n >= 2 is different and does survive,
     because ZIv genuinely repeats a title per cabinet when a contributor
     enumerates them (271 titles in the live Japan payload appear more than
     once, and GiGO's three DDR WORLD rows really are three gold cabs).
     A count backed by an explicit human comment ("6x", "12 machines") is
     authoritative at any value, including one. */
  function countIsShowable(a, game) {
    var n = gameCount(a, game);
    if (n === null) return false;
    var ev = a && a.count_evidence && a.count_evidence[game];
    if (ev === "ziv_listed") return n >= 2;
    return true;
  }

  /* Sum of only the counts a source ACTUALLY PUBLISHED, or null when none of
     them survive countIsShowable.

     This exists because the panel and the marker were telling different
     stories about the same store. AM.format.totalCabs sums game_counts RAW,
     which is the right answer to "what is in the file" and the wrong answer to
     "how big is this arcade": a lone ZIv machine row means "this game is
     here", not "there is exactly one cabinet", and countIsShowable is the rule
     that already suppresses it everywhere a NUMBER is printed.

     KINGPIN MELBOURNE (id 177) is the case that made this visible. Its raw sum
     is 6, which the marker graded "3 to 9 cabinets", while the panel printed
     "maimai DX | CHUNITHM x2 listed | DDR | DANCERUSH | Taiko" - four of its
     five counts suppressed, a showable sum of 2. One store, two contradictory
     claims, and the bigger one was the one drawn on the map. 516 arcades
     disagreed this way and 213 of them were graded into the wrong tier.

     Returns null, never 0, when nothing is showable: that is the same contract
     AM.format.totalCabs uses, and it is what lets markers.js fall through to
     the UNKNOWN tier without a special case. "We do not know how big this is"
     and "this is tiny" are different statements and must not share a symbol. */
  function showableCabs(a) {
    var counts = a && a.game_counts;
    if (!counts || typeof counts !== "object") return null;
    var total = 0, seen = false;
    for (var g in counts) {
      if (!Object.prototype.hasOwnProperty.call(counts, g)) continue;
      var n = counts[g];
      if (typeof n !== "number" || !isFinite(n) || n <= 0) continue;
      if (!countIsShowable(a, g)) continue;
      total += n;
      seen = true;
    }
    return seen ? total : null;
  }

  /* "listed" means a lower bound: this many were enumerated, there may be
     more. Explicit quantities and BemaniCN's published per-title numbers are
     not hedged; a ZIv enumeration is. Falls back to the arcade-level
     counts_src for rows written before count_evidence existed. */
  function countIsQualified(a, game, src) {
    var ev = a && a.count_evidence && a.count_evidence[game];
    if (ev) return ev === "ziv_listed";
    return src === "ziv";
  }

  /* ---------- cab-variant detection ----------

     Everything below turns one arcade into a map of

         variant slug -> { n: count|null, src: "eagate"|"ziv"|"cab_models" }

     computed ONCE per arcade and cached on a side map keyed by id. It has to
     be cached: markers.js runs the visibility predicate over 13,540 rows on
     every filter toggle, and search.js and nearby.js run it again, so a regex
     sweep inside that predicate would make every checkbox click walk the whole
     data file. Nothing here runs during a zoom or pan - the cache is built on
     first read and only invalidated when the data file itself is replaced. */

  /* ZIv publishes the machine list inside `notes` as
       "region: X | Cabs: TITLE; TITLE; TITLE | other prose"
     Only the segment between "Cabs:" and the next pipe is a machine list;
     the prose after it is human commentary that happens to name games
     ("Standard Round1 US rhythm lineup assumed: DDR, maimai DX, ...") and
     reading that as a cab list would invent machines. */
  function cabTitles(a) {
    var n = a && a.notes;
    if (typeof n !== "string") return [];
    var at = n.indexOf("Cabs:");
    if (at === -1) return [];
    var body = n.slice(at + 5).split("|")[0];
    var out = [];
    body.split(";").forEach(function (t) {
      t = t.trim();
      if (t) out.push(t);
    });
    return out;
  }

  /* Ordered rules, first match wins WITHIN a game. Anchored to the game token
     on purpose: a bare /\(.*model.*\)/ scoops "Terminator Salvation (Unknown
     Model)" 193 times, plus Sweet Land's Blue/Pink models and a Batman - all
     checked, none of them rhythm games. Everything is case-insensitive
     because the source mixes "(LIGHTNING MODEL)", "(Valkyrie model)" and
     "(20th anniversary model)" freely, and every parenthesis class accepts
     the FULL-WIDTH form too: the 267-row Asia Taiko build is written
     "ニジイロVer.(アシア版）" with an ASCII open paren and a full-width close,
     which a plain [^)]+ never matches. */
  var TITLE_RULES = [
    /* maimai: the classic rule MUST be tested before the DX rule, because
       "舞萌DX 2026 (maimai DX PRiSM PLUS)" contains both tokens. */
    { id: "maimai_classic",
      re: /(?:^|[\s\/])maimai(?:PLUS)?\b(?!\s*(?:dx|でらっくす))|^舞萌\s*[\(（](?!.*dx)/i },
    { id: "maimai_dx_cab", re: /maimai\s*dx|maimai\s*でらっくす|舞萌\s*dx/i },

    { id: "iidx_lm", re: /beatmania[\s\S]*[\(（]\s*lightning\s+model\s*[\)）]/i },

    { id: "sdvx_vm", re: /(?:sound\s*voltex|音律炫动)[\s\S]*[\(（]\s*valkyrie\s+model\s*[\)）]/i },
    { id: "sdvx_nemsys", re: /(?:sound\s*voltex|音律炫动)[\s\S]*[\(（]\s*nemsys\s+model\s*[\)）]/i },

    { id: "ddr_gold",
      re: /(?:dance\s*dance\s*revolution|ddr)[\s\S]*[\(（]\s*20th\s+anniversary\s+model\s*[\)）]/i },
    { id: "ddr_universal",
      re: /(?:dance\s*dance\s*revolution|ddr)[\s\S]*[\(（]\s*universal\s+model\s*[\)）]/i },
    /* Legacy is a TITLE test, not a parenthetical: these cabinets are CRT-era
       and identified by which mix they are stuck on. DDR WORLD is the first
       DDR with no CRT support, so an EXTREME or SuperNOVA cab is hard-capped
       at dead software - 251 EXTREME cabs currently render identically to a
       live A3. Deliberately excludes the A/A20/A3/WORLD generation. */
    { id: "ddr_legacy",
      re: /(?:dance\s*dance\s*revolution|dancing\s*stage|ddrmax)[\s\S]*(?:extreme|supernova|euromix|fusion|ddrmax|\bsolo\b|[2-8](?:nd|rd|th)\s*mix|\bstomp\b|\bX[23]?\b|hottest\s*party|konamix)|ddrmax/i },

    { id: "taiko_asia", re: /(?:太鼓の達人|taiko)[\s\S]*[\(（]\s*(?:アシア版|亞洲版|亚洲版)\s*[\)）]|亞洲版|亚洲版/i },
    { id: "taiko_us", re: /taiko[\s\S]*nijii?ro[\s\S]*\busa\b/i },
    { id: "taiko_jp", re: /太鼓の達人\s*ニジイロ/i },

    { id: "popn_pikapika", re: /pop'?n[\s\S]*(?:ピカピカ|pikapika)/i },
    { id: "gitadora_gf_arena", re: /gitadora[\s\S]*arena[\s\S]*guitar|guitarfreaks[\s\S]*arena/i },
    { id: "gitadora_dm_arena", re: /gitadora[\s\S]*arena[\s\S]*drum|drummania[\s\S]*arena/i }
  ];

  /* An e-amusement flag is only evidence when its facility file actually
     differs from the base game's. SDVX_VM is a real gkey that returns the
     plain SDVX result set byte for byte, so it flags every Japanese SDVX
     store as Valkyrie; believing it is worse than having no data. */
  var UNTRUSTED_EAGATE_CAB = { sdvx_vm: true };

  /* A machine title the source clipped: "maimai D...", "SOUND...", "...". */
  var TRUNCATED = /(?:\.\.\.|…)\s*$/;

  function addHit(map, id, src, n) {
    if (!id) return;
    var cur = map[id];
    if (!cur) { map[id] = { n: (typeof n === "number" && n > 0) ? n : null, src: src }; return; }
    /* Two sources agreeing is not two cabinets. Keep the stronger provenance
       and the count only if one side actually has one. */
    if (typeof n === "number" && n > 0 && (cur.n === null || n > cur.n)) cur.n = n;
    if (src === "cab_models") cur.src = src;
    else if (src === "eagate" && cur.src === "ziv") cur.src = "both";
    else if (src === "ziv" && cur.src === "eagate") cur.src = "both";
  }

  function computeVariants(a) {
    var map = {};

    /* 1. cab_models {slug: count} - the field a concurrent scraper change is
       adding. Absent from every row today, so this branch is written blind
       and is deliberately the highest-precedence source: when it lands it
       carries real per-variant quantities and supersedes both guesses. */
    var cm = a && a.cab_models;
    if (cm && typeof cm === "object") {
      for (var slug in cm) {
        if (!Object.prototype.hasOwnProperty.call(cm, slug)) continue;
        var q = cm[slug];
        /* Same lie as the game chips, one level down: these quantities are
           tallied from the same ZIv machine rows, so a lone row means "this
           cabinet is here", not "there is exactly one of it". A Valkyrie pill
           reading X1 at a flagship is a claim no source made. Drop the number
           and keep the pill; n >= 2 is a real enumeration and survives. */
        addHit(map, slug, "cab_models",
          (typeof q === "number" && isFinite(q) && q >= 2) ? q : null);
      }
    }

    /* 2. cabs[] from e-amusement, minus the flag that carries no information. */
    if (a && a.cabs && a.cabs.length) {
      for (var i = 0; i < a.cabs.length; i++) {
        var c = a.cabs[i];
        if (UNTRUSTED_EAGATE_CAB[c]) continue;
        addHit(map, c, "eagate", null);
      }
    }

    /* 3. ZIv titles - the only worldwide source. Each title is tested against
       the ordered rules and takes the FIRST match, so one machine can never
       count as two variants of the same game. */
    var titles = cabTitles(a);
    for (var t = 0; t < titles.length; t++) {
      /* 301 titles in this file arrive TRUNCATED ("maimai D...", "SOUND...",
         and 36 bare "..."), because the upstream listing clipped them. A
         truncated title is not evidence: "maimai D..." is almost certainly
         "maimai DX", but the classic rule matches it first and would label a
         live DX cabinet as a dead offline FiNALE - the single worst error this
         feature can make, because it sends someone to a machine that cannot
         save a score. A clipped string proves only that SOMETHING is there,
         so it is skipped rather than guessed at. */
      if (TRUNCATED.test(titles[t])) continue;
      for (var r = 0; r < TITLE_RULES.length; r++) {
        if (TITLE_RULES[r].re.test(titles[t])) {
          addHit(map, TITLE_RULES[r].id, "ziv", null);
          break;
        }
      }
    }

    /* maimai three-state. ALL.Net and WAHLAP are official locators that list
       only currently-serviced titles, and no maimai FiNALE network exists
       anywhere on earth (JP closed 2019-09, Asia 2020-02, maimai-NET
       2020-03). So a store listed by one of them and carrying maimai is
       running DX, full stop - that is a positive, not an assumption, and it
       resolves 4,179 stores that ZIv never described. */
    /* The official listing wins even when ZIv ALSO names a classic cabinet,
       and dropping the old `!map.maimai_classic` guard is the point. ZIv's cab
       list is community-maintained and goes stale: Round1 Hiroshima still
       carries "maimai GreeN", a 2013 title, so the chip renamed itself to
       "maimai (FiNALE / pre-DX)" and told a player the machine was offline
       while SEGA's own current maimai DX locator lists that exact store.
       41 venues were mislabelled this way, 22 of them present in an official
       list. A newer official listing beats an older community one: the store
       is running DX, and any classic cabinet it also has is a second cabinet
       rather than a correction. */
    if (a && a.games && a.games.indexOf("maimai_dx") !== -1 && !map.maimai_dx_cab
        && a.src) {
      for (var s = 0; s < a.src.length; s++) {
        if (a.src[s] === "allnet" || a.src[s] === "wahlap") {
          addHit(map, "maimai_dx_cab", "official", null);
          break;
        }
      }
    }
    return map;
  }

  var variantCache = {};

  /* variantsOf(a) -> { slug: {n, src} }. Never null. */
  function variantsOf(a) {
    if (!a) return {};
    var key = a.id;
    if (key === undefined || key === null) return computeVariants(a);
    var hit = variantCache[key];
    if (hit === undefined) { hit = variantCache[key] = computeVariants(a); }
    return hit;
  }

  function hasVariant(a, slug) {
    return Object.prototype.hasOwnProperty.call(variantsOf(a), slug);
  }

  /* Variants for one game, in CAB_VARIANTS order, only the ones present. */
  function variantsForGame(a, game) {
    var have = variantsOf(a);
    var defs = VARIANTS_BY_GAME[game] || [];
    var out = [];
    for (var i = 0; i < defs.length; i++) {
      if (Object.prototype.hasOwnProperty.call(have, defs[i].id)) {
        out.push({ def: defs[i], ev: have[defs[i].id] });
      }
    }
    return out;
  }

  /* Which `other` titles a store actually has, so the grey "Other" chip can
     stop being a black box. Returns [] when nothing is derivable.

     A title that has since been PROMOTED to a real game slug is skipped, and
     that guard is what keeps this list from double-naming a machine. Six of
     the eight entries in OTHER_GAMES also exist in GAMES and the merge now
     keeps them, so a store with a Pump It Up cabinet gets a real "Pump It Up"
     chip, and without this test the grey chip beside it would ALSO read
     "Pump It Up" off the same cabinet. The
     store has one machine, so the UI must name it once.

     Only the arcade's own games list can decide this - not the presence of the
     slug in GAMES - because during the changeover a store scraped before the
     merge fix still carries the title under `other` alone and must keep its
     name on the grey chip. Beat Saber and DanceEvolution have no game slug at
     all, so they always fall through and always show here. */
  function otherGamesOf(a) {
    var titles = cabTitles(a);
    if (!titles.length) return [];
    var games = (a && a.games) || [];
    var seen = {}, out = [];
    for (var i = 0; i < titles.length; i++) {
      for (var j = 0; j < OTHER_GAMES.length; j++) {
        var og = OTHER_GAMES[j];
        if (seen[og.id]) continue;
        /* Already promoted to its own chip on THIS store: naming it again on
           the catch-all chip would claim a second machine that is not there. */
        if (games.indexOf(og.id) !== -1) { seen[og.id] = true; continue; }
        if (og.re.test(titles[i])) { seen[og.id] = true; out.push(og); }
      }
    }
    return out;
  }

  /* The game's name AT ONE STORE, which is not always the game's own label.

     A store whose only maimai cabinet is a pre-DX one is not a maimai DX
     store, and calling it one is the single most misleading thing this map
     did: 222 stores advertised a game whose network shut down in 2020, so a
     player could travel to one and find a machine that cannot save a score.

     This lives in util rather than in the panel because FIVE surfaces print a
     game name (place-panel chip, hero caption, price row, no-coords list, map
     popup) and nearby.js prints a sixth. Fixing one leaves the same false
     claim on the others in a different font, so they all read it from here. */
  function gameLabelFor(a, g) {
    if (g === "maimai_dx") {
      var have = variantsOf(a);
      if (have.maimai_classic && !have.maimai_dx_cab) return "maimai (FiNALE / pre-DX)";
    }
    return GAME_LABEL[g] || g;
  }

  /* Only needed if the data file is ever swapped at runtime; arcades.json is
     fetched once today, so nothing calls this. */
  function resetVariantCache() { variantCache = {}; }

  AM.util = {
    $: $,
    esc: esc,
    hasCoords: hasCoords,
    gmapsSearchUrl: gmapsSearchUrl,
    safeUrl: safeUrl,
    num: num,
    gameCount: gameCount,
    countIsShowable: countIsShowable,
    showableCabs: showableCabs,
    countIsQualified: countIsQualified,
    cabTitles: cabTitles,
    variantsOf: variantsOf,
    hasVariant: hasVariant,
    variantsForGame: variantsForGame,
    otherGamesOf: otherGamesOf,
    gameLabelFor: gameLabelFor,
    resetVariantCache: resetVariantCache
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
