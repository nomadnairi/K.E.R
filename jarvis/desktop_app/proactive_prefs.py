"""The desktop app's (single-user) equivalent of a proactive-engine prefs store.

``jarvis.interfaces.user_prefs.UserPreferences`` is SQLite-backed and
multi-user (keyed by Telegram ``chat_id``) -- the wrong shape for "the one
person running this app." ``ProactiveEngine`` only ever calls two methods
(see ``jarvis.proactive.engine.ProactivePrefs``), so a tiny duck-typed
adapter over :class:`~jarvis.desktop_app.config.AppConfig` is all local mode
needs -- no new database.
"""

from __future__ import annotations

import time

from jarvis.desktop_app.config import AppConfig

#: The single local user's id/session id -- matches EngineThread's own
#: default session id ("desktop"), so ProactiveEngine's default identity
#: session_id_for mapping already lands on the right session.
LOCAL_USER_ID = "desktop"


class LocalProactivePrefs:
    """Always reports exactly one opted-in user: whoever is running the app."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def list_proactive(self) -> list[dict]:
        if not self.config.proactive_enabled:
            return []
        return [{
            "user_id": LOCAL_USER_ID,
            "chat_id": LOCAL_USER_ID,
            "language": self.config.language,
            "last_seen": time.time(),
        }]

    def get_assistant_name(self, user_id: int | str) -> str | None:
        return self.config.assistant_name or None
