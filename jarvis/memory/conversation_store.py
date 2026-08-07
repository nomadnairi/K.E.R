"""
Persistent conversation store (SQLite).

Persists conversation turns per session so history survives process restarts.
Uses the standard-library :mod:`sqlite3` — no external database or driver
required. Thread-safe for the simple, low-concurrency access patterns of an
assistant (one connection with a lock).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from jarvis.config.constants import Role
from jarvis.memory.base import like_prefix_pattern
from jarvis.models.message import Conversation, Message
from jarvis.security.crypto import KeyProvider, SecretBox
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
"""


class SQLiteConversationStore:
    """Stores and loads conversation history in a SQLite database."""

    def __init__(self, db_path: str = "data/jarvis.db",
                 secret_box: SecretBox | None = None) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        # Chat text is encrypted at rest when a key is configured
        # (KER_DATA_KEY); with no key this is a transparent pass-through.
        self._box = secret_box if secret_box is not None else KeyProvider.box()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- write --------------------------------------------------------------

    def append(self, session_id: str, message: Message) -> None:
        """Persist a single message for ``session_id``."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (session_id, message.role.value,
                self._box.encrypt(message.content, aad=session_id),
                message.timestamp.isoformat()),
            )
            self._conn.commit()

    def append_exchange(self, session_id: str, user: str, assistant: str) -> None:
        """Persist a user message and the assistant's reply together."""
        self.append(session_id, Message.user(user))
        self.append(session_id, Message.assistant(assistant))

    # -- read ---------------------------------------------------------------

    def load(self, session_id: str, *, limit: int | None = None) -> Conversation:
        """Load a session's history into a :class:`Conversation`."""
        query = (
            "SELECT role, content, timestamp FROM messages "
            "WHERE session_id = ? ORDER BY id ASC"
        )
        with self._lock:
            rows = self._conn.execute(query, (session_id,)).fetchall()
        if limit is not None:
            rows = rows[-limit:]
        conversation = Conversation()
        for row in rows:
            conversation.messages.append(
                Message(role=Role(row["role"]),
                        content=self._box.decrypt(row["content"],
                                                aad=session_id))
            )
        return conversation

    def sessions(self, *, session_prefix: str | None = None) -> list[str]:
        """Return all known session ids, optionally scoped to one tenant."""
        with self._lock:
            if session_prefix is not None:
                rows = self._conn.execute(
                    "SELECT DISTINCT session_id FROM messages WHERE session_id "
                    "LIKE ? ESCAPE '\\'", (like_prefix_pattern(session_prefix),),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT DISTINCT session_id FROM messages"
                ).fetchall()
        return [row["session_id"] for row in rows]

    def recent(self, limit: int = 20, *,
            session_prefix: str | None = None) -> list[dict]:
        """Recent sessions, newest first: id, title, message count, last time.

        ``title`` is the first user message (a natural conversation title).
        With ``session_prefix`` set, only sessions belonging to that tenant
        are considered — otherwise every account sharing this engine would
        see everyone's conversation titles in their own session list.
        """
        where = ""
        params: tuple = (max(1, limit),)
        if session_prefix is not None:
            where = "WHERE session_id LIKE ? ESCAPE '\\' "
            params = (like_prefix_pattern(session_prefix), max(1, limit))
        with self._lock:
            rows = self._conn.execute(
                "SELECT session_id, MAX(timestamp) AS last_ts, COUNT(*) AS n, "
                "(SELECT content FROM messages m2 WHERE m2.session_id = m.session_id "
                " AND m2.role = 'user' ORDER BY m2.id ASC LIMIT 1) AS title "
                f"FROM messages m {where}GROUP BY session_id "
                "ORDER BY last_ts DESC LIMIT ?",
                params,
            ).fetchall()
        out: list[dict] = []
        for r in rows:
            raw_title = self._box.decrypt(r["title"] or "",
                                        aad=r["session_id"])
            title = (raw_title or "").strip() or "Диалог"
            out.append({"session_id": r["session_id"],
                        "title": title[:60],
                        "count": int(r["n"]),
                        "last_ts": r["last_ts"]})
        return out

    def count(self, session_id: str | None = None, *,
            session_prefix: str | None = None) -> int:
        with self._lock:
            if session_prefix is not None:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM messages WHERE session_id LIKE ? "
                    "ESCAPE '\\'", (like_prefix_pattern(session_prefix),),
                ).fetchone()
            elif session_id is None:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM messages"
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
        return int(row["n"])

    # -- delete -------------------------------------------------------------

    def clear(self, session_id: str | None = None, *,
            session_prefix: str | None = None) -> None:
        with self._lock:
            if session_prefix is not None:
                self._conn.execute(
                    "DELETE FROM messages WHERE session_id LIKE ? ESCAPE '\\'",
                    (like_prefix_pattern(session_prefix),))
            elif session_id is None:
                self._conn.execute("DELETE FROM messages")
            else:
                self._conn.execute(
                    "DELETE FROM messages WHERE session_id = ?", (session_id,)
                )
            self._conn.commit()

    def close(self) -> None:  # pragma: no cover - lifecycle
        with self._lock:
            self._conn.close()
