"""Regression test for the same-name/same-street merge tier.

Reported by the verification fleet: "Circuit Social" shipped twice, once
at "258 Granby St" and once at "258 Granby Street". Same source, so the
cross-source tiers skip it; and the two pins are 753 km apart because
one row is badly geocoded, so every distance tier skips it too. The
printed address is the only usable evidence.

The narrowness matters. An earlier version compared only a prefix of the
address and merged four DIFFERENT Wanda Plazas in four different cities,
each of which prints "3rd Floor, Wanda Plaza".
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import merge as M          # noqa: E402


def test_abbreviated_street_types_normalize_together():
    for a, b in (("258 Granby St Norfolk Virginia",
                  "258 Granby Street Norfolk Virginia"),
                 ("5947 Clark Center Ave Sarasota",
                  "5947 Clark Center Avenue Sarasota"),
                 ("155 W Hampton Ave Mesa Arizona",
                  "155 West Hampton Avenue Mesa Arizona"),
                 ("6205 Merle Hay Rd Johnston Iowa",
                  "6205 Merle Hay Rd Suite 100 Johnston")):
        assert M.street_signature(a) == M.street_signature(b), \
            "%r and %r are the same address" % (a, b)


def test_different_streets_do_not_collide():
    # Same house number, different street.
    assert (M.street_signature("258 Granby St Norfolk")
            != M.street_signature("258 Colley Ave Norfolk"))


def test_floor_only_addresses_never_anchor_a_merge():
    # The failure an address-prefix rule produced: one chain's malls in
    # four different cities all print "3rd Floor, Wanda Plaza". None of
    # them states a house number, so none may qualify - a shared None
    # must NOT be treated as a shared signature by the caller either,
    # which is why the rule skips falsy signatures.
    for addr in ("3rd Floor, Wanda Plaza, Xihuan Road, Sanyuan",
                 "3rd Floor, Wanda Plaza, Yangling, Yulin",
                 "2nd floor, Wanda Plaza(Daming Palace)"):
        assert not M.street_signature(addr), \
            "%r has no house number and must not anchor a merge" % addr


def test_signature_needs_two_street_tokens():
    # A bare number with nothing after it identifies nothing.
    assert M.street_signature("258") is None
    assert M.street_signature("258 Granby") is None
    assert M.street_signature("") is None
    assert M.street_signature(None) is None


def test_house_number_is_required():
    # An address with no number cannot anchor this rule; the name tiers
    # handle those.
    assert M.street_signature("Granby Street Norfolk Virginia") is None


def test_suite_numbers_do_not_become_the_house_number():
    # "Suite 100" must be stripped BEFORE the first-number scan, or the
    # suite becomes the anchor and two unrelated venues in one building
    # collide.
    sig = M.street_signature("6205 Merle Hay Rd Suite 100 Johnston Iowa")
    assert sig is not None and sig[0] == "6205"
