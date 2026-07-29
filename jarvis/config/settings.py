"""
Centralised, type-safe configuration for J.A.R.V.I.S.

All settings are loaded from environment variables (and an optional `.env`
file) and validated with pydantic. Access them via :func:`get_settings`,
which returns a cached singleton so the environment is parsed only once.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_ids(raw: str) -> set[int]:
    """Parse a comma-separated list of integer IDs, ignoring junk."""
    ids: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


class Settings(BaseSettings):
    """Application settings loaded from the environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM providers ---
    anthropic_api_key: str = Field(default="", description="Anthropic API key.")
    openai_api_key: str = Field(default="", description="OpenAI API key.")

    #: Which provider the core engine uses by default. Each is standalone:
    #: "openai" = the real OpenAI, "openrouter" = OpenRouter (its own key/model).
    llm_provider: Literal[
        "anthropic", "openai", "openrouter", "local"] = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    #: Custom OpenAI-compatible endpoint for the OpenAI provider only. Empty =
    #: the official OpenAI API. (For OpenRouter use the OPENROUTER_* settings.)
    openai_base_url: str = ""
    #: OpenRouter — a fully separate provider. Set these to use OpenRouter as the
    #: engine (LLM_PROVIDER=openrouter) and/or as a switchable model profile.
    openrouter_api_key: str = ""
    #: Default model used by the OpenRouter provider (an OpenRouter model slug).
    openrouter_model: str = "anthropic/claude-3.7-sonnet"
    #: OpenRouter endpoint (rarely changed).
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    #: Local / self-hosted models via an OpenAI-compatible server. Pick a backend
    #: preset (its default URL is used unless LOCAL_LLM_BASE_URL overrides it).
    local_llm_backend: Literal[
        "ollama", "lmstudio", "vllm", "llamacpp", "custom"] = "ollama"
    #: Override the backend's default endpoint (needed for "custom").
    local_llm_base_url: str = ""
    #: Model name to request from the local server (e.g. "llama3", "qwen2.5").
    local_llm_model: str = "llama3"
    #: Most local servers ignore auth; set only if yours requires a token.
    local_llm_api_key: str = ""

    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2048, gt=0)

    # --- AI router (model-tier routing) ---
    #: Route simple turns to a fast model and complex ones to a strong model.
    ai_router_enabled: bool = False
    #: Fast/strong model names (empty → use llm_model). Must match the provider.
    llm_model_fast: str = ""
    llm_model_strong: str = ""
    #: Word count at/above which a turn is routed to the strong model.
    router_word_threshold: int = Field(default=40, gt=0)

    #: Max agentic tool-calling rounds before returning to the user.
    max_tool_rounds: int = Field(default=5, gt=0, le=20)
    #: Max concurrent sessions kept in memory (LRU-evicted beyond this).
    max_sessions: int = Field(default=1000, gt=0)

    # --- Rate limiting (per session) ---
    rate_limit_enabled: bool = True
    rate_limit_capacity: int = Field(default=20, gt=0)
    rate_limit_window_seconds: float = Field(default=60.0, gt=0)

    # --- Assistant persona ---
    #: The assistant's name. Ships as "KER" but is white-label: each user can
    #: rename their assistant, and operators can override the default here.
    assistant_name: str = "KER"
    #: Extra names the assistant also answers to (comma-separated), e.g. a
    #: personal wake-word alias. Left blank in the shipping default so resold
    #: copies carry no third-party name; set e.g. "Jarvis" for a personal build.
    assistant_aliases: str = ""
    user_name: str = "Sir"

    def alias_list(self) -> list[str]:
        """The assistant's extra address names, parsed and de-duplicated."""
        seen: list[str] = []
        for raw in self.assistant_aliases.split(","):
            name = raw.strip()
            if name and name.lower() != self.assistant_name.lower() \
                    and name not in seen:
                seen.append(name)
        return seen

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_file: str = "logs/jarvis.log"

    # --- Storage ---
    database_url: str = "sqlite:///data/jarvis.db"
    redis_url: str = "redis://localhost:6379/0"
    vector_store_path: str = "chroma_db"

    # --- Memory ---
    memory_enabled: bool = True
    #: Vector backend: "sqlite" (default, persistent) | "memory" | "chroma".
    memory_backend: Literal["sqlite", "memory", "chroma"] = "sqlite"
    #: Embedding backend: "hashing" (offline) | "local" (semantic) | "openai".
    embedding_backend: Literal["hashing", "local", "openai"] = "hashing"
    #: Local (fastembed) embedding model when embedding_backend="local".
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"
    #: How many memories to recall and inject into the prompt per turn.
    memory_recall_limit: int = Field(default=4, ge=0, le=20)
    #: Minimum cosine similarity for a memory to be recalled.
    memory_min_score: float = Field(default=0.15, ge=0.0, le=1.0)
    #: Weight of recency vs. similarity in recall scoring (0..1).
    memory_recency_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    #: Extract durable facts via the LLM instead of storing raw transcripts.
    memory_fact_extraction: bool = True
    #: Max semantic memories kept per session (0 = unlimited); oldest evicted.
    memory_max_per_session: int = Field(default=200, ge=0)
    #: Skip storing a new memory this similar to an existing one (0/1 = off).
    memory_dedup_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    #: Redact secrets (tokens, keys, card numbers) before storing memory.
    memory_redact_secrets: bool = True
    #: SQLite file for persistent conversation history and vectors.
    memory_db_path: str = "data/jarvis.db"
    #: JSON file backing the "memory" vector backend (when selected).
    memory_vector_path: str = "data/memory.json"

    # --- Voice (pluggable STT / TTS) ---
    #: Enable voice messages in the Telegram bot.
    voice_enabled: bool = True
    #: Speech-to-text backend: "openai" (Whisper API, paid) or
    #: "local" (open-source Whisper, free/offline, needs openai-whisper).
    stt_backend: Literal["openai", "local"] = "openai"
    #: Text-to-speech backend: "openai" (paid), "edge" (free, edge-tts),
    #: or "gtts" (free, gTTS).
    tts_backend: Literal["openai", "edge", "gtts"] = "openai"
    #: OpenAI STT/TTS model + voice (when the OpenAI backend is selected).
    stt_model: str = "whisper-1"
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"
    #: Local Whisper model size (tiny | base | small | medium | large).
    local_whisper_model: str = "base"
    #: Whether the bot also replies with a spoken (TTS) voice/audio message.
    voice_replies: bool = True

    # --- Security (dangerous capabilities are OFF by default) ---
    #: Root directory file/coding tools are sandboxed to.
    workspace_root: str = "."
    allow_file_read: bool = True
    allow_file_write: bool = False
    allow_shell: bool = False
    allow_desktop_control: bool = False
    #: Ask before each use of a capability that is otherwise allowed. This is
    #: the middle ground between refusing a power outright and handing it over:
    #: the assistant may use it, but every single time it stops and asks. Has
    #: no effect on a capability that is switched off.
    confirm_file_read: bool = False
    confirm_file_write: bool = False
    confirm_shell: bool = False
    confirm_desktop_control: bool = False
    #: Speak the question aloud and accept a spoken yes/no (needs voice).
    confirm_by_voice: bool = False
    #: How long to wait for an answer before refusing, in seconds.
    confirm_timeout_seconds: float = Field(default=60.0, gt=1.0, le=600.0)
    #: Audit log file for dangerous-capability attempts ("" disables it).
    audit_log_path: str = "logs/audit.log"

    # --- Files & coding ---
    #: Expose sandboxed file tools (read on; write gated by security).
    files_enabled: bool = True
    #: Expose coding tools (run command/tests; shell gated by security).
    coding_enabled: bool = True
    #: Command used by the run_tests tool.
    test_command: str = "pytest -q"
    #: Timeout (seconds) for shell commands.
    shell_timeout: float = 60.0
    #: Expose desktop-control tools (gated by allow_desktop_control).
    desktop_enabled: bool = True

    # --- Agents ---
    #: Expose the run_agent tool (delegate multi-step tasks to a sub-agent).
    agents_enabled: bool = True
    #: Max steps an autonomous sub-agent may take.
    max_agent_steps: int = Field(default=8, gt=0, le=30)

    # --- Goals ---
    #: Track goals/tasks and surface open ones to the assistant.
    goals_enabled: bool = True

    # --- Integrations ---
    #: Master switch for the integrations subsystem.
    integrations_enabled: bool = True
    #: Weather integration (Open-Meteo, free, no key).
    weather_enabled: bool = True
    #: City shown on the dashboard's weather panel (empty = no live weather).
    weather_city: str = ""
    #: Home Assistant (smart home) — both are required to enable it.
    homeassistant_url: str = ""
    homeassistant_token: str = ""

    # --- Updates ---
    #: Repository that releases are published to (owner/name).
    update_repo: str = "nomadnairi/K.E.R"
    #: Which release channel to track: "early" includes pre-releases (grey
    #: access), "stable" only full releases, "off" disables update checks.
    update_channel: Literal["early", "stable", "off"] = "early"
    #: Optional Telegram channel to point users at for update announcements.
    update_telegram_channel: str = ""

    # --- MCP (Model Context Protocol) — mount external agent skills as tools ---
    #: Connect to MCP servers (the agentskills.io / Hermes / Claude standard) and
    #: expose their tools as J.A.R.V.I.S. skills the model can call.
    mcp_enabled: bool = False
    #: Path to a JSON file with the standard {"mcpServers": {...}} shape.
    mcp_config_path: str = ""
    #: Inline JSON alternative to the file (same shape). Handy for env-only setups.
    mcp_servers: str = ""

    # --- API server ---
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, gt=0, le=65535)
    #: Bearer / X-API-Key required to call the API (empty = open, dev only).
    api_key: str = ""
    #: Browser origins allowed to call the API (comma-separated, "*" = any).
    #: The interfaces are pages, and a page always sits on a different origin
    #: than the API it talks to — the desktop app's own window included — so
    #: without this the browser blocks every request. Calls still need a key;
    #: narrow this when the API faces the internet.
    api_cors_origins: str = "*"

    # --- Accounts & licensing (per-user login for exe/apk clients) ---
    #: Enable username/password accounts + license checks on the API.
    #: When off, the API falls back to the shared ``api_key`` only.
    auth_enabled: bool = False
    #: SQLite file holding accounts, licenses, tokens and pairings.
    auth_db_path: str = "data/auth.db"
    #: Admin key required to create accounts / issue licenses (empty = disabled).
    auth_admin_key: str = ""
    #: Lifetime of an issued login token, in hours.
    auth_token_ttl_hours: int = Field(default=720, gt=0)
    #: Require a linked+verified Telegram account before login succeeds.
    auth_require_telegram: bool = False

    # --- Billing (payments → automatic license issuance) ---
    #: Enable the /buy flow in the bot and the /billing/webhook endpoint.
    billing_enabled: bool = False
    #: Price of a license in Telegram Stars (XTR).
    billing_price_stars: int = Field(default=2500, gt=0)
    #: Plan name written on issued licenses.
    billing_plan: str = "standard"
    #: License validity in days (0 = perpetual).
    billing_plan_days: int = Field(default=365, ge=0)
    #: HMAC-SHA256 secret for POST /billing/webhook (empty = webhook disabled).
    billing_webhook_secret: str = ""

    # --- Plans / tiers (Free / Plus / Pro) ---
    #: Daily message allowance per tier (0 = unlimited). Free is deliberately
    #: tight; Plus is generous; Pro is unlimited.
    plan_free_daily: int = Field(default=10, ge=0)
    plan_plus_daily: int = Field(default=100, ge=0)
    plan_pro_daily: int = Field(default=0, ge=0)
    #: Telegram Stars price shown on the Plus / Pro upgrade cards.
    plan_plus_price_stars: int = Field(default=2500, gt=0)
    plan_pro_price_stars: int = Field(default=8000, gt=0)

    # --- Image generation (Plus/Pro feature) ---
    #: Enable the bot's image mode (needs an OpenAI-compatible Images API key).
    image_enabled: bool = False
    #: Image model, size, and optional dedicated key/endpoint. The key/endpoint
    #: fall back to the OpenAI ones when left blank.
    image_model: str = "dall-e-3"
    image_size: str = "1024x1024"
    image_api_key: str = ""
    image_base_url: str = ""

    # --- Referrals ---
    #: Extra daily messages granted per successful referral (0 disables the
    #: referral program's reward, but invite links still work).
    referral_bonus_daily: int = Field(default=20, ge=0)

    # --- Web / AI search (Search Manager) ---
    #: Enable the search service (the AI never hits the internet directly).
    #: On by default — the keyless DuckDuckGo backend works with no API key;
    #: add a provider key for higher-quality results.
    search_enabled: bool = True
    #: Preferred provider: "auto" picks the first available by priority.
    search_provider: str = "auto"
    #: Provider API keys (each empty = that provider is unavailable).
    tavily_api_key: str = ""
    exa_api_key: str = ""
    brave_api_key: str = ""
    perplexity_api_key: str = ""
    serpapi_key: str = ""
    google_cse_key: str = ""
    google_cse_cx: str = ""

    # --- Proactive messaging (the bot reaches out first) ---
    #: Hour (server local time, 0-23) for the opt-in morning check-in.
    proactive_morning_hour: int = Field(default=9, ge=0, le=23)
    #: Nudge users who've been quiet for at least this many days (0 disables).
    proactive_idle_days: int = Field(default=3, ge=0)

    # --- Telegram bot ---
    telegram_bot_token: str = Field(default="", description="Bot token from @BotFather.")
    #: Optional comma-separated allowlist of Telegram user IDs (empty = open).
    telegram_allowed_users: str = ""
    #: Comma-separated Telegram user IDs with access to the bot's admin panel.
    telegram_admin_users: str = ""
    #: Comma-separated Telegram user IDs treated as Pro (unlimited, all features)
    #: with no licence or key needed — for close people / a ready-to-use gift bot.
    telegram_vip_users: str = ""
    #: Allow the assistant to SEND Telegram messages/posts as a tool (outbound).
    telegram_send_enabled: bool = False
    #: Default channel (@channelusername or chat id) for the telegram_post tool.
    telegram_channel: str = ""
    #: If set (e.g. "@jar_v1_s"), users must join this channel before they can
    #: use the bot — a subscription gate checked on every interaction.
    telegram_required_channel: str = ""

    def telegram_allowlist(self) -> set[int]:
        """Parsed set of allowed Telegram user IDs (empty = everyone)."""
        ids: set[int] = set()
        for part in self.telegram_allowed_users.split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
        return ids

    def telegram_admins(self) -> set[int]:
        """Parsed set of Telegram user IDs allowed to use the admin panel."""
        return _parse_ids(self.telegram_admin_users)

    def telegram_vips(self) -> set[int]:
        """Parsed set of VIP Telegram user IDs (always Pro, no setup needed)."""
        return _parse_ids(self.telegram_vip_users)

    def active_api_key(self) -> str:
        """Return the API key for the currently selected provider.

        Local backends need no cloud key, so a placeholder is returned to mark
        them as "credentialed" (see :meth:`has_llm_credentials`).
        """
        return {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "openrouter": self.openrouter_api_key,
            "local": self.local_llm_api_key or "local",
        }.get(self.llm_provider, "")

    def has_llm_credentials(self) -> bool:
        """Whether the active provider is usable (key set, or a local model)."""
        if self.llm_provider == "local":
            return bool(self.local_llm_model)
        return bool(self.active_api_key())


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
