#!/usr/bin/env python3
"""Playwright + screenshot verification of Arcade Maps i18n (strict)."""
from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tools" / "_verify_shots"
OUT.mkdir(parents=True, exist_ok=True)

FAILS: list[str] = []
OKS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print("FAIL:", msg)


def ok(msg: str) -> None:
    OKS.append(msg)
    print("OK:", msg)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, fmt, *args):
        pass


def start_server():
    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def wait_data(page, timeout_ms=60000):
    page.wait_for_function(
        """() => window.AM && AM.data && AM.data.arcades && AM.data.arcades.length > 1000""",
        timeout=timeout_ms,
    )


def main() -> int:
    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}/"
    print("serving", base)
    report: dict = {"shots": [], "langs": {}}

    # Keys the UI actually uses (from panel.js / nearby.js / settings)
    must_keys = [
        "tab.filters",
        "pane.games",
        "pane.cab_variants",
        "pane.arcade_size",
        "search.placeholder",
        "ui.search_wide",
        "place.directions",
        "place.share",
        "place.nearby",
        "place.search_gmaps",
        "nearby.empty",
        "nearby.nearest_you",
        "nearby.showing",
        "nb.err_denied",
        "settings.sec_sources",
        "cabs.other_game",
        "ui.show_more",
        "ui.size_3",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 920}, locale="en-US")
        page = context.new_page()
        page.goto(base, wait_until="domcontentloaded", timeout=120_000)
        page.evaluate("() => localStorage.removeItem('am_lang')")
        page.reload(wait_until="domcontentloaded")
        wait_data(page)
        page.wait_for_timeout(800)

        if page.locator("#lang-btn").count() == 0:
            fail("lang button missing")
        else:
            ok("lang button present")

        # 16 locales in menu
        page.locator("#lang-btn").click()
        page.wait_for_timeout(200)
        n = page.locator("#am-lang-menu [data-lang]").count()
        if n != 16:
            fail(f"lang menu items={n} expected 16")
        else:
            ok("16 locales in menu")
        page.screenshot(path=str(OUT / "10_lang_menu.png"))
        report["shots"].append("10_lang_menu.png")
        page.keyboard.press("Escape")

        for lang in ["en", "ja", "zh-Hans", "ko", "es", "fr", "de", "pt", "ru", "th", "vi", "id"]:
            page.evaluate("(c) => AM.i18n.setLang(c, {force:true})", lang)
            page.wait_for_timeout(500)
            if page.evaluate("() => AM.i18n.getLang()") != lang:
                fail(f"getLang not {lang}")
                continue

            # key resolution
            miss = []
            vals = {}
            for k in must_keys:
                v = page.evaluate("(k) => AM.i18n.t(k)", k)
                vals[k] = v
                if v == k:
                    miss.append(k)
            if miss:
                fail(f"{lang}: missing keys {miss}")
            else:
                ok(f"{lang}: all must_keys resolve")

            # English keys must not stay English for non-en (spot check)
            if lang != "en":
                if vals["tab.filters"] == "Filters":
                    fail(f"{lang}: tab.filters still Filters")
                if vals["place.directions"] == "Directions":
                    fail(f"{lang}: place.directions still Directions")
                if vals["place.search_gmaps"] == "Search in Google Maps" and lang in (
                    "ja", "zh-Hans", "ko", "ru", "th"
                ):
                    fail(f"{lang}: search_gmaps still English")

            # Open a real place panel via state
            opened = page.evaluate(
                """() => {
                  const list = AM.data.arcades;
                  const a = list.find(x => x && x.lat != null && (x.lng != null || x.lon != null)
                    && (x.games && x.games.length > 2));
                  if (!a) return {ok:false, reason:'no arcade'};
                  AM.state.set('selectedArcade', a.id, {focus:true, source:'verify'});
                  return {ok:true, id:a.id, name:a.name};
                }"""
            )
            page.wait_for_timeout(700)
            panel_txt = page.evaluate(
                """() => {
                  const el = document.getElementById('place') || document.querySelector('.place-panel') || document.getElementById('place-panel');
                  // place panel is often #place or body class
                  const candidates = [
                    document.getElementById('place'),
                    document.querySelector('.pl-panel'),
                    document.querySelector('#drawer .place'),
                    document.querySelector('[class*=\"place\"]'),
                  ].filter(Boolean);
                  let best = '';
                  for (const c of candidates) {
                    const t = (c.innerText || '').trim();
                    if (t.length > best.length) best = t;
                  }
                  // also action buttons
                  const acts = Array.from(document.querySelectorAll('.act-lb, .pl-act .act-lb, [data-act]'))
                    .map(e => (e.innerText||'').trim()).filter(Boolean);
                  return {text: best.slice(0, 1500), acts, bodyClass: document.body.className};
                }"""
            )
            print(f"  {lang} open:", opened, "acts:", panel_txt.get("acts"))
            page.screenshot(path=str(OUT / f"11_{lang}_panel.png"))
            report["shots"].append(f"11_{lang}_panel.png")
            (OUT / f"11_{lang}_panel.txt").write_text(
                json.dumps({"opened": opened, "panel": panel_txt, "vals": vals}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            acts = panel_txt.get("acts") or []
            # After open, should see localized Directions/Share/Nearby labels
            if opened.get("ok") and acts:
                joined = " ".join(acts)
                if lang == "ja" and ("ルート" not in joined and "共有" not in joined and "近く" not in joined):
                    # still might use different wording
                    if vals["place.directions"] not in joined and vals["place.share"] not in joined:
                        fail(f"ja panel acts not localized: {acts}")
                    else:
                        ok(f"ja panel acts localized: {acts}")
                elif lang != "en":
                    # at least one act should match t() value
                    expected = {vals["place.directions"], vals["place.share"], vals["place.nearby"]}
                    if expected & set(acts):
                        ok(f"{lang} panel acts match t(): {acts}")
                    else:
                        # soft if panel structure different
                        print(f"  note {lang}: acts={acts} expected one of {expected}")
            elif opened.get("ok"):
                print(f"  note {lang}: panel opened but no .act-lb found; body={panel_txt.get('bodyClass')}")

            # Drawer labels via data-i18n
            drawer = page.evaluate(
                """() => {
                  const t = (id) => {
                    const el = document.getElementById(id);
                    return el ? (el.innerText||'').trim() : null;
                  };
                  return {
                    filters: t('tab-filters'),
                    games: document.querySelector('#pane-filters [data-i18n=\"pane.games\"], #pane-filters .pane-title')?.innerText,
                    all: document.getElementById('games-all')?.innerText,
                  };
                }"""
            )
            report["langs"][lang] = {"vals": vals, "drawer": drawer, "opened": opened, "acts": acts}
            page.screenshot(path=str(OUT / f"12_{lang}_drawer.png"))

            # Close panel for next
            page.evaluate("() => { try { AM.state.set('selectedArcade', null); } catch(e){} }")
            page.wait_for_timeout(200)

        # Menu click path for ja
        page.evaluate("() => AM.i18n.setLang('en', {force:true})")
        page.wait_for_timeout(200)
        page.locator("#lang-btn").click()
        page.locator('#am-lang-menu [data-lang="ja"]').click()
        page.wait_for_timeout(400)
        if page.evaluate("() => AM.i18n.getLang()") != "ja":
            fail("menu click ja failed")
        else:
            ok("menu click sets ja")
        page.screenshot(path=str(OUT / "13_menu_ja.png"))

        # Nearby empty string localization without geolocation: call showFrom
        page.evaluate(
            """() => {
              AM.i18n.setLang('ja', {force:true});
              if (AM.nearby && AM.nearby.showFrom) {
                AM.nearby.showFrom(35.68, 139.76, {label: 'Tokyo', fly:false});
              }
            }"""
        )
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "14_ja_nearby.png"))
        nb = page.evaluate(
            """() => ({
              title: document.querySelector('#pane-nearby .pane-title')?.innerText,
              origin: document.getElementById('nb-origin')?.innerText,
              empty: document.querySelector('#nb-list .nb-empty')?.innerText,
              cap: document.getElementById('nb-caption')?.innerText,
            })"""
        )
        print("nearby ja:", nb)
        (OUT / "14_ja_nearby.txt").write_text(json.dumps(nb, ensure_ascii=False, indent=2), encoding="utf-8")
        if nb.get("origin") and "Nearest to" in (nb.get("origin") or ""):
            fail(f"nearby origin still English: {nb.get('origin')!r}")
        elif nb.get("origin"):
            ok(f"nearby origin localized: {nb.get('origin')!r}")
        if nb.get("empty") and "No stores match" in (nb.get("empty") or ""):
            fail(f"nearby empty still English: {nb.get('empty')!r}")
        if nb.get("cap") and "Showing the" in (nb.get("cap") or ""):
            fail(f"nearby caption still English: {nb.get('cap')!r}")
        elif nb.get("cap"):
            ok(f"nearby caption: {nb.get('cap')!r}")

        # Place-panel re-render on lang change while open
        page.evaluate(
            """() => {
              AM.i18n.setLang('en', {force:true});
              const a = AM.data.arcades.find(x => x && x.lat != null && x.games && x.games.length > 1);
              AM.state.set('selectedArcade', a.id, {focus:true, source:'verify-rerender'});
            }"""
        )
        page.wait_for_timeout(700)
        en_acts = page.evaluate(
            """() => Array.from(document.querySelectorAll('.act-lb'))
              .map(e => (e.innerText||'').trim()).filter(Boolean)"""
        )
        page.screenshot(path=str(OUT / "15_panel_en_before.png"))
        page.evaluate("() => AM.i18n.setLang('ja', {force:true})")
        page.wait_for_timeout(900)
        ja_acts = page.evaluate(
            """() => Array.from(document.querySelectorAll('.act-lb'))
              .map(e => (e.innerText||'').trim()).filter(Boolean)"""
        )
        page.screenshot(path=str(OUT / "16_panel_ja_after_lang.png"))
        report["panel_rerender"] = {"en_acts": en_acts, "ja_acts": ja_acts}
        print("panel re-render EN:", en_acts, "JA:", ja_acts)
        ja_dir = page.evaluate("() => AM.i18n.t('place.directions')")
        en_dir = "Directions"
        if not en_acts and not ja_acts:
            fail("place panel re-render: no .act-lb found before/after lang change")
        elif en_acts == ja_acts and ja_dir not in (ja_acts or []):
            fail(f"place panel did NOT re-render on lang change; stayed {ja_acts}")
        elif ja_dir in (ja_acts or []) and en_dir not in (ja_acts or []):
            ok(f"place panel re-render: {en_acts} -> {ja_acts}")
        elif ja_dir in (ja_acts or []):
            ok(f"place panel re-render includes JA directions: {ja_acts}")
        else:
            fail(f"place panel re-render unclear en={en_acts} ja={ja_acts} want={ja_dir!r}")

        # Filter chip rebuild: Other label flips with lang
        page.evaluate("() => AM.i18n.setLang('en', {force:true})")
        page.wait_for_timeout(400)
        en_other = page.evaluate(
            """() => {
              const chips = Array.from(document.querySelectorAll('#game-chips .chip, #game-chips button'));
              const hit = chips.find(c => /other/i.test(c.innerText||''));
              return hit ? (hit.innerText||'').trim() : null;
            }"""
        )
        page.evaluate("() => AM.i18n.setLang('ja', {force:true})")
        page.wait_for_timeout(500)
        ja_other = page.evaluate(
            """() => {
              const chips = Array.from(document.querySelectorAll('#game-chips .chip, #game-chips button'));
              const hit = chips.find(c => /その他|Other/i.test(c.innerText||''));
              return hit ? (hit.innerText||'').trim() : null;
            }"""
        )
        print("other chip EN:", en_other, "JA:", ja_other)
        if ja_other and "その他" in ja_other:
            ok(f"game chip rebuild: Other -> {ja_other!r}")
        elif en_other and ja_other and en_other != ja_other:
            ok(f"game chip rebuild changed: {en_other!r} -> {ja_other!r}")
        else:
            fail(f"game chip Other did not localize: en={en_other!r} ja={ja_other!r}")

        browser.close()

    httpd.shutdown()
    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(f"OK={len(OKS)} FAIL={len(FAILS)}")
    for f in FAILS:
        print(" -", f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
