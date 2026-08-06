"""Tests for the accounts / licensing / token service."""

from __future__ import annotations

import time

import pytest

from jarvis.licensing import AuthError, LicenseService, hash_password, verify_password


@pytest.fixture()
def svc() -> LicenseService:
    service = LicenseService(":memory:", token_ttl_hours=1)
    yield service
    service.close()


def test_password_hash_roundtrip():
    stored = hash_password("s3cret!")
    # Memory-hard by default: Argon2id where available, else scrypt.
    assert stored.startswith("$argon2") or stored.startswith("scrypt$")
    assert verify_password("s3cret!", stored)
    assert not verify_password("wrong", stored)
    # Two hashes of the same password differ (random salt).
    assert hash_password("s3cret!") != stored


def test_verify_rejects_garbage():
    assert not verify_password("x", "not-a-valid-hash")
    assert not verify_password("x", "")


def test_create_account_and_duplicate(svc: LicenseService):
    acc = svc.create_account("Tony", "arcreactor")
    assert acc.username == "tony"  # normalised to lower-case
    assert acc.active and not acc.telegram_verified
    with pytest.raises(AuthError):
        svc.create_account("tony", "other")


def test_a_licence_is_not_needed_to_sign_in(svc: LicenseService):
    """Free users have to get in — the licence decides the tier, not entry."""
    acc = svc.create_account("bruce", "hulk")
    assert svc.authenticate("bruce", "hulk").id == acc.id
    # The password still has to be right.
    with pytest.raises(AuthError):
        svc.authenticate("bruce", "nope")


def test_a_licence_can_be_demanded_when_the_operator_wants_it(svc: LicenseService):
    acc = svc.create_account("bruce", "hulk")
    with pytest.raises(AuthError):
        svc.authenticate("bruce", "hulk", require_license=True)
    svc.issue_license(acc.id)
    assert svc.authenticate("bruce", "hulk", require_license=True).id == acc.id


def test_disabled_account_cannot_login(svc: LicenseService):
    acc = svc.create_account("nat", "widow")
    svc.issue_license(acc.id)
    svc.set_active("nat", False)
    with pytest.raises(AuthError):
        svc.authenticate("nat", "widow")


def test_unknown_user_raises(svc: LicenseService):
    with pytest.raises(AuthError):
        svc.authenticate("ghost", "boo")


def test_token_issue_validate_revoke(svc: LicenseService):
    acc = svc.create_account("steve", "shield")
    svc.issue_license(acc.id)
    token = svc.issue_token(acc.id)
    assert svc.validate_token(token).id == acc.id
    assert svc.validate_token("bogus") is None
    assert svc.validate_token("") is None
    svc.revoke_token(token)
    assert svc.validate_token(token) is None


def test_expired_token_is_invalid(svc: LicenseService):
    acc = svc.create_account("thor", "mjolnir")
    svc.issue_license(acc.id)
    token = svc.issue_token(acc.id)
    # Force the token to be expired.
    svc._conn.execute(
        "UPDATE tokens SET expires_at = ? WHERE token_hash IS NOT NULL",
        (time.time() - 1,),
    )
    svc._conn.commit()
    assert svc.validate_token(token) is None
    assert svc.purge_expired_tokens() == 1


# -- device metadata / sessions (Этап 2 / Фаза A2) ---------------------------
#
# tokens previously recorded nothing about the client that requested one —
# no device id, name, platform, or client type, and no "last seen" — so the
# server could never answer "what's logged in on this account right now".
# See jarvis.licensing.service.LicenseService.list_sessions/revoke_session.

def test_issue_token_without_device_info_is_unchanged(svc: LicenseService):
    # Every pre-existing call site (password login, Telegram redemption) —
    # must keep working exactly as before.
    acc = svc.create_account("clint", "arrow")
    token = svc.issue_token(acc.id)
    assert svc.validate_token(token).id == acc.id
    sessions = svc.list_sessions(acc.id)
    assert len(sessions) == 1
    assert sessions[0]["device_id"] is None
    assert sessions[0]["device_name"] == ""
    assert sessions[0]["platform"] == ""


def test_issue_token_records_device_metadata(svc: LicenseService):
    acc = svc.create_account("wanda", "hex")
    svc.issue_token(acc.id, device_id="desktop-abc123", device_name="Wanda's PC",
                    platform="windows", client_type="desktop")
    sessions = svc.list_sessions(acc.id)
    assert len(sessions) == 1
    row = sessions[0]
    assert row["device_id"] == "desktop-abc123"
    assert row["device_name"] == "Wanda's PC"
    assert row["platform"] == "windows"
    assert row["client_type"] == "desktop"
    assert row["created_at"] is not None


def test_validate_token_stamps_last_seen(svc: LicenseService):
    acc = svc.create_account("sam", "falcon")
    token = svc.issue_token(acc.id)
    assert svc.list_sessions(acc.id)[0]["last_seen_at"] is None
    svc.validate_token(token)
    assert svc.list_sessions(acc.id)[0]["last_seen_at"] is not None


def test_list_sessions_only_shows_this_accounts_tokens(svc: LicenseService):
    a = svc.create_account("peter", "spidey")
    b = svc.create_account("miles", "spidey2")
    svc.issue_token(a.id, device_name="Peter's phone")
    svc.issue_token(b.id, device_name="Miles's phone")
    a_sessions = svc.list_sessions(a.id)
    assert len(a_sessions) == 1
    assert a_sessions[0]["device_name"] == "Peter's phone"


def test_list_sessions_excludes_expired(svc: LicenseService):
    acc = svc.create_account("bucky", "winter")
    svc.issue_token(acc.id)
    svc._conn.execute(
        "UPDATE tokens SET expires_at = ? WHERE user_id = ?",
        (time.time() - 1, acc.id))
    svc._conn.commit()
    assert svc.list_sessions(acc.id) == []


def test_revoke_session_ends_that_token_only(svc: LicenseService):
    acc = svc.create_account("carol", "binary")
    tok1 = svc.issue_token(acc.id, device_name="Phone")
    tok2 = svc.issue_token(acc.id, device_name="Laptop")
    sessions = {s["device_name"]: s["id"] for s in svc.list_sessions(acc.id)}

    assert svc.revoke_session(acc.id, sessions["Phone"]) is True

    assert svc.validate_token(tok1) is None
    assert svc.validate_token(tok2).id == acc.id
    remaining = svc.list_sessions(acc.id)
    assert len(remaining) == 1 and remaining[0]["device_name"] == "Laptop"


def test_revoke_session_cannot_touch_another_accounts_token():
    """One account can never end another's session by guessing/reusing an id
    — the exact class of bug this session revamp exists to prevent."""
    svc = LicenseService(":memory:", token_ttl_hours=1)
    try:
        victim = svc.create_account("victim", "password1")
        attacker = svc.create_account("attacker", "password2")
        svc.issue_token(victim.id, device_name="Victim's phone")
        victim_session_id = svc.list_sessions(victim.id)[0]["id"]

        assert svc.revoke_session(attacker.id, victim_session_id) is False
        # Victim's session is untouched.
        assert len(svc.list_sessions(victim.id)) == 1
    finally:
        svc.close()


def test_revoke_session_unknown_id_returns_false(svc: LicenseService):
    acc = svc.create_account("hope", "wasp")
    assert svc.revoke_session(acc.id, "not-a-real-token-hash") is False


def test_old_schema_tokens_table_migrates_cleanly(tmp_path):
    """A tokens table created before device columns existed must not crash
    startup — same guarantee already given to accounts/telegram_user_id."""
    import sqlite3

    db_path = str(tmp_path / "auth.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        );
        CREATE TABLE tokens (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    svc = LicenseService(db_path, token_ttl_hours=1)
    try:
        acc = svc.create_account("legacy", "oldpw")
        token = svc.issue_token(acc.id, device_name="New client")
        assert svc.validate_token(token).id == acc.id
        assert svc.list_sessions(acc.id)[0]["device_name"] == "New client"
    finally:
        svc.close()


def test_license_expiry_and_revoke(svc: LicenseService):
    acc = svc.create_account("clint", "arrow")
    key = svc.issue_license(acc.id, valid_days=30)
    assert svc.has_active_license(acc.id)
    # Expired in the past → not active.
    assert not svc.has_active_license(acc.id, now=time.time() + 31 * 86400)
    assert svc.revoke_license_by_key(key)
    assert not svc.has_active_license(acc.id)
    assert not svc.revoke_license_by_key("JVS-unknown")


def test_license_key_is_not_stored_plaintext(svc: LicenseService):
    acc = svc.create_account("wanda", "chaos")
    key = svc.issue_license(acc.id)
    rows = svc._conn.execute("SELECT key_hash FROM licenses").fetchall()
    assert all(key not in r["key_hash"] for r in rows)


def test_telegram_pairing(svc: LicenseService):
    acc = svc.create_account("peter", "spider")
    svc.issue_license(acc.id)
    code = svc.create_pairing_code(acc.id)
    assert len(code) == 8
    linked = svc.confirm_pairing(code.lower(), telegram_user_id=42)
    assert linked is not None and linked.telegram_verified
    assert svc.get_account_by_telegram(42).id == acc.id
    # A used code cannot be replayed.
    assert svc.confirm_pairing(code, telegram_user_id=99) is None


def test_pairing_code_expiry(svc: LicenseService):
    acc = svc.create_account("scott", "antman")
    code = svc.create_pairing_code(acc.id, ttl_seconds=-1)
    assert svc.confirm_pairing(code, telegram_user_id=7) is None


def test_require_telegram_flag_on_login(svc: LicenseService):
    acc = svc.create_account("carol", "marvel")
    svc.issue_license(acc.id)
    assert svc.get_account_by_telegram(1234) is None


def test_telegram_login_creates_account_and_token(svc: LicenseService):
    code = svc.create_telegram_login_code(555001)
    assert len(code) == 6 and code.isdigit()
    result = svc.redeem_telegram_login(code)
    assert result is not None
    token, username = result
    # Token is valid and maps to an account bound to the Telegram user.
    acc = svc.validate_token(token)
    assert acc is not None and acc.username == username
    assert svc.get_account_by_telegram(555001).username == username
    # Single-use: a second redeem fails.
    assert svc.redeem_telegram_login(code) is None


def test_telegram_login_reuses_existing_account(svc: LicenseService):
    c1 = svc.create_telegram_login_code(555002)
    _t1, u1 = svc.redeem_telegram_login(c1)
    c2 = svc.create_telegram_login_code(555002)
    _t2, u2 = svc.redeem_telegram_login(c2)
    assert u1 == u2                    # same person → same account


def test_telegram_login_bad_code(svc: LicenseService):
    assert svc.redeem_telegram_login("000000") is None


# -- ensure_account_for_telegram (the bot's "set a password" flow) -----------
#
# Shared by redeem_telegram_login (silent) and the bot's own password-setting
# button (explicit) — a person who wants to sign in on a second PC can set a
# password on the account their Telegram code already created.


def test_ensure_account_for_telegram_creates_once(svc: LicenseService):
    acc1 = svc.ensure_account_for_telegram(555010)
    acc2 = svc.ensure_account_for_telegram(555010)
    assert acc1.id == acc2.id
    assert acc1.telegram_verified is True


def test_ensure_account_for_telegram_matches_login_code_path(svc: LicenseService):
    # Redeeming a code first, then asking to "set a password" for the same
    # person, must land on the same account rather than creating a second one.
    code = svc.create_telegram_login_code(555011)
    _token, username = svc.redeem_telegram_login(code)
    acc = svc.ensure_account_for_telegram(555011)
    assert acc.username == username


def test_set_password_then_login_with_it(svc: LicenseService):
    acc = svc.ensure_account_for_telegram(555012)
    svc.change_password(acc.username, "correct horse battery")
    logged_in = svc.authenticate(acc.username, "correct horse battery")
    assert logged_in.id == acc.id


def test_migrates_an_accounts_table_predating_telegram_columns(tmp_path):
    # Simulates a database created before telegram_user_id/telegram_verified
    # existed in the schema -- CREATE TABLE IF NOT EXISTS is a no-op against
    # an existing table, so without an explicit ALTER TABLE fallback every
    # Telegram-login path fails with "no such column" (an HTTP 500 in prod).
    import sqlite3

    db_path = str(tmp_path / "accounts.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, "
        "active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)")
    conn.commit()
    conn.close()

    service = LicenseService(db_path, token_ttl_hours=1)
    try:
        code = service.create_telegram_login_code(555999)
        result = service.redeem_telegram_login(code)
        assert result is not None
        assert service.get_account_by_telegram(555999) is not None
    finally:
        service.close()


# -- API keys (the credential behind "API от меня") --------------------------

def test_api_key_is_minted_validated_and_scoped_to_its_account(svc):
    ann = svc.create_account("ann", "pw-ann")
    bob = svc.create_account("bob", "pw-bob")
    key = svc.create_api_key(ann.id, label="my laptop")
    assert key.startswith("ker-")
    who = svc.validate_api_key(key)
    assert who is not None and who.id == ann.id
    assert who.username == "ann" and who.id != bob.id


def test_api_key_is_stored_hashed_never_in_the_clear(svc):
    ann = svc.create_account("ann", "pw")
    key = svc.create_api_key(ann.id)
    row = svc._conn.execute(
        "SELECT key_hash, prefix FROM api_keys").fetchone()
    assert row["key_hash"] != key                 # only the hash is kept
    assert key.startswith(row["prefix"])          # prefix is a visible slice
    assert len(row["prefix"]) < len(key)


def test_a_bad_or_foreign_key_validates_to_nothing(svc):
    ann = svc.create_account("ann", "pw")
    svc.create_api_key(ann.id)
    assert svc.validate_api_key("") is None
    assert svc.validate_api_key("sk-not-ours") is None
    assert svc.validate_api_key("ker-totally-made-up") is None


def test_listing_shows_metadata_but_not_the_secret(svc):
    ann = svc.create_account("ann", "pw")
    svc.create_api_key(ann.id, label="one")
    svc.create_api_key(ann.id, label="two")
    keys = svc.list_api_keys(ann.id)
    assert {k["label"] for k in keys} == {"one", "two"}
    for k in keys:
        assert "key_hash" not in k and "secret" not in k
        assert k["prefix"].startswith("ker-")


def test_revoking_a_key_kills_it_immediately(svc):
    ann = svc.create_account("ann", "pw")
    key = svc.create_api_key(ann.id)
    key_id = svc.list_api_keys(ann.id)[0]["id"]
    assert svc.revoke_api_key(ann.id, key_id) is True
    assert svc.validate_api_key(key) is None       # revocation is instant
    assert svc.list_api_keys(ann.id) == []


def test_you_cannot_revoke_someone_elses_key(svc):
    ann = svc.create_account("ann", "pw")
    bob = svc.create_account("bob", "pw")
    svc.create_api_key(ann.id)
    ann_key_id = svc.list_api_keys(ann.id)[0]["id"]
    # Bob names Ann's key id; the ownership clause refuses it.
    assert svc.revoke_api_key(bob.id, ann_key_id) is False
    assert len(svc.list_api_keys(ann.id)) == 1


def test_a_deactivated_account_cannot_use_its_key(svc):
    ann = svc.create_account("ann", "pw")
    key = svc.create_api_key(ann.id)
    svc.set_active("ann", False)
    assert svc.validate_api_key(key) is None


def test_validating_stamps_last_used(svc):
    ann = svc.create_account("ann", "pw")
    key = svc.create_api_key(ann.id)
    assert svc.list_api_keys(ann.id)[0]["last_used_at"] is None
    svc.validate_api_key(key)
    assert svc.list_api_keys(ann.id)[0]["last_used_at"] is not None


# -- owner bootstrap (owner account straight from server env) ----------------

def test_bootstrap_creates_the_owner_account(svc):
    acc = svc.bootstrap_owner("admin", "s3cret-pass")
    assert acc is not None and acc.username == "admin"
    # The operator can now sign in with exactly those credentials.
    assert svc.authenticate("admin", "s3cret-pass").username == "admin"


def test_bootstrap_realigns_the_password_on_an_existing_owner(svc):
    svc.create_account("admin", "old-pass")
    svc.bootstrap_owner("admin", "new-pass")
    assert svc.authenticate("admin", "new-pass").username == "admin"
    with pytest.raises(AuthError):
        svc.authenticate("admin", "old-pass")


def test_bootstrap_reactivates_a_disabled_owner(svc):
    svc.create_account("admin", "pw")
    svc.set_active("admin", False)
    svc.bootstrap_owner("admin", "pw")
    assert svc.authenticate("admin", "pw").username == "admin"


def test_bootstrap_needs_both_name_and_password(svc):
    assert svc.bootstrap_owner("admin", "") is None
    assert svc.bootstrap_owner("", "pw") is None
    assert svc.get_account("admin") is None


# -- password hashing scheme (Argon2id / scrypt / legacy) --------------------

def test_new_hashes_use_a_memory_hard_scheme():
    from jarvis.licensing.service import hash_password, verify_password
    h = hash_password("s3cret!")
    assert h.startswith("$argon2") or h.startswith("scrypt$")
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)


def test_legacy_pbkdf2_hashes_still_verify():
    import hashlib
    import os
    from jarvis.licensing.service import verify_password
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", b"old-pass", salt, 200_000)
    legacy = f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"
    assert verify_password("old-pass", legacy)
    assert not verify_password("nope", legacy)


def test_login_upgrades_a_legacy_hash(svc):
    import hashlib
    import os
    # Plant an account with a legacy PBKDF2 hash directly.
    acc = svc.create_account("olduser", "temp")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", b"realpass", salt, 200_000)
    legacy = f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"
    svc._conn.execute("UPDATE accounts SET password_hash = ? WHERE id = ?",
                    (legacy, acc.id))
    svc._conn.commit()
    # A correct login succeeds and rehashes to the current scheme.
    assert svc.authenticate("olduser", "realpass").username == "olduser"
    stored = svc._conn.execute(
        "SELECT password_hash FROM accounts WHERE id = ?", (acc.id,)
    ).fetchone()["password_hash"]
    assert not stored.startswith("pbkdf2_sha256$")   # upgraded
    assert svc.authenticate("olduser", "realpass")   # still works after upgrade
