"""Unit tests for scrapers/place_ids.py match verification and the no-key path.

Run: python scrapers/test_place_ids.py

Everything here is offline. Google is never called: the Text Search responses
are saved fixtures shaped exactly like the real ones (places[] with id,
displayName.text, formattedAddress, location.latitude/longitude), and the one
transport test monkeypatches _request.

The rejection cases are the point of the file. A wrong place ID puts a photo of
the wrong building on an arcade, so the tests that matter are the ones proving
we say no: the mall tenant 40 m away with an unrelated name, the same-named
chain branch in another city, and the district centroid that cannot be
verified by distance at all.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_ids as P

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):   # pragma: no cover
    pass

FAILED = []
RAN = []


def check(label, cond, detail=""):
    print("%s  %s%s" % ("PASS" if cond else "FAIL", label,
                        ("  <- " + detail) if detail else ""))
    RAN.append(label)
    if not cond:
        FAILED.append(label)


def place(pid, name, addr, lat, lng):
    """One Text Search result, in Google's exact response shape."""
    return {
        "id": pid,
        "displayName": {"text": name, "languageCode": "ja"},
        "formattedAddress": addr,
        "location": {"latitude": lat, "longitude": lng},
    }


def arcade(aid, name, lat, lng, country="Japan", **kw):
    a = {"id": aid, "name": name, "lat": lat, "lng": lng, "country": country,
         "addr": kw.pop("addr", "somewhere")}
    a.update(kw)
    return a


# ------------------------------------------------------- classify() grading --

def test_classify():
    print("\n-- classify(): distance x name grading --")

    conf, why = P.classify(12.0, 0.95, brand_ok=True)
    check("exact name on top of the pin -> high", conf == "high", why)

    conf, why = P.classify(120.0, 0.62, brand_ok=True)
    check("good name, 120m -> high", conf == "high", why)

    conf, why = P.classify(280.0, 0.62, brand_ok=True)
    check("good name, 280m (inside 300m gate) -> medium",
          conf == "medium", why)

    # A matching brand head under the score gate is NOT enough on its own:
    # "Sega"/"Segafredo Cafe" agrees on its head and scores 0.43. Failing
    # safe here costs a miss; accepting would cost a wrong photo.
    conf, why = P.classify(40.0, 0.30, brand_ok=True)
    check("low score, same brand head, 40m away -> low, NOT accepted",
          conf == "low", "%s/%s" % (conf, why))

    # ---- the rejections ----
    conf, why = P.classify(301.0, 1.00, brand_ok=True)
    check("REJECT: perfect name but 301m away (chain branch)",
          conf == "reject" and why == "too_far",
          "%s/%s" % (conf, why))

    conf, why = P.classify(15000.0, 1.00, brand_ok=True)
    check("REJECT: identical chain name in another city",
          conf == "reject", why)

    conf, why = P.classify(None, 1.00, brand_ok=True)
    check("REJECT: no coordinate on our side, so no distance test",
          conf == "reject" and why == "no_coordinates",
          "%s/%s" % (conf, why))

    # THE case the score alone gets wrong: a neighbouring arcade whose name
    # shares the district suffix and therefore scores HIGHER than a true
    # cross-script match. Distance cannot save this; only the brand head can.
    conf, why = P.classify(30.0, 0.70, brand_ok=False)
    check("REJECT: 0.70 score, 30m away, but a DIFFERENT brand "
          "(GiGO Shinjuku vs Namco Shinjuku)",
          conf == "reject" and why == "brand_mismatch",
          "%s/%s" % (conf, why))

    conf, why = P.classify(30.0, 0.45, brand_ok=False)
    check("REJECT: mid score and different brand stays out of high/medium",
          conf == "low", "%s/%s" % (conf, why))

    # ---- approx (centroid) rows ----
    conf, why = P.classify(2500.0, 0.90, approx_level="district",
                           brand_ok=True)
    check("approx district + strong name -> medium, never high",
          conf == "medium" and why == "approx_name_only",
          "%s/%s" % (conf, why))

    conf, why = P.classify(2500.0, 0.70, approx_level="district",
                           brand_ok=True)
    check("REJECT: approx district with only a 0.70 name",
          conf == "reject" and "approx_needs_name" in why,
          "%s/%s" % (conf, why))

    conf, why = P.classify(2500.0, 0.99, approx_level="district",
                           brand_ok=False)
    check("REJECT: approx district, perfect score, wrong brand",
          conf == "reject" and why == "approx_brand_mismatch",
          "%s/%s" % (conf, why))

    conf, why = P.classify(40000.0, 0.99, approx_level="district",
                           brand_ok=True)
    check("REJECT: approx district, 40km from the centroid",
          conf == "reject" and "too_far" in why, "%s/%s" % (conf, why))

    conf, why = P.classify(40000.0, 0.99, approx_level="city", brand_ok=True)
    check("approx CITY tolerates 40km (city centroid is coarser)",
          conf == "medium", "%s/%s" % (conf, why))

    # A near-miss on the boundary should not silently flip grade.
    at = P.classify(300.0, 0.62, brand_ok=True)[0]
    over = P.classify(300.1, 0.62, brand_ok=True)[0]
    check("300m boundary is inclusive, 300.1m is not",
          at == "medium" and over == "reject", "%s / %s" % (at, over))


# ------------------------------------------------------------- score_name() --

def test_score_name():
    print("\n-- score_name(): shared comparer, reported raw --")

    s = P.score_name("GiGO Akihabara 3", "GiGO Akihabara 3")
    check("identical names score 1.0", s == 1.0, "%.3f" % s)

    s = P.score_name("アミパラここじゃ店", "AmiPara Kokoja")
    check("kana vs romaji for the same venue scores as a match",
          s >= 0.55, "%.3f" % s)

    s = P.score_name("Taito Station Shinjuku", "Starbucks Coffee Shinjuku")
    check("unrelated tenant in the same building scores under the gate",
          s < P.MIN_NAME_SIM, "%.3f" % s)

    s = P.score_name(None, "GiGO")
    check("missing name scores 0", s == 0.0, "%.3f" % s)

    # The score is reported RAW: no substring floor is applied any more,
    # because flooring it promoted "Round1" over "Roundabout Cafe".
    s = P.score_name("Round1", "Roundabout Cafe")
    check("no hidden floor inflates an unrelated name", s < P.MIN_NAME_SIM,
          "%.3f" % s)


# ------------------------------------------------------------ brand_agrees --

def test_brand_agrees():
    print("\n-- brand_agrees(): the front of the name, across scripts --")

    check("truncation agrees ('GiGO' / 'GiGO Akihabara 1')",
          P.brand_agrees("GiGO", "GiGO Akihabara 1") is True)
    check("branch suffix differs but brand agrees",
          P.brand_agrees("Round1 Sakai", "Round1 Stadium Sakai") is True)
    check("kana vs romaji brand agrees",
          P.brand_agrees("GiGO Akihabara 3", "ギーゴ秋葉原3号館") is True)
    check("kana vs romaji, long form",
          P.brand_agrees("タイトーステーション 新宿東口店",
                         "Taito Station Shinjuku East") is True)

    check("different arcade brands in one district do NOT agree",
          P.brand_agrees("GiGO Shinjuku", "Namco Shinjuku") is False)
    check("Taito Station vs Round1 in one district do NOT agree",
          P.brand_agrees("Taito Station Ikebukuro",
                         "Round1 Ikebukuro") is False)
    check("an unrelated tenant does not agree",
          P.brand_agrees("Taito Station Shinjuku",
                         "Starbucks Coffee Shinjuku") is False)
    check("a mall is not its tenant",
          P.brand_agrees("GiGO Ikebukuro 3", "Sunshine City") is False)

    check("a name shorter than the prefix floor never matches",
          P.brand_agrees("GO", "GiGO") is False)
    check("an empty name never matches", P.brand_agrees("", "GiGO") is False)
    check("None never matches", P.brand_agrees(None, "GiGO") is False)


def test_adversarial_pairs_end_to_end():
    """The whole point of the module, as a table.

    Every DIFFERENT row here is a real shape a Text Search returns within
    300 m of an arcade. None of them may be accepted at any confidence a
    photo would be fetched at.
    """
    print("\n-- adversarial table: nothing wrong may be accepted --")

    same = [
        ("アミパラここじゃ店", "AmiPara Kokoja"),
        ("Round1 Stadium Machida", "ROUND1 Machida"),
        ("Taito Station", "Taito Station Kinshicho"),
        ("Taito Station Akihabara", "Taito Station Akihabara"),
        ("Round1 Stadium Sakai", "Round1 Sakai"),
    ]
    # Same venue, but our romanizer cannot bridge the writing systems well
    # enough to prove it. These MUST end up as misses, not as guesses: the
    # test asserts they are refused, so if the comparer ever improves this
    # list is the thing that has to be revisited deliberately.
    same_but_unprovable = [
        ("GiGO Akihabara 3", "ギーゴ秋葉原3号館"),
        ("ラウンドワン スタジアム 町田店", "Round1 Stadium Machida"),
    ]
    different = [
        ("Taito Station Ikebukuro", "Round1 Ikebukuro"),
        ("GiGO Shinjuku", "Namco Shinjuku"),
        ("Club Sega Akihabara", "GiGO Akihabara 3"),
        ("Sega", "Segafredo Cafe"),
        ("Taito Station", "Tait Bar"),
        ("Round1", "Roundabout Cafe"),
        ("Game Panic", "Game Fantasia"),
        ("Silk Hat", "Silky Cafe"),
        ("Namco Namba", "Bic Camera Namba"),
        ("Adores Shibuya", "Tsutaya Shibuya"),
        ("Taito Station Shinjuku", "Starbucks Coffee Shinjuku"),
        ("マツモトキヨシ 新宿", "タイトーステーション 新宿"),
        ("GiGO Ikebukuro 3", "Sunshine City"),
    ]

    # Judge them all at 30 m, the hardest setting: close enough that distance
    # gives every candidate the benefit of the doubt.
    def grade(a, b):
        return P.classify(30.0, P.score_name(a, b),
                          brand_ok=P.brand_agrees(a, b))[0]

    accepted_same = 0
    for a, b in same:
        g = grade(a, b)
        if g in ("high", "medium"):
            accepted_same += 1
        else:
            print("     (same pair not accepted: %s | %s -> %s)" % (a, b, g))

    false_accepts = []
    for a, b in different:
        g = grade(a, b)
        if g in ("high", "medium"):
            false_accepts.append("%s | %s -> %s (sim=%.2f brand=%s)"
                                 % (a, b, g, P.score_name(a, b),
                                    P.brand_agrees(a, b)))

    check("ZERO different-venue pairs are accepted (%d/%d)"
          % (len(false_accepts), len(different)),
          not false_accepts, "; ".join(false_accepts))
    check("all %d same-venue pairs are accepted (got %d)"
          % (len(same), accepted_same), accepted_same == len(same),
          str(accepted_same))

    # The known blind spot, asserted rather than hidden.
    unproven = [(a, b, grade(a, b)) for a, b in same_but_unprovable]
    check("known cross-script blind spot yields a MISS, never a wrong photo",
          all(g not in ("high", "medium") for _, _, g in unproven),
          "; ".join("%s|%s->%s" % t for t in unproven))


# ------------------------------------------------- best_candidate() picking --

def test_best_candidate_picks_the_right_tenant():
    print("\n-- best_candidate(): a mall with several tenants --")

    # Our pin: GiGO inside a Tokyo shopping centre.
    a = arcade(101, "GiGO Ikebukuro 3", 35.729000, 139.710000)

    # Google returns the mall itself, a coffee shop 40 m away, and the arcade.
    places = [
        place("mall", "Sunshine City", "1-1 Higashi-Ikebukuro",
              35.729100, 139.710100),
        place("cafe", "Starbucks Coffee Sunshine", "1-1 Higashi-Ikebukuro",
              35.729300, 139.710200),
        place("gigo", "GiGO Ikebukuro 3", "1-1 Higashi-Ikebukuro",
              35.729050, 139.710050),
    ]
    chosen, rejects = P.best_candidate(a, places)
    check("picks the arcade, not the mall or the cafe",
          chosen and chosen["place_id"] == "gigo",
          chosen["place_id"] if chosen else "None")
    check("grades that pick high", chosen and chosen["confidence"] == "high",
          chosen["confidence"] if chosen else "")
    check("records dist_m and name_sim for audit",
          chosen and chosen["dist_m"] is not None
          and chosen["name_sim"] is not None,
          json.dumps({k: chosen[k] for k in ("dist_m", "name_sim")})
          if chosen else "")
    check("the losers are all kept in rejects", len(rejects) == 2,
          str(len(rejects)))


def test_best_candidate_rejects_a_distant_chain_branch():
    print("\n-- best_candidate(): identically named branch, wrong city --")

    a = arcade(102, "Round1 Stadium", 34.702500, 135.495900)   # Osaka
    places = [
        # Tokyo, ~400 km away, name identical. This is the money case: name
        # alone would accept it and put a Tokyo photo on an Osaka arcade.
        place("tokyo", "Round1 Stadium", "Tokyo", 35.689500, 139.691700),
    ]
    chosen, rejects = P.best_candidate(a, places)
    check("REJECT: nothing chosen", chosen is None,
          chosen["place_id"] if chosen else "None")
    check("rejection reason recorded as too_far",
          rejects and rejects[0]["reason"] == "too_far",
          rejects[0]["reason"] if rejects else "")


def test_best_candidate_rejects_a_near_but_unrelated_venue():
    print("\n-- best_candidate(): right spot, wrong business --")

    a = arcade(103, "Taito Station Akihabara", 35.698300, 139.773100)
    places = [
        # 20 m away, but it is a pharmacy. Distance alone would take it.
        place("pharm", "Matsumoto Kiyoshi", "Akihabara",
              35.698310, 139.773300),
    ]
    chosen, rejects = P.best_candidate(a, places)
    check("20m away with an unrelated name is NOT graded high",
          chosen is None or chosen["confidence"] != "high",
          chosen["confidence"] if chosen else "None")
    if chosen:
        check("...and it is at most medium, so a stricter frontend gate "
              "can refuse it", chosen["confidence"] in ("medium", "low"),
              chosen["confidence"])


def test_best_candidate_empty_and_malformed():
    print("\n-- best_candidate(): empty / malformed input --")

    a = arcade(104, "Somewhere", 35.0, 139.0)
    chosen, rejects = P.best_candidate(a, [])
    check("no results -> no pick, no crash", chosen is None and rejects == [])

    chosen, _ = P.best_candidate(a, [{"displayName": {"text": "x"}}])
    check("a result with no id is skipped", chosen is None)

    chosen, _ = P.best_candidate(a, [{"id": "z", "displayName": {"text":
                                     "Somewhere"}}])
    check("a result with no location is rejected (no distance test)",
          chosen is None)

    b = arcade(105, "Nowhere", None, None)
    chosen, _ = P.best_candidate(b, [place("p", "Nowhere", "x", 35.0, 139.0)])
    check("an arcade with no coordinates never resolves", chosen is None)


# ------------------------------------------------------------ store / dates --

def test_stale():
    print("\n-- stale(): Google's 12-month refresh advice --")
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=30)).isoformat()
    old = (date.today() - timedelta(days=500)).isoformat()
    check("30 days old is fresh", P.stale(recent) is False)
    check("500 days old is stale", P.stale(old) is True)
    check("no date at all is stale", P.stale(None) is True)
    check("garbage date is stale", P.stale("not-a-date") is True)


def test_store_roundtrip():
    print("\n-- store: load/save keeps places and misses --")
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "place_ids.json")
        s = P.empty_store()
        s["places"]["7"] = {"place_id": "abc", "resolved_at": "2026-01-01"}
        s["misses"]["8"] = {"reason": "no_results"}
        P.save_store(path, s)
        back = P.load_store(path)
        check("places survive a round trip",
              back["places"]["7"]["place_id"] == "abc")
        check("misses survive a round trip",
              back["misses"]["8"]["reason"] == "no_results")
        check("updated is stamped", bool(back["updated"]))

        blob = json.load(open(path, encoding="utf-8"))
        joined = json.dumps(blob).lower()
        check("NO photo name or photo bytes are stored",
              "photo" not in joined or "photos" not in blob,
              "the file must only ever carry IDs")

        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{ this is not json")
        back = P.load_store(path)
        check("a corrupt file starts fresh instead of crashing",
              back["places"] == {})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------- the no-key path --

def test_no_key_is_a_silent_noop():
    print("\n-- no GOOGLE_MAPS_API_KEY: no request, no file, exit 0 --")

    tmp = tempfile.mkdtemp()
    calls = []
    real_request = P._request
    P._request = lambda *a, **k: calls.append(a) or {}
    saved = os.environ.pop(P.ENV_KEY, None)
    try:
        rc = P.main(["--out", tmp])
        check("exit code is 0", rc == 0, str(rc))
        check("zero HTTP calls were made", calls == [], str(len(calls)))
        check("no place_ids.json was written",
              not os.path.exists(os.path.join(tmp, "place_ids.json")))

        os.environ[P.ENV_KEY] = "   "
        rc = P.main(["--out", tmp])
        check("a whitespace-only key is treated as absent",
              rc == 0 and calls == [])
    finally:
        P._request = real_request
        os.environ.pop(P.ENV_KEY, None)
        if saved is not None:
            os.environ[P.ENV_KEY] = saved
        shutil.rmtree(tmp, ignore_errors=True)


def test_all_requires_yes():
    print("\n-- --all cannot bill by accident --")

    tmp = tempfile.mkdtemp()
    calls = []
    real_request = P._request
    P._request = lambda *a, **k: calls.append(a) or {}
    saved = os.environ.get(P.ENV_KEY)
    os.environ[P.ENV_KEY] = "test-key-not-real"
    try:
        with open(os.path.join(tmp, "arcades.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"arcades": [
                arcade(i, "Arcade %d" % i, 35.0 + i / 1000.0, 139.0)
                for i in range(5)]}, fh)

        rc = P.main(["--out", tmp, "--all"])
        check("--all without --yes exits 1 and requests nothing",
              rc == 1 and calls == [], "rc=%s calls=%d" % (rc, len(calls)))

        rc = P.main(["--out", tmp, "--dry-run"])
        check("--dry-run requests nothing", rc == 0 and calls == [],
              "rc=%s calls=%d" % (rc, len(calls)))
    finally:
        P._request = real_request
        os.environ.pop(P.ENV_KEY, None)
        if saved is not None:
            os.environ[P.ENV_KEY] = saved
        shutil.rmtree(tmp, ignore_errors=True)


def test_resolve_against_a_fixture():
    print("\n-- a full resolve run against a stubbed Google --")

    tmp = tempfile.mkdtemp()
    saved = os.environ.get(P.ENV_KEY)
    os.environ[P.ENV_KEY] = "test-key-not-real"
    real_request = P._request

    rows = [
        arcade(1, "GiGO Akihabara 3", 35.698300, 139.771000),
        arcade(2, "Ghost Arcade", 35.600000, 139.600000),
        arcade(3, "Centroid Palace", 31.230000, 121.470000,
               country="China", approx=True, approx_level="district"),
    ]
    fixtures = {
        "GiGO Akihabara 3": [place("gigo3", "GiGO Akihabara 3", "Tokyo",
                                   35.698310, 139.771020)],
        "Ghost Arcade": [],                       # no results at all
        "Centroid Palace": [place("far", "Centroid Palace", "Shanghai",
                                  31.240000, 121.480000)],
    }

    def fake_request(url, key, mask, body=None):
        q = (body or {}).get("textQuery", "")
        for name, res in fixtures.items():
            if q.startswith(name):
                return {"places": res}
        return {"places": []}

    P._request = fake_request
    try:
        with open(os.path.join(tmp, "arcades.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"arcades": rows}, fh)

        rc = P.main(["--out", tmp, "--limit", "10"])
        store = json.load(open(os.path.join(tmp, "place_ids.json"),
                               encoding="utf-8"))
        check("run exits 0", rc == 0, str(rc))
        check("the good match is stored with its place_id",
              store["places"].get("1", {}).get("place_id") == "gigo3")
        check("the good match is graded high",
              store["places"]["1"]["confidence"] == "high")
        check("a no-results arcade is recorded as an explicit MISS",
              store["misses"].get("2", {}).get("reason") == "no_results")
        check("an approx row is skipped by default (not even queried)",
              "3" not in store["places"] and "3" not in store["misses"])

        # A second run must not re-pay for what is already known.
        seen = []
        P._request = lambda url, key, mask, body=None: (
            seen.append(body) or fake_request(url, key, mask, body))
        P.main(["--out", tmp, "--limit", "10"])
        check("a re-run re-queries nothing already resolved or missed",
              seen == [], "%d call(s)" % len(seen))

        # Now allow approx rows: strict name gate, capped at medium.
        P._request = fake_request
        P.main(["--out", tmp, "--limit", "10", "--include-approx"])
        store = json.load(open(os.path.join(tmp, "place_ids.json"),
                               encoding="utf-8"))
        rec = store["places"].get("3")
        check("--include-approx resolves the centroid row", rec is not None)
        if rec:
            check("...but never above medium confidence",
                  rec["confidence"] == "medium", rec["confidence"])
            check("...and records that it came via an approx pin",
                  rec.get("via_approx") == "district", str(rec.get("via_approx")))
    finally:
        P._request = real_request
        os.environ.pop(P.ENV_KEY, None)
        if saved is not None:
            os.environ[P.ENV_KEY] = saved
        shutil.rmtree(tmp, ignore_errors=True)


def test_photo_filter_matches_the_frontend():
    """Every field js/panel.js imageRecords() reads must skip a Pro call.

    If this list is narrower than the frontend's, we pay $32/1k to resolve an
    arcade whose panel will never ask Google for a photo, because it already
    has one. That is real money for nothing.
    """
    print("\n-- the 'already photographed' filter mirrors panel.js --")

    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "enrichment.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"arcades": {
                "1": {"images": [{"url": "https://x/1.jpg"}]},
                "2": {"image_thumb": "https://x/2.jpg"},
                "3": {"image": "https://x/3.jpg"},
                "4": {"photo": "https://x/4.jpg"},
                "5": {"photo_url": "https://x/5.jpg"},
                "6": {"info_text": "no photo here"},
                "7": {"images": []},
            }}, fh)

        have = P.photo_ids_from_enrichment(path)
        for k in ("1", "2", "3", "4", "5"):
            check("id %s counts as photographed" % k, k in have)
        check("an entry with no photo is not counted", "6" not in have)
        check("an empty images[] is not counted", "7" not in have)

        # A photo on the ARCADE ROW counts too: panel.js checks it first.
        rows = [arcade(8, "Has row photo", 35.0, 139.0),
                arcade(9, "No photo", 35.0, 139.0)]
        rows[0]["image_thumb"] = "https://x/8.jpg"
        have = P.photo_ids_from_enrichment(path, rows)
        check("a photo on the arcade row counts", "8" in have)
        check("an arcade with no photo anywhere does not", "9" not in have)

        have = P.photo_ids_from_enrichment(os.path.join(tmp, "nope.json"))
        check("a missing enrichment file is not an error", have == set())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_refresh_survives_one_bad_id():
    """A single malformed stored place_id must not abort --refresh.

    Refresh is free and re-runnable, so one 400 aborting the batch would mean
    that row poisons every future run.
    """
    print("\n-- --refresh: one bad id does not poison the batch --")

    tmp = tempfile.mkdtemp()
    saved = os.environ.get(P.ENV_KEY)
    os.environ[P.ENV_KEY] = "test-key-not-real"
    real_request = P._request
    seen = []

    def fake_request(url, key, mask, body=None):
        seen.append(url)
        if "TRUNCATED" in url:
            raise P.ApiError("HTTP 400: INVALID_REQUEST", status=400)
        if "OBSOLETE" in url:
            return None                       # 404 -> NOT_FOUND
        return {"id": url.rsplit("/", 1)[-1].split("?")[0]}

    P._request = fake_request
    try:
        path = os.path.join(tmp, "place_ids.json")
        store = P.empty_store()
        for aid, pid in (("1", "ChIJgoodOne"), ("2", "TRUNCATED"),
                         ("3", "ChIJgoodTwo"), ("4", "OBSOLETE")):
            store["places"][aid] = {"place_id": pid, "name": "A" + aid,
                                    "resolved_at": "2020-01-01"}
        P.save_store(path, store)

        rc = P.main(["--out", tmp, "--refresh", "--all"])
        back = json.load(open(path, encoding="utf-8"))

        check("run exits 0", rc == 0, str(rc))
        check("all 4 ids were attempted, the 400 did not abort the batch",
              len(seen) == 4, "%d call(s)" % len(seen))
        check("the good ids survive",
              back["places"].get("1") and back["places"].get("3"))
        check("the malformed id is dropped and recorded",
              "2" not in back["places"]
              and back["misses"].get("2", {}).get("reason")
              == "place_id_invalid")
        check("the obsolete id is dropped and recorded",
              "4" not in back["places"]
              and back["misses"].get("4", {}).get("reason")
              == "place_id_obsolete")

        # A 403 IS a key problem and must still stop everything.
        seen[:] = []
        P._request = lambda *a, **k: (
            seen.append(1) or (_ for _ in ()).throw(
                P.ApiError("HTTP 403", status=403)))
        store = P.empty_store()
        for i in range(5):
            store["places"][str(i)] = {"place_id": "p%d" % i,
                                       "resolved_at": "2020-01-01"}
        P.save_store(path, store)
        P.main(["--out", tmp, "--refresh", "--all"])
        check("a 403 still stops the batch after the first call",
              len(seen) == 1, "%d call(s)" % len(seen))
    finally:
        P._request = real_request
        os.environ.pop(P.ENV_KEY, None)
        if saved is not None:
            os.environ[P.ENV_KEY] = saved
        shutil.rmtree(tmp, ignore_errors=True)


def test_search_body_shape():
    print("\n-- the Text Search request body matches Google's schema --")

    captured = {}

    def fake_request(url, key, mask, body=None):
        captured["url"] = url
        captured["mask"] = mask
        captured["body"] = body
        return {"places": []}

    real_request = P._request
    P._request = fake_request
    try:
        P.search_text("k", arcade(9, "GiGO", 35.7, 139.7, country="Japan",
                                  addr="1-1 Somewhere"))
        b = captured["body"]
        check("POSTs to places:searchText",
              captured["url"].endswith("places:searchText"), captured["url"])
        check("textQuery combines name and address",
              b["textQuery"] == "GiGO 1-1 Somewhere", b["textQuery"])
        check("locationBias is a circle at our coordinate",
              b["locationBias"]["circle"]["center"]["latitude"] == 35.7)
        check("regionCode is set from the country",
              b.get("regionCode") == "JP", str(b.get("regionCode")))
        check("field mask asks for exactly what verification needs",
              captured["mask"] == P.SEARCH_MASK, captured["mask"])
        check("field mask has no spaces (Google rejects them)",
              " " not in captured["mask"])
        check("field mask does NOT request photos (that would be an "
              "Enterprise SKU, and a photo name we may not store)",
              "photo" not in captured["mask"].lower())
    finally:
        P._request = real_request


def main():
    test_classify()
    test_score_name()
    test_brand_agrees()
    test_adversarial_pairs_end_to_end()
    test_best_candidate_picks_the_right_tenant()
    test_best_candidate_rejects_a_distant_chain_branch()
    test_best_candidate_rejects_a_near_but_unrelated_venue()
    test_best_candidate_empty_and_malformed()
    test_stale()
    test_store_roundtrip()
    test_no_key_is_a_silent_noop()
    test_all_requires_yes()
    test_resolve_against_a_fixture()
    test_photo_filter_matches_the_frontend()
    test_refresh_survives_one_bad_id()
    test_search_body_shape()

    print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
