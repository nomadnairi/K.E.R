"""Tests for the reminder parser, store, proactive prefs and screens."""

from __future__ import annotations

from datetime import datetime, timedelta

from jarvis.interfaces.bot_menu import screen_reminders
from jarvis.interfaces.reminders import (
    ReminderStore,
    is_reminder,
    parse_reminder,
)
from jarvis.interfaces.user_prefs import UserPreferences

NOW = datetime(2026, 7, 21, 12, 0, 0)


def _flat(rows):
    return [data for row in rows for _, data in row]


# -- parser -------------------------------------------------------------------


def test_is_reminder_detects_triggers():
    assert is_reminder("напомни через 5 минут пить воду")
    assert is_reminder("remind me tomorrow at 9 call mom")
    assert not is_reminder("какая погода завтра?")


def test_relative_minutes_and_hours():
    due, body = parse_reminder("напомни через 10 минут выпить воды", NOW)
    assert due == NOW + timedelta(minutes=10)
    assert body == "выпить воды"
    due2, _ = parse_reminder("remind in 2 hours stretch", NOW)
    assert due2 == NOW + timedelta(hours=2)


def test_absolute_tomorrow_and_today_rollover():
    due, body = parse_reminder("напомни завтра в 9 позвонить маме", NOW)
    assert due == datetime(2026, 7, 22, 9, 0)
    assert body == "позвонить маме"
    # 08:00 is already past 12:00 → rolls over to tomorrow.
    due2, _ = parse_reminder("напомни в 8:00 зарядка", NOW)
    assert due2 == datetime(2026, 7, 22, 8, 0)
    # 18:30 today is still ahead.
    due3, _ = parse_reminder("remind at 18:30 dinner", NOW)
    assert due3 == datetime(2026, 7, 21, 18, 30)


def test_unparseable_returns_none():
    assert parse_reminder("напомни когда-нибудь потом", NOW) is None
    assert parse_reminder("just a normal message", NOW) is None


# -- store --------------------------------------------------------------------


def test_store_add_due_and_cancel():
    store = ReminderStore(":memory:")
    t0 = 1_000_000.0
    rid = store.add(user_id=1, chat_id=100, text="ping", due_ts=t0 + 60)
    # Not due yet.
    assert store.due(now=t0) == []
    # Due after the time passes.
    due = store.due(now=t0 + 61)
    assert len(due) == 1 and due[0]["text"] == "ping"
    # Active list shows the upcoming one.
    assert len(store.list_active(1, now=t0)) == 1
    # Cancelling removes it from due/active.
    assert store.cancel(rid, user_id=1) is True
    assert store.due(now=t0 + 61) == []
    assert store.cancel(rid, user_id=1) is False  # already cancelled
    store.close()


def test_mark_fired_hides_reminder():
    store = ReminderStore(":memory:")
    rid = store.add(1, 100, "x", due_ts=0)
    assert len(store.due(now=10)) == 1
    store.mark_fired(rid)
    assert store.due(now=10) == []
    store.close()


# -- prefs --------------------------------------------------------------------


def test_proactive_prefs_and_touch():
    prefs = UserPreferences(":memory:")
    assert prefs.get_proactive(1) is False
    prefs.set_proactive(1, True)
    assert prefs.get_proactive(1) is True
    prefs.touch(1, chat_id=555)
    assert prefs.get_chat_id(1) == "555"
    rows = prefs.list_proactive()
    assert any(r["user_id"] == "1" and r["chat_id"] == "555" for r in rows)
    prefs.close()


# -- screens ------------------------------------------------------------------


def test_screen_reminders_lists_and_cancels():
    empty_text, empty_rows = screen_reminders("en", [])
    assert "No active" in empty_text
    text, rows = screen_reminders("en", [(7, "22.07 09:00 — call mom")])
    assert "call mom" in text
    assert "m:remcancel:7" in _flat(rows)


def test_settings_shows_proactive_toggle():
    # Proactive lives in the Preferences sub-hub now.
    from jarvis.interfaces.bot_menu import screen_settings_prefs
    _t, rows = screen_settings_prefs("en", proactive=True)
    assert "m:proactive" in _flat(rows)
