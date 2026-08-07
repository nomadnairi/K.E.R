"""
Единый источник состояния запуска Desktop (Этап 2 / Фаза B3).

До этого модуля запуск не имел вообще никакого видимого состояния: между
``QApplication([])`` и ``window.show()`` пользователь видел только пустой
экран ОС — ни спиннера, ни прогресса, ни намёка на то, что происходит
(включая до 30 секунд немого блока на ``EngineThread.start()`` в
local-режиме). ``AppStatus`` — конечный автомат из явных стадий, с одной
точкой подписки на переходы, чтобы boot-сплэш, деково-показанный статус
синхронизации и будущие статусы AI Runtime ("агент работает", "цель
завершена") читали из одного источника вместо изобретения своего.

Qt-free (как ``config.py``/``notifications.py``) — переходы стадий и их
подписчики тестируются без GUI; :func:`jarvis.desktop_app.app.run_app`
подключает сюда Qt-виджет (``QSplashScreen``) отдельным, тонким слоем.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable


class Stage(str, Enum):
    """Boot/sync stages, in the order a normal launch passes through them.

    ``DEGRADED`` is not a step in that sequence — it replaces ``READY``
    when the server could not be reached but a cached session let the app
    continue offline, so the user is told, not left to guess.
    """

    CONNECTING = "connecting"
    STARTING_ENGINE = "starting_engine"
    SYNCING = "syncing"
    READY = "ready"
    DEGRADED = "degraded"


#: Human-facing text for each stage. Russian, matching the rest of the boot
#: UI copy (login screen, tray messages) — this is not run through
#: jarvis.desktop_app.strings because it needs to render before AppConfig's
#: language is even known to matter to anything Qt has built yet.
STAGE_TEXT: dict[Stage, str] = {
    Stage.CONNECTING: "Проверяем сессию…",
    Stage.STARTING_ENGINE: "Запускаем AI Core…",
    Stage.SYNCING: "Синхронизируем данные…",
    Stage.READY: "Готово.",
    Stage.DEGRADED: "Сервер недоступен — офлайн-режим.",
}


class AppStatus:
    """Tiny observable finite-state machine for the boot/sync lifecycle.

    Not a Qt object on purpose: it needs to be constructible and testable
    without PySide6 installed, same as the rest of this package. A caller
    that wants Qt signals wraps :meth:`on_change` in one (see
    :func:`jarvis.desktop_app.app.run_app`'s splash-screen wiring) instead
    of this class depending on Qt itself.
    """

    def __init__(self) -> None:
        self.stage: Stage = Stage.CONNECTING
        self._listeners: list[Callable[[Stage, str], None]] = []

    def on_change(self, callback: Callable[[Stage, str], None]) -> None:
        """Register *callback* to run on every future transition.

        Does not fire for the current stage — a caller that needs the
        starting text too should read :attr:`stage`/``STAGE_TEXT`` once
        before registering, the same way it would read any other current
        value before subscribing to future changes.
        """
        self._listeners.append(callback)

    def set(self, stage: Stage) -> None:
        """Move to *stage* and notify every listener, even on a repeat."""
        self.stage = stage
        text = STAGE_TEXT.get(stage, "")
        for callback in list(self._listeners):
            callback(stage, text)
