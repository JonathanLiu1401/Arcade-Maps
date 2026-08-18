"""keep_games vs inverted remove_games (2026-08-18 weekly killer)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge  # noqa: E402


class TestApplyAttestedGameEdits(unittest.TestCase):
    def test_mlab_inverted_remove_would_empty_now_keeps(self):
        # After the fleet apply stored the KEEP list as remove_games,
        # a clean BemaniCN scrape of M.Lab is only chunithm+maimai_dx.
        arcade = {"name": "M.Lab", "games": ["chunithm", "maimai_dx"]}
        rec = {"remove_games": ["chunithm", "maimai_dx"]}
        games, drop = merge.apply_attested_game_edits(arcade, rec)
        self.assertTrue(drop)
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


if __name__ == "__main__":
    unittest.main()
