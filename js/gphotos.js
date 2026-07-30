/* Arcade Maps - Google Places photos, fetched at runtime and never stored.

   WHY THIS FILE LOOKS LIKE THIS
   -----------------------------
   Only ~7.5% of arcades have a real venue photo of their own (Japan ~3%,
   China ~0%). Google has a photo of most of the rest. We are allowed to show
   one; we are not allowed to keep one. Google's Place Photos documentation is
   blunt about it:

       "You cannot cache a photo name. Also, the name can expire."

   So this module stores NOTHING durable. No localStorage, no sessionStorage,
   no IndexedDB, no cookie, and nothing written back into any data file. The
   only cache is a plain JavaScript object that dies with the tab, and it
   exists purely so that closing and reopening the same panel does not bill a
   second time.

   The one thing we DO keep is the place ID, which Google exempts explicitly
   ("Place IDs are exempt from the caching restrictions"). scrapers/place_ids.py
   resolves those offline into data/place_ids.json, and this module joins on it.

   COST IS THE OTHER DESIGN CONSTRAINT
   -----------------------------------
   "Place Details Photos" is an Enterprise SKU: 1,000 free calls per month,
   then USD 7.00 per 1,000. There are 13,534 arcades. So a photo is fetched
   ONLY when a human opens a place panel for an arcade that has no better
   photo. Never on map load, never for a marker, never speculatively, never in
   a loop over the dataset. One panel open by one reader is at most one photo.

   TWO CALLS, NOT ONE
   ------------------
   Because the photo NAME may not be cached, it has to be re-fetched every
   session before the bytes can be requested:

     1. GET places/{place_id}?fields=photos    -> the photo name + attributions
        (Place Details Essentials IDs Only - free, unlimited)
     2. GET {name}/media?skipHttpRedirect=true -> a short-lived photoUri
        (Place Details Photos - Enterprise, 1,000/month free, then $7/1k)

   Step 2 uses skipHttpRedirect=true deliberately. The default redirects
   straight to the image, and a bare <img src> cannot detect failure: Google
   answers an over-quota request with HTTP 403 AND A QUOTA NOTIFICATION IMAGE,
   which an <img> renders happily. The site would then show Google's "you are
   over quota" graphic captioned as if it were the arcade - the exact class of
   confident wrong information this project keeps having to remove. Asking for
   JSON instead means res.ok is a real check, and 403/429 fall back silently to
   the existing photo chain. Both endpoints send Access-Control-Allow-Origin
   for the calling origin (verified live 2026-07-30), so the fetch works from
   a static page with no backend.

   ABSENT KEY IS A TOTAL NO-OP
   ---------------------------
   Most visitors have no key, and the owner's public deploy may not either.
   With no key configured this module makes no request, logs nothing, and the
   site behaves exactly as it does today. Silence is the requirement: a console
   error on every panel open would be a regression for every visitor.

   Loaded before js/panel.js. Exposes AM.gphotos. */

window.AM = window.AM || {};

(function (AM) {
  "use strict";

  /* ---------- configuration ---------- */

  /* The key lives in one obvious place: window.AM_CONFIG, set by an inline
     <script> in index.html. Inline rather than a js/config.js file on purpose -
     a missing config FILE 404s in every visitor's console, and an absent
     inline object simply reads as undefined. See docs/GOOGLE_PHOTOS.md. */
  function config() {
    return (window.AM_CONFIG && typeof window.AM_CONFIG === "object")
      ? window.AM_CONFIG : {};
  }

  function apiKey() {
    var k = config().googleMapsApiKey;
    return (typeof k === "string" && k.trim()) ? k.trim() : null;
  }

  function enabled() { return !!apiKey(); }

  /* Confidence floor for using a resolved place ID.

     scrapers/place_ids.py grades every match high / medium / low. "low" means
     the name agreement was weak, which in a shopping centre means the pick may
     be the shop next door - so low is stored for auditing and never used here.
     "medium" includes centroid-placed (approx) rows, whose coordinate never
     corroborated anything, so the default floor is "high": on a map whose
     whole value is being right about WHERE something is, a missing photo is a
     far cheaper mistake than a photo of the wrong building.

     Set AM_CONFIG.googlePhotoMinConfidence = "medium" to loosen it. */
  var CONFIDENCE_RANK = { high: 3, medium: 2, low: 1 };
  var DEFAULT_MIN_CONFIDENCE = "high";

  function minConfidenceRank() {
    var want = config().googlePhotoMinConfidence || DEFAULT_MIN_CONFIDENCE;
    return CONFIDENCE_RANK[want] || CONFIDENCE_RANK[DEFAULT_MIN_CONFIDENCE];
  }

  /* Requested pixel size. The hero is 148px tall (62-132px on a phone) and at
     most ~560px wide, so 800 covers a 2x display without paying for pixels
     nobody sees. Google scales down and preserves aspect ratio. */
  var MAX_W = 800, MAX_H = 500;

  var PLACE_IDS_URL = "data/place_ids.json";
  var DETAILS_URL = "https://places.googleapis.com/v1/places/";
  var MEDIA_BASE = "https://places.googleapis.com/v1/";

  /* ---------- session-only state ---------- */

  /* arcade id -> {status, url, attributions, googleMapsUri}
     Plain object, lives in memory, dies with the tab. Deliberately NOT
     localStorage: persisting any of this would be caching a photo name. */
  var photos = Object.create(null);

  /* Arcades already asked for, so a re-render (the panel re-renders when
     enrichment lands) cannot fire a second billable request. */
  var inflight = Object.create(null);

  var placeIds = null;          /* parsed data/place_ids.json, or {} */
  var placeIdsPromise = null;
  var quotaBlocked = false;     /* set on the first 403; stops all fetching */

  /* Bumped whenever a photo arrives, so panel.js can tell that re-rendering
     would now produce something different. Mirrors its own dataVersion idea. */
  var version = 0;

  function onArrive() { version++; }
  var listeners = [];

  function notify(arcadeId) {
    onArrive();
    for (var i = 0; i < listeners.length; i++) {
      try { listeners[i](arcadeId); } catch (e) { /* never break the panel */ }
    }
  }

  /* ---------- place id table ---------- */

  /* data/place_ids.json does not exist until the owner runs a resolve, and
     most forks will never have one. The fetch is therefore gated on a
     configured key: without one, we never even ask, so a keyless visitor gets
     no 404 in the console. */
  function ensurePlaceIds() {
    if (!placeIdsPromise) {
      placeIdsPromise = new Promise(function (resolve) {
        if (!enabled() || typeof fetch !== "function") {
          placeIds = {};
          resolve(placeIds);
          return;
        }
        fetch(PLACE_IDS_URL, { cache: "no-cache" })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (blob) {
            placeIds = (blob && blob.places && typeof blob.places === "object")
              ? blob.places : {};
            resolve(placeIds);
          })
          .catch(function () { placeIds = {}; resolve(placeIds); });
      });
    }
    return placeIdsPromise;
  }

  /* The stored record for an arcade, if it clears the confidence floor. */
  function recordFor(a) {
    if (!placeIds || !a) return null;
    var rec = placeIds[a.id];
    if (!rec && a.id !== undefined) rec = placeIds[String(a.id)];
    if (!rec || typeof rec !== "object" || !rec.place_id) return null;
    var rank = CONFIDENCE_RANK[rec.confidence] || 0;
    if (rank < minConfidenceRank()) return null;
    return rec;
  }

  /* ---------- fetching ---------- */

  function jsonFetch(url) {
    return fetch(url, { method: "GET" }).then(function (res) {
      if (res.status === 403) {
        /* Over quota, or the key is restricted away from this origin. Either
           way, asking again this session is pointless and would only burn more
           calls, so stop for good and let the existing chain take over. */
        quotaBlocked = true;
        return null;
      }
      if (res.status === 429) return null;   /* rate limited; just skip */
      if (!res.ok) return null;
      return res.json();
    });
  }

  /* Step 1: the photo name. Free (Essentials IDs Only). The name is used
     immediately and never written anywhere. */
  function fetchPhotoName(placeId, key) {
    var url = DETAILS_URL + encodeURIComponent(placeId) +
      "?fields=photos,googleMapsUri&key=" + encodeURIComponent(key);
    return jsonFetch(url).then(function (blob) {
      if (!blob || !Array.isArray(blob.photos) || !blob.photos.length) {
        return null;
      }
      var p = blob.photos[0];
      if (!p || typeof p.name !== "string" || !p.name) return null;
      return {
        name: p.name,
        attributions: Array.isArray(p.authorAttributions)
          ? p.authorAttributions : [],
        googleMapsUri: typeof blob.googleMapsUri === "string"
          ? blob.googleMapsUri : null
      };
    });
  }

  /* Step 2: the bytes. THIS is the Enterprise-billed call.

     skipHttpRedirect=true so a failure is a status code we can read rather
     than a quota graphic we would render as the venue. */
  function fetchPhotoUri(photoName, key) {
    /* Google's media URL is v1/{name}/media, where {name} is the photo
       resource "places/{place_id}/photos/{photo_resource}". The /media suffix
       is NOT part of the name the Details call returns, so it is appended
       here. Omitting it silently returns a photo resource with no photoUri
       rather than an error, which reads as "this place has no photo". */
    var name = String(photoName).replace(/\/media$/, "");
    var url = MEDIA_BASE + name + "/media" +
      "?maxWidthPx=" + MAX_W + "&maxHeightPx=" + MAX_H +
      "&skipHttpRedirect=true&key=" + encodeURIComponent(key);
    return jsonFetch(url).then(function (blob) {
      if (!blob || typeof blob.photoUri !== "string" || !blob.photoUri) {
        return null;
      }
      return blob.photoUri;
    });
  }

  /* Ask for a photo for this arcade. Idempotent per session and per arcade.

     Returns nothing useful: the caller renders from get() and is told to
     re-render through the listener. That keeps this module free of any
     knowledge of the panel's markup. */
  function request(a) {
    if (!a || !enabled() || quotaBlocked) return;
    if (typeof fetch !== "function") return;
    var id = String(a.id);
    if (inflight[id] || photos[id]) return;
    inflight[id] = true;

    ensurePlaceIds().then(function () {
      var rec = recordFor(a);
      if (!rec) { photos[id] = { status: "none" }; return null; }
      var key = apiKey();
      if (!key) { photos[id] = { status: "none" }; return null; }

      return fetchPhotoName(rec.place_id, key).then(function (meta) {
        if (!meta) { photos[id] = { status: "none" }; return null; }
        return fetchPhotoUri(meta.name, key).then(function (uri) {
          if (!uri) { photos[id] = { status: "none" }; return null; }
          photos[id] = {
            status: "ok",
            url: uri,
            attributions: meta.attributions,
            googleMapsUri: meta.googleMapsUri
          };
          notify(a.id);
          return null;
        });
      });
    }).catch(function () {
      /* A network failure must be indistinguishable from "no photo": the
         panel keeps its existing fallback and the console stays clean. */
      photos[id] = { status: "none" };
    });
  }

  /* What we have for this arcade right now, or null. Synchronous, so the
     panel's string builders can call it without becoming async. */
  function get(a) {
    if (!a || !enabled()) return null;
    var rec = photos[String(a.id)];
    if (!rec || rec.status !== "ok" || !rec.url) return null;
    return rec;
  }

  /* ---------- rendering ---------- */

  /* Emitted in the SAME record shape js/panel.js normalises its own photos
     into ({url, credit, license, page, kind}), so the panel needs no separate
     rendering path for a Google photo and this module needs no knowledge of
     the panel's markup. Whatever the gallery does to a photo - lazy slide
     promotion, the credit line, the CSS - it does to this one identically.

     ATTRIBUTION. Google's Place Photos doc: "if the returned photo element
     includes a value in the authorAttributions field, you must include the
     additional attribution in your application wherever you display the
     image." The policy page adds "You must always credit the author when
     displaying photos or reviews" and requires that users "retain access to
     view the individual source photo or review on Google Maps using the
     provided googleMapsUri".

     So the credit text names the photo's author and Google Maps, and the link
     goes to the place's googleMapsUri, which is the route back to the original
     photo. Both halves are required; neither is decoration. */
  function records(a) {
    var rec = get(a);
    if (!rec) return [];
    var url = AM.util.safeUrl(rec.url);
    if (!url) return [];

    var names = [];
    var atts = rec.attributions || [];
    for (var i = 0; i < atts.length && i < 2; i++) {
      if (atts[i] && atts[i].displayName) names.push(atts[i].displayName);
    }

    return [{
      url: url,
      credit: names.length
        ? "photo: " + names.join(", ") + " / Google Maps"
        : "photo via Google Maps",
      license: null,
      page: rec.googleMapsUri ? AM.util.safeUrl(rec.googleMapsUri) : null,
      kind: "google"
    }];
  }

  AM.gphotos = {
    enabled: enabled,
    request: request,
    get: get,
    records: records,
    version: function () { return version; },
    onPhoto: function (fn) { if (typeof fn === "function") listeners.push(fn); },

    /* test seams. Nothing here persists, so a test can drive the whole path
       without a key and without touching the network. */
    _classify: recordFor,
    _setPlaceIds: function (blob) {
      placeIds = (blob && blob.places) ? blob.places : (blob || {});
      placeIdsPromise = Promise.resolve(placeIds);
    },
    _inject: function (arcadeId, rec) {
      photos[String(arcadeId)] = rec;
      notify(arcadeId);
    },
    _reset: function () {
      photos = Object.create(null);
      inflight = Object.create(null);
      quotaBlocked = false;
    },
    _quotaBlocked: function () { return quotaBlocked; }
  };
})(window.AM);
