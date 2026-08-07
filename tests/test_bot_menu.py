"""Tests for the Telegram bot menu, usage store and profile/report builders."""

from __future__ import annotations

import time

import pytest

from jarvis.interfaces.bot_menu import (
    card_rows,
    channel_url,
    gate_screen,
    profile_text,
    screen_admin,
    screen_confirm,
    screen_language,
    screen_link,
    screen_main,
    screen_memory,
    screen_model,
    screen_settings,
    screen_voice,
    subscription_text,
    usage_text,
)
from jarvis.interfaces.usage import UsageStore


# -- usage store --------------------------------------------------------------


@pytest.fixture()
def usage() -> UsageStore:
    store = UsageStore(":memory:")
    yield store
    store.close()


def test_usage_records_and_aggregates(usage):
    usage.record(1, tokens=100)
    usage.record(1, tokens=50)
    usage.record(2, tokens=999)
    s = usage.stats(1)
    assert s["messages"] == 2 and s["tokens"] == 150
    assert s["messages_today"] == 2 and s["tokens_today"] == 150
    # Other users are separate.
    assert usage.stats(2)["tokens"] == 999
    assert usage.stats(3)["tokens"] == 0


def test_usage_time_windows(usage):
    usage.record(1, tokens=10)
    # Backdate one row beyond 30 days.
    usage._conn.execute("UPDATE usage SET ts = ? WHERE tokens = 10",
                        (time.time() - 40 * 86400,))
    usage._conn.commit()
    usage.record(1, tokens=7)
    s = usage.stats(1)
    assert s["tokens"] == 17          # all time
    assert s["tokens_today"] == 7     # only the fresh one
    assert s["tokens_month"] == 7


# -- menu layout --------------------------------------------------------------


def _flat(rows):
    return [data for row in rows for _, data in row]


def test_nav_row_top_level_has_back_and_close():
    from jarvis.interfaces.bot_menu import _nav
    row = _nav("en", "main")
    flat = [d for _, d in row]
    assert flat == ["m:main", "m:close"]  # Home redundant at top level


def test_nav_row_nested_has_back_home_close():
    from jarvis.interfaces.bot_menu import _nav
    row = _nav("en", "settings")
    flat = [d for _, d in row]
    assert flat == ["m:settings", "m:main", "m:close"]


def test_every_settings_submenu_offers_close():
    # Model / language / settings all carry the ❌ Close escape hatch.
    for _t, rows in (screen_settings("en", multi_model=True),
                    screen_model("en", ["claude"], ""),
                    screen_language("en", "en")):
        assert "m:close" in _flat(rows)


def test_main_menu_minimal():
    text, rows = screen_main("en")
    assert "KER" in text
    flat = _flat(rows)
    assert "m:profile" in flat and "m:usage" in flat
    assert "m:settings" in flat and "m:memory" in flat
    assert "m:help" in flat
    # Admin / billing absent by default.
    assert "m:admin" not in flat
    assert "m:plans" not in flat


def test_main_menu_full():
    _text, rows = screen_main("ru", is_admin=True, billing_on=True,
                            accounts_on=True, multi_model=True)
    flat = _flat(rows)
    for expected in ("m:subscription", "m:plans", "m:link", "m:admin"):
        assert expected in flat


def test_main_menu_shows_plan_status():
    from jarvis.billing import default_plans
    plans = default_plans()
    text, _rows = screen_main("en", billing_on=True, plan=plans["free"],
                            used_today=3)
    # Free tier badge with remaining-today counter.
    assert "Free" in text and "7/10" in text
    text_pro, _r = screen_main("en", billing_on=True, plan=plans["pro"])
    assert "unlimited" in text_pro


def test_settings_hub_and_submenus_have_back():
    # The Settings hub is minimal: category buttons, not individual toggles.
    _t, srows = screen_settings("en")
    flat = _flat(srows)
    assert "m:setai" in flat and "m:setprefs" in flat
    assert "m:main" in flat  # back button
    # Individual toggles live one level down.
    from jarvis.interfaces.bot_menu import (
        screen_settings_ai,
        screen_settings_prefs,
    )
    _t, ai = screen_settings_ai("en", multi_model=True)
    assert "m:model" in _flat(ai) and "m:byok" in _flat(ai)
    assert "m:settings" in _flat(ai)  # back to hub
    _t, prefs = screen_settings_prefs("en", proactive=False)
    assert "m:language" in _flat(prefs) and "m:proactive" in _flat(prefs)
    _t, mrows = screen_memory("en")
    assert "m:reset" in _flat(mrows) and "m:forget" in _flat(mrows)
    assert "m:main" in _flat(mrows)
    _t, mdl = screen_model("en", ["claude", "gpt"], "gpt")
    flat = _flat(mdl)
    assert "m:setmodel:claude" in flat and "m:setmodel:auto" in flat
    assert "m:settings" in flat  # back to settings
    _t, lang = screen_language("en", "ru")
    flat = _flat(lang)
    assert "m:setlang:ru" in flat and "m:setlang:en" in flat
    assert "m:settings" in flat


def test_settings_ai_hides_model_when_single():
    from jarvis.interfaces.bot_menu import screen_settings_ai
    _t, rows = screen_settings_ai("en", multi_model=False)
    assert "m:model" not in _flat(rows)
    assert "m:byok" in _flat(rows)


def test_settings_hub_shows_tools_category_only_when_available():
    _t, on = screen_settings("en", search_on=True)
    assert "m:settools" in _flat(on)
    _t2, off = screen_settings("en")
    assert "m:settools" not in _flat(off)


def test_channel_url_forms():
    assert channel_url("@jar_v1_s") == "https://t.me/jar_v1_s"
    assert channel_url("jar_v1_s") == "https://t.me/jar_v1_s"
    assert channel_url("https://t.me/x") == "https://t.me/x"


def test_gate_screen_has_subscribe_and_check():
    text, rows = gate_screen("ru", "@jar_v1_s")
    flat = _flat(rows)
    assert "https://t.me/jar_v1_s" in flat   # subscribe link button
    assert "m:checksub" in flat               # check button
    assert "Подпишитесь" in text


def test_main_menu_voice_and_channel_buttons():
    _t, rows = screen_main("en", voice_on=True, channel="@jar_v1_s")
    flat = _flat(rows)
    assert "m:voice" in flat
    assert "https://t.me/jar_v1_s" in flat    # channel link button
    # Without voice/channel they are absent.
    _t2, rows2 = screen_main("en")
    assert "m:voice" not in _flat(rows2)


def test_screen_voice_has_back():
    text, rows = screen_voice("en")
    assert "Voice" in text
    assert "m:main" in _flat(rows)


def test_memory_buttons_lead_to_confirmation():
    # The memory screen must route to the *confirm* step, not wipe directly.
    _t, rows = screen_memory("en")
    flat = _flat(rows)
    assert "m:reset" in flat and "m:forget" in flat


@pytest.mark.parametrize("kind,expect_body", [
    ("reset", "clears"),
    ("forget", "wipes"),
])
def test_screen_confirm(kind, expect_body):
    text, rows = screen_confirm("en", kind)
    flat = _flat(rows)
    assert "Are you sure?" in text and expect_body in text
    # A confirm-yes button that performs the action, and a Back to memory.
    assert f"m:{kind}_do" in flat
    assert "m:memory" in flat


def test_screen_admin_toggles_sales_with_billing():
    _t, rows = screen_admin("en", billing_on=True)
    flat = _flat(rows)
    assert "m:adminpanel" in flat and "m:adminsales" in flat
    assert "m:main" in flat
    _t2, rows2 = screen_admin("en", billing_on=False)
    flat2 = _flat(rows2)
    assert "m:adminpanel" in flat2 and "m:adminsales" not in flat2


def test_card_rows_have_refresh_and_back():
    rows = card_rows("en", "profile")
    flat = _flat(rows)
    assert "m:profile" in flat   # refresh re-opens the same screen
    assert "m:main" in flat      # back


# -- text builders ------------------------------------------------------------


def test_profile_text_contains_fields():
    stats = {"messages": 12, "tokens": 34567}
    text = profile_text(
        "en", telegram_id=42, name="Tony", language="en", model="claude",
        account="tony", telegram_verified=True, stats=stats)
    assert "42" in text and "Tony" in text and "tony" in text
    assert "Claude" in text  # model label
    assert "34 567" in text  # thousands formatted with a space


def test_profile_text_no_account():
    stats = {"messages": 0, "tokens": 0}
    text = profile_text(
        "ru", telegram_id=1, name="X", language="ru", model="",
        account=None, telegram_verified=False, stats=stats)
    assert "не привязан" in text
    assert "Auto" in text


def test_usage_text():
    stats = {"messages": 5, "tokens": 1000, "messages_today": 2,
            "tokens_today": 400, "messages_month": 5, "tokens_month": 1000}
    text = usage_text("en", stats)
    assert "Token report" in text and "400" in text and "1 000" in text


def test_subscription_text_states():
    class Lic:
        def __init__(self, plan, expires, revoked=False):
            self.plan = plan
            self.expires_at = expires
            self._revoked = revoked

        def is_valid(self, *, now):
            return not self._revoked and (self.expires_at is None
                                        or self.expires_at > now)

    now = time.time()
    assert "license yet" in subscription_text("en", account=None, licenses=[],
                                            now=now).lower()
    active = subscription_text("en", account="tony",
                            licenses=[Lic("pro", now + 10 * 86400)], now=now)
    assert "pro" in active and "days left" in active
    perpetual = subscription_text("en", account="tony",
                                licenses=[Lic("std", None)], now=now)
    assert "Lifetime" in perpetual
    inactive = subscription_text("en", account="tony",
                                licenses=[Lic("std", now - 1)], now=now)
    assert "No active" in inactive


# -- screen_link: app login + password-setting entry points -----------------


def test_screen_link_hides_app_login_when_accounts_disabled():
    _text, rows = screen_link("en", app_login=False)
    flat = _flat(rows)
    assert "m:appcode" not in flat
    assert "m:setpass" not in flat


def test_screen_link_offers_both_code_and_password_when_enabled():
    _text, rows = screen_link("en", app_login=True)
    flat = _flat(rows)
    assert "m:appcode" in flat
    assert "m:setpass" in flat
