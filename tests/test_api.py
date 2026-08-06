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
        # /health is a bare liveness probe now — no provider names, no
        # capability states, no security-audit findings. That detail moved
        # to /health/full, which only the owner can reach (see below).
        assert client.get("/health").json() == {"ok": True}


def test_health_full_is_open_only_when_the_whole_server_is_open():
    """With no shared key and no accounts, every caller *is* the owner —
    the same rule /dashboard/mcp already relies on for single-user/dev use.
    """
    with TestClient(_app()) as client:
        r = client.get("/health/full")
        assert r.status_code == 200
        body = r.json()
        assert "ok" in body and isinstance(body["checks"], list)
        assert any(c["name"] == "llm" for c in body["checks"])


def test_health_full_requires_the_shared_key_once_one_is_set():
    with TestClient(_app(api_key="secret-key")) as client:
        anon = client.get("/health/full")
        assert anon.status_code == 401

        owner = client.get("/health/full", headers={"X-API-Key": "secret-key"})
        assert owner.status_code == 200
        assert isinstance(owner.json()["checks"], list)


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


def _voice_app(monkeypatch, voice=None, **overrides):
    """Build an app whose voice service is the injected fake."""
    from jarvis.voice import VoiceService
    monkeypatch.setattr(VoiceService, "from_settings",
                        classmethod(lambda cls, s: voice), raising=True)
    settings = Settings(anthropic_api_key="k", log_file="", memory_enabled=False,
                        integrations_enabled=False, goals_enabled=False,
                        rate_limit_enabled=False, api_key="", voice_enabled=True,
                        **overrides)
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


# -- size limits enforced by the app itself, not just a reverse proxy --------
#
# Before this, `await file.read()` pulled the whole upload into one Python
# object regardless of size, and SpeakIn.text had no length check at all — a
# bare `python -m jarvis.api`, with no nginx in front, had no limit whatsoever.


class _ChunkedReader:
    """Hands out fixed-size chunks on demand, up to ``total`` bytes.

    Never actually holds ``total`` bytes at once — if the code under test
    called a bare, unbounded ``.read()`` instead of reading chunk by chunk,
    this would still return the right bytes (nothing here depends on the
    caller behaving), so what actually proves the capped behaviour is
    ``max_seen`` below, not this class needing to fail on misuse.
    """

    def __init__(self, total: int, chunk: int = 8) -> None:
        self._remaining = total
        self._chunk = chunk
        self.max_seen = 0
        self._served = 0

    async def read(self, size: int = -1) -> bytes:
        n = min(self._chunk, self._remaining)
        self._remaining -= n
        self._served += n
        self.max_seen = max(self.max_seen, self._served)
        return b"x" * n


def test_read_capped_stops_at_the_boundary_without_buffering_the_whole_stream():
    """Direct unit test of the reader FastAPI's voice_stt route uses — the
    part of this fix that actually matters: memory used is bounded by the
    cap plus one chunk, not by however much the client sends."""
    import asyncio

    from jarvis.api.app import _read_capped

    reader = _ChunkedReader(total=10_000_000, chunk=64)  # ~10 MB, 64 B at a time
    with pytest.raises(ValueError):
        asyncio.run(_read_capped(reader, max_bytes=1000))
    # Stopped soon after crossing 1000 bytes — nowhere near the 10 MB total.
    assert reader.max_seen < 1000 + 64


def test_read_capped_returns_everything_when_under_the_limit():
    import asyncio

    from jarvis.api.app import _read_capped

    reader = _ChunkedReader(total=500, chunk=64)
    result = asyncio.run(_read_capped(reader, max_bytes=1000))
    assert result == b"x" * 500


def test_read_capped_accepts_exactly_the_limit():
    import asyncio

    from jarvis.api.app import _read_capped

    reader = _ChunkedReader(total=1000, chunk=100)
    result = asyncio.run(_read_capped(reader, max_bytes=1000))
    assert len(result) == 1000


def test_oversized_voice_upload_is_rejected_with_413(monkeypatch):
    pytest.importorskip("multipart")
    app = _voice_app(monkeypatch, _FakeVoice(), voice_stt_max_bytes=100)
    with TestClient(app) as c:
        r = c.post("/voice/stt",
                   files={"file": ("v.webm", b"x" * 500, "audio/webm")})
        assert r.status_code == 413
        assert "MB" in r.json()["detail"]


def test_voice_upload_at_exactly_the_limit_is_accepted(monkeypatch):
    pytest.importorskip("multipart")
    # The cap applies to the file's own content, not the whole multipart body
    # (boundaries/headers add a little overhead) — use a large enough file
    # that this test's own encoding overhead can't be mistaken for the bug.
    size = 100_000
    app = _voice_app(monkeypatch, _FakeVoice(), voice_stt_max_bytes=size)
    with TestClient(app) as c:
        r = c.post("/voice/stt",
                   files={"file": ("v.webm", b"x" * size, "audio/webm")})
        assert r.status_code == 200
        assert r.json() == {"text": f"heard {size} bytes", "language": "ru"}


def test_oversized_tts_text_is_rejected_with_413(monkeypatch):
    app = _voice_app(monkeypatch, _FakeVoice(), voice_tts_max_chars=10)
    with TestClient(app) as c:
        r = c.post("/voice/tts", json={"text": "x" * 11})
        assert r.status_code == 413


def test_tts_text_at_exactly_the_limit_is_accepted(monkeypatch):
    app = _voice_app(monkeypatch, _FakeVoice(), voice_tts_max_chars=10)
    with TestClient(app) as c:
        r = c.post("/voice/tts", json={"text": "x" * 10})
        assert r.status_code == 200


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


# -- memory, search and permission questions over the API -------------------

def _memory_app(tmp_path):
    """An app with real memory behind it (hashing embedder, no network)."""
    settings = Settings(
        anthropic_api_key="k", log_file="", memory_enabled=True,
        memory_backend="sqlite", memory_db_path=str(tmp_path / "m.db"),
        embedding_backend="hashing",
        integrations_enabled=False, goals_enabled=False,
        rate_limit_enabled=False, api_key="",
    )
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    return engine, create_app(engine=engine, settings=settings)


def test_memory_can_be_listed_and_forgotten(tmp_path):
    import asyncio
    engine, app = _memory_app(tmp_path)
    asyncio.run(engine.memory.remember("default", "Меня зовут Сержод",
                                       kind="fact"))
    with TestClient(app) as c:
        listing = c.get("/dashboard/memory").json()
        assert listing["can_browse"] is True
        assert listing["stats"]["memories"] == 1
        item = listing["items"][0]
        assert item["content"] == "Меня зовут Сержод"

        assert c.delete(f"/dashboard/memory/{item['id']}").status_code == 200
        assert c.get("/dashboard/memory").json()["items"] == []
        # Forgetting the same thing twice is a 404, not a silent success.
        assert c.delete(f"/dashboard/memory/{item['id']}").status_code == 404


def test_memory_search_uses_real_recall(tmp_path):
    import asyncio
    engine, app = _memory_app(tmp_path)
    asyncio.run(engine.memory.remember("default", "Я живу в Ташкенте",
                                       kind="fact"))
    with TestClient(app) as c:
        # Russian must work at all — it used to return nothing whatsoever.
        # The default embedder is bag-of-words, so the query shares words with
        # the memory rather than being a synonym for it.
        found = c.get("/dashboard/memory/search",
                      params={"q": "где я живу"}).json()
        assert any("Ташкенте" in i["content"] for i in found["items"])
        assert c.get("/dashboard/memory/search",
                     params={"q": "  "}).json()["items"] == []


def test_forget_everything_clears_memory(tmp_path):
    import asyncio
    engine, app = _memory_app(tmp_path)
    asyncio.run(engine.memory.remember("default", "что-то", kind="fact"))
    with TestClient(app) as c:
        out = c.post("/dashboard/memory/forget", json={"everything": True})
        assert out.status_code == 200
        assert out.json()["stats"]["memories"] == 0


def test_memory_endpoints_say_so_when_memory_is_off():
    with TestClient(_app()) as c:      # the default app has memory disabled
        assert c.get("/dashboard/memory").status_code == 503


def test_search_providers_report_real_availability():
    with TestClient(_app()) as c:
        out = c.get("/dashboard/search/providers").json()
        names = {p["name"] for p in out["providers"]}
        assert "duckduckgo" in names
        keyless = next(p for p in out["providers"] if p["name"] == "duckduckgo")
        assert keyless["requires_key"] is False
        assert keyless["available"] is True
        # A provider with no key configured must not claim to be usable.
        keyed = [p for p in out["providers"] if p["requires_key"]]
        assert all(p["available"] is False for p in keyed)


def test_search_test_needs_something_to_search_for():
    with TestClient(_app()) as c:
        assert c.post("/dashboard/search/test",
                      json={"query": "   "}).status_code == 400


def test_pending_permission_questions_are_visible_and_answerable():
    """The interface must be able to see the question and answer it."""
    import threading
    import time

    from jarvis.security.policy import Capability
    settings = Settings(anthropic_api_key="k", log_file="", audit_log_path="",
                        memory_enabled=False, integrations_enabled=False,
                        goals_enabled=False, rate_limit_enabled=False,
                        allow_shell=True, confirm_shell=True)
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    app = create_app(engine=engine, settings=settings)
    broker = engine.security.confirmer
    answers: list[bool] = []
    threading.Thread(
        target=lambda: answers.append(
            broker.request(Capability.SHELL_EXEC, "echo hi")),
        daemon=True).start()
    while not broker.pending():
        time.sleep(0.01)

    with TestClient(app) as c:
        pending = c.get("/dashboard/confirmations").json()["pending"]
        assert pending and pending[0]["action"] == "echo hi"
        assert c.get("/dashboard/state").json()["confirmations"]
        ok = c.post("/dashboard/confirm",
                    json={"id": pending[0]["id"], "allow": True})
        assert ok.status_code == 200
        # Answering it again fails loudly rather than pretending.
        assert c.post("/dashboard/confirm",
                      json={"id": pending[0]["id"], "allow": True}
                      ).status_code == 404
    for _ in range(200):
        if answers:
            break
        time.sleep(0.01)
    assert answers == [True]


def test_state_reports_the_capability_modes():
    settings = Settings(anthropic_api_key="k", log_file="", audit_log_path="",
                        memory_enabled=False, integrations_enabled=False,
                        goals_enabled=False, rate_limit_enabled=False,
                        allow_file_write=True, confirm_file_write=True)
    engine = JarvisEngine(container=ServiceContainer(
        settings, llm_client=LLMClient(primary=FakeProvider())))
    with TestClient(create_app(engine=engine, settings=settings)) as c:
        modes = c.get("/dashboard/state").json()["security"]["modes"]
        assert modes["file_write"] == "ask"
        assert modes["shell_exec"] == "off"
