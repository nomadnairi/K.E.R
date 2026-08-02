"""Tests for the system-prompt persona (jarvis/llm/prompts.py)."""

from __future__ import annotations

from jarvis.llm.prompts import PromptBuilder


def test_persona_instructs_the_model_to_act_not_narrate():
    builder = PromptBuilder(assistant_name="KER", user_name="Sir")
    persona = builder.persona()
    assert "call the matching tool" in persona


def test_persona_instructs_honest_reporting_of_tool_outcomes():
    builder = PromptBuilder(assistant_name="KER", user_name="Sir")
    persona = builder.persona()
    assert "never invent a success" in persona


def test_system_prompt_includes_the_acting_section():
    builder = PromptBuilder(assistant_name="KER", user_name="Sir")
    prompt = builder.system_prompt(include_time=False)
    assert "Acting in the real world" in prompt
