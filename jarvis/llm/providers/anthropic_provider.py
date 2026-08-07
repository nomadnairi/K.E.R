"""Anthropic (Claude) provider implementation — async, with tools & streaming."""

from __future__ import annotations

from typing import AsyncIterator

from jarvis.llm.base import LLMProvider, LLMResult
from jarvis.llm.tools import ToolCall, ToolResult, ToolSpec
from jarvis.utils.exceptions import LLMConfigError, LLMRequestError


class AnthropicProvider(LLMProvider):
    """LLM provider backed by the Anthropic Messages API."""

    name = "anthropic"

    def _ensure_client(self) -> object:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - env guard
            raise LLMConfigError(
                "The 'anthropic' package is not installed. "
                "Run: pip install anthropic"
            ) from exc
        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
    ) -> LLMResult:
        if not self.api_key:
            raise LLMConfigError("Missing Anthropic API key.")

        client = self._ensure_client()
        use_model = model or self.model
        kwargs: dict = {
            "model": use_model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system or "",
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = [t.to_anthropic() for t in tools]

        try:
            response = await client.messages.create(**kwargs)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise LLMRequestError(
                f"Anthropic request failed: {exc}",
                details={"model": use_model},
            ) from exc

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )

        usage = getattr(response, "usage", None)
        return LLMResult(
            text="".join(text_parts).strip(),
            model=use_model,
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            tool_calls=tool_calls,
            stop_reason=getattr(response, "stop_reason", "") or "",
            raw=response,
        )

    async def stream(
        self,
        messages: list[dict],
        system: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise LLMConfigError("Missing Anthropic API key.")

        client = self._ensure_client()
        use_model = model or self.model
        try:
            async with client.messages.stream(  # type: ignore[attr-defined]
                model=use_model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system or "",
                messages=messages,
            ) as stream:
                async for chunk in stream.text_stream:
                    yield chunk
        except Exception as exc:  # noqa: BLE001
            raise LLMRequestError(
                f"Anthropic stream failed: {exc}",
                details={"model": use_model},
            ) from exc

    def vision_user_message(self, text: str, image_b64: str,
                            mime: str = "image/png") -> dict:
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image",
                "source": {"type": "base64", "media_type": mime, "data": image_b64}},
            ],
        }

    def continuation_messages(
        self,
        result: LLMResult,
        tool_results: list[ToolResult],
    ) -> list[dict]:
        assistant_content: list[dict] = []
        if result.text:
            assistant_content.append({"type": "text", "text": result.text})
        for call in result.tool_calls:
            assistant_content.append(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
            )

        result_blocks: list[dict] = []
        for tr in tool_results:
            block = {
                "type": "tool_result",
                "tool_use_id": tr.call_id,
                "content": tr.content,
            }
            if tr.is_error:
                block["is_error"] = True
            result_blocks.append(block)

        return [
            {"role": "assistant", "content": assistant_content},
            {"role": "user", "content": result_blocks},
        ]
