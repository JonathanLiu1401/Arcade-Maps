"""Fetch USD FX rates for arcade price display (data/fx_rates.json).

Primary:  https://api.frankfurter.app/latest?from=USD  (ECB, keyless)
Fallback: https://open.er-api.com/v6/latest/USD       (for gaps / full fail)

Currencies: JPY/HKD/CNY plus every code in js/format.js CURRENCY_SYMBOL
(TWD KRW SGD MYR THB VND IDR AUD NZD GBP EUR CAD PHP), with USD=1.

Frankfurter is ECB-based and omits some Asian codes (live-verified
2026-07-27: TWD and VND absent; PHP is present). Missing codes are
filled from open.er-api.com and recorded in the per-currency `sources`
map.

Never writes a broken file: if both sources fail (or required rates are
still missing after both), the previous data/fx_rates.json is left in
place and this module exits 0 with a warning so the weekly Actions run
can still commit the rest of the data refresh.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PRIMARY_URL = "https://api.frankfurter.app/latest?from=USD"
FALLBACK_URL = "https://open.er-api.com/v6/latest/USD"
OUTFILE = "fx_rates.json"
PRIMARY_NAME = "frankfurter"
FALLBACK_NAME = "open.er-api.com"

# Mirror js/format.js CURRENCY_SYMBOL (plus USD base). Keep in sync when
# the frontend gains a new display currency.
CURRENCIES = [
    "USD",
    "JPY", "HKD", "CNY",
    "PHP", "TWD", "KRW", "SGD", "MYR", "THB", "VND", "IDR",
    "AUD", "NZD", "GBP", "EUR", "CAD",
]

# Soft sanity bands for 2026 (USD base). Out-of-band rates are accepted
# but printed loudly so a bad feed is obvious in CI logs.
SANITY = {
    "JPY": (140.0, 190.0),
    "HKD": (7.7, 7.9),
    "CNY": (6.0, 8.0),
}


def _parse_frankfurter(text):
    """Return (date_str_or_None, {CODE: float}) from frankfurter JSON."""
    data = json.loads(text)
    rates_in = data.get("rates") or {}
    out = {}
    for code, val in rates_in.items():
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if v > 0:
            out[str(code).upper()] = v
    out["USD"] = 1.0
    date_str = data.get("date")
    if not isinstance(date_str, str) or not date_str:
        date_str = None
    return date_str, out


def _parse_erapi(text):
    """Return (date_str_or_None, {CODE: float}) from open.er-api.com JSON."""
    data = json.loads(text)
    # older/alternate shapes may omit result; only hard-fail on explicit error
    result = data.get("result")
    if result is not None and result != "success":
        raise common.FetchError(
            "open.er-api.com result=%r" % (result,))
    rates_in = data.get("rates") or {}
    out = {}
    for code, val in rates_in.items():
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if v > 0:
            out[str(code).upper()] = v
    out["USD"] = 1.0
    # Prefer the YYYY-MM-DD portion of time_last_update_utc if present.
    date_str = None
    utc = data.get("time_last_update_utc")
    if isinstance(utc, str) and len(utc) >= 16:
        # e.g. "Mon, 27 Jul 2026 00:02:31 +0000"
        try:
            dt = datetime.strptime(utc, "%a, %d %b %Y %H:%M:%S %z")
            date_str = dt.date().isoformat()
        except ValueError:
            date_str = None
    return date_str, out


def _fetch_primary():
    text = common.fetch(PRIMARY_URL, sleep=0)
    return _parse_frankfurter(text)


def _fetch_fallback():
    text = common.fetch(FALLBACK_URL, sleep=0)
    return _parse_erapi(text)


def build_rates():
    """Fetch and merge rates. Raises FetchError only if nothing usable.

    Returns the payload dict ready to write (base/date/rates/source/
    sources/fetched_at). Does not touch the filesystem.
    """
    primary_date = None
    primary_rates = {}
    primary_err = None
    try:
        primary_date, primary_rates = _fetch_primary()
        print("fx: primary %s returned %d rates (date=%s)"
              % (PRIMARY_NAME, len(primary_rates), primary_date),
              file=sys.stderr)
    except Exception as e:
        primary_err = e
        print("fx: primary %s FAILED: %s: %s"
              % (PRIMARY_NAME, type(e).__name__, e), file=sys.stderr)

    need = [c for c in CURRENCIES if c not in primary_rates]
    fallback_date = None
    fallback_rates = {}
    fallback_err = None
    if need or not primary_rates:
        try:
            fallback_date, fallback_rates = _fetch_fallback()
            print("fx: fallback %s returned %d rates (date=%s); "
                  "filling %s"
                  % (FALLBACK_NAME, len(fallback_rates), fallback_date,
                     ",".join(need) if need else "(full)"),
                  file=sys.stderr)
        except Exception as e:
            fallback_err = e
            print("fx: fallback %s FAILED: %s: %s"
                  % (FALLBACK_NAME, type(e).__name__, e), file=sys.stderr)

    rates = {}
    sources = {}
    for code in CURRENCIES:
        if code in primary_rates:
            rates[code] = primary_rates[code]
            sources[code] = PRIMARY_NAME
        elif code in fallback_rates:
            rates[code] = fallback_rates[code]
            sources[code] = FALLBACK_NAME

    # USD is definitional even if both feeds omit it.
    rates["USD"] = 1.0
    sources["USD"] = "base"

    missing = [c for c in CURRENCIES if c not in rates]
    if missing:
        raise common.FetchError(
            "still missing currencies after both feeds: %s "
            "(primary_err=%s, fallback_err=%s)"
            % (",".join(missing), primary_err, fallback_err))

    used = sorted(set(sources.values()) - {"base"})
    if not used:
        source_summary = "base"
    elif len(used) == 1:
        source_summary = used[0]
    else:
        # stable order: frankfurter first when present
        order = [PRIMARY_NAME, FALLBACK_NAME]
        source_summary = "+".join(
            [s for s in order if s in used]
            + [s for s in used if s not in order])

    date_str = primary_date or fallback_date
    if not date_str:
        date_str = datetime.now(timezone.utc).date().isoformat()

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for code, (lo, hi) in SANITY.items():
        v = rates.get(code)
        if v is None:
            continue
        if not (lo <= v <= hi):
            print("fx: WARNING %s=%.6g outside expected [%.4g, %.4g] "
                  "(2026 sanity band) - investigate the feed"
                  % (code, v, lo, hi), file=sys.stderr)

    return {
        "base": "USD",
        "date": date_str,
        "rates": {c: rates[c] for c in CURRENCIES},
        "source": source_summary,
        "sources": {c: sources[c] for c in CURRENCIES},
        "fetched_at": fetched_at,
    }


def run(out_dir="data", outfile=OUTFILE):
    """Write fx_rates.json under out_dir. Never clobbers on failure.

    Returns (path, payload) on success. On total failure returns
    (path, None) after printing a warning, and does not raise - callers
    (weekly Actions, run_all) treat FX as non-fatal.
    """
    path = os.path.join(out_dir, outfile)
    try:
        payload = build_rates()
    except Exception as e:
        print("fx: WARNING both feeds failed (%s: %s); keeping previous "
              "file at %s if present"
              % (type(e).__name__, e, path), file=sys.stderr)
        if os.path.isfile(path):
            print("fx: previous file retained (%d bytes)"
                  % os.path.getsize(path), file=sys.stderr)
        else:
            print("fx: no previous file at %s" % path, file=sys.stderr)
        return path, None

    # Atomic-ish write: build in memory, only then save. common.save_json
    # truncates on open, so we only call it after a complete payload.
    common.save_json(path, payload)
    print("fx: wrote %s (base=%s date=%s source=%s rates=%d)"
          % (path, payload["base"], payload["date"], payload["source"],
             len(payload["rates"])), file=sys.stderr)
    return path, payload


def main():
    ap = argparse.ArgumentParser(
        description="fetch USD FX rates into data/fx_rates.json")
    ap.add_argument("--out", default="data", help="output directory")
    ap.add_argument("--outfile", default=OUTFILE)
    args = ap.parse_args()
    path, payload = run(args.out, args.outfile)
    if payload is None:
        # Non-fatal: weekly pipeline should still commit other data.
        print("fx: degraded (exit 0); see warnings above")
        return
    # Human-readable summary on stdout for CI / local runs.
    print(json.dumps(payload, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
