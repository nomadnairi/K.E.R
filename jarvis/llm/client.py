"""
Unified async LLM client.

Wraps one or more :class:`~jarvis.llm.base.LLMProvider` instances behind a
single interface, adding:

* async ``complete`` (with tool calling) and async ``stream``,
* automatic retry with exponential backoff (transient failures), and
* provider fallback — if the primary provider fails, configured fallbacks are
  tried in order before giving up.

The rest of the system talks only to this class.
"""

from __future__ import annotations

from typing import AsyncIterator

from jarvis.config.settings import Settings
from jarvis.llm.base import LLMProvider, LLMResult
from jarvis.llm.providers import PROVIDER_REGISTRY
from jarvis.llm.tools import ToolResult, ToolSpec
from jarvis.utils.exceptions import (
    AllProvidersFailedError,
    LLMConfigError,
    LLMError,
)
from jarvis.utils.logger import get_logger
from jarvis.utils.retry import retry_async

logger = get_logger(__name__)


class LLMClient:
    """Provider-agnostic async client with retry and fallback."""

    def __init__(
        self,
        primary: LLMProvider,
        fallbacks: list[LLMProvider] | None = None,
        *,
        retry_attempts: int = 3,
        profiles: "dict[str, LLMProvider] | None" = None,
    ) -> None:
        self.primary = primary
        self.fallbacks = fallbacks or []
        self._retry_attempts = retry_attempts
        #: Named, switchable providers (e.g. "claude", "gpt", "openrouter").
        self.profiles: dict[str, LLMProvider] = profiles or {}

    def list_profiles(self) -> list[str]:
        """Names of the configured, switchable model profiles."""
        return list(self.profiles)

    def _select(self, profile: str | None) -> LLMProvider | None:
        """Return the provider for a profile name, or ``None`` to use the chain."""
        if profile and profile in self.profiles:
            return self.profiles[profile]
        return None

    # -- construction from settings ----------------------------------------

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMClient":
        """Build a client from :class:`Settings`.

        The primary provider is ``settings.llm_provider``; any *other*
        provider with credentials configured is registered as a fallback.
        """
        # OpenRouter and local backends carry their own model name, so don't
        # force the anthropic/openai LLM_MODEL onto them — that would send a
        # wrong model name and fail.
        primary_model = (None if settings.llm_provider in ("openrouter", "local")
                        else settings.llm_model)
        primary = cls._make_provider(settings, settings.llm_provider, primary_model)

        fallbacks: list[LLMProvider] = []
        for name in PROVIDER_REGISTRY:
            if name == settings.llm_provider:
                continue
            if cls._key_for(settings, name):
                fallbacks.append(cls._make_provider(settings, name))

        return cls(primary, fallbacks,
                profiles=cls._build_profiles(settings))

    @staticmethod
    def _key_for(settings: Settings, name: str) -> str:
        # "local" intentionally returns "" so it is never auto-added to the
        # fallback chain (the server may be offline); it is used only when it is
        # the explicitly selected provider.
        return {
            "anthropic": settings.anthropic_api_key,
            "openai": settings.openai_api_key,
            "openrouter": settings.openrouter_api_key,
        }.get(name, "")

    @staticmethod
    def _build_profiles(settings: Settings) -> dict[str, LLMProvider]:
        """One switchable profile per configured provider/key.

        - ``claude``     — Anthropic (needs ANTHROPIC_API_KEY)
        - ``gpt``        — OpenAI (needs OPENAI_API_KEY)
        - ``openrouter`` — OpenAI-compatible via OpenRouter (OPENROUTER_API_KEY)
        """
        from jarvis.config.constants import DEFAULT_MODELS
        from jarvis.llm.providers.openai_provider import OpenAIProvider
        from jarvis.llm.providers.openrouter_provider import OpenRouterProvider

        profiles: dict[str, LLMProvider] = {}
        if settings.anthropic_api_key:
            profiles["claude"] = PROVIDER_REGISTRY["anthropic"](
                api_key=settings.anthropic_api_key,
                model=DEFAULT_MODELS.get("anthropic", ""),
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
        if settings.openai_api_key:
            profiles["gpt"] = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=DEFAULT_MODELS.get("openai", ""),
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                base_url=settings.openai_base_url,
            )
        if settings.openrouter_api_key:
            profiles["openrouter"] = OpenRouterProvider(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                base_url=settings.openrouter_base_url,
            )
        # Local models become a switchable profile once the user runs on them
        # (or explicitly points at a local endpoint).
        if settings.llm_provider == "local" or settings.local_llm_base_url:
            from jarvis.llm.providers.local_provider import LocalProvider
            profiles["local"] = LocalProvider(
                api_key=settings.local_llm_api_key,
                model=settings.local_llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                base_url=settings.local_llm_base_url,
                backend=settings.local_llm_backend,
            )
        return profiles

    @staticmethod
    def _make_provider(settings: Settings, name: str,
                    model: str | None = None) -> LLMProvider:
        provider_cls = PROVIDER_REGISTRY.get(name)
        if provider_cls is None:
            raise LLMConfigError(f"Unknown LLM provider: {name!r}")

        from jarvis.config.constants import DEFAULT_MODELS
        key = LLMClient._key_for(settings, name)
        if name == "local":
            # Local backends take a preset endpoint + their own model name.
            return provider_cls(
                api_key=settings.local_llm_api_key,
                model=model or settings.local_llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                base_url=settings.local_llm_base_url,
                backend=settings.local_llm_backend,
            )
        if name == "openrouter":
            base_url = settings.openrouter_base_url
            default_model = settings.openrouter_model
        elif name == "openai":
            base_url = settings.openai_base_url
            default_model = DEFAULT_MODELS.get(name, "")
        else:
            base_url = ""
            default_model = DEFAULT_MODELS.get(name, "")
        return provider_cls(
            api_key=key,
            model=model or default_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            base_url=base_url,
        )

    # -- completion ---------------------------------------------------------

    async def complete(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        profile: str | None = None,
        override: LLMProvider | None = None,
    ) -> LLMResult:
        """Complete ``messages``, retrying and falling back as needed.

        ``model`` optionally overrides the provider's default model for this
        call (used by the AI router to pick a tier). ``profile`` pins the call
        to one configured provider (user's chosen AI); it still retries but
        does not fall back to other providers. ``override`` is an explicit
        provider (e.g. a user's own BYOK credentials) used directly.
        """
        if override is not None:
            return await self._complete_with_retry(
                override, messages, system, tools, model)

        selected = self._select(profile)
        if selected is not None:
            return await self._complete_with_retry(
                selected, messages, system, tools, model
            )

        errors: list[str] = []
        for provider in self._chain():
            if not provider.is_available():
                errors.append(f"{provider.name}: no credentials")
                continue
            try:
                return await self._complete_with_retry(
                    provider, messages, system, tools, model
                )
            except LLMError as exc:
                logger.warning("Provider '%s' failed: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
                continue

        raise AllProvidersFailedError(
            "All LLM providers failed or are unconfigured.",
            details={"errors": errors},
        )

    async def _complete_with_retry(
        self,
        provider: LLMProvider,
        messages: list[dict],
        system: str | None,
        tools: list[ToolSpec] | None,
        model: str | None = None,
    ) -> LLMResult:
        @retry_async(attempts=self._retry_attempts, base_delay=1.0, exceptions=(LLMError,))
        async def _call() -> LLMResult:
            return await provider.complete(messages, system, tools, model)

        return await _call()

    # -- streaming ----------------------------------------------------------

    async def stream(
        self,
        messages: list[dict],
        system: str | None = None,
        profile: str | None = None,
        model: str | None = None,
        override: LLMProvider | None = None,
    ) -> AsyncIterator[str]:
        """Stream a completion, falling back before the first chunk only.

        Once a provider has produced its first chunk we are committed to it;
        mid-stream fallback is not possible. ``profile`` pins the stream to one
        configured provider (the user's chosen AI); ``model`` overrides that
        provider's default model (a specific catalog model). ``override`` is an
        explicit provider (BYOK) used directly.
        """
        if override is not None:
            async for chunk in override.stream(messages, system, model):
                yield chunk
            return

        selected = self._select(profile)
        if selected is not None:
            async for chunk in selected.stream(messages, system, model):
                yield chunk
            return

        errors: list[str] = []
        for provider in self._chain():
            if not provider.is_available():
                errors.append(f"{provider.name}: no credentials")
                continue
            agen = provider.stream(messages, system, model)
            try:
                first = await agen.__anext__()
            except StopAsyncIteration:
                return  # empty but successful stream
            except LLMError as exc:
                logger.warning("Provider '%s' stream failed: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
                continue

            yield first
            async for chunk in agen:
                yield chunk
            return

        raise AllProvidersFailedError(
            "All LLM providers failed or are unconfigured.",
            details={"errors": errors},
        )

    # -- tool-loop helpers --------------------------------------------------

    def continuation_messages(
        self,
        result: LLMResult,
        tool_results: list[ToolResult],
    ) -> list[dict]:
        """Format tool-round follow-up messages using the producing provider."""
        provider = self._provider_by_name(result.provider) or self.primary
        return provider.continuation_messages(result, tool_results)

    def provider_for(self, profile: str | None = None,
                    override: LLMProvider | None = None) -> LLMProvider:
        """The provider that :meth:`complete` will use, given the same args.

        Mirrors ``complete``'s own precedence (override > profile > primary)
        so a caller that needs to build a provider-specific message *before*
        calling ``complete`` — e.g. a vision message for screen sharing — asks
        the right provider for its wire format.
        """
        if override is not None:
            return override
        return self._select(profile) or self.primary

    def _provider_by_name(self, name: str) -> LLMProvider | None:
        for provider in self._chain():
            if provider.name == name:
                return provider
        return None

    # -- introspection ------------------------------------------------------

    def _chain(self) -> list[LLMProvider]:
        return [self.primary, *self.fallbacks]

    def available_providers(self) -> list[str]:
        return [p.name for p in self._chain() if p.is_available()]

    def has_any_provider(self) -> bool:
        return bool(self.available_providers())
