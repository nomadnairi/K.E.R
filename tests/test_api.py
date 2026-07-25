"""Tests for the HTTP/WebSocket API (FastAPI TestClient, fake engine)."""

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


def _app(api_key: str = ""):
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False, rate_limit_enabled=False,
        api_key=api_key,
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    return create_app(engine=engine, settings=settings)


def test_root_and_health():
    with TestClient(_app()) as client:
        assert client.get("/").json()["name"] == "KER"
        health = client.get("/health").json()
        assert "ok" in health and isinstance(health["checks"], list)


def test_dashboard_page_served():
    with TestClient(_app()) as client:
        r = client.get("/app")
        assert r.status_code == 200
        assert "KER" in r.text and "reactor" in r.text


def test_dashboard_state_shape():
    with TestClient(_app()) as client:
        s = client.get("/dashboard/state").json()
        assert "capabilities" in s and "mcp" in s
        assert "cpu" in s and "uptime" in s and "tools" in s
        assert isinstance(s["capabilities"], list)


def test_dashboard_state_requires_key_when_set():
    with TestClient(_app(api_key="secret")) as client:
        assert client.get("/dashboard/state").status_code == 401
        ok = client.get("/dashboard/state", headers={"X-API-Key": "secret"})
        assert ok.status_code == 200


def test_dashboard_state_has_ai_and_security():
    with TestClient(_app()) as client:
        s = client.get("/dashboard/state").json()
        assert "ai" in s and "provider" in s["ai"] and "model" in s["ai"]
        assert "security" in s and "shell" in s["security"]
        # Dangerous caps default off.
        assert s["security"]["shell"] is False


def test_dashboard_sessions_shape():
    with TestClient(_app()) as client:
        s = client.get("/dashboard/sessions").json()
        assert "sessions" in s and isinstance(s["sessions"], list)


def test_dashboard_tasks_shape():
    with TestClient(_app()) as client:
        t = client.get("/dashboard/tasks").json()
        assert "automations" in t and "reminders" in t
        assert isinstance(t["automations"], list)


def test_dashboard_ws_pushes_state():
    with TestClient(_app()) as client:
        with client.websocket_connect("/dashboard/ws") as ws:
            state = ws.receive_json()
            assert "capabilities" in state and "cpu" in state


def test_dashboard_ws_requires_key_when_set():
    from starlette.websockets import WebSocketDisconnect as _WSD
    with TestClient(_app(api_key="secret")) as client:
        with pytest.raises(_WSD):
            with client.websocket_connect("/dashboard/ws") as ws:
                ws.receive_json()


def test_dashboard_update_check():
    # update_channel defaults to "early"; check should return a shape even
    # though the network call is stubbed to fail offline (soft -> not available).
    with TestClient(_app()) as client:
        u = client.get("/dashboard/update").json()
        assert "current" in u and "available" in u and "auto_allowed" in u
        # Self-hosted (no accounts) -> auto-update allowed.
        assert u["auto_allowed"] is True


def test_dashboard_update_off_channel():
    settings = Settings(anthropic_api_key="k", log_file="", memory_enabled=False,
                        integrations_enabled=False, goals_enabled=False,
                        rate_limit_enabled=False, update_channel="off")
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    with TestClient(create_app(engine=engine, settings=settings)) as client:
        u = client.get("/dashboard/update").json()
        assert u["available"] is False and u["channel"] == "off"


def test_dashboard_models_from_registry():
    with TestClient(_app()) as client:
        d = client.get("/dashboard/models").json()
        assert d["models"] and "categories" in d and "providers" in d
        m0 = d["models"][0]
        for k in ("slug", "name", "provider", "rating", "free", "categories"):
            assert k in m0
        # Ratings are normalised to a 0-5 scale.
        assert 0 <= m0["rating"] <= 5


def test_chat_open_when_no_key():
    with TestClient(_app()) as client:
        resp = client.post("/chat", json={"message": "hello"})
        assert resp.status_code == 200
        assert resp.json()["reply"] == "Certainly, Sir."


def test_chat_requires_key_when_set():
    with TestClient(_app(api_key="secret")) as client:
        assert client.post("/chat", json={"message": "hi"}).status_code == 401
        ok = client.post("/chat", json={"message": "hi"},
                        headers={"Authorization": "Bearer secret"})
        assert ok.status_code == 200


def test_chat_accepts_x_api_key_header():
    with TestClient(_app(api_key="secret")) as client:
        resp = client.post("/chat", json={"message": "hi"},
                        headers={"X-API-Key": "secret"})
        assert resp.status_code == 200


def test_websocket_streams():
    import json

    with TestClient(_app()) as client:
        with client.websocket_connect("/ws/s1") as ws:
            ws.send_text("stream please")
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


def test_websocket_rejects_bad_key():
    from starlette.websockets import WebSocketDisconnect

    with TestClient(_app(api_key="secret")) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/s1") as ws:
                ws.receive_text()


# -- voice endpoints ---------------------------------------------------------


class _FakeSTT:
    async def transcribe(self, audio: bytes, filename: str = "v.ogg"):
        from jarvis.voice.base import Transcription
        return Transcription(text=f"heard {len(audio)} bytes", language="ru")


class _FakeVoice:
    """Minimal stand-in with the same contract as the real VoiceService."""

    def __init__(self, stt: bool = True, tts: bool = True) -> None:
        self._stt, self._tts = stt, tts

    def stt_available(self) -> bool:
        return self._stt

    def tts_available(self) -> bool:
        return self._tts

    async def transcribe(self, audio: bytes, filename: str = "v.ogg"):
        from jarvis.voice.base import Transcription
        return Transcription(text=f"heard {len(audio)} bytes", language="ru")

    async def synthesize(self, text: str, language=None) -> bytes:
        return b"OggS-fake-audio"

    def tts_ext(self) -> str:
        return "ogg"


def _voice_app(monkeypatch, voice=None):
    """Build an app whose voice service is the injected fake."""
    from jarvis.voice import VoiceService
    monkeypatch.setattr(VoiceService, "from_settings",
                        classmethod(lambda cls, s: voice), raising=True)
    settings = Settings(anthropic_api_key="k", log_file="", memory_enabled=False,
                        integrations_enabled=False, goals_enabled=False,
                        rate_limit_enabled=False, api_key="", voice_enabled=True)
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    return create_app(engine=engine, settings=settings)


def test_voice_status_reports_real_availability(monkeypatch):
    with TestClient(_voice_app(monkeypatch, _FakeVoice(stt=True, tts=False))) as c:
        body = c.get("/voice/status").json()
        assert body == {"enabled": True, "stt": True, "tts": False}


def test_voice_stt_transcribes_upload(monkeypatch):
    pytest.importorskip("multipart")
    with TestClient(_voice_app(monkeypatch, _FakeVoice())) as c:
        r = c.post("/voice/stt",
                   files={"file": ("v.webm", b"1234567890", "audio/webm")})
        assert r.status_code == 200
        assert r.json() == {"text": "heard 10 bytes", "language": "ru"}


def test_voice_stt_rejects_empty_upload(monkeypatch):
    pytest.importorskip("multipart")
    with TestClient(_voice_app(monkeypatch, _FakeVoice())) as c:
        r = c.post("/voice/stt", files={"file": ("v.webm", b"", "audio/webm")})
        assert r.status_code == 400


def test_voice_tts_returns_audio(monkeypatch):
    with TestClient(_voice_app(monkeypatch, _FakeVoice())) as c:
        r = c.post("/voice/tts", json={"text": "привет", "language": "ru"})
        assert r.status_code == 200
        assert r.content == b"OggS-fake-audio"
        assert r.headers["content-type"].startswith("audio/ogg")


def test_voice_endpoints_503_when_unconfigured(monkeypatch):
    """No usable backend must fail loudly, never silently fake a result."""
    with TestClient(_voice_app(monkeypatch, _FakeVoice(stt=False, tts=False))) as c:
        assert c.post("/voice/tts", json={"text": "hi"}).status_code == 503
        if pytest.importorskip("multipart", reason="needs python-multipart"):
            assert c.post("/voice/stt",
                          files={"file": ("v.webm", b"x", "audio/webm")}
                          ).status_code == 503


def test_state_exposes_voice_and_real_python(monkeypatch):
    import platform
    with TestClient(_voice_app(monkeypatch, _FakeVoice())) as c:
        s = c.get("/dashboard/state").json()
        assert s["voice"] == {"stt": True, "tts": True}
        assert s["python"] == platform.python_version()   # real, not hardcoded
        assert "session" in s and isinstance(s["session"], int)


def test_the_interface_is_allowed_to_call_the_api():
    """A page always sits on another origin; without this it gets nothing.

    The desktop window and a locally run dashboard both call the API
    cross-origin, so a missing CORS header shows up as an interface full of
    dashes over a perfectly healthy engine.
    """
    with TestClient(_app()) as c:
        r = c.get("/health", headers={"Origin": "ker://deck"})
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "*"


def test_cors_can_be_narrowed_to_named_origins():
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=False,
        integrations_enabled=False, goals_enabled=False,
        rate_limit_enabled=False,
        api_cors_origins="https://deck.example",
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    with TestClient(create_app(engine=engine, settings=settings)) as c:
        allowed = c.get("/health", headers={"Origin": "https://deck.example"})
        assert allowed.headers.get("access-control-allow-origin") == \
            "https://deck.example"
        blocked = c.get("/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in blocked.headers
