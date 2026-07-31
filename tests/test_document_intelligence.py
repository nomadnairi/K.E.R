"""Document Intelligence: chunking, ingest, retrieval, per-account isolation.

The service reads documents the user gives it and answers from their contents.
These tests pin the chunker's shape and the store's retrieval with a
deterministic embedder — no network, no parser libraries.
"""

from __future__ import annotations

import pytest

from jarvis.documents import DocumentIntelligence, chunk_text
from jarvis.memory.embeddings import HashingEmbedder


# -- chunking ----------------------------------------------------------------

def test_empty_text_yields_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_is_one_chunk():
    assert chunk_text("Just a line.") == ["Just a line."]


def test_paragraphs_pack_up_to_the_size():
    text = "\n\n".join([f"Para {i} " + "x" * 100 for i in range(6)])
    chunks = chunk_text(text, size=300, overlap=0)
    assert len(chunks) > 1
    assert all(len(c) <= 320 for c in chunks)      # ~size, packed


def test_an_over_long_paragraph_is_hard_split():
    chunks = chunk_text("y" * 2000, size=500, overlap=50)
    assert len(chunks) >= 4
    # Each window is ~size; the overlap stitched onto the front (plus a join
    # newline) adds at most `overlap`+a couple, so the bound is size + overlap.
    assert all(len(c) <= 560 for c in chunks)


def test_overlap_carries_context_across_the_seam():
    a = "alpha " * 40           # ~240 chars
    b = "bravo " * 40
    chunks = chunk_text(a + "\n\n" + b, size=250, overlap=60)
    assert len(chunks) >= 2
    assert "alpha" in chunks[1]                     # tail of the first carried


# -- the service -------------------------------------------------------------

@pytest.fixture()
def docs():
    svc = DocumentIntelligence(":memory:", embedder=HashingEmbedder())
    yield svc
    svc.close()


def test_ingest_records_the_document_and_its_passages(docs):
    doc = docs.ingest("notes.txt", "Tashkent is the capital of Uzbekistan.\n\n"
                    "The Amu Darya is a river in Central Asia.")
    assert doc.name == "notes.txt"
    assert doc.passages >= 1 and doc.chars > 0
    assert doc.id in [d.id for d in docs.documents()]


def test_ask_returns_the_most_relevant_passage(docs):
    docs.ingest("geo.txt",
                "Tashkent is the capital of Uzbekistan.\n\n"
                "Bananas are a tropical fruit rich in potassium.\n\n"
                "The Sun is a star at the centre of the Solar System.")
    hits = docs.ask("What is the capital of Uzbekistan?", k=1)
    assert hits and "Tashkent" in hits[0].text
    assert hits[0].doc_name == "geo.txt"
    assert hits[0].score > 0


def test_context_for_names_its_sources(docs):
    docs.ingest("a.txt", "The KER assistant runs on this computer.")
    ctx = docs.context_for("Where does KER run?", k=2)
    assert "[a.txt]" in ctx and "KER" in ctx


def test_context_is_empty_when_there_is_nothing(docs):
    assert docs.context_for("anything", k=2) == ""


def test_documents_are_isolated_per_account(docs):
    docs.ingest("ann.txt", "Ann's private notes about project Falcon.",
                principal="user:ann")
    docs.ingest("bob.txt", "Bob's private notes about project Condor.",
                principal="user:bob")
    ann = docs.documents(principal="user:ann")
    assert [d.name for d in ann] == ["ann.txt"]
    hits = docs.ask("Falcon", principal="user:bob", k=5)
    assert all(h.doc_name != "ann.txt" for h in hits)


def test_delete_removes_a_document_and_its_passages(docs):
    doc = docs.ingest("gone.txt", "delete me", principal="user:ann")
    assert docs.delete(doc.id, principal="user:ann") is True
    assert docs.documents(principal="user:ann") == []
    assert docs.ask("delete", principal="user:ann") == []


def test_you_cannot_delete_another_accounts_document(docs):
    doc = docs.ingest("ann.txt", "Ann's doc", principal="user:ann")
    assert docs.delete(doc.id, principal="user:bob") is False
    assert len(docs.documents(principal="user:ann")) == 1


def test_clear_forgets_only_this_accounts_library(docs):
    docs.ingest("a.txt", "one", principal="user:ann")
    docs.ingest("b.txt", "two", principal="user:ann")
    docs.ingest("c.txt", "three", principal="user:bob")
    assert docs.clear(principal="user:ann") == 2
    assert docs.documents(principal="user:ann") == []
    assert len(docs.documents(principal="user:bob")) == 1


def test_the_library_survives_reopening(tmp_path):
    path = str(tmp_path / "docs.db")
    svc = DocumentIntelligence(path, embedder=HashingEmbedder())
    svc.ingest("keep.txt", "Persisted knowledge about KER.", principal="user:x")
    svc.close()
    reopened = DocumentIntelligence(path, embedder=HashingEmbedder())
    try:
        assert [d.name for d in reopened.documents(principal="user:x")] == \
            ["keep.txt"]
        assert reopened.ask("KER", principal="user:x", k=1)
    finally:
        reopened.close()
