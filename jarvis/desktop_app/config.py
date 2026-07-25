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

    # -- remote mode ----------------------------------------------------------
    server_url: str = ""
    #: Login token from /auth/login (stored so you stay signed in).
    auth_token: str = ""
    username: str = ""

    # -- local mode: LLM ------------------------------------------------------
    llm_provider: str = "anthropic"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # -- local mode: granular PC capabilities (all dangerous ones OFF) --------
    allow_file_read: bool = True
    allow_file_write: bool = False
    allow_shell: bool = False
    allow_desktop_control: bool = False
    workspace_root: str = ""

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

    # -- engine bridge --------------------------------------------------------

    def to_settings_overrides(self) -> dict:
        """Map app config onto :class:`jarvis.config.settings.Settings` fields."""
        overrides: dict = {
            "llm_provider": self.llm_provider,
            "anthropic_api_key": self.anthropic_api_key,
            "openai_api_key": self.openai_api_key,
            "allow_file_read": self.allow_file_read,
            "allow_file_write": self.allow_file_write,
            "allow_shell": self.allow_shell,
            "allow_desktop_control": self.allow_desktop_control,
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
        if self.llm_model:
            overrides["llm_model"] = self.llm_model
        if self.workspace_root:
            overrides["workspace_root"] = self.workspace_root
        return overrides
