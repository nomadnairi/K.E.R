"""Tests for the skill system and built-in skills."""

from __future__ import annotations

import pytest

from jarvis.skills.base import BaseSkill, SkillResult
from jarvis.skills.builtin.calculator_skill import CalculatorSkill, evaluate
from jarvis.skills.builtin.datetime_skill import DateTimeSkill
from jarvis.skills.builtin.system_skill import SystemSkill
from jarvis.skills.registry import SkillRegistry
from jarvis.utils.exceptions import SkillNotFoundError, SkillRegistrationError


class _EchoSkill(BaseSkill):
    name = "echo"
    description = "Echo the input."
    priority = 10

    def can_handle(self, text: str) -> bool:
        return text.startswith("echo ")

    async def handle(self, text: str, context=None) -> SkillResult:
        return SkillResult(text=text[len("echo "):])


@pytest.mark.asyncio
async def test_register_and_dispatch():
    reg = SkillRegistry()
    reg.register(_EchoSkill())
    result = await reg.dispatch("echo hello")
    assert result.handled is True
    assert result.text == "hello"


@pytest.mark.asyncio
async def test_no_match_returns_not_handled():
    reg = SkillRegistry()
    reg.register(_EchoSkill())
    result = await reg.dispatch("something else")
    assert result.handled is False


def test_duplicate_registration_rejected():
    reg = SkillRegistry()
    reg.register(_EchoSkill())
    with pytest.raises(SkillRegistrationError):
        reg.register(_EchoSkill())


def test_priority_ordering():
    reg = SkillRegistry()

    class _Low(_EchoSkill):
        name = "low"
        priority = 1

    class _High(_EchoSkill):
        name = "high"
        priority = 100

    reg.register(_Low())
    reg.register(_High())
    assert reg.find("echo x").name == "high"


def test_datetime_skill_matches_time_question():
    skill = DateTimeSkill()
    assert skill.can_handle("what time is it")
    assert not skill.can_handle("tell me a joke")


@pytest.mark.asyncio
async def test_system_skill_reports_version():
    skill = SystemSkill()
    assert skill.can_handle("system status")
    result = await skill.handle("system status")
    assert "Version" in result.text


# -- tool path --------------------------------------------------------------


def test_tool_specs_only_include_exposed_skills():
    reg = SkillRegistry()
    reg.register_many([DateTimeSkill(), SystemSkill(), CalculatorSkill(), _EchoSkill()])
    names = {spec.name for spec in reg.tool_specs()}
    # Echo has no parameters -> not a tool; the others are exposed.
    assert "echo" not in names
    assert {"get_datetime", "system_status", "calculator"} <= names


@pytest.mark.asyncio
async def test_invoke_tool_runs_calculator():
    reg = SkillRegistry()
    reg.register(CalculatorSkill())
    result = await reg.invoke_tool("calculator", {"expression": "(12.5/100)*320"})
    assert "40" in result.text


@pytest.mark.asyncio
async def test_invoke_unknown_tool_raises():
    reg = SkillRegistry()
    with pytest.raises(SkillNotFoundError):
        await reg.invoke_tool("nope", {})


@pytest.mark.asyncio
async def test_invoke_tool_passes_context_through():
    class _ContextAwareSkill(BaseSkill):
        name = "ctx_probe"
        description = "test-only"
        parameters = {"type": "object", "properties": {}}

        def can_handle(self, text: str) -> bool:
            return False

        async def handle(self, text: str, context=None) -> SkillResult:
            return SkillResult.not_handled()

        async def execute(self, context=None, **_: object) -> SkillResult:
            return SkillResult(text=str(context))

    reg = SkillRegistry()
    reg.register(_ContextAwareSkill())
    reg.register(CalculatorSkill())
    result = await reg.invoke_tool("ctx_probe", {}, context={"scratch": "value"})
    assert result.text == "{'scratch': 'value'}"
    # A skill that ignores context (like every built-in) isn't broken by it.
    result2 = await reg.invoke_tool("calculator", {"expression": "1+1"},
                                    context={"anything": True})
    assert "2" in result2.text


def test_calculator_safe_eval():
    assert evaluate("2 + 3 * 4") == 14
    assert evaluate("(1+1) ** 10") == 1024


def test_calculator_rejects_code():
    import pytest as _pytest

    with _pytest.raises(ValueError):
        evaluate("__import__('os').system('ls')")
