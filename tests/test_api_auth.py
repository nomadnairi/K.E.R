"""Tests for the account/login flow on the API (auth enabled)."""

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
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False, rate_limit_enabled=False,
        api_key="", auth_enabled=True, auth_db_path=":memory:",
        auth_admin_key="admin-secret", **overrides,
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    return create_app(engine=engine, settings=settings)


def _seed(client) -> str:
    """Create an account + license via the admin API, return the password."""
    r = client.post("/admin/accounts",
                    json={"username": "tony", "password": "arcreactor"},
                    headers=ADMIN)
    assert r.status_code == 200, r.text
    r = client.post("/admin/licenses", json={"username": "tony"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["license_key"].startswith("JVS-")
    return "arcreactor"


def test_telegram_login_exchanges_code_for_token():
    app = _app()
    with TestClient(app) as client:
        # The bot would issue this; use the app's own service here.
        code = app.state.license_service.create_telegram_login_code(4242)
        r = client.post("/auth/telegram", json={"code": code})
        assert r.status_code == 200
        token = r.json()["token"]
        ok = client.post("/chat", json={"message": "hi"},
                        headers={"Authorization": f"Bearer {token}"})
        assert ok.status_code == 200
        assert client.post("/auth/telegram",
                        json={"code": "000000"}).status_code == 401


def test_admin_requires_key():
    with TestClient(_app()) as client:
        r = client.post("/admin/accounts",
                        json={"username": "x", "password": "y"})
        assert r.status_code == 403


def test_login_and_authenticated_chat():
    with TestClient(_app()) as client:
        _seed(client)
        # Wrong password rejected.
        assert client.post("/auth/login",
                        json={"username": "tony", "password": "nope"}
                        ).status_code == 401
        # Correct login returns a bearer token.
        r = client.post("/auth/login",
                        json={"username": "tony", "password": "arcreactor"})
        assert r.status_code == 200
        token = r.json()["token"]

        # Chat is rejected without a token, accepted with one.
        assert client.post("/chat", json={"message": "hi"}).status_code == 401
        auth = {"Authorization": f"Bearer {token}"}
        ok = client.post("/chat", json={"message": "hi"}, headers=auth)
        assert ok.status_code == 200
        assert ok.json()["reply"] == "Certainly, Sir."

        # /auth/me reflects the account.
        me = client.get("/auth/me", headers=auth).json()
        assert me["username"] == "tony" and me["telegram_verified"] is False


def test_an_account_without_a_licence_signs_in_as_free():
    """There is a Free tier, so the door opens; the licence sets the tier."""
    with TestClient(_app()) as client:
        client.post("/admin/accounts",
                    json={"username": "bruce", "password": "hulk"}, headers=ADMIN)
        out = client.post("/auth/login",
                        json={"username": "bruce", "password": "hulk"})
        assert out.status_code == 200
        me = client.get("/auth/me", headers={
            "Authorization": f"Bearer {out.json()['token']}"}).json()
        assert me["tier"] == "free"
        assert me["owner"] is False
        assert "chat" in me["features"]
        assert "pc_access" not in me["features"]


def test_a_licence_only_deployment_can_still_refuse():
    """Operators selling licence-only keep the stricter door."""
    with TestClient(_app(auth_require_license=True)) as client:
        client.post("/admin/accounts",
                    json={"username": "bruce", "password": "hulk"}, headers=ADMIN)
        assert client.post("/auth/login",
                        json={"username": "bruce", "password": "hulk"}
                        ).status_code == 401


def test_logout_revokes_token():
    with TestClient(_app()) as client:
        _seed(client)
        token = client.post("/auth/login",
                            json={"username": "tony", "password": "arcreactor"}
                            ).json()["token"]
        auth = {"Authorization": f"Bearer {token}"}
        assert client.post("/auth/logout", headers=auth).status_code == 200
        assert client.get("/auth/me", headers=auth).status_code == 401


def test_pairing_code_issued():
    with TestClient(_app()) as client:
        _seed(client)
        token = client.post("/auth/login",
                            json={"username": "tony", "password": "arcreactor"}
                            ).json()["token"]
        auth = {"Authorization": f"Bearer {token}"}
        r = client.post("/auth/pairing-code", headers=auth)
        assert r.status_code == 200
        assert len(r.json()["code"]) == 8


def test_websocket_requires_token():
    from starlette.websockets import WebSocketDisconnect

    with TestClient(_app()) as client:
        _seed(client)
        token = client.post("/auth/login",
                            json={"username": "tony", "password": "arcreactor"}
                            ).json()["token"]
        # No token → rejected.
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/s1") as ws:
                ws.receive_text()
        # With token → streams.
        import json
        with client.websocket_connect(f"/ws/s1?key={token}") as ws:
            ws.send_text("hello")
            chunks = []
            while True:
                frame = ws.receive_text()
                try:
                    payload = json.loads(frame)
                except json.JSONDecodeError:
                    chunks.append(frame)
                    continue
                if isinstance(payload, dict) and payload.get("event") == "done":
                    break
                chunks.append(frame)
            assert "".join(chunks) == "Certainly, Sir."


# -- the plan the client is told about --------------------------------------

def test_a_licence_puts_the_account_on_that_tier():
    with TestClient(_app()) as client:
        client.post("/admin/accounts",
                    json={"username": "tony", "password": "ironman"},
                    headers=ADMIN)
        client.post("/admin/licenses",
                    json={"username": "tony", "plan": "pro"}, headers=ADMIN)
        token = client.post("/auth/login",
                            json={"username": "tony", "password": "ironman"}
                            ).json()["token"]
        me = client.get("/auth/me",
                        headers={"Authorization": f"Bearer {token}"}).json()
        assert me["tier"] == "pro"
        assert "pc_access" in me["features"]
        assert me["plan"]["unlimited"] is True


def test_the_operator_account_gets_everything():
    with TestClient(_app(owner_username="boss")) as client:
        client.post("/admin/accounts",
                    json={"username": "boss", "password": "secret"},
                    headers=ADMIN)
        token = client.post("/auth/login",
                            json={"username": "boss", "password": "secret"}
                            ).json()["token"]
        me = client.get("/auth/me",
                        headers={"Authorization": f"Bearer {token}"}).json()
        assert me["owner"] is True
        assert me["tier"] == "pro"
        assert me["usage"]["remaining_today"] is None      # nothing counted
        assert all(c["included"] for c in me["capabilities"])


def test_the_profile_says_what_is_enforced_and_what_is_packaging():
    """A client must be able to tell a real refusal from a sales boundary."""
    with TestClient(_app()) as client:
        client.post("/admin/accounts",
                    json={"username": "sam", "password": "falcon"},
                    headers=ADMIN)
        token = client.post("/auth/login",
                            json={"username": "sam", "password": "falcon"}
                            ).json()["token"]
        me = client.get("/auth/me",
                        headers={"Authorization": f"Bearer {token}"}).json()
        assert "pc_access" in me["local_only"]
        assert "images" in me["enforced_server_side"]
        assert not set(me["local_only"]) & set(me["enforced_server_side"])
