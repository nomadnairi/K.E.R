"""
SQLite-backed semantic vector store.

Stores :class:`MemoryRecord` items with their embedding in SQLite and recalls
them by relevance. Unlike the JSON-backed :class:`InMemoryVectorStore`, writes
are **incremental** (a single INSERT), so remembering is O(1) on disk instead
of rewriting the whole store each time.

Recall combines cosine similarity with an optional **recency** boost and drops
matches below a **similarity threshold**, so weak or stale memories don't
pollute the prompt. Similarity is still computed in Python (adequate for tens
of thousands of records); a true ANN index is a later optimisation.
"""

from __future__ import annotations

import json
import sqlite3
import struct
import threading
from datetime import datetime, timezone
from math import exp
from pathlib import Path

from jarvis.memory.base import BaseEmbedder, BaseMemoryStore, MemoryRecord
from jarvis.memory.embeddings import cosine_similarity
from jarvis.security.crypto import KeyProvider, SecretBox
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    kind        TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   BLOB NOT NULL,
    timestamp   TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id);
"""


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


class SQLiteVectorStore(BaseMemoryStore):
    """A persistent vector store backed by SQLite."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        db_path: str = "data/jarvis.db",
        *,
        min_score: float = 0.15,
        recency_weight: float = 0.15,
        recency_half_life_days: float = 7.0,
        max_per_session: int = 0,
        dedup_threshold: float = 0.0,
        secret_box: SecretBox | None = None,
    ) -> None:
        self.embedder = embedder
        self.db_path = db_path
        # Memory content is encrypted at rest when a key is configured
        # (KER_DATA_KEY); with no key this is a transparent pass-through.
        self._box = secret_box if secret_box is not None else KeyProvider.box()
        self.min_score = min_score
        self.recency_weight = max(0.0, min(1.0, recency_weight))
        self.recency_half_life_s = recency_half_life_days * 86400.0
        self.max_per_session = max_per_session
        self.dedup_threshold = dedup_threshold
        self._lock = threading.Lock()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- write --------------------------------------------------------------

    def remember(self, record: MemoryRecord) -> None:
        embedding = self.embedder.embed(record.content)
        with self._lock:
            if self._is_duplicate(record.session_id, embedding):
                logger.debug("Skipping near-duplicate memory for %s", record.session_id)
                return
            self._conn.execute(
                "INSERT INTO memories (session_id, kind, content, embedding, "
                "timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.session_id,
                    record.kind,
                    self._box.encrypt(record.content, aad=record.session_id),
                    _pack(embedding),
                    record.timestamp.isoformat(),
                    json.dumps(record.metadata),
                ),
            )
            self._conn.commit()
            self._evict(record.session_id)

    def _is_duplicate(self, session_id: str, embedding: list[float]) -> bool:
        """Whether an existing memory is similar enough to skip storing."""
        if not (0.0 < self.dedup_threshold < 1.0):
            return False
        rows = self._conn.execute(
            "SELECT embedding FROM memories WHERE session_id = ?", (session_id,)
        ).fetchall()
        return any(
            cosine_similarity(embedding, _unpack(row["embedding"])) >= self.dedup_threshold
            for row in rows
        )

    def _evict(self, session_id: str) -> None:
        """Keep at most ``max_per_session`` memories, dropping the oldest."""
        if self.max_per_session <= 0:
            return
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM memories WHERE session_id = ?", (session_id,)
        ).fetchone()
        excess = int(row["n"]) - self.max_per_session
        if excess <= 0:
            return
        self._conn.execute(
            "DELETE FROM memories WHERE id IN ("
            "  SELECT id FROM memories WHERE session_id = ? ORDER BY id ASC LIMIT ?"
            ")",
            (session_id, excess),
        )
        self._conn.commit()

    # -- read ---------------------------------------------------------------

    def recall(self, query: str, *, session_id: str | None = "default",
            limit: int = 5) -> list[MemoryRecord]:
        q = self.embedder.embed(query)
        if session_id is None:
            sql = "SELECT * FROM memories"
            params: tuple = ()
        else:
            sql = "SELECT * FROM memories WHERE session_id = ?"
            params = (session_id,)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        now = datetime.now(timezone.utc)
        scored: list[MemoryRecord] = []
        for row in rows:
            similarity = cosine_similarity(q, _unpack(row["embedding"]))
            if similarity < self.min_score:
                continue
            final = self._apply_recency(similarity, row["timestamp"], now)
            scored.append(
                MemoryRecord(
                    content=self._box.decrypt(row["content"],
                                            aad=row["session_id"]),
                    session_id=row["session_id"],
                    kind=row["kind"],
                    score=final,
                    metadata=json.loads(row["metadata"]),
                )
            )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    def _apply_recency(self, similarity: float, ts_iso: str,
                    now: datetime) -> float:
        if self.recency_weight <= 0.0:
            return similarity
        try:
            ts = datetime.fromisoformat(ts_iso)
        except ValueError:
            return similarity
        age = max(0.0, (now - ts).total_seconds())
        recency = exp(-age / self.recency_half_life_s)  # 1.0 (now) → 0.0 (old)
        return (1.0 - self.recency_weight) * similarity + self.recency_weight * recency

    # -- delete -------------------------------------------------------------

    def forget(self, session_id: str | None = "default") -> None:
        with self._lock:
            if session_id is None:
                self._conn.execute("DELETE FROM memories")
            else:
                self._conn.execute(
                    "DELETE FROM memories WHERE session_id = ?", (session_id,)
                )
            self._conn.commit()

    def delete(self, record_id: int) -> bool:
        """Remove one memory by id."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM memories WHERE id = ?",
                                    (int(record_id),))
            self._conn.commit()
        return cur.rowcount > 0

    # -- introspection ------------------------------------------------------

    def browse(self, *, session_id: str | None = None, limit: int = 100,
            offset: int = 0) -> list[MemoryRecord]:
        """Stored memories, newest first — what a person is actually shown."""
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        sql = "SELECT * FROM memories"
        params: tuple = ()
        if session_id is not None:
            sql += " WHERE session_id = ?"
            params = (session_id,)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        with self._lock:
            rows = self._conn.execute(sql, (*params, limit, offset)).fetchall()
        out: list[MemoryRecord] = []
        for row in rows:
            try:
                ts = datetime.fromisoformat(row["timestamp"])
            except ValueError:
                ts = datetime.now(timezone.utc)
            out.append(MemoryRecord(
                content=self._box.decrypt(row["content"],
                                        aad=row["session_id"]),
                session_id=row["session_id"],
                kind=row["kind"],
                timestamp=ts,
                metadata=json.loads(row["metadata"]),
                record_id=int(row["id"]),
            ))
        return out

    def can_browse(self) -> bool:
        return True

    def count(self, session_id: str | None = None) -> int:
        with self._lock:
            if session_id is None:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM memories"
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM memories WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
        return int(row["n"])

    def close(self) -> None:  # pragma: no cover - lifecycle
        with self._lock:
            self._conn.close()
