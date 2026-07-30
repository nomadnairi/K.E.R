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

    #: What /auth/me should answer. Tests override it per case.
    profile: dict = {"username": "ann", "owner": False, "tier": "free",
                     "features": ["chat", "memory"]}
    #: What the root endpoint says this server is. Overridden per case.
    server_info: dict = {"name": "KER", "version": "9.9.9", "status": "online",
                        "auth": "accounts", "accounts": True, "signup": True,
                        "telegram_login": True, "requires_license": False}

    def __init__(self, base_url: str, *, token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.calls: list[tuple] = []

    def info(self) -> dict:
        self.calls.append(("info",))
        return dict(self.server_info)

    def login(self, username: str, password: str) -> str:
        self.calls.append(("login", username, password))
        if password == "wrong":
            raise ApiError(401, "Bad credentials")
        self.token = "token-123"
        return self.token

    def register(self, username: str, password: str) -> str:
        self.calls.append(("register", username, password))
        if username == "taken":
            raise ApiError(409, "That username is taken.")
        self.token = "token-new"
        return self.token

    def login_with_telegram_code(self, code: str) -> str:
        self.calls.append(("telegram", code))
        if code == "000000":
            raise ApiError(400, "Code expired")
        self.token = "token-tg"
        return self.token

    def me(self) -> dict:
        self.calls.append(("me",))
        return dict(self.profile)


class UnreachableClient(FakeClient):
    """A server that answers the login but is gone by the time we ask again."""

    def me(self) -> dict:
        raise ApiError(0, "Cannot reach server")


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

def test_there_is_no_way_in_but_an_account(bridge):
    """Signing in is the only way in — the owner included."""
    assert bridge.handle("login.local")["ok"] is False


def test_password_sign_in_stores_the_token_and_the_plan(bridge, tmp_path):
    out = bridge.handle("login.password", {"server": "http://localhost:8000",
                                           "username": "ann",
                                           "password": "secret"})
    assert out["ok"] is True and out["tier"] == "free"
    saved = AppConfig.load(tmp_path)
    assert saved.auth_token == "token-123"
    assert saved.username == "ann"
    assert saved.plan_features == ["chat", "memory"]
    assert saved.role == "user"
    # Free has no local capabilities, so the engine is the server's.
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


# -- registering ------------------------------------------------------------

def test_registering_creates_the_account_and_signs_in(tmp_path):
    class FreshClient(FakeClient):
        profile = {"username": "bob", "owner": False, "tier": "free",
                   "features": ["chat", "memory"]}

    bridge = Bridge(AppConfig(), client_factory=FreshClient,
                    config_dir=tmp_path)
    out = bridge.handle("login.register", {"server": "http://localhost:8000",
                                           "username": "bob",
                                           "password": "hunter2hunter2",
                                           "password2": "hunter2hunter2"})
    assert out["ok"] is True and out["tier"] == "free"
    saved = AppConfig.load(tmp_path)
    assert saved.auth_token == "token-new"
    assert saved.username == "bob"
    # A brand-new account is nobody special: Free tier, ordinary role.
    assert saved.role == "user" and saved.is_owner is False


def test_mistyped_repeat_never_reaches_the_server(bridge):
    out = bridge.handle("login.register", {"server": "http://localhost:8000",
                                           "username": "bob",
                                           "password": "hunter2hunter2",
                                           "password2": "hunter2hunter3"})
    assert out["ok"] is False
    assert "not match" in out["error"]
    assert bridge.signed_in is False


def test_a_taken_username_is_reported_as_the_server_put_it(bridge):
    out = bridge.handle("login.register", {"server": "http://localhost:8000",
                                           "username": "taken",
                                           "password": "hunter2hunter2",
                                           "password2": "hunter2hunter2"})
    assert out == {"ok": False, "error": "That username is taken."}


def test_registering_needs_all_the_fields(bridge):
    out = bridge.handle("login.register", {"server": "", "username": "",
                                           "password": ""})
    assert out["ok"] is False and bridge.signed_in is False


# -- what kind of server is this? -------------------------------------------

def test_the_probe_says_what_the_server_offers(bridge):
    out = bridge.handle("server.probe", {"server": "http://localhost:8000"})
    assert out["ok"] is True and out["reachable"] is True
    assert out["accounts"] is True and out["signup"] is True
    assert out["telegram_login"] is True
    assert out["version"] == "9.9.9"


def test_the_probe_names_a_server_with_accounts_switched_off(bridge,
                                                            monkeypatch):
    """The real cause behind 'invalid or expired code', said out loud."""
    monkeypatch.setattr(FakeClient, "server_info",
                        {"name": "KER", "version": "9.9.9",
                         "auth": "shared-key", "accounts": False,
                         "signup": False, "telegram_login": False})
    out = bridge.handle("server.probe", {"server": "http://localhost:8000"})
    assert out["ok"] is True
    assert out["accounts"] is False and out["telegram_login"] is False


def test_an_older_server_is_read_from_its_auth_field_alone(bridge, monkeypatch):
    monkeypatch.setattr(FakeClient, "server_info",
                        {"name": "KER", "version": "1.0.0",
                         "auth": "accounts"})
    out = bridge.handle("server.probe", {"server": "http://localhost:8000"})
    assert out["accounts"] is True and out["telegram_login"] is True
    assert out["signup"] is False        # unknown means no, never assumed yes


def test_the_probe_reports_a_server_that_is_not_there(tmp_path):
    class Gone(FakeClient):
        def info(self) -> dict:
            raise ApiError(0, "Cannot reach server: [Errno 111] refused")

    bridge = Bridge(AppConfig(), client_factory=Gone, config_dir=tmp_path)
    out = bridge.handle("server.probe", {"server": "http://localhost:9"})
    assert out["ok"] is False and out["reachable"] is False
    assert "refused" in out["error"]


def test_the_probe_needs_an_address(bridge):
    assert bridge.handle("server.probe", {"server": " "})["ok"] is False


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


# -- the subscription decides what the app is -------------------------------

def test_the_owner_gets_everything_and_the_admin_role(tmp_path):
    class OwnerClient(FakeClient):
        profile = {"username": "boss", "owner": True, "tier": "pro",
                   "features": ["chat", "memory", "pc_access", "local_ai"]}

    config = AppConfig(anthropic_api_key="sk-test")
    bridge = Bridge(config, client_factory=OwnerClient, config_dir=tmp_path)
    out = bridge.handle("login.password", {"server": "http://localhost:8000",
                                           "username": "boss",
                                           "password": "secret"})
    assert out["owner"] is True
    saved = AppConfig.load(tmp_path)
    assert saved.role == "admin"
    assert saved.is_owner is True
    # Local capabilities plus a key: the engine belongs on this machine.
    assert saved.mode == "local"
    assert saved.has("pc_access") is True


def test_a_plan_without_local_powers_uses_the_server(tmp_path):
    config = AppConfig(anthropic_api_key="sk-test")   # key present…
    bridge = Bridge(config, client_factory=FakeClient, config_dir=tmp_path)
    bridge.handle("login.password", {"server": "http://localhost:8000",
                                     "username": "ann", "password": "secret"})
    # …but Free is not entitled to run anything locally.
    assert config.may_run_locally() is False
    assert config.mode == "remote"


def test_local_powers_still_need_a_model_to_talk_to(tmp_path):
    class ProClient(FakeClient):
        profile = {"username": "pat", "owner": False, "tier": "pro",
                   "features": ["chat", "pc_access", "local_ai"]}

    config = AppConfig()                     # entitled, but no key anywhere
    bridge = Bridge(config, client_factory=ProClient, config_dir=tmp_path)
    bridge.handle("login.password", {"server": "http://localhost:8000",
                                     "username": "pat", "password": "secret"})
    assert config.may_run_locally() is False
    assert config.mode == "remote"


def test_an_unreachable_server_keeps_the_plan_you_had(tmp_path):
    """Losing the network must not silently demote a paying user."""
    config = AppConfig(plan_tier="pro", plan_features=["chat", "pc_access"],
                       is_owner=False)
    bridge = Bridge(config, client_factory=UnreachableClient,
                    config_dir=tmp_path)
    out = bridge.handle("login.password", {"server": "http://localhost:8000",
                                           "username": "pat",
                                           "password": "secret"})
    assert out["ok"] is True                 # the login itself worked
    assert config.plan_tier == "pro"         # cached plan survives
    assert config.plan_features == ["chat", "pc_access"]


def test_plan_get_reports_whether_it_is_live_or_cached(tmp_path):
    config = AppConfig()
    bridge = Bridge(config, client_factory=FakeClient, config_dir=tmp_path)
    bridge.handle("login.password", {"server": "http://localhost:8000",
                                     "username": "ann", "password": "secret"})
    live = bridge.handle("plan.get")
    assert live["ok"] is True and live["live"] is True
    assert live["tier"] == "free"

    bridge.client = UnreachableClient("http://localhost:8000")
    cached = bridge.handle("plan.get")
    assert cached["live"] is False            # honest about being stale
    assert cached["tier"] == "free"           # but still knows the plan


def test_the_page_cannot_promote_itself(tmp_path):
    """The plan comes from the server; the interface may not write it."""
    config = AppConfig()
    bridge = Bridge(config, config_dir=tmp_path)
    bridge.handle("settings.save", {"settings": {"plan_tier": "pro",
                                                 "is_owner": True,
                                                 "plan_features": ["pc_access"]}})
    assert config.plan_tier == "free"
    assert config.is_owner is False
    assert config.plan_features == []
