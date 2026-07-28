/* Arcade Maps - shared display formatters.

   Pure functions, no DOM and no state: any module can call these and get the
   same string. Loaded straight after state.js because markers.js and the
   detail UI both depend on it.

   Public surface:
     AM.format.fmtDistance(metres)          "820 m" / "4.2 km" / "1,180 km"
     AM.format.fmtCount(slugCounts)         ["maimai DX x9", "CHUNITHM x4"]
     AM.format.fmtCountLine(slugCounts)     the same, joined for one line
     AM.format.totalCabs(slugCounts)        summed cabs, or null when unknown
     AM.format.fmtPrice(amount, cur, fx)    "PHP 40 (~USD 0.68 / JPY 112 ...)"
     AM.format.fmtMoney(amount, cur, opts)  "USD 0.68" or "$0.68"
     AM.format.ensureFxRates(url)           lazy one-shot fetch, resolves rates
     AM.format.getFxRates()                 what has been loaded, or null
     AM.format.normalizeFx(blob)            table -> {code: perOneBase}
     AM.format.CURRENCY_SYMBOL              code -> symbol
     AM.format.FX_URL / FX_TARGETS          defaults

   FX file shape (data/fx_rates.json, optional - the data pipeline delivers it
   separately, and every price still renders without it):

     { "updated": "2026-07-27", "base": "USD",
       "rates": { "USD": 1, "JPY": 157.2, "PHP": 58.4, ... } }

   rates[X] is "how many X you get for one unit of base". A bare
   { "USD": 1, "JPY": 157.2 } map is accepted too. Nothing here fetches on its
   own: a caller has to ask, so a site with no price data makes no request. */
window.AM = window.AM || {};

(function (AM) {
  "use strict";

  var C = AM.consts, U = AM.util;

  var FX_URL = "data/fx_rates.json";

  /* Shown next to a local price by default. The local currency is dropped from
     this list at render time so a Japanese price never says "JPY 100 (~JPY 100)". */
  var FX_TARGETS = ["USD", "JPY", "HKD", "CNY"];

  /* Non-ASCII glyphs are written as \u escapes so this file is byte-identical
     under any encoding a tool or editor decides to use - the site is served as
     UTF-8, but a stray ANSI read of a literal yen sign would corrupt it.
     HK$/NT$/S$ keep the dollar family apart, and CNY takes a CN prefix so a
     yuan price is never misread as yen. */
  var CURRENCY_SYMBOL = {
    JPY: "\u00A5",        /* yen */
    USD: "$",
    HKD: "HK$",
    CNY: "CN\u00A5",      /* yuan, prefixed so it is not read as JPY */
    PHP: "\u20B1",        /* peso */
    TWD: "NT$",
    KRW: "\u20A9",        /* won */
    SGD: "S$",
    MYR: "RM",
    THB: "\u0E3F",        /* baht */
    VND: "\u20AB",        /* dong */
    IDR: "Rp",
    AUD: "A$",
    NZD: "NZ$",
    GBP: "\u00A3",        /* pound */
    EUR: "\u20AC",        /* euro */
    CAD: "C$"
  };

  /* Currencies whose smallest circulating unit is the whole unit: showing
     "JPY 112.35" for an arcade credit would be nonsense. */
  var ZERO_DECIMAL = { JPY: 1, KRW: 1, VND: 1, IDR: 1 };

  /* ---------- small numeric helpers ---------- */

  function isNum(v) { return typeof v === "number" && isFinite(v); }

  /* Up to `max` decimals, trailing zeros dropped: 40 -> "40", 4.90 -> "4.9". */
  function trimNum(v, max) {
    var s = Number(v).toFixed(max == null ? 2 : max);
    if (s.indexOf(".") !== -1) s = s.replace(/0+$/, "").replace(/\.$/, "");
    return s;
  }

  /* Group thousands without dragging in a locale-specific decimal separator. */
  function grouped(v) {
    return U && U.num ? U.num(v) : String(v);
  }

  /* Thousands separators on the integer part, decimals left alone: a VND price
     of 30000 has to read "30,000" or nobody can count the zeros. */
  function groupedStr(s) {
    var neg = s.charAt(0) === "-";
    if (neg) s = s.slice(1);
    var dot = s.indexOf(".");
    var whole = dot === -1 ? s : s.slice(0, dot);
    var rest = dot === -1 ? "" : s.slice(dot);
    return (neg ? "-" : "") + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + rest;
  }

  /* ---------- distance ---------- */

  /* Metres in, one human string out. Below a kilometre the metre form is the
     honest one; at 999.5 m and up the rounded km form reads "1.0 km" rather
     than "1000 m". Sub-10 m keeps a decimal so a 4 m walk is not "4 m" next to
     a 9 m one. */
  function fmtDistance(metres) {
    if (!isNum(metres) || metres < 0) return "";
    if (metres < 999.5) {
      return (metres < 10 ? metres.toFixed(1) : String(Math.round(metres))) + " m";
    }
    var km = metres / 1000;
    if (km < 10) return km.toFixed(1) + " km";
    return grouped(Math.round(km)) + " km";
  }

  /* ---------- cab counts ---------- */

  function gameLabel(slug) {
    return (C && C.GAME_LABEL && C.GAME_LABEL[slug]) || slug;
  }

  /* Sum of a game_counts map. null (not 0) when the data does not say, so a
     caller can tell "no cabs here" apart from "nobody counted". */
  function totalCabs(counts) {
    if (!counts || typeof counts !== "object") return null;
    var total = 0, seen = false;
    for (var k in counts) {
      if (!Object.prototype.hasOwnProperty.call(counts, k)) continue;
      var n = counts[k];
      if (isNum(n) && n > 0) { total += n; seen = true; }
    }
    return seen ? total : null;
  }

  /* ["maimai DX x9", "CHUNITHM x4"] in canonical game order, with any slug the
     constants do not know about appended rather than dropped. */
  function fmtCount(counts) {
    if (!counts || typeof counts !== "object") return [];
    var order = (C && C.GAME_ORDER) || [];
    var out = [], done = {};
    function push(slug) {
      var n = counts[slug];
      if (!isNum(n) || n <= 0 || done[slug]) return;
      done[slug] = true;
      out.push(gameLabel(slug) + " x" + trimNum(n, 0));
    }
    order.forEach(push);
    Object.keys(counts).forEach(push);
    return out;
  }

  function fmtCountLine(counts, sep) {
    return fmtCount(counts).join(sep == null ? ", " : sep);
  }

  /* ---------- money ---------- */

  /* Currency codes travel in from scraped data, so only accept the ISO shape
     and normalise the case before it reaches any markup. */
  function normCode(cur) {
    if (typeof cur !== "string") return "";
    var c = cur.trim().toUpperCase();
    return /^[A-Z]{3}$/.test(c) ? c : "";
  }

  /* Decimals that suit the magnitude: a 0.68 conversion needs cents, a 112
     one does not, and a zero-decimal currency never shows any. */
  function moneyDigits(v, code) {
    if (ZERO_DECIMAL[code]) return 0;
    var a = Math.abs(v);
    if (a >= 100) return 0;
    if (a >= 1) return 1;
    return 2;
  }

  /* opts: {symbol: use the glyph instead of the ISO code,
            approx: this is a converted value, so round it by magnitude,
            digits: force a decimal count}

     Without approx or digits the amount is shown as written, to two decimals
     at most: a real shelf price of 40 stays "40" and 4.50 stays "4.5". A
     conversion is approximate by nature, so approx trades the extra digits for
     something a reader can hold in their head. */
  function fmtMoney(amount, currency, opts) {
    if (!isNum(amount)) return "";
    opts = opts || {};
    var code = normCode(currency);
    var digits = opts.digits;
    if (digits == null && opts.approx) digits = moneyDigits(amount, code);
    var body = digits == null ? groupedStr(trimNum(amount, 2))
      : (digits === 0 ? grouped(Math.round(amount)) : groupedStr(amount.toFixed(digits)));
    if (!code) return body;
    if (opts.symbol) return (CURRENCY_SYMBOL[code] || code + " ") + body;
    return code + " " + body;
  }

  /* ---------- fx table ---------- */

  /* Accepts {base, rates} or a bare {code: rate} map and returns a flat
     {CODE: unitsPerOneBase} object, or null when there is nothing usable. */
  function normalizeFx(blob) {
    if (!blob || typeof blob !== "object") return null;
    var src = (blob.rates && typeof blob.rates === "object") ? blob.rates : blob;
    var out = null;
    Object.keys(src).forEach(function (k) {
      var code = normCode(k), v = src[k];
      if (!code || !isNum(v) || v <= 0) return;
      (out = out || {})[code] = v;
    });
    return out;
  }

  var fxRates = null, fxPromise = null;

  function getFxRates() { return fxRates; }

  /* One fetch per page, and only when a caller actually needs a conversion.
     A missing or broken file is not an error condition here: it resolves null
     and every price falls back to the local amount alone. */
  function ensureFxRates(url) {
    if (fxPromise) return fxPromise;
    var target = url || FX_URL;
    fxPromise = new Promise(function (resolve) {
      if (typeof fetch !== "function") { resolve(null); return; }
      fetch(target)
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (blob) { fxRates = normalizeFx(blob); resolve(fxRates); })
        .catch(function () { resolve(null); });
    });
    return fxPromise;
  }

  /* Test seam and a way for a caller that already holds the table (bundled in
     another payload) to install it without a second request. */
  function setFxRates(blob) {
    fxRates = normalizeFx(blob);
    fxPromise = Promise.resolve(fxRates);
    return fxRates;
  }

  /* ---------- price ---------- */

  /* "PHP 40 (~USD 0.68 / JPY 112 / HKD 5.3 / CNY 4.9)".
     fxRates is optional and may be the raw file blob, a normalised map, or
     omitted entirely (then whatever ensureFxRates loaded is used). With no
     table, or a table that does not know the local currency, the local amount
     is returned on its own - never a wrong conversion. */
  function fmtPrice(amount, currency, rates, opts) {
    if (!isNum(amount)) return "";
    opts = opts || {};
    var code = normCode(currency);
    var local = fmtMoney(amount, code, { symbol: !!opts.symbol });
    var table = normalizeFx(rates) || fxRates;
    if (!table || !code || !isNum(table[code]) || table[code] <= 0) return local;

    var inBase = amount / table[code];
    var targets = opts.targets || FX_TARGETS;
    var parts = [];
    targets.forEach(function (t) {
      var tc = normCode(t);
      if (!tc || tc === code || !isNum(table[tc]) || table[tc] <= 0) return;
      var v = inBase * table[tc];
      parts.push(fmtMoney(v, tc, { symbol: !!opts.symbol, approx: true }));
    });
    if (!parts.length) return local;
    return local + " (~" + parts.join(" / ") + ")";
  }

  AM.format = {
    FX_URL: FX_URL,
    FX_TARGETS: FX_TARGETS,
    CURRENCY_SYMBOL: CURRENCY_SYMBOL,
    ZERO_DECIMAL: ZERO_DECIMAL,
    fmtDistance: fmtDistance,
    fmtCount: fmtCount,
    fmtCountLine: fmtCountLine,
    totalCabs: totalCabs,
    fmtMoney: fmtMoney,
    fmtPrice: fmtPrice,
    normalizeFx: normalizeFx,
    ensureFxRates: ensureFxRates,
    getFxRates: getFxRates,
    setFxRates: setFxRates,
    trimNum: trimNum
  };
})(window.AM);
