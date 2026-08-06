"""
Device registry — the server's side of "cloud brain, local hands".

When the engine runs on the operator's server (remote-mode desktop clients,
the Telegram bot, the web API) it has no desktop of its own to control — a
connected device (the exe in remote mode, or the standalone
:mod:`jarvis.desktop.agent`) is what actually runs :class:`DesktopController`
on the user's own machine. This registry tracks which principal currently has
a device online and relays a tool call to it, correlating the reply by id.

Kept deliberately simple for what exists today (every action completes in
under a couple of seconds): a plain bounded ``await`` per call, the same
blocking-with-timeout shape :class:`~jarvis.security.confirm.ConfirmationBroker`
already uses — not a task queue. Keyed by ``(principal, device_id)`` rather
than just ``principal`` so a second device type (Android, Raspberry Pi, ...)
can be added later without reshaping this map; nothing today picks between
multiple devices for one principal.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from dataclasses import dataclass, field

from jarvis.skills.base import SkillResult
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

_ids = itertools.count(1)


@dataclass
class _Connection:
    websocket: object  # a Starlette/FastAPI WebSocket — kept untyped to avoid
    #                     importing fastapi where it isn't otherwise needed.
    device_id: str
    capabilities: list[str] = field(default_factory=list)


class DeviceRegistry:
    """Tracks connected devices and relays tool calls to them."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._connections: dict[str, _Connection] = {}
        # Keyed by (principal, call_id), not call_id alone: call_id is a short
        # sequential counter shared by the whole process ("dc1", "dc2", ...),
        # so without the principal in the key, any connected device — any
        # signed-in account — could resolve (or overwrite the answer to)
        # another account's in-flight tool call just by sending back a
        # guessed or reused id.
        self._pending: dict[tuple[str, str], asyncio.Future] = {}

    # -- connection lifecycle ------------------------------------------------

    def register(self, principal: str, websocket: object, device_id: str,
                capabilities: list[str] | None = None) -> None:
        self._connections[principal] = _Connection(
            websocket=websocket, device_id=device_id,
            capabilities=capabilities or [])
        logger.info("Device connected: principal=%s device_id=%s", principal,
                    device_id)

    def unregister(self, principal: str) -> None:
        self._connections.pop(principal, None)
        logger.info("Device disconnected: principal=%s", principal)

    def is_connected(self, principal: str) -> bool:
        return principal in self._connections

    def describe(self, principal: str) -> list[dict]:
        """The devices this principal has online, for the dashboard to list.

        Returns a list even though one principal currently has at most one
        connection — the map is keyed for more, and a caller written against a
        list today needs no change when that day comes.
        """
        conn = self._connections.get(principal)
        if conn is None:
            return []
        return [{
            "device_id": conn.device_id,
            "capabilities": list(conn.capabilities),
            "online": True,
        }]

    # -- relaying tool calls ---------------------------------------------------

    async def call(self, principal: str, tool: str, arguments: dict,
                    timeout: float | None = None) -> SkillResult:
        """Relay a tool call to the connected device for ``principal``."""
        conn = self._connections.get(principal)
        if conn is None:
            return SkillResult(
                text="No PC is connected right now — open the app on the "
                    "device you want to control.")
        call_id = f"dc{next(_ids)}"
        key = (principal, call_id)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[key] = future
        try:
            await conn.websocket.send_text(json.dumps({
                "type": "tool_call", "call_id": call_id, "tool": tool,
                "arguments": arguments,
            }))
            result = await asyncio.wait_for(future, timeout or self._timeout)
        except asyncio.TimeoutError:
            return SkillResult(text="The device didn't respond in time — "
                                "it may be asleep or offline.")
        except Exception as exc:  # noqa: BLE001 - the socket may have dropped
            return SkillResult(text=f"Could not reach the device: {exc}")
        finally:
            self._pending.pop(key, None)
        return result

    def resolve(self, principal: str, call_id: str, *, content: str,
                metadata: dict | None = None) -> bool:
        """Called by the WS receive loop when a ``tool_result`` arrives.

        ``principal`` is the identity of *that socket* (resolved once at
        connection time from its own auth, never from the message body), so
        a connection can only ever resolve a call that was issued to it in
        the first place — sending back another account's call_id, guessed or
        not, matches nothing and is silently ignored, the same as an unknown
        or already-resolved id.

        No separate "is_error" flag: exactly like every other skill in this
        codebase, a denial or failure is just explanatory text in a normal
        (non-exception) :class:`SkillResult` — the model reads it and reports
        honestly, per the "Acting in the real world" system-prompt rule.
        """
        future = self._pending.get((principal, call_id))
        if future is None or future.done():
            return False
        future.set_result(SkillResult(text=content, metadata=metadata or {}))
        return True
