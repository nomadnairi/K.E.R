"""
Tests for GET /dashboard/devices and POST /dashboard/devices/revoke
(Этап 2 / Фаза A4) — the Device Manager backend.

Before this endpoint existed, DeviceRegistry.describe() (live desktop-control
connections) and LicenseService.list_sessions() (persisted login history,
Фаза A2) each held half the picture and neither was reachable over HTTP —
there was no way for a client to ask "what does my account have logged in
right now." This endpoint merges the two and scopes strictly to the caller's
own account, the same isolation /dashboard/mcp and /dashboard/memory already
enforce.
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


def _create_account(client, username: str, password: str) -> str:
    r = client.post("/admin/accounts", json={"username": username, "password": password},
                    headers=ADMIN)
    assert r.status_code == 200, r.text
    return _token(client, username, password)


def test_devices_empty_by_default():
    with TestClient(_app()) as client:
        token = _token(client, "tony", "arcreactor123")
        r = client.get("/dashboard/devices", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["live_devices"] == []
        # The login just performed is itself a session.
        assert len(body["sessions"]) == 1
        assert body["sessions"][0]["online"] is False


def test_devices_requires_auth():
    with TestClient(_app()) as client:
        assert client.get("/dashboard/devices").status_code == 401


def test_devices_shows_a_live_desktop_connection_as_online():
    app = _app()
    with TestClient(app) as client:
        token = _token(client, "tony", "arcreactor123")
        with client.websocket_connect(f"/device/ws?key={token}") as ws:
            ws.send_json({"device_id": "laptop-1", "capabilities": ["desktop.open_url"]})
            r = client.get("/dashboard/devices",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            body = r.json()
            assert [d["device_id"] for d in body["live_devices"]] == ["laptop-1"]
        # After the socket closes, the live entry disappears.
        r = client.get("/dashboard/devices", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["live_devices"] == []


def test_devices_are_isolated_between_accounts():
    with TestClient(_app()) as client:
        tok_a = _create_account(client, "alice", "password1")
        tok_b = _create_account(client, "bob", "password2")

        r_a = client.get("/dashboard/devices", headers={"Authorization": f"Bearer {tok_a}"})
        r_b = client.get("/dashboard/devices", headers={"Authorization": f"Bearer {tok_b}"})

        # Each sees only their own single login session, never the other's.
        assert len(r_a.json()["sessions"]) == 1
        assert len(r_b.json()["sessions"]) == 1


def test_revoke_ends_the_named_session():
    with TestClient(_app()) as client:
        token = _token(client, "tony", "arcreactor123")
        session_id = client.get(
            "/dashboard/devices", headers={"Authorization": f"Bearer {token}"}
        ).json()["sessions"][0]["id"]

        r = client.post("/dashboard/devices/revoke", json={"id": session_id},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

        # The very token used to revoke it is now itself revoked.
        r2 = client.get("/dashboard/devices", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 401


def test_revoke_cannot_touch_another_accounts_session():
    with TestClient(_app()) as client:
        tok_a = _create_account(client, "alice", "password1")
        tok_b = _create_account(client, "bob", "password2")
        alice_session_id = client.get(
            "/dashboard/devices", headers={"Authorization": f"Bearer {tok_a}"}
        ).json()["sessions"][0]["id"]

        r = client.post("/dashboard/devices/revoke", json={"id": alice_session_id},
                        headers={"Authorization": f"Bearer {tok_b}"})
        assert r.status_code == 404

        # Alice's session survives Bob's attempt.
        r2 = client.get("/dashboard/devices", headers={"Authorization": f"Bearer {tok_a}"})
        assert r2.status_code == 200


def test_revoke_unknown_id_is_404():
    with TestClient(_app()) as client:
        token = _token(client, "tony", "arcreactor123")
        r = client.post("/dashboard/devices/revoke", json={"id": "not-a-real-session"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404


def test_devices_with_no_accounts_shows_no_session_history():
    # Fully open/shared-key mode: no LicenseService, so no session history —
    # only whatever is live in DeviceRegistry (empty here), never a crash.
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False, rate_limit_enabled=False,
        api_key="",
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    with TestClient(create_app(engine=engine, settings=settings)) as client:
        r = client.get("/dashboard/devices")
        assert r.status_code == 200
        assert r.json() == {"live_devices": [], "sessions": []}
