"""The proactive engine: per-user loop that notices things and speaks up.

Runs alongside (not instead of, and never touching) the existing
``_proactive_worker`` in ``jarvis/interfaces/telegram_bot.py``, which keeps
handling reminders/automations/idle-nudges exactly as it always has. This
engine only ever *sends a message* -- it never executes a tool or action
unprompted; that boundary is a deliberate, separate design decision.
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Protocol

from jarvis.core.engine import JarvisEngine
from jarvis.i18n import language_name
from jarvis.config.settings import Settings
from jarvis.proactive.decision import should_speak
from jarvis.proactive.models import Signal
from jarvis.proactive.sensors.base import ProactiveSensor
from jarvis.proactive.sensors.system_health import SystemHealthSensor
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

#: Delivers a message to one user; the caller wires this to the real
#: transport (e.g. ``lambda chat_id, text: bot.send_message(int(chat_id), text)``).
SendFn = Callable[[str, str], Awaitable[None]]


class ProactivePrefs(Protocol):
    """The two calls this engine actually needs from a prefs store.

    ``jarvis.interfaces.user_prefs.UserPreferences`` (multi-user, SQLite)
    satisfies this already; the desktop app's single-user
    ``LocalProactivePrefs`` (`jarvis/desktop_app/proactive_prefs.py`) is a
    tiny duck-typed alternative -- neither needs to subclass anything.
    """

    def list_proactive(self) -> list: ...
    def get_assistant_name(self, user_id: int | str) -> str | None: ...


class ProactiveEngine:
    """Polls sensors for every opted-in user and speaks up when warranted."""

    def __init__(self, engine: JarvisEngine, prefs: ProactivePrefs,
                settings: Settings, sensors: list[ProactiveSensor] | None = None,
                session_id_for: Callable[[str], str] = lambda user_id: user_id) -> None:
        self.engine = engine
        self.prefs = prefs
        self.settings = settings
        self.sensors = sensors if sensors is not None else self._default_sensors(settings)
        #: Maps a prefs row's user_id to the engine session id actually used
        #: for that channel (e.g. Telegram's "tg-<id>", vs. the desktop app's
        #: "desktop" session id, which already matches identically).
        self.session_id_for = session_id_for
        #: user_id -> last-proactive-message timestamp (process-lifetime,
        #: same precedent as _proactive_worker's own nudged/sent_morning dicts).
        self._last_sent: dict[str, float] = {}

    @staticmethod
    def _default_sensors(settings: Settings) -> list[ProactiveSensor]:
        sensors: list[ProactiveSensor] = []
        if settings.proactive_system_health_enabled:
            sensors.append(SystemHealthSensor(
                cpu_threshold_pct=settings.proactive_cpu_threshold_pct,
                mem_threshold_pct=settings.proactive_mem_threshold_pct,
            ))
        return sensors

    # -- one pass over every opted-in user -----------------------------------

    async def tick(self, send: SendFn) -> int:
        """Run one check pass. Returns how many messages were actually sent."""
        if not self.settings.proactive_sensors_enabled or not self.sensors:
            return 0

        now = time.time()
        sem = asyncio.Semaphore(self.settings.proactive_max_concurrent)
        sent = 0

        async def handle_one(raw_row) -> None:
            nonlocal sent
            # prefs.list_proactive() returns sqlite3.Row objects (no .get()) in
            # production, but tests pass plain dicts -- normalise once here.
            row = dict(raw_row)
            user_id = str(row.get("user_id", ""))
            chat_id = row.get("chat_id")
            if not user_id or not chat_id:
                return
            if now - self._last_sent.get(user_id, 0) < self.settings.proactive_cooldown_seconds:
                return

            async with sem:
                signals = await self._collect_signals(user_id)
            if not signals:
                return

            language = row.get("language")
            text = await should_speak(
                llm=self.engine.llm, prompts=self.engine.prompts,
                settings=self.settings, signals=signals,
                language=language_name(language) if language else None,
                assistant_name=self.prefs.get_assistant_name(user_id),
            )
            if not text:
                return

            try:
                await send(str(chat_id), text)
            except Exception:  # noqa: BLE001 - one user's delivery failure
                logger.warning("Proactive send failed for user %s", user_id,
                                exc_info=True)
                return
            # So a later reply that references this has it in context -- a
            # NOTHING decision never reaches here, so history stays clean.
            session_id = self.session_id_for(user_id)
            self.engine.session(session_id).conversation.add_assistant(text)
            self._last_sent[user_id] = now
            sent += 1

        await asyncio.gather(*(handle_one(row) for row in self.prefs.list_proactive()))
        return sent

    async def _collect_signals(self, user_id: str) -> list[Signal]:
        results = await asyncio.gather(
            *(self._safe_check(sensor, user_id) for sensor in self.sensors)
        )
        return [signal for signal in results if signal is not None]

    async def _safe_check(self, sensor: ProactiveSensor, user_id: str) -> Signal | None:
        try:
            return await sensor.check(user_id=user_id, scratch={})
        except Exception:  # noqa: BLE001 - one sensor's bug must not sink the tick
            logger.warning("Proactive sensor %r failed for user %s", sensor.name,
                            user_id, exc_info=True)
            return None

    # -- the long-running loop ------------------------------------------------

    async def run(self, send: SendFn) -> None:
        """Tick forever until cancelled -- mirrors _proactive_worker's shape."""
        while True:
            try:
                await self.tick(send)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - keep the loop alive
                logger.warning("Proactive engine tick failed", exc_info=True)
            await asyncio.sleep(self.settings.proactive_sensor_interval_seconds)
