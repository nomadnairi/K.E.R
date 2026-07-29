"""
Memory-subsystem contracts.

Defines the interfaces the memory layer is built on:

* :class:`MemoryRecord` — a single stored memory item.
* :class:`BaseEmbedder` — turns text into a vector for similarity search.
* :class:`BaseMemoryStore` — a semantic (vector) store: remember / recall /
  forget.

Concrete implementations live alongside this module (embeddings, vector store,
conversation store).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MemoryRecord:
    """A single stored memory item."""

    content: str
    session_id: str = "default"
    kind: str = "note"          # note | fact | preference | exchange | event ...
    score: float = 0.0          # relevance score (set on recall)
    timestamp: datetime = field(default_factory=_now)
    metadata: dict = field(default_factory=dict)
    #: Set by stores that can address one memory, so it can be listed and
    #: deleted individually. ``None`` means this store cannot address items.
    record_id: int | None = None

    def to_dict(self) -> dict:
        """JSON-serialisable representation (for disk persistence)."""
        return {
            "content": self.content,
            "session_id": self.session_id,
            "kind": self.kind,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryRecord":
        ts = data.get("timestamp")
        return cls(
            content=data["content"],
            session_id=data.get("session_id", "default"),
            kind=data.get("kind", "note"),
            timestamp=datetime.fromisoformat(ts) if ts else _now(),
            metadata=data.get("metadata", {}),
        )


class BaseEmbedder(ABC):
    """Turns text into a fixed-length embedding vector."""

    #: Dimensionality of the produced vectors.
    dimensions: int = 0

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for ``text``."""
        raise NotImplementedError

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed several texts (override for batch efficiency)."""
        return [self.embed(t) for t in texts]


class BaseMemoryStore(ABC):
    """Interface for semantic (vector) memory backends."""

    @abstractmethod
    def remember(self, record: MemoryRecord) -> None:
        """Persist a memory record."""
        raise NotImplementedError

    @abstractmethod
    def recall(self, query: str, *, session_id: str | None = "default",
            limit: int = 5) -> list[MemoryRecord]:
        """Return records relevant to ``query``, most relevant first.

        ``session_id=None`` searches across all sessions.
        """
        raise NotImplementedError

    @abstractmethod
    def forget(self, session_id: str | None = "default") -> None:
        """Delete stored memories (``None`` clears everything)."""
        raise NotImplementedError

    def count(self, session_id: str | None = None) -> int:  # pragma: no cover - default
        """Number of stored records (optionally scoped to a session)."""
        return 0

    # -- browsing -----------------------------------------------------------
    # Recall answers "what is relevant to this question". Showing a person what
    # their assistant remembers is a different question, so it gets its own
    # pair: list newest-first, and delete one item.

    def browse(self, *, session_id: str | None = None, limit: int = 100,
            offset: int = 0) -> list[MemoryRecord]:
        """Stored memories, newest first.

        Stores that cannot enumerate return an empty list — callers show that
        as "this backend cannot list memories", never as "you have none".
        """
        return []

    def can_browse(self) -> bool:
        """Whether :meth:`browse` and :meth:`delete` actually do something."""
        return False

    def delete(self, record_id: int) -> bool:
        """Remove one memory by id; ``False`` if it was not there."""
        return False
