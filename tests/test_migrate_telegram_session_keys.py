"""
Tests for scripts/migrate_telegram_session_keys.py — the one-time backfill
that moves a linked Telegram user's existing history onto the session key
their Desktop/Web account uses (see the audit behind
jarvis.interfaces.telegram_bot.principal_session_id).

The risky part of this script is the encryption handling: content is
AEAD-encrypted with the session_id as associated data, so a naive rename
would leave every migrated row permanently undecryptable. These tests prove
the round-trip survives a real SecretBox, that a dry run never mutates
anything, that re-running after a migration is a safe no-op, and that a
missing table (nothing ever stored) doesn't crash the script.
"""

from __future__ import annotations

import importlib.util
import os
import sqlite3
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "migrate_telegram_session_keys.py"
_spec = importlib.util.spec_from_file_location("migrate_telegram_session_keys", _SCRIPT_PATH)
migrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate)  # type: ignore[union-attr]

from jarvis.security.crypto import SecretBox  # noqa: E402


def _box(key: bytes | None = None) -> SecretBox:
    return SecretBox(key)


def _messages_conn(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "mem.db"))
    conn.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id TEXT NOT NULL, content TEXT NOT NULL)")
    conn.commit()
    return conn


@pytest.mark.parametrize("key", [None, os.urandom(32)])
def test_migrate_table_reencrypts_so_the_new_key_decrypts_it(tmp_path, key):
    box = _box(key)
    old, new = "tg-42", "user:alice::default"
    conn = _messages_conn(tmp_path)
    conn.execute("INSERT INTO messages (session_id, content) VALUES (?, ?)",
                (old, box.encrypt("hello from telegram", aad=old)))
    conn.commit()

    moved = migrate.migrate_table(conn, "messages", box, old, new, apply=True)
    conn.commit()

    assert moved == 1
    row = conn.execute("SELECT session_id, content FROM messages").fetchone()
    assert row[0] == new
    # The whole point: decrypting under the OLD aad must now fail (content is
    # bound to its new session_id), and under the NEW aad must round-trip.
    assert box.decrypt(row[1], aad=new) == "hello from telegram"
    if box.enabled:
        with pytest.raises(Exception):
            box.decrypt(row[1], aad=old)


def test_migrate_table_dry_run_never_mutates(tmp_path):
    box = _box(os.urandom(32))
    old, new = "tg-1", "user:bob::default"
    conn = _messages_conn(tmp_path)
    ciphertext = box.encrypt("untouched", aad=old)
    conn.execute("INSERT INTO messages (session_id, content) VALUES (?, ?)",
                (old, ciphertext))
    conn.commit()

    reported = migrate.migrate_table(conn, "messages", box, old, new, apply=False)

    assert reported == 1  # reports what WOULD move
    row = conn.execute("SELECT session_id, content FROM messages").fetchone()
    assert row[0] == old  # but nothing actually changed
    assert row[1] == ciphertext


def test_migrate_table_is_idempotent(tmp_path):
    box = _box(None)  # encryption off — pass-through, still must be idempotent
    old, new = "tg-7", "user:carol::default"
    conn = _messages_conn(tmp_path)
    conn.execute("INSERT INTO messages (session_id, content) VALUES (?, ?)",
                (old, box.encrypt("hi", aad=old)))
    conn.commit()

    first = migrate.migrate_table(conn, "messages", box, old, new, apply=True)
    conn.commit()
    second = migrate.migrate_table(conn, "messages", box, old, new, apply=True)

    assert first == 1
    assert second == 0  # nothing left under the old key to move


def test_migrate_table_missing_table_is_a_safe_zero(tmp_path):
    box = _box(None)
    conn = sqlite3.connect(str(tmp_path / "empty.db"))  # no tables at all
    assert migrate.migrate_table(conn, "messages", box, "tg-1",
                                "user:x::default", apply=True) == 0


def test_migrate_table_only_touches_the_matching_session(tmp_path):
    box = _box(None)
    conn = _messages_conn(tmp_path)
    conn.execute("INSERT INTO messages (session_id, content) VALUES (?, ?)",
                ("tg-1", box.encrypt("mine", aad="tg-1")))
    conn.execute("INSERT INTO messages (session_id, content) VALUES (?, ?)",
                ("tg-2", box.encrypt("someone else's", aad="tg-2")))
    conn.commit()

    migrate.migrate_table(conn, "messages", box, "tg-1",
                        "user:alice::default", apply=True)
    conn.commit()

    untouched = conn.execute(
        "SELECT session_id FROM messages WHERE session_id = 'tg-2'").fetchone()
    assert untouched is not None


def test_linked_accounts_returns_only_verified_telegram_links(tmp_path):
    auth_db = tmp_path / "auth.db"
    conn = sqlite3.connect(str(auth_db))
    conn.execute(
        "CREATE TABLE accounts (username TEXT, telegram_user_id INTEGER, "
        "telegram_verified INTEGER)")
    conn.execute("INSERT INTO accounts VALUES ('alice', 111, 1)")
    conn.execute("INSERT INTO accounts VALUES ('pending', 222, 0)")  # not verified
    conn.execute("INSERT INTO accounts VALUES ('nolink', NULL, 0)")  # never linked
    conn.commit()
    conn.close()

    accounts = migrate.linked_accounts(str(auth_db))

    assert accounts == [("alice", 111)]
