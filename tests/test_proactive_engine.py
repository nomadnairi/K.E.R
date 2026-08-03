"""Tests for the proactive engine's per-tick orchestration."""

from __future__ import annotations

import pytest

from jarvis.interfaces.user_prefs import UserPreferences
from jarvis.proactive.engine import ProactiveEngine
from jarvis.proactive.models import Signal
from jarvis.proactive.sensors.base import ProactiveSensor
from tests.conftest import FakeProvider, build_engine


class _StubSensor(ProactiveSensor):
    """A test-only sensor whose output the test fully controls."""

    name = "stub"

    def __init__(self, signal: Signal | None) -> None:
        self.signal = signal
        self.calls = 0

    async def check(self, *, user_id: str, scratch: dict) -> Signal | None:
        self.calls += 1
        return self.signal


class _BoomSensor(ProactiveSensor):
    name = "boom"

    async def check(self, *, user_id: str, scratch: dict) -> Signal | None:
        raise RuntimeError("sensor bug")


def _prefs_with_one_opted_in_user(user_id: str = "1") -> UserPreferences:
    prefs = UserPreferences(":memory:")
    prefs.touch(user_id, "chat-1")
    prefs.set_proactive(user_id, True)
    return prefs


class _Recorder:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def __call__(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.mark.asyncio
async def test_master_switch_off_sends_nothing(settings):
    settings.proactive_sensors_enabled = False
    engine = build_engine(settings, FakeProvider(default_reply="Hello."))
    prefs = _prefs_with_one_opted_in_user()
    sensor = _StubSensor(Signal(sensor="stub", summary="something"))
    pe = ProactiveEngine(engine, prefs, settings, sensors=[sensor])

    send = _Recorder()
    sent = await pe.tick(send)

    assert sent == 0
    assert send.sent == []
    assert sensor.calls == 0  # short-circuited before touching any sensor


@pytest.mark.asyncio
async def test_a_real_signal_and_decision_sends_a_message(settings):
    settings.proactive_sensors_enabled = True
    engine = build_engine(settings, FakeProvider(default_reply="Sir, heads up."))
    prefs = _prefs_with_one_opted_in_user()
    sensor = _StubSensor(Signal(sensor="stub", summary="CPU is high"))
    pe = ProactiveEngine(engine, prefs, settings, sensors=[sensor])

    send = _Recorder()
    sent = await pe.tick(send)

    assert sent == 1
    assert send.sent == [("chat-1", "Sir, heads up.")]
    # So a later reply referencing it has it in context.
    assert engine.session("1").conversation.messages[-1].content == "Sir, heads up."


@pytest.mark.asyncio
async def test_uses_a_custom_session_id_mapping(settings):
    # e.g. Telegram's session_id_for(uid) == f"tg-{uid}", vs. the raw prefs
    # user_id -- the engine must record history under the REAL session id.
    settings.proactive_sensors_enabled = True
    engine = build_engine(settings, FakeProvider(default_reply="Sir, heads up."))
    prefs = _prefs_with_one_opted_in_user("1")
    sensor = _StubSensor(Signal(sensor="stub", summary="CPU is high"))
    pe = ProactiveEngine(engine, prefs, settings, sensors=[sensor],
                        session_id_for=lambda uid: f"tg-{uid}")

    await pe.tick(_Recorder())
    assert engine.session("tg-1").conversation.messages[-1].content == "Sir, heads up."
    assert len(engine.session("1").conversation) == 0


@pytest.mark.asyncio
async def test_no_signal_sends_nothing(settings):
    settings.proactive_sensors_enabled = True
    engine = build_engine(settings, FakeProvider(default_reply="Sir, heads up."))
    prefs = _prefs_with_one_opted_in_user()
    sensor = _StubSensor(None)
    pe = ProactiveEngine(engine, prefs, settings, sensors=[sensor])

    sent = await pe.tick(_Recorder())
    assert sent == 0


@pytest.mark.asyncio
async def test_nothing_decision_sends_nothing(settings):
    settings.proactive_sensors_enabled = True
    engine = build_engine(settings, FakeProvider(default_reply="NOTHING"))
    prefs = _prefs_with_one_opted_in_user()
    sensor = _StubSensor(Signal(sensor="stub", summary="minor thing"))
    pe = ProactiveEngine(engine, prefs, settings, sensors=[sensor])

    send = _Recorder()
    sent = await pe.tick(send)
    assert sent == 0
    assert send.sent == []


@pytest.mark.asyncio
async def test_cooldown_suppresses_a_second_message(settings):
    settings.proactive_sensors_enabled = True
    settings.proactive_cooldown_seconds = 3600
    engine = build_engine(settings, FakeProvider(default_reply="Heads up."))
    prefs = _prefs_with_one_opted_in_user()
    sensor = _StubSensor(Signal(sensor="stub", summary="CPU is high"))
    pe = ProactiveEngine(engine, prefs, settings, sensors=[sensor])

    send = _Recorder()
    assert await pe.tick(send) == 1
    # Sensors aren't even polled again while on cooldown.
    assert await pe.tick(send) == 0
    assert sensor.calls == 1
    assert len(send.sent) == 1


@pytest.mark.asyncio
async def test_only_opted_in_users_are_checked(settings):
    settings.proactive_sensors_enabled = True
    engine = build_engine(settings, FakeProvider(default_reply="Heads up."))
    prefs = UserPreferences(":memory:")
    prefs.touch("1", "chat-1")
    # Never opted in.
    sensor = _StubSensor(Signal(sensor="stub", summary="CPU is high"))
    pe = ProactiveEngine(engine, prefs, settings, sensors=[sensor])

    sent = await pe.tick(_Recorder())
    assert sent == 0
    assert sensor.calls == 0


@pytest.mark.asyncio
async def test_a_failing_sensor_does_not_sink_the_tick(settings):
    settings.proactive_sensors_enabled = True
    engine = build_engine(settings, FakeProvider(default_reply="Heads up."))
    prefs = _prefs_with_one_opted_in_user()
    good = _StubSensor(Signal(sensor="stub", summary="CPU is high"))
    pe = ProactiveEngine(engine, prefs, settings, sensors=[_BoomSensor(), good])

    send = _Recorder()
    sent = await pe.tick(send)
    assert sent == 1
    assert send.sent == [("chat-1", "Heads up.")]


@pytest.mark.asyncio
async def test_a_failing_send_does_not_mark_the_cooldown(settings):
    settings.proactive_sensors_enabled = True
    engine = build_engine(settings, FakeProvider(default_reply="Heads up."))
    prefs = _prefs_with_one_opted_in_user()
    sensor = _StubSensor(Signal(sensor="stub", summary="CPU is high"))
    pe = ProactiveEngine(engine, prefs, settings, sensors=[sensor])

    async def failing_send(chat_id: str, text: str) -> None:
        raise RuntimeError("telegram is down")

    sent = await pe.tick(failing_send)
    assert sent == 0
    # Cooldown wasn't recorded, so a retry next tick is still possible.
    assert pe._last_sent == {}
