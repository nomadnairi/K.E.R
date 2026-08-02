"""Tests for the server-side device relay wired into the FastAPI app.

Covers what tests/test_device_registry.py and tests/test_desktop.py can't:
the actual app.py wiring — /device/ws registration, _apply_device_relay
stashing the relay onto the session before a turn, and the server's own
create_app(settings=...) (no engine passed) never touching a real desktop
controller.
"""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from jarvis.api.app import create_app  # noqa: E402
from jarvis.config.settings import Settings  # noqa: E402
from jarvis.core.container import ServiceContainer  # noqa: E402
from jarvis.core.engine import JarvisEngine  # noqa: E402
from jarvis.llm.base import LLMResult  # noqa: E402
from jarvis.llm.client import LLMClient  # noqa: E402
from jarvis.llm.tools import ToolCall  # noqa: E402
from tests.conftest import FakeProvider  # noqa: E402


def _open_url_tool_call() -> LLMResult:
    return LLMResult(
        text="", model="fake-model", provider="fake", stop_reason="tool_use",
        output_tokens=3,
        tool_calls=[ToolCall(id="call_1", name="desktop.open_url",
                            arguments={"url": "https://youtube.com"})],
    )


def _app_with_fake_llm(settings: Settings, provider: FakeProvider):
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=provider)))
    return create_app(engine=engine, settings=settings), engine


class _AutoRespondingWebSocket:
    """Stands in for a connected device: replies to any tool_call as soon as
    it's sent, exactly like tests/test_device_registry.py's fake — this lets
    a normal synchronous /chat POST exercise the full relay round trip
    without needing a second real WebSocket thread in the test.
    """

    def __init__(self, registry) -> None:
        self._registry = registry

    async def send_text(self, text: str) -> None:
        msg = json.loads(text)
        assert msg["type"] == "tool_call"

        async def _reply():
            self._registry.resolve(msg["call_id"],
                                    content=f"Opened {msg['arguments']['url']} on the PC.")

        asyncio.ensure_future(_reply())


def _settings() -> Settings:
    return Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False, rate_limit_enabled=False,
        desktop_enabled=True,
    )


def test_chat_relays_a_desktop_tool_call_to_the_connected_device():
    settings = _settings()
    provider = FakeProvider(default_reply="Done — opened it for you.",
                            results=[_open_url_tool_call()])
    app, engine = _app_with_fake_llm(settings, provider)
    engine.container.devices.register(
        "shared", _AutoRespondingWebSocket(engine.container.devices), "device-1")

    with TestClient(app) as client:
        resp = client.post("/chat", json={"message": "open youtube"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Done — opened it for you."


def test_chat_without_a_connected_device_gets_a_clean_refusal_not_a_crash():
    settings = _settings()
    provider = FakeProvider(default_reply="Sorry, couldn't do that.",
                            results=[_open_url_tool_call()])
    app, engine = _app_with_fake_llm(settings, provider)
    # No device registered at all.

    with TestClient(app) as client:
        resp = client.post("/chat", json={"message": "open youtube"})
    assert resp.status_code == 200
    # The tool result fed back to the model said "no PC connected" —
    # confirmed indirectly: the call succeeded and used the scripted final
    # reply (i.e. two completions happened, the tool didn't raise/crash).
    assert len(provider.calls) == 2


def test_device_ws_registers_and_unregisters_on_disconnect():
    settings = _settings()
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    app = create_app(engine=engine, settings=settings)

    with TestClient(app) as client:
        with client.websocket_connect("/device/ws") as ws:
            ws.send_json({"device_id": "laptop-1", "capabilities": ["desktop.open_url"]})
            assert engine.container.devices.is_connected("shared") is True
    assert engine.container.devices.is_connected("shared") is False


def test_standalone_server_never_builds_a_real_desktop_controller():
    """create_app(settings=...) with NO engine passed — the actual
    `python -m jarvis.api` path — must never wire a controller that could
    touch pyautogui/webbrowser in-process; only a relay may execute anything.
    """
    from jarvis.security.policy import Capability, CapabilityMode

    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False, rate_limit_enabled=False,
        desktop_enabled=True, allow_desktop_control=True,  # even if turned on...
    )
    app = create_app(settings=settings)
    engine = app.state.engine
    skill = engine.skills._skills["desktop.open_url"]  # noqa: SLF001 - test-only
    # ...the server's own controller must still refuse direct execution.
    assert skill.controller.security.mode(Capability.DESKTOP_CONTROL) == CapabilityMode.OFF
