"""The native half of the desktop interface.

Everything the interface can ask the app to do goes through
:class:`jarvis.desktop_app.bridge.Bridge`, so these tests are the contract for
signing in, saving settings and reading the log — no Qt, no display needed.
"""

from __future__ import annotations

import pytest

from jarvis.desktop_app.api_client import ApiError
from jarvis.desktop_app.bridge import Bridge
from jarvis.desktop_app.config import AppConfig


class FakeClient:
    """Stands in for a server: records the calls, hands back a token."""

    def __init__(self, base_url: str, *, token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.calls: list[tuple] = []

    def login(self, username: str, password: str) -> str:
        self.calls.append(("login", username, password))
        if password == "wrong":
            raise ApiError(401, "Bad credentials")
        self.token = "token-123"
        return self.token

    def login_with_telegram_code(self, code: str) -> str:
        self.calls.append(("telegram", code))
        if code == "000000":
            raise ApiError(400, "Code expired")
        self.token = "token-tg"
        return self.token


@pytest.fixture()
def bridge(tmp_path):
    config = AppConfig()
    return Bridge(config, client_factory=FakeClient, config_dir=tmp_path,
                  log_root=tmp_path)


# -- dispatch ---------------------------------------------------------------

def test_unknown_action_is_refused(bridge):
    out = bridge.handle("settings.destroy_everything")
    assert out["ok"] is False
    assert "Unknown action" in out["error"]


# -- signing in -------------------------------------------------------------

def test_local_mode_makes_this_machine_the_owner(bridge, tmp_path):
    out = bridge.handle("login.local")
    assert out == {"ok": True, "mode": "local", "role": "admin"}
    assert bridge.signed_in is True
    saved = AppConfig.load(tmp_path)
    assert (saved.mode, saved.role, saved.mode_chosen) == ("local", "admin", True)


def test_password_sign_in_stores_the_token(bridge, tmp_path):
    out = bridge.handle("login.password", {"server": "http://localhost:8000",
                                           "username": "ann",
                                           "password": "secret"})
    assert out["ok"] is True and out["role"] == "user"
    saved = AppConfig.load(tmp_path)
    assert saved.auth_token == "token-123"
    assert saved.username == "ann"
    assert saved.mode == "remote"


def test_password_sign_in_reports_the_server_error(bridge):
    out = bridge.handle("login.password", {"server": "http://localhost:8000",
                                           "username": "ann",
                                           "password": "wrong"})
    assert out == {"ok": False, "error": "Bad credentials"}
    assert bridge.signed_in is False


def test_sign_in_needs_all_three_fields(bridge):
    out = bridge.handle("login.password", {"server": "", "username": "",
                                           "password": ""})
    assert out["ok"] is False
    assert bridge.signed_in is False


def test_telegram_code_signs_in(bridge, tmp_path):
    out = bridge.handle("login.telegram", {"server": "http://localhost:8000",
                                           "code": "123456"})
    assert out["ok"] is True
    assert AppConfig.load(tmp_path).auth_token == "token-tg"


def test_expired_telegram_code_is_reported(bridge):
    out = bridge.handle("login.telegram", {"server": "http://localhost:8000",
                                           "code": "000000"})
    assert out == {"ok": False, "error": "Code expired"}


# -- settings ---------------------------------------------------------------

def test_snapshot_never_carries_secrets_to_the_page(bridge):
    bridge.config.anthropic_api_key = "sk-ant-real-key"
    out = bridge.handle("settings.get")
    assert out["ok"] is True
    settings = out["settings"]
    assert settings["anthropic_api_key"] == ""
    assert settings["anthropic_api_key_set"] is True
    assert "sk-ant-real-key" not in str(out)


def test_settings_get_describes_the_build(bridge):
    out = bridge.handle("settings.get")
    assert out["version"]
    assert any(t["key"] == "obsidian" for t in out["themes"])
    assert out["config_path"].endswith("desktop.json")


def test_saving_a_setting_writes_it_to_disk(bridge, tmp_path):
    out = bridge.handle("settings.save", {"settings": {"theme": "hud"}})
    assert out["ok"] is True and out["changed"] == ["theme"]
    assert AppConfig.load(tmp_path).theme == "hud"


def test_saving_the_same_value_changes_nothing(bridge):
    out = bridge.handle("settings.save",
                        {"settings": {"theme": bridge.config.theme}})
    assert out["changed"] == []


def test_the_page_cannot_write_fields_it_has_no_business_with(bridge):
    out = bridge.handle("settings.save",
                        {"settings": {"auth_token": "stolen", "role": "admin"}})
    assert out["changed"] == []
    assert bridge.config.auth_token == ""


def test_a_value_outside_the_allowed_set_is_rejected(bridge):
    out = bridge.handle("settings.save",
                        {"settings": {"llm_provider": "definitely-not-real"}})
    assert out["rejected"] == ["llm_provider"]
    assert bridge.config.llm_provider == "anthropic"


def test_a_blank_secret_keeps_the_key_you_already_had(bridge):
    bridge.config.openai_api_key = "sk-existing"
    bridge.handle("settings.save", {"settings": {"openai_api_key": ""}})
    assert bridge.config.openai_api_key == "sk-existing"


def test_toggles_arrive_as_booleans_however_the_page_sends_them(bridge):
    bridge.handle("settings.save", {"settings": {"allow_shell": "true"}})
    assert bridge.config.allow_shell is True
    bridge.handle("settings.save", {"settings": {"allow_shell": False}})
    assert bridge.config.allow_shell is False


def test_the_app_is_told_what_changed(tmp_path):
    seen: list[set] = []
    bridge = Bridge(AppConfig(), config_dir=tmp_path,
                    on_change=lambda changed: seen.append(changed))
    bridge.handle("settings.save",
                  {"settings": {"voice_enabled": True, "tts_voice": "echo"}})
    assert seen and seen[0] == {"voice_enabled", "tts_voice"}


def test_a_failing_hook_does_not_lose_the_save(tmp_path):
    def boom(_changed):
        raise RuntimeError("the app blew up")

    bridge = Bridge(AppConfig(), config_dir=tmp_path, on_change=boom)
    out = bridge.handle("settings.save", {"settings": {"theme": "carbon"}})
    assert out["ok"] is True
    assert AppConfig.load(tmp_path).theme == "carbon"


def test_reset_restores_defaults_but_keeps_you_signed_in(bridge, tmp_path):
    bridge.config.theme = "hud"
    bridge.config.allow_shell = True
    bridge.config.auth_token = "keep-me"
    bridge.config.mode = "remote"
    out = bridge.handle("settings.reset")
    assert out["ok"] is True
    assert bridge.config.theme == AppConfig().theme
    assert bridge.config.allow_shell is False
    assert bridge.config.auth_token == "keep-me"
    assert bridge.config.mode == "remote"


# -- autostart --------------------------------------------------------------

def test_autostart_follows_the_switch(bridge, monkeypatch, tmp_path):
    from jarvis.desktop_app import autostart
    calls: list = []
    monkeypatch.setattr(autostart, "set_enabled",
                        lambda enabled, command, **kw: calls.append(enabled))
    out = bridge.handle("autostart.set", {"enabled": True})
    assert out == {"ok": True, "enabled": True}
    assert calls == [True]
    assert AppConfig.load(tmp_path).start_on_boot is True


# -- logs -------------------------------------------------------------------

def test_logs_come_from_the_real_file(bridge, tmp_path):
    log = tmp_path / "logs" / "jarvis.log"
    log.parent.mkdir()
    log.write_text("\n".join(f"line {i}" for i in range(500)), encoding="utf-8")
    out = bridge.handle("logs.tail", {"lines": 50})
    assert out["ok"] is True
    assert out["path"].endswith("jarvis.log")
    assert len(out["lines"]) == 50
    assert out["lines"][-1] == "line 499"


def test_no_log_yet_is_not_an_error(bridge):
    out = bridge.handle("logs.tail")
    assert out == {"ok": True, "path": "", "lines": []}


def test_a_silly_line_count_is_brought_back_into_range(bridge, tmp_path):
    log = tmp_path / "logs" / "jarvis.log"
    log.parent.mkdir()
    log.write_text("\n".join(str(i) for i in range(5000)), encoding="utf-8")
    assert len(bridge.handle("logs.tail", {"lines": 99999})["lines"]) == 2000
    assert len(bridge.handle("logs.tail", {"lines": "nonsense"})["lines"]) == 300
