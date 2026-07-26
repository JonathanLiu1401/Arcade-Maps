"""Shared helpers for Arcade Maps scrapers.

stdlib only: urllib for HTTP, json for output.
Every fetch retries 3x with exponential backoff and raises on final failure
so callers exit nonzero instead of silently writing empty output.
"""

import html
import json
import os
import sys
import time
import urllib.error
import urllib.request

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

DEFAULT_SLEEP = 0.4


class FetchError(RuntimeError):
    pass


def fetch(url, extra_headers=None, retries=3, sleep=DEFAULT_SLEEP, timeout=30):
    """GET url, return decoded text (utf-8, replace errors).

    Retries `retries` times with exponential backoff (1s, 2s, 4s).
    Raises FetchError after the last attempt fails.
    Sleeps `sleep` seconds after each successful request (politeness).
    """
    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            time.sleep(sleep)
            return raw.decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            last_err = e
            wait = 2 ** attempt
            print("fetch attempt %d/%d failed for %s: %s (retry in %ds)"
                  % (attempt + 1, retries, url, e, wait), file=sys.stderr)
            time.sleep(wait)
    raise FetchError("giving up on %s after %d attempts: %s"
                     % (url, retries, last_err))


def unescape(text):
    """HTML-unescape and normalize whitespace."""
    if text is None:
        return None
    return " ".join(html.unescape(text).split())


def save_json(path, data):
    """Write pretty UTF-8 JSON (matching the scratch data style)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def die(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)
