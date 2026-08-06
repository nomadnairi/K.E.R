"""
Account, license and login-token management backed by SQLite (standard library).

The typical lifecycle:

1. After a purchase you (the operator) run
   :meth:`LicenseService.create_account` and :meth:`LicenseService.issue_license`,
   handing the user their username, a one-time password and a license key.
2. The desktop/mobile client calls ``POST /auth/login``; the API uses
   :meth:`authenticate` then :meth:`issue_token` to return a bearer token.
3. Optionally the user links Telegram: the client asks for a pairing code
   (:meth:`create_pairing_code`), the user sends ``/link <code>`` to the bot,
   and the bot calls :meth:`confirm_pairing`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path

from jarvis.licensing.models import Account, License
from jarvis.security import events as audit

_PBKDF2_ROUNDS = 200_000
_SALT_BYTES = 16
_ALGO = "pbkdf2_sha256"


class AuthError(Exception):
    """Raised for authentication / licensing failures."""


# -- password hashing ---------------------------------------------------------
#
# Argon2id is the default (memory-hard, the modern OWASP/NIST recommendation).
# It is an optional dependency: where argon2-cffi is unavailable we fall back to
# scrypt (also memory-hard, standard library), and both readers below still
# verify the legacy PBKDF2 hashes so existing accounts keep working. On the next
# successful login a legacy or weaker hash is transparently upgraded — see
# :func:`needs_rehash` and ``LicenseService.authenticate``.

try:  # pragma: no cover - depends on the environment
    from argon2 import PasswordHasher
    _PH: "PasswordHasher | None" = PasswordHasher(
        time_cost=3, memory_cost=64 * 1024, parallelism=1)
except Exception:  # noqa: BLE001 - argon2 is optional
    _PH = None

_SCRYPT_N = 2 ** 15  # 32768: memory-hard cost for the stdlib fallback


def hash_password(password: str, *, rounds: int = _PBKDF2_ROUNDS) -> str:
    """Hash *password* with the strongest scheme available (Argon2id first)."""
    if not password:
        raise AuthError("Password must not be empty.")
    if _PH is not None:
        return _PH.hash(password)                      # "$argon2id$..."
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N,
                            r=8, p=1, dklen=32)
    return f"scrypt${_SCRYPT_N}${salt.hex()}${digest.hex()}"


def _verify_scrypt(password: str, stored: str) -> bool:
    try:
        _algo, n_s, salt_hex, hash_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=int(n_s),
                                r=8, p=1, dklen=len(expected))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest, expected)


def _verify_pbkdf2(password: str, stored: str) -> bool:
    try:
        algo, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds_s))
    return hmac.compare_digest(digest, expected)


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of *password* against any supported hash scheme."""
    if not isinstance(stored, str) or not stored:
        return False
    if stored.startswith("$argon2"):
        if _PH is None:
            return False
        try:
            return _PH.verify(stored, password)
        except Exception:  # noqa: BLE001 - any argon2 error is a failed verify
            return False
    if stored.startswith("scrypt$"):
        return _verify_scrypt(password, stored)
    return _verify_pbkdf2(password, stored)


def needs_rehash(stored: str) -> bool:
    """Whether a valid hash should be upgraded (weaker scheme or stale params)."""
    if not isinstance(stored, str):
        return True
    if stored.startswith("$argon2"):
        if _PH is None:
            return False
        try:
            return _PH.check_needs_rehash(stored)
        except Exception:  # noqa: BLE001
            return False
    # A non-Argon2 hash (scrypt/pbkdf2) is upgraded once Argon2id is available.
    return _PH is not None


def _token_hash(value: str) -> str:
    """SHA-256 hex of a token/key (only the hash is ever stored)."""
    return hashlib.sha256(value.encode()).hexdigest()


# -- service ------------------------------------------------------------------

class LicenseService:
    """SQLite-backed accounts, licenses, tokens and Telegram pairings."""

    def __init__(self, db_path: str, *, token_ttl_hours: int = 720) -> None:
        self._db_path = db_path
        self._token_ttl = token_ttl_hours * 3600
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                telegram_user_id INTEGER,
                telegram_verified INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                key_hash TEXT UNIQUE NOT NULL,
                plan TEXT NOT NULL DEFAULT 'standard',
                issued_at REAL NOT NULL,
                expires_at REAL,
                revoked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pairings (
                code TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                key_hash TEXT UNIQUE NOT NULL,
                prefix TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                last_used_at REAL,
                revoked INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
            """
        )
        # CREATE TABLE IF NOT EXISTS is a no-op against an existing table, so
        # a database created before telegram_user_id/telegram_verified were
        # added to this schema never gets them -- every telegram-login path
        # (redeem_telegram_login, confirm_pairing, get_account_by_telegram)
        # then fails with "no such column" (surfaces as an HTTP 500).
        columns = {row["name"] for row in
                self._conn.execute("PRAGMA table_info(accounts)")}
        if "telegram_user_id" not in columns:
            self._conn.execute(
                "ALTER TABLE accounts ADD COLUMN telegram_user_id INTEGER")
        if "telegram_verified" not in columns:
            self._conn.execute(
                "ALTER TABLE accounts ADD COLUMN telegram_verified "
                "INTEGER NOT NULL DEFAULT 0")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- accounts -------------------------------------------------------------

    def create_account(self, username: str, password: str) -> Account:
        """Create an account. Raises :class:`AuthError` if the name is taken."""
        username = username.strip().lower()
        if not username:
            raise AuthError("Username must not be empty.")
        now = time.time()
        try:
            cur = self._conn.execute(
                "INSERT INTO accounts (username, password_hash, created_at) "
                "VALUES (?, ?, ?)",
                (username, hash_password(password), now),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise AuthError("That username is already taken.") from exc
        audit.audit_event(audit.ACCOUNT_CREATED, principal=username)
        return self._account_row(int(cur.lastrowid))

    def _account_from_row(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            username=row["username"],
            telegram_user_id=row["telegram_user_id"],
            telegram_verified=bool(row["telegram_verified"]),
            active=bool(row["active"]),
            created_at=row["created_at"],
        )

    def _account_row(self, user_id: int) -> Account:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise AuthError("Account not found.")
        return self._account_from_row(row)

    def bootstrap_owner(self, username: str, password: str) -> Account | None:
        """Create the owner account from config, or align its password.

        Called on startup so the operator gets in with nothing more than an
        ``OWNER_USERNAME`` / ``OWNER_PASSWORD`` pair in the server's env — no
        CLI, no admin key. The env is the source of truth: an existing account
        has its password reset to match, and a re-activated one is switched back
        on. Ownership itself is decided elsewhere (the username matching
        ``owner_username``); this only guarantees the account exists to log in to.
        """
        username = (username or "").strip().lower()
        if not username or not password:
            return None
        existing = self.get_account(username)
        if existing is None:
            audit.audit_event(audit.OWNER_BOOTSTRAP, principal=username,
                            detail="created")
            return self.create_account(username, password)
        self.change_password(username, password)
        if not existing.active:
            self.set_active(username, True)
        audit.audit_event(audit.OWNER_BOOTSTRAP, principal=username,
                        detail="realigned")
        return self._account_row(existing.id)

    def get_account(self, username: str) -> Account | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
        return self._account_from_row(row) if row else None

    def get_account_by_telegram(self, telegram_user_id: int) -> Account | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE telegram_user_id = ? "
            "AND telegram_verified = 1",
            (telegram_user_id,),
        ).fetchone()
        return self._account_from_row(row) if row else None

    def ensure_account_for_telegram(self, telegram_user_id: int) -> Account:
        """The account bound to this Telegram user, creating one if needed.

        Shared by :meth:`redeem_telegram_login` (silent, via a bot-issued code)
        and the bot's own "set a password" flow (explicit — so a person can
        also sign in with a username and password, which matters the moment
        they set the app up on a second machine and would rather not fetch a
        fresh code from Telegram every time).

        A freshly created account gets a random password nobody is ever told;
        it is reachable only through a login code until someone calls
        :meth:`change_password` on it.
        """
        tg = int(telegram_user_id)
        acc = self.get_account_by_telegram(tg)
        if acc is not None:
            return acc
        username = f"tg{tg}"
        if self.get_account(username) is not None:
            username = f"tg{tg}_{secrets.token_hex(2)}"
        acc = self.create_account(username, secrets.token_urlsafe(16))
        self._conn.execute(
            "UPDATE accounts SET telegram_user_id = ?, telegram_verified = 1 "
            "WHERE id = ?", (tg, acc.id))
        self._conn.commit()
        return self._account_row(acc.id)

    def set_active(self, username: str, active: bool) -> None:
        self._conn.execute(
            "UPDATE accounts SET active = ? WHERE username = ?",
            (1 if active else 0, username.strip().lower()),
        )
        self._conn.commit()

    def change_password(self, username: str, new_password: str) -> None:
        self._conn.execute(
            "UPDATE accounts SET password_hash = ? WHERE username = ?",
            (hash_password(new_password), username.strip().lower()),
        )
        self._conn.commit()

    # -- authentication -------------------------------------------------------

    def authenticate(self, username: str, password: str, *,
                    require_license: bool = False) -> Account:
        """Verify credentials; return the account or raise.

        A licence is **not** required to sign in. There is a Free tier, and a
        free user has to be able to get in — otherwise the only way into the
        product is to have already paid, and nobody can see what they would be
        buying. What a licence changes is the *tier* (see
        :mod:`jarvis.billing.entitlements`), not whether the door opens.

        ``require_license=True`` restores the stricter behaviour for a
        deployment sold as licence-only.
        """
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
        # Always run a hash to keep timing uniform for unknown usernames.
        stored = row["password_hash"] if row else hash_password("x")
        if not verify_password(password, stored) or row is None:
            audit.audit_event(audit.LOGIN_FAIL, principal=username, ok=False,
                            detail="bad credentials")
            raise AuthError("Invalid username or password.")
        account = self._account_from_row(row)
        if not account.active:
            audit.audit_event(audit.LOGIN_FAIL, principal=username, ok=False,
                            detail="account disabled")
            raise AuthError("This account is disabled.")
        # Transparent upgrade: a legacy PBKDF2/scrypt hash (or stale Argon2
        # params) is re-hashed with the current scheme now that we hold the
        # plaintext, so accounts drift to Argon2id without a password reset.
        if needs_rehash(stored):
            try:
                self.change_password(account.username, password)
            except Exception:  # noqa: BLE001 - login must not fail on an upgrade
                pass
        if require_license and not self.has_active_license(account.id):
            audit.audit_event(audit.LOGIN_FAIL, principal=username, ok=False,
                            detail="no active licence")
            raise AuthError("No active license for this account.")
        audit.audit_event(audit.LOGIN_OK, principal=account.username)
        return account

    # -- login tokens ---------------------------------------------------------

    def issue_token(self, user_id: int) -> str:
        """Create and return a plaintext bearer token (stored hashed)."""
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._conn.execute(
            "INSERT INTO tokens (token_hash, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (_token_hash(token), user_id, now, now + self._token_ttl),
        )
        self._conn.commit()
        return token

    def validate_token(self, token: str) -> Account | None:
        """Return the account for a valid, unexpired token, else ``None``."""
        if not token:
            return None
        row = self._conn.execute(
            "SELECT a.* FROM tokens t JOIN accounts a ON a.id = t.user_id "
            "WHERE t.token_hash = ? AND t.expires_at > ? AND a.active = 1",
            (_token_hash(token), time.time()),
        ).fetchone()
        return self._account_from_row(row) if row else None

    def revoke_token(self, token: str) -> None:
        self._conn.execute(
            "DELETE FROM tokens WHERE token_hash = ?", (_token_hash(token),)
        )
        self._conn.commit()

    def purge_expired_tokens(self) -> int:
        cur = self._conn.execute(
            "DELETE FROM tokens WHERE expires_at <= ?", (time.time(),)
        )
        self._conn.commit()
        return cur.rowcount

    # -- API keys -------------------------------------------------------------
    #
    # These are the credential behind "API от меня". Unlike a login token they
    # do not expire on a clock — a person pastes one into their own tool and
    # expects it to keep working — so they are long-lived, listable and
    # individually revocable. Only the hash is stored; the plaintext is shown
    # once, at creation. A short prefix is kept in the clear so a person can
    # tell their keys apart in a list without us ever holding the secret.

    #: Human-readable start of every proxy key, so it is obvious what it is.
    API_KEY_PREFIX = "ker-"

    def create_api_key(self, user_id: int, *, label: str = "") -> str:
        """Mint a new API key for an account; returns the plaintext once."""
        key = self.API_KEY_PREFIX + secrets.token_urlsafe(30)
        display = key[:12]              # e.g. "ker-Ab3xQ" — enough to recognise
        self._conn.execute(
            "INSERT INTO api_keys (user_id, key_hash, prefix, label, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, _token_hash(key), display, label.strip()[:60], time.time()),
        )
        self._conn.commit()
        audit.audit_event(audit.APIKEY_CREATED, principal=f"id:{user_id}",
                        detail=f"prefix={display}")
        return key

    def validate_api_key(self, key: str) -> Account | None:
        """Return the account for a live key, else ``None`` (and stamp usage)."""
        if not key or not key.startswith(self.API_KEY_PREFIX):
            return None
        row = self._conn.execute(
            "SELECT a.*, k.id AS key_id FROM api_keys k "
            "JOIN accounts a ON a.id = k.user_id "
            "WHERE k.key_hash = ? AND k.revoked = 0 AND a.active = 1",
            (_token_hash(key),),
        ).fetchone()
        if row is None:
            return None
        # Best-effort last-used stamp; a write failure must not deny a valid key.
        try:
            self._conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (time.time(), row["key_id"]),
            )
            self._conn.commit()
        except sqlite3.Error:  # pragma: no cover - stamping is a nicety
            pass
        return self._account_from_row(row)

    def list_api_keys(self, user_id: int) -> list[dict]:
        """Live keys for an account — metadata only, never the secret."""
        rows = self._conn.execute(
            "SELECT id, prefix, label, created_at, last_used_at FROM api_keys "
            "WHERE user_id = ? AND revoked = 0 ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "prefix": r["prefix"],
                "label": r["label"],
                "created_at": r["created_at"],
                "last_used_at": r["last_used_at"],
            }
            for r in rows
        ]

    def revoke_api_key(self, user_id: int, key_id: int) -> bool:
        """Revoke one key, but only if it belongs to this account."""
        cur = self._conn.execute(
            "UPDATE api_keys SET revoked = 1 WHERE id = ? AND user_id = ? "
            "AND revoked = 0",
            (key_id, user_id),
        )
        self._conn.commit()
        if cur.rowcount > 0:
            audit.audit_event(audit.APIKEY_REVOKED, principal=f"id:{user_id}",
                            detail=f"key_id={key_id}")
        return cur.rowcount > 0

    # -- licenses -------------------------------------------------------------

    def issue_license(
        self,
        user_id: int,
        *,
        plan: str = "standard",
        valid_days: int | None = None,
    ) -> str:
        """Grant a license and return the plaintext key (shown once)."""
        key = f"JVS-{secrets.token_urlsafe(24)}"
        now = time.time()
        expires = now + valid_days * 86400 if valid_days else None
        self._conn.execute(
            "INSERT INTO licenses (user_id, key_hash, plan, issued_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, _token_hash(key), plan, now, expires),
        )
        self._conn.commit()
        return key

    def has_active_license(self, user_id: int, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        row = self._conn.execute(
            "SELECT 1 FROM licenses WHERE user_id = ? AND revoked = 0 "
            "AND (expires_at IS NULL OR expires_at > ?) LIMIT 1",
            (user_id, now),
        ).fetchone()
        return row is not None

    def revoke_license_by_key(self, key: str) -> bool:
        cur = self._conn.execute(
            "UPDATE licenses SET revoked = 1 WHERE key_hash = ?",
            (_token_hash(key),),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_licenses(self, user_id: int) -> list[License]:
        rows = self._conn.execute(
            "SELECT * FROM licenses WHERE user_id = ? ORDER BY issued_at DESC",
            (user_id,),
        ).fetchall()
        return [
            License(
                id=r["id"],
                user_id=r["user_id"],
                plan=r["plan"],
                issued_at=r["issued_at"],
                expires_at=r["expires_at"],
                revoked=bool(r["revoked"]),
            )
            for r in rows
        ]

    # -- overview / admin -------------------------------------------------

    def stats(self) -> dict:
        """Aggregate account/license counters for the admin panel."""
        now = time.time()
        row = self._conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(active) AS active, "
            "SUM(telegram_verified) AS linked FROM accounts"
        ).fetchone()
        licensed = self._conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM licenses "
            "WHERE revoked = 0 AND (expires_at IS NULL OR expires_at > ?)",
            (now,),
        ).fetchone()[0]
        return {
            "accounts": row["total"] or 0,
            "active_accounts": row["active"] or 0,
            "telegram_linked": row["linked"] or 0,
            "licensed_accounts": licensed or 0,
        }

    def list_accounts(self, limit: int = 20) -> list[Account]:
        """Most recently created accounts first."""
        rows = self._conn.execute(
            "SELECT * FROM accounts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._account_from_row(r) for r in rows]

    # -- Telegram pairing -----------------------------------------------------

    def create_pairing_code(self, user_id: int, *, ttl_seconds: int = 600) -> str:
        """Create a short code the user sends to the bot to link Telegram."""
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
                    for _ in range(8))
        now = time.time()
        self._conn.execute(
            "INSERT INTO pairings (code, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (code, user_id, now, now + ttl_seconds),
        )
        self._conn.commit()
        return code

    def _ensure_login_codes_table(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tg_login_codes ("
            " code TEXT PRIMARY KEY, telegram_user_id INTEGER NOT NULL,"
            " expires_at REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0)")

    def create_telegram_login_code(self, telegram_user_id: int, *,
                                ttl_seconds: int = 600) -> str:
        """A short code a Telegram user redeems to sign into a desktop/app."""
        self._ensure_login_codes_table()
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        self._conn.execute(
            "INSERT OR REPLACE INTO tg_login_codes "
            "(code, telegram_user_id, expires_at, used) VALUES (?, ?, ?, 0)",
            (code, int(telegram_user_id), time.time() + ttl_seconds))
        self._conn.commit()
        return code

    def redeem_telegram_login(self, code: str) -> tuple[str, str] | None:
        """Redeem a login code → (token, username).

        Creates an account bound to the Telegram user on first use, so a person
        can sign in with Telegram alone (no password).
        """
        self._ensure_login_codes_table()
        code = (code or "").strip()
        row = self._conn.execute(
            "SELECT telegram_user_id FROM tg_login_codes WHERE code = ? AND "
            "used = 0 AND expires_at > ?", (code, time.time())).fetchone()
        if row is None:
            return None
        tg = int(row["telegram_user_id"])
        self._conn.execute(
            "UPDATE tg_login_codes SET used = 1 WHERE code = ?", (code,))
        self._conn.commit()
        acc = self.ensure_account_for_telegram(tg)
        return self.issue_token(acc.id), acc.username

    def confirm_pairing(self, code: str, telegram_user_id: int) -> Account | None:
        """Bind *telegram_user_id* to the account for a valid pairing code."""
        code = code.strip().upper()
        row = self._conn.execute(
            "SELECT user_id FROM pairings WHERE code = ? AND used = 0 "
            "AND expires_at > ?",
            (code, time.time()),
        ).fetchone()
        if row is None:
            return None
        user_id = row["user_id"]
        with self._conn:
            self._conn.execute(
                "UPDATE pairings SET used = 1 WHERE code = ?", (code,)
            )
            self._conn.execute(
                "UPDATE accounts SET telegram_user_id = ?, telegram_verified = 1 "
                "WHERE id = ?",
                (telegram_user_id, user_id),
            )
        return self._account_row(user_id)
