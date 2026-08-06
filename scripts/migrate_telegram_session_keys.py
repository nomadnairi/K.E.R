#!/usr/bin/env python3
"""
Move a linked Telegram user's existing chat history onto the session key
their Desktop/Web account uses, so old conversations become visible there
too — not just new ones.

Before this migration, the bot always stored memory under
``tg-<telegram_id>``, even for accounts later linked via ``/link`` — see
``jarvis.interfaces.telegram_bot.principal_session_id`` and the audit that
found it. New activity after that fix already lands on the shared
``user:<username>::default`` key automatically; this script back-fills
history that already existed under the old key for accounts that were
linked *before* the fix shipped. Running it is optional — nothing breaks if
you skip it, old history just stays invisible from Desktop/Web until this
runs. Safe to run more than once: already-migrated rows have nothing left
under the old key, so a second run reports 0 for them.

**Handles encryption correctly.** Message/memory content is AEAD-encrypted
with the *session_id* as associated data (see ``jarvis/security/crypto.py``
— "binding the ciphertext to its context so it cannot be transplanted to
another row"), so a plain ``UPDATE ... SET session_id = ...`` would leave
every migrated row permanently undecryptable. This script decrypts each row
under its old session_id and re-encrypts it under the new one before
renaming — using the same ``KER_DATA_KEY`` the running server uses. With no
key configured, encryption is a pass-through and this is a plain rename.

Only covers the default SQLite memory backend (session_id lives in the
``messages``/``memories`` tables in one shared file, ``memory_db_path``) —
not the optional Chroma/in-memory backends.

    python3 scripts/migrate_telegram_session_keys.py            # dry-run: report only
    python3 scripts/migrate_telegram_session_keys.py --apply    # actually migrate

Back up your database first:

    cp data/jarvis.db data/jarvis.db.bak
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.config.settings import get_settings  # noqa: E402
from jarvis.security.crypto import KeyProvider  # noqa: E402


def linked_accounts(auth_db_path: str) -> list[tuple[str, int]]:
    """``(username, telegram_user_id)`` for every verified Telegram link."""
    conn = sqlite3.connect(auth_db_path)
    try:
        rows = conn.execute(
            "SELECT username, telegram_user_id FROM accounts "
            "WHERE telegram_verified = 1 AND telegram_user_id IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    return [(str(r[0]), int(r[1])) for r in rows]


def migrate_table(conn: sqlite3.Connection, table: str, box, old_session: str,
                new_session: str, *, apply: bool) -> int:
    """Move every row in ``table`` from ``old_session`` to ``new_session``.

    Re-encrypts ``content`` under the new session id as the AEAD associated
    data. Returns the row count found (moved only when ``apply`` is set).
    """
    try:
        rows = conn.execute(
            f"SELECT id, content FROM {table} WHERE session_id = ?",
            (old_session,),
        ).fetchall()
    except sqlite3.OperationalError:
        return 0  # table doesn't exist yet — nothing has ever been stored
    if not rows:
        return 0
    if apply:
        for row_id, content in rows:
            plaintext = box.decrypt(content, aad=old_session)
            ciphertext = box.encrypt(plaintext, aad=new_session)
            conn.execute(
                f"UPDATE {table} SET session_id = ?, content = ? WHERE id = ?",
                (new_session, ciphertext, row_id),
            )
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="Actually migrate (default: dry-run report only)")
    args = parser.parse_args(argv)

    settings = get_settings()
    accounts = linked_accounts(settings.auth_db_path)
    if not accounts:
        print("No linked Telegram accounts found — nothing to migrate.")
        return 0

    box = KeyProvider.box()
    conn = sqlite3.connect(settings.memory_db_path)
    total_messages = total_memories = 0
    try:
        for username, tg_id in accounts:
            old_session = f"tg-{tg_id}"
            new_session = f"user:{username}::default"
            n_msg = migrate_table(conn, "messages", box, old_session,
                                new_session, apply=args.apply)
            n_mem = migrate_table(conn, "memories", box, old_session,
                                new_session, apply=args.apply)
            if n_msg or n_mem:
                verb = "Migrated" if args.apply else "Would migrate"
                print(f"{verb} {username} (tg {tg_id}): "
                    f"{n_msg} messages, {n_mem} memories")
            total_messages += n_msg
            total_memories += n_mem
        if args.apply:
            conn.commit()
    finally:
        conn.close()

    if not args.apply:
        print(f"\nDry run: {total_messages} messages + {total_memories} "
            f"memories would move across {len(accounts)} linked account(s). "
            "Back up the database, then re-run with --apply.")
    else:
        print(f"\nDone: moved {total_messages} messages + "
            f"{total_memories} memories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
