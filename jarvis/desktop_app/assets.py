"""
Where the desktop app finds the interface it renders.

The same lookup has to work twice over: from a checkout, where the files sit in
the source tree, and from a packaged build, where PyInstaller unpacks them into
a temporary directory. Both are tried here so the rest of the app can just ask
for a file by name.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: The desktop product's own interface files. The browser dashboard is a
#: separate product and is not listed here on purpose.
DECK = "desktop.html"
LOGIN = "desktop_login.html"


def icon_path(name: str = "ker.ico") -> Path | None:
    """Locate the app icon, in a checkout or inside a frozen build."""
    candidates: list[Path] = []
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(Path(base) / "jarvis" / "desktop_app" / "assets" / name)
    candidates.append(Path(__file__).resolve().parent / "assets" / name)
    for path in candidates:
        if path.is_file():
            return path
    return None


def interface_path(name: str) -> Path | None:
    """Locate an interface file, in a checkout or inside a frozen build."""
    candidates: list[Path] = []
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(Path(base) / "jarvis" / "api" / "static" / name)
    candidates.append(
        Path(__file__).resolve().parents[1] / "api" / "static" / name)
    for path in candidates:
        if path.is_file():
            return path
    return None


def interface_html(name: str) -> str:
    """Read an interface file, or a plain message if the build lacks it."""
    path = interface_path(name)
    if path is None:
        return ("<h1 style='color:#eee;font-family:sans-serif'>"
                f"Interface file missing from this build: {name}</h1>")
    return path.read_text(encoding="utf-8")


def login_strings(config) -> dict:
    """Everything the sign-in page needs to render itself for this user."""
    from jarvis import __version__
    from jarvis.desktop_app.strings import tr
    loc = config.language
    return {
        "brand": config.assistant_name or "KER",
        "title": tr("login_title", loc),
        "subtitle": tr("login_subtitle", loc),
        "tagline": tr("login_tagline", loc),
        "tab_account": tr("login_tab_account", loc),
        "tab_telegram": tr("login_tab_telegram", loc),
        "tab_register": tr("login_tab_register", loc),
        "hint_account": tr("login_remote_hint", loc),
        "hint_telegram": tr("login_hint_telegram", loc),
        "hint_register": tr("login_hint_register", loc),
        "server": tr("server_url", loc),
        "username": tr("username", loc),
        "password": tr("password", loc),
        "password_repeat": tr("password_repeat", loc),
        "password_mismatch": tr("password_mismatch", loc),
        "code": tr("login_code", loc),
        "cta_account": tr("sign_in", loc),
        "cta_telegram": tr("login_cta_telegram", loc),
        "cta_register": tr("login_cta_register", loc),
        "failed": tr("login_failed", loc, error=""),
        "no_bridge": tr("login_no_bridge", loc),
        "foot_note": tr("login_foot", loc),
        # The page asks the server what it is and picks one of these to show,
        # so "invalid code" is never the only thing a person is told. The two
        # templates keep their {placeholders} — the page fills them in.
        "probe_checking": tr("probe_checking", loc),
        "probe_ready": tr("probe_ready", loc),
        "probe_no_accounts": tr("probe_no_accounts", loc),
        "probe_unreachable": tr("probe_unreachable", loc),
        "probe_no_signup": tr("probe_no_signup", loc),
        "version_line": f"KER {__version__}",
        "server_url": config.server_url or "",
        "username_value": config.username or "",
        "theme": config.theme,
    }


def login_page(config) -> str:
    """The sign-in page with this app's text, defaults and palette poured in."""
    import json
    html = interface_html(LOGIN)
    return html.replace("__STRINGS__", json.dumps(login_strings(config),
                                                  ensure_ascii=False))
