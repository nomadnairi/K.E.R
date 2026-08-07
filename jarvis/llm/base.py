"""
Abstract LLM provider contract (async).

Concrete providers (Anthropic, OpenAI, and future local models) implement
:class:`LLMProvider`. The rest of the system depends only on this interface,
never on a vendor SDK. Providers support three capabilities:

* ``complete`` — a full, awaited completion (with optional tool calling),
* ``stream``   — an async iterator of text chunks, and
* tool calling — via provider-neutral :mod:`jarvis.llm.tools` types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

from jarvis.llm.tools import ToolCall, ToolResult, ToolSpec


@dataclass
class LLMResult:
    """Normalised result returned by every provider."""

    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    #: Populated when the model wants to call one or more tools.
    tool_calls: list[ToolCall] = field(default_factory=list)
    #: Provider stop reason, normalised where possible ("tool_use", "end", …).
    stop_reason: str = ""
    raw: object = field(default=None, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    #: Provider identifier, e.g. ``"anthropic"``.
    name: str = "base"

    def __init__(self, api_key: str, model: str, *, temperature: float = 0.7,
                max_tokens: int = 2048, base_url: str = "") -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        #: Optional custom API endpoint (e.g. OpenRouter, a local gateway).
        self.base_url = base_url
        self._client: object | None = None

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
    ) -> LLMResult:
        """Generate a completion for ``messages``.

        Args:
            messages: Ordered provider-format message dicts.
            system: Optional system prompt.
            tools: Optional tools the model may call.

        Returns:
            A populated :class:`LLMResult` (which may carry ``tool_calls``).

        Raises:
            LLMError (or subclass) on failure.
        """
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        system: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield the completion as a stream of text chunks.

        ``model`` optionally overrides the provider's default model for this
        call. Streaming does not support tool calls; use :meth:`complete`.
        """
        raise NotImplementedError
        yield ""  # pragma: no cover - marks this as an async generator

    @abstractmethod
    def continuation_messages(
        self,
        result: "LLMResult",
        tool_results: list[ToolResult],
    ) -> list[dict]:
        """Build the messages to append after a tool-calling round.

        Returns the assistant message echoing the tool calls followed by the
        tool-result message(s), in this provider's wire format, so the agentic
        loop can continue the conversation.
        """
        raise NotImplementedError

    def vision_user_message(self, text: str, image_b64: str,
                            mime: str = "image/png") -> dict:
        """Build a user message carrying both ``text`` and an image.

        Default is OpenAI's content-parts shape, used as-is by OpenRouter and
        any local OpenAI-compatible backend (they all send ``messages``
        straight to an OpenAI-shaped SDK call, untouched). Anthropic overrides
        this for its own block shape.
        """
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
            ],
        }

    def is_available(self) -> bool:
        """Whether the provider has the credentials it needs to run."""
        return bool(self.api_key)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<{type(self).__name__} model={self.model!r}>"
