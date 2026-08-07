"""Notices when the machine KER is running on is under sustained load.

Samples the same primitives ``jarvis/api/app.py``'s dashboard ``_system_stats``
already uses -- ``psutil`` is optional there and here for the same reason: a
deployment without it (or without permission to read it) just never fires
this sensor, rather than crashing the proactive loop.
"""

from __future__ import annotations

from jarvis.proactive.models import Signal
from jarvis.proactive.sensors.base import ProactiveSensor


class SystemHealthSensor(ProactiveSensor):
    """Fires when CPU or RAM stays above threshold for a few consecutive ticks.

    A single instant sample is noisy (a one-off spike is normal), so this
    only reports *sustained* load -- ``consecutive_ticks`` in a row above the
    threshold -- rather than reacting to every momentary blip. This is still
    just a cheap mechanical pre-filter: whether sustained high load is worth
    mentioning to the user is the LLM decision step's call, not this class's.
    """

    name = "system_health"

    def __init__(self, cpu_threshold_pct: int = 90, mem_threshold_pct: int = 90,
                consecutive_ticks: int = 2) -> None:
        self.cpu_threshold_pct = cpu_threshold_pct
        self.mem_threshold_pct = mem_threshold_pct
        self.consecutive_ticks = max(1, consecutive_ticks)
        self._streak: dict[str, int] = {}

    @staticmethod
    def _sample() -> tuple[int | None, int | None]:
        try:
            import psutil
            return (int(psutil.cpu_percent(interval=0.0)),
                    int(psutil.virtual_memory().percent))
        except Exception:  # noqa: BLE001 - psutil optional; just skip this tick
            return None, None

    async def check(self, *, user_id: str, scratch: dict) -> Signal | None:
        cpu, ram = self._sample()
        if cpu is None or ram is None:
            return None

        breached = cpu >= self.cpu_threshold_pct or ram >= self.mem_threshold_pct
        if not breached:
            self._streak[user_id] = 0
            return None

        streak = self._streak.get(user_id, 0) + 1
        self._streak[user_id] = streak
        if streak < self.consecutive_ticks:
            return None

        parts = []
        if cpu >= self.cpu_threshold_pct:
            parts.append(f"CPU at {cpu}%")
        if ram >= self.mem_threshold_pct:
            parts.append(f"memory at {ram}%")
        return Signal(
            sensor=self.name,
            summary=f"The machine has had {' and '.join(parts)} for a while now.",
            detail=f"cpu={cpu}% mem={ram}% (thresholds: cpu>={self.cpu_threshold_pct}% "
                    f"mem>={self.mem_threshold_pct}%, sustained for "
                    f"{self.consecutive_ticks} checks)",
            severity="notable",
        )
