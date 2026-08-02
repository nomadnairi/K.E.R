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


def desktop_skills(controller: DesktopController) -> list[BaseSkill]:
    return [
        TypeTextSkill(controller),
        PressKeySkill(controller),
        OpenUrlSkill(controller),
        ScreenshotSkill(controller),
    ]
