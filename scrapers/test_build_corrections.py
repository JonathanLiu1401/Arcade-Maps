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
    # cab_models is {slug: int|None} with a hard assert downstream, and
    # the fleet writes prose into it ("DX PRiSM PLUS (x3)").
    for field, proposed in (("cab_models", {"maimai_dx": "DX PRiSM (x3)"}),
                            ("prices", "Admission $12 all-day"),
                            ("status", {"action": "merge_into"})):
        out, stats = _one(str(tmp_path), {
            "field": field, "name": "Test Arcade",
            "current": {"name": "Test Arcade", "addr": "1 Main St"},
            "proposed": proposed, "confidence": "certain",
            "evidence_url": "https://x", "evidence_quote": "q",
        })
        assert not out, "%s was applied without a translation step" % field


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


def test_unknown_game_slugs_are_dropped(tmp_path):
    out, stats = _one(str(tmp_path), {
        "field": "games", "name": "Test Arcade",
        "current": {"name": "Test Arcade", "addr": "1 Main St"},
        "proposed": ["not_a_real_game"], "confidence": "certain",
        "evidence_url": "https://x", "evidence_quote": "q",
    })
    assert not out and stats["bad_slug"] == 1
