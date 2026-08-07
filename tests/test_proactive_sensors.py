"""Tests for the proactive engine's sensors."""

from __future__ import annotations

import pytest

from jarvis.proactive.sensors.system_health import SystemHealthSensor


def _patch_sample(monkeypatch, cpu: int | None, ram: int | None) -> None:
    monkeypatch.setattr(SystemHealthSensor, "_sample",
                        staticmethod(lambda: (cpu, ram)))


@pytest.mark.asyncio
async def test_system_health_fires_after_sustained_breach(monkeypatch):
    sensor = SystemHealthSensor(cpu_threshold_pct=90, consecutive_ticks=2)
    _patch_sample(monkeypatch, cpu=96, ram=50)

    # First breach: not sustained yet -> no signal.
    assert await sensor.check(user_id="u1", scratch={}) is None
    # Second consecutive breach: sustained -> signal.
    signal = await sensor.check(user_id="u1", scratch={})
    assert signal is not None
    assert signal.sensor == "system_health"
    assert "96%" in signal.summary


@pytest.mark.asyncio
async def test_system_health_resets_streak_when_back_to_normal(monkeypatch):
    sensor = SystemHealthSensor(cpu_threshold_pct=90, consecutive_ticks=2)
    _patch_sample(monkeypatch, cpu=96, ram=50)
    assert await sensor.check(user_id="u1", scratch={}) is None  # streak=1

    _patch_sample(monkeypatch, cpu=10, ram=10)
    assert await sensor.check(user_id="u1", scratch={}) is None  # resets

    _patch_sample(monkeypatch, cpu=96, ram=50)
    assert await sensor.check(user_id="u1", scratch={}) is None  # streak=1 again, not 2


@pytest.mark.asyncio
async def test_system_health_streak_is_per_user(monkeypatch):
    sensor = SystemHealthSensor(cpu_threshold_pct=90, consecutive_ticks=2)
    _patch_sample(monkeypatch, cpu=96, ram=50)

    await sensor.check(user_id="u1", scratch={})
    await sensor.check(user_id="u1", scratch={})  # u1 now at streak 2 -> fired
    # A different user starts fresh, doesn't inherit u1's streak.
    assert await sensor.check(user_id="u2", scratch={}) is None


@pytest.mark.asyncio
async def test_system_health_no_signal_below_threshold(monkeypatch):
    sensor = SystemHealthSensor(cpu_threshold_pct=90, mem_threshold_pct=90)
    _patch_sample(monkeypatch, cpu=20, ram=30)
    assert await sensor.check(user_id="u1", scratch={}) is None


@pytest.mark.asyncio
async def test_system_health_skips_when_psutil_unavailable(monkeypatch):
    sensor = SystemHealthSensor(consecutive_ticks=1)
    _patch_sample(monkeypatch, cpu=None, ram=None)
    assert await sensor.check(user_id="u1", scratch={}) is None
