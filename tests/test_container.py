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


def test_desktop_controller_override_is_used_instead_of_the_default(settings):
    # The API server passes a controller of its own (relay-or-refuse, never
    # touching pyautogui/webbrowser directly) instead of the real one every
    # local engine builds by default.
    sentinel = object()
    container = ServiceContainer(settings, desktop_controller=sentinel)
    registry = container.skills
    desktop_skill = next(s for s in registry.tool_specs() if s.name == "desktop.open_url")
    assert desktop_skill is not None  # still advertised
    # Fetch the actual skill instance to check which controller it was built with.
    live_skill = registry._skills["desktop.open_url"]  # noqa: SLF001 - test-only introspection
    assert live_skill.controller is sentinel


def test_devices_registry_is_shared_and_lazy(settings):
    from jarvis.desktop.device_registry import DeviceRegistry

    container = ServiceContainer(settings)
    assert isinstance(container.devices, DeviceRegistry)
    assert container.devices is container.devices  # cached, one instance
