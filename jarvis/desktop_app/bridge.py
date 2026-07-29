"""
Native actions for the desktop app's embedded interface.

The desktop app *is* an HTML interface in a web view, so anything the page
cannot do on its own — sign in, write the config file, read the log, flip
autostart — is asked for here. A request is an action name plus a payload; the
answer is a plain dict. Deliberately free of Qt, so the whole native surface of
the interface is testable without a display.

The page only gets to touch fields listed in :data:`WRITABLE`; anything else it
sends is ignored, and values are coerced and range-checked on the way in. Secret
fields never travel back to the page — the snapshot reports whether a key is set,
not what it is, and an empty secret on save means "leave it alone".
"""

from __future__ import annotations

import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from jarvis.desktop_app.api_client import ApiError, JarvisApiClient
from jarvis.desktop_app.config import AppConfig
from jarvis.desktop_app.theme import THEMES

logger = logging.getLogger(__name__)

#: Values a field is allowed to take. Anything else is refused, so a typo in
#: the page cannot put the app into a state it cannot start from. Themes are
#: read from the palette table itself, so the two can never drift apart.
CHOICES: dict[str, tuple[str, ...]] = {
    "language": ("en", "ru", "uz"),
    "theme": tuple(THEMES),
    "llm_provider": ("anthropic", "openai", "openrouter", "local"),
    # "auto" lets the engine pick the best key you actually have.
    "search_provider": ("auto", "duckduckgo", "tavily", "exa", "brave",
                        "google", "serpapi", "perplexity", "playwright"),
    "update_channel": ("early", "stable"),
    # Kept in step with jarvis.config.settings, which only accepts these.
    "stt_backend": ("openai", "local"),
    "tts_backend": ("openai", "edge", "gtts"),
}

#: Config fields the interface may write, with the type each is coerced to.
WRITABLE: dict[str, type] = {
    # interface
    "language": str,
    "theme": str,
    "notifications": bool,
    "minimize_to_tray": bool,
    "start_on_boot": bool,
    # assistant
    "assistant_name": str,
    # AI — one field per provider the engine can actually talk to
    "llm_provider": str,
    "llm_model": str,
    "anthropic_api_key": str,
    "openai_api_key": str,
    "openrouter_api_key": str,
    "local_llm_base_url": str,
    "local_llm_api_key": str,
    # capabilities: allowed at all, and whether each use is confirmed first
    "allow_file_read": bool,
    "allow_file_write": bool,
    "allow_shell": bool,
    "allow_desktop_control": bool,
    "confirm_file_read": bool,
    "confirm_file_write": bool,
    "confirm_shell": bool,
    "confirm_desktop_control": bool,
    "confirm_by_voice": bool,
    "workspace_root": str,
    # web search
    "search_enabled": bool,
    "search_provider": str,
    "tavily_api_key": str,
    "exa_api_key": str,
    "brave_api_key": str,
    "perplexity_api_key": str,
    "serpapi_key": str,
    # voice
    "voice_enabled": bool,
    "voice_replies": bool,
    "stt_backend": str,
    "tts_backend": str,
    "tts_voice": str,
    # integrations
    "weather_enabled": bool,
    "homeassistant_url": str,
    "homeassistant_token": str,
    "telegram_bot_token": str,
    "telegram_send_enabled": bool,
    "telegram_channel": str,
    # updates
    "auto_update": bool,
    "update_channel": str,
}

#: Fields whose value must never be handed back to the page.
SECRETS = ("anthropic_api_key", "openai_api_key", "openrouter_api_key",
           "local_llm_api_key", "homeassistant_token", "telegram_bot_token",
           "tavily_api_key", "exa_api_key", "brave_api_key",
           "perplexity_api_key", "serpapi_key", "auth_token")

#: Where the app looks for its log, most interesting first.
LOG_CANDIDATES = ("logs/jarvis.log", "logs/audit.log")


def adopt_profile(config: AppConfig, client: JarvisApiClient, *,
                  config_dir: Path | None = None) -> dict:
    """Store what the server says this account is, and what it may do.

    Cached on disk on purpose: the app must still know what to show when the
    server cannot be reached, and a slightly stale plan beats an empty window.
    Ownership, role and where the engine runs are all derived from the server's
    answer — never guessed by the interface.
    """
    import time
    try:
        profile = client.me()
    except Exception as exc:  # noqa: BLE001 - keep whatever was cached
        logger.warning("Could not refresh the plan: %s", exc)
        return {}
    config.plan_tier = str(profile.get("tier") or "free")
    config.plan_features = list(profile.get("features") or [])
    config.is_owner = bool(profile.get("owner"))
    # The owner runs the deployment; everyone else is a signed-in user.
    config.role = "admin" if config.is_owner else "user"
    config.plan_checked_at = time.time()
    if profile.get("username"):
        config.username = str(profile["username"])
    config.mode = config.resolved_mode()
    config.save(config_dir)
    return profile


def _as_bool(value: Any) -> bool:
    """Read a checkbox the way the page might send it."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "on", "yes")
    return bool(value)


class Bridge:
    """Runs the native half of an interface action.

    ``on_change`` is called with the set of field names a save actually
    changed, so the app can restyle itself, restart the engine, or update the
    autostart entry — the bridge itself stays free of that machinery.
    """

    def __init__(self, config: AppConfig, *,
                 client_factory: Callable[..., JarvisApiClient] = JarvisApiClient,
                 on_change: Callable[[set[str]], None] | None = None,
                 config_dir: Path | None = None,
                 log_root: Path | None = None) -> None:
        self.config = config
        self._client_factory = client_factory
        self._on_change = on_change
        self._config_dir = config_dir
        self._log_root = log_root or Path()
        #: Set once a login action succeeds — the app reads it to go on.
        self.client: JarvisApiClient | None = None
        self.signed_in = False

    def set_on_change(self,
                      callback: Callable[[set[str]], None] | None) -> None:
        """Set who hears about saved changes (the app, once it can act on them)."""
        self._on_change = callback

    # -- dispatch -------------------------------------------------------------

    def handle(self, action: str, payload: dict | None = None) -> dict:
        """Run ``action`` and return a JSON-ready result."""
        payload = payload or {}
        handler = getattr(self, "_do_" + action.replace(".", "_"), None)
        if handler is None:
            return {"ok": False, "error": f"Unknown action: {action}"}
        try:
            return handler(payload)
        except ApiError as exc:
            return {"ok": False, "error": exc.detail}
        except Exception as exc:  # noqa: BLE001 - the page shows the message
            logger.warning("Bridge action %s failed: %s", action, exc)
            return {"ok": False, "error": str(exc)}

    # -- signing in -----------------------------------------------------------

    def _do_login_password(self, payload: dict) -> dict:
        server = str(payload.get("server", "")).strip()
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        if not server or not username or not password:
            return {"ok": False, "error": "Fill in server, username and password."}
        client = self._client_factory(server)
        client.login(username, password)
        return self._remember(client, username=username)

    def _do_login_telegram(self, payload: dict) -> dict:
        server = str(payload.get("server", "")).strip()
        code = str(payload.get("code", "")).strip()
        if not server or not code:
            return {"ok": False, "error": "Enter the server and the login code."}
        client = self._client_factory(server)
        client.login_with_telegram_code(code)
        return self._remember(client)

    def _remember(self, client: JarvisApiClient, *, username: str = "") -> dict:
        """Store a successful sign-in, along with what the account may do."""
        self.config.server_url = client.base_url
        self.config.auth_token = client.token
        self.config.mode_chosen = True
        if username:
            self.config.username = username
        self.client = client
        profile = self.refresh_plan(client)
        self.config.save(self._config_dir)
        self.signed_in = True
        return {"ok": True, "username": self.config.username,
                "tier": self.config.plan_tier, "owner": self.config.is_owner,
                "features": list(self.config.plan_features),
                "profile": profile}

    # -- what this account may do ---------------------------------------------

    def refresh_plan(self, client: JarvisApiClient | None = None) -> dict:
        """Ask the server for the account's tier and capabilities."""
        client = client or self.client
        if client is None:
            return {}
        return adopt_profile(self.config, client, config_dir=self._config_dir)

    def _do_plan_get(self, payload: dict) -> dict:
        """The account's plan — refreshed when asked, cached when offline."""
        profile: dict = {}
        if payload.get("refresh", True):
            profile = self.refresh_plan()
        return {
            "ok": True,
            "tier": self.config.plan_tier,
            "owner": self.config.is_owner,
            "features": list(self.config.plan_features),
            "username": self.config.username,
            "checked_at": self.config.plan_checked_at,
            "live": bool(profile),      # False = showing the cached answer
            "profile": profile,
        }

    # -- settings -------------------------------------------------------------

    def snapshot(self) -> dict:
        """The config as the interface should see it — no secrets in it."""
        data = {k: v for k, v in asdict(self.config).items()
                if k in WRITABLE or k in ("mode", "role", "username",
                                          "server_url", "onboarded")}
        for field in SECRETS:
            if field in data:
                data[field] = ""
            data[field + "_set"] = bool(getattr(self.config, field, ""))
        return data

    def _do_settings_get(self, _payload: dict) -> dict:
        from jarvis import __version__
        from jarvis.desktop_app.theme import theme_names
        return {"ok": True, "settings": self.snapshot(),
                "version": __version__,
                "platform": sys.platform,
                "themes": [{"key": k, "label": label}
                           for k, label in theme_names()],
                "config_path": str(AppConfig.path(self._config_dir))}

    def _do_settings_save(self, payload: dict) -> dict:
        """Write the fields the page sent, then report what actually changed."""
        values = payload.get("settings")
        if not isinstance(values, dict):
            values = payload
        changed: set[str] = set()
        rejected: list[str] = []
        for name, raw in values.items():
            if name not in WRITABLE:
                continue                      # not the page's business
            kind = WRITABLE[name]
            value: Any
            if kind is bool:
                value = _as_bool(raw)
            else:
                value = str(raw if raw is not None else "").strip()
                if name in SECRETS and value == "":
                    continue                  # blank secret = keep the old one
                allowed = CHOICES.get(name)
                if allowed and value not in allowed:
                    rejected.append(name)
                    continue
            if getattr(self.config, name) != value:
                setattr(self.config, name, value)
                changed.add(name)
        if changed:
            self.config.save(self._config_dir)
            if self._on_change is not None:
                try:
                    self._on_change(changed)
                except Exception as exc:  # noqa: BLE001 - saving still worked
                    logger.warning("Post-save hook failed: %s", exc)
        out = {"ok": True, "changed": sorted(changed),
               "settings": self.snapshot()}
        if rejected:
            out["rejected"] = sorted(rejected)
        return out

    def _do_settings_reset(self, _payload: dict) -> dict:
        """Back to defaults, keeping the sign-in so the app stays usable."""
        fresh = AppConfig()
        for name in WRITABLE:
            setattr(self.config, name, getattr(fresh, name))
        self.config.save(self._config_dir)
        if self._on_change is not None:
            self._on_change(set(WRITABLE))
        return {"ok": True, "settings": self.snapshot()}

    # -- autostart ------------------------------------------------------------

    def _do_autostart_get(self, _payload: dict) -> dict:
        from jarvis.desktop_app import autostart
        return {"ok": True, "enabled": autostart.is_enabled()}

    def _do_autostart_set(self, payload: dict) -> dict:
        from jarvis.desktop_app import autostart
        enabled = _as_bool(payload.get("enabled"))
        autostart.set_enabled(enabled, f'"{sys.executable}"')
        self.config.start_on_boot = enabled
        self.config.save(self._config_dir)
        return {"ok": True, "enabled": enabled}

    # -- logs -----------------------------------------------------------------

    def _do_logs_tail(self, payload: dict) -> dict:
        """The real log file, last N lines — no invented entries."""
        try:
            lines = int(payload.get("lines", 300))
        except (TypeError, ValueError):
            lines = 300
        lines = max(20, min(lines, 2000))
        for candidate in LOG_CANDIDATES:
            path = self._log_root / candidate
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                tail = text.splitlines()[-lines:]
                return {"ok": True, "path": str(path), "lines": tail}
        return {"ok": True, "path": "", "lines": []}
