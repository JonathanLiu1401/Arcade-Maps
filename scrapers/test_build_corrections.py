"""Tests for the verification-fleet correction filter.

The filter exists because a confident proposal is not the same as a true
one. Two of its rules carry most of the risk and are pinned here.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_corrections as BC      # noqa: E402


ARCADE = {
    "id": 1, "name": "Test Arcade", "addr": "1 Main St", "country": "Japan",
    "games": ["maimai_dx"], "links": {"ziv": "https://ziv/1"},
}


def _shard(tmp, corrections):
    import json
    d = os.path.join(tmp, "verify", "corrections")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "shard_000.json"), "w", encoding="utf-8") as fh:
        json.dump({"shard": 0, "checked": 1, "corrections": corrections}, fh)
    return tmp


def _one(tmp, corr, arcade=None):
    _shard(tmp, [corr])
    out, stats = BC.build(tmp, [arcade or ARCADE], {"maimai_dx", "chunithm"})
    return out, stats


def test_a_count_without_a_quoted_quantity_is_rejected(tmp_path):
    # This is the "x1 everywhere" bug: the agent counts ROWS on a ZIv
    # page and reports 1 per row. Nobody stated a quantity, so nothing
    # may be published as one.
    out, stats = _one(str(tmp_path), {
        "field": "game_counts", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": {"maimai_dx": 1},
        "confidence": "certain",
        "evidence_url": "https://ziv/1",
        "evidence_quote": "Separate ZIv rows: maimai DX; CHUNITHM",
    })
    assert not out, "row-counting was published as a real count"
    assert stats["counts_without_quantity"] == 1


def test_a_count_with_a_quoted_quantity_is_accepted(tmp_path):
    for quote in ("CHUNITHM - 4 cabinets",
                  "maimai DX (x4)",
                  "4 machines on the 3rd floor",
                  "maimai DX 4台"):
        out, _ = _one(str(tmp_path), {
            "field": "game_counts", "name": "Test Arcade",
            "current": {"name": "Test Arcade", "addr": "1 Main St"},
            "proposed": {"maimai_dx": 4},
            "confidence": "certain",
            "evidence_url": "https://ziv/1",
            "evidence_quote": quote,
        })
        assert out, "a stated quantity was rejected: %r" % quote


def test_free_text_fields_are_held(tmp_path):
    # prices is a measured per-country table built by prices.py, and
    # status collects merge proposals as well as closures. Neither can be
    # applied verbatim.
    for field, proposed in (("prices", "Admission $12 all-day"),
                            ("status", {"action": "merge_into"})):
        out, stats = _one(str(tmp_path), {
            "field": field, "name": "Test Arcade",
            "current": {"name": "Test Arcade", "addr": "1 Main St"},
            "proposed": proposed, "confidence": "certain",
            "evidence_url": "https://x", "evidence_quote": "q",
        })
        assert not out, "%s was applied without a translation step" % field


def test_cab_models_prose_is_translated_to_schema_slugs(tmp_path):
    # The fleet writes prose under a GAME key ("iidx": "Lightning
    # Model...") where cab_models wants {"iidx_lm": count|None}. Only 29
    # of 256 proposals used the slugs, so without translation the whole
    # field - the cabinet distinctions the owner asked for - is lost.
    arcade = dict(ARCADE, games=["iidx"])
    out, _ = _one(str(tmp_path), {
        "field": "cab_models", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": {"iidx": "Lightning Model x2"},
        "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    }, arcade)
    assert out, "cab_models prose was not translated"
    val = out[BC.venue_key(arcade)]["fields"]["cab_models"]["value"]
    assert val == {"iidx_lm": 2}


def test_a_cab_model_that_cannot_be_resolved_is_dropped(tmp_path):
    # A wrong cabinet badge is worse than a missing one: a veteran
    # travels for a specific cabinet.
    arcade = dict(ARCADE, games=["ddr"])
    out, stats = _one(str(tmp_path), {
        "field": "cab_models", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": {"ddr": "A3 X-cab online + A20 offline"},
        "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    }, arcade)
    assert not out and stats["cab_untranslatable"] == 1


def test_a_game_version_number_is_not_a_cabinet_count(tmp_path):
    # "Lightning Model (IIDX 33 Sparkle Shower)" was read as 33 cabinets.
    arcade = dict(ARCADE, games=["iidx"])
    out, _ = _one(str(tmp_path), {
        "field": "cab_models", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": {"iidx": "Lightning Model (IIDX 33 Sparkle Shower)"},
        "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    }, arcade)
    val = out[BC.venue_key(arcade)]["fields"]["cab_models"]["value"]
    assert val == {"iidx_lm": None}, \
        "a game version number was published as a cabinet count"


def test_a_cab_model_for_a_game_the_venue_lacks_is_dropped(tmp_path):
    arcade = dict(ARCADE, games=["maimai_dx"])
    out, stats = _one(str(tmp_path), {
        "field": "cab_models", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": {"iidx": "Lightning Model"}, "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    }, arcade)
    assert not out and stats["cab_untranslatable"] == 1


def test_lookup_matches_any_of_a_venues_source_urls(tmp_path):
    # A merged venue answers to a url per source; venue_key returns only
    # the first. A file keyed on the OTHER one silently no-ops.
    a = dict(ARCADE, links={"ziv": "https://ziv/1",
                            "bemanicn": "https://map.bemanicn.com/s/2744"})
    table = {"bemanicn|https://map.bemanicn.com/s/2744": {"hit": True}}
    assert BC.lookup(table, a) == {"hit": True}
    assert BC.lookup({"nope": 1}, a) is None


def test_unverified_confidence_never_applies(tmp_path):
    out, stats = _one(str(tmp_path), {
        "field": "website", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": "https://example.com", "confidence": "unverified",
        "evidence_url": "https://x", "evidence_quote": "q",
    })
    assert not out and stats["unverified"] == 1


def test_a_correction_with_no_evidence_url_never_applies(tmp_path):
    out, stats = _one(str(tmp_path), {
        "field": "website", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": "https://example.com", "confidence": "certain",
        "evidence_quote": "trust me",
    })
    assert not out and stats["unverified"] == 1


def test_an_ambiguous_name_is_refused_not_guessed(tmp_path):
    # Two venues share a name and the correction gives an address that
    # matches neither. Writing to either one is a coin flip.
    twins = [dict(ARCADE, id=1, addr="1 Main St",
                  links={"ziv": "https://ziv/1"}),
             dict(ARCADE, id=2, addr="2 Other Rd",
                  links={"ziv": "https://ziv/2"})]
    _shard(str(tmp_path), [{
        "field": "website", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "9 Nowhere Ln"},
        "proposed": "https://example.com", "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    }])
    out, stats = BC.build(str(tmp_path), twins, {"maimai_dx"})
    assert not out and stats["unresolved"] == 1


def test_venue_key_prefers_the_source_page_over_the_address(tmp_path):
    # The key must not be the field a correction changes, or the overlay
    # stops matching itself after the first rebuild.
    before = BC.venue_key(dict(ARCADE, addr="1 Main St"))
    after = BC.venue_key(dict(ARCADE, addr="1 Main Street, Suite 4"))
    assert before == after == "ziv|https://ziv/1"


def test_a_proposal_matching_current_data_is_still_kept(tmp_path):
    # build() reads arcades.json, which is the ALREADY-CORRECTED output
    # of the previous build. "already right" therefore usually means
    # "the overlay put it there", so skipping those shrank the overlay
    # on every rebuild until the corrections silently reverted.
    out, stats = _one(str(tmp_path), {
        "field": "games", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": ["maimai_dx"], "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    })
    assert out, "a correction was dropped because it already applied"
    assert stats["no_change"] == 0


CN = {"id": 9, "name": "Test 电玩城", "addr": "北京市海淀区万柳",
      "country": "China", "games": ["maimai_dx"], "lat": 39.90, "lng": 116.40,
      "links": {"ziv": "https://ziv/9"}}
# (name, lat, lng, depth) - 海淀区 Haidian, Beijing.
PLACES = [("海淀区", 39.9593, 116.2979, 2), ("北京市", 39.9028, 116.4011, 1)]


def _loc(tmp, proposed, arcade=None, places=PLACES):
    import merge as merge_mod
    _shard(tmp, [{
        "field": "location", "name": (arcade or CN)["name"],
        "current": {"name": (arcade or CN)["name"],
                    "addr": (arcade or CN)["addr"]},
        "proposed": proposed, "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    }])
    return BC.build(tmp, [arcade or CN], {"maimai_dx"},
                    places=places, merge_mod=merge_mod)


def test_a_coordinate_in_the_wrong_country_is_refused(tmp_path):
    # Measured: three "certain" proposals moved a pin across a border.
    out, stats = _loc(str(tmp_path), {"lat": 35.68, "lng": 139.76})  # Tokyo
    assert not out and stats["location_wrong_country"] == 1


def test_a_coordinate_moving_away_from_its_own_district_is_refused(tmp_path):
    # The arcade's address says 海淀区; this lands further from it than
    # the current pin, so the proposal is the wrong one, not the data.
    out, stats = _loc(str(tmp_path), {"lat": 39.80, "lng": 116.70})
    assert not out and stats["location_no_geographic_gain"] == 1


def test_a_coordinate_moving_into_its_own_district_is_accepted(tmp_path):
    out, stats = _loc(str(tmp_path), {"lat": 39.9590, "lng": 116.2980})
    assert out, "a coordinate landing in the named district was refused"
    key = BC.venue_key(CN)
    assert out[key]["fields"]["location"]["value"]["lat"] == 39.9590


def test_a_coordinate_fills_a_gap_when_the_arcade_has_no_pin(tmp_path):
    blank = dict(CN, lat=None, lng=None)
    out, _ = _loc(str(tmp_path), {"lat": 39.9590, "lng": 116.2980}, blank)
    assert out, "an arcade with no pin at all should take a plausible one"


def test_a_nonnumeric_location_proposal_is_refused(tmp_path):
    # The fleet frequently proposes prose here ("re-geocode; pin
    # currently identical to ...").
    out, stats = _loc(str(tmp_path), {"note": "re-geocode this one"})
    assert not out and stats["location_not_numeric"] == 1


def _status(tmp, proposed, note="", conf="certain",
            url="https://news.example.com/story"):
    import merge as merge_mod
    _shard(tmp, [{
        "field": "status", "name": ARCADE["name"],
        "current": {"name": ARCADE["name"], "addr": ARCADE["addr"]},
        "proposed": proposed, "note": note, "confidence": conf,
        "evidence_url": url, "evidence_quote": "q",
    }])
    return BC.build(tmp, [ARCADE], {"maimai_dx"}, merge_mod=merge_mod)


def test_a_plain_permanent_closure_is_accepted(tmp_path):
    out, _ = _status(str(tmp_path), "permanently closed (last day 2025-09-28)")
    assert out, "a sourced permanent closure was refused"
    assert out[BC.venue_key(ARCADE)]["fields"]["status"]["value"]["closed"]


def test_a_temporary_closure_is_not_a_closure(tmp_path):
    # "closed for renovation, reopening October" is a venue that still
    # exists. Marking it permanently closed is its own kind of wrong.
    for text in ("closed for renovation, reopening 2026-10-01",
                 "closed temporarily while the mall is refurbished",
                 "店铺搬迁至高新三期玫瑰ONE，装修中",
                 "open but network offline (已断网)"):
        out, stats = _status(str(tmp_path), text)
        assert not out, "treated a temporary state as permanent: %r" % text


def test_a_merge_proposal_is_not_a_closure(tmp_path):
    # The fleet writes merge_into proposals into this same field.
    out, _ = _status(str(tmp_path),
                     {"action": "merge_into", "target_id": 12062,
                      "reason": "duplicate; the other row is no longer needed"})
    assert not out


def test_a_closure_needs_certainty(tmp_path):
    out, stats = _status(str(tmp_path), "permanently closed", conf="likely")
    assert not out and stats["status_not_certain"] == 1


def test_a_closure_sourced_to_the_community_listing_is_refused(tmp_path):
    # The row already came from these sites. Citing them back is not
    # corroboration, and removing a venue is not reversible for a user
    # who trusted the map and stayed home.
    for url in ("https://map.bemanicn.com/s/4035",
                "https://zenius-i-vanisher.com/v5.2/arcade.php?id=1"):
        out, stats = _status(str(tmp_path), "permanently closed", url=url)
        assert not out, "accepted a closure sourced to %s" % url


def test_vague_status_text_is_not_a_closure(tmp_path):
    for text in ("possibly gone?", "could not verify", "status unclear",
                 "unverified / possibly delisted"):
        out, _ = _status(str(tmp_path), text)
        assert not out, "read %r as a permanent closure" % text


def test_unknown_game_slugs_are_dropped(tmp_path):
    out, stats = _one(str(tmp_path), {
        "field": "games", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": ["not_a_real_game"], "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    })
    assert not out and stats["bad_slug"] == 1
