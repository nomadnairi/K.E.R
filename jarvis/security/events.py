"""
Security audit log for authentication events.

Separate from the capability audit (:mod:`jarvis.security.manager`, "may this
action touch the machine?") — this records *who tried to get in and whether it
worked*: logins, token issue/revoke, API-key create/revoke, account creation,
owner bootstrap. A tamper-evident trail of auth activity is an ASVS/GDPR
expectation and the first thing an incident responder reads.

Deliberately tiny: events go to a dedicated ``jarvis.security.audit`` logger, so
a deployment routes them wherever its logs already go (file, journald, SIEM)
without new plumbing. Secrets are redacted before anything is written, and we
log **identifiers and outcomes, never passwords, tokens or keys**.
"""

from __future__ import annotations

import logging

from jarvis.utils.redaction import redact_secrets

audit_logger = logging.getLogger("jarvis.security.audit")

# Event names — a closed vocabulary so logs are greppable and stable.
LOGIN_OK = "login.ok"
LOGIN_FAIL = "login.fail"
ACCOUNT_CREATED = "account.created"
TOKEN_ISSUED = "token.issued"
TOKEN_REVOKED = "token.revoked"
APIKEY_CREATED = "apikey.created"
APIKEY_REVOKED = "apikey.revoked"
OWNER_BOOTSTRAP = "owner.bootstrap"
PASSWORD_CHANGED = "password.changed"


def audit_event(event: str, *, principal: str = "", ok: bool = True,
                detail: str = "") -> None:
    """Record one auth event. Never raises — auditing must not break a login."""
    try:
        who = redact_secrets(str(principal))[:120]
        extra = redact_secrets(str(detail))[:300] if detail else ""
        audit_logger.info("auth event=%s principal=%s ok=%s%s",
                        event, who or "-", ok,
                        f" detail={extra}" if extra else "")
    except Exception:  # noqa: BLE001 - audit is best-effort, never fatal
        pass
