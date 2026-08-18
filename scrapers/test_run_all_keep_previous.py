"""Keep last week's raw file when a source FetchErrors after retries.

The 2026-08-17 weekly Action finished ALL.Net, then died on the first
eagate URL (HTTP 503 x3) and committed nothing. Empty parses must still
abort (that is a markup change). A down host must not.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common  # noqa: E402
import eagate  # noqa: E402
import run_all  # noqa: E402


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


class TestKeepPreviousOnFetchError(unittest.TestCase):
    def test_eagate_fetcherror_keeps_file(self):
        first = sorted(eagate.GKEYS)[0]
        slug = eagate.GKEYS[first]
        with tempfile.TemporaryDirectory() as tmp:
            prev = [{"name": "kept-store"}]
            _write_json(os.path.join(tmp, slug + ".json"), prev)

            def boom(gkey, **kw):
                raise common.FetchError("HTTP Error 503: 503")

            with mock.patch.object(eagate, "scrape_game", side_effect=boom):
                run_all.scrape_all(tmp, only={"eagate"})
            kept = json.load(open(os.path.join(tmp, slug + ".json"),
                                  encoding="utf-8"))
            self.assertEqual(kept, prev)

    def test_eagate_fetcherror_without_previous_dies(self):
        def boom(gkey, **kw):
            raise common.FetchError("HTTP Error 503: 503")

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(eagate, "scrape_game", side_effect=boom):
                with self.assertRaises(SystemExit):
                    run_all.scrape_all(tmp, only={"eagate"})

    def test_eagate_empty_rows_still_dies(self):
        first = sorted(eagate.GKEYS)[0]
        slug = eagate.GKEYS[first]
        with tempfile.TemporaryDirectory() as tmp:
            _write_json(os.path.join(tmp, slug + ".json"), [{"name": "old"}])
            with mock.patch.object(eagate, "scrape_game", return_value=[]):
                with self.assertRaises(SystemExit):
                    run_all.scrape_all(tmp, only={"eagate"})
            kept = json.load(open(os.path.join(tmp, slug + ".json"),
                                  encoding="utf-8"))
            self.assertEqual(kept, [{"name": "old"}])

    def test_eagate_circuit_breaker_skips_remaining_gkeys(self):
        calls = []

        def boom(gkey, **kw):
            calls.append(gkey)
            raise common.FetchError("HTTP Error 503: 503")

        first = sorted(eagate.GKEYS)[0]
        slug = eagate.GKEYS[first]
        with tempfile.TemporaryDirectory() as tmp:
            _write_json(os.path.join(tmp, slug + ".json"), [{"name": "old"}])
            with mock.patch.object(eagate, "scrape_game", side_effect=boom):
                run_all.scrape_all(tmp, only={"eagate"})
        self.assertEqual(calls, [first])

    def test_successful_scrape_overwrites(self):
        first = sorted(eagate.GKEYS)[0]
        slug = eagate.GKEYS[first]
        rest = [k for k in sorted(eagate.GKEYS) if k != first]

        def fake(gkey, **kw):
            return [{"name": "fresh-%s" % gkey}]

        with tempfile.TemporaryDirectory() as tmp:
            _write_json(os.path.join(tmp, slug + ".json"), [{"name": "old"}])
            with mock.patch.object(eagate, "scrape_game", side_effect=fake):
                run_all.scrape_all(tmp, only={"eagate"})
            fresh = json.load(open(os.path.join(tmp, slug + ".json"),
                                   encoding="utf-8"))
            self.assertEqual(fresh, [{"name": "fresh-%s" % first}])
            last = rest[-1]
            last_rows = json.load(
                open(os.path.join(tmp, eagate.GKEYS[last] + ".json"),
                     encoding="utf-8"))
            self.assertEqual(last_rows, [{"name": "fresh-%s" % last}])


if __name__ == "__main__":
    unittest.main()
