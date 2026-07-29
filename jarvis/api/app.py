"""
FastAPI application factory.

Endpoints:
    GET  /                — service info (open).
    GET  /health          — diagnostics (open).
    POST /chat            — send a message, get a reply (auth).
    WS   /ws/{session}    — stream a reply chunk by chunk (auth via ?key=).
    POST /auth/login …    — per-user accounts (only when AUTH_ENABLED).
    POST /admin/…         — operator endpoints (only when AUTH_ENABLED).

Authentication resolves a *principal* for each request:

* A per-user login token (``AUTH_ENABLED``) — the strongest, and it namespaces
  the caller's sessions/memory to their account.
* The shared ``API_KEY`` — a single bearer/``X-API-Key`` secret.

If neither accounts nor a shared key are configured the API is **open** — for
local development only.
"""

from contextlib import asynccontextmanager

from pydantic import BaseModel

from jarvis import __version__
from jarvis.api.auth import install_auth_routes, resolve_principal
from jarvis.config.settings import Settings, get_settings
from jarvis.core.engine import JarvisEngine
from jarvis.licensing import LicenseService
from jarvis.models.response import Request
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class ChatIn(BaseModel):
    message: str
    session_id: str = "default"
    #: Optional model profile to pin this turn to (see GET /models).
    model: str | None = None
    #: Optional reply language hint (e.g. "en", "ru", "uz").
    language: str | None = None


class ChatOut(BaseModel):
    reply: str
    session_id: str


class SpeakIn(BaseModel):
    """A text-to-speech request."""

    text: str
    #: Optional language hint (e.g. "ru") passed to the TTS backend.
    language: str | None = None


#: Sentinel for the lazily-built voice service ("not resolved yet").
_UNSET: object = object()


def create_app(engine: JarvisEngine | None = None,
            settings: Settings | None = None):
    """Build the FastAPI application over an engine."""
    try:
        from fastapi import (
            Depends,
            FastAPI,
            File,
            Header,
            HTTPException,
            UploadFile,
            WebSocket,
            WebSocketDisconnect,
        )
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "The API needs 'fastapi' and 'uvicorn'. Install with: "
            "pip install fastapi 'uvicorn[standard]'"
        ) from exc

    settings = settings or get_settings()
    engine = engine or JarvisEngine(settings)
    #: Built on first voice request so the API starts fast without audio deps.
    _voice_svc: object = _UNSET

    service: LicenseService | None = None
    if settings.auth_enabled:
        service = LicenseService(
            settings.auth_db_path, token_ttl_hours=settings.auth_token_ttl_hours
        )

    @asynccontextmanager
    async def lifespan(_app):
        await engine.start()
        try:
            yield
        finally:
            await engine.shutdown()
            if service is not None:
                service.close()

    app = FastAPI(title=f"{settings.assistant_name} API", version=__version__,
                  lifespan=lifespan)

    # Every interface is a page on some other origin — the desktop app's own
    # window, a locally run dashboard — so without this the browser refuses the
    # request and the UI shows nothing at all.
    origins = [o.strip() for o in settings.api_cors_origins.split(",")
               if o.strip()]
    if origins:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials="*" not in origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _principal(provided: str | None) -> str | None:
        return resolve_principal(provided, settings, service)

    def _scoped(principal: str, session_id: str) -> str:
        """Namespace a session by its owner so users never share memory."""
        return f"{principal}::{session_id}"

    def _apply_prefs(scoped: str, body: ChatIn) -> None:
        """Apply per-request model / language onto the session before a turn."""
        if not body.model and not body.language:
            return
        scratch = engine.session(scoped).scratch
        if body.model:
            scratch["model_profile"] = body.model
        if body.language:
            scratch["language"] = body.language

    async def require_principal(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> str:
        provided = None
        if authorization and authorization.startswith("Bearer "):
            provided = authorization[len("Bearer "):]
        provided = provided or x_api_key
        principal = _principal(provided)
        if principal is None:
            raise HTTPException(status_code=401, detail="Invalid or missing credentials.")
        return principal

    # -- routes -------------------------------------------------------------

    @app.get("/")
    async def root() -> dict:
        return {
            "name": settings.assistant_name,
            "version": __version__,
            "status": "online",
            "auth": "accounts" if service is not None else "shared-key",
        }

    @app.get("/health")
    async def health() -> dict:
        from jarvis.core.diagnostics import all_ok, diagnose
        checks = diagnose(engine)
        return {
            "ok": all_ok(checks),
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail}
                    for c in checks],
        }

    @app.get("/models")
    async def models(_: str = Depends(require_principal)) -> dict:
        return {"models": engine.llm.list_profiles()}

    # -- voice (real STT / TTS over the same engine's voice service) --------

    def _voice():
        """Lazily build the shared VoiceService, or None when voice is off."""
        nonlocal _voice_svc
        if _voice_svc is _UNSET:
            if not settings.voice_enabled:
                _voice_svc = None
            else:
                try:
                    from jarvis.voice import VoiceService
                    _voice_svc = VoiceService.from_settings(settings)
                except Exception as exc:  # noqa: BLE001 - optional deps
                    logger.warning("Voice service unavailable: %s", exc)
                    _voice_svc = None
        return _voice_svc

    @app.get("/voice/status")
    async def voice_status(_: str = Depends(require_principal)) -> dict:
        """Whether speech-to-text / text-to-speech are actually usable."""
        svc = _voice()
        return {
            "enabled": svc is not None,
            "stt": bool(svc and svc.stt_available()),
            "tts": bool(svc and svc.tts_available()),
        }

    # File uploads need python-multipart; FastAPI raises at *registration* time
    # if it is missing, so only mount the upload route when it is importable.
    try:
        import python_multipart  # noqa: F401
        _multipart = True
    except ImportError:  # pragma: no cover - older releases use the old name
        try:
            import multipart  # noqa: F401
            _multipart = True
        except ImportError:
            _multipart = False

    if _multipart:
        @app.post("/voice/stt")
        async def voice_stt(file: UploadFile = File(...),  # noqa: B008 - FastAPI dep
                            _: str = Depends(require_principal)) -> dict:
            """Transcribe uploaded audio to text."""
            svc = _voice()
            if svc is None or not svc.stt_available():
                raise HTTPException(503, "Speech-to-text is not configured.")
            audio = await file.read()
            if not audio:
                raise HTTPException(400, "Empty audio upload.")
            result = await svc.transcribe(audio, file.filename or "voice.webm")
            return {"text": result.text,
                    "language": getattr(result, "language", "")}
    else:  # pragma: no cover - exercised only without python-multipart
        @app.post("/voice/stt")
        async def voice_stt_unavailable(_: str = Depends(require_principal)) -> dict:
            raise HTTPException(
                503, "Audio upload needs python-multipart: pip install python-multipart")

    @app.post("/voice/tts")
    async def voice_tts(body: SpeakIn,
                        _: str = Depends(require_principal)):
        """Synthesise speech for ``text`` and return the audio bytes."""
        from fastapi.responses import Response

        svc = _voice()
        if svc is None or not svc.tts_available():
            raise HTTPException(503, "Text-to-speech is not configured.")
        if not body.text.strip():
            raise HTTPException(400, "Nothing to speak.")
        audio = await svc.synthesize(body.text, body.language)
        ext = svc.tts_ext()
        media = {"ogg": "audio/ogg", "mp3": "audio/mpeg",
                "wav": "audio/wav"}.get(ext, "application/octet-stream")
        return Response(content=audio, media_type=media)

    @app.post("/chat", response_model=ChatOut)
    async def chat(body: ChatIn,
                principal: str = Depends(require_principal)) -> ChatOut:
        scoped = _scoped(principal, body.session_id)
        _apply_prefs(scoped, body)
        reply = await engine.ask(body.message, session_id=scoped)
        return ChatOut(reply=reply, session_id=body.session_id)

    @app.post("/chat/stream")
    async def chat_stream(body: ChatIn,
                        principal: str = Depends(require_principal)):
        """Stream the reply as plain-text chunks (chunked transfer encoding).

        Easy to consume from any HTTP client — no WebSocket needed: read the
        body incrementally until EOF.
        """
        from fastapi.responses import StreamingResponse

        scoped = _scoped(principal, body.session_id)
        _apply_prefs(scoped, body)

        async def _generate():
            async for chunk in engine.stream(
                Request(text=body.message, session_id=scoped)
            ):
                yield chunk

        return StreamingResponse(_generate(), media_type="text/plain; charset=utf-8")

    @app.websocket("/ws/{session_id}")
    async def ws(websocket: WebSocket, session_id: str) -> None:
        principal = _principal(websocket.query_params.get("key"))
        if principal is None:
            await websocket.close(code=1008)  # policy violation
            return
        await websocket.accept()
        scoped = _scoped(principal, session_id)
        try:
            while True:
                text = await websocket.receive_text()
                async for chunk in engine.stream(
                    Request(text=text, session_id=scoped)
                ):
                    await websocket.send_text(chunk)
                await websocket.send_json({"event": "done"})
        except WebSocketDisconnect:
            return

    # -- dashboard (Command Deck web UI) -----------------------------------

    import time as _time
    from pathlib import Path as _Path

    _STARTED = _time.time()
    _STATIC = _Path(__file__).parent / "static"

    @app.get("/app")
    async def dashboard_page():
        from fastapi.responses import FileResponse, JSONResponse
        page = _STATIC / "dashboard.html"
        if not page.is_file():
            return JSONResponse({"error": "dashboard not built"}, status_code=404)
        return FileResponse(str(page))

    def _system_stats() -> dict:
        import platform
        cpu = ram = None
        try:
            import psutil
            cpu = int(psutil.cpu_percent(interval=0.0))
            ram = int(psutil.virtual_memory().percent)
        except Exception:  # noqa: BLE001 - psutil optional; report null, not fake
            cpu, ram = None, None
        secs = int(_time.time() - _STARTED)
        uptime = f"{secs // 3600:02d}:{secs % 3600 // 60:02d}:{secs % 60:02d}"
        return {"cpu": cpu, "ram": ram, "uptime": uptime,
                "tools": len(engine.skills.tool_specs()),
                "session": len(engine.sessions),
                "python": platform.python_version()}

    _weather_cache: dict = {"at": 0.0, "data": None}

    async def _weather() -> dict:
        """Live weather for settings.weather_city, cached for 10 minutes."""
        city = settings.weather_city.strip()
        if not city or engine.integrations is None:
            return {"temp": "—", "loc": settings.user_name or "Local",
                    "cond": "telemetry", "glyph": "🛰"}
        if _time.time() - _weather_cache["at"] < 600 and _weather_cache["data"]:
            return _weather_cache["data"]
        try:
            wx = engine.integrations.get("weather")
            data = await wx.current(city) if wx is not None else None
        except Exception:  # noqa: BLE001 - weather must never break the dashboard
            data = None
        if not data:
            data = {"temp": "—", "loc": city, "cond": "—", "glyph": "🛰"}
        _weather_cache.update(at=_time.time(), data=data)
        return data

    @app.get("/dashboard/sessions")
    async def dashboard_sessions(_: str = Depends(require_principal)) -> dict:
        """Recent conversations (real history) for the chat sidebar."""
        import asyncio as _a
        mem = getattr(engine, "memory", None)
        if mem is None or getattr(mem, "conversations", None) is None:
            return {"sessions": []}
        rows = await _a.to_thread(mem.conversations.recent, 20)
        return {"sessions": rows}

    def _broker():
        """The engine's confirmation broker, when it has one."""
        return getattr(engine.security, "confirmer", None)

    async def _state_payload() -> dict:
        from jarvis.core.capabilities import CapabilityManager
        cap_state = {"enabled": "on", "restricted": "res", "disabled": "off"}
        caps = [[c.label, cap_state.get(c.state.value, "off")]
                for c in CapabilityManager(settings).all()]
        mcp = []
        if getattr(engine, "mcp", None) is not None:
            mcp = [{"name": s.name, "up": s.connected, "tools": s.tool_count}
                for s in engine.mcp.statuses()]
        active_model = {
            "openrouter": settings.openrouter_model,
            "local": settings.local_llm_model,
        }.get(settings.llm_provider, settings.llm_model)
        return {
            **_system_stats(),
            "name": settings.assistant_name,
            "capabilities": caps,
            "mcp": mcp,
            "ai": {"provider": settings.llm_provider, "model": active_model,
                "profiles": engine.llm.list_profiles(),
                "router": settings.ai_router_enabled,
                "search": settings.search_provider if settings.search_enabled else "off"},
            "voice": {"stt": bool(_voice() and _voice().stt_available()),
                    "tts": bool(_voice() and _voice().tts_available())},
            "security": {"file_write": settings.allow_file_write,
                        "shell": settings.allow_shell,
                        "desktop": settings.allow_desktop_control,
                        "redact": settings.memory_redact_secrets,
                        # What the running engine actually enforces, per
                        # capability: off / ask / on.
                        "modes": engine.security.modes()},
            # Questions the assistant is waiting on right now. Carried in the
            # state payload so the interface learns about them through the
            # channel it already listens to.
            "confirmations": _broker().pending() if _broker() else [],
            "weather": await _weather(),
        }

    @app.get("/dashboard/state")
    async def dashboard_state(_: str = Depends(require_principal)) -> dict:
        return await _state_payload()

    @app.websocket("/dashboard/ws")
    async def dashboard_ws(websocket: WebSocket) -> None:
        """Push live dashboard state to the client every few seconds."""
        import asyncio as _a
        principal = _principal(websocket.query_params.get("key"))
        if principal is None:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(await _state_payload())
                # A question the assistant is blocked on must reach the screen
                # quickly; the rest of the state can wait five seconds.
                broker = _broker()
                waiting = bool(broker and broker.pending())
                await _a.sleep(0.7 if waiting else 5)
        except WebSocketDisconnect:
            return
        except Exception:  # noqa: BLE001 - client gone / send failed
            return

    @app.get("/dashboard/tasks")
    async def dashboard_tasks(_: str = Depends(require_principal)) -> dict:
        """Scheduled automations + reminders (read from the shared store)."""
        import asyncio as _a

        from jarvis.interfaces.automations import AutomationStore
        from jarvis.interfaces.reminders import ReminderStore

        def _read() -> dict:
            autos, rems = [], []
            a_store = AutomationStore(settings.memory_db_path)
            r_store = ReminderStore(settings.memory_db_path)
            try:
                rows = a_store._conn.execute(  # noqa: SLF001 - read-only view
                    "SELECT id, prompt, kind, next_ts FROM automations "
                    "WHERE enabled = 1 ORDER BY next_ts LIMIT 50").fetchall()
                autos = [{"id": r["id"], "prompt": r["prompt"], "kind": r["kind"],
                        "next_ts": r["next_ts"]} for r in rows]
                rrows = r_store._conn.execute(  # noqa: SLF001
                    "SELECT id, text, due_ts FROM reminders WHERE fired = 0 "
                    "ORDER BY due_ts LIMIT 50").fetchall()
                rems = [{"id": r["id"], "text": r["text"], "due_ts": r["due_ts"]}
                        for r in rrows]
            finally:
                a_store.close()
                r_store.close()
            return {"automations": autos, "reminders": rems}

        return await _a.to_thread(_read)

    @app.get("/dashboard/models")
    async def dashboard_models(_: str = Depends(require_principal)) -> dict:
        from jarvis.interfaces import model_registry as mr
        models = [{
            "slug": m.slug, "name": m.name,
            "provider": mr.PROVIDERS.get(m.provider, m.provider),
            "emoji": m.emoji, "rating": round(m.rating / 20, 1),
            "free": m.free, "popular": m.popular,
            "categories": list(m.categories), "cost": m.cost_label,
        } for m in mr.all_models()]
        cats = [{"id": cid, "label": f"{emoji} {label}"}
                for cid, (emoji, label) in mr.CATEGORIES.items()]
        provs = [{"name": name, "count": count}
                for _pid, name, count in mr.providers_with_models()]
        return {"models": models, "categories": cats, "providers": provs}

    @app.get("/dashboard/update")
    async def dashboard_update(_: str = Depends(require_principal)) -> dict:
        """Check for a newer release and whether auto-update is allowed here."""
        import asyncio as _asyncio

        from jarvis import __version__
        from jarvis.core.updater import UpdateInfo, check_github
        if settings.update_channel == "off":
            info = UpdateInfo(current=__version__, latest=__version__,
                            available=False, channel="off")
        else:
            info = await _asyncio.to_thread(
                check_github, __version__, repo=settings.update_repo,
                include_prerelease=(settings.update_channel == "early"))
        # Self-hosted owner (no accounts) always may auto-update; a hosted,
        # multi-user deployment gates it behind an active subscription.
        auto_allowed = service is None
        return {**info.as_dict(),
                "channel_mode": settings.update_channel,
                "telegram_channel": settings.update_telegram_channel,
                "auto_allowed": auto_allowed}

    class _TgLoginIn(BaseModel):
        code: str

    @app.post("/auth/telegram")
    async def auth_telegram(body: _TgLoginIn) -> dict:
        """Exchange a bot-issued login code for an auth token (Telegram login)."""
        if service is None:
            raise HTTPException(status_code=400,
                                detail="Accounts are not enabled on this server.")
        result = service.redeem_telegram_login(body.code)
        if result is None:
            raise HTTPException(status_code=401,
                                detail="Invalid or expired code.")
        token, username = result
        return {"token": token, "username": username}

    class _McpIn(BaseModel):
        spec: str

    @app.post("/dashboard/mcp")
    async def dashboard_add_mcp(body: _McpIn,
                            _: str = Depends(require_principal)) -> dict:
        """Connect an MCP server at runtime and mount its tools."""
        from jarvis.mcp.base import MCPServerConfig
        from jarvis.mcp.manager import MCPManager
        spec = body.spec.strip()
        if spec.startswith("http"):
            cfg = MCPServerConfig(name=spec.split("//")[-1][:20],
                                transport="sse", url=spec)
        else:
            parts = spec.split()
            cfg = MCPServerConfig(name=parts[0], command=parts[0],
                                args=parts[1:])
        mgr = MCPManager([cfg])
        try:
            skills = await mgr.start()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502,
                                detail=f"Could not connect: {exc}") from exc
        for skill in skills:
            try:
                engine.skills.register(skill)
            except Exception:  # noqa: BLE001 - ignore duplicates
                pass
        return {"connected": True, "server": cfg.name, "tools": len(skills)}

    # -- who is signed in, and what their plan includes ----------------------

    @app.get("/dashboard/plan")
    async def dashboard_plan(
            authorization: str | None = Header(default=None),
            x_api_key: str | None = Header(default=None),
            _: str = Depends(require_principal)) -> dict:
        """The signed-in person's tier, limits and capabilities.

        The interface asks this to decide what to show. Without accounts (a
        private single-user server, or the owner's own machine) there is nobody
        to bill, so the caller is the operator and gets everything.
        """
        from jarvis.api.auth import profile_for
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer "):]
        token = token or x_api_key
        account = service.validate_token(token) if (service and token) else None
        if account is None and settings.auth_enabled:
            raise HTTPException(status_code=401, detail="Sign in first.")
        usage = None
        try:
            from jarvis.interfaces.usage import UsageStore
            usage = UsageStore(settings.memory_db_path)
        except Exception:  # noqa: BLE001 - usage is a nicety, not a gate
            usage = None
        try:
            return profile_for(account, settings, service, usage=usage,
                            owner=None if account is not None else True)
        finally:
            if usage is not None:
                usage.close()

    # -- permission questions ------------------------------------------------

    class _ConfirmIn(BaseModel):
        id: str
        allow: bool

    @app.get("/dashboard/confirmations")
    async def dashboard_confirmations(
            _: str = Depends(require_principal)) -> dict:
        """Anything the assistant is currently waiting on the user for."""
        broker = _broker()
        return {"pending": broker.pending() if broker else []}

    @app.post("/dashboard/confirm")
    async def dashboard_confirm(body: _ConfirmIn,
                                _: str = Depends(require_principal)) -> dict:
        """Answer one permission question."""
        broker = _broker()
        if broker is None:
            raise HTTPException(status_code=503,
                                detail="This engine does not ask for "
                                        "confirmation.")
        answered = broker.resolve(body.id, body.allow)
        if not answered:
            # Already answered, or it timed out while the user was deciding.
            raise HTTPException(status_code=404,
                                detail="That request is no longer waiting.")
        return {"ok": True, "id": body.id, "allowed": body.allow}

    # -- memory --------------------------------------------------------------

    def _memory():
        return getattr(engine, "memory", None)

    def _memory_or_503():
        memory = _memory()
        if memory is None:
            raise HTTPException(status_code=503,
                                detail="Memory is switched off for this "
                                        "assistant.")
        return memory

    @app.get("/dashboard/memory")
    async def dashboard_memory(limit: int = 100, offset: int = 0,
                            session: str = "",
                            _: str = Depends(require_principal)) -> dict:
        """What the assistant remembers, newest first."""
        memory = _memory_or_503()
        records = await memory.browse(session_id=session or None,
                                    limit=limit, offset=offset)
        return {
            "can_browse": memory.can_browse(),
            "stats": memory.stats(),
            "items": [{"id": r.record_id, "content": r.content,
                    "kind": r.kind, "session": r.session_id,
                    "timestamp": r.timestamp.isoformat()} for r in records],
        }

    @app.get("/dashboard/memory/search")
    async def dashboard_memory_search(q: str, limit: int = 20,
                                    _: str = Depends(require_principal)) -> dict:
        """Search memories the way the assistant itself recalls them."""
        memory = _memory_or_503()
        if not q.strip():
            return {"items": []}
        records = await memory.recall(q, session_id=None, limit=limit)
        return {"items": [{"id": r.record_id, "content": r.content,
                        "kind": r.kind, "session": r.session_id,
                        "score": round(r.score, 3),
                        "timestamp": r.timestamp.isoformat()}
                        for r in records]}

    @app.delete("/dashboard/memory/{record_id}")
    async def dashboard_memory_delete(record_id: int,
                                    _: str = Depends(require_principal)) -> dict:
        """Forget one specific thing."""
        memory = _memory_or_503()
        removed = await memory.delete_memory(record_id)
        if not removed:
            raise HTTPException(status_code=404, detail="No such memory.")
        return {"ok": True, "id": record_id}

    class _ForgetIn(BaseModel):
        session: str | None = None
        everything: bool = False

    @app.post("/dashboard/memory/forget")
    async def dashboard_memory_forget(body: _ForgetIn,
                                    _: str = Depends(require_principal)) -> dict:
        """Clear a session's memory, or all of it."""
        memory = _memory_or_503()
        await memory.forget(None if body.everything else (body.session or "default"))
        return {"ok": True, "stats": memory.stats()}

    # -- web search ----------------------------------------------------------

    def _search():
        return getattr(engine, "search", None)

    def _search_or_503():
        search = _search()
        if search is None:
            raise HTTPException(status_code=503,
                                detail="Web search is switched off for this "
                                        "assistant.")
        return search

    @app.get("/dashboard/search/providers")
    async def dashboard_search_providers(
            _: str = Depends(require_principal)) -> dict:
        """Every search backend, and whether it is actually usable."""
        search = _search()
        if search is None:
            return {"enabled": False, "active": None, "preferred":
                    settings.search_provider, "providers": []}
        return {
            "enabled": settings.search_enabled,
            "active": search.active(),
            "preferred": settings.search_provider,
            "providers": [{"name": s.name, "label": s.label, "kind": s.kind,
                        "available": s.available,
                        "requires_key": s.requires_key,
                        "is_default": s.is_default}
                        for s in search.statuses()],
        }

    class _SearchIn(BaseModel):
        query: str
        provider: str | None = None
        limit: int = 5

    @app.post("/dashboard/search/test")
    async def dashboard_search_test(body: _SearchIn,
                                    _: str = Depends(require_principal)) -> dict:
        """Run a real search, so a key can be proven rather than assumed."""
        search = _search_or_503()
        query = body.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Enter something to "
                                                        "search for.")
        try:
            results = await search.search(query, provider=body.provider,
                                        limit=max(1, min(body.limit, 10)))
        except Exception as exc:  # noqa: BLE001 - the page shows the reason
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"provider": body.provider or search.active(),
                "results": [{"title": r.title, "url": r.url,
                            "snippet": r.snippet} for r in results]}

    if service is not None:
        install_auth_routes(app, settings, service)
        if settings.billing_enabled and settings.billing_webhook_secret:
            from jarvis.api.billing_routes import install_billing_routes
            install_billing_routes(app, settings, service)

    app.state.engine = engine
    app.state.license_service = service
    return app
