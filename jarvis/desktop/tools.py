"""Desktop tools — expose desktop control to the LLM (security-gated).

Each skill's ``execute()`` checks ``context["device_relay"]`` first (set by
the caller — see ``jarvis/api/app.py`` — only when the engine runs on a
server and a device is connected for this principal, via
:class:`~jarvis.desktop.device_registry.DeviceRegistry`). When present, the
call is relayed to that device instead of touching ``self.controller``
in-process — the server has no desktop of its own to control. When absent
(a genuinely local engine: the desktop app in local mode, or the CLI),
``self.controller`` runs exactly as before — nothing changes for that path.

Tool names carry a ``desktop.`` prefix so a future ``browser.*``/
``filesystem.*`` device-capability namespace doesn't collide with these.
"""

from __future__ import annotations

from jarvis.desktop.controller import DesktopController
from jarvis.skills.base import BaseSkill, SkillResult
from jarvis.utils.exceptions import JarvisError


class _DesktopSkill(BaseSkill):
    priority = 20

    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    def can_handle(self, text: str) -> bool:
        return False

    async def handle(self, text: str, context: dict | None = None) -> SkillResult:
        return SkillResult.not_handled()

    @staticmethod
    def _relay(context: dict | None):
        return (context or {}).get("device_relay")


class TypeTextSkill(_DesktopSkill):
    name = "desktop.type"
    description = "Type text on the keyboard (desktop control; off by default)."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Text to type."}},
        "required": ["text"],
    }

    async def execute(self, text: str = "", context: dict | None = None,
                    **_: object) -> SkillResult:
        relay = self._relay(context)
        if relay is not None:
            return await relay(self.name, {"text": text})
        try:
            return SkillResult(text=await self.controller.type_text(text))
        except JarvisError as exc:
            return SkillResult(text=f"Cannot type: {exc}")


class PressKeySkill(_DesktopSkill):
    name = "desktop.press_key"
    description = "Press a key or hotkey combo (e.g. 'enter' or 'ctrl+c')."
    parameters = {
        "type": "object",
        "properties": {"key": {"type": "string", "description": "Key or combo."}},
        "required": ["key"],
    }

    async def execute(self, key: str = "", context: dict | None = None,
                    **_: object) -> SkillResult:
        relay = self._relay(context)
        if relay is not None:
            return await relay(self.name, {"key": key})
        try:
            return SkillResult(text=await self.controller.press_key(key))
        except JarvisError as exc:
            return SkillResult(text=f"Cannot press key: {exc}")


class OpenUrlSkill(_DesktopSkill):
    name = "desktop.open_url"
    description = "Open a URL in the default web browser."
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "The URL to open."}},
        "required": ["url"],
    }

    async def execute(self, url: str = "", context: dict | None = None,
                    **_: object) -> SkillResult:
        relay = self._relay(context)
        if relay is not None:
            return await relay(self.name, {"url": url})
        try:
            return SkillResult(text=await self.controller.open_url(url))
        except JarvisError as exc:
            return SkillResult(text=f"Cannot open URL: {exc}")


class ScreenshotSkill(_DesktopSkill):
    name = "desktop.screenshot"
    description = "Take a screenshot of the screen and save it to a file."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Output path."}},
    }

    async def execute(self, path: str = "screenshot.png", context: dict | None = None,
                    **_: object) -> SkillResult:
        relay = self._relay(context)
        if relay is not None:
            return await relay(self.name, {"path": path or "screenshot.png"})
        try:
            return SkillResult(text=await self.controller.screenshot(path or "screenshot.png"))
        except JarvisError as exc:
            return SkillResult(text=f"Cannot take screenshot: {exc}")


class CaptureScreenSkill(_DesktopSkill):
    """Captures the screen for share mode (see :class:`ShareScreenSkill`).

    Internal only — no ``parameters``, so it is never offered to the model as
    a callable tool; the engine invokes it directly by name (see
    ``jarvis/core/engine.py``) once per turn while sharing is on. Unlike
    :class:`ScreenshotSkill`, ``text`` is a short status line and the actual
    image goes in ``metadata["image_png_b64"]`` (matching
    ``jarvis/media/tools.py``'s ``ImageSkill`` convention) — nothing here is
    ever shown to the user verbatim.
    """

    name = "desktop.capture_screen"
    description = "Capture the screen as image data (internal use only)."

    async def execute(self, context: dict | None = None, **_: object) -> SkillResult:
        relay = self._relay(context)
        if relay is not None:
            return await relay(self.name, {})
        try:
            b64 = await self.controller.capture_png_b64()
            return SkillResult(text="Captured the screen.",
                                metadata={"image_png_b64": b64})
        except JarvisError as exc:
            return SkillResult(text=f"Cannot capture screen: {exc}")


class ShareScreenSkill(BaseSkill):
    """Turns screen sharing on/off — a session-scoped flag, not a desktop action
    itself, so it doesn't go through ``_relay``/``self.controller`` at all."""

    name = "desktop.share_screen"
    description = ("Turn screen sharing on or off for this conversation. While "
                    "on, every message you send is accompanied by a fresh "
                    "screenshot, so you can see what's on the screen (e.g. to "
                    "explain code someone has open, or describe a window).")
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean",
                        "description": "True to start sharing, false to stop."},
        },
        "required": ["enabled"],
    }
    priority = 20

    def can_handle(self, text: str) -> bool:
        return False

    async def handle(self, text: str, context: dict | None = None) -> SkillResult:
        return SkillResult.not_handled()

    async def execute(self, enabled: bool = False, context: dict | None = None,
                    **_: object) -> SkillResult:
        if context is not None:
            context["share_screen"] = bool(enabled)
        if enabled:
            text = "Screen sharing is on — I'll see a fresh screenshot with each message."
        else:
            text = "Screen sharing is off."
        return SkillResult(text=text)


def desktop_skills(controller: DesktopController) -> list[BaseSkill]:
    return [
        TypeTextSkill(controller),
        PressKeySkill(controller),
        OpenUrlSkill(controller),
        ScreenshotSkill(controller),
        CaptureScreenSkill(controller),
        ShareScreenSkill(),
    ]
