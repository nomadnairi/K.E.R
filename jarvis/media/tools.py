"""The ``generate_image`` tool — draw from a natural-language prompt.

No hardcoded "if the message says X, run action Y": the model decides on its
own, from ordinary conversation, when to call this — the same tool-calling
path every other skill in this codebase already uses. The manual "🎨 Image"
button in the Telegram bot is a second, explicit entry point onto the same
:class:`~jarvis.media.image_service.ImageService`; neither replaces the other.
"""

from __future__ import annotations

import base64

from jarvis.media.image_service import ImageError, ImageService
from jarvis.skills.base import BaseSkill, SkillResult
from jarvis.utils.retry import retry_async


class ImageSkill(BaseSkill):
    """Generate an image from a text prompt."""

    name = "generate_image"
    description = (
        "Generate an image from a text description (e.g. \"a cat in a hat, "
        "watercolor\"). Use this whenever the user asks you to draw, "
        "generate, create, or make a picture/image/illustration."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "What to draw, in as much visual detail as given.",
            }
        },
        "required": ["prompt"],
    }

    def __init__(self, image_service: ImageService) -> None:
        self._image_service = image_service

    def can_handle(self, text: str) -> bool:
        return False

    async def handle(self, text: str, context: dict | None = None) -> SkillResult:
        return SkillResult.not_handled()

    async def execute(self, prompt: str = "", context: dict | None = None,
                    **_: object) -> SkillResult:
        if not prompt.strip():
            return SkillResult(text="I need a description of what to draw.")
        if context is not None and not context.get("plan_images", True):
            return SkillResult(
                text="Image generation needs the Plus or Pro plan — tell the "
                    "user to check the Tariffs menu to upgrade.")

        @retry_async(attempts=3, base_delay=0.2, exceptions=(ImageError,))
        async def _call() -> bytes:
            return await self._image_service.generate(prompt)

        try:
            png = await _call()
        except ImageError as exc:
            return SkillResult(text=f"Image generation failed: {exc}")
        return SkillResult(
            text=f"Image generated for: {prompt!r}",
            metadata={"image_png_b64": base64.b64encode(png).decode("ascii")},
        )


def image_skills(image_service: ImageService) -> list[BaseSkill]:
    return [ImageSkill(image_service)]
