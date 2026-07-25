"""The desktop app and the browser dashboard are separate products.

They used to share one HTML file, which meant neither could change without
dragging the other along. These tests pin the split so it cannot regress.
"""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "jarvis" / "api" / "static"
DESKTOP = STATIC / "desktop.html"
LOGIN = STATIC / "desktop_login.html"
DASHBOARD = STATIC / "dashboard.html"
SPEC = (Path(__file__).resolve().parents[1] / "deploy" / "desktop"
        / "jarvis-desktop.spec")


def test_both_interfaces_exist():
    assert DESKTOP.is_file(), "the desktop app needs its own interface file"
    assert LOGIN.is_file(), "the desktop app needs its own sign-in screen"
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
    """Served from the app's own scheme, it cannot reach external files."""
    for path in (DESKTOP, LOGIN):
        html = path.read_text(encoding="utf-8")
        for tag in ('<link rel="stylesheet"', "<script src="):
            assert tag not in html, f"{tag} would not resolve inside the app"


def test_the_sign_in_screen_gets_its_text_from_the_app():
    """The app pours in the user's language, so the page keeps a slot for it."""
    html = LOGIN.read_text(encoding="utf-8")
    assert "__STRINGS__" in html
    from jarvis.desktop_app.assets import login_page
    from jarvis.desktop_app.config import AppConfig
    page = login_page(AppConfig(language="ru"))
    assert "__STRINGS__" not in page
    assert "Вход в KER" in page


def test_packaging_ships_the_desktop_interface():
    spec = SPEC.read_text(encoding="utf-8")
    assert "static/desktop.html" in spec
    assert "static/desktop_login.html" in spec


def test_packaging_keeps_the_web_view():
    """The interface is a page: excluding WebEngine would gut the built app."""
    spec = SPEC.read_text(encoding="utf-8")
    excludes = spec.split("excludes=[")[1].split("]")[0]
    for module in ("PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
                   "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtWebChannel"):
        # Quoted, so excluding QtQuick3D doesn't read as excluding QtQuick.
        assert f'"{module}"' not in excludes, f"{module} must stay in the bundle"
