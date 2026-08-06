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
already uses — not a task queue. Connections are keyed by ``(principal,
device_id)``, not ``principal`` alone: an account can have more than one
device online (a desktop PC and, later, a phone) without a second one
silently disconnecting the first — which is exactly what a bare-``principal``
key did before this module was audited. ``_pending`` call correlation is
additionally keyed by ``(principal, call_id)`` so ``call_id`` — a short
sequential counter shared by the whole process — can never be guessed or
reused across accounts.
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
        # (principal, device_id) -> connection. Plain dicts preserve
        # insertion order, which `call()` relies on to pick "the most
        # recently connected device" when a caller doesn't name one.
        self._connections: dict[tuple[str, str], _Connection] = {}
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
        self._connections[(principal, device_id)] = _Connection(
            websocket=websocket, device_id=device_id,
            capabilities=capabilities or [])
        logger.info("Device connected: principal=%s device_id=%s", principal,
                    device_id)

    def unregister(self, principal: str, device_id: str) -> None:
        self._connections.pop((principal, device_id), None)
        logger.info("Device disconnected: principal=%s device_id=%s",
                    principal, device_id)

    def is_connected(self, principal: str) -> bool:
        return any(p == principal for p, _ in self._connections)

    def describe(self, principal: str) -> list[dict]:
        """Every device this principal has online right now, for the
        dashboard to list — genuinely more than one, now that connections
        are keyed by ``(principal, device_id)`` instead of ``principal``
        alone."""
        return [
            {"device_id": conn.device_id, "capabilities": list(conn.capabilities),
            "online": True}
            for (p, _), conn in self._connections.items() if p == principal
        ]

    def _pick(self, principal: str, device_id: str | None) -> _Connection | None:
        """The connection a tool call should go to.

        A specific ``device_id`` is used if given and online; otherwise the
        most recently connected device for this principal — there is no UI
        yet for a caller to pick between several, so "whichever came online
        last" is the least surprising default until one exists.
        """
        if device_id is not None:
            return self._connections.get((principal, device_id))
        matches = [c for (p, _), c in self._connections.items() if p == principal]
        return matches[-1] if matches else None

    # -- relaying tool calls ---------------------------------------------------

    async def call(self, principal: str, tool: str, arguments: dict,
                    timeout: float | None = None, *,
                    device_id: str | None = None) -> SkillResult:
        """Relay a tool call to a connected device for ``principal``.

        ``device_id`` picks a specific device when the principal has more
        than one online; omitted, the most recently connected one is used
        (see :meth:`_pick`).
        """
        conn = self._pick(principal, device_id)
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
