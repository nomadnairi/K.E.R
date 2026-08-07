"""Tests for jarvis.desktop_app.notifications.NotificationCenter.

Этап 2 / Фаза B2 — the single channel that replaces the ad hoc mix of
runJavaScript()/QMessageBox/direct-widget-mutation calls that used to push
things at the user, and that fixes the boot bug where _on_proactive crashed
silently in the WebView build (see app.py's _on_proactive/_push_notification
for the Qt-side half, not exercised here — no GUI in this test suite, same
as the rest of tests/test_desktop_app.py).
"""

from __future__ import annotations

import json

from jarvis.desktop_app.notifications import Notification, NotificationCenter


def test_starts_empty_when_no_file_exists(tmp_path):
    nc = NotificationCenter(tmp_path / "notifications.json")
    assert nc.list() == []
    assert nc.unread_count() == 0


def test_add_is_unread_and_listed_most_recent_first(tmp_path):
    nc = NotificationCenter(tmp_path / "notifications.json")
    nc.add("first")
    nc.add("second", kind="proactive")
    out = nc.list()
    assert [n["text"] for n in out] == ["second", "first"]
    assert out[0]["kind"] == "proactive"
    assert out[0]["read"] is False
    assert nc.unread_count() == 2


def test_mark_all_read_clears_the_unread_count(tmp_path):
    nc = NotificationCenter(tmp_path / "notifications.json")
    nc.add("a")
    nc.add("b")
    nc.mark_all_read()
    assert nc.unread_count() == 0
    assert all(n["read"] for n in nc.list())


def test_persists_across_instances(tmp_path):
    path = tmp_path / "notifications.json"
    NotificationCenter(path).add("hello")
    reloaded = NotificationCenter(path)
    assert [n["text"] for n in reloaded.list()] == ["hello"]


def test_rolls_over_past_max_kept(tmp_path):
    nc = NotificationCenter(tmp_path / "notifications.json")
    nc.MAX_KEPT = 5
    for i in range(8):
        nc.add(f"note-{i}")
    kept = [n["text"] for n in nc.list(limit=100)]
    assert len(kept) == 5
    assert kept[0] == "note-7"  # most recent first
    assert "note-0" not in kept  # the oldest were dropped


def test_a_corrupt_file_is_treated_as_empty_not_fatal(tmp_path):
    path = tmp_path / "notifications.json"
    path.write_text("{not json", encoding="utf-8")
    nc = NotificationCenter(path)
    assert nc.list() == []
    nc.add("still works")
    assert [n["text"] for n in nc.list()] == ["still works"]


def test_a_malformed_row_in_an_otherwise_valid_file_is_skipped(tmp_path):
    path = tmp_path / "notifications.json"
    path.write_text(json.dumps([
        {"text": "good"},
        {"no_text_field": True},
        "not even a dict",
    ]), encoding="utf-8")
    nc = NotificationCenter(path)
    assert [n["text"] for n in nc.list()] == ["good"]


def test_default_path_lives_next_to_desktop_json(tmp_path):
    assert NotificationCenter.default_path(tmp_path) == tmp_path / "notifications.json"


def test_notification_as_dict_round_trips_the_fields():
    note = Notification(text="hi", kind="update", read=True)
    d = note.as_dict()
    assert d["text"] == "hi"
    assert d["kind"] == "update"
    assert d["read"] is True
    assert isinstance(d["created_at"], float)
