"""Tests for the Telegram /link handler and the jarvis-admin CLI."""

from __future__ import annotations

import pytest

from jarvis.interfaces.telegram_bot import handle_link
from jarvis.licensing import LicenseService
from jarvis.licensing.__main__ import main as admin_main


@pytest.fixture()
def svc() -> LicenseService:
    service = LicenseService(":memory:", token_ttl_hours=1)
    yield service
    service.close()


# -- /link handler -------------------------------------------------------------


def test_link_disabled_when_no_service():
    assert "not enabled" in handle_link(None, "/link ABC", 1, "en")


def test_link_usage_without_code(svc: LicenseService):
    assert "/link CODE" in handle_link(svc, "/link", 1, "en")


def test_link_invalid_code(svc: LicenseService):
    out = handle_link(svc, "/link WRONGCODE", 1, "en")
    assert "invalid" in out.lower()


def test_link_success_flow(svc: LicenseService):
    acc = svc.create_account("tony", "arcreactor")
    code = svc.create_pairing_code(acc.id)
    out = handle_link(svc, f"/link {code}", 555, "en")
    assert "tony" in out
    assert svc.get_account_by_telegram(555).username == "tony"


def test_link_localized_ru(svc: LicenseService):
    acc = svc.create_account("tony", "arcreactor")
    code = svc.create_pairing_code(acc.id)
    out = handle_link(svc, f"/link {code}", 777, "ru")
    assert "привязан" in out.lower()


# -- admin CLI ------------------------------------------------------------------


@pytest.fixture()
def admin_env(tmp_path, monkeypatch):
    """Point the settings singleton at a temp auth DB for CLI runs."""
    from jarvis.config import settings as settings_mod

    db = tmp_path / "auth.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(db))
    settings_mod.get_settings.cache_clear()
    yield db
    settings_mod.get_settings.cache_clear()


def test_admin_full_lifecycle(admin_env, capsys):
    assert admin_main(["create-user", "pepper", "--password", "rescue"]) == 0
    assert admin_main(["issue-license", "pepper", "--days", "30"]) == 0
    out = capsys.readouterr().out
    assert "JVS-" in out

    assert admin_main(["list", "pepper"]) == 0
    out = capsys.readouterr().out
    assert "valid (29 days left)" in out or "valid (30 days left)" in out

    # The issued account can actually log in.
    svc = LicenseService(str(admin_env))
    assert svc.authenticate("pepper", "rescue").username == "pepper"
    svc.close()

    assert admin_main(["disable", "pepper"]) == 0
    svc = LicenseService(str(admin_env))
    with pytest.raises(Exception):
        svc.authenticate("pepper", "rescue")
    svc.close()

    assert admin_main(["enable", "pepper"]) == 0
    assert admin_main(["set-password", "pepper", "--password", "newpass"]) == 0
    svc = LicenseService(str(admin_env))
    assert svc.authenticate("pepper", "newpass").username == "pepper"
    svc.close()


def test_admin_generated_password_shown(admin_env, capsys):
    assert admin_main(["create-user", "happy"]) == 0
    out = capsys.readouterr().out
    assert "Generated password:" in out


def test_admin_errors(admin_env, capsys):
    assert admin_main(["issue-license", "nobody"]) == 1
    assert admin_main(["list", "nobody"]) == 1
    assert admin_main(["revoke-license", "JVS-bogus"]) == 1
    assert admin_main(["create-user", "dup"]) == 0
    assert admin_main(["create-user", "dup"]) == 1


def test_admin_revoke_license(admin_env, capsys):
    admin_main(["create-user", "rhodey", "--password", "warmachine"])
    admin_main(["issue-license", "rhodey"])
    out = capsys.readouterr().out
    key = next(line.split(": ", 1)[1] for line in out.splitlines()
            if line.startswith("Key (shown once):"))
    assert admin_main(["revoke-license", key]) == 0
    svc = LicenseService(str(admin_env))
    # Revoking takes the plan away, not the account: they drop to Free.
    assert svc.has_active_license(svc.get_account("rhodey").id) is False
    with pytest.raises(Exception):
        svc.authenticate("rhodey", "warmachine", require_license=True)
    svc.close()
