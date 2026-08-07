"""Tests for jarvis.desktop_app.status.AppStatus (Этап 2 / Фаза B3).

Qt-free by design (no GUI in this test suite, same as the rest of
tests/test_desktop_app.py) — the QSplashScreen wiring in app.py's run_app()
that subscribes to this is not exercised here.
"""

from __future__ import annotations

from jarvis.desktop_app.status import STAGE_TEXT, AppStatus, Stage


def test_starts_at_connecting():
    status = AppStatus()
    assert status.stage is Stage.CONNECTING


def test_set_updates_the_current_stage():
    status = AppStatus()
    status.set(Stage.READY)
    assert status.stage is Stage.READY


def test_listeners_receive_the_stage_and_its_text():
    status = AppStatus()
    seen: list[tuple[Stage, str]] = []
    status.on_change(lambda stage, text: seen.append((stage, text)))

    status.set(Stage.STARTING_ENGINE)
    assert seen == [(Stage.STARTING_ENGINE, STAGE_TEXT[Stage.STARTING_ENGINE])]


def test_every_stage_has_non_empty_text():
    for stage in Stage:
        assert STAGE_TEXT[stage]


def test_multiple_listeners_all_fire_in_order():
    status = AppStatus()
    calls: list[str] = []
    status.on_change(lambda stage, text: calls.append("a"))
    status.on_change(lambda stage, text: calls.append("b"))
    status.set(Stage.SYNCING)
    assert calls == ["a", "b"]


def test_registering_a_listener_does_not_replay_the_current_stage():
    status = AppStatus()
    status.set(Stage.STARTING_ENGINE)
    seen: list[Stage] = []
    status.on_change(lambda stage, text: seen.append(stage))
    assert seen == []  # no replay — only future transitions


def test_setting_the_same_stage_again_still_notifies():
    """A repeat matters here (e.g. re-affirming READY after a splash
    reappears) — this is not an edge-triggered signal."""
    status = AppStatus()
    seen: list[Stage] = []
    status.on_change(lambda stage, text: seen.append(stage))
    status.set(Stage.READY)
    status.set(Stage.READY)
    assert seen == [Stage.READY, Stage.READY]
