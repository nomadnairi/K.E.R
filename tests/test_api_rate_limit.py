"""
Tests for the per-IP rate limiter on sensitive HTTP endpoints.

Before this, none of /auth/login, /auth/register or /auth/telegram had any
throttling on the HTTP layer at all — a password or a bot-issued 6-digit
Telegram login code could be guessed at whatever rate the network allowed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from jarvis.api.app import create_app  # noqa: E402
from jarvis.config.settings import Settings  # noqa: E402
from jarvis.core.container import ServiceContainer  # noqa: E402
from jarvis.core.engine import JarvisEngine  # noqa: E402
from jarvis.llm.client import LLMClient  # noqa: E402
from tests.conftest import FakeProvider  # noqa: E402


def _app(*, capacity: int = 3, window: float = 60.0, **overrides):
    overrides.setdefault("api_key", "")
    overrides.setdefault("api_auth_rate_limit_enabled", True)
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False, rate_limit_enabled=False,
        auth_enabled=True, auth_db_path=":memory:", auth_admin_key="admin-secret",
        api_auth_rate_limit_capacity=capacity,
        api_auth_rate_limit_window_seconds=window,
        **overrides,
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    return create_app(engine=engine, settings=settings)


def test_login_is_throttled_after_the_configured_number_of_attempts():
    with TestClient(_app(capacity=3)) as client:
        for _ in range(3):
            r = client.post("/auth/login",
                            json={"username": "nobody", "password": "wrong"})
            assert r.status_code == 401  # wrong credentials, but not yet blocked

        blocked = client.post("/auth/login",
                            json={"username": "nobody", "password": "wrong"})
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers


def test_registration_is_throttled_independently_of_login():
    # Two different routes must not share one bucket — exhausting one must
    # not block the other.
    with TestClient(_app(capacity=2)) as client:
        for _ in range(2):
            client.post("/auth/login", json={"username": "x", "password": "y"})
        blocked_login = client.post("/auth/login",
                                    json={"username": "x", "password": "y"})
        assert blocked_login.status_code == 429

        # Registration is closed on this server (auth_allow_signup defaults
        # to False) — 403, not 429 — proving its own bucket is still open.
        still_open = client.post("/auth/register",
                                json={"username": "new", "password": "password123"})
        assert still_open.status_code == 403


def test_telegram_code_exchange_is_throttled():
    with TestClient(_app(capacity=3)) as client:
        for _ in range(3):
            r = client.post("/auth/telegram", json={"code": "000000"})
            assert r.status_code == 401  # bad code, but not yet blocked
        blocked = client.post("/auth/telegram", json={"code": "000000"})
        assert blocked.status_code == 429


def test_change_password_is_throttled():
    """Этап 2 / Фаза B5 — a stolen bearer token should not buy unlimited
    guesses at the real password behind it."""
    with TestClient(_app(capacity=3, auth_allow_signup=True)) as client:
        client.post("/auth/register", json={"username": "ann", "password": "wonderland1"})
        token = client.post("/auth/login",
                            json={"username": "ann", "password": "wonderland1"}
                            ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        for _ in range(3):
            r = client.post("/auth/change-password",
                            json={"current_password": "wrong", "new_password": "newpass123"},
                            headers=headers)
            assert r.status_code == 401  # wrong current password, not yet blocked
        blocked = client.post("/auth/change-password",
                            json={"current_password": "wrong", "new_password": "newpass123"},
                            headers=headers)
        assert blocked.status_code == 429


def test_different_ips_get_independent_buckets(monkeypatch):
    with TestClient(_app(capacity=1)) as client:
        # Exhaust the default TestClient IP's bucket.
        client.post("/auth/login", json={"username": "a", "password": "b"})
        blocked = client.post("/auth/login", json={"username": "a", "password": "b"})
        assert blocked.status_code == 429

        # A different X-Forwarded-For is irrelevant while trust_proxy_headers
        # is off (the default) — the real socket peer is unchanged, so this
        # caller shares the same, already-exhausted bucket.
        still_blocked = client.post(
            "/auth/login", json={"username": "a", "password": "b"},
            headers={"X-Forwarded-For": "203.0.113.9"})
        assert still_blocked.status_code == 429


def test_trust_proxy_headers_reads_the_forwarded_client_address():
    with TestClient(_app(capacity=1, api_trust_proxy_headers=True)) as client:
        r1 = client.post("/auth/login", json={"username": "a", "password": "b"},
                        headers={"X-Forwarded-For": "203.0.113.1"})
        assert r1.status_code == 401
        blocked = client.post("/auth/login", json={"username": "a", "password": "b"},
                            headers={"X-Forwarded-For": "203.0.113.1"})
        assert blocked.status_code == 429

        # A different forwarded address is a different bucket, still open.
        other = client.post("/auth/login", json={"username": "a", "password": "b"},
                            headers={"X-Forwarded-For": "203.0.113.2"})
        assert other.status_code == 401  # not 429 — its own, fresh bucket


def test_routes_outside_the_sensitive_list_are_never_throttled():
    with TestClient(_app(capacity=1)) as client:
        # /auth/me has nothing to do with brute force and is not in the
        # throttled set; hammering it must never 429.
        for _ in range(10):
            r = client.get("/auth/me")
            assert r.status_code != 429


def test_disabled_by_setting():
    app = _app(capacity=1, api_auth_rate_limit_enabled=False)
    with TestClient(app) as client:
        for _ in range(10):
            r = client.post("/auth/login", json={"username": "x", "password": "y"})
            assert r.status_code != 429
