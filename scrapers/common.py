"""Shared helpers for Arcade Maps scrapers.

stdlib only: urllib for HTTP, json for output.
Every fetch retries on failure and raises FetchError at the end so
callers exit nonzero instead of silently writing empty output.

Ordinary transport errors (timeout, reset, IncompleteRead, 4xx) retry
`retries` times with 1s/2s/4s backoff. HTTP 429/500/502/503/504 retry
longer: those are WAF cool-downs and brief origin outages, and the
2026-08-17 weekly Action died on the first eagate URL after three 503s
in seven seconds. A 5xx from Imperva is not a parser bug.
"""

import html
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

DEFAULT_SLEEP = 0.4
DEFAULT_RETRIES = 3
TRANSIENT_RETRIES = 8
TRANSIENT_HTTP_CODES = frozenset({429, 500, 502, 503, 504})
TRANSIENT_BACKOFF_START = 5
TRANSIENT_BACKOFF_CAP = 120


class FetchError(RuntimeError):
    pass


def http_status(err):
    """HTTP status code on HTTPError, else None."""
    return getattr(err, "code", None)


def is_transient_http(err):
    """True for 429 / 5xx that should wait out a WAF or blip."""
    return http_status(err) in TRANSIENT_HTTP_CODES


def _open(req, timeout, cookiejar):
    if cookiejar is None:
        return urllib.request.urlopen(req, timeout=timeout)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookiejar))
    return opener.open(req, timeout=timeout)


def fetch(url, extra_headers=None, retries=DEFAULT_RETRIES, sleep=DEFAULT_SLEEP,
          timeout=30, cookiejar=None, transient_retries=TRANSIENT_RETRIES):
    """GET url, return decoded text (utf-8, replace errors).

    Retries ordinary failures `retries` times (1s, 2s, 4s). HTTP 429 and
    5xx use `transient_retries` and a longer cap (5s, 10s, ... 120s) so a
    WAF 503 can cool down. Raises FetchError after the last attempt.
    Sleeps `sleep` seconds after each successful request (politeness).
    Pass `cookiejar` (http.cookiejar.CookieJar) to keep WAF/session cookies.
    """
    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    last_err = None
    used = 0
    max_attempts = max(retries, transient_retries)
    for attempt in range(max_attempts):
        try:
            req = urllib.request.Request(url, headers=headers)
            with _open(req, timeout, cookiejar) as resp:
                raw = resp.read()
            time.sleep(sleep)
            return raw.decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                http.client.HTTPException) as e:
            # http.client.IncompleteRead (a server that announces a chunked
            # body and then stops sending) is an HTTPException, NOT an
            # OSError or URLError. Every scraper in this repo fetches
            # through here, so omitting it meant ONE truncated response
            # anywhere could abort the whole weekly build - which is what
            # killed the 2026-08-03 run at a BemaniCN city request. A
            # truncated read is transient and is exactly what retrying is for.
            last_err = e
            used = attempt + 1
            limit = transient_retries if is_transient_http(e) else retries
            if used >= limit:
                break
            if is_transient_http(e):
                wait = min(TRANSIENT_BACKOFF_CAP,
                           TRANSIENT_BACKOFF_START * (2 ** attempt))
            else:
                wait = 2 ** attempt
            print("fetch attempt %d/%d failed for %s: %s (retry in %ds)"
                  % (used, limit, url, e, wait), file=sys.stderr)
            time.sleep(wait)
    raise FetchError("giving up on %s after %d attempts: %s"
                     % (url, used if last_err is not None else 0, last_err))


def unescape(text):
    """HTML-unescape, normalize whitespace, and replace en/em dashes
    (U+2013 / U+2014, as they appear in some upstream names/addresses)
    with ASCII hyphens, per this repo's ASCII-punctuation policy."""
    if text is None:
        return None
    text = html.unescape(text).replace(chr(0x2013), "-").replace(chr(0x2014), "-")
    return " ".join(text.split())


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
