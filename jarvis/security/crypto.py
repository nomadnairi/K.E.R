"""
Authenticated encryption for data at rest (AES-256-GCM).

Sensitive user data the server has to hold — assistant memory, chat history,
document text, any stored third-party secret — should be ciphertext on disk, so
a stolen database is useless without the key. This module is that primitive: a
small :class:`SecretBox` over AES-256-GCM (AEAD — confidentiality *and*
integrity, a fresh random nonce per message), plus a :class:`KeyProvider` that
reads the key from the environment / a secret manager and **never** from source.

Design choices, on purpose:

* **The key never lives in code or the repo.** It comes from ``KER_DATA_KEY``
  (32 bytes, base64) — in production that env var is fed from a KMS/Vault. Ship
  without a key and encryption is simply *off* (``SecretBox.enabled is False``):
  callers store plaintext in dev and opt in by setting the key. This keeps the
  door open to envelope encryption later without changing call sites.
* **Versioned, self-describing tokens** (``v1:<b64 nonce+ct+tag>``) so the
  scheme can rotate and a reader can tell an encrypted value from a plain one.
* **cryptography is an optional import**: if a key is set but the library is
  missing, we fail loud rather than silently store plaintext.
"""

from __future__ import annotations

import base64
import os

#: Marker prefix for a ciphertext token, so plaintext and ciphertext are
#: distinguishable and the format can be versioned.
_PREFIX = "v1:"
_NONCE = 12  # AES-GCM standard nonce length


class SecretBox:
    """Encrypt/decrypt short values with AES-256-GCM under one key.

    With no key it is a transparent pass-through (``enabled`` is False), so the
    same call sites work in development and switch to real encryption the moment
    a key is provided.
    """

    def __init__(self, key: bytes | None) -> None:
        if key is not None and len(key) != 32:
            raise ValueError("Data key must be exactly 32 bytes (AES-256).")
        self._key = key
        self._aead = None
        if key is not None:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            except Exception as exc:  # noqa: BLE001 - fail loud, never silent
                raise RuntimeError(
                    "A data-encryption key is set but 'cryptography' is not "
                    "installed. Install it or unset KER_DATA_KEY.") from exc
            self._aead = AESGCM(key)

    @property
    def enabled(self) -> bool:
        """True when a key is present and values are actually encrypted."""
        return self._aead is not None

    def encrypt(self, plaintext: str, *, aad: str = "") -> str:
        """Return a ``v1:`` token, or the plaintext unchanged when disabled.

        ``aad`` is authenticated-but-not-encrypted associated data (e.g. the
        owning principal), binding the ciphertext to its context so it cannot be
        transplanted to another row.
        """
        if self._aead is None:
            return plaintext
        nonce = os.urandom(_NONCE)
        ct = self._aead.encrypt(nonce, plaintext.encode("utf-8"),
                                aad.encode("utf-8") if aad else None)
        return _PREFIX + base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, token: str, *, aad: str = "") -> str:
        """Reverse :meth:`encrypt`. A non-token value is returned as-is.

        Legacy plaintext (written before a key was set) round-trips unchanged,
        so turning encryption on does not orphan existing rows.
        """
        if not isinstance(token, str) or not token.startswith(_PREFIX):
            return token
        if self._aead is None:
            raise RuntimeError(
                "Found encrypted data but no key is configured (KER_DATA_KEY).")
        raw = base64.b64decode(token[len(_PREFIX):])
        nonce, ct = raw[:_NONCE], raw[_NONCE:]
        pt = self._aead.decrypt(nonce, ct, aad.encode("utf-8") if aad else None)
        return pt.decode("utf-8")

    def is_encrypted(self, value: str) -> bool:
        return isinstance(value, str) and value.startswith(_PREFIX)


class KeyProvider:
    """Where the data key comes from — the environment / a secret manager.

    The key is 32 raw bytes, supplied base64-encoded in ``KER_DATA_KEY``. In
    production that variable is injected from a KMS/Vault, never committed. A
    convenience :meth:`generate` prints a fresh key for first setup.
    """

    ENV_VAR = "KER_DATA_KEY"

    @classmethod
    def load(cls, env: dict | None = None) -> bytes | None:
        raw = (env or os.environ).get(cls.ENV_VAR, "").strip()
        if not raw:
            return None
        try:
            key = base64.b64decode(raw)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{cls.ENV_VAR} must be base64-encoded.") from exc
        if len(key) != 32:
            raise ValueError(f"{cls.ENV_VAR} must decode to 32 bytes (AES-256).")
        return key

    @classmethod
    def box(cls, env: dict | None = None) -> SecretBox:
        """A :class:`SecretBox` built from the configured key (or pass-through)."""
        return SecretBox(cls.load(env))

    @staticmethod
    def generate() -> str:
        """A fresh base64 key for ``KER_DATA_KEY`` (store it in your secrets)."""
        return base64.b64encode(os.urandom(32)).decode("ascii")
