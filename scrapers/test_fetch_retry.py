"""Regression: truncated HTTP responses must be retried, not kill the build.

The 2026-08-03 weekly Action died mid-BemaniCN crawl with:

    http.client.IncompleteRead: IncompleteRead(2942 bytes read)

IncompleteRead is an HTTPException, not OSError/URLError. Before the fix,
every scraper retry loop omitted it, so ONE truncated chunked body aborted
the whole pipeline and left the map on the previous week's data.

These tests pin that both common.fetch and bemanicn._fetch_json:
  * catch IncompleteRead
  * retry
  * return the body on a later success
  * raise FetchError only after retries are exhausted
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common  # noqa: E402
import bemanicn  # noqa: E402


class _FakeResp:
    """urlopen context-manager stand-in."""

    def __init__(self, body=None, raise_on_read=None):
        self._body = body if body is not None else b""
        self._raise = raise_on_read

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        if self._raise is not None:
            raise self._raise
        return self._body


class TestCommonFetchRetriesIncompleteRead(unittest.TestCase):
    def test_incomplete_read_then_success(self):
        calls = {"n": 0}

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            if calls["n"] == 1:
                return _FakeResp(
                    raise_on_read=http.client.IncompleteRead(b"partial"))
            return _FakeResp(body=b"ok-body")

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             mock.patch("time.sleep"):  # no real backoff in tests
            text = common.fetch("https://example.test/x", retries=3, sleep=0)
        self.assertEqual(text, "ok-body")
        self.assertEqual(calls["n"], 2)

    def test_incomplete_read_exhausted_raises_fetch_error(self):
        def always_truncated(req, timeout=30):
            return _FakeResp(
                raise_on_read=http.client.IncompleteRead(b"x"))

        with mock.patch("urllib.request.urlopen",
                        side_effect=always_truncated), \
             mock.patch("time.sleep"):
            with self.assertRaises(common.FetchError) as cm:
                common.fetch("https://example.test/x", retries=3, sleep=0)
        self.assertIn("IncompleteRead", str(cm.exception))


class TestBemaniCNFetchJsonRetriesIncompleteRead(unittest.TestCase):
    def test_incomplete_read_then_success(self):
        payload = {"props": {"city": {"shops": []}}}
        body = json.dumps(payload).encode("utf-8")
        calls = {"n": 0}

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            if calls["n"] < 3:
                return _FakeResp(
                    raise_on_read=http.client.IncompleteRead(b"{"))
            return _FakeResp(body=body)

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             mock.patch("time.sleep"), \
             mock.patch.object(bemanicn, "SLEEP", 0), \
             mock.patch.object(bemanicn, "RETRIES", 4):
            data = bemanicn._fetch_json("https://map.bemanicn.com/region/city/1")
        self.assertEqual(data, payload)
        self.assertEqual(calls["n"], 3)

    def test_incomplete_read_exhausted_raises_fetch_error(self):
        def always_truncated(req, timeout=30):
            return _FakeResp(
                raise_on_read=http.client.IncompleteRead(b"2942"))

        with mock.patch("urllib.request.urlopen",
                        side_effect=always_truncated), \
             mock.patch("time.sleep"), \
             mock.patch.object(bemanicn, "SLEEP", 0), \
             mock.patch.object(bemanicn, "RETRIES", 3):
            with self.assertRaises(common.FetchError) as cm:
                bemanicn._fetch_json("https://map.bemanicn.com/region/city/1")
        self.assertIn("IncompleteRead", str(cm.exception))

    def test_city_shops_survives_transient_truncation(self):
        """city_shops must not let IncompleteRead escape as a raw exception.

        That is the exact failure mode of the 2026-08-03 Action: the
        exception left _fetch_json, skipped the per-city FetchError handler
        in _crawl_pass, and killed scrape().
        """
        payload = {"props": {"city": {"shops": [{"id": 1, "name": "x"}]}}}
        body = json.dumps(payload).encode("utf-8")
        calls = {"n": 0}

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            if calls["n"] == 1:
                return _FakeResp(
                    raise_on_read=http.client.IncompleteRead(b"2942"))
            return _FakeResp(body=body)

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             mock.patch("time.sleep"), \
             mock.patch.object(bemanicn, "SLEEP", 0):
            shops = bemanicn.city_shops("350200000000")
        self.assertEqual(len(shops), 1)
        self.assertEqual(shops[0]["id"], 1)


class TestIncompleteReadIsHttpException(unittest.TestCase):
    def test_mro(self):
        # Guard against a future stdlib change silently undoing the catch.
        self.assertTrue(
            issubclass(http.client.IncompleteRead, http.client.HTTPException))


if __name__ == "__main__":
    unittest.main()
