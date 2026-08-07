"""Tests for the proactive engine's decision step."""

from __future__ import annotations

import pytest

from jarvis.config.constants import DEFAULT_FAST_MODELS
from jarvis.llm.client import LLMClient
from jarvis.llm.prompts import PromptBuilder
from jarvis.proactive.decision import should_speak
from jarvis.proactive.models import Signal
from tests.conftest import FakeProvider


def _prompts() -> PromptBuilder:
    return PromptBuilder(assistant_name="KER", user_name="Sir")


@pytest.mark.asyncio
async def test_no_signals_never_calls_the_llm(settings):
    provider = FakeProvider()
    llm = LLMClient(primary=provider)
    result = await should_speak(llm=llm, prompts=_prompts(), settings=settings,
                                signals=[])
    assert result is None
    assert provider.calls == []


@pytest.mark.asyncio
async def test_nothing_sentinel_means_no_message(settings):
    provider = FakeProvider(default_reply="NOTHING")
    llm = LLMClient(primary=provider)
    result = await should_speak(
        llm=llm, prompts=_prompts(), settings=settings,
        signals=[Signal(sensor="system_health", summary="CPU at 96%.")],
    )
    assert result is None
    assert provider.calls  # the LLM was actually asked


@pytest.mark.asyncio
async def test_a_real_reply_is_returned_as_the_message(settings):
    provider = FakeProvider(default_reply="Sir, the machine has been under heavy load.")
    llm = LLMClient(primary=provider)
    result = await should_speak(
        llm=llm, prompts=_prompts(), settings=settings,
        signals=[Signal(sensor="system_health", summary="CPU at 96%.")],
    )
    assert result == "Sir, the machine has been under heavy load."


@pytest.mark.asyncio
async def test_uses_the_fast_model_by_default(settings):
    assert settings.llm_model_fast == ""
    provider = FakeProvider(default_reply="NOTHING")
    llm = LLMClient(primary=provider)
    await should_speak(llm=llm, prompts=_prompts(), settings=settings,
                        signals=[Signal(sensor="x", summary="y")])
    assert provider.models[-1] == DEFAULT_FAST_MODELS[settings.llm_provider]


@pytest.mark.asyncio
async def test_llm_failure_fails_closed(settings):
    class _Boom(FakeProvider):
        async def complete(self, *a, **k):
            raise RuntimeError("provider down")

    llm = LLMClient(primary=_Boom())
    result = await should_speak(
        llm=llm, prompts=_prompts(), settings=settings,
        signals=[Signal(sensor="x", summary="y")],
    )
    assert result is None
