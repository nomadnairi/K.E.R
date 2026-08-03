"""End-to-end tests for the async engine (routing, tools, streaming, sessions)."""

from __future__ import annotations

import pytest

from jarvis.config.constants import AssistantState, ResponseType
from jarvis.models.response import Request
from tests.conftest import FakeProvider, build_engine, make_tool_call_result


@pytest.mark.asyncio
async def test_llm_path_returns_reply(engine):
    reply = await engine.ask("Tell me a story about the sea.")
    assert reply == "Certainly, Sir."


@pytest.mark.asyncio
async def test_skill_path_bypasses_llm(engine, fake_provider):
    # "system status" is handled by the SystemSkill, not the LLM.
    response = await engine.process(Request(text="system status"))
    assert response.type == ResponseType.SKILL
    assert response.source == "system_status"
    assert fake_provider.calls == []  # LLM never called


@pytest.mark.asyncio
async def test_llm_path_records_history(engine):
    await engine.ask("first")
    await engine.ask("second")
    session = engine.session("default")
    assert len(session.conversation) == 4  # 2 user + 2 assistant


@pytest.mark.asyncio
async def test_reset_clears_history(engine):
    await engine.ask("hello")
    assert len(engine.session("default").conversation) > 0
    await engine.reset("default")
    assert len(engine.session("default").conversation) == 0


@pytest.mark.asyncio
async def test_engine_returns_to_idle(engine):
    await engine.ask("anything")
    assert engine.state.state == AssistantState.IDLE


@pytest.mark.asyncio
async def test_telemetry_counts_requests(engine):
    await engine.ask("one")
    await engine.ask("two")
    stats = engine.stats
    assert stats["requests_total"] == 2
    assert stats["responses_total"] == 2


@pytest.mark.asyncio
async def test_telemetry_tracks_skill_by_name(engine):
    await engine.process(Request(text="system status"))
    await engine.process(Request(text="what time is it"))
    stats = engine.stats
    assert stats["skill_usage"].get("system_status") == 1
    assert stats["skill_usage"].get("get_datetime") == 1


# -- agentic tool loop ------------------------------------------------------


@pytest.mark.asyncio
async def test_agentic_tool_loop(settings):
    # First completion asks to call the calculator; second returns final text.
    provider = FakeProvider(
        default_reply="The answer is 40.",
        results=[make_tool_call_result("calculator", {"expression": "(12.5/100)*320"})],
    )
    engine = build_engine(settings, provider)

    response = await engine.process(Request(text="what is 12.5% of 320?"))

    assert response.type == ResponseType.LLM
    assert response.text == "The answer is 40."
    # Two completions: one requesting the tool, one producing the final answer.
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_tool_loop_stops_at_max_rounds(settings):
    # Provider always asks for a tool -> loop must terminate at max_tool_rounds.
    settings.max_tool_rounds = 3
    provider = FakeProvider(
        results=[make_tool_call_result("calculator", {"expression": "1+1"})] * 10
    )
    engine = build_engine(settings, provider)
    await engine.process(Request(text="loop forever"))
    assert len(provider.calls) == 3


@pytest.mark.asyncio
async def test_voice_source_stops_at_the_shorter_voice_round_cap(settings):
    # A voice-originated turn is capped by voice_max_tool_rounds, not the
    # (longer) default — independent of the setting above.
    settings.max_tool_rounds = 5
    settings.voice_max_tool_rounds = 1
    provider = FakeProvider(
        results=[make_tool_call_result("calculator", {"expression": "1+1"})] * 10
    )
    engine = build_engine(settings, provider)
    await engine.process(Request(text="loop forever", source="voice"))
    assert len(provider.calls) == 1
    # A plain (non-voice) request on the same engine still gets the full budget.
    await engine.process(Request(text="loop forever again"))
    assert len(provider.calls) == 1 + 5


@pytest.mark.asyncio
async def test_voice_source_prefers_the_fast_model(settings):
    settings.llm_model_fast = "fast-model"
    provider = FakeProvider(default_reply="ok")
    engine = build_engine(settings, provider)

    await engine.process(Request(text="hi", source="voice"))
    assert provider.models[-1] == "fast-model"

    await engine.process(Request(text="hi"))  # cli/text: unaffected
    assert provider.models[-1] is None


@pytest.mark.asyncio
async def test_tool_metadata_reaches_the_final_response(settings):
    from jarvis.skills.base import BaseSkill, SkillResult
    from jarvis.skills.registry import SkillRegistry

    class _StubSkill(BaseSkill):
        name = "stub_tool"
        description = "test-only"
        parameters = {"type": "object", "properties": {}}

        def can_handle(self, text: str) -> bool:
            return False

        async def handle(self, text: str, context=None) -> SkillResult:
            return SkillResult.not_handled()

        async def execute(self, context=None, **_: object) -> SkillResult:
            return SkillResult(text="done", metadata={"artifact": "xyz"})

    registry = SkillRegistry()
    registry.register(_StubSkill())
    provider = FakeProvider(
        default_reply="Here it is.",
        results=[make_tool_call_result("stub_tool", {})],
    )
    from jarvis.core.container import ServiceContainer
    from jarvis.core.engine import JarvisEngine
    from jarvis.llm.client import LLMClient

    container = ServiceContainer(settings, llm_client=LLMClient(primary=provider),
                                skill_registry=registry)
    engine = JarvisEngine(container=container)

    response = await engine.process(Request(text="use the stub tool"))
    assert response.metadata == {"artifact": "xyz"}


@pytest.mark.asyncio
async def test_multiple_tool_calls_in_one_round_all_execute(settings):
    from jarvis.llm.base import LLMResult
    from jarvis.llm.tools import ToolCall

    provider = FakeProvider(
        default_reply="Both done.",
        results=[LLMResult(
            text="", model="fake-model", provider="fake", stop_reason="tool_use",
            output_tokens=3,
            tool_calls=[
                ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"}),
                ToolCall(id="call_2", name="calculator", arguments={"expression": "2+2"}),
            ],
        )],
    )
    engine = build_engine(settings, provider)
    response = await engine.process(Request(text="compute two things"))
    assert response.text == "Both done."
    # Both tool calls from the single round were executed (not just the first).
    assert "[tool_results x2]" in provider.calls[-1][-1]["content"]


# -- screen sharing -----------------------------------------------------------


@pytest.mark.asyncio
async def test_share_screen_off_by_default_keeps_plain_text_messages(engine, fake_provider):
    await engine.ask("hello")
    assert isinstance(fake_provider.calls[-1][-1]["content"], str)


@pytest.mark.asyncio
async def test_share_screen_on_attaches_a_vision_message(settings):
    from jarvis.skills.base import BaseSkill, SkillResult
    from jarvis.skills.registry import SkillRegistry

    class _StubCapture(BaseSkill):
        name = "desktop.capture_screen"
        description = "test-only"

        def can_handle(self, text: str) -> bool:
            return False

        async def handle(self, text: str, context=None) -> SkillResult:
            return SkillResult.not_handled()

        async def execute(self, context=None, **_: object) -> SkillResult:
            return SkillResult(text="Captured.", metadata={"image_png_b64": "ZmFrZQ=="})

    registry = SkillRegistry()
    registry.register(_StubCapture())
    provider = FakeProvider(default_reply="I can see it.")
    from jarvis.core.container import ServiceContainer
    from jarvis.core.engine import JarvisEngine
    from jarvis.llm.client import LLMClient

    container = ServiceContainer(settings, llm_client=LLMClient(primary=provider),
                                skill_registry=registry)
    engine = JarvisEngine(container=container)
    engine.session("default").scratch["share_screen"] = True

    await engine.process(Request(text="what's on my screen?"))

    sent = provider.calls[-1][-1]
    assert isinstance(sent["content"], list)
    image_part = next(p for p in sent["content"] if p["type"] == "image_url")
    assert "ZmFrZQ==" in image_part["image_url"]["url"]
    # The persisted conversation history stays plain text — only the outgoing
    # wire message for this call carries the image.
    history_turn = engine.session("default").conversation.messages[0]
    assert history_turn.content == "what's on my screen?"


@pytest.mark.asyncio
async def test_share_screen_on_but_denied_falls_back_to_plain_text(engine, fake_provider):
    # desktop_enabled=True by default but allow_desktop_control is off, so the
    # capture skill itself refuses (PermissionDenied) — this must not crash
    # the turn, just skip attaching an image.
    engine.session("default").scratch["share_screen"] = True
    reply = await engine.ask("what's on my screen?")
    assert reply == "Certainly, Sir."
    assert isinstance(fake_provider.calls[-1][-1]["content"], str)


@pytest.mark.asyncio
async def test_share_screen_on_but_desktop_disabled_fails_open(settings):
    # No desktop skills registered at all -> invoke_tool raises
    # SkillNotFoundError; _attach_screen must swallow it, not crash the turn.
    settings.desktop_enabled = False
    provider = FakeProvider(default_reply="ok")
    engine = build_engine(settings, provider)
    engine.session("default").scratch["share_screen"] = True

    reply = await engine.ask("what's on my screen?")
    assert reply == "ok"
    assert isinstance(provider.calls[-1][-1]["content"], str)


# -- streaming --------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_llm_reply(engine):
    chunks = [c async for c in engine.stream(Request(text="stream me a poem"))]
    assert "".join(chunks) == "Certainly, Sir."


@pytest.mark.asyncio
async def test_stream_skill_reply_single_chunk(engine):
    chunks = [c async for c in engine.stream(Request(text="system status"))]
    assert len(chunks) == 1
    assert "Version" in chunks[0]


# -- multi-session ----------------------------------------------------------


@pytest.mark.asyncio
async def test_sessions_are_isolated(engine):
    await engine.ask("remember A", session_id="alice")
    await engine.ask("remember B", session_id="bob")
    assert len(engine.session("alice").conversation) == 2
    assert len(engine.session("bob").conversation) == 2
    # Different objects, no cross-contamination.
    assert engine.session("alice") is not engine.session("bob")
