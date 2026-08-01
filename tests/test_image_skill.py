"""Tests for the generate_image tool (jarvis/media/tools.py).

The manual "🎨 Image" button/mode is covered by test_image_service.py and the
Telegram-layer tests; this file covers the assistant-initiated path — the
model calling generate_image mid-conversation, no button required.
"""

from __future__ import annotations

import base64

import pytest

from jarvis.media.image_service import ImageError, ImageService
from jarvis.media.tools import ImageSkill, image_skills


class _FakeImageService(ImageService):
    def __init__(self, *, fail_times: int = 0, png: bytes = b"fake-png") -> None:
        super().__init__(api_key="sk-x")
        self.fail_times = fail_times
        self.calls: list[str] = []
        self._png = png

    async def generate(self, prompt: str) -> bytes:
        self.calls.append(prompt)
        if len(self.calls) <= self.fail_times:
            raise ImageError("transient failure")
        return self._png


def test_tool_spec_shape():
    skill = ImageSkill(_FakeImageService())
    spec = skill.as_tool_spec()
    assert spec is not None
    assert spec.name == "generate_image"
    assert spec.parameters["required"] == ["prompt"]


def test_image_skills_factory_returns_the_skill():
    skills = image_skills(_FakeImageService())
    assert len(skills) == 1 and isinstance(skills[0], ImageSkill)


@pytest.mark.asyncio
async def test_execute_rejects_empty_prompt():
    skill = ImageSkill(_FakeImageService())
    result = await skill.execute(prompt="   ")
    assert "description" in result.text.lower()


@pytest.mark.asyncio
async def test_execute_denies_when_plan_lacks_images():
    skill = ImageSkill(_FakeImageService())
    result = await skill.execute(prompt="a cat", context={"plan_images": False})
    assert "plus" in result.text.lower() or "pro" in result.text.lower()
    assert "image_png_b64" not in result.metadata


@pytest.mark.asyncio
async def test_execute_allows_when_no_context_given():
    # CLI/API callers that never set plan_images shouldn't be silently blocked.
    service = _FakeImageService()
    skill = ImageSkill(service)
    result = await skill.execute(prompt="a cat")
    assert service.calls == ["a cat"]
    assert "image_png_b64" in result.metadata


@pytest.mark.asyncio
async def test_execute_returns_image_bytes_as_base64_metadata():
    service = _FakeImageService(png=b"\x89PNG raw bytes")
    skill = ImageSkill(service)
    result = await skill.execute(prompt="a sunset", context={"plan_images": True})
    decoded = base64.b64decode(result.metadata["image_png_b64"])
    assert decoded == b"\x89PNG raw bytes"


@pytest.mark.asyncio
async def test_execute_retries_transient_failures():
    service = _FakeImageService(fail_times=2)
    skill = ImageSkill(service)
    result = await skill.execute(prompt="a cat", context={"plan_images": True})
    assert len(service.calls) == 3  # two failures, then success
    assert "image_png_b64" in result.metadata


@pytest.mark.asyncio
async def test_execute_reports_failure_after_exhausting_retries():
    service = _FakeImageService(fail_times=99)
    skill = ImageSkill(service)
    result = await skill.execute(prompt="a cat", context={"plan_images": True})
    assert "failed" in result.text.lower()
    assert "image_png_b64" not in result.metadata
