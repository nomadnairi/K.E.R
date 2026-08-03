"""
Desktop controller.

Wraps keyboard/mouse/screen control behind a security gate. Permission is
checked *before* any GUI backend is touched, so a denied action never even
imports ``pyautogui`` — and the whole thing stays safe by default.
"""

from __future__ import annotations

import asyncio
import base64
import io
import webbrowser

from jarvis.security.manager import SecurityManager
from jarvis.security.policy import Capability
from jarvis.utils.exceptions import IntegrationError


class DesktopError(IntegrationError):
    """A desktop action failed (e.g. no display, backend missing)."""


class DesktopController:
    """Controls the local desktop; every action is security-gated."""

    def __init__(self, security: SecurityManager) -> None:
        self.security = security

    def _pyautogui(self):
        try:
            import pyautogui
        except Exception as exc:  # noqa: BLE001 - import can fail without a display
            raise DesktopError(
                "Desktop GUI control needs 'pyautogui' and a desktop session. "
                "Install it with: pip install pyautogui"
            ) from exc
        return pyautogui

    def _require(self, action: str) -> None:
        self.security.require(Capability.DESKTOP_CONTROL, action)

    # -- actions ------------------------------------------------------------

    async def type_text(self, text: str) -> str:
        self._require(f"type_text: {text[:40]}")
        gui = self._pyautogui()
        await asyncio.to_thread(gui.typewrite, text)
        return f"Typed {len(text)} characters."

    async def press_key(self, key: str) -> str:
        self._require(f"press_key: {key}")
        gui = self._pyautogui()
        keys = [k.strip() for k in key.split("+") if k.strip()]
        if len(keys) > 1:
            await asyncio.to_thread(gui.hotkey, *keys)
        else:
            await asyncio.to_thread(gui.press, keys[0] if keys else key)
        return f"Pressed {key}."

    async def click(self, x: int | None = None, y: int | None = None) -> str:
        self._require(f"click: {x},{y}")
        gui = self._pyautogui()
        if x is not None and y is not None:
            await asyncio.to_thread(gui.click, x, y)
        else:
            await asyncio.to_thread(gui.click)
        return "Clicked."

    async def screenshot(self, path: str = "screenshot.png") -> str:
        self._require(f"screenshot: {path}")
        gui = self._pyautogui()
        image = await asyncio.to_thread(gui.screenshot)
        await asyncio.to_thread(image.save, path)
        return f"Saved a screenshot to {path}."

    async def capture_png_b64(self) -> str:
        """Capture the screen in memory and return it as base64-encoded PNG.

        Used for screen-share mode (feeding the model a live look at the
        screen) — unlike :meth:`screenshot`, nothing is written to disk.
        """
        self._require("screen capture (share mode)")
        gui = self._pyautogui()
        image = await asyncio.to_thread(gui.screenshot)
        buf = io.BytesIO()
        await asyncio.to_thread(image.save, buf, "PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    async def open_url(self, url: str) -> str:
        # Opening a browser is still a real-world action -> gate it.
        self._require(f"open_url: {url}")
        opened = await asyncio.to_thread(webbrowser.open, url)
        return f"Opened {url}." if opened else f"Could not open {url}."
