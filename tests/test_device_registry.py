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
    registry.unregister("user:ann", "device-1")
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
        registry.resolve("user:ann", call_id, content="Opened https://x.")

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
    assert registry.resolve("user:ann", "nope", content="stray") is False


# -- per-principal isolation (the fix) ---------------------------------------
#
# call_id is a short, sequential, process-wide counter ("dc1", "dc2", ...).
# Before this fix, resolve() only looked it up by call_id, so any connected
# device — any signed-in account — could answer (or overwrite the answer to)
# another account's in-flight tool call just by sending back a guessed id.


@pytest.mark.asyncio
async def test_two_users_with_identical_call_ids_do_not_collide(monkeypatch):
    # Two separate registries would never prove this — the point is that one
    # shared _pending map, indexed only by call_id, is exactly where the bug
    # lived. Force both calls to mint the same id and confirm each answer
    # still reaches only its own caller. monkeypatch restores the module's
    # real, process-wide counter afterwards — it must not leak into other
    # tests, which mint their own ids from it.
    from jarvis.desktop import device_registry as dr

    registry = DeviceRegistry()
    ws_ann, ws_bob = _FakeWebSocket(), _FakeWebSocket()
    registry.register("user:ann", ws_ann, "device-ann")
    registry.register("user:bob", ws_bob, "device-bob")

    monkeypatch.setattr(dr, "_ids", iter([1, 1]))  # both calls mint "dc1"

    async def respond_to_both():
        await asyncio.sleep(0.01)
        assert ws_ann.sent[0]["call_id"] == ws_bob.sent[0]["call_id"] == "dc1"
        registry.resolve("user:ann", "dc1", content="Ann's own result")
        registry.resolve("user:bob", "dc1", content="Bob's own result")

    asyncio.ensure_future(respond_to_both())
    ann_result, bob_result = await asyncio.gather(
        registry.call("user:ann", "desktop.open_url", {"url": "https://a"}, timeout=2.0),
        registry.call("user:bob", "desktop.open_url", {"url": "https://b"}, timeout=2.0),
    )

    assert ann_result.text == "Ann's own result"
    assert bob_result.text == "Bob's own result"


@pytest.mark.asyncio
async def test_a_users_own_call_id_cannot_be_used_to_resolve_another_users_call():
    registry = DeviceRegistry()
    ws_ann, ws_bob = _FakeWebSocket(), _FakeWebSocket()
    registry.register("user:ann", ws_ann, "device-ann")
    registry.register("user:bob", ws_bob, "device-bob")

    async def bob_tries_to_answer_anns_call():
        await asyncio.sleep(0.01)
        call_id = ws_ann.sent[0]["call_id"]
        # Bob's own connection (his own authenticated principal) tries to
        # resolve the id it observed/guessed for Ann's call.
        forged = registry.resolve("user:bob", call_id, content="forged by bob")
        assert forged is False
        # The real device answers afterwards; Ann's call must still succeed
        # with its own, real result — not Bob's forged one.
        registry.resolve("user:ann", call_id, content="Ann's real result")

    asyncio.ensure_future(bob_tries_to_answer_anns_call())
    result = await registry.call("user:ann", "desktop.open_url",
                                {"url": "https://a"}, timeout=2.0)
    assert result.text == "Ann's real result"


# -- per-account multi-device (the A3 fix) -----------------------------------
#
# _connections used to be keyed by principal alone, so a second device
# connecting for the same account silently evicted the first — even though
# the module docstring already claimed (principal, device_id) keying. These
# tests prove the real behaviour now matches that claim.


def test_a_second_device_does_not_evict_the_first():
    registry = DeviceRegistry()
    ws1, ws2 = _FakeWebSocket(), _FakeWebSocket()
    registry.register("user:ann", ws1, "phone")
    registry.register("user:ann", ws2, "laptop")

    assert registry.is_connected("user:ann") is True
    devices = {d["device_id"] for d in registry.describe("user:ann")}
    assert devices == {"phone", "laptop"}


def test_unregistering_one_device_leaves_the_other_connected():
    registry = DeviceRegistry()
    ws1, ws2 = _FakeWebSocket(), _FakeWebSocket()
    registry.register("user:ann", ws1, "phone")
    registry.register("user:ann", ws2, "laptop")

    registry.unregister("user:ann", "phone")

    assert registry.is_connected("user:ann") is True
    assert [d["device_id"] for d in registry.describe("user:ann")] == ["laptop"]


def test_unregistering_the_last_device_marks_the_account_offline():
    registry = DeviceRegistry()
    ws = _FakeWebSocket()
    registry.register("user:ann", ws, "phone")
    registry.unregister("user:ann", "phone")
    assert registry.is_connected("user:ann") is False


@pytest.mark.asyncio
async def test_call_targets_a_specific_device_id_when_given():
    registry = DeviceRegistry()
    phone, laptop = _FakeWebSocket(), _FakeWebSocket()
    registry.register("user:ann", phone, "phone")
    registry.register("user:ann", laptop, "laptop")

    async def respond_on_laptop():
        await asyncio.sleep(0.01)
        call_id = laptop.sent[0]["call_id"]
        registry.resolve("user:ann", call_id, content="done on laptop")

    asyncio.ensure_future(respond_on_laptop())
    result = await registry.call("user:ann", "desktop.open_url", {"url": "https://x"},
                                timeout=2.0, device_id="laptop")

    assert result.text == "done on laptop"
    assert phone.sent == []  # the other device never saw the call


@pytest.mark.asyncio
async def test_call_without_a_device_id_uses_the_most_recently_connected():
    registry = DeviceRegistry()
    old, new = _FakeWebSocket(), _FakeWebSocket()
    registry.register("user:ann", old, "old-laptop")
    registry.register("user:ann", new, "new-laptop")

    async def respond():
        await asyncio.sleep(0.01)
        call_id = new.sent[0]["call_id"]
        registry.resolve("user:ann", call_id, content="ok")

    asyncio.ensure_future(respond())
    await registry.call("user:ann", "desktop.open_url", {"url": "https://x"}, timeout=2.0)

    assert old.sent == []
    assert len(new.sent) == 1


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
