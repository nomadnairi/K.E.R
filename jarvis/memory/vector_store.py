"""
In-memory semantic vector store.

Stores :class:`MemoryRecord` items together with their embedding and recalls
them by cosine similarity. Optionally persists to a JSON file so long-term
memory survives restarts — no external database required.

For larger deployments a drop-in Chroma backend implements the same
:class:`BaseMemoryStore` contract (see :mod:`jarvis.memory.chroma_store`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from jarvis.memory.base import BaseEmbedder, BaseMemoryStore, MemoryRecord
from jarvis.memory.embeddings import cosine_similarity
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _Entry:
    record: MemoryRecord
    embedding: list[float]


@dataclass
class InMemoryVectorStore(BaseMemoryStore):
    """A cosine-similarity vector store with optional JSON persistence."""

    embedder: BaseEmbedder
    persist_path: str | None = None
    min_score: float = 0.0
    _entries: list[_Entry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.persist_path:
            self._load()

    # -- write --------------------------------------------------------------

    def remember(self, record: MemoryRecord) -> None:
        embedding = self.embedder.embed(record.content)
        # Position is the id here: stable for as long as the store lives, which
        # is all a list-and-delete view needs.
        record.record_id = len(self._entries)
        self._entries.append(_Entry(record=record, embedding=embedding))
        self._save()

    # -- read ---------------------------------------------------------------

    def recall(self, query: str, *, session_id: str | None = "default",
            limit: int = 5) -> list[MemoryRecord]:
        if not self._entries:
            return []
        q = self.embedder.embed(query)
        scored: list[MemoryRecord] = []
        for entry in self._entries:
            if session_id is not None and entry.record.session_id != session_id:
                continue
            score = cosine_similarity(q, entry.embedding)
            if score <= self.min_score:
                continue
            rec = entry.record
            rec.score = score
            scored.append(rec)
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    # -- delete -------------------------------------------------------------

    def forget(self, session_id: str | None = "default") -> None:
        if session_id is None:
            self._entries.clear()
        else:
            self._entries = [
                e for e in self._entries if e.record.session_id != session_id
            ]
        self._save()

    def delete(self, record_id: int) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries
                        if e.record.record_id != record_id]
        if len(self._entries) == before:
            return False
        self._save()
        return True

    # -- introspection ------------------------------------------------------

    def browse(self, *, session_id: str | None = None, limit: int = 100,
            offset: int = 0) -> list[MemoryRecord]:
        """Stored memories, newest first."""
        picked = [e.record for e in self._entries
                if session_id is None or e.record.session_id == session_id]
        picked.reverse()
        offset = max(0, int(offset))
        return picked[offset:offset + max(1, min(int(limit), 500))]

    def can_browse(self) -> bool:
        return True

    def count(self, session_id: str | None = None) -> int:
        if session_id is None:
            return len(self._entries)
        return sum(1 for e in self._entries if e.record.session_id == session_id)

    # -- persistence --------------------------------------------------------

    def _save(self) -> None:
        if not self.persist_path:
            return
        path = Path(self.persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {"record": e.record.to_dict(), "embedding": e.embedding}
            for e in self._entries
        ]
        try:
            path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError as exc:  # pragma: no cover - disk edge case
            logger.warning("Could not persist memory to %s: %s", path, exc)

    def _load(self) -> None:
        path = Path(self.persist_path)  # type: ignore[arg-type]
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
            logger.warning("Could not load memory from %s: %s", path, exc)
            return
        self._entries = [
            _Entry(
                record=MemoryRecord.from_dict(item["record"]),
                embedding=item["embedding"],
            )
            for item in payload
        ]
        logger.debug("Loaded %d memory records from %s", len(self._entries), path)
