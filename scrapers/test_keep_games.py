"""keep_games vs inverted remove_games (2026-08-18 weekly killer)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge  # noqa: E402


class TestApplyAttestedGameEdits(unittest.TestCase):
    def test_remove_all_does_not_drop_the_pin(self):
        arcade = {"name": "M.Lab", "games": ["chunithm", "maimai_dx"]}
        rec = {"remove_games": ["chunithm", "maimai_dx"]}
        games, drop = merge.apply_attested_game_edits(arcade, rec)
        self.assertFalse(drop)
        self.assertIsNone(games)

    def test_keep_games_no_overlap_does_not_drop(self):
        arcade = {"name": "Wonderpark", "games": ["other", "taiko"]}
        rec = {"keep_games": ["maimai_dx"]}
        games, drop = merge.apply_attested_game_edits(arcade, rec)
        self.assertFalse(drop)
        self.assertIsNone(games)

    def test_keep_games_preserves_official_list(self):
        arcade = {"name": "M.Lab", "games": ["chunithm", "maimai_dx"]}
        rec = {"keep_games": ["chunithm", "maimai_dx"]}
        games, drop = merge.apply_attested_game_edits(arcade, rec)
        self.assertFalse(drop)
        self.assertIsNone(games)  # no change

    def test_keep_games_strips_overlisted_extras(self):
        arcade = {
            "name": "M.Lab",
            "games": ["chunithm", "maimai_dx", "iidx", "sdvx", "project_diva"],
        }
        rec = {"keep_games": ["chunithm", "maimai_dx"]}
        games, drop = merge.apply_attested_game_edits(arcade, rec)
        self.assertFalse(drop)
        self.assertEqual(games, ["chunithm", "maimai_dx"])

    def test_real_remove_games_still_drops_one_title(self):
        arcade = {"name": "GiGO", "games": ["taiko", "ongeki"]}
        rec = {"remove_games": ["ongeki"]}
        games, drop = merge.apply_attested_game_edits(arcade, rec)
        self.assertFalse(drop)
        self.assertEqual(games, ["taiko"])

    def test_add_games(self):
        arcade = {"name": "x", "games": ["maimai_dx"]}
        rec = {"add_games": ["ongeki"]}
        games, drop = merge.apply_attested_game_edits(arcade, rec)
        self.assertFalse(drop)
        self.assertEqual(games, ["maimai_dx", "ongeki"])


class TestPruneFieldsToGames(unittest.TestCase):
    def test_azisai_ddr_gold_stripped_with_ddr(self):
        # 2026-08-18 second weekly death: keep_games dropped ddr but
        # left cab_models.ddr_gold = 1 with no count_evidence.
        a = {
            "name": "和音屋 x -Azisai- 北京店 立直麻将/音游",
            "games": ["chunithm", "maimai_dx", "sdvx"],
            "game_counts": {"chunithm": 2, "ddr": 1},
            "count_evidence": {"chunithm": "bemanicn_qty", "ddr": "ziv_comment"},
            "cab_models": {"ddr_gold": 1, "sdvx_vm": None},
            "cabs": ["ddr_gold", "sdvx_vm"],
            "counts_src": "ziv",
        }
        merge.prune_fields_to_games(a)
        self.assertEqual(a["games"], ["chunithm", "maimai_dx", "sdvx"])
        self.assertNotIn("ddr", a.get("game_counts", {}))
        self.assertNotIn("ddr_gold", a.get("cab_models", {}))
        self.assertNotIn("ddr_gold", a.get("cabs", []))
        self.assertIn("sdvx_vm", a.get("cab_models", {}))
        self.assertIsNone(a["cab_models"]["sdvx_vm"])


class TestSharedListUrlMustNotKeyAttested(unittest.TestCase):
    def test_otogesetchi_wiki_page_is_not_a_venue_key(self):
        import build_corrections
        url = "https://w.atwiki.jp/otogesetchi/pages/19.html"
        self.assertTrue(build_corrections.is_shared_list_url(url))
        arcade = {
            "name": "新宿スポーツランド本館",
            "addr": "東京都新宿区新宿3-22-12",
            "country": "Japan",
            "links": {"otogesetchi": url,
                      "ziv": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=5168"},
        }
        keys = build_corrections.venue_keys(arcade)
        self.assertFalse(any(k.startswith("otogesetchi|") for k in keys))
        self.assertTrue(any(k.startswith("ziv|") for k in keys))
        table = {
            "otogesetchi|" + url: {
                "name": "ホテルバリアンリゾート新宿本店",
                "exclude": True,
            }
        }
        self.assertIsNone(build_corrections.lookup(table, arcade))


if __name__ == "__main__":
    unittest.main()
