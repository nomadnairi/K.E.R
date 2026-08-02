"""Tests for the server-side device relay (jarvis/desktop/device_registry.py)."""

from __future__ import annotations

import asyncio
import json

import pytest

from jarvis.desktop.device_registry import DeviceRegistry


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def test_not_connected_by_default():
    registry = DeviceRegistry()
    assert registry.is_connected("user:ann") is False


def test_register_and_unregister():
    registry = DeviceRegistry()
    ws = _FakeWebSocket()
    registry.register("user:ann", ws, "device-1", capabilities=["desktop.open_url"])
    assert registry.is_connected("user:ann") is True
    registry.unregister("user:ann")
    assert registry.is_connected("user:ann") is False


@pytest.mark.asyncio
async def test_call_without_a_connected_device_fails_cleanly():
    registry = DeviceRegistry()
    result = await registry.call("user:ann", "desktop.open_url", {"url": "https://x"})
    assert "no pc" in result.text.lower() or "not connected" in result.text.lower()


@pytest.mark.asyncio
async def test_call_sends_a_correlated_message_and_awaits_the_reply():
    registry = DeviceRegistry()
    ws = _FakeWebSocket()
    registry.register("user:ann", ws, "device-1")

    async def respond_soon():
        await asyncio.sleep(0.01)
        call_id = ws.sent[0]["call_id"]
        registry.resolve(call_id, content="Opened https://x.")

    asyncio.ensure_future(respond_soon())
    result = await registry.call("user:ann", "desktop.open_url", {"url": "https://x"},
                                timeout=2.0)

    assert result.text == "Opened https://x."
    assert ws.sent[0]["type"] == "tool_call"
    assert ws.sent[0]["tool"] == "desktop.open_url"
    assert ws.sent[0]["arguments"] == {"url": "https://x"}


@pytest.mark.asyncio
async def test_call_times_out_cleanly_when_the_device_never_replies():
    registry = DeviceRegistry()
    ws = _FakeWebSocket()
    registry.register("user:ann", ws, "device-1")

    result = await registry.call("user:ann", "desktop.open_url", {"url": "https://x"},
                                timeout=0.05)

    assert "time" in result.text.lower() or "offline" in result.text.lower()


@pytest.mark.asyncio
async def test_resolve_ignores_an_unknown_or_already_resolved_call_id():
    registry = DeviceRegistry()
    assert registry.resolve("nope", content="stray") is False


@pytest.mark.asyncio
async def test_a_dropped_socket_fails_the_call_instead_of_hanging():
    class _BrokenSocket:
        async def send_text(self, text: str) -> None:
            raise ConnectionError("socket closed")

    registry = DeviceRegistry()
    registry.register("user:ann", _BrokenSocket(), "device-1")
    result = await registry.call("user:ann", "desktop.open_url", {"url": "https://x"},
                                timeout=1.0)
    assert "could not reach" in result.text.lower()
