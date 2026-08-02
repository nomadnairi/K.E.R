"""Tests for the client-side device agent (jarvis/desktop/agent.py)."""

from __future__ import annotations

import asyncio

import pytest

from jarvis.desktop.agent import (
    CAPABILITIES,
    LocalAgent,
    TerminalConfirmer,
    stable_device_id,
)
from jarvis.desktop.controller import DesktopController
from jarvis.security.manager import SecurityManager
from jarvis.security.policy import Capability, CapabilityMode


def _controller(mode: CapabilityMode = CapabilityMode.ON) -> DesktopController:
    return DesktopController(SecurityManager({Capability.DESKTOP_CONTROL: mode}))


def test_capabilities_match_the_dispatch_table():
    assert set(CAPABILITIES) == {"desktop.open_url", "desktop.type",
                                "desktop.press_key", "desktop.screenshot"}


@pytest.mark.asyncio
async def test_handle_dispatches_open_url(monkeypatch):
    controller = _controller()
    calls = []

    async def fake_open_url(url):
        calls.append(url)
        return f"Opened {url}."

    monkeypatch.setattr(controller, "open_url", fake_open_url)
    agent = LocalAgent("https://ker.example.com", "ker-key", controller, "dev-1")

    reply = await agent._handle({"call_id": "c1", "tool": "desktop.open_url",
                                "arguments": {"url": "https://youtube.com"}})

    assert calls == ["https://youtube.com"]
    assert reply == {"type": "tool_result", "call_id": "c1",
                    "content": "Opened https://youtube.com."}


@pytest.mark.asyncio
async def test_handle_unknown_tool_is_reported_not_crashed():
    agent = LocalAgent("https://x", "k", _controller(), "dev-1")
    reply = await agent._handle({"call_id": "c2", "tool": "camera.snap", "arguments": {}})
    assert reply["call_id"] == "c2"
    assert "Unknown tool" in reply["content"]


@pytest.mark.asyncio
async def test_handle_reports_a_permission_denial_as_text_not_an_exception():
    # Off by default -> the underlying controller raises PermissionDenied;
    # the agent must turn that into ordinary tool_result content, not crash.
    agent = LocalAgent("https://x", "k", _controller(CapabilityMode.OFF), "dev-1")
    reply = await agent._handle({"call_id": "c3", "tool": "desktop.open_url",
                                "arguments": {"url": "https://x"}})
    assert "disabled" in reply["content"].lower()


def test_ws_url_converts_http_scheme_to_websocket_scheme():
    agent = LocalAgent("https://ker.example.com", "ker-abc", _controller(), "dev-1")
    assert agent._ws_url() == "wss://ker.example.com/device/ws?key=ker-abc"

    agent2 = LocalAgent("http://localhost:8000", "ker-abc", _controller(), "dev-1")
    assert agent2._ws_url() == "ws://localhost:8000/device/ws?key=ker-abc"


def test_stable_device_id_persists_across_calls(tmp_path, monkeypatch):
    import jarvis.desktop.agent as agent_mod
    monkeypatch.setattr(agent_mod, "_device_id_path", lambda: tmp_path / "device_id")

    first = stable_device_id()
    second = stable_device_id()
    assert first == second
    assert (tmp_path / "device_id").read_text(encoding="utf-8").strip() == first


@pytest.mark.asyncio
async def test_terminal_confirmer_accepts_y(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    confirmer = TerminalConfirmer()
    assert confirmer.request(Capability.DESKTOP_CONTROL, "open a site") is True


@pytest.mark.asyncio
async def test_terminal_confirmer_defaults_to_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    confirmer = TerminalConfirmer()
    assert confirmer.request(Capability.DESKTOP_CONTROL, "open a site") is False


@pytest.mark.asyncio
async def test_run_retries_with_backoff_and_stops_cleanly(monkeypatch):
    import jarvis.desktop.agent as agent_mod
    monkeypatch.setattr(agent_mod, "_BACKOFF_INITIAL", 0.01)
    monkeypatch.setattr(agent_mod, "_BACKOFF_MAX", 0.02)

    agent = LocalAgent("https://x", "k", _controller(), "dev-1")
    attempts = 0

    async def failing_session():
        nonlocal attempts
        attempts += 1
        if attempts >= 3:
            agent.stop()
        raise ConnectionError("no server")

    monkeypatch.setattr(agent, "_session", failing_session)
    await asyncio.wait_for(agent.run(), timeout=2.0)
    assert attempts == 3
