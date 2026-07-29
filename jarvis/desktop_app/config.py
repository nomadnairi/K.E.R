"""
Per-user configuration for the desktop app.

Stored as JSON in the OS-appropriate user config directory
(``%APPDATA%/JARVIS`` on Windows, ``~/.config/jarvis`` elsewhere) — NOT in the
project tree, so a packaged .exe works from anywhere. Secrets (LLM keys, the
login token) live here with file permissions restricted to the current user.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def default_config_dir() -> Path:
    """OS-appropriate per-user config directory."""
    if sys.platform == "win32":  # pragma: no cover - platform specific
        base = os.environ.get("APPDATA", str(Path.home()))
        return Path(base) / "JARVIS"
    return Path(os.environ.get("XDG_CONFIG_HOME",
                            str(Path.home() / ".config"))) / "jarvis"


@dataclass
class AppConfig:
    """Desktop app settings persisted between runs."""

    #: UI + assistant language: en | ru | uz.
    language: str = "en"
    #: Visual theme key (see jarvis.desktop_app.theme.THEMES).
    theme: str = "obsidian"
    #: What this copy calls its assistant. Blank = whatever the engine ships
    #: with, so a renamed build stays renamed without editing the app.
    assistant_name: str = ""

    # -- desktop behaviour ----------------------------------------------------
    #: Hide to the system tray on close instead of quitting.
    minimize_to_tray: bool = True
    #: Launch J.A.R.V.I.S. when the operating system starts.
    start_on_boot: bool = False
    #: Show a desktop notification when a reply arrives while hidden.
    notifications: bool = True
    #: Set once the first-run onboarding has been shown.
    onboarded: bool = False
    #: Check GitHub for updates on launch and open the download automatically.
    auto_update: bool = False
    #: "early" (include pre-releases) or "stable" (full releases only).
    update_channel: str = "early"
    #: "local" (engine runs on this PC) or "remote" (talk to a server API).
    mode: str = "local"
    #: "admin" (owner — full app) or "user" (signed-in guest — limited UI).
    role: str = "admin"
    #: Set once the user has picked how they get in, so the sign-in screen is
    #: not put in front of a local owner on every launch.
    mode_chosen: bool = False

    # -- account --------------------------------------------------------------
    server_url: str = ""
    #: Login token from /auth/login (stored so you stay signed in).
    auth_token: str = ""
    username: str = ""

    # -- subscription (cached from the server) --------------------------------
    # Kept on disk so the app still opens, and still knows what it may show,
    # when the server cannot be reached. Refreshed on every successful start.
    #: free | plus | pro
    plan_tier: str = "free"
    #: Capability names unlocked by that tier (see jarvis.billing.entitlements).
    plan_features: list = field(default_factory=list)
    #: The operator's own account — everything unlocked, nothing counted.
    is_owner: bool = False
    #: When the plan was last confirmed by the server (unix seconds).
    plan_checked_at: float = 0.0

    # -- local mode: LLM ------------------------------------------------------
    llm_provider: str = "anthropic"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    #: Local model server (Ollama, LM Studio, vLLM, llama.cpp) — no cloud key.
    local_llm_base_url: str = ""
    local_llm_api_key: str = ""

    # -- local mode: granular PC capabilities (all dangerous ones OFF) --------
    allow_file_read: bool = True
    allow_file_write: bool = False
    allow_shell: bool = False
    allow_desktop_control: bool = False
    #: Ask before each use of a capability that is otherwise allowed.
    confirm_file_read: bool = False
    confirm_file_write: bool = False
    confirm_shell: bool = False
    confirm_desktop_control: bool = False
    #: Speak the question and accept a spoken answer.
    confirm_by_voice: bool = False
    workspace_root: str = ""

    # -- web search -----------------------------------------------------------
    search_enabled: bool = True
    #: "auto" picks the best available provider by priority.
    search_provider: str = "auto"
    tavily_api_key: str = ""
    exa_api_key: str = ""
    brave_api_key: str = ""
    perplexity_api_key: str = ""
    serpapi_key: str = ""

    # -- integrations ---------------------------------------------------------
    weather_enabled: bool = True
    homeassistant_url: str = ""
    homeassistant_token: str = ""
    telegram_bot_token: str = ""
    telegram_send_enabled: bool = False
    telegram_channel: str = ""

    # -- voice ----------------------------------------------------------------
    voice_enabled: bool = False
    stt_backend: str = "openai"
    tts_backend: str = "openai"
    tts_voice: str = "alloy"
    local_whisper_model: str = "base"
    voice_replies: bool = True

    extra: dict = field(default_factory=dict)

    # -- persistence ----------------------------------------------------------

    @classmethod
    def path(cls, config_dir: Path | None = None) -> Path:
        return (config_dir or default_config_dir()) / "desktop.json"

    @classmethod
    def load(cls, config_dir: Path | None = None) -> "AppConfig":
        path = cls.path(config_dir)
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)

    def save(self, config_dir: Path | None = None) -> Path:
        path = self.path(config_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        try:  # restrict to the current user (no-op on Windows ACLs)
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:  # pragma: no cover - platform specific
            pass
        return path

    # -- where the engine runs ------------------------------------------------

    def may_run_locally(self) -> bool:
        """Whether this account is entitled to an engine on this machine.

        Local powers — files, shell, a local model, MCP — only exist where the
        engine runs, and an engine needs a model to talk to. Tiers without those
        capabilities use the operator's server instead, which is also where
        their allowance is counted.
        """
        from jarvis.billing.entitlements import LOCAL_AI, PC_ACCESS
        entitled = self.is_owner or bool(
            {PC_ACCESS, LOCAL_AI} & set(self.plan_features))
        has_brain = bool(self.anthropic_api_key or self.openai_api_key
                        or self.openrouter_api_key or self.local_llm_base_url)
        return entitled and has_brain

    def resolved_mode(self) -> str:
        """"local" when the engine runs here, "remote" when it is the server's."""
        return "local" if self.may_run_locally() else "remote"

    def has(self, feature: str) -> bool:
        """Whether the account's plan includes ``feature``."""
        return self.is_owner or feature in self.plan_features

    # -- engine bridge --------------------------------------------------------

    def to_settings_overrides(self) -> dict:
        """Map app config onto :class:`jarvis.config.settings.Settings` fields."""
        overrides: dict = {
            "llm_provider": self.llm_provider,
            "anthropic_api_key": self.anthropic_api_key,
            "openai_api_key": self.openai_api_key,
            "openrouter_api_key": self.openrouter_api_key,
            "local_llm_api_key": self.local_llm_api_key,
            "allow_file_read": self.allow_file_read,
            "allow_file_write": self.allow_file_write,
            "allow_shell": self.allow_shell,
            "allow_desktop_control": self.allow_desktop_control,
            "confirm_file_read": self.confirm_file_read,
            "confirm_file_write": self.confirm_file_write,
            "confirm_shell": self.confirm_shell,
            "confirm_desktop_control": self.confirm_desktop_control,
            "confirm_by_voice": self.confirm_by_voice,
            "search_enabled": self.search_enabled,
            "search_provider": self.search_provider,
            "tavily_api_key": self.tavily_api_key,
            "exa_api_key": self.exa_api_key,
            "brave_api_key": self.brave_api_key,
            "perplexity_api_key": self.perplexity_api_key,
            "serpapi_key": self.serpapi_key,
            "weather_enabled": self.weather_enabled,
            "homeassistant_url": self.homeassistant_url,
            "homeassistant_token": self.homeassistant_token,
            "telegram_bot_token": self.telegram_bot_token,
            "telegram_send_enabled": self.telegram_send_enabled,
            "telegram_channel": self.telegram_channel,
            "voice_enabled": self.voice_enabled,
            "stt_backend": self.stt_backend,
            "tts_backend": self.tts_backend,
            "tts_voice": self.tts_voice,
            "local_whisper_model": self.local_whisper_model,
            "voice_replies": self.voice_replies,
        }
        if self.assistant_name:
            overrides["assistant_name"] = self.assistant_name
        if self.llm_model:
            # Each provider reads its own model field, so point the right one
            # at what the user typed.
            key = {"openrouter": "openrouter_model",
                "local": "local_llm_model"}.get(self.llm_provider,
                                                    "llm_model")
            overrides[key] = self.llm_model
        if self.local_llm_base_url:
            overrides["local_llm_base_url"] = self.local_llm_base_url
        if self.workspace_root:
            overrides["workspace_root"] = self.workspace_root
        return overrides
