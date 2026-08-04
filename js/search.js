/* Arcade Maps - the header omnibox: one search box, three grouped result
   sections (Games / Arcades / Places), keyboard-navigable.

   Games use a hand-maintained alias table rather than a fuzzy library: the
   game set is closed (19 slugs) and the aliases we actually need are CJK
   (舞萌, 中二節奏, 太鼓の達人) or scene abbreviations (iidx, sdvx, drs), which
   no fuzzy matcher recovers from an English label. That keeps the match
   deterministic and adds zero dependencies - see docs/research section 4.4.

   Picks never render anything themselves; they write state and the owning
   module reacts:
     game   -> selectedGames gains the slug, panel.js redraws the chip
     arcade -> selectedArcade with meta.focus, markers.js flies + halos
               (the halo highlight is markers.js's, reused as-is)
     place  -> the map is fitted to that place's bounding box */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts, U = AM.util;
  var $ = U.$, esc = U.esc;

  var MAX_GAMES = 6;      /* game rows shown */
  var MAX_ARCADES = 8;    /* arcade rows shown (spec) */
  var MAX_PLACES = 5;     /* place rows shown */
  var LEGACY_MAX = 20;    /* cap of the documented query() contract */
  var DEBOUNCE_MS = 120;
  var FLASH_MS = 1400;

  /* ---------- game alias table ---------- */
  /* Latin terms are stored lowercase; CJK is stored as-is (case folding is a
     no-op there). Every canonical label is added automatically in build().
     Deliberately NO prsk/pjsk: Project SEKAI is not in this data set. */

  var GAME_ALIASES = {
    maimai_dx: ["maimai", "maimai dx", "maidx", "mai", "舞萌", "舞萌dx",
      "まいまい", "マイマイ", "メイマイ"],
    chunithm: ["chunithm", "chuni", "chunith", "中二節奏", "中二节奏", "中二",
      "チュウニズム", "チュウニ"],
    ongeki: ["ongeki", "o.n.g.e.k.i", "オンゲキ", "音击", "音擊"],
    project_diva: ["project diva", "diva", "pjd", "miku", "hatsune miku",
      "初音ミク", "プロジェクトディーヴァ"],
    sdvx: ["sdvx", "sound voltex", "voltex", "ボルテ", "サウンドボルテックス"],
    iidx: ["iidx", "beatmania", "beatmania iidx", "2dx", "ビートマニア",
      "ビーマニ"],
    ddr: ["ddr", "dance dance revolution", "ダンレボ",
      "ダンスダンスレボリューション", "跳舞机"],
    polaris_chord: ["polaris chord", "polaris", "ポラリスコード", "ポラリス"],
    gitadora: ["gitadora", "ギタドラ", "guitarfreaks", "drummania",
      "ギターフリークス", "ドラムマニア"],
    jubeat: ["jubeat", "ユビート", "乐动魔方"],
    popn: ["popn", "pop'n", "pop'n music", "pop n music", "ポップン",
      "ポップンミュージック"],
    nostalgia: ["nostalgia", "ノスタルジア", "ノスタ"],
    drs: ["drs", "dancerush", "dance rush", "dancerush stardom",
      "ダンスラッシュ", "ダンラン"],
    dance_around: ["dance around", "ダンスアラウンド"],
    dance_evo: ["dance evolution", "danceevolution", "danevo",
      "ダンスエボリューション"],
    museca: ["museca", "ミュゼカ"],
    reflec: ["reflec", "reflec beat", "リフレク", "リフレクビート"],
    taiko: ["taiko", "taiko no tatsujin", "drum master", "太鼓の達人",
      "太鼓达人", "太鼓", "たいこ"],
    other: ["other", "misc"]
  };

  /* Titles the data does not track as their own slug. They resolve to the
     "other" bucket and the row says so, rather than returning nothing and
     leaving the user thinking the site has no WACCA stores at all.

     `slug` is the game slug the title carries in the merged data. Six of
     these are now live (merge.py's GAME_SLUGS keeps what ziv.py emits); the
     rest still fold into `other`. Either way this is not a CLAIM that the
     slug is live - queryGames checks gamesInData at query time, so a row
     stops saying "has no filter chip" exactly when that sentence becomes
     false, rather than sending a reader to the grey Other chip when their
     own chip is sitting right there. */
  var OTHER_TITLES = {
    wacca: { label: "WACCA", slug: "wacca" },
    "ワッカ": { label: "WACCA", slug: "wacca" },
    "华卡音舞": { label: "WACCA", slug: "wacca" },
    "groove coaster": { label: "Groove Coaster", slug: "groove_coaster" },
    "グルーヴコースター": { label: "Groove Coaster", slug: "groove_coaster" },
    "音炫轨道": { label: "Groove Coaster", slug: "groove_coaster" },
    "pump it up": { label: "Pump It Up", slug: "pump_it_up" },
    piu: { label: "Pump It Up", slug: "pump_it_up" },
    "펌프": { label: "Pump It Up", slug: "pump_it_up" },
    /* StepManiaX is in 543 stores and had no alias at all, so a US player
       searching the second most common pad game on this map got nothing. */
    stepmaniax: { label: "StepManiaX", slug: "stepmaniax" },
    smx: { label: "StepManiaX", slug: "stepmaniax" },
    stepmania: { label: "StepManiaX", slug: "stepmaniax" },
    /* Beat Saber has no game slug anywhere in the pipeline, so it stays in
       the Other bucket permanently and keeps the explanatory note forever. */
    "beat saber": { label: "Beat Saber", slug: null },
    "beatstream": { label: "BEATSTREAM", slug: "beatstream" },
    "crossbeats": { label: "crossbeats", slug: "crossbeats" }
  };

  /* ---------- place tables ---------- */
  /* Japanese prefectures arrive as romaji from one source and kanji from
     another ("Osaka" and "大阪府" are the same place). Both spellings must
     collapse to one row or the counts and the bounding box are wrong. */

  var JP_PREF = {
    "北海道": "Hokkaido", "青森": "Aomori", "岩手": "Iwate", "宮城": "Miyagi",
    "秋田": "Akita", "山形": "Yamagata", "福島": "Fukushima", "茨城": "Ibaraki",
    "栃木": "Tochigi", "群馬": "Gunma", "埼玉": "Saitama", "千葉": "Chiba",
    "東京": "Tokyo", "神奈川": "Kanagawa", "新潟": "Niigata", "富山": "Toyama",
    "石川": "Ishikawa", "福井": "Fukui", "山梨": "Yamanashi", "長野": "Nagano",
    "岐阜": "Gifu", "静岡": "Shizuoka", "愛知": "Aichi", "三重": "Mie",
    "滋賀": "Shiga", "京都": "Kyoto", "大阪": "Osaka", "兵庫": "Hyogo",
    "奈良": "Nara", "和歌山": "Wakayama", "鳥取": "Tottori", "島根": "Shimane",
    "岡山": "Okayama", "広島": "Hiroshima", "山口": "Yamaguchi",
    "徳島": "Tokushima", "香川": "Kagawa", "愛媛": "Ehime", "高知": "Kochi",
    "福岡": "Fukuoka", "佐賀": "Saga", "長崎": "Nagasaki", "熊本": "Kumamoto",
    "大分": "Oita", "宮崎": "Miyazaki", "鹿児島": "Kagoshima", "沖縄": "Okinawa"
  };
  var JP_PREF_REV = {};
  Object.keys(JP_PREF).forEach(function (k) {
    JP_PREF_REV[JP_PREF[k].toLowerCase()] = k;
  });

  /* Non-Latin ways of naming the countries that actually carry stores. */
  var COUNTRY_ALIASES = {
    Japan: ["日本", "にほん", "jp"],
    China: ["中国", "中國", "prc"],
    Taiwan: ["台湾", "臺灣", "台灣"],
    "Hong Kong": ["香港", "hk"],
    "South Korea": ["韓国", "한국", "대한민국", "korea"],
    "United States": ["アメリカ", "米国", "美国", "usa", "us"],
    "United Kingdom": ["英国", "uk", "britain"],
    Singapore: ["新加坡", "シンガポール"],
    Macau: ["澳门", "澳門"]
  };

  /* ---------- indexes ---------- */

  var arcadeIndex = [];   /* [{ a, hay }] - name + addr + pref */
  var gameIndex = [];     /* [{ slug, label, color, terms }] */
  var placeIndex = [];    /* [{ key, label, alt, country, terms, ... bbox }] */

  var rows = [];          /* flat list of SELECTABLE rows, in render order */
  var arcadeRows = [];    /* the arcade subset, for the legacy getResults() */
  var selIdx = -1;
  var tmr = null;
  var flashTimer = null;
  var input = null, list = null;

  /* ---------- index construction ---------- */

  function buildArcadeIndex() {
    /* pref is in the haystack because many Chinese addresses are only the
       street ("全运路万达3F") with the province in pref; without it those
       stores are unreachable by province name. country is deliberately NOT
       in the haystack - "japan" would return 8 arbitrary stores, which the
       Places group answers properly instead. */
    /* The machine titles go in too. Two things were unfindable without them:
       the ~2,200 stores whose only slug is "other" (Pump It Up is in 1,481 of
       them, StepManiaX 543, WACCA 178 - typing "pump it up" returned nothing
       at all), and cabinet models, so "lightning model" or "valkyrie" now
       finds the stores that have one. These are the first things a player
       types, and every one of them was a dead end.

       Only the machine list is indexed, not the whole notes field: the prose
       after it includes "Standard Round1 US rhythm lineup assumed: DDR, maimai
       DX, ..." on 171 stores, and indexing that makes a search for a game
       return stores that were only GUESSED to have it. */
    arcadeIndex = AM.data.arcades.map(function (a) {
      var titles = AM.util.cabTitles(a);
      return {
        a: a,
        hay: (a.name + " " + (a.addr || "") + " " + (a.pref || "") +
          (titles.length ? " " + titles.join(" ") : "")).toLowerCase()
      };
    });
  }

  function buildGameIndex() {
    gameIndex = AM.data.gamesInData.map(function (slug) {
      var en = C.GAME_LABEL[slug] || slug;
      var label = (AM.util && AM.util.gameLabel)
        ? AM.util.gameLabel(slug) : en;
      /* Index both the localized label and the English brand so a JP UI
         still finds "maimai" / "CHUNITHM" by English typing. */
      var terms = [label.toLowerCase(), en.toLowerCase(), slug,
        slug.replace(/_/g, " ")];
      (GAME_ALIASES[slug] || []).forEach(function (t) {
        terms.push(t.toLowerCase());
      });
      /* Dedupe so an alias that equals the label does not double-rank. */
      var seen = {}, uniq = [];
      terms.forEach(function (t) {
        if (t && !seen[t]) { seen[t] = 1; uniq.push(t); }
      });
      return {
        slug: slug, label: label,
        color: C.GAME_COLOR[slug] || C.GAME_COLOR.other,
        terms: uniq
      };
    });
  }

  /* Strip the administrative suffix so 广东 / 广东省 and 大阪 / 大阪府 are one
     key. 北海道 is left whole: its 道 IS the name. */
  function stripPrefSuffix(p) {
    p = String(p).trim();
    if (p.indexOf("中国") === 0) p = p.slice(2);
    if (p !== "北海道") {
      var last = p.charAt(p.length - 1);
      if (last === "省" || last === "県" || last === "府" || last === "都") {
        p = p.slice(0, -1);
      }
    }
    return p;
  }

  /* Canonical identity for a raw pref value: JP prefectures collapse across
     scripts, everything else keys off its own country so two countries can
     never share a row. */
  function prefKey(country, rawPref) {
    var p = stripPrefSuffix(rawPref);
    if (JP_PREF[p]) return { key: "jp:" + JP_PREF[p].toLowerCase(), label: JP_PREF[p], alt: p };
    var low = p.toLowerCase();
    if (JP_PREF_REV[low]) return { key: "jp:" + low, label: p, alt: JP_PREF_REV[low] };
    return { key: (country || "?") + ":" + low, label: p, alt: null };
  }

  function newPlace(key, label, alt, country, kind) {
    return {
      key: key, label: label, alt: alt, country: country, kind: kind,
      n: 0, plottable: 0, terms: [],
      minLat: Infinity, maxLat: -Infinity, minLng: Infinity, maxLng: -Infinity
    };
  }

  function addTerm(p, t) {
    if (!t) return;
    t = String(t).toLowerCase();
    if (p.terms.indexOf(t) === -1) p.terms.push(t);
  }

  function absorb(p, a) {
    p.n++;
    if (!U.hasCoords(a)) return;
    p.plottable++;
    if (a.lat < p.minLat) p.minLat = a.lat;
    if (a.lat > p.maxLat) p.maxLat = a.lat;
    if (a.lng < p.minLng) p.minLng = a.lng;
    if (a.lng > p.maxLng) p.maxLng = a.lng;
  }

  function buildPlaceIndex() {
    var byKey = {};
    AM.data.arcades.forEach(function (a) {
      if (a.pref) {
        var id = prefKey(a.country, a.pref);
        var p = byKey[id.key];
        if (!p) {
          p = byKey[id.key] = newPlace(id.key, id.label, id.alt, a.country, "pref");
          addTerm(p, id.label);
          addTerm(p, id.alt);
        }
        /* Every raw spelling stays searchable ("大阪府" as typed, not just 大阪). */
        addTerm(p, a.pref);
        absorb(p, a);
      }
      if (a.country) {
        var ck = "country:" + a.country.toLowerCase();
        var cp = byKey[ck];
        if (!cp) {
          cp = byKey[ck] = newPlace(ck, a.country, null, a.country, "country");
          addTerm(cp, a.country);
          (COUNTRY_ALIASES[a.country] || []).forEach(function (t) { addTerm(cp, t); });
        }
        absorb(cp, a);
      }
    });
    /* A place with no plotted store cannot be flown to. Those stores are
       still reachable through the Arcades group (pref is in that haystack)
       and through the no-coords tab, so dropping the row is honest rather
       than offering a jump that would do nothing. */
    placeIndex = Object.keys(byKey).map(function (k) { return byKey[k]; })
      .filter(function (p) { return p.plottable > 0; });
  }

  /* ---------- matching ---------- */

  /* 0 exact, 1 prefix, 2 contained, -1 miss. Lower is better. */
  function termRank(terms, q) {
    var best = -1;
    for (var i = 0; i < terms.length; i++) {
      var t = terms[i];
      var at = t.indexOf(q);
      if (at === -1) continue;
      var r = (t === q) ? 0 : (at === 0 ? 1 : 2);
      if (best === -1 || r < best) best = r;
      if (best === 0) break;
    }
    return best;
  }

  function queryGames(q) {
    var out = [];
    gameIndex.forEach(function (g) {
      var r = termRank(g.terms, q);
      if (r !== -1) out.push({ g: g, rank: r, note: null });
    });
    /* Untracked titles resolve to the "other" bucket with an explanation.

       These terms are also the ONLY way to reach several of these games: the
       gameIndex terms for a slug are just its label, its slug and its aliases,
       so "piu", "smx", "펌프", "ワッカ", "华卡音舞" and "グルーヴコースター"
       match no game row at all and exist only in this table. So the promoted
       case must REDIRECT this row onto the real game, not drop it - dropping
       it would make all six of those queries return nothing the day the merge
       lands, which is the exact silence this table was written to prevent. */
    Object.keys(OTHER_TITLES).forEach(function (term) {
      if (term.indexOf(q) === -1) return;
      var info = OTHER_TITLES[term];
      /* Live only when the data actually carries the slug. gamesInData is the
         test, so a title promoted in the merge lights up here on its own and
         one still folded into `other` keeps saying so, with no edit here. */
      var live = !!info.slug && AM.data.gamesInData.indexOf(info.slug) !== -1;
      var wantSlug = live ? info.slug : "other";
      var og = null;
      for (var i = 0; i < gameIndex.length; i++) {
        if (gameIndex[i].slug === wantSlug) { og = gameIndex[i]; break; }
      }
      if (!og) return;
      var rank = (term === q) ? 0 : (term.indexOf(q) === 0 ? 1 : 2);
      var hit = null;
      for (var j = 0; j < out.length; j++) {
        if (out[j].g === og) { hit = out[j]; break; }
      }
      /* While the title has no chip of its own, the row must say so: the chip
         it points at really does filter to "Other" and no further. It does not
         say the title is unfindable, because the machine lists are indexed and
         the ARCADES group below lists the actual stores.

         Once the title HAS a chip, the sentence is simply false and the note
         is dropped - the row now points at that game's own chip, which filters
         to exactly the game the user asked for. */
      var note = live ? null
        : info.label + " has no filter chip - see arcades below";
      if (hit) {
        if (rank < hit.rank) hit.rank = rank;
        if (!hit.note && note) hit.note = note;
      } else {
        out.push({ g: og, rank: rank, note: note });
      }
    });
    out.sort(function (x, y) {
      if (x.rank !== y.rank) return x.rank - y.rank;
      return C.GAME_ORDER.indexOf(x.g.slug) - C.GAME_ORDER.indexOf(y.g.slug);
    });
    return out.slice(0, MAX_GAMES);
  }

  function queryPlaces(q) {
    var out = [];
    placeIndex.forEach(function (p) {
      var r = termRank(p.terms, q);
      if (r !== -1) out.push({ p: p, rank: r });
    });
    out.sort(function (x, y) {
      if (x.rank !== y.rank) return x.rank - y.rank;
      return y.p.n - x.p.n;
    });
    return out.slice(0, MAX_PLACES);
  }

  /* Substring over the prebuilt haystack. Kept exactly as the documented
     contract: query(str) -> [{ a, hay }], capped at LEGACY_MAX. */
  function query(q) {
    var out = [];
    q = String(q || "").trim().toLowerCase();
    if (!q) return out;
    for (var i = 0; i < arcadeIndex.length && out.length < LEGACY_MAX; i++) {
      if (arcadeIndex[i].hay.indexOf(q) !== -1) out.push(arcadeIndex[i]);
    }
    return out;
  }

  function queryArcades(q) {
    var out = [];
    for (var i = 0; i < arcadeIndex.length && out.length < MAX_ARCADES; i++) {
      if (arcadeIndex[i].hay.indexOf(q) !== -1) out.push(arcadeIndex[i]);
    }
    return out;
  }

  /* ---------- per-game visible counts ---------- */
  /* "How many stores land on the map if I pick this row" - computed under the
     live source and cab filters, independent of whether the chip is already
     on. Cached because the answer only moves when those filters move. */

  var countCache = {};
  function invalidateCounts() { countCache = {}; }

  function visibleCountForGame(slug) {
    if (slug in countCache) return countCache[slug];
    var enabled = AM.state.get("enabledSources");
    var selCabs = AM.state.get("selectedCabs");
    var list1 = AM.data.plottable, n = 0;
    for (var i = 0; i < list1.length; i++) {
      var a = list1[i];
      if (!AM.markers.sourceEnabled(a, enabled)) continue;
      if (!AM.markers.matchesForGame(a, slug, selCabs)) continue;
      n++;
    }
    countCache[slug] = n;
    return n;
  }

  /* ---------- rendering ---------- */

  /* Escape, then wrap the matched run in <mark>.

     Indices from a whole-string toLowerCase() cannot be used against the
     original: a few characters change LENGTH when folded, and every later
     index then shifts. This data really contains one ("Funlab Forum
     İstanbul" - U+0130 folds to two code units), which made a search for
     "stanbul" highlight "tanbul". So the probe is built character by
     character while recording where each folded chunk started, and the match
     is mapped back through that table. */
  function foldIndex(text) {
    var low = "", map = [], i, f, j;
    for (i = 0; i < text.length; i++) {
      f = text.charAt(i).toLowerCase();
      for (j = 0; j < f.length; j++) map.push(i);
      low += f;
    }
    map.push(text.length);   /* one past the end, so a match at the tail maps */
    return { low: low, map: map };
  }

  function mark(text, q) {
    text = String(text == null ? "" : text);
    if (!q) return esc(text);
    var fi = foldIndex(text);
    var at = fi.low.indexOf(q);
    if (at === -1) return esc(text);
    var start = fi.map[at];
    var end = fi.map[at + q.length];
    if (typeof start !== "number" || typeof end !== "number" || end < start) {
      return esc(text);
    }
    return esc(text.slice(0, start)) + "<mark>" + esc(text.slice(start, end)) +
      "</mark>" + esc(text.slice(end));
  }

  /* Chips on a search result. gameLabelFor, not the raw label: a store whose
     only maimai cabinet is a dead pre-DX one must not be advertised as maimai
     DX here either, or the result row contradicts the panel it opens. */
  function gameChipsHtml(a) {
    return a.games.slice(0, 3).map(function (g) {
      return '<span class="gc" style="--c:' +
        (C.GAME_COLOR[g] || C.GAME_COLOR.other) + '">' +
        esc(AM.util.gameLabelFor(a, g)) + "</span>";
    }).join("");
  }

  function head(text) {
    return '<li class="og-head" role="presentation">' + esc(text) + "</li>";
  }

  function rowHtml(row, i, q) {
    var cls = "orow r-" + row.kind + (i === selIdx ? " sel" : "");
    var h = '<li id="omni-opt-' + i + '" role="option" data-i="' + i + '"' +
      ' aria-selected="' + (i === selIdx ? "true" : "false") + '" class="' + cls + '">';
    if (row.kind === "game") {
      var on = (AM.state.get("selectedGames") || new Set()).has(row.game.slug);
      h += '<span class="o-dot" style="--c:' + row.game.color + '"></span>' +
        '<span class="o-main">' +
        '<span class="o-title">' + mark(row.game.label, q) + "</span>" +
        (row.note ? '<span class="o-note">' + esc(row.note) + "</span>"
                  : '<span class="o-sub">' + (on ? "filter already on" : "add this game filter") + "</span>") +
        "</span>" +
        '<span class="o-n tabnum">' + U.num(row.count) + "</span>";
    } else if (row.kind === "arcade") {
      var a = row.a;
      /* Machine titles are in the haystack, so a row can match on a cabinet
         the name and address never mention - "valkyrie" or "pump it up" would
         otherwise return stores with no visible reason for being there. When
         the hit is in a title, show THAT title as the subtitle instead of the
         address, with the match highlighted, so the row explains itself. */
      var sub = a.addr || "", hitTitle = null;
      if (q && (a.name + " " + (a.addr || "") + " " + (a.pref || ""))
          .toLowerCase().indexOf(q) === -1) {
        var titles = AM.util.cabTitles(a);
        for (var ti = 0; ti < titles.length; ti++) {
          if (titles[ti].toLowerCase().indexOf(q) !== -1) { hitTitle = titles[ti]; break; }
        }
      }
      h += '<span class="o-main">' +
        '<span class="o-title">' + mark(a.name, q) + "</span>" +
        '<span class="o-sub">' +
        (hitTitle ? '<span class="o-hit">' + mark(hitTitle, q) + "</span>"
                  : mark(sub, q)) + "</span>" +
        '<span class="o-chips">' + gameChipsHtml(a) + "</span>" +
        "</span>" +
        '<span class="o-tag">' + esc(a.country || "?") + "</span>";
    } else {
      var p = row.place;
      h += '<span class="o-main">' +
        '<span class="o-title">' + mark(p.label, q) +
        (p.alt ? ' <span class="o-alt">' + mark(p.alt, q) + "</span>" : "") +
        "</span>" +
        '<span class="o-sub">' + esc(p.kind === "country" ? "country" : p.country || "") +
        " &middot; zoom to " + U.num(p.plottable) + " mapped</span>" +
        "</span>" +
        '<span class="o-n tabnum">' + U.num(p.n) + "</span>";
    }
    return h + "</li>";
  }

  /* A bare "No matches" tells the user the search failed but not what would
     have worked, and on a phone leaves them to clear a long query character by
     character. So the empty state names what this box actually searches, with
     one example per group, and offers a button that empties the field. The
     button is a real <button> so it is reachable by keyboard and by tap; the
     row itself is presentation and never becomes a selectable option (rows
     stays empty, so Enter and the arrow keys have nothing to land on). */
  function emptyHtml(q) {
    return '<li class="r-none" role="presentation">' +
      '<span class="rn-main">' +
      '<span class="rn-title">No matches for &ldquo;' + esc(q) + '&rdquo;</span>' +
      '<span class="rn-hint">Try a game (maimai, SDVX, IIDX), a city or ' +
      'prefecture (Osaka, 大阪), or an arcade name.</span>' +
      "</span>" +
      '<button type="button" class="rn-clear">Clear</button>' +
      "</li>";
  }

  function clearSearch() {
    input.value = "";
    close();
    input.focus();
  }

  function render(q) {
    if (!rows.length) {
      list.innerHTML = emptyHtml(input.value.trim());
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      input.removeAttribute("aria-activedescendant");
      return;
    }
    /* Fixed group order: Games, Arcades, Places. */
    var html = "", lastGroup = null;
    rows.forEach(function (row, i) {
      if (row.group !== lastGroup) { html += head(row.group); lastGroup = row.group; }
      html += rowHtml(row, i, q);
    });
    list.innerHTML = html;
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    if (selIdx >= 0) {
      input.setAttribute("aria-activedescendant", "omni-opt-" + selIdx);
      var el = list.querySelector("li.sel");
      if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function close() {
    /* A debounce started by the last keystroke is still pending here, and run()
       reads input.value, which pick() deliberately leaves in the box. Without
       this, picking a result inside the DEBOUNCE_MS window re-opened the
       dropdown on top of the store the user just chose. */
    clearTimeout(tmr);
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    selIdx = -1;
  }

  function run() {
    var q = input.value.trim().toLowerCase();
    if (!q) { close(); return; }
    rows = [];
    arcadeRows = [];
    queryGames(q).forEach(function (m) {
      rows.push({
        kind: "game", group: "Games", game: m.g, note: m.note,
        count: visibleCountForGame(m.g.slug)
      });
    });
    queryArcades(q).forEach(function (r) {
      arcadeRows.push(r);
      rows.push({ kind: "arcade", group: "Arcades", a: r.a });
    });
    queryPlaces(q).forEach(function (m) {
      rows.push({ kind: "place", group: "Places", place: m.p });
    });
    selIdx = -1;
    render(q);
  }

  /* ---------- picks ---------- */

  /* Show the chip the pick just turned on. openDrawer() alone leaves the map
     at its old width - panel.js only calls invalidateSize from its own toggle
     handler - so the resize is done here. */
  function revealChip(slug) {
    if (AM.panel && typeof AM.panel.openDrawer === "function") {
      AM.panel.openDrawer();
      if (typeof AM.panel.switchTab === "function") AM.panel.switchTab("filters");
      if (AM.map && AM.map.map) AM.map.map.invalidateSize();
    }
    var box = $("game-chips");
    if (!box) return;
    var chip = null;
    for (var i = 0; i < box.children.length; i++) {
      if (box.children[i].dataset.g === slug) { chip = box.children[i]; break; }
    }
    if (!chip) return;
    if (chip.scrollIntoView) chip.scrollIntoView({ block: "nearest" });
    /* Flash unconditionally: state.set dedupes an unchanged Set and would not
       emit, but the user still asked to be shown where that filter lives. */
    chip.classList.remove("chip-flash");
    void chip.offsetWidth;   /* restart the transition on a repeat pick */
    chip.classList.add("chip-flash");
    /* Tracked, because overlapping picks otherwise stack: the first pick's
       timer would land mid-flash on the second chip and cut it short. */
    clearTimeout(flashTimer);
    flashTimer = setTimeout(function () {
      chip.classList.remove("chip-flash");
    }, FLASH_MS);
  }

  function pickGame(row) {
    /* Never toggleGame(): the omnibox turns a filter ON, it does not flip a
       filter the user may already have on back off. */
    var next = new Set(AM.state.get("selectedGames") || []);
    next.add(row.game.slug);
    AM.state.set("selectedGames", next);
    revealChip(row.game.slug);
  }

  function pickArcade(row) {
    /* markers.js owns the fly + halo highlight; panel.js reveals a no-coords
       store. Both react to this one write. */
    AM.state.set("selectedArcade", row.a.id, { focus: true, source: "search" });
  }

  function pickPlace(row) {
    var p = row.place;
    if (!(p.plottable > 0)) return;
    /* Leaving a stale halo pinned to some other store while the map flies
       somewhere else reads as a bug. */
    if (AM.markers && typeof AM.markers.removeHalo === "function") AM.markers.removeHalo();
    AM.state.set("selectedArcade", null, { source: "search" });
    AM.map.map.fitBounds(
      L.latLngBounds([[p.minLat, p.minLng], [p.maxLat, p.maxLng]]),
      { padding: [40, 40], maxZoom: 12, animate: !C.REDUCED }
    );
  }

  function pick(i) {
    var row = rows[i];
    if (!row) return;
    close();
    input.blur();
    if (row.kind === "game") pickGame(row);
    else if (row.kind === "arcade") pickArcade(row);
    else pickPlace(row);
  }

  /* ---------- wiring ---------- */

  function tr(key, vars) {
    return (AM.i18n && AM.i18n.t) ? AM.i18n.t(key, vars) : key;
  }

  function syncPlaceholder() {
    if (!input) return;
    /* The long wording does not fit the box a phone can spare (measured:
       187 px of text in a 172 px field at 390 px viewport), and a clipped
       placeholder reads as breakage, so narrow screens get a short one.
       The aria-label always carries the full wording. */
    var narrow = window.matchMedia &&
      window.matchMedia("(max-width: 760px)").matches;
    var wide = tr("ui.search_wide");
    var short = tr("ui.search_narrow");
    if (!wide || wide === "ui.search_wide") {
      wide = "Search games, arcades, places...";
    }
    if (!short || short === "ui.search_narrow") short = "Search...";
    input.placeholder = narrow ? short : wide;
    input.setAttribute("aria-label", wide);
  }

  function build() {
    buildArcadeIndex();
    buildGameIndex();
    buildPlaceIndex();
    input = $("search");
    list = $("search-results");

    syncPlaceholder();
    if (AM.i18n && AM.i18n.on) {
      AM.i18n.on(function () {
        syncPlaceholder();
        /* Localized game names change; rebuild so result rows and
           typeahead match the current UI language. */
        try { buildGameIndex(); } catch (e) {}
      });
    }

    input.addEventListener("input", function () {
      clearTimeout(tmr);
      tmr = setTimeout(run, DEBOUNCE_MS);
    });
    input.addEventListener("keydown", function (e) {
      if (list.hidden) {
        /* Re-open the dropdown for text that is still in the box. */
        if (e.key === "ArrowDown" && input.value.trim()) { run(); e.preventDefault(); }
        return;
      }
      if (e.key === "ArrowDown") {
        selIdx = Math.min(selIdx + 1, rows.length - 1);
        render(input.value.trim().toLowerCase()); e.preventDefault();
      } else if (e.key === "ArrowUp") {
        selIdx = Math.max(selIdx - 1, 0);
        render(input.value.trim().toLowerCase()); e.preventDefault();
      } else if (e.key === "Enter") {
        pick(selIdx >= 0 ? selIdx : 0); e.preventDefault();
      } else if (e.key === "Escape") {
        close();
      }
    });
    /* mousedown, not click: the document-level outside-click handler below
       would otherwise close the list before the click landed. */
    list.addEventListener("mousedown", function (e) {
      /* The clear button in the empty state is not a result row. mousedown
         fires before the input's blur, so the field is emptied and refocused
         in one gesture. */
      if (e.target.closest(".rn-clear")) { clearSearch(); e.preventDefault(); return; }
      var li = e.target.closest("li[data-i]");
      if (li) { pick(+li.dataset.i); e.preventDefault(); }
    });
    /* Touch fires no mousedown before the tap's click, so the button needs a
       click path of its own for the phone, which is where a long mistyped
       query is hardest to clear. */
    list.addEventListener("click", function (e) {
      if (e.target.closest(".rn-clear")) { clearSearch(); e.preventDefault(); }
    });
    document.addEventListener("click", function (e) {
      if (!$("searchwrap").contains(e.target)) close();
    });

    AM.state.on("enabledSources", invalidateCounts);
    AM.state.on("selectedCabs", invalidateCounts);
  }

  AM.search = {
    build: build,
    /* documented contract, unchanged: [{ a, hay }] */
    query: query,
    close: close,
    getResults: function () { return arcadeRows.slice(); },
    /* omnibox additions */
    getRows: function () { return rows.slice(); },
    /* Exported so the filter chips and the settings source list print the
       SAME number the omnibox does. All three answer "how many stores land on
       the map if I pick this game", and before this they did not agree: the
       chips printed a build-time total that ignored the source and cab
       filters entirely. */
    visibleCountForGame: visibleCountForGame,
    queryGames: queryGames,
    queryPlaces: queryPlaces,
    placeIndex: function () { return placeIndex.slice(); },
    syncPlaceholder: syncPlaceholder,
    run: run
  };
})(window.AM);
