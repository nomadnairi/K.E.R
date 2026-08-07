"""
Единая точка входа для уведомлений в Desktop (Этап 2 / Фаза B2).

До этого модуля push из Python в интерфейс был россыпью ad hoc механизмов:
``runJavaScript()`` на конкретные события, прямой ``QMessageBox`` из
апдейтера, и proactive-сообщения, которые в WebView-сборке вообще падали
внутри Qt-слота (``_on_proactive`` трогало ``self.transcript``, которого без
нативного fallback-режима не существует — см. регрессию, которую чинит этот
модуль). ``NotificationCenter`` — то место, куда что-либо *записывается*
в первую очередь; тост/чат-пузырь — лишь побочный эффект показа, поэтому
ничего не теряется, если тост не увидели (окно было свёрнуто, WebView ещё не
успел загрузиться и т.д.).

Хранится как JSON-файл рядом с ``desktop.json``, не в БД: объём небольшой на
одну установку, ротация по количеству записей, а не по времени — этого
достаточно для локального «журнала уведомлений одного приложения» и не тянет
за собой SQLite для десятков записей.

Импортируемо без Qt (как ``config.py``), чтобы оставаться тестируемым
headless и не тянуть PySide6 туда, где он не нужен.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Notification:
    """One entry in the log — a proactive message, an update, or (later) an
    AI Runtime event (agent started, goal finished, ...)."""

    text: str
    #: "proactive" | "update" | "info" | ... — free-form, the deck decides
    #: how to render each kind; new kinds need no schema change here.
    kind: str = "info"
    created_at: float = field(default_factory=time.time)
    read: bool = False

    def as_dict(self) -> dict:
        return {"text": self.text, "kind": self.kind,
                "created_at": self.created_at, "read": self.read}


class NotificationCenter:
    """Append-only log of notifications, capped and persisted to disk."""

    #: Oldest entries are dropped past this — a rolling window, not history.
    MAX_KEPT = 200

    def __init__(self, path: Path) -> None:
        self.path = path
        self._items: list[Notification] = self._load()

    @classmethod
    def default_path(cls, config_dir: Path | None = None) -> Path:
        from jarvis.desktop_app.config import default_config_dir
        return (config_dir or default_config_dir()) / "notifications.json"

    def _load(self) -> list[Notification]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items: list[Notification] = []
        for row in raw if isinstance(raw, list) else []:
            try:
                items.append(Notification(
                    text=str(row["text"]), kind=str(row.get("kind", "info")),
                    created_at=float(row.get("created_at", time.time())),
                    read=bool(row.get("read", False))))
            except (KeyError, TypeError, ValueError):
                continue  # a corrupt row is dropped, not fatal to the rest
        return items

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        kept = self._items[-self.MAX_KEPT:]
        self.path.write_text(json.dumps([n.as_dict() for n in kept]),
                            encoding="utf-8")

    def add(self, text: str, *, kind: str = "info") -> Notification:
        note = Notification(text=text, kind=kind)
        self._items.append(note)
        if len(self._items) > self.MAX_KEPT:
            self._items = self._items[-self.MAX_KEPT:]
        self._save()
        return note

    def list(self, limit: int = 50) -> list[dict]:
        """Most recent first — what a Notifications panel would render."""
        return [n.as_dict() for n in reversed(self._items[-limit:])]

    def unread_count(self) -> int:
        return sum(1 for n in self._items if not n.read)

    def mark_all_read(self) -> None:
        if not any(not n.read for n in self._items):
            return
        for n in self._items:
            n.read = True
        self._save()
