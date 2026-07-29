"""Showing a person what their assistant remembers — and letting them undo it.

Recall answers "what is relevant to this question"; browsing answers "what do
you know about me". They are different jobs, and this covers the second one.
"""

from __future__ import annotations

import pytest

from jarvis.memory.base import MemoryRecord
from jarvis.memory.embeddings import HashingEmbedder
from jarvis.memory.sqlite_vector_store import SQLiteVectorStore
from jarvis.memory.vector_store import InMemoryVectorStore


@pytest.fixture(params=["sqlite", "memory"])
def store(request, tmp_path):
    """Both real stores, so the two cannot drift apart."""
    embedder = HashingEmbedder(dimensions=64)
    if request.param == "sqlite":
        return SQLiteVectorStore(embedder, db_path=str(tmp_path / "m.db"))
    return InMemoryVectorStore(embedder=embedder)


def _remember(store, *contents: str, session: str = "default") -> None:
    for text in contents:
        store.remember(MemoryRecord(content=text, session_id=session,
                                    kind="fact"))


def test_browsing_shows_the_newest_first(store):
    _remember(store, "первое", "второе", "третье")
    seen = [r.content for r in store.browse()]
    assert seen == ["третье", "второе", "первое"]


def test_every_listed_memory_can_be_addressed(store):
    """Without an id there is no way to offer "forget this one"."""
    _remember(store, "что-то важное")
    assert store.browse()[0].record_id is not None


def test_forgetting_one_leaves_the_rest(store):
    _remember(store, "оставить", "удалить")
    target = next(r for r in store.browse() if r.content == "удалить")
    assert store.delete(target.record_id) is True
    assert [r.content for r in store.browse()] == ["оставить"]
    assert store.count() == 1


def test_forgetting_something_twice_is_not_an_error(store):
    _remember(store, "раз")
    record_id = store.browse()[0].record_id
    assert store.delete(record_id) is True
    assert store.delete(record_id) is False


def test_browsing_can_be_scoped_to_one_conversation(store):
    _remember(store, "личное", session="alice")
    _remember(store, "рабочее", session="bob")
    assert [r.content for r in store.browse(session_id="alice")] == ["личное"]
    assert len(store.browse()) == 2


def test_browsing_is_paged(store):
    _remember(store, *[f"факт {i}" for i in range(10)])
    first = store.browse(limit=4)
    second = store.browse(limit=4, offset=4)
    assert len(first) == 4 and len(second) == 4
    assert not {r.content for r in first} & {r.content for r in second}


def test_a_silly_limit_is_brought_into_range(store):
    _remember(store, "один")
    assert len(store.browse(limit=10_000)) == 1


def test_a_store_that_cannot_list_says_so_plainly():
    """Callers must be able to tell "cannot list" from "nothing stored"."""
    from jarvis.memory.base import BaseMemoryStore

    class Opaque(BaseMemoryStore):
        def remember(self, record): ...
        def recall(self, query, *, session_id="default", limit=5): return []
        def forget(self, session_id="default"): ...

    store = Opaque()
    assert store.can_browse() is False
    assert store.browse() == []
    assert store.delete(1) is False
