"""At-rest encryption of memory and chat history, plus the auth audit log.

With a key configured, sensitive text is ciphertext in the SQLite file and only
plaintext in memory; auth events are recorded to the security audit logger with
no secrets in them.
"""

from __future__ import annotations

import sqlite3

import pytest

pytest.importorskip("cryptography")

from jarvis.memory.conversation_store import SQLiteConversationStore  # noqa: E402
from jarvis.memory.embeddings import HashingEmbedder  # noqa: E402
from jarvis.memory.sqlite_vector_store import SQLiteVectorStore  # noqa: E402
from jarvis.models.message import Message  # noqa: E402
from jarvis.security import events as audit  # noqa: E402
from jarvis.security.crypto import SecretBox  # noqa: E402


def _key() -> bytes:
    import os
    return os.urandom(32)


def _raw_column(path: str, table: str, col: str) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute(f"SELECT {col} FROM {table}")]
    finally:
        conn.close()


# -- memory ------------------------------------------------------------------

def test_memory_content_is_ciphertext_on_disk(tmp_path):
    from jarvis.memory.base import MemoryRecord
    db = str(tmp_path / "mem.db")
    store = SQLiteVectorStore(HashingEmbedder(), db, min_score=0.0,
                            secret_box=SecretBox(_key()))
    store.remember(MemoryRecord(content="I live in Tashkent",
                                session_id="user:ann", kind="fact"))
    # On disk: encrypted. In memory: plaintext.
    raw = _raw_column(db, "memories", "content")
    assert raw and raw[0].startswith("v1:") and "Tashkent" not in raw[0]
    hits = store.recall("where do I live", session_id="user:ann")
    assert any("Tashkent" in h.content for h in hits)


def test_memory_without_a_key_stays_plaintext(tmp_path):
    from jarvis.memory.base import MemoryRecord
    db = str(tmp_path / "mem.db")
    store = SQLiteVectorStore(HashingEmbedder(), db, min_score=0.0,
                            secret_box=SecretBox(None))
    store.remember(MemoryRecord(content="plain note", session_id="s", kind="fact"))
    assert _raw_column(db, "memories", "content") == ["plain note"]


# -- chat history ------------------------------------------------------------

def test_chat_history_is_ciphertext_on_disk(tmp_path):
    db = str(tmp_path / "chat.db")
    store = SQLiteConversationStore(db, secret_box=SecretBox(_key()))
    store.append_exchange("user:ann", "my card is secret", "noted")
    raw = _raw_column(db, "messages", "content")
    assert all(c.startswith("v1:") for c in raw)
    assert all("secret" not in c for c in raw)
    # Reads back as plaintext, in order.
    convo = store.load("user:ann")
    assert [m.content for m in convo.messages] == ["my card is secret", "noted"]


def test_recent_titles_are_decrypted(tmp_path):
    db = str(tmp_path / "chat.db")
    store = SQLiteConversationStore(db, secret_box=SecretBox(_key()))
    store.append("user:ann", Message.user("Plan my week please"))
    recent = store.recent(limit=5)
    assert recent and recent[0]["title"].startswith("Plan my week")


# -- auth audit log ----------------------------------------------------------

def test_login_success_and_failure_are_audited(caplog):
    from jarvis.licensing.service import LicenseService
    svc = LicenseService(":memory:")
    try:
        svc.create_account("ann", "correct-horse")
        with caplog.at_level("INFO", logger="jarvis.security.audit"):
            svc.authenticate("ann", "correct-horse")
            try:
                svc.authenticate("ann", "wrong")
            except Exception:  # noqa: BLE001
                pass
        text = "\n".join(caplog.messages)
        assert "event=login.ok" in text
        assert "event=login.fail" in text
        # The password itself is never in the log.
        assert "correct-horse" not in text and "wrong" not in text
    finally:
        svc.close()


def test_api_key_lifecycle_is_audited(caplog):
    from jarvis.licensing.service import LicenseService
    svc = LicenseService(":memory:")
    try:
        acc = svc.create_account("ann", "pw-ann-123")
        with caplog.at_level("INFO", logger="jarvis.security.audit"):
            key = svc.create_api_key(acc.id)
            kid = svc.list_api_keys(acc.id)[0]["id"]
            svc.revoke_api_key(acc.id, kid)
        text = "\n".join(caplog.messages)
        assert "event=apikey.created" in text
        assert "event=apikey.revoked" in text
        assert key not in text                      # the secret is never logged
    finally:
        svc.close()


def test_audit_event_never_raises():
    # Even with junk input, auditing must not throw into the auth path.
    audit.audit_event(audit.LOGIN_OK, principal=None, detail=object())  # type: ignore[arg-type]
