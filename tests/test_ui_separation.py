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


# -- the way in --------------------------------------------------------------

def test_the_sign_in_screen_offers_every_way_in():
    """Account, bot code and registration — each with its own submit."""
    html = LOGIN.read_text(encoding="utf-8")
    for pane in ("pane-account", "pane-telegram", "pane-register"):
        assert f'id="{pane}"' in html
    for action in ("login.password", "login.telegram", "login.register"):
        assert action in html


def test_the_server_address_is_asked_for_once():
    """Two address fields invited typing two different servers."""
    html = LOGIN.read_text(encoding="utf-8")
    assert html.count('id="server"') == 1
    assert 'id="server2"' not in html


def test_the_screen_probes_the_server_before_offering_a_login():
    """So 'accounts are off here' is said instead of 'invalid code'."""
    html = LOGIN.read_text(encoding="utf-8")
    assert "server.probe" in html
    assert 'id="probe"' in html


def test_the_register_tab_stays_hidden_until_the_server_allows_signup():
    html = LOGIN.read_text(encoding="utf-8")
    tab = [line for line in html.splitlines() if 'id="tab-register"' in line][0]
    assert "hidden" in tab, "an open form on a closed server is a dead end"
    assert '$("tab-register").hidden = !res.signup' in html


def test_every_string_the_sign_in_screen_asks_for_is_translated():
    """A missing key would render as the key itself, in every language."""
    from jarvis.desktop_app.assets import login_strings
    from jarvis.desktop_app.config import AppConfig
    from jarvis.desktop_app.strings import STRINGS
    skip = {"version_line", "server_url", "username_value", "theme", "brand"}
    for locale in STRINGS:
        strings = login_strings(AppConfig(language=locale))
        for key, value in strings.items():
            if key in skip:
                continue
            assert value, f"{locale}: {key} is empty"
            assert not value.startswith("login_"), f"{locale}: {key} untranslated"
            assert not value.startswith("probe_"), f"{locale}: {key} untranslated"


def test_the_telegram_hint_explains_that_the_code_makes_an_account():
    """People were reading the code as a link-only step and getting stuck."""
    from jarvis.desktop_app.strings import tr
    assert "аккаунт" in tr("login_hint_telegram", "ru").lower()
    assert "account" in tr("login_hint_telegram", "en").lower()


# -- the API-keys panel ------------------------------------------------------

def test_the_deck_has_an_api_keys_screen_gated_by_the_entitlement():
    html = DESKTOP.read_text(encoding="utf-8")
    assert 'id="view-apikeys"' in html
    assert 'data-view="apikeys"' in html
    # Gated on api_access, so Free sees it locked, not open.
    assert '"api_access"' in html and 'apikeys:"api_access"' in html
    # Every key action is wired to the native bridge.
    for action in ("apikeys.list", "apikeys.create", "apikeys.revoke"):
        assert action in html


def test_the_api_keys_screen_shows_the_secret_once():
    """The one-time reveal must exist; the list only ever shows the prefix."""
    html = DESKTOP.read_text(encoding="utf-8")
    assert "JUST_MADE" in html
    assert "copyKey" in html


def test_the_api_keys_screen_shows_todays_usage():
    """A usage card with a spend bar, fed by the proxy's meter."""
    html = DESKTOP.read_text(encoding="utf-8")
    assert "apikeys.usage" in html
    assert "usageCard" in html
    assert "Использование сегодня" in html


# -- the Device Manager panel (Этап 2 / Фаза A4 backend, B4 UI) -------------


def test_the_deck_has_a_devices_screen_between_plan_and_apikeys():
    html = DESKTOP.read_text(encoding="utf-8")
    assert 'id="view-devices"' in html
    assert 'data-view="devices"' in html
    # Same nav-item/section/load-function convention as every other screen —
    # not a bespoke pattern (see desktop.html's own audit-derived docstring).
    for action in ("devices.list", "devices.revoke"):
        assert action in html
    assert "loadDevices" in html and "renderDevices" in html
    # Placed between "plan" and "apikeys" in the rail, as the plan calls for.
    plan_idx = html.index('data-view="plan"')
    devices_idx = html.index('data-view="devices"')
    apikeys_idx = html.index('data-view="apikeys"')
    assert plan_idx < devices_idx < apikeys_idx


def test_devices_screen_is_not_gated_by_a_paid_tier():
    """Session management is basic account security, not a paid feature —
    unlike apikeys, it must not appear in the entitlement-lock map."""
    html = DESKTOP.read_text(encoding="utf-8")
    lock_map = html.split("PLAN_FEATURE_FOR_VIEW")[1].split("}")[0]
    assert "devices:" not in lock_map


def test_devices_screen_marks_the_current_device_and_confirms_before_self_logout():
    """Revoking your own live session needs an explicit yes — the same
    confirm() guard the deck already uses for forgetAll()/settings.reset."""
    html = DESKTOP.read_text(encoding="utf-8")
    assert "current_device_id" in html
    revoke_fn = html.split("async function revokeDevice")[1].split("\n\n")[0]
    assert "confirm(" in revoke_fn
    assert "isCurrent" in revoke_fn


# -- the profile screen: identity + password change (Этап 2 / Фаза B5) ------


def test_the_profile_screen_shows_real_identity_from_the_plan():
    """It used to be a static "Sir / Pro / Владелец" card — identity now
    comes from PLAN (plan.get), the same source of truth the Plan screen
    already uses, not invented markup."""
    html = DESKTOP.read_text(encoding="utf-8")
    assert 'id="view-profile"' in html
    assert "loadProfile" in html and "renderProfile" in html
    render_fn = html.split("function renderProfile")[1].split("function ")[0]
    assert "PLAN.username" in render_fn
    assert "PLAN.owner" in render_fn


def test_the_profile_screen_has_a_working_password_change_form():
    html = DESKTOP.read_text(encoding="utf-8")
    assert "account.change_password" in html
    assert 'id="pwCurrent"' in html and 'id="pwNew"' in html and 'id="pwNew2"' in html
    change_fn = html.split("async function changePassword")[1].split("\n\n")[0]
    # New password confirmation is checked client-side before ever calling
    # the bridge — the server also enforces it, but failing fast is kinder.
    assert "n1!==n2" in change_fn or "n1 !== n2" in change_fn


def test_the_password_form_is_hidden_without_a_server_account():
    """Open/shared-key mode (no accounts) has no password to change."""
    html = DESKTOP.read_text(encoding="utf-8")
    render_fn = html.split("function renderProfile")[1].split("function ")[0]
    assert "canChangePassword" in render_fn
    assert "PLAN.username" in render_fn.split("canChangePassword")[1].split(";")[0]


# -- clickable chat history (Этап 2 / Фаза B6) -------------------------------


def test_history_items_carry_their_session_id():
    """groupByDay used to drop session_id on the floor — a history entry is
    a chat with a different session_id, so the id has to survive into what
    renderHist draws."""
    html = DESKTOP.read_text(encoding="utf-8")
    group_fn = html.split("function groupByDay")[1].split("function ")[0]
    assert "r.session_id" in group_fn


def test_history_items_are_clickable_and_open_the_session():
    html = DESKTOP.read_text(encoding="utf-8")
    assert "openHistorySession" in html
    render_fn = html.split("function renderHist")[1].split("function ")[0]
    assert "onclick=" in render_fn and "openHistorySession" in render_fn


def test_opening_history_fetches_that_sessions_messages():
    html = DESKTOP.read_text(encoding="utf-8")
    open_fn = html.split("async function openHistorySession")[1].split("\n  }")[0]
    assert "/dashboard/sessions/" in open_fn and "/messages" in open_fn


def test_reopening_a_session_redirects_new_messages_to_it():
    """The composer must stop talking to the fixed 'dashboard' session once
    a real history entry is open — otherwise 'reopening' would only be a
    read-only history view, not the chat continuing where it left off."""
    html = DESKTOP.read_text(encoding="utf-8")
    send_fn = html.split("async function sendMsg")[1].split("function ")[0]
    assert "ACTIVE_SESSION" in send_fn
    assert 'session_id:"dashboard"' not in send_fn


def test_new_chat_returns_to_the_default_session():
    """Otherwise a fresh 'Новый чат' after browsing history would keep
    appending to whatever old session was last opened."""
    html = DESKTOP.read_text(encoding="utf-8")
    new_chat_fn = html.split("function newChat")[1].split("\n  }")[0]
    assert "DEFAULT_SESSION" in new_chat_fn
