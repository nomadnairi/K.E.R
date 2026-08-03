"""Tests for the desktop app's (local-mode) proactive-engine wiring.

The Qt signal/slot hop itself isn't exercised here (no GUI in this test
suite) -- what's tested is everything up to that hop: LocalProactivePrefs,
the AppConfig mapping, and running a real ProactiveEngine on a real
EngineThread's loop (the exact mechanism app.py's _start_proactive uses).
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from jarvis.config.settings import Settings
from jarvis.desktop_app.config import AppConfig
from jarvis.desktop_app.engine_thread import EngineThread
from jarvis.desktop_app.proactive_prefs import LOCAL_USER_ID, LocalProactivePrefs
from jarvis.llm.client import LLMClient
from jarvis.proactive.engine import ProactiveEngine
from jarvis.proactive.models import Signal
from jarvis.proactive.sensors.base import ProactiveSensor
from tests.conftest import FakeProvider


# -- LocalProactivePrefs -----------------------------------------------------


def test_off_by_default_reports_no_opted_in_users():
    prefs = LocalProactivePrefs(AppConfig(proactive_enabled=False))
    assert prefs.list_proactive() == []


def test_on_reports_the_one_local_user():
    config = AppConfig(proactive_enabled=True, language="ru")
    prefs = LocalProactivePrefs(config)
    rows = prefs.list_proactive()
    assert len(rows) == 1
    assert rows[0]["user_id"] == LOCAL_USER_ID
    assert rows[0]["chat_id"] == LOCAL_USER_ID
    assert rows[0]["language"] == "ru"


def test_assistant_name_falls_back_to_none():
    prefs = LocalProactivePrefs(AppConfig(assistant_name=""))
    assert prefs.get_assistant_name(LOCAL_USER_ID) is None
    prefs2 = LocalProactivePrefs(AppConfig(assistant_name="Jarvis"))
    assert prefs2.get_assistant_name(LOCAL_USER_ID) == "Jarvis"


# -- AppConfig mapping --------------------------------------------------------


def test_proactive_enabled_maps_to_settings():
    overrides = AppConfig(proactive_enabled=True).to_settings_overrides()
    assert overrides["proactive_sensors_enabled"] is True
    overrides_off = AppConfig(proactive_enabled=False).to_settings_overrides()
    assert overrides_off["proactive_sensors_enabled"] is False


# -- end-to-end on a real EngineThread loop -----------------------------------


class _StubSensor(ProactiveSensor):
    name = "stub"

    async def check(self, *, user_id: str, scratch: dict) -> Signal | None:
        return Signal(sensor="stub", summary="CPU is high")


def _fake_engine_thread(settings: Settings) -> EngineThread:
    """Same fake-provider injection tests/test_desktop_app.py already uses."""
    from jarvis.core.container import ServiceContainer
    from jarvis.core.engine import JarvisEngine

    thread = EngineThread(settings)

    def _run_with_fake() -> None:
        thread._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(thread._loop)
        thread._engine = JarvisEngine(container=ServiceContainer(
            settings, llm_client=LLMClient(primary=FakeProvider(default_reply="Heads up."))))
        thread._loop.run_until_complete(thread._engine.start())
        thread._started.set()
        thread._loop.run_forever()
        thread._loop.run_until_complete(thread._engine.shutdown())
        thread._loop.close()

    thread._run = _run_with_fake
    thread._thread = threading.Thread(target=thread._run, daemon=True)
    return thread


@pytest.mark.asyncio
async def test_proactive_engine_runs_on_the_real_engine_thread_loop():
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False, rate_limit_enabled=False,
        proactive_sensors_enabled=True,
    )
    thread = _fake_engine_thread(settings)
    thread.start()
    try:
        config = AppConfig(proactive_enabled=True)
        prefs = LocalProactivePrefs(config)
        proactive_engine = ProactiveEngine(thread.engine, prefs, settings,
                                        sensors=[_StubSensor()])

        received: list[str] = []
        done = threading.Event()

        async def send(chat_id: str, text: str) -> None:
            received.append(text)
            done.set()

        thread.submit(proactive_engine.tick(send))
        assert done.wait(10)
        assert received == ["Heads up."]
        # And it's recorded in the real session's history.
        assert thread.engine.session(LOCAL_USER_ID).conversation.messages[-1].content \
            == "Heads up."
    finally:
        thread.stop()
