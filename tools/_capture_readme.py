#!/usr/bin/env python3
"""Capture README screenshots from a local server.

Writes into docs/. Waits for arcade data, Leaflet tiles, and markers
so the old circle-cluster world shot is replaced with the current UI.
"""
from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"

TOKYO = "13.2/35.6993/139.7710"
AKI_ZOOM = "15.5/35.69926/139.77090"
AKI_SID = "z2701"
AKI_HASH = f"{AKI_ZOOM}/arcade={AKI_SID}"


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


def wait_map(page, timeout_ms=90000):
    page.wait_for_function(
        """() => window.AM && AM.data && AM.data.arcades
           && AM.data.arcades.length > 1000""",
        timeout=timeout_ms,
    )
    page.wait_for_function(
        """() => {
          const tiles = [...document.querySelectorAll('.leaflet-tile-loaded')];
          const marks = document.querySelectorAll('.leaflet-marker-icon');
          return tiles.length >= 6 && marks.length >= 3;
        }""",
        timeout=timeout_ms,
    )
    page.wait_for_selector(".leaflet-control-scale-line", timeout=timeout_ms)
    page.wait_for_selector("#game-chips .chip", state="attached", timeout=timeout_ms)
    page.wait_for_timeout(1800)


def open_filters(page):
    page.evaluate(
        """() => {
          document.body.classList.remove('drawer-closed');
          const t = document.getElementById('drawer-toggle');
          if (t) t.setAttribute('aria-expanded', 'true');
          if (window.AM && AM.map && AM.map.map) AM.map.map.invalidateSize();
        }"""
    )
    page.wait_for_timeout(400)


def close_filters(page):
    page.evaluate(
        """() => {
          document.body.classList.add('drawer-closed');
          const t = document.getElementById('drawer-toggle');
          if (t) t.setAttribute('aria-expanded', 'false');
          if (window.AM && AM.map && AM.map.map) AM.map.map.invalidateSize();
        }"""
    )
    page.wait_for_timeout(400)


def collapse_legend(page):
    page.evaluate(
        """() => {
          const btn = document.getElementById('legend-toggle');
          if (btn && btn.getAttribute('aria-expanded') === 'true') btn.click();
        }"""
    )
    page.wait_for_timeout(300)


def expand_legend(page):
    page.wait_for_selector("#legend-toggle", timeout=20000)
    page.evaluate(
        """() => {
          const btn = document.getElementById('legend-toggle');
          if (btn && btn.getAttribute('aria-expanded') !== 'true') btn.click();
        }"""
    )
    page.wait_for_function(
        """() => {
          const b = document.getElementById('legend-body');
          const btn = document.getElementById('legend-toggle');
          return b && !b.hidden && btn && btn.getAttribute('aria-expanded') === 'true';
        }""",
        timeout=10000,
    )
    page.wait_for_timeout(500)


def open_aki(page):
    page.evaluate(
        """() => {
          const a = AM.data.bySid && AM.data.bySid['z2701'];
          if (a) AM.state.set('selectedArcade', a.id, {focus:true, source:'hash'});
        }"""
    )


def wait_place(page):
    page.wait_for_function(
        """() => {
          const el = document.getElementById('place');
          if (!el || el.hidden) return false;
          const r = el.getBoundingClientRect();
          return r.width > 80 && r.height > 120 && el.innerText.length > 40;
        }""",
        timeout=20000,
    )
    try:
        page.wait_for_selector("#place img", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(800)


def tile_info(page):
    return page.evaluate(
        """() => {
          const srcs = [...document.querySelectorAll('.leaflet-tile')]
            .map(i => i.src || '');
          const carto = srcs.filter(s => /cartocdn|voyager/i.test(s)).length;
          const osm = srcs.filter(s => /tile\\.openstreetmap\\.org/i.test(s)).length;
          const attr = (document.querySelector('.leaflet-control-attribution')
            || {}).innerText || '';
          const scale = document.querySelector('.leaflet-control-scale');
          const sr = scale ? scale.getBoundingClientRect() : null;
          const legend = document.getElementById('legend-toggle');
          const body = document.getElementById('legend-body');
          const chips = document.querySelectorAll('#game-chips .chip').length;
          const other = [...document.querySelectorAll('#game-chips .chip')]
            .find(c => (c.dataset.g || '') === 'other');
          return {
            nTiles: srcs.length,
            carto,
            osm,
            attr,
            scale: !!scale,
            scaleText: scale ? (scale.innerText || '').replace(/\\s+/g, ' ').trim() : '',
            scaleBox: sr ? {x: sr.x, y: sr.y, w: sr.width, h: sr.height} : null,
            legendOpen: !!(legend && legend.getAttribute('aria-expanded') === 'true'),
            legendBody: !!(body && !body.hidden),
            chips,
            otherColor: other ? getComputedStyle(other).getPropertyValue('--chip')
              || getComputedStyle(other.querySelector('.dot') || other).backgroundColor
              : null,
            shown: (document.getElementById('meta-count') || {}).innerText || '',
            sample: srcs.slice(0, 3),
          };
        }"""
    )


def shot(page, name):
    path = OUT / name
    page.screenshot(path=str(path), full_page=False)
    if path.suffix.lower() == ".jpg":
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.save(path, "JPEG", quality=88, optimize=True, progressive=True)
    info = tile_info(page)
    print("wrote", path, path.stat().st_size, info)


def main():
    httpd, port = start_server()
    base = "http://127.0.0.1:%d/" % port
    print("serving", base)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        desktop = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
            locale="en-US",
        )
        page = desktop.new_page()
        page.goto(base, wait_until="domcontentloaded", timeout=120000)
        page.evaluate("() => { localStorage.clear(); }")
        page.reload(wait_until="domcontentloaded")
        wait_map(page)
        open_filters(page)
        wait_map(page)
        shot(page, "screenshot.png")

        page.goto(base + "#" + AKI_ZOOM, wait_until="domcontentloaded")
        wait_map(page)
        open_filters(page)
        shot(page, "readme-akihabara.jpg")

        page.goto(base + "#" + TOKYO, wait_until="domcontentloaded")
        wait_map(page)
        open_filters(page)
        expand_legend(page)
        shot(page, "readme-legend.jpg")

        page.goto(base + "#" + AKI_HASH, wait_until="domcontentloaded")
        wait_map(page)
        collapse_legend(page)
        open_aki(page)
        wait_place(page)
        shot(page, "readme-place.jpg")

        page.evaluate("() => AM.i18n.setLang('ja', {force:true})")
        page.wait_for_timeout(700)
        open_aki(page)
        wait_place(page)
        shot(page, "readme-ja.jpg")

        desktop.close()

        phone = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        )
        mp = phone.new_page()
        mp.goto(base + "#" + TOKYO, wait_until="domcontentloaded",
                timeout=120000)
        mp.evaluate("() => localStorage.clear()")
        mp.reload(wait_until="domcontentloaded")
        wait_map(mp)
        close_filters(mp)
        mp.goto(base + "#" + AKI_HASH, wait_until="domcontentloaded")
        wait_map(mp)
        close_filters(mp)
        open_aki(mp)
        wait_place(mp)
        close_filters(mp)
        shot(mp, "readme-mobile-place.jpg")
        browser.close()
    httpd.shutdown()
    print("done")


if __name__ == "__main__":
    main()
