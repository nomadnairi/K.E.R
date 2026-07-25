"""The desktop app and the browser dashboard are separate products.

They used to share one HTML file, which meant neither could change without
dragging the other along. These tests pin the split so it cannot regress.
"""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "jarvis" / "api" / "static"
DESKTOP = STATIC / "desktop.html"
DASHBOARD = STATIC / "dashboard.html"


def test_both_interfaces_exist():
    assert DESKTOP.is_file(), "the desktop app needs its own interface file"
    assert DASHBOARD.is_file(), "the browser dashboard needs its own file"


def test_desktop_app_loads_the_desktop_interface():
    """The exe must read desktop.html — never the browser dashboard."""
    source = (Path(__file__).resolve().parents[1] / "jarvis" / "desktop_app"
            / "app.py").read_text(encoding="utf-8")
    deck = source.split("def _deck_html")[1].split("def ")[0]
    assert '"desktop.html"' in deck
    assert "dashboard.html" not in deck


def test_api_serves_the_browser_dashboard():
    """/app is the web product, so it must serve dashboard.html."""
    source = (Path(__file__).resolve().parents[1] / "jarvis" / "api"
            / "app.py").read_text(encoding="utf-8")
    assert '"dashboard.html"' in source


def test_desktop_interface_is_self_contained():
    """It is injected with setHtml(), so it cannot reference external files."""
    html = DESKTOP.read_text(encoding="utf-8")
    for tag in ('<link rel="stylesheet"', "<script src="):
        assert tag not in html, f"{tag} would not resolve inside the app"


def test_packaging_ships_the_desktop_interface():
    spec = (Path(__file__).resolve().parents[1] / "deploy" / "desktop"
            / "jarvis-desktop.spec").read_text(encoding="utf-8")
    assert "static/desktop.html" in spec
