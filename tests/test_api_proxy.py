"""The hosted LLM proxy: auth, entitlement, metering and the OpenAI shape.

This is "API от меня" end to end — a signed-in account uses the operator's
models through the server, counted and revocable. These tests drive the real
FastAPI app with a fake provider behind the engine.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from jarvis.api.app import create_app  # noqa: E402
from jarvis.api.proxy_routes import (  # noqa: E402
    estimate_tokens,
    resolve_route,
    split_system,
)
from jarvis.config.settings import Settings  # noqa: E402
from jarvis.core.container import ServiceContainer  # noqa: E402
from jarvis.core.engine import JarvisEngine  # noqa: E402
from jarvis.llm.client import LLMClient  # noqa: E402
from tests.conftest import FakeProvider  # noqa: E402

ADMIN = {"X-Admin-Key": "admin-secret"}


def _app(**overrides):
    overrides.setdefault("proxy_enabled", True)
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        memory_db_path=":memory:", integrations_enabled=False,
        goals_enabled=False, rate_limit_enabled=False, api_key="",
        auth_enabled=True, auth_db_path=":memory:", auth_admin_key="admin-secret",
        **overrides,
    )
    llm = LLMClient(primary=FakeProvider(), profiles={"claude": FakeProvider()})
    engine = JarvisEngine(container=ServiceContainer(settings, llm_client=llm))
    return create_app(engine=engine, settings=settings)


def _plus_key(client, username="tony", password="arcreactor"):
    """A Plus account with a fresh API key; returns (token, api_key)."""
    client.post("/admin/accounts",
                json={"username": username, "password": password}, headers=ADMIN)
    client.post("/admin/licenses",
                json={"username": username, "plan": "standard"}, headers=ADMIN)
    token = client.post("/auth/login",
                        json={"username": username, "password": password}
                        ).json()["token"]
    key = client.post("/auth/api-keys", json={"label": "test"},
                    headers={"Authorization": f"Bearer {token}"}).json()["key"]
    return token, key


# -- pure helpers ------------------------------------------------------------

def test_estimate_tokens_never_zero_for_real_text():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 40) == 10


def test_split_system_pulls_system_out():
    system, rest = split_system([
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ])
    assert system == "be brief"
    assert rest == [{"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "hello"}]


def test_split_system_flattens_content_parts():
    system, rest = split_system([
        {"role": "user", "content": [{"type": "text", "text": "a"},
                                    {"type": "text", "text": "b"}]},
    ])
    assert rest == [{"role": "user", "content": "ab"}]


def test_resolve_route_prefers_a_profile_then_openrouter_then_default():
    assert resolve_route("claude", ["claude", "gpt"]) == ("claude", None)
    assert resolve_route("meta/llama", ["openrouter"]) == ("openrouter",
                                                        "meta/llama")
    assert resolve_route("gpt-4o", ["claude"]) == (None, "gpt-4o")


# -- the endpoint ------------------------------------------------------------

def test_a_plus_account_completes_through_the_proxy():
    with TestClient(_app()) as client:
        _token, key = _plus_key(client)
        r = client.post("/v1/chat/completions",
                        json={"model": "claude",
                            "messages": [{"role": "user", "content": "hi"}]},
                        headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["object"] == "chat.completion"
        assert body["choices"][0]["message"]["role"] == "assistant"
        assert body["usage"]["total_tokens"] == 15   # 10 + 5 from FakeProvider


def test_the_login_token_also_works_as_a_proxy_credential():
    with TestClient(_app()) as client:
        token, _key = _plus_key(client)
        r = client.post("/v1/chat/completions",
                        json={"messages": [{"role": "user", "content": "hi"}]},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text


def test_no_credentials_is_401():
    with TestClient(_app()) as client:
        r = client.post("/v1/chat/completions",
                        json={"messages": [{"role": "user", "content": "hi"}]})
        assert r.status_code == 401


def test_a_free_account_is_refused_with_403():
    with TestClient(_app()) as client:
        # An account with no licence is Free — no api_access entitlement.
        client.post("/admin/accounts",
                    json={"username": "free", "password": "pw-free-123"},
                    headers=ADMIN)
        token = client.post("/auth/login",
                            json={"username": "free", "password": "pw-free-123"}
                            ).json()["token"]
        key = client.post("/auth/api-keys", json={},
                        headers={"Authorization": f"Bearer {token}"}
                        ).json()["key"]
        r = client.post("/v1/chat/completions",
                        json={"messages": [{"role": "user", "content": "hi"}]},
                        headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 403
        assert "API access" in r.json()["detail"]


def test_the_daily_token_limit_returns_429_once_spent():
    # Plus allowance of 10 tokens; the first call spends 15 and crosses it.
    with TestClient(_app(proxy_plus_daily_tokens=10)) as client:
        _token, key = _plus_key(client)
        head = {"Authorization": f"Bearer {key}"}
        first = client.post("/v1/chat/completions",
                            json={"messages": [{"role": "user", "content": "hi"}]},
                            headers=head)
        assert first.status_code == 200
        second = client.post("/v1/chat/completions",
                            json={"messages": [{"role": "user", "content": "hi"}]},
                            headers=head)
        assert second.status_code == 429
        assert second.headers.get("Retry-After") == "3600"


def test_pro_is_never_metered_out():
    with TestClient(_app(proxy_pro_daily_tokens=0, owner_username="boss")) as client:
        client.post("/admin/accounts",
                    json={"username": "boss", "password": "secret-boss"},
                    headers=ADMIN)
        token = client.post("/auth/login",
                            json={"username": "boss", "password": "secret-boss"}
                            ).json()["token"]
        key = client.post("/auth/api-keys", json={},
                        headers={"Authorization": f"Bearer {token}"}
                        ).json()["key"]
        head = {"Authorization": f"Bearer {key}"}
        for _ in range(4):
            r = client.post("/v1/chat/completions",
                            json={"messages": [{"role": "user", "content": "hi"}]},
                            headers=head)
            assert r.status_code == 200


def test_revoking_a_key_stops_the_proxy_immediately():
    with TestClient(_app()) as client:
        token, key = _plus_key(client)
        head = {"Authorization": f"Bearer {token}"}
        key_id = client.get("/auth/api-keys", headers=head).json()["keys"][0]["id"]
        assert client.delete(f"/auth/api-keys/{key_id}",
                            headers=head).status_code == 200
        r = client.post("/v1/chat/completions",
                        json={"messages": [{"role": "user", "content": "hi"}]},
                        headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 401


def test_an_empty_message_list_is_rejected():
    with TestClient(_app()) as client:
        _token, key = _plus_key(client)
        r = client.post("/v1/chat/completions",
                        json={"messages": [{"role": "system", "content": "x"}]},
                        headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 400


def test_models_lists_the_operators_profiles():
    with TestClient(_app()) as client:
        _token, key = _plus_key(client)
        r = client.get("/v1/models", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200
        assert "claude" in [m["id"] for m in r.json()["data"]]


def test_streaming_returns_openai_style_sse():
    with TestClient(_app()) as client:
        _token, key = _plus_key(client)
        r = client.post("/v1/chat/completions",
                        json={"stream": True,
                            "messages": [{"role": "user", "content": "hi"}]},
                        headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        lines = [ln for ln in r.text.splitlines() if ln.startswith("data: ")]
        assert lines[-1] == "data: [DONE]"
        # Every non-terminal frame is a chat.completion.chunk.
        first = json.loads(lines[0][len("data: "):])
        assert first["object"] == "chat.completion.chunk"


def test_the_proxy_does_not_exist_when_disabled():
    with TestClient(_app(proxy_enabled=False)) as client:
        _token, key = _plus_key(client)
        r = client.post("/v1/chat/completions",
                        json={"messages": [{"role": "user", "content": "hi"}]},
                        headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 404


def test_root_advertises_the_proxy():
    with TestClient(_app()) as client:
        assert client.get("/").json()["proxy"] is True
    with TestClient(_app(proxy_enabled=False)) as client:
        assert client.get("/").json()["proxy"] is False
