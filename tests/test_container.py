"""Tests for ServiceContainer's conditional skill wiring (jarvis/core/container.py)."""

from __future__ import annotations

from jarvis.core.container import ServiceContainer


def _tool_names(registry) -> set[str]:
    return {spec.name for spec in registry.tool_specs()}


def test_generate_image_tool_registered_when_enabled_and_keyed(settings):
    settings.image_enabled = True
    settings.openai_api_key = "sk-test"
    registry = ServiceContainer(settings).skills
    assert "generate_image" in _tool_names(registry)


def test_generate_image_tool_absent_when_disabled(settings):
    settings.image_enabled = False
    settings.openai_api_key = "sk-test"
    registry = ServiceContainer(settings).skills
    assert "generate_image" not in _tool_names(registry)


def test_generate_image_tool_absent_without_a_key(settings):
    settings.image_enabled = True
    settings.openai_api_key = ""
    settings.image_api_key = ""
    registry = ServiceContainer(settings).skills
    assert "generate_image" not in _tool_names(registry)
