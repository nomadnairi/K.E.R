"""
Regression tests for cross-tenant data exposure in /dashboard/*.

Before this fix, every /dashboard/memory* and /dashboard/sessions endpoint
read from the single shared JarvisEngine with no filter at all — any
authenticated account (even a Free-tier one, created for free through the
bot) could see, search and delete *every other account's* conversations and
memories on a server with accounts enabled, and "forget everything" wiped
the whole engine's memory, not just the caller's own. /dashboard/tasks had
the same problem for automations/reminders.

These tests prove the isolation actually holds between two real, distinct
accounts on the same engine — not just that the code runs.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from jarvis.api.app import create_app  # noqa: E402
from jarvis.config.settings import Settings  # noqa: E402
from jarvis.core.container import ServiceContainer  # noqa: E402
from jarvis.core.engine import JarvisEngine  # noqa: E402
from jarvis.llm.client import LLMClient  # noqa: E402
from jarvis.interfaces.automations import Automation, AutomationStore  # noqa: E402
from jarvis.interfaces.reminders import ReminderStore  # noqa: E402
from tests.conftest import FakeProvider  # noqa: E402

ADMIN = {"X-Admin-Key": "admin-secret"}


def _tenant_app(tmp_path):
    """A real, accounts-enabled, multi-tenant app sharing one engine — the
    exact shape of the hosted server this bug lived on."""
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=True,
        memory_backend="sqlite", memory_db_path=str(tmp_path / "m.db"),
        embedding_backend="hashing",
        integrations_enabled=False, goals_enabled=False,
        rate_limit_enabled=False, api_key="",
        auth_enabled=True, auth_db_path=str(tmp_path / "accounts.db"),
        auth_admin_key="admin-secret",
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    return engine, create_app(engine=engine, settings=settings), settings


def _account(client, username: str, password: str) -> dict:
    r = client.post("/admin/accounts", json={"username": username, "password": password},
                    headers=ADMIN)
    assert r.status_code == 200, r.text
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# -- memory: browse, search, delete, forget ----------------------------------


def test_one_account_cannot_browse_another_accounts_memory(tmp_path):
    engine, app, _settings = _tenant_app(tmp_path)
    asyncio.run(engine.memory.remember("user:alice::default",
                                    "Alice's secret", kind="fact"))
    asyncio.run(engine.memory.remember("user:bob::default",
                                    "Bob's own thing", kind="fact"))
    with TestClient(app) as client:
        alice = _account(client, "alice", "wonderland1")
        bob = _account(client, "bob", "thebuilder1")

        alice_view = client.get("/dashboard/memory", headers=alice).json()
        bob_view = client.get("/dashboard/memory", headers=bob).json()

        alice_contents = {i["content"] for i in alice_view["items"]}
        bob_contents = {i["content"] for i in bob_view["items"]}

        assert "Alice's secret" in alice_contents
        assert "Bob's own thing" not in alice_contents
        assert "Bob's own thing" in bob_contents
        assert "Alice's secret" not in bob_contents
        # Aggregate stats must not count the other tenant's records either.
        assert alice_view["stats"]["memories"] == 1


def test_one_account_cannot_search_up_another_accounts_memory(tmp_path):
    engine, app, _settings = _tenant_app(tmp_path)
    asyncio.run(engine.memory.remember("user:alice::default",
                                    "Alice lives in Tashkent", kind="fact"))
    with TestClient(app) as client:
        alice = _account(client, "alice", "wonderland1")
        bob = _account(client, "bob", "thebuilder1")

        bob_search = client.get("/dashboard/memory/search",
                                params={"q": "Tashkent"}, headers=bob).json()
        assert bob_search["items"] == []

        alice_search = client.get("/dashboard/memory/search",
                                params={"q": "Tashkent"}, headers=alice).json()
        assert any("Tashkent" in i["content"] for i in alice_search["items"])


def test_one_account_cannot_delete_another_accounts_memory_by_guessing_id(tmp_path):
    engine, app, _settings = _tenant_app(tmp_path)
    asyncio.run(engine.memory.remember("user:alice::default",
                                    "Alice's only memory", kind="fact"))
    with TestClient(app) as client:
        alice = _account(client, "alice", "wonderland1")
        bob = _account(client, "bob", "thebuilder1")

        record_id = client.get("/dashboard/memory", headers=alice).json()["items"][0]["id"]

        # Bob doesn't know it's Alice's — he just tries every small id, as an
        # attacker would.
        r = client.delete(f"/dashboard/memory/{record_id}", headers=bob)
        assert r.status_code == 404

        # It must still be there — Bob's attempt did not remove it.
        still_there = client.get("/dashboard/memory", headers=alice).json()
        assert any(i["id"] == record_id for i in still_there["items"])


def test_forget_everything_only_clears_the_callers_own_memory(tmp_path):
    engine, app, _settings = _tenant_app(tmp_path)
    asyncio.run(engine.memory.remember("user:alice::default",
                                    "Alice's memory", kind="fact"))
    asyncio.run(engine.memory.remember("user:bob::default",
                                    "Bob's memory", kind="fact"))
    with TestClient(app) as client:
        alice = _account(client, "alice", "wonderland1")
        bob = _account(client, "bob", "thebuilder1")

        r = client.post("/dashboard/memory/forget", json={"everything": True},
                        headers=bob)
        assert r.status_code == 200
        assert r.json()["stats"]["memories"] == 0  # Bob's own count, now zero

        # Alice's memory must be untouched by Bob's "forget everything".
        alice_view = client.get("/dashboard/memory", headers=alice).json()
        assert any(i["content"] == "Alice's memory" for i in alice_view["items"])


def test_sessions_list_shows_only_the_callers_own_conversations(tmp_path):
    engine, app, _settings = _tenant_app(tmp_path)
    asyncio.run(engine.memory.persist_turn(
        "user:alice::default", "hi from alice", "hello alice"))
    asyncio.run(engine.memory.persist_turn(
        "user:bob::default", "hi from bob", "hello bob"))
    with TestClient(app) as client:
        alice = _account(client, "alice", "wonderland1")
        bob = _account(client, "bob", "thebuilder1")

        alice_sessions = client.get("/dashboard/sessions", headers=alice).json()["sessions"]
        bob_sessions = client.get("/dashboard/sessions", headers=bob).json()["sessions"]

        assert any("alice" in s["session_id"] for s in alice_sessions)
        assert not any("bob" in s["session_id"] for s in alice_sessions)
        assert any("bob" in s["session_id"] for s in bob_sessions)
        assert not any("alice" in s["session_id"] for s in bob_sessions)


def test_a_username_cannot_widen_its_own_scope_with_like_wildcards(tmp_path):
    # "ali" is a real account; "ali%" would, if the % were not escaped in the
    # LIKE pattern, match "ali" too and everyone whose name starts with it.
    engine, app, _settings = _tenant_app(tmp_path)
    asyncio.run(engine.memory.remember("user:ali::default",
                                    "Ali's private note", kind="fact"))
    with TestClient(app) as client:
        client.post("/admin/accounts",
                    json={"username": "ali%", "password": "wildcard99"},
                    headers=ADMIN)
        r = client.post("/auth/login",
                        json={"username": "ali%", "password": "wildcard99"})
        assert r.status_code == 200, r.text
        wild = {"Authorization": f"Bearer {r.json()['token']}"}

        view = client.get("/dashboard/memory", headers=wild).json()
        assert view["items"] == []


# -- tasks: automations + reminders -----------------------------------------


def test_tasks_are_empty_for_an_account_with_no_linked_telegram(tmp_path):
    _engine, app, _settings = _tenant_app(tmp_path)
    with TestClient(app) as client:
        alice = _account(client, "alice", "wonderland1")
        out = client.get("/dashboard/tasks", headers=alice).json()
        assert out == {"automations": [], "reminders": []}


def test_tasks_are_scoped_to_the_callers_linked_telegram_id(tmp_path):
    _engine, app, settings = _tenant_app(tmp_path)
    a_store = AutomationStore(settings.memory_db_path)
    r_store = ReminderStore(settings.memory_db_path)
    try:
        a_store.add(111, 111, Automation(kind="daily", prompt="alice's daily brief"),
                    next_ts=9_999_999_999.0)
        a_store.add(222, 222, Automation(kind="daily", prompt="bob's daily brief"),
                    next_ts=9_999_999_999.0)
        r_store.add(111, 111, "alice's reminder", due_ts=9_999_999_999.0)
        r_store.add(222, 222, "bob's reminder", due_ts=9_999_999_999.0)
    finally:
        a_store.close()
        r_store.close()

    with TestClient(app) as client:
        from jarvis.licensing import LicenseService

        svc = LicenseService(db_path=settings.auth_db_path)
        try:
            alice_acc = svc.ensure_account_for_telegram(111)
            svc.change_password(alice_acc.username, "wonderland1")
        finally:
            svc.close()

        r = client.post("/auth/login",
                        json={"username": alice_acc.username, "password": "wonderland1"})
        assert r.status_code == 200, r.text
        alice = {"Authorization": f"Bearer {r.json()['token']}"}

        out = client.get("/dashboard/tasks", headers=alice).json()
        prompts = [a["prompt"] for a in out["automations"]]
        texts = [r["text"] for r in out["reminders"]]
        assert "alice's daily brief" in prompts
        assert "bob's daily brief" not in prompts
        assert "alice's reminder" in texts
        assert "bob's reminder" not in texts


# -- single-tenant deployments keep their old, unscoped behaviour -----------


def test_single_tenant_deployment_is_unaffected(tmp_path):
    """No accounts configured: exactly one legitimate caller, so the old
    behaviour (see a bare "default" session with no principal prefix at all)
    must keep working — this is the local desktop / self-hosted case."""
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=True,
        memory_backend="sqlite", memory_db_path=str(tmp_path / "m.db"),
        embedding_backend="hashing",
        integrations_enabled=False, goals_enabled=False,
        rate_limit_enabled=False, api_key="",
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    app = create_app(engine=engine, settings=settings)
    asyncio.run(engine.memory.remember("default", "the only user's note",
                                    kind="fact"))
    with TestClient(app) as client:
        view = client.get("/dashboard/memory").json()
        assert any(i["content"] == "the only user's note" for i in view["items"])
