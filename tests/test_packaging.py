"""The Docker image's dependency install must actually match pyproject.toml.

The Dockerfile does:

    pip install -r requirements.txt
    pip install --no-deps .

``--no-deps`` means pyproject.toml's own ``dependencies`` list is *never*
consulted when building the image — only requirements.txt is. If a package
is added to pyproject.toml's dependencies but not mirrored into
requirements.txt, it silently never reaches the built image.

This is exactly how ``cryptography`` and ``argon2-cffi`` went missing from
production: both are declared in pyproject.toml (security-by-default:
Argon2id password hashing, AES-256-GCM encryption at rest), but
requirements.txt never listed them. Password hashing silently degraded to
scrypt, and the moment KER_DATA_KEY was set, jarvis/security/crypto.py
failed loud on startup with a bare RuntimeError, and the whole API
container never became healthy.

CI has the same gap — it also installs only from requirements.txt — which
is why tests guarded with ``pytest.importorskip("cryptography")`` were
silently skipped instead of failing.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _package_name(requirement: str) -> str | None:
    match = re.match(r"^\s*([A-Za-z0-9_.\-]+)", requirement)
    return match.group(1).lower() if match else None


def _pyproject_dependency_names() -> set[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"(?m)^dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
    assert match, "could not find [project] dependencies array in pyproject.toml"
    names = set()
    for item in re.findall(r'"([^"]+)"', match.group(1)):
        name = _package_name(item)
        if name:
            names.add(name)
    return names


def _requirements_txt_names() -> set[str]:
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name = _package_name(line)
        if name:
            names.add(name)
    return names


def test_requirements_txt_covers_every_core_pyproject_dependency():
    declared = _pyproject_dependency_names()
    pinned = _requirements_txt_names()
    missing = declared - pinned
    assert not missing, (
        f"pyproject.toml declares {sorted(missing)} as core dependencies, "
        "but requirements.txt does not pin them. The Docker image installs "
        "via `pip install -r requirements.txt` followed by "
        "`pip install --no-deps .`, so anything missing from requirements.txt "
        "silently never reaches the built image."
    )


def test_encryption_and_password_hashing_deps_are_pinned():
    """Narrow, explicit regression test for the exact incident."""
    pinned = _requirements_txt_names()
    assert "cryptography" in pinned, (
        "cryptography must be pinned in requirements.txt — without it, "
        "setting KER_DATA_KEY crashes the API on startup "
        "(jarvis/security/crypto.py raises RuntimeError instead of silently "
        "storing plaintext)."
    )
    assert "argon2-cffi" in pinned, (
        "argon2-cffi must be pinned in requirements.txt — without it, "
        "password hashing silently degrades from Argon2id to a weaker "
        "scrypt fallback in production."
    )
