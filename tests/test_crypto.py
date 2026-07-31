"""AES-256-GCM data-at-rest encryption and the key provider.

The box turns sensitive fields into ciphertext on disk when a key is set, and is
a transparent pass-through when it is not — so the same call sites work in dev
and switch to real encryption the moment KER_DATA_KEY is provided.
"""

from __future__ import annotations

import base64

import pytest

from jarvis.security.crypto import KeyProvider, SecretBox

pytest.importorskip("cryptography")


def _key() -> bytes:
    import os
    return os.urandom(32)


def test_roundtrip_with_a_key():
    box = SecretBox(_key())
    assert box.enabled is True
    token = box.encrypt("secret value")
    assert token.startswith("v1:") and "secret value" not in token
    assert box.decrypt(token) == "secret value"


def test_without_a_key_it_is_pass_through():
    box = SecretBox(None)
    assert box.enabled is False
    assert box.encrypt("hello") == "hello"
    assert box.decrypt("hello") == "hello"


def test_ciphertext_is_random_each_time():
    box = SecretBox(_key())
    assert box.encrypt("x") != box.encrypt("x")     # fresh nonce per message


def test_tampering_is_detected():
    box = SecretBox(_key())
    token = box.encrypt("important")
    bad = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(Exception):                  # GCM tag fails
        box.decrypt(bad)


def test_aad_binds_ciphertext_to_its_context():
    box = SecretBox(_key())
    token = box.encrypt("ann's note", aad="user:ann")
    # The same box cannot read it under a different principal.
    with pytest.raises(Exception):
        box.decrypt(token, aad="user:bob")
    assert box.decrypt(token, aad="user:ann") == "ann's note"


def test_a_wrong_length_key_is_rejected():
    with pytest.raises(ValueError):
        SecretBox(b"too-short")


def test_plaintext_survives_when_encryption_is_turned_on_later():
    # A value written before a key existed still reads back.
    plain = SecretBox(None)
    stored = plain.encrypt("legacy row")
    box = SecretBox(_key())
    assert box.decrypt(stored) == "legacy row"


def test_encrypted_data_without_a_key_fails_loud():
    token = SecretBox(_key()).encrypt("x")
    with pytest.raises(RuntimeError):
        SecretBox(None).decrypt(token)


# -- key provider ------------------------------------------------------------

def test_key_provider_reads_base64_env():
    key = _key()
    env = {"KER_DATA_KEY": base64.b64encode(key).decode()}
    assert KeyProvider.load(env) == key
    assert KeyProvider.box(env).enabled is True


def test_key_provider_empty_is_no_key():
    assert KeyProvider.load({}) is None
    assert KeyProvider.box({}).enabled is False


def test_key_provider_rejects_a_bad_length():
    env = {"KER_DATA_KEY": base64.b64encode(b"short").decode()}
    with pytest.raises(ValueError):
        KeyProvider.load(env)


def test_generate_makes_a_usable_key():
    env = {"KER_DATA_KEY": KeyProvider.generate()}
    assert KeyProvider.box(env).enabled is True
