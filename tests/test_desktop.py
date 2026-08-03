"""Tests for desktop control and the tool manager (no GUI touched)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from jarvis.config.settings import Settings
from jarvis.core.container import ServiceContainer
from jarvis.desktop.controller import DesktopController
from jarvis.desktop.tools import (
    CaptureScreenSkill,
    OpenUrlSkill,
    ShareScreenSkill,
    TypeTextSkill,
)
from jarvis.security.manager import SecurityManager
from jarvis.skills.manager import ToolManager
from jarvis.utils.exceptions import PermissionDenied


def _security(desktop: bool) -> SecurityManager:
    return SecurityManager.from_settings(
        Settings(allow_desktop_control=desktop, audit_log_path="")
    )


# -- desktop gating ---------------------------------------------------------


@pytest.mark.asyncio
async def test_desktop_denied_by_default():
    controller = DesktopController(_security(False))
    with pytest.raises(PermissionDenied):
        await controller.type_text("hello")  # denied before touching any GUI


@pytest.mark.asyncio
async def test_desktop_tool_surfaces_denial():
    skill = TypeTextSkill(DesktopController(_security(False)))
    result = await skill.execute(text="hi")
    assert "Cannot type" in result.text


@pytest.mark.asyncio
async def test_open_url_when_allowed():
    controller = DesktopController(_security(True))
    with patch("webbrowser.open", return_value=True) as opener:
        skill = OpenUrlSkill(controller)
        result = await skill.execute(url="https://example.com")
    opener.assert_called_once()
    assert "Opened" in result.text


@pytest.mark.asyncio
async def test_open_url_denied_by_default():
    skill = OpenUrlSkill(DesktopController(_security(False)))
    result = await skill.execute(url="https://example.com")
    assert "Cannot open URL" in result.text


# -- device relay (server-hosted engine, no desktop of its own) -------------


@pytest.mark.asyncio
async def test_relay_is_used_when_present_in_context():
    from jarvis.skills.base import SkillResult

    calls = []

    async def fake_relay(tool, arguments):
        calls.append((tool, arguments))
        return SkillResult(text="Opened on the customer's PC.")

    # A relay in context means self.controller is never touched — even one
    # that would otherwise deny the action locally.
    skill = OpenUrlSkill(DesktopController(_security(False)))
    result = await skill.execute(url="https://example.com",
                                context={"device_relay": fake_relay})

    assert calls == [("desktop.open_url", {"url": "https://example.com"})]
    assert result.text == "Opened on the customer's PC."


@pytest.mark.asyncio
async def test_no_relay_falls_back_to_the_local_controller_unchanged():
    # context=None or a context without "device_relay" behaves exactly as
    # before the relay feature existed — this is the local-mode regression
    # guard (also covered by the un-parametrised tests above).
    with patch("webbrowser.open", return_value=True) as opener:
        skill = OpenUrlSkill(DesktopController(_security(True)))
        result = await skill.execute(url="https://example.com", context={})
    opener.assert_called_once()
    assert "Opened" in result.text


# -- screen sharing -----------------------------------------------------------


class _FakeImage:
    def save(self, fp, fmt=None) -> None:
        fp.write(b"\x89PNG\r\n\x1a\nfakedata")


class _FakePyAutoGui:
    def screenshot(self):
        return _FakeImage()


@pytest.mark.asyncio
async def test_capture_png_b64_returns_the_captured_bytes():
    import base64

    controller = DesktopController(_security(True))
    with patch.object(DesktopController, "_pyautogui", return_value=_FakePyAutoGui()):
        b64 = await controller.capture_png_b64()
    assert base64.b64decode(b64) == b"\x89PNG\r\n\x1a\nfakedata"


@pytest.mark.asyncio
async def test_capture_png_b64_denied_by_default():
    controller = DesktopController(_security(False))
    with pytest.raises(PermissionDenied):
        await controller.capture_png_b64()


@pytest.mark.asyncio
async def test_capture_screen_skill_puts_the_image_in_metadata_not_text():
    skill = CaptureScreenSkill(DesktopController(_security(True)))
    with patch.object(DesktopController, "_pyautogui", return_value=_FakePyAutoGui()):
        result = await skill.execute()
    assert "image_png_b64" in result.metadata
    assert "image_png_b64" not in result.text


@pytest.mark.asyncio
async def test_capture_screen_skill_surfaces_denial_as_text_not_an_image():
    skill = CaptureScreenSkill(DesktopController(_security(False)))
    result = await skill.execute()
    assert result.metadata == {}
    assert "Cannot capture screen" in result.text


@pytest.mark.asyncio
async def test_capture_screen_skill_uses_the_relay_when_present():
    from jarvis.skills.base import SkillResult

    calls = []

    async def fake_relay(tool, arguments):
        calls.append((tool, arguments))
        return SkillResult(text="Captured.", metadata={"image_png_b64": "cmVsYXk="})

    skill = CaptureScreenSkill(DesktopController(_security(False)))
    result = await skill.execute(context={"device_relay": fake_relay})

    assert calls == [("desktop.capture_screen", {})]
    assert result.metadata["image_png_b64"] == "cmVsYXk="


@pytest.mark.asyncio
async def test_share_screen_skill_toggles_a_session_flag():
    skill = ShareScreenSkill()
    scratch: dict = {}

    on = await skill.execute(enabled=True, context=scratch)
    assert scratch["share_screen"] is True
    assert "on" in on.text.lower()

    off = await skill.execute(enabled=False, context=scratch)
    assert scratch["share_screen"] is False
    assert "off" in off.text.lower()


# -- tool manager -----------------------------------------------------------


def test_tool_manager_categorizes():
    settings = Settings(
        memory_enabled=False, integrations_enabled=False, goals_enabled=True,
        files_enabled=True, coding_enabled=True, desktop_enabled=True,
        agents_enabled=True, memory_db_path=":memory:",
    )
    tm: ToolManager = ServiceContainer(settings).tool_manager
    categories = tm.categories()
    assert "goals" in categories
    assert "files" in categories
    assert "desktop" in categories
    assert "coding" in categories
    assert any("add_goal" in names for names in categories.values())


def test_tool_manager_disable():
    settings = Settings(memory_enabled=False, integrations_enabled=False,
                        goals_enabled=True, memory_db_path=":memory:")
    tm: ToolManager = ServiceContainer(settings).tool_manager
    assert tm.disable("add_goal") is True
    assert all("add_goal" != s.name for s in tm.tools())
