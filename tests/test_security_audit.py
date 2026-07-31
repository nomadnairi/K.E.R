"""Tests for the security self-audit."""

from __future__ import annotations

from jarvis.config.settings import Settings
from jarvis.search.base import SearchError, request_json
from jarvis.security.audit import audit_settings, worst_severity


def _areas(findings):
    return {f.area for f in findings}


def test_hardened_defaults_are_low_risk():
    # Defaults: dangerous caps off, redaction on. The only findings are the
    # unauthenticated API (medium) — acceptable for local dev.
    findings = audit_settings(Settings(log_file="", api_key="k"))
    assert all(f.severity in ("low", "info") for f in findings)


def test_shell_and_desktop_are_high():
    findings = audit_settings(Settings(log_file="", api_key="k",
                                    allow_shell=True,
                                    allow_desktop_control=True))
    highs = [f for f in findings if f.severity == "high"]
    assert {"shell", "desktop"} <= {f.area for f in highs}
    assert worst_severity(findings) == "high"


def test_missing_api_key_flagged():
    findings = audit_settings(Settings(log_file="", api_key=""))
    assert "api" in _areas(findings)


def test_redaction_off_flagged():
    findings = audit_settings(Settings(log_file="", api_key="k",
                                    memory_redact_secrets=False))
    assert "memory" in _areas(findings)


def test_public_bot_is_info():
    findings = audit_settings(Settings(log_file="", api_key="k",
                                    telegram_bot_token="t",
                                    telegram_allowed_users=""))
    tg = [f for f in findings if f.area == "telegram"]
    assert any(f.severity == "info" for f in tg)


def test_findings_sorted_most_severe_first():
    findings = audit_settings(Settings(log_file="", api_key="",
                                    allow_shell=True))
    severities = [f.severity for f in findings]
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    assert severities == sorted(severities, key=lambda s: order[s])


def test_search_error_does_not_leak_url_key():
    # A failing request must not surface the full URL (which may carry a key).
    try:
        request_json("https://example.invalid/search?api_key=SECRET123", timeout=1)
    except SearchError as exc:
        assert "SECRET123" not in str(exc)
        assert "example.invalid" in str(exc)
    else:
        raise AssertionError("expected SearchError")


# -- production-hardening findings (release gate) -----------------------------

def _prod_settings(**kw):
    from jarvis.config.settings import Settings
    base = dict(log_file="", auth_enabled=True, api_key="secret",
                api_docs_enabled=False, api_cors_origins="https://app.example",
                memory_redact_secrets=True)
    base.update(kw)
    return Settings(**base)


def test_encryption_off_is_flagged_when_accounts_on():
    from jarvis.security.audit import audit_settings
    findings = audit_settings(_prod_settings())  # no KER_DATA_KEY
    areas = {(f.area, f.severity) for f in findings}
    assert ("encryption", "medium") in areas


def test_open_docs_and_wildcard_cors_are_flagged():
    from jarvis.security.audit import audit_settings
    findings = audit_settings(_prod_settings(api_docs_enabled=True,
                                            api_cors_origins="*"))
    areas = {f.area for f in findings}
    assert "api" in areas and "cors" in areas


def test_a_hardened_config_has_no_high_or_medium(monkeypatch):
    from jarvis.security.audit import audit_settings, worst_severity
    monkeypatch.setenv("KER_DATA_KEY",
                    __import__("jarvis.security.crypto", fromlist=["KeyProvider"])
                    .KeyProvider.generate())
    findings = audit_settings(_prod_settings(
        owner_username="boss", owner_password="a-long-strong-secret"))
    worst = worst_severity(findings)
    assert worst in (None, "low", "info"), [str(f) for f in findings]


def test_short_owner_password_is_flagged():
    from jarvis.security.audit import audit_settings
    findings = audit_settings(_prod_settings(owner_username="boss",
                                            owner_password="short"))
    assert any(f.area == "owner" for f in findings)
