"""
Document Intelligence — ingest documents and answer questions over them.

The assistant should be able to read a file the user gives it and then answer
from its contents rather than from the model's general knowledge. This service
is the store and the retriever behind that:

* **ingest** a document → split it into passages, embed each, keep them;
* **ask** a question → embed it, return the closest passages across every
  document (with the source name and a similarity score);
* **context_for** a question → those passages formatted as grounding text to
  put in front of the model, with the sources named so an answer can cite them.

Backed by SQLite so a library of documents survives a restart; the embeddings
are stored as JSON and cosine similarity is computed in Python, which is plenty
for a personal library and keeps the dependency surface at the standard library
plus whatever embedder is configured. Per-user isolation is by ``principal`` so
one account never retrieves another's documents.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from jarvis.documents.chunking import chunk_text
from jarvis.memory.embeddings import BaseEmbedder, HashingEmbedder, cosine_similarity


@dataclass(frozen=True)
class Document:
    """One ingested document."""

    id: str
    name: str
    principal: str
    passages: int
    chars: int
    created_at: float

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "passages": self.passages,
                "chars": self.chars, "created_at": self.created_at}


@dataclass(frozen=True)
class Passage:
    """A retrieved passage and where it came from."""

    doc_id: str
    doc_name: str
    ord: int
    text: str
    score: float = 0.0

    def as_dict(self) -> dict:
        return {"doc_id": self.doc_id, "doc_name": self.doc_name,
                "ord": self.ord, "text": self.text,
                "score": round(self.score, 4)}


@dataclass
class _Row:
    doc_id: str
    doc_name: str
    ord: int
    text: str
    embedding: list[float] = field(default_factory=list)


class DocumentIntelligence:
    """A per-account library of documents, searchable by meaning."""

    def __init__(self, db_path: str = "data/documents.db",
                 embedder: BaseEmbedder | None = None) -> None:
        self._lock = threading.Lock()
        self._embedder = embedder or HashingEmbedder()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                principal TEXT NOT NULL,
                name TEXT NOT NULL,
                chars INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS passages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                principal TEXT NOT NULL,
                ord INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_passages_principal
                ON passages(principal);
            CREATE INDEX IF NOT EXISTS idx_documents_principal
                ON documents(principal);
            """
        )
        self._conn.commit()

    def close(self) -> None:  # pragma: no cover - lifecycle
        with self._lock:
            self._conn.close()

    # -- ingest --------------------------------------------------------------

    def ingest(self, name: str, text: str, *, principal: str = "shared",
               size: int = 800, overlap: int = 150) -> Document:
        """Split, embed and store ``text`` as a document; returns its record."""
        passages = chunk_text(text, size=size, overlap=overlap)
        doc_id = f"doc_{int(time.time()*1000):x}_{abs(hash(name)) % 10000:04d}"
        now = time.time()
        chars = len(text or "")
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents (id, principal, name, chars, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (doc_id, principal, name, chars, now))
            for i, passage in enumerate(passages):
                emb = json.dumps(self._embedder.embed(passage))
                self._conn.execute(
                    "INSERT INTO passages (doc_id, principal, ord, text, "
                    "embedding) VALUES (?, ?, ?, ?, ?)",
                    (doc_id, principal, i, passage, emb))
            self._conn.commit()
        return Document(id=doc_id, name=name, principal=principal,
                        passages=len(passages), chars=chars, created_at=now)

    # -- query ---------------------------------------------------------------

    def ask(self, query: str, *, principal: str = "shared", k: int = 4,
            min_score: float = 0.0) -> list[Passage]:
        """The ``k`` passages most similar to ``query`` for this account."""
        query = (query or "").strip()
        if not query:
            return []
        q = self._embedder.embed(query)
        with self._lock:
            rows = self._conn.execute(
                "SELECT p.doc_id, p.ord, p.text, p.embedding, d.name "
                "FROM passages p JOIN documents d ON d.id = p.doc_id "
                "WHERE p.principal = ?", (principal,)).fetchall()
        scored: list[Passage] = []
        for r in rows:
            try:
                emb = json.loads(r["embedding"])
            except (json.JSONDecodeError, TypeError):
                continue
            score = cosine_similarity(q, emb)
            if score >= min_score:
                scored.append(Passage(doc_id=r["doc_id"], doc_name=r["name"],
                                    ord=r["ord"], text=r["text"], score=score))
        scored.sort(key=lambda p: p.score, reverse=True)
        return scored[:max(1, k)]

    def context_for(self, query: str, *, principal: str = "shared", k: int = 4,
                    min_score: float = 0.0, max_chars: int = 4000) -> str:
        """Grounding text for the model: the top passages, sources named.

        Empty when nothing is relevant, so the caller can skip grounding rather
        than feed the model noise.
        """
        hits = self.ask(query, principal=principal, k=k, min_score=min_score)
        if not hits:
            return ""
        parts: list[str] = []
        used = 0
        for h in hits:
            block = f"[{h.doc_name}]\n{h.text}"
            if used + len(block) > max_chars and parts:
                break
            parts.append(block)
            used += len(block)
        return "\n\n---\n\n".join(parts)

    # -- library -------------------------------------------------------------

    def documents(self, *, principal: str = "shared") -> list[Document]:
        """Every document this account has ingested, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT d.id, d.name, d.chars, d.created_at, "
                "COUNT(p.id) AS passages FROM documents d "
                "LEFT JOIN passages p ON p.doc_id = d.id "
                "WHERE d.principal = ? GROUP BY d.id ORDER BY d.created_at DESC",
                (principal,)).fetchall()
        return [Document(id=r["id"], name=r["name"], principal=principal,
                        passages=r["passages"], chars=r["chars"],
                        created_at=r["created_at"]) for r in rows]

    def delete(self, doc_id: str, *, principal: str = "shared") -> bool:
        """Remove one document (and its passages), if it belongs to ``principal``."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM documents WHERE id = ? AND principal = ?",
                (doc_id, principal))
            self._conn.execute(
                "DELETE FROM passages WHERE doc_id = ? AND principal = ?",
                (doc_id, principal))
            self._conn.commit()
        return cur.rowcount > 0

    def clear(self, *, principal: str = "shared") -> int:
        """Forget every document for this account; returns how many were removed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM documents WHERE principal = ?", (principal,))
            self._conn.execute(
                "DELETE FROM passages WHERE principal = ?", (principal,))
            self._conn.commit()
        return cur.rowcount
