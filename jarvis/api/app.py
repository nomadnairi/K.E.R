"""
FastAPI application factory.

Endpoints:
    GET  /                — service info (open).
    GET  /health          — minimal liveness probe (open; used by Docker healthcheck).
    GET  /health/full     — full diagnostics (owner only).
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
from jarvis.api.auth import SHARED_PRINCIPAL, install_auth_routes, resolve_principal
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


#: Chunk size for the capped upload reader below.
_STT_CHUNK_BYTES = 65_536


async def _read_capped(reader, max_bytes: int, *,
                        chunk_size: int = _STT_CHUNK_BYTES) -> bytes:
    """Read from ``reader`` (anything with an async ``read(size)``, e.g. a
    FastAPI ``UploadFile``) in chunks, raising ``ValueError`` the moment the
    running total exceeds ``max_bytes``.

    Never a bare, unbounded ``read()`` — a client can claim any
    ``Content-Length`` header (or none at all, with chunked transfer
    encoding), so the only limit that actually holds is the one enforced
    while reading, not one assumed from a header a caller controls. Reading
    stops the instant the cap is crossed, so at most one chunk past the limit
    is ever held in memory — never the full size of an oversized upload.

    Free of any FastAPI import on purpose, so it needs no HTTP machinery to
    unit-test.
    """
    total = 0
    parts: list[bytes] = []
    while True:
        chunk = await reader.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"stream exceeds {max_bytes} bytes")
        parts.append(chunk)
    return b"".join(parts)


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
        from fastapi import Request as HttpRequest
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "The API needs 'fastapi' and 'uvicorn'. Install with: "
            "pip install fastapi 'uvicorn[standard]'"
        ) from exc

    settings = settings or get_settings()
    if engine is None:
        # The real, standalone API server: it has no desktop of its own, so
        # its DesktopController must never touch pyautogui/webbrowser
        # in-process — only relay to a connected device (see
        # _apply_device_relay / jarvis/desktop/device_registry.py). An
        # engine passed in explicitly (e.g. the desktop app's own embedded
        # local-mode engine, jarvis/desktop_app/engine_thread.py) already has
        # its real controller built and is left untouched here.
        from jarvis.core.container import ServiceContainer
        from jarvis.desktop.controller import DesktopController
        from jarvis.security.manager import SecurityManager
        from jarvis.security.policy import Capability, CapabilityMode
        server_desktop_controller = DesktopController(
            SecurityManager({Capability.DESKTOP_CONTROL: CapabilityMode.OFF}))
        container = ServiceContainer(settings,
                                    desktop_controller=server_desktop_controller)
        engine = JarvisEngine(container=container)
    #: Built on first voice request so the API starts fast without audio deps.
    _voice_svc: object = _UNSET

    service: LicenseService | None = None
    if settings.auth_enabled:
        service = LicenseService(
            settings.auth_db_path, token_ttl_hours=settings.auth_token_ttl_hours
        )
        # The operator gets in with an OWNER_USERNAME / OWNER_PASSWORD pair in
        # the env — the account is created (or its password realigned) here, so
        # there is no CLI step to becoming the owner.
        if settings.owner_username and settings.owner_password:
            try:
                service.bootstrap_owner(settings.owner_username,
                                        settings.owner_password)
            except Exception as exc:  # noqa: BLE001 - never block startup
                logger.warning("Owner bootstrap failed: %s", exc)

    @asynccontextmanager
    async def lifespan(_app):
        # Surface the deployment's security posture at startup so an operator
        # sees anything risky (unauthenticated API, encryption off, docs open).
        try:
            from jarvis.security.audit import audit_settings
            for finding in audit_settings(settings):
                if finding.severity in ("high", "medium"):
                    logger.warning("security: %s", finding)
        except Exception as exc:  # noqa: BLE001 - a check must not block startup
            logger.debug("security self-check skipped: %s", exc)
        await engine.start()
        try:
            yield
        finally:
            await engine.shutdown()
            if service is not None:
                service.close()

    # In production the OpenAPI docs/schema are turned off so the API surface is
    # not published to anonymous callers.
    _docs = settings.api_docs_enabled
    app = FastAPI(title=f"{settings.assistant_name} API", version=__version__,
                  lifespan=lifespan,
                  docs_url="/docs" if _docs else None,
                  redoc_url="/redoc" if _docs else None,
                  openapi_url="/openapi.json" if _docs else None)

    # Throttle brute-forceable endpoints (login, registration, the Telegram
    # code exchange) per client IP, before CORS so a rate-limited browser
    # caller still gets a readable 429 rather than a blocked cross-origin
    # response. One middleware for every such route, not a check bolted onto
    # each handler — see jarvis/api/rate_limit.py for why these routes and
    # not others.
    if settings.api_auth_rate_limit_enabled:
        from jarvis.api.rate_limit import SensitiveRouteRateLimit, default_limits
        app.add_middleware(
            SensitiveRouteRateLimit,
            limits=default_limits(settings.api_auth_rate_limit_capacity,
                                settings.api_auth_rate_limit_window_seconds),
            trust_proxy_headers=settings.api_trust_proxy_headers,
        )

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

    def _apply_device_relay(scoped: str, principal: str) -> None:
        """Stash a device-tool relay onto the session if one is connected.

        Consumed by the desktop-control skills (jarvis/desktop/tools.py) —
        this engine has no desktop of its own, so a relayed call is the only
        way "open a URL" etc. does anything meaningful. Absent by default;
        stashed only for the duration each connected device stays online.
        """
        from functools import partial
        scratch = engine.session(scoped).scratch
        if engine.container.devices.is_connected(principal):
            scratch["device_relay"] = partial(engine.container.devices.call, principal)
        else:
            scratch.pop("device_relay", None)

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

    def _is_owner_principal(principal: str) -> bool:
        """True for the operator: the shared API key, or the OWNER_USERNAME account.

        The shared key is a single secret only the operator holds — the same
        trust level as the owner account. Every other principal is someone
        else's per-user token, and being signed in does not make them the
        owner of this server.
        """
        if principal == SHARED_PRINCIPAL:
            return True
        if not settings.owner_username:
            return False
        return principal == f"user:{settings.owner_username.strip().lower()}"

    async def require_owner(
        principal: str = Depends(require_principal),
    ) -> str:
        """Like :func:`require_principal`, but only the server owner passes.

        For actions that affect the whole engine rather than the caller's own
        account or session — this one shared ``JarvisEngine`` serves every
        signed-in customer, so "any authenticated caller" is not a narrow
        enough gate for anything that changes what the engine can do.
        """
        if not _is_owner_principal(principal):
            raise HTTPException(
                status_code=403,
                detail="This action is restricted to the server owner.")
        return principal

    # -- routes -------------------------------------------------------------

    @app.get("/")
    async def root() -> dict:
        """What this server is and how one gets in.

        A client asks this *before* offering a way in, so it can say "this
        server has accounts switched off" instead of letting someone type a
        login code that could never work.
        """
        accounts = service is not None
        return {
            "name": settings.assistant_name,
            "version": __version__,
            "status": "online",
            "auth": "accounts" if accounts else "shared-key",
            "accounts": accounts,
            "signup": bool(accounts and settings.auth_allow_signup),
            "telegram_login": accounts,
            "requires_license": bool(accounts and settings.auth_require_license),
            "proxy": bool(accounts and settings.proxy_enabled),
        }

    @app.get("/health")
    async def health() -> dict:
        """Liveness probe only: no auth, no detail, safe to leave open.

        Anything more — which providers are configured, which dangerous
        capabilities are enabled, security-audit findings, config validation
        errors — is a map of the server's attack surface handed to anyone
        who can reach the port. That detail moved to /health/full, which
        only the owner can read. Docker's healthcheck only cares about the
        HTTP status code, so this change is invisible to it.
        """
        return {"ok": True}

    @app.get("/health/full")
    async def health_full(_: str = Depends(require_owner)) -> dict:
        """Full diagnostics: providers, capabilities, config, security audit.

        Same payload /health used to return before it was locked down —
        moved here rather than removed, so `jarvis doctor`-style operator
        tooling still works, just behind ownership instead of the open
        internet.
        """
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
        async def voice_stt(request: HttpRequest,
                            file: UploadFile = File(...),  # noqa: B008 - FastAPI dep
                            _: str = Depends(require_principal)) -> dict:
            """Transcribe uploaded audio to text."""
            svc = _voice()
            if svc is None or not svc.stt_available():
                raise HTTPException(503, "Speech-to-text is not configured.")
            cap = settings.voice_stt_max_bytes
            too_big = HTTPException(
                status_code=413,
                detail=f"Audio upload exceeds the {cap // (1024 * 1024)} MB limit.")
            # Fast path: a clearly, honestly oversized request is refused
            # before reading a single byte of the body. Content-Length here
            # is the *whole* multipart body (boundaries, per-part headers,
            # filename) — a few hundred bytes more than the file content the
            # cap actually governs — so only reject when it overshoots by
            # more than any realistic framing overhead could explain; the
            # exact, authoritative check is the capped read below, which
            # counts the file's own bytes and needs no such margin. Neither
            # check trusts the header alone (a client can omit or lie about
            # it with chunked transfer encoding) — that's what the read does.
            declared = request.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > cap + 65_536:
                raise too_big
            try:
                audio = await _read_capped(file, cap)
            except ValueError:
                raise too_big from None
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
        text = body.text.strip()
        if not text:
            raise HTTPException(400, "Nothing to speak.")
        if len(text) > settings.voice_tts_max_chars:
            raise HTTPException(
                status_code=413,
                detail=f"Text exceeds the {settings.voice_tts_max_chars} "
                        f"character limit.")
        audio = await svc.synthesize(text, body.language)
        ext = svc.tts_ext()
        media = {"ogg": "audio/ogg", "mp3": "audio/mpeg",
                "wav": "audio/wav"}.get(ext, "application/octet-stream")
        return Response(content=audio, media_type=media)

    @app.post("/chat", response_model=ChatOut)
    async def chat(body: ChatIn,
                principal: str = Depends(require_principal)) -> ChatOut:
        scoped = _scoped(principal, body.session_id)
        _apply_prefs(scoped, body)
        _apply_device_relay(scoped, principal)
        response = await engine.process(
            Request(text=body.message, session_id=scoped, source="api"))
        return ChatOut(reply=response.text, session_id=body.session_id)

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
        _apply_device_relay(scoped, principal)

        async def _generate():
            async for chunk in engine.stream(
                Request(text=body.message, session_id=scoped, source="api")
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
        _apply_device_relay(scoped, principal)
        try:
            while True:
                text = await websocket.receive_text()
                async for chunk in engine.stream(
                    Request(text=text, session_id=scoped, source="api")
                ):
                    await websocket.send_text(chunk)
                await websocket.send_json({"event": "done"})
        except WebSocketDisconnect:
            return

    @app.websocket("/device/ws")
    async def device_ws(websocket: WebSocket) -> None:
        """A connected device (the exe in remote mode, or the standalone
        ``python -m jarvis.desktop.agent``) — see
        jarvis/desktop/device_registry.py for the protocol. One socket per
        principal; the desktop-control tools relay through it via
        `_apply_device_relay` above.
        """
        principal = _principal(websocket.query_params.get("key"))
        if principal is None:
            await websocket.close(code=1008)  # policy violation
            return
        await websocket.accept()
        try:
            hello = await websocket.receive_json()
        except Exception:  # noqa: BLE001 - a malformed first frame just disconnects
            await websocket.close(code=1003)
            return
        device_id = str(hello.get("device_id") or "device")
        capabilities = list(hello.get("capabilities") or [])
        engine.container.devices.register(principal, websocket, device_id,
                                        capabilities)
        try:
            while True:
                msg = await websocket.receive_json()
                if msg.get("type") == "tool_result":
                    # `principal` is this socket's own authenticated identity
                    # (resolved once above, at connection time) — never taken
                    # from the message — so this connection can only ever
                    # resolve a call that was issued to it.
                    engine.container.devices.resolve(
                        principal, msg.get("call_id", ""),
                        content=str(msg.get("content", "")),
                        metadata=msg.get("metadata") or {},
                    )
        except WebSocketDisconnect:
            pass
        finally:
            engine.container.devices.unregister(principal, device_id)

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

    def _tenant_prefix(principal: str) -> str | None:
        """The caller's own memory/session namespace, or ``None``.

        This engine — and the memory database behind it — is shared by every
        request the API serves. When accounts are enabled, several distinct
        principals genuinely share one process, and every real chat session
        already lives under ``f"{principal}::{session_id}"`` (see
        ``_scoped``), so filtering by that prefix here shows each caller only
        their own conversations and memories rather than everyone's.

        With accounts disabled there is exactly one legitimate caller (the
        holder of the single ``API_KEY``, or nobody at all in open dev mode),
        so there is nothing to scope against — and a local/CLI caller may
        have written memory under a bare id like ``"default"`` with no
        principal prefix at all, which a prefix filter would hide from them.
        Returning ``None`` here keeps that single-tenant case working exactly
        as it always has.
        """
        return f"{principal}::" if service is not None else None

    def _confirm_owner(principal: str) -> str | None:
        """Whose confirmation questions ``principal`` may see or answer.

        Same single-tenant passthrough as :func:`_tenant_prefix` (``None``
        when accounts are off — there is only one legitimate caller and
        nothing to scope against), without the trailing ``"::"`` since this
        compares against a whole owner name, not a session-id prefix.
        """
        return principal if service is not None else None

    @app.get("/dashboard/sessions")
    async def dashboard_sessions(
            principal: str = Depends(require_principal)) -> dict:
        """Recent conversations (real history) for the chat sidebar."""
        import asyncio as _a
        mem = getattr(engine, "memory", None)
        if mem is None or getattr(mem, "conversations", None) is None:
            return {"sessions": []}
        rows = await _a.to_thread(
            mem.conversations.recent, 20,
            session_prefix=_tenant_prefix(principal))
        return {"sessions": rows}

    @app.get("/dashboard/sessions/{session_id}/messages")
    async def dashboard_session_messages(
            session_id: str,
            principal: str = Depends(require_principal)) -> dict:
        """One past conversation's messages, for reopening it in the chat
        view (Этап 2 / Фаза B6) — /dashboard/sessions only ever returned the
        summary list (title/count/last_ts), never a way to see what was
        actually said.

        ``session_id`` is caller-supplied, so it is checked against the
        caller's own tenant prefix before anything is loaded — the same
        "don't confirm which" 404 every other cross-tenant probe in this
        file gets, rather than a permission error that would out a real id
        belonging to someone else.
        """
        mem = getattr(engine, "memory", None)
        if mem is None or getattr(mem, "conversations", None) is None:
            return {"messages": []}
        prefix = _tenant_prefix(principal)
        if prefix is not None and not session_id.startswith(prefix):
            raise HTTPException(status_code=404, detail="No such session.")
        import asyncio as _a
        convo = await _a.to_thread(mem.conversations.load, session_id, limit=200)
        return {"messages": [
            {"role": m.role.value, "content": m.content,
            "timestamp": m.timestamp.timestamp()}
            for m in convo.messages
        ]}

    def _broker():
        """The engine's confirmation broker, when it has one."""
        return getattr(engine.security, "confirmer", None)

    async def _state_payload(principal: str) -> dict:
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
            "confirmations": _broker().pending(owner=_confirm_owner(principal))
                            if _broker() else [],
            "weather": await _weather(),
        }

    @app.get("/dashboard/state")
    async def dashboard_state(
            principal: str = Depends(require_principal)) -> dict:
        return await _state_payload(principal)

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
                await websocket.send_json(await _state_payload(principal))
                # A question the assistant is blocked on must reach the screen
                # quickly; the rest of the state can wait five seconds.
                broker = _broker()
                waiting = bool(
                    broker and broker.pending(owner=_confirm_owner(principal)))
                await _a.sleep(0.7 if waiting else 5)
        except WebSocketDisconnect:
            return
        except Exception:  # noqa: BLE001 - client gone / send failed
            return

    @app.get("/dashboard/tasks")
    async def dashboard_tasks(
            authorization: str | None = Header(default=None),
            x_api_key: str | None = Header(default=None),
            _: str = Depends(require_principal)) -> dict:
        """Scheduled automations + reminders — the caller's own.

        Automations and reminders are always created through the Telegram
        bot, keyed by the creator's numeric Telegram id (see
        jarvis.interfaces.automations / .reminders) — this API only ever
        reads them. That used to mean an unscoped "SELECT * ... LIMIT 50",
        handing every account on a shared server everyone's scheduled tasks.
        Scoping means resolving which Telegram id, if any, the caller's
        account is linked to.
        """
        import asyncio as _a

        from jarvis.interfaces.automations import AutomationStore
        from jarvis.interfaces.reminders import ReminderStore

        telegram_owner = ""
        if service is not None:
            token = None
            if authorization and authorization.startswith("Bearer "):
                token = authorization[len("Bearer "):]
            token = token or x_api_key
            account = service.validate_token(token) if token else None
            if account and account.telegram_user_id:
                telegram_owner = str(account.telegram_user_id)

        def _read() -> dict:
            # Accounts are on, but this one has no linked Telegram: it cannot
            # own an automation or reminder (only the bot creates them), so
            # there is nothing to show rather than everyone else's.
            if service is not None and not telegram_owner:
                return {"automations": [], "reminders": []}
            a_store = AutomationStore(settings.memory_db_path)
            r_store = ReminderStore(settings.memory_db_path)
            try:
                if telegram_owner:
                    a_rows = a_store.list_active(telegram_owner, limit=50)
                    r_rows = r_store.list_active(telegram_owner, limit=50)
                else:
                    # No accounts on this server: a single-tenant deployment
                    # has exactly one legitimate caller, so "everything" is
                    # already "their own" — the original, unscoped behaviour.
                    a_rows = a_store._conn.execute(  # noqa: SLF001 - read-only
                        "SELECT * FROM automations WHERE enabled = 1 "
                        "ORDER BY next_ts LIMIT 50").fetchall()
                    r_rows = r_store._conn.execute(  # noqa: SLF001
                        "SELECT * FROM reminders WHERE fired = 0 "
                        "ORDER BY due_ts LIMIT 50").fetchall()
                autos = [{"id": r["id"], "prompt": r["prompt"], "kind": r["kind"],
                        "next_ts": r["next_ts"]} for r in a_rows]
                rems = [{"id": r["id"], "text": r["text"], "due_ts": r["due_ts"]}
                        for r in r_rows]
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
        # Optional device metadata (Этап 2 / Фаза B1) — see LoginIn in
        # jarvis/api/auth.py for the same fields on password login.
        device_id: str | None = None
        device_name: str = ""
        platform: str = ""
        client_type: str = ""

    @app.post("/auth/telegram")
    async def auth_telegram(body: _TgLoginIn) -> dict:
        """Exchange a bot-issued login code for an auth token (Telegram login)."""
        if service is None:
            raise HTTPException(status_code=400,
                                detail="Accounts are not enabled on this server.")
        result = service.redeem_telegram_login(
            body.code, device_id=body.device_id, device_name=body.device_name,
            platform=body.platform, client_type=body.client_type)
        if result is None:
            raise HTTPException(status_code=401,
                                detail="Invalid or expired code.")
        token, username = result
        return {"token": token, "username": username}

    class _McpIn(BaseModel):
        spec: str

    @app.post("/dashboard/mcp")
    async def dashboard_add_mcp(body: _McpIn,
                            _: str = Depends(require_owner)) -> dict:
        """Connect an MCP server over SSE at runtime, and mount its tools.

        Owner-only, and SSE-only. This used to also accept a bare command
        ("command arg1 arg2 …") and hand it straight to
        ``StdioServerParameters`` — which spawns it as a subprocess of the API
        server. Combined with ``require_principal`` (any signed-in account,
        including one a person just created for free through the bot), that
        was unauthenticated-enough-to-matter remote code execution: one POST
        with a valid token and a shell one-liner as `spec` ran it on the
        server. There is no way to make "run this string as a local process"
        safe to expose over HTTP to customers, so that branch is gone rather
        than patched — a server that genuinely needs a stdio MCP server
        configures it via MCP_CONFIG_PATH/MCP_SERVERS (jarvis/mcp/config.py),
        read once at startup, under the operator's own control.

        The SSE branch stays because it does not execute anything on this
        server — it only makes the server a network client of a URL — but it
        is still owner-gated: an SSE connection is still an outbound request
        the server owner didn't necessarily choose (SSRF against internal
        services), and there is no reason a customer's account should be able
        to make the shared engine originate arbitrary outbound connections.
        """
        from jarvis.mcp.base import MCPServerConfig
        from jarvis.mcp.manager import MCPManager
        spec = body.spec.strip()
        if not (spec.startswith("http://") or spec.startswith("https://")):
            raise HTTPException(
                status_code=400,
                detail="Only an http(s) URL (SSE transport) may be connected "
                        "here. A local command belongs in the server's own "
                        "MCP_CONFIG_PATH configuration, not sent over the API.")
        cfg = MCPServerConfig(name=spec.split("//")[-1][:20],
                            transport="sse", url=spec)
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
            principal: str = Depends(require_principal)) -> dict:
        """Anything the assistant is currently waiting on *this caller* for."""
        broker = _broker()
        return {"pending": broker.pending(owner=_confirm_owner(principal))
                if broker else []}

    @app.post("/dashboard/confirm")
    async def dashboard_confirm(
            body: _ConfirmIn,
            principal: str = Depends(require_principal)) -> dict:
        """Answer one of *this caller's own* permission questions."""
        broker = _broker()
        if broker is None:
            raise HTTPException(status_code=503,
                                detail="This engine does not ask for "
                                        "confirmation.")
        answered = broker.resolve(body.id, body.allow,
                                owner=_confirm_owner(principal))
        if not answered:
            # Already answered, timed out, or (same response either way)
            # belongs to someone else — this never confirms which.
            raise HTTPException(status_code=404,
                                detail="That request is no longer waiting.")
        return {"ok": True, "id": body.id, "allowed": body.allow}

    # -- devices ---------------------------------------------------------------
    #
    # Two independent sources, merged: DeviceRegistry (jarvis/desktop/
    # device_registry.py) knows which devices can run a desktop-control tool
    # call *right now* — live WebSocket connections only, nothing persisted.
    # LicenseService.list_sessions (Этап 2 / Фаза A2) knows every session
    # (login) ever issued to the account — Telegram, Web, Desktop — with a
    # "last seen" stamp that survives a dropped connection. Neither alone
    # answers "what does this account have logged in": the registry forgets
    # a device the moment it disconnects, and sessions don't know whether a
    # desktop-control socket happens to be open right now.

    def _account_for_principal(principal: str):
        """The account row behind ``principal``, or ``None``.

        Only ``user:<username>`` principals have one — the shared API_KEY
        (``SHARED_PRINCIPAL``) is a single operator secret with no account
        row of its own, so it has no session history to list. Same
        single-tenant-vs-real-accounts distinction ``_tenant_prefix`` and
        ``_confirm_owner`` already draw.
        """
        if service is None or not principal.startswith("user:"):
            return None
        return service.get_account(principal[len("user:"):])

    @app.get("/dashboard/devices")
    async def dashboard_devices(
            principal: str = Depends(require_principal)) -> dict:
        """This account's devices: live desktop-control connections merged
        with every session ever issued to it. Session history is only
        available with accounts enabled — in shared-key/open mode this shows
        live desktop-control connections alone, with no login history."""
        live = engine.container.devices.describe(principal)
        live_ids = {d["device_id"] for d in live if d.get("device_id")}
        sessions: list[dict] = []
        account = _account_for_principal(principal)
        if account is not None:
            for s in service.list_sessions(account.id):
                sessions.append({
                    **s,
                    "online": bool(s["device_id"]) and s["device_id"] in live_ids,
                })
        return {"live_devices": live, "sessions": sessions}

    class _RevokeSessionIn(BaseModel):
        id: str

    @app.post("/dashboard/devices/revoke")
    async def dashboard_devices_revoke(
            body: _RevokeSessionIn,
            principal: str = Depends(require_principal)) -> dict:
        """End one of *this account's own* sessions — e.g. signing an old
        phone or a lost laptop out remotely."""
        account = _account_for_principal(principal)
        if account is None:
            raise HTTPException(status_code=404,
                                detail="No session history without an account.")
        revoked = service.revoke_session(account.id, body.id)
        if not revoked:
            # Unknown id and someone else's id are reported identically —
            # same "don't confirm which" reasoning as /dashboard/confirm.
            raise HTTPException(status_code=404,
                                detail="That session is not yours or no "
                                        "longer exists.")
        return {"ok": True, "id": body.id}

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

    def _own_session_id(principal: str, session: str) -> str | None:
        """The exact session a caller may name directly.

        In multi-tenant mode the caller's own prefix is stitched onto
        whatever session name they gave — they can browse *within* their own
        sessions, but cannot hand in someone else's already-qualified session
        id and read it verbatim. Single-tenant mode is untouched: the raw
        name they gave, exactly as before.
        """
        prefix = _tenant_prefix(principal)
        if not session:
            return None
        return f"{prefix}{session}" if prefix else session

    @app.get("/dashboard/memory")
    async def dashboard_memory(limit: int = 100, offset: int = 0,
                            session: str = "",
                            principal: str = Depends(require_principal)) -> dict:
        """What the assistant remembers, newest first — the caller's own."""
        memory = _memory_or_503()
        session_id = _own_session_id(principal, session)
        prefix = None if session_id else _tenant_prefix(principal)
        records = await memory.browse(session_id=session_id,
                                    session_prefix=prefix,
                                    limit=limit, offset=offset)
        return {
            "can_browse": memory.can_browse(),
            "stats": memory.stats(session_prefix=_tenant_prefix(principal)),
            "items": [{"id": r.record_id, "content": r.content,
                    "kind": r.kind, "session": r.session_id,
                    "timestamp": r.timestamp.isoformat()} for r in records],
        }

    @app.get("/dashboard/memory/search")
    async def dashboard_memory_search(
            q: str, limit: int = 20,
            principal: str = Depends(require_principal)) -> dict:
        """Search memories the way the assistant itself recalls them.

        Scoped to the caller's own sessions — recall used to search
        (``session_id=None``) *every* account's memory on a shared server.
        """
        memory = _memory_or_503()
        if not q.strip():
            return {"items": []}
        records = await memory.recall(q, session_id=None,
                                    session_prefix=_tenant_prefix(principal),
                                    limit=limit)
        return {"items": [{"id": r.record_id, "content": r.content,
                        "kind": r.kind, "session": r.session_id,
                        "score": round(r.score, 3),
                        "timestamp": r.timestamp.isoformat()}
                        for r in records]}

    @app.delete("/dashboard/memory/{record_id}")
    async def dashboard_memory_delete(
            record_id: int,
            principal: str = Depends(require_principal)) -> dict:
        """Forget one specific thing — only if it is the caller's own.

        A record outside the caller's own sessions is reported the same way
        as one that never existed (404), never a permission error: telling
        the two apart would confirm that some other tenant's record id is
        real.
        """
        memory = _memory_or_503()
        removed = await memory.delete_memory(
            record_id, session_prefix=_tenant_prefix(principal))
        if not removed:
            raise HTTPException(status_code=404, detail="No such memory.")
        return {"ok": True, "id": record_id}

    class _ForgetIn(BaseModel):
        session: str | None = None
        everything: bool = False

    @app.post("/dashboard/memory/forget")
    async def dashboard_memory_forget(
            body: _ForgetIn,
            principal: str = Depends(require_principal)) -> dict:
        """Clear a session's memory, or all of it — all of *theirs*, on a
        server that has more than one tenant."""
        memory = _memory_or_503()
        prefix = _tenant_prefix(principal)
        if body.everything:
            if prefix:
                await memory.forget_by_prefix(prefix)
            else:
                await memory.forget(None)
        else:
            await memory.forget(_own_session_id(principal, body.session or "default"))
        return {"ok": True, "stats": memory.stats(session_prefix=prefix)}

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
        if settings.proxy_enabled:
            from jarvis.api.proxy_routes import install_proxy_routes
            install_proxy_routes(app, settings, service, engine)

    app.state.engine = engine
    app.state.license_service = service
    return app
