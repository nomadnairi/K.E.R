"""
Optional ChromaDB-backed vector store.

Implements the same :class:`BaseMemoryStore` contract as
:class:`~jarvis.memory.vector_store.InMemoryVectorStore`, so it is a drop-in
replacement for larger, persistent deployments. ChromaDB is imported lazily;
the dependency is only needed if this backend is selected.
"""

from __future__ import annotations

import uuid

from jarvis.memory.base import BaseEmbedder, BaseMemoryStore, MemoryRecord
from jarvis.utils.exceptions import MemoryError as JarvisMemoryError
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class ChromaVectorStore(BaseMemoryStore):
    """A :class:`BaseMemoryStore` backed by ChromaDB."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        path: str = "chroma_db",
        collection: str = "jarvis_memory",
    ) -> None:
        self.embedder = embedder
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise JarvisMemoryError(
                "ChromaVectorStore requires the 'chromadb' package. "
                "Install it or use the default in-memory backend."
            ) from exc
        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(collection)

    def remember(self, record: MemoryRecord) -> None:
        embedding = self.embedder.embed(record.content)
        self._collection.add(
            ids=[uuid.uuid4().hex],
            embeddings=[embedding],
            documents=[record.content],
            metadatas=[{
                "session_id": record.session_id,
                "kind": record.kind,
                "timestamp": record.timestamp.isoformat(),
            }],
        )

    def _ids_matching_prefix(self, prefix: str) -> list[str]:
        """Ids of every record whose session belongs to ``prefix``.

        Chroma's ``where`` metadata filter has no prefix/contains operator
        (only equality, comparisons and set membership), so a tenant-scoped
        query can't be expressed in one call the way the SQLite store's
        ``LIKE`` can. This fetches ids + metadata (not the vectors) and
        filters in Python instead — fine at the scale this backend targets,
        and correctness (never handing back another tenant's memory) matters
        more here than the extra round trip.
        """
        got = self._collection.get(include=["metadatas"])
        ids = got.get("ids") or []
        metas = got.get("metadatas") or []
        return [i for i, m in zip(ids, metas)
                if str((m or {}).get("session_id", "")).startswith(prefix)]

    def recall(self, query: str, *, session_id: str | None = "default",
            session_prefix: str | None = None,
            limit: int = 5) -> list[MemoryRecord]:
        if session_prefix is not None:
            allowed = set(self._ids_matching_prefix(session_prefix))
            if not allowed:
                return []
            where = None
            # Over-fetch: some of Chroma's top matches may fall outside the
            # tenant's own sessions and get filtered out below, so ask for
            # more than `limit` up front rather than under-return.
            n_results = max(limit * 5, limit, len(allowed))
        else:
            where = {"session_id": session_id} if session_id is not None else None
            allowed = None
            n_results = limit
        result = self._collection.query(
            query_embeddings=[self.embedder.embed(query)],
            n_results=n_results,
            where=where,
        )
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        records: list[MemoryRecord] = []
        for rid, doc, meta, dist in zip(ids, docs, metas, distances):
            if allowed is not None and rid not in allowed:
                continue
            records.append(
                MemoryRecord(
                    content=doc,
                    session_id=(meta or {}).get("session_id", "default"),
                    kind=(meta or {}).get("kind", "note"),
                    score=1.0 - float(dist),  # distance -> similarity
                )
            )
            if len(records) >= limit:
                break
        return records

    def forget(self, session_id: str | None = "default", *,
            session_prefix: str | None = None) -> None:
        if session_prefix is not None:
            ids = self._ids_matching_prefix(session_prefix)
            if ids:
                self._collection.delete(ids=ids)
        elif session_id is None:
            # Recreate the collection to wipe everything.
            name = self._collection.name
            self._client.delete_collection(name)
            self._collection = self._client.get_or_create_collection(name)
        else:
            self._collection.delete(where={"session_id": session_id})

    def count(self, session_id: str | None = None, *,
            session_prefix: str | None = None) -> int:
        try:
            if session_prefix is not None:
                return len(self._ids_matching_prefix(session_prefix))
            return self._collection.count()
        except Exception:  # noqa: BLE001 - backend-specific
            return 0
