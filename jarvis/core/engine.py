"""
The J.A.R.V.I.S. engine — the async orchestrator that ties every layer together.

Flow of a single turn:

    Request
      → pipeline (normalise, log, …)
        → skill registry     (fast path: handle locally if a skill matches)
        → LLM agentic loop   (otherwise reason with the model, calling tools)
      → Response
      → events + telemetry

The engine owns the session manager, the state machine, and the wiring
provided by the :class:`~jarvis.core.container.ServiceContainer`.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from jarvis.config.constants import AssistantState, EventType, ResponseType
from jarvis.config.settings import Settings
from jarvis.core.container import ServiceContainer
from jarvis.core.context import SessionContext
from jarvis.core.pipeline import (
    LoggingMiddleware,
    NormalizeMiddleware,
    Pipeline,
    RateLimitMiddleware,
)
from jarvis.core.ratelimit import RateLimiter
from jarvis.core.runtime import set_session
from jarvis.core.session import SessionManager
from jarvis.core.state import StateMachine
from jarvis.i18n import language_name
from jarvis.llm.tools import ToolResult
from jarvis.models.response import Request, Response
from jarvis.utils.exceptions import JarvisError
from jarvis.utils.logger import get_logger
from jarvis.utils.text import normalize
from jarvis.utils.timing import measure

logger = get_logger(__name__)


class JarvisEngine:
    """Central async coordinator for J.A.R.V.I.S."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        container: ServiceContainer | None = None,
    ) -> None:
        self.container = container or ServiceContainer(settings)
        self.settings = self.container.settings

        # Shared services (constructed lazily by the container).
        self.bus = self.container.event_bus
        self.metrics = self.container.metrics
        self.llm = self.container.llm
        self.skills = self.container.skills
        self.prompts = self.container.prompts
        self.memory = self.container.memory  # None when memory is disabled
        self.integrations = self.container.integrations  # None when disabled
        self.goals = self.container.goals  # None when goals are disabled
        self.security = self.container.security  # capability gate + audit
        self.search = self.container.search  # None when web search is off
        self.router = self.container.router  # model-tier routing
        self.tools = self.container.tool_manager  # tool governance/introspection
        self.mcp = self.container.mcp_manager  # None unless MCP is enabled

        # Per-engine state. When memory is on, new sessions reload their
        # persisted history transparently via the loader.
        loader = self.memory.load_conversation if self.memory else None
        self.state = StateMachine(self.bus)
        self.sessions = SessionManager(
            max_sessions=self.settings.max_sessions, loader=loader
        )
        middleware = [NormalizeMiddleware(), LoggingMiddleware()]
        if self.settings.rate_limit_enabled:
            limiter = RateLimiter(
                capacity=self.settings.rate_limit_capacity,
                window_seconds=self.settings.rate_limit_window_seconds,
            )
            middleware.insert(0, RateLimitMiddleware(limiter))
        self.pipeline = Pipeline(middleware)

        # Fire-and-forget background work (e.g. fact extraction after a reply).
        self._background: set[asyncio.Task] = set()

        logger.info(
            "%s ready (provider=%s, model=%s, skills=%d, tools=%d, memory=%s, "
            "integrations=%d)",
            self.settings.assistant_name,
            self.settings.llm_provider,
            self.settings.llm_model,
            len(self.skills),
            len(self.skills.tool_specs()),
            "on" if self.memory else "off",
            len(self.integrations) if self.integrations else 0,
        )

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        await self.bus.emit(EventType.STARTUP, source="engine")
        await self._connect_integrations()
        await self._connect_mcp()

    async def shutdown(self) -> None:
        await self.drain()
        if self.integrations is not None:
            await self.integrations.disconnect_all()
        if self.mcp is not None:
            await self.mcp.stop()
        await self.bus.emit(EventType.SHUTDOWN, source="engine")

    async def _connect_mcp(self) -> None:
        """Connect MCP servers and register their tools as skills."""
        if self.mcp is None:
            return
        try:
            skills = await self.mcp.start()
        except Exception as exc:  # noqa: BLE001 - MCP must never block startup
            logger.warning("MCP startup failed: %s", exc)
            return
        for skill in skills:
            try:
                self.skills.register(skill)
            except Exception as exc:  # noqa: BLE001 - skip duplicates/bad tools
                logger.warning("Could not register MCP skill %r: %s",
                            skill.name, exc)
        if skills:
            logger.info("MCP: mounted %d external tool(s).", len(skills))

    async def _connect_integrations(self) -> None:
        if self.integrations is None:
            return
        for status in await self.integrations.connect_all():
            event = (
                EventType.INTEGRATION_CONNECTED
                if status.state.value == "connected"
                else EventType.INTEGRATION_ERROR
            )
            await self.bus.emit(event, source=status.name, detail=status.detail)

    # -- public API ---------------------------------------------------------

    async def ask(self, user_input: str, *, session_id: str = "default") -> str:
        """Process one user message and return the assistant's reply text."""
        response = await self.process(
            Request(text=user_input, session_id=session_id)
        )
        return response.text

    async def process(self, request: Request) -> Response:
        """Process a structured :class:`Request` through the full pipeline."""
        await self.bus.emit(EventType.USER_INPUT, source="engine", text=request.text)
        try:
            response = await self.pipeline.run(request, self._handle)
        except JarvisError as exc:
            await self.state.transition(AssistantState.ERROR)
            await self.bus.emit(EventType.ERROR, source="engine", error=str(exc))
            logger.error("Turn failed: %s", exc)
            response = Response.system_message(
                f"I ran into a problem: {exc}",
                request_id=request.request_id,
            )
        finally:
            await self.state.transition(AssistantState.IDLE)

        await self.bus.emit(
            EventType.RESPONSE_READY,
            source=response.source or "engine",
            latency_ms=response.latency_ms,
            tokens=response.tokens,
            via_skill=response.type == ResponseType.SKILL,
        )
        return response

    async def stream(self, request: Request) -> AsyncIterator[str]:
        """Stream a reply as text chunks.

        Skills are still tried first (their reply is emitted as one chunk);
        otherwise the LLM response is streamed token by token. Tool calling is
        not available on the streaming path — use :meth:`process` for that.
        """
        request.text = normalize(request.text)
        set_session(request.session_id)
        session = self.sessions.get_or_create(request.session_id)
        await self.bus.emit(EventType.USER_INPUT, source="engine", text=request.text)

        skill = self.skills.find(request.text)
        if skill is not None:
            result = await skill.handle(request.text, session.scratch)
            if result.handled:
                session.conversation.add_user(request.text)
                session.conversation.add_assistant(result.text)
                await self._persist_turn(session.session_id, request.text,
                                        result.text, semantic=False)
                await self.bus.emit(EventType.SKILL_MATCHED, source=skill.name)
                await self.bus.emit(EventType.RESPONSE_READY, source=skill.name,
                                    via_skill=True)
                yield result.text
                await self.state.transition(AssistantState.IDLE)
                return

        # LLM streaming path.
        session.conversation.add_user(request.text)
        system = self.prompts.system_prompt(
            extra_context=await self._context(request.text, session.session_id),
            language=self._language(session),
            assistant_name=self._assistant_name(session),
        )
        await self.state.transition(AssistantState.THINKING)
        await self.bus.emit(EventType.LLM_REQUEST, source=self.settings.llm_provider)

        model_id, profile = self._model_selection(session)
        override = self._byok_provider(session)
        chunks: list[str] = []
        async for chunk in self.llm.stream(
            session.conversation.to_provider_format(), system=system,
            profile=profile, model=model_id, override=override,
        ):
            chunks.append(chunk)
            yield chunk

        full = "".join(chunks).strip()
        session.conversation.add_assistant(full)
        await self._persist_turn(session.session_id, request.text, full,
                                semantic=True)
        await self.bus.emit(EventType.RESPONSE_READY, source=self.settings.llm_provider)
        await self.state.transition(AssistantState.IDLE)

    def _model_selection(self, session) -> tuple[str | None, str | None]:
        """Resolve ``(model, profile)`` from the session scratch.

        A specific catalog model (``model_id``) is routed through the
        OpenRouter profile; otherwise only the user's chosen profile applies.
        """
        model_id = session.scratch.get("model_id")
        if model_id:
            return model_id, "openrouter"
        return None, session.scratch.get("model_profile")

    def _byok_provider(self, session):
        """Build an ad-hoc provider from the user's own key (BYOK), or None."""
        byok = session.scratch.get("byok")
        if not byok or not byok.get("key"):
            return None
        from jarvis.llm.providers import PROVIDER_REGISTRY
        cls = PROVIDER_REGISTRY.get(byok.get("provider", ""))
        if cls is None:
            return None
        return cls(
            api_key=byok["key"],
            model=byok.get("model") or "",
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            base_url=byok.get("base_url", ""),
        )

    # -- core handler (wrapped by the pipeline) ----------------------------

    async def _handle(self, request: Request) -> Response:
        set_session(request.session_id)
        session = self.sessions.get_or_create(request.session_id)
        if not request.text:
            return Response.system_message("", request_id=request.request_id)

        # 1) Try a local skill first (fast path).
        response = await self._try_skill(request, session)
        if response is not None:
            return response

        # 2) Fall back to the LLM agentic loop.
        return await self._ask_llm(request, session)

    async def _try_skill(
        self, request: Request, session: SessionContext
    ) -> Response | None:
        await self.state.transition(AssistantState.THINKING)

        skill = self.skills.find(request.text)
        if skill is None:
            return None

        try:
            result = await skill.handle(request.text, session.scratch)
        except Exception as exc:  # noqa: BLE001 - degrade to LLM on skill failure
            await self.bus.emit(EventType.SKILL_FAILED, source=skill.name, error=str(exc))
            logger.warning("Skill %r failed (%s) — falling back to LLM", skill.name, exc)
            return None

        if not result.handled:
            return None

        await self.bus.emit(EventType.SKILL_MATCHED, source=skill.name)
        session.conversation.add_user(request.text)
        session.conversation.add_assistant(result.text)
        # Persist history, but skill turns are trivial — don't add to semantic memory.
        await self._persist_turn(session.session_id, request.text, result.text,
                                semantic=False)
        return Response.from_skill(
            result.text,
            skill_name=skill.name,
            request_id=request.request_id,
            metadata=result.metadata,
        )

    async def _ask_llm(
        self, request: Request, session: SessionContext
    ) -> Response:
        """Run the agentic loop: complete → run tools → repeat → final text."""
        await self.state.transition(AssistantState.THINKING)
        session.conversation.add_user(request.text)

        is_voice = request.source == "voice"
        extra_context = await self._context(request.text, session.session_id)
        if is_voice:
            hint = ("This reply will be read aloud; answer in 2-4 sentences "
                    "unless the user asked for detail.")
            extra_context = f"{extra_context}\n\n{hint}" if extra_context else hint
        system = self.prompts.system_prompt(
            extra_context=extra_context,
            language=self._language(session),
            assistant_name=self._assistant_name(session),
        )
        tools = self.skills.tool_specs()
        model_id, profile = self._model_selection(session)
        override = self._byok_provider(session)
        # A specific catalog model wins everywhere (incl. on a BYOK key); a
        # voice turn prefers the fast tier next (kept snappy for speech);
        # otherwise BYOK uses its own default and the router picks a tier.
        if model_id:
            model = model_id
        elif override:
            model = None
        elif is_voice and self.settings.llm_model_fast:
            model = self.settings.llm_model_fast
        else:
            model = self.router.model_for(request.text)
        messages = session.conversation.to_provider_format()
        total_tokens = 0
        tool_metadata: dict = {}
        result = None
        rounds = (self.settings.voice_max_tool_rounds if is_voice
                else self.settings.max_tool_rounds)

        with measure() as sw:
            await self.bus.emit(EventType.LLM_REQUEST, source=self.settings.llm_provider)
            for _ in range(rounds):
                result = await self.llm.complete(
                    messages, system=system, tools=tools, model=model,
                    profile=profile, override=override,
                )
                total_tokens += result.total_tokens

                if not result.wants_tools:
                    break

                await self.state.transition(AssistantState.EXECUTING)
                tool_results, round_metadata = await self._run_tools(
                    result, session.scratch)
                tool_metadata.update(round_metadata)
                messages = messages + self.llm.continuation_messages(result, tool_results)
                await self.state.transition(AssistantState.THINKING)

        assert result is not None
        await self.bus.emit(EventType.LLM_RESPONSE, source=result.provider,
                            tokens=total_tokens)
        session.conversation.add_assistant(result.text)
        await self._persist_turn(session.session_id, request.text, result.text,
                                semantic=True)
        await self.state.transition(AssistantState.SPEAKING)
        return Response.from_llm(
            result.text,
            provider=result.provider,
            request_id=request.request_id,
            latency_ms=sw.elapsed_ms,
            tokens=total_tokens,
            metadata=tool_metadata,
        )

    async def _run_tools(
        self, result, context: dict | None = None
    ) -> tuple[list[ToolResult], dict]:
        """Execute every tool call requested by the model, concurrently.

        Calls within one round come from a single model completion and are
        independent of each other by construction, so running them with
        ``asyncio.gather`` is safe and cuts round-trip latency — a real win
        shared by every caller (text, voice, API, CLI), not only voice.
        """

        async def one(call) -> tuple[ToolResult, dict]:
            await self.bus.emit(EventType.TOOL_CALL, source=call.name,
                                arguments=call.arguments)
            try:
                skill_result = await self.skills.invoke_tool(
                    call.name, call.arguments, context=context)
                content, is_error, metadata = skill_result.text, False, skill_result.metadata
            except JarvisError as exc:
                content, is_error, metadata = f"Tool error: {exc}", True, {}
                await self.bus.emit(EventType.SKILL_FAILED, source=call.name,
                                    error=str(exc))
            await self.bus.emit(EventType.TOOL_RESULT, source=call.name)
            return (ToolResult(call_id=call.id, name=call.name, content=content,
                            is_error=is_error), metadata)

        pairs = await asyncio.gather(*(one(call) for call in result.tool_calls))
        tool_results = [p[0] for p in pairs]
        merged_metadata: dict = {}
        for _, metadata in pairs:
            merged_metadata.update(metadata)
        return tool_results, merged_metadata

    # -- memory helpers -----------------------------------------------------

    async def _context(self, query: str, session_id: str) -> str | None:
        """Assemble extra system-prompt context: recalled memory + open goals."""
        parts: list[str] = []
        if self.memory is not None:
            recalled = await self.memory.recall_context(query, session_id=session_id)
            if recalled:
                parts.append(recalled)
        if self.goals is not None:
            goals = await self.goals.active(session_id)
            if goals:
                listing = "\n".join(f"- #{g.id}: {g.text}" for g in goals)
                parts.append(f"The user's open goals:\n{listing}")
        return "\n\n".join(parts) if parts else None

    @staticmethod
    def _language(session: SessionContext) -> str | None:
        """Human-readable language the assistant should reply in, if set."""
        code = session.scratch.get("language")
        return language_name(code) if code else None

    @staticmethod
    def _assistant_name(session: SessionContext) -> str | None:
        """A per-user assistant name (white-label override), if set."""
        return session.scratch.get("assistant_name") or None

    async def _persist_turn(self, session_id: str, user: str, assistant: str, *,
                            semantic: bool) -> None:
        """Persist a turn to history and, optionally, semantic memory.

        History is persisted inline; distilling the turn into durable memory
        (which may call the LLM for fact extraction) runs in the background so
        it never adds latency to the user's reply.
        """
        if self.memory is None:
            return
        await self.memory.persist_turn(session_id, user, assistant)
        if semantic:
            self._spawn(self.memory.remember_turn(session_id, user, assistant))

    def _spawn(self, coro) -> None:
        """Schedule a background coroutine, keeping a reference until done."""
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def drain(self) -> None:
        """Await all pending background tasks (useful in tests and shutdown)."""
        if self._background:
            await asyncio.gather(*list(self._background), return_exceptions=True)

    # -- session management -------------------------------------------------

    async def reset(self, session_id: str = "default") -> None:
        """Clear the conversation history for a session (keeps long-term memory)."""
        self.sessions.reset(session_id)
        if self.memory is not None:
            await self.memory.clear_history(session_id)
        await self.state.reset()
        logger.debug("Session %r reset.", session_id)

    async def forget(self, session_id: str = "default") -> None:
        """Wipe both conversation history and long-term memory for a session."""
        self.sessions.reset(session_id)
        if self.memory is not None:
            await self.memory.forget(session_id)
        if self.goals is not None:
            await self.goals.clear(session_id)
        await self.state.reset()
        logger.debug("Session %r fully forgotten.", session_id)

    def session(self, session_id: str = "default") -> SessionContext:
        """Return (creating if needed) the context for a session."""
        return self.sessions.get_or_create(session_id)

    # -- convenience --------------------------------------------------------

    @property
    def stats(self) -> dict:
        """Telemetry snapshot for the current process."""
        return self.metrics.summary()
