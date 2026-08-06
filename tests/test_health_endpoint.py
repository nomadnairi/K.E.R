"""
Regression tests for locking down /health.

Before this fix, GET /health was open to anyone and returned full
diagnostics: which LLM providers have working credentials, whether
memory/goals/integrations are enabled, which dangerous capabilities
(file write / shell / desktop control) are turned on, config validation
errors, and security-audit findings with severity. That is a map of the
server's attack surface, handed out to anyone who can reach the port with
no authentication at all.

/health now returns only {"ok": true} — enough for Docker's healthcheck,
which only looks at the HTTP status code. The old payload moved to
/health/full, gated the same way /dashboard/mcp already is: only the
server owner (the shared API_KEY holder, or the OWNER_USERNAME account)
can read it.
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

ADMIN = {"X-Admin-Key": "admin-secret"}


def _app(**overrides):
    overrides.setdefault("api_key", "")
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False, rate_limit_enabled=False,
        auth_enabled=True, auth_db_path=":memory:",
        auth_admin_key="admin-secret",
        owner_username="tony", owner_password="arcreactor123",
        **overrides,
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    return create_app(engine=engine, settings=settings)


def _token(client, username: str, password: str) -> str:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _customer(client) -> str:
    r = client.post("/admin/accounts",
                    json={"username": "villain", "password": "goldfinger1"},
                    headers=ADMIN)
    assert r.status_code == 200, r.text
    return _token(client, "villain", "goldfinger1")


def test_health_reveals_nothing():
    with TestClient(_app()) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


def test_health_needs_no_auth_for_the_docker_healthcheck():
    # docker-compose's healthcheck hits this with no credentials at all and
    # only cares about the status code — this must never start requiring auth.
    with TestClient(_app()) as client:
        assert client.get("/health").status_code == 200


def test_health_full_is_401_with_no_credentials():
    with TestClient(_app()) as client:
        r = client.get("/health/full")
        assert r.status_code == 401


def test_health_full_is_403_for_a_regular_customer():
    with TestClient(_app()) as client:
        token = _customer(client)
        r = client.get("/health/full", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


def test_health_full_works_for_the_owner_account():
    with TestClient(_app()) as client:
        token = _token(client, "tony", "arcreactor123")
        r = client.get("/health/full", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert "ok" in body
        assert isinstance(body["checks"], list)
        # The detail that used to leak through the open /health.
        assert any(c["name"] == "llm" for c in body["checks"])
        assert any(c["name"] == "security_audit" for c in body["checks"])


def test_health_full_works_for_the_shared_api_key():
    # Same trust level as the owner account (see /dashboard/mcp).
    with TestClient(_app(api_key="ops-secret")) as client:
        r = client.get("/health/full", headers={"X-Api-Key": "ops-secret"})
        assert r.status_code == 200
        assert isinstance(r.json()["checks"], list)
