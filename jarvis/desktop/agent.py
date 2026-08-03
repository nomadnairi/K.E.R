"""
Local device agent — the client side of the server's device relay.

Connects **out** to the server (no inbound ports, no VPN needed on the
customer's side — the same outbound-only pattern used by relay/tunnel tools
like RelayCloud), and executes desktop-control tool calls it receives using
the exact same :class:`~jarvis.desktop.controller.DesktopController` /
:class:`~jarvis.security.manager.SecurityManager` any local engine already
uses. The permission decision is made *here*, on the machine being
controlled, using that machine's own ``allow_desktop_control`` /
``confirm_desktop_control`` settings — the server never decides this, it only
relays (see ``jarvis/desktop/device_registry.py`` and
``jarvis/api/app.py``'s ``/device/ws``).

Two ways to run it:

* Embedded in the desktop exe (``jarvis/desktop_app/app.py``) when the app is
  in "remote" mode (talking to the operator's server instead of running its
  own engine) — reuses this class unchanged.
* Standalone: ``python -m jarvis.desktop.agent`` — controls a PC without the
  exe open at all (e.g. so the Telegram bot can ask it to do something).
  Reads ``KER_SERVER_URL`` / ``KER_API_KEY`` from the environment (or
  ``--server`` / ``--api-key``), and everything else (``ALLOW_DESKTOP_CONTROL``,
  ``CONFIRM_DESKTOP_CONTROL``, ...) from the same ``.env`` / environment
  variables the rest of this project already reads via
  :class:`~jarvis.config.settings.Settings` — no separate config format.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from pathlib import Path

from jarvis.desktop.controller import DesktopController
from jarvis.utils.exceptions import JarvisError
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

#: Reconnect backoff — same shape as the Telegram bot's own polling loop
#: (jarvis/interfaces/telegram_bot.py).
_BACKOFF_INITIAL = 3.0
_BACKOFF_MAX = 300.0

#: The tool names this agent can execute, mapped to a (controller_method,
#: arg_names) pair — kept in sync with jarvis/desktop/tools.py's skill names.
_DISPATCH: dict[str, tuple[str, tuple[str, ...]]] = {
    "desktop.open_url": ("open_url", ("url",)),
    "desktop.type": ("type_text", ("text",)),
    "desktop.press_key": ("press_key", ("key",)),
    "desktop.screenshot": ("screenshot", ("path",)),
}

#: Tools whose result is image data, not human-readable text — sent back in
#: the tool_result's "metadata" field instead of "content" (see
#: ``jarvis/desktop/tools.py``'s ``CaptureScreenSkill``, the local-mode
#: equivalent of this same dispatch).
_IMAGE_DISPATCH: dict[str, str] = {
    "desktop.capture_screen": "capture_png_b64",
}

CAPABILITIES = tuple(_DISPATCH.keys()) + tuple(_IMAGE_DISPATCH.keys())


class TerminalConfirmer:
    """Blocking terminal y/n prompt — for the standalone, GUI-less agent.

    Compatible with :class:`~jarvis.security.confirm.ConfirmationBroker`'s
    duck-typed ``request(capability, action, *, timeout=None) -> bool``, so
    it plugs directly into an existing :class:`SecurityManager`. Blocking the
    process while waiting for an answer is fine here — this script has
    nothing else to stay responsive to.
    """

    def request(self, capability, action: str, *, timeout: float | None = None) -> bool:
        try:
            answer = input(f"KER wants to: {action}. Allow? [y/N] ").strip().lower()
        except EOFError:  # no interactive terminal attached
            return False
        return answer == "y"


def _device_id_path() -> Path:
    from jarvis.desktop_app.config import default_config_dir
    return default_config_dir() / "device_id"


def stable_device_id() -> str:
    """A device id that survives restarts, generated once and cached on disk."""
    path = _device_id_path()
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    new_id = uuid.uuid4().hex
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_id, encoding="utf-8")
    except OSError:  # pragma: no cover - best effort; a fresh id next run is fine
        pass
    return new_id


class LocalAgent:
    """Connects to the server's /device/ws and executes relayed tool calls."""

    def __init__(self, server_url: str, api_key: str, controller: DesktopController,
                device_id: str, *, capabilities: tuple[str, ...] = CAPABILITIES) -> None:
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.controller = controller
        self.device_id = device_id
        self.capabilities = list(capabilities)
        self._stop = asyncio.Event()

    def _ws_url(self) -> str:
        scheme = "wss" if self.server_url.startswith("https") else "ws"
        host = self.server_url.split("://", 1)[-1]
        return f"{scheme}://{host}/device/ws?key={self.api_key}"

    async def _handle(self, msg: dict) -> dict:
        tool = msg.get("tool", "")
        call_id = msg.get("call_id", "")
        arguments = msg.get("arguments") or {}

        image_method_name = _IMAGE_DISPATCH.get(tool)
        if image_method_name is not None:
            method = getattr(self.controller, image_method_name)
            try:
                b64 = await method()
                return {"type": "tool_result", "call_id": call_id,
                        "content": "Captured the screen.",
                        "metadata": {"image_png_b64": b64}}
            except JarvisError as exc:
                return {"type": "tool_result", "call_id": call_id, "content": str(exc)}

        spec = _DISPATCH.get(tool)
        if spec is None:
            return {"type": "tool_result", "call_id": call_id,
                    "content": f"Unknown tool {tool!r}."}
        method_name, arg_names = spec
        method = getattr(self.controller, method_name)
        try:
            content = await method(*(arguments.get(a, "") for a in arg_names))
        except JarvisError as exc:
            content = str(exc)
        return {"type": "tool_result", "call_id": call_id, "content": content}

    async def _session(self) -> None:
        import websockets

        async with websockets.connect(self._ws_url()) as ws:
            await ws.send(json.dumps({"device_id": self.device_id,
                                    "capabilities": self.capabilities}))
            logger.info("Device agent connected (device_id=%s)", self.device_id)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if msg.get("type") != "tool_call":
                    continue
                reply = await self._handle(msg)
                await ws.send(json.dumps(reply))

    async def run(self) -> None:
        """Connect, reconnecting with backoff, until :meth:`stop` is called."""
        backoff = _BACKOFF_INITIAL
        while not self._stop.is_set():
            try:
                await self._session()
                backoff = _BACKOFF_INITIAL  # a clean session resets the backoff
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - keep retrying, never crash
                logger.warning("Device agent disconnected (%s) — reconnecting "
                            "in %.0fs", exc, backoff)
            if self._stop.is_set():
                break
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, _BACKOFF_MAX)

    def stop(self) -> None:
        self._stop.set()


def _build_agent_from_env() -> LocalAgent:
    import argparse
    import os

    from jarvis.config.settings import get_settings
    from jarvis.security.manager import SecurityManager

    parser = argparse.ArgumentParser(
        prog="python -m jarvis.desktop.agent",
        description="Run K.E.R. as a headless local device agent — lets the "
                    "cloud-hosted assistant (bot, remote-mode exe) control "
                    "this PC without the desktop app open. Reads "
                    "ALLOW_DESKTOP_CONTROL / CONFIRM_DESKTOP_CONTROL and "
                    "everything else from the same .env this project "
                    "already uses.")
    parser.add_argument("--server", help="Server URL, e.g. https://ker.example.com "
                                        "(or set KER_SERVER_URL)")
    parser.add_argument("--api-key", help="A personal API key from Settings > "
                                        "API keys (or set KER_API_KEY)")
    args = parser.parse_args()

    server_url = args.server or os.environ.get("KER_SERVER_URL", "")
    api_key = args.api_key or os.environ.get("KER_API_KEY", "")
    if not server_url:
        parser.error("No server URL given (--server or KER_SERVER_URL).")
    if not api_key:
        parser.error("No API key given (--api-key or KER_API_KEY).")

    settings = get_settings()
    security = SecurityManager.from_settings(settings, confirmer=TerminalConfirmer())
    controller = DesktopController(security)
    return LocalAgent(server_url, api_key, controller, stable_device_id())


class AgentThread:
    """Runs a :class:`LocalAgent` on its own event loop/thread.

    For embedding in something that already owns an event loop it can't
    block — a Qt app's GUI thread, in particular — without needing that host
    to be asyncio-aware at all. Mirrors
    :class:`jarvis.desktop_app.engine_thread.EngineThread`'s shape.
    """

    def __init__(self, agent: LocalAgent) -> None:
        self._agent = agent
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="ker-device-agent")

    def start(self, timeout: float = 5.0) -> None:
        self._thread.start()
        self._started.wait(timeout)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_until_complete(self._agent.run())

    def stop(self, timeout: float = 5.0) -> None:
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._agent.stop)
        self._thread.join(timeout)


def main() -> None:
    agent = _build_agent_from_env()
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
