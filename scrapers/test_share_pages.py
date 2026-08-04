"""Unit tests for scrapers/build_share_pages.py (static map + dual card)."""

from __future__ import annotations

import re

from scrapers.build_share_pages import (
    STATIC_MAP_ZOOM,
    _coords,
    _map_caption,
    _static_map_url,
    render_page,
)


def test_coords_valid():
    assert _coords({"lat": 10.67, "lng": 122.94}) == (10.67, 122.94)
    assert _coords({"lat": "31.2", "lng": "121.4"}) == (31.2, 121.4)


def test_coords_missing_or_invalid():
    assert _coords({}) is None
    assert _coords({"lat": None, "lng": 1}) is None
    assert _coords({"lat": 91, "lng": 0}) is None
    assert _coords({"lat": 0, "lng": 200}) is None
    assert _coords({"lat": "x", "lng": 1}) is None


def test_static_map_url_shape():
    url = _static_map_url(10.67361, 122.94525)
    assert url.startswith("https://staticmap.openstreetmap.de/staticmap.php?")
    assert "center=10.67361,122.94525" in url
    assert "zoom=%d" % STATIC_MAP_ZOOM in url
    assert "markers=10.67361,122.94525,red-pushpin" in url
    assert "maptype=mapnik" in url
    assert "size=600x400" in url


def test_map_caption():
    assert _map_caption({"country": "China", "pref": "上海"}) == "China / 上海"
    assert _map_caption({"country": "Philippines", "pref": None}) == "Philippines"
    assert _map_caption({}) == "Location"


def _base_arcade(**kw):
    a = {
        "sid": "z195",
        "name": "Quantum SM City Bacolod",
        "lat": 10.67361,
        "lng": 122.94525,
        "country": "Philippines",
        "pref": None,
        "addr": "SM City Bacolod",
        "games": ["chunithm", "maimai_dx"],
    }
    a.update(kw)
    return a


def test_render_dual_card_with_map():
    html = render_page(_base_arcade(), None, {})
    assert 'class="card card-wide"' in html
    assert 'class="media"' in html
    assert "staticmap.openstreetmap.de" in html
    assert 'property="og:image"' in html
    # Venue/cab first, map second
    og_images = re.findall(
        r'<meta property="og:image" content="([^"]+)"', html)
    assert len(og_images) == 2
    assert "staticmap.openstreetmap.de" in og_images[1]
    assert "Philippines" in html
    assert "setTimeout" in html
    assert "2000" in html
    assert "Discordbot" in html
    assert "onerror=" in html


def test_render_no_map_without_coords():
    html = render_page(_base_arcade(lat=None, lng=None), None, {})
    assert "staticmap.openstreetmap.de" not in html
    assert 'class="card card-wide"' not in html
    og_images = re.findall(
        r'<meta property="og:image" content="([^"]+)"', html)
    assert len(og_images) == 1


def test_render_china_caption():
    html = render_page(
        _base_arcade(sid="b1", name="街机烈火", country="China", pref="上海",
                     lat=31.2311, lng=121.45086),
        {"images": [{"file": "assets/venues/cn/1.jpg"}]},
        {},
    )
    assert "China / 上海" in html
    assert "assets/venues/cn/1.jpg" in html
    assert "staticmap.openstreetmap.de" in html
