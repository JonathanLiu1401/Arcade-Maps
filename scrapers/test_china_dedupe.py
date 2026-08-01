"""Regression test for the China co-located dedupe rule.

Reported bug: every Chinese city showed the same arcade two or three
times, once per source. The two existing merge rules could not reach
these - the proximity tier gates at 30 m (the median real duplicate is
31 m apart, because the sources pin different doors of one mall) and it
only considers official-vs-community pairs, while China's duplicates are
overwhelmingly bemanicn x wahlap, both community.

Every pair below was checked by hand against BOTH addresses. They are
kept as a test rather than a threshold because the discriminator is
non-obvious: name similarity ranks these backwards, scoring sibling
branches higher than true duplicates.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import merge as M          # noqa: E402


def decide(a_name, b_name, dist_m):
    """The rule as the pipeline applies it: name evidence, then the
    distance gate that the weakest evidence tier depends on."""
    ok, why = M.cn_same_venue_evidence(a_name, b_name)
    if not ok:
        return False, why
    if dist_m > M.CN_MAX_M:
        return False, "too_far"
    if why != "landmark_agree" and dist_m > M.CN_BRAND_ONLY_M:
        return False, "brand_only_too_far"
    return True, why


# (a_name, b_name, metres apart, why) - must judge these the SAME venue.
SAME_VENUE = [
    ("汤姆熊天津和平路天河城店", "汤姆熊天津天河城店", 64,
     "both 天河城 5F shop 501"),
    ("乐玩客潮玩城 Fun Guest (沙坪坝店)", "乐玩客潮玩城(沙坪坝店)", 134,
     "same shop, one row romanized"),
    ("星际梦想城 辛集店", "星际梦想城辛集万达广场店", 0,
     "one row omits the mall name"),
    ("玩里挑一漳浦店", "玩里挑一漳浦绥安店", 0,
     "identical street address, one row adds the subdistrict"),
    ("酷玩时代兰州城关店", "酷玩时代电玩城", 44,
     "one row is the bare chain name; only adjacency supports it"),
    ("星际小镇新乡原阳县香港城店", "星际小镇河南原阳店", 0,
     "one row names 香港城, the other only the county"),
    ("1号机长超乐场芜湖inPARK店", "1号机长（芜湖镜湖inPARK店）", 87,
     "branch text lives in the parenthetical on one side"),
    ("宝贝王石家庄西桥禧欢里店", "宝贝王（禧欢里店）", 0,
     "addresses DISAGREE on the building; names agree - names win"),
    ("51区超级乐园天津红桥水游城店", "51区超级乐园水游城店", 86,
     "both 红桥区水游城 A座 2F"),
    ("11Lab超乐场天津SM广场店", "11Lab超乐场天津东丽店", 64,
     "both 环河北路168号 SM城市广场 1F"),
]

# The rule must keep these apart. Note how similar several of them are:
# this is why a similarity threshold cannot do this job.
DIFFERENT_VENUES = [
    ("汤姆熊天津和平路天河城店", "汤姆熊天津恒隆广场店", 412,
     "天河城 vs 恒隆广场, two malls"),
    ("爱玩嘉年华江北观音桥一店", "爱玩嘉年华重庆江北二店", 209,
     "branch 1 vs branch 2 - scores 0.95 similar"),
    ("大玩家哈尔滨南岗万达店", "大玩家哈尔滨南岗西城红场店", 484,
     "same district, two malls"),
    ("拾光派对沈阳大东区大悦城店", "拾光派对沈阳大东吾悦店", 106,
     "大悦城 vs 吾悦广场"),
    ("晴空超乐场 南风里A店", "晴空超乐场 南风里B店", 104,
     "A wing vs B wing of one complex, 104 m apart"),
    ("乐玩客潮玩城(沙坪坝店)", "乐玩客重庆金沙天街店", 428,
     "三峡广场 vs 金沙天街"),
    ("星际传奇京基KKmall店", "星际玩家海口龙华海口天街店", 482660,
     "different chains entirely"),
    # Both of these sat 33 m and 195 m apart before the fix - close
    # enough that a distance rule alone would have fused them.
    ("万达宝贝王 Wanda Kids (上海浦江万达店)", "啵比特 BOBITE（上海浦江万达店）", 33,
     "two different operators inside one mall"),
    ("城市英雄 Party House (南昌大悦城)", "纯玩世界 JOYONE (南昌大悦城)", 195,
     "two different operators inside one mall"),
    ("星辉之城荆州购物公园店", "星辉之城（洪湖购物公园店）", 60,
     "same mall brand in two CITIES; 60 m apart only via a bad geocode"),
]


def test_same_venue_pairs_are_compatible():
    bad = []
    for a, b, dist, why in SAME_VENUE:
        ok, reason = decide(a, b, dist)
        if not ok:
            bad.append("%s || %s  (%s) -> rejected as %s" % (a, b, why, reason))
    assert not bad, "rule rejects known duplicates:\n  " + "\n  ".join(bad)


def test_different_venues_are_rejected():
    bad = []
    for a, b, dist, why in DIFFERENT_VENUES:
        ok, reason = decide(a, b, dist)
        if ok:
            bad.append("%s || %s  (%s) -> accepted as %s" % (a, b, why, reason))
    assert not bad, "rule merges distinct venues:\n  " + "\n  ".join(bad)


def test_branch_markers_parse_both_scripts():
    # 一店 and 1店 must read as the same marker, or the Chinese-numeral
    # form silently stops rejecting.
    assert M.cn_branch_markers("爱玩嘉年华江北一店") == {"1"}
    assert M.cn_branch_markers("爱玩嘉年华江北1店") == {"1"}
    assert M.cn_branch_markers("晴空超乐场 南风里A店") == {"A"}
    assert M.cn_branch_markers("酷玩时代兰州城关店") == set()


def test_brand_prefix_floor_blocks_unrelated_chains():
    # Two chains sharing a 2-char prefix must not qualify.
    ok, reason = M.cn_same_venue_evidence("星际传奇京基KKmall店",
                                          "星际玩家海口龙华海口天街店")
    assert not ok and reason == "brand_differs"


def _cn(name, lat, lng, **kw):
    e = {"name": name, "addr": kw.pop("addr", ""), "lat": lat, "lng": lng,
         "country": "China", "pref": "", "games": kw.pop("games", ["other"]),
         "cabs": [], "src": kw.pop("src", ["bemanicn"]),
         "links": kw.pop("links", {}), "notes": ""}
    e.update(kw)
    return e


def test_merge_unions_and_never_loses_a_source_link():
    # The real hazard of any dedupe here: dropping a row takes its
    # links.ziv with it, and photos join on that URL, so the surviving
    # venue silently loses its pictures.
    a = _cn("汤姆熊天津和平路天河城店", 39.1300, 117.2000,
            src=["wahlap"], games=["maimai_dx"],
            links={"ziv": None, "bemanicn": "b/1"})
    b = _cn("汤姆熊天津天河城店", 39.1305, 117.2001,
            src=["ziv"], games=["chunithm"],
            links={"ziv": "z/9", "bemanicn": None})
    log = []
    out = M.dedupe_china_colocated([a, b], log)
    assert len(out) == 1, "the two pins should have become one"
    kept = out[0]
    assert kept["links"]["ziv"] == "z/9", "ziv link was dropped"
    assert kept["links"]["bemanicn"] == "b/1", "bemanicn link was dropped"
    assert set(kept["src"]) == {"wahlap", "ziv"}
    assert set(kept["games"]) == {"maimai_dx", "chunithm"}
    assert log and log[0]["rule"] == "china_colocated"


def test_same_source_merge_keeps_the_loser_page_url():
    # links holds one url per source, so merging two ziv rows would drop
    # the loser's page - and photos join on exactly that url. Measured:
    # 16 China photos were orphaned this way before links.also existed.
    a = _cn("星际玩家（海口龙湖天街店）", 20.0300, 110.3300, src=["ziv"],
            links={"ziv": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=10222",
                   "gmaps": "https://maps.google.com/?q=a"})
    b = _cn("星际玩家潮玩（海口龙湖天街店）", 20.0301, 110.3301, src=["ziv"],
            links={"ziv": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=10223",
                   "gmaps": "https://maps.google.com/?q=b"})
    out = M.dedupe_china_colocated([a, b], [])
    assert len(out) == 1
    # Whichever row survived, BOTH ziv page urls must still be reachable
    # - links.ziv for the survivor's own, links.also for the other's.
    also = out[0]["links"].get("also") or []
    reachable = set(also) | {out[0]["links"].get("ziv")}
    for want in ("id=10222", "id=10223"):
        assert any(u and want in u for u in reachable), \
            "ziv page url %s was lost; its photos are orphaned" % want
    # A generated gmaps search url is not a source page and must not
    # crowd the real ones out.
    assert not any("maps.google" in u for u in also), \
        "gmaps search url leaked into links.also"


def test_merge_keeps_the_better_evidenced_count():
    a = _cn("酷玩时代兰州城关店", 36.0600, 103.8300, games=["maimai_dx"],
            game_counts={"maimai_dx": 1},
            count_evidence={"maimai_dx": "ziv_listed"}, counts_src="ziv")
    b = _cn("酷玩时代电玩城", 36.0600, 103.8302, games=["maimai_dx"],
            game_counts={"maimai_dx": 6},
            count_evidence={"maimai_dx": "bemanicn_qty"},
            counts_src="bemanicn")
    out = M.dedupe_china_colocated([a, b], [])
    assert len(out) == 1
    assert out[0]["game_counts"]["maimai_dx"] == 6, \
        "a ziv_listed placeholder outranked a published quantity"
    assert out[0]["count_evidence"]["maimai_dx"] == "bemanicn_qty"


def test_merge_prefers_a_real_pin_over_an_approximate_one():
    a = _cn("玩里挑一漳浦店", 24.1170, 117.6130, approx=True,
            approx_level="district")
    b = _cn("玩里挑一漳浦绥安店", 24.1171, 117.6131, src=["wahlap"])
    out = M.dedupe_china_colocated([a, b], [])
    assert len(out) == 1
    assert not out[0].get("approx"), \
        "kept the approximate coordinate when a real one was available"


def test_distinct_venues_survive_the_pass():
    a = _cn("拾光派对沈阳大东区大悦城店", 41.8000, 123.4300)
    b = _cn("拾光派对沈阳大东吾悦店", 41.8009, 123.4301)   # ~100 m
    out = M.dedupe_china_colocated([a, b], [])
    assert len(out) == 2, "merged two different malls"


def test_three_sources_collapse_to_one_pin():
    rows = [_cn("11Lab超乐场天津SM广场店", 39.0870, 117.3120, src=["wahlap"]),
            _cn("11Lab超乐场天津东丽店", 39.0871, 117.3121, src=["bemanicn"]),
            _cn("11Lab超乐场天津东丽SM城市广场店", 39.0872, 117.3122,
                src=["ziv"])]
    out = M.dedupe_china_colocated(rows, [])
    assert len(out) == 1, "a 3-source venue should end as ONE pin"
    assert set(out[0]["src"]) == {"wahlap", "bemanicn", "ziv"}


def test_non_china_rows_are_untouched():
    jp = [{"name": "GiGO A", "addr": "", "lat": 35.7, "lng": 139.7,
           "country": "Japan", "pref": "Tokyo", "games": ["maimai_dx"],
           "cabs": [], "src": ["allnet"], "links": {}, "notes": ""},
          {"name": "GiGO A", "addr": "", "lat": 35.7, "lng": 139.7,
           "country": "Japan", "pref": "Tokyo", "games": ["maimai_dx"],
           "cabs": [], "src": ["eagate"], "links": {}, "notes": ""}]
    assert len(M.dedupe_china_colocated(jp, [])) == 2


def test_addresses_never_reject():
    # cn_same_venue_evidence reads names only. The 宝贝王 pair has
    # contradictory addresses and must still merge; if this signature
    # ever grows address arguments again, that regression comes back.
    ok, _ = M.cn_same_venue_evidence("宝贝王石家庄西桥禧欢里店",
                                     "宝贝王（禧欢里店）")
    assert ok
