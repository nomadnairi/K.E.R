"""
Memory manager.

Ties the pieces of the memory subsystem together and exposes the small surface
the engine needs:

* **persistence** — every turn is written to the conversation store, so history
  survives restarts, and sessions can be reloaded on demand;
* **semantic recall** — durable facts (or, if fact extraction is off, whole
  exchanges) are embedded into the vector store and relevant ones are recalled
  to enrich the LLM's context (RAG).

The write/recall surface is **async**: blocking work (SQLite I/O, embeddings,
which may hit the network) runs in a worker thread so it never stalls the event
loop. History loading stays synchronous — it is a fast local read used while a
session is being created.
"""

from __future__ import annotations

import asyncio

from jarvis.config.settings import Settings
from jarvis.llm.client import LLMClient
from jarvis.memory.base import BaseEmbedder, BaseMemoryStore, MemoryRecord
from jarvis.memory.conversation_store import SQLiteConversationStore
from jarvis.memory.embeddings import HashingEmbedder, LocalEmbedder, OpenAIEmbedder
from jarvis.memory.facts import FactExtractor
from jarvis.models.message import Conversation, Message
from jarvis.utils.logger import get_logger
from jarvis.utils.redaction import redact_secrets

logger = get_logger(__name__)


class MemoryManager:
    """Coordinates conversation persistence and semantic recall."""

    #: How many recent messages to reload into a session's live context.
    history_limit: int = 50

    def __init__(
        self,
        vector_store: BaseMemoryStore,
        conversation_store: SQLiteConversationStore,
        *,
        recall_limit: int = 4,
        fact_extractor: FactExtractor | None = None,
        redact_secrets: bool = True,
    ) -> None:
        self.vectors = vector_store
        self.conversations = conversation_store
        self.recall_limit = recall_limit
        self.fact_extractor = fact_extractor
        self.redact_secrets = redact_secrets

    def _clean(self, text: str) -> str:
        """Redact secrets from text before it is persisted, if enabled."""
        return redact_secrets(text) if self.redact_secrets else text

    # -- construction -------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Settings,
                    llm: LLMClient | None = None) -> "MemoryManager":
        embedder = cls._make_embedder(settings)
        vector_store = cls._make_vector_store(settings, embedder)
        conversation_store = SQLiteConversationStore(settings.memory_db_path)
        fact_extractor = (
            FactExtractor(llm)
            if (settings.memory_fact_extraction and llm is not None)
            else None
        )
        return cls(
            vector_store,
            conversation_store,
            recall_limit=settings.memory_recall_limit,
            fact_extractor=fact_extractor,
            redact_secrets=settings.memory_redact_secrets,
        )

    @staticmethod
    def _make_embedder(settings: Settings) -> BaseEmbedder:
        backend = settings.embedding_backend
        if backend == "openai" and settings.openai_api_key:
            return OpenAIEmbedder(settings.openai_api_key)
        if backend == "local":
            return LocalEmbedder(settings.local_embedding_model)
        return HashingEmbedder()

    @staticmethod
    def _make_vector_store(settings: Settings, embedder: BaseEmbedder) -> BaseMemoryStore:
        backend = settings.memory_backend
        if backend == "chroma":
            from jarvis.memory.chroma_store import ChromaVectorStore
            return ChromaVectorStore(embedder, path=settings.vector_store_path)
        if backend == "memory":
            from jarvis.memory.vector_store import InMemoryVectorStore
            return InMemoryVectorStore(
                embedder=embedder,
                persist_path=settings.memory_vector_path,
                min_score=settings.memory_min_score,
            )
        # Default: SQLite-backed, incremental writes.
        from jarvis.memory.sqlite_vector_store import SQLiteVectorStore
        return SQLiteVectorStore(
            embedder,
            db_path=settings.memory_db_path,
            min_score=settings.memory_min_score,
            recency_weight=settings.memory_recency_weight,
            max_per_session=settings.memory_max_per_session,
            dedup_threshold=settings.memory_dedup_threshold,
        )

    # -- persistence (history) ---------------------------------------------

    def load_conversation(self, session_id: str) -> Conversation:
        """Load recent persisted history for a session (fast, synchronous)."""
        return self.conversations.load(session_id, limit=self.history_limit)

    async def persist_message(self, session_id: str, message: Message) -> None:
        await asyncio.to_thread(self.conversations.append, session_id, message)

    async def persist_turn(self, session_id: str, user: str, assistant: str) -> None:
        """Persist a full turn (user + assistant) to the conversation store."""
        await asyncio.to_thread(
            self.conversations.append_exchange,
            session_id,
            self._clean(user),
            self._clean(assistant),
        )

    async def clear_history(self, session_id: str | None = "default") -> None:
        await asyncio.to_thread(self.conversations.clear, session_id)

    # -- semantic memory ----------------------------------------------------

    async def remember(self, session_id: str, content: str, *, kind: str = "fact",
                    metadata: dict | None = None) -> None:
        """Store ``content`` in the semantic vector store."""
        record = MemoryRecord(content=self._clean(content), session_id=session_id,
                            kind=kind, metadata=metadata or {})
        await asyncio.to_thread(self.vectors.remember, record)

    async def remember_turn(self, session_id: str, user: str,
                            assistant: str) -> None:
        """Store the durable takeaways of a turn in semantic memory.

        With a fact extractor, stores extracted facts; otherwise falls back to
        storing the raw exchange.
        """
        # Redact before the exchange reaches the LLM or the store.
        user, assistant = self._clean(user), self._clean(assistant)
        if self.fact_extractor is not None:
            facts = await self.fact_extractor.extract(user, assistant)
            for fact in facts:
                await self.remember(session_id, fact, kind="fact")
            return
        await self.remember(
            session_id,
            f"User said: {user}\nYou replied: {assistant}",
            kind="exchange",
        )

    async def recall(self, query: str, *, session_id: str = "default",
                    limit: int | None = None) -> list[MemoryRecord]:
        return await asyncio.to_thread(
            self.vectors.recall,
            query,
            session_id=session_id,
            limit=limit or self.recall_limit,
        )

    async def recall_context(self, query: str, *,
                            session_id: str = "default") -> str | None:
        """Return recalled memories formatted for system-prompt injection."""
        records = await self.recall(query, session_id=session_id)
        if not records:
            return None
        lines = ["Relevant things you remember from earlier:"]
        lines.extend(f"- {r.content}" for r in records)
        return "\n".join(lines)

    # -- what the user is shown ---------------------------------------------
    # Recall answers "what matters for this question". Showing someone what
    # their assistant remembers is a different question, so it has its own way in.

    async def browse(self, *, session_id: str | None = None,
                    limit: int = 100, offset: int = 0) -> list[MemoryRecord]:
        """Stored memories, newest first."""
        return await asyncio.to_thread(
            self.vectors.browse, session_id=session_id, limit=limit,
            offset=offset,
        )

    def can_browse(self) -> bool:
        """Whether this backend can list and delete individual memories."""
        return self.vectors.can_browse()

    async def delete_memory(self, record_id: int) -> bool:
        """Forget one specific thing."""
        return await asyncio.to_thread(self.vectors.delete, record_id)

    # -- lifecycle ----------------------------------------------------------

    async def forget(self, session_id: str | None = "default") -> None:
        """Clear both semantic memory and stored history for a session."""
        await asyncio.to_thread(self.vectors.forget, session_id)
        await asyncio.to_thread(self.conversations.clear, session_id)

    def stats(self) -> dict:
        return {
            "memories": self.vectors.count(),
            "stored_messages": self.conversations.count(),
            "sessions": len(self.conversations.sessions()),
        }
