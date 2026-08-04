"""Regression test for share-link identity.

Reported bug: a saved link to a Hong Kong arcade
(#arcade=6072) opened an Indonesian venue in Bandung, quoting rupiah.

Cause: `id` is a ROW NUMBER. merge sorts by (country, name, addr) and
assigns 1..N on every build, so one venue appearing, merging or being
relabelled shifts every id after it. Measured across two consecutive
builds of this repo, 589 row numbers came to point at a different venue.
Any URL, bookmark or shared message carrying an id therefore rots.

`sid` is derived from the venue's own source page url instead, and was
measured stable for 11,370 of 11,370 venues present in both builds.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import merge as M          # noqa: E402


def test_ziv_url_gives_a_stable_sid():
    a = {"name": "Game Zone", "country": "Hong Kong", "addr": "x",
         "links": {"ziv": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=4627"}}
    assert M.stable_sid(a) == "z4627"
    # The row number, the name and the address are all allowed to change
    # without changing identity - that is the entire point.
    b = dict(a, name="GAME ZONE (Mong Kok)", addr="somewhere else")
    assert M.stable_sid(b) == M.stable_sid(a)


def test_bemanicn_url_gives_a_stable_sid():
    a = {"name": "x", "country": "China", "addr": "y",
         "links": {"bemanicn": "https://map.bemanicn.com/s/2744"}}
    assert M.stable_sid(a) == "b2744"


def test_ziv_wins_over_bemanicn_so_one_venue_has_one_sid():
    # A venue listed by both sources must not get two identities
    # depending on which link happened to be written first.
    a = {"name": "x", "country": "China", "addr": "y",
         "links": {"ziv": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=11",
                   "bemanicn": "https://map.bemanicn.com/s/22"}}
    b = {"name": "x", "country": "China", "addr": "y",
         "links": {"bemanicn": "https://map.bemanicn.com/s/22",
                   "ziv": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=11"}}
    assert M.stable_sid(a) == M.stable_sid(b) == "z11"


def test_a_sourceless_venue_still_gets_a_deterministic_sid():
    a = {"name": "Some Arcade", "country": "Japan", "addr": "1 Main St",
         "links": {}}
    first = M.stable_sid(a)
    assert first.startswith("h") and len(first) > 3
    assert M.stable_sid(dict(a)) == first
    # Case and surrounding whitespace are not identity.
    assert M.stable_sid({"name": "  SOME ARCADE ", "country": "Japan",
                         "addr": "1 Main St ", "links": {}}) == first


def test_different_venues_get_different_sids():
    a = {"name": "A", "country": "Japan", "addr": "1 Main St", "links": {}}
    b = {"name": "B", "country": "Japan", "addr": "1 Main St", "links": {}}
    c = {"name": "A", "country": "Japan", "addr": "2 Main St", "links": {}}
    d = {"name": "A", "country": "Taiwan", "addr": "1 Main St", "links": {}}
    assert len({M.stable_sid(x) for x in (a, b, c, d)}) == 4


def test_sid_never_looks_like_a_row_number():
    # panel.js refuses a bare numeric hash key on purpose, so that an old
    # #arcade=<id> link opens nothing rather than the wrong venue. A sid
    # that was all digits would defeat that guard.
    for a in ({"name": "x", "country": "c", "addr": "a", "links": {}},
              {"name": "x", "country": "c", "addr": "a",
               "links": {"ziv": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=7"}},
              {"name": "x", "country": "c", "addr": "a",
               "links": {"bemanicn": "https://map.bemanicn.com/s/7"}}):
        assert not M.stable_sid(a).isdigit()


def test_every_shipped_arcade_has_a_unique_sid():
    import json
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "arcades.json")
    if not os.path.exists(path):
        return                      # fresh clone, nothing built yet
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)["arcades"]
    sids = [r.get("sid") for r in rows]
    assert all(sids), "some arcades shipped without a sid"
    assert len(set(sids)) == len(sids), "sid collision: a share link is ambiguous"
