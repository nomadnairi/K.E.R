"""
Security manager.

Decides how far a :class:`Capability` is trusted — refused, allowed, or
allowed once the user confirms this particular use — and records every attempt
to an in-memory audit trail plus an optional log file. Secrets are redacted
from audit details.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.config.settings import Settings
from jarvis.security.confirm import ConfirmationBroker
from jarvis.security.policy import AuditRecord, Capability, CapabilityMode
from jarvis.utils.exceptions import PermissionDenied
from jarvis.utils.logger import get_logger
from jarvis.utils.redaction import redact_secrets

logger = get_logger(__name__)


class SecurityManager:
    """Central permission checks + audit log for dangerous capabilities."""

    def __init__(self, allowed: dict[Capability, CapabilityMode | bool],
                audit_log_path: str | None = None,
                confirmer: ConfirmationBroker | None = None) -> None:
        # Callers that pass plain booleans keep working: True means "on".
        self._modes = {cap: CapabilityMode.coerce(value)
                    for cap, value in allowed.items()}
        self._audit_log_path = audit_log_path
        self._records: list[AuditRecord] = []
        #: Asks the user when a capability is set to "ask". With nobody to ask,
        #: that mode refuses — it must never fall through to allowed.
        self.confirmer = confirmer

    @classmethod
    def from_settings(cls, settings: Settings,
                    confirmer: ConfirmationBroker | None = None
                    ) -> "SecurityManager":
        def mode(allowed: bool, ask: bool) -> CapabilityMode:
            if not allowed:
                return CapabilityMode.OFF
            return CapabilityMode.ASK if ask else CapabilityMode.ON

        return cls(
            allowed={
                Capability.FILE_READ: mode(settings.allow_file_read,
                                        settings.confirm_file_read),
                Capability.FILE_WRITE: mode(settings.allow_file_write,
                                            settings.confirm_file_write),
                Capability.SHELL_EXEC: mode(settings.allow_shell,
                                            settings.confirm_shell),
                Capability.DESKTOP_CONTROL: mode(
                    settings.allow_desktop_control,
                    settings.confirm_desktop_control),
                Capability.NETWORK: CapabilityMode.ON,
            },
            audit_log_path=settings.audit_log_path or None,
            confirmer=confirmer,
        )

    # -- permission checks --------------------------------------------------

    def mode(self, capability: Capability) -> CapabilityMode:
        """How far this capability is currently trusted."""
        return self._modes.get(capability, CapabilityMode.OFF)

    def modes(self) -> dict[str, str]:
        """Every capability's mode — the real state, for showing the user."""
        return {cap.value: self.mode(cap).value for cap in Capability}

    def is_allowed(self, capability: Capability) -> bool:
        """Whether the capability may be used *without* asking.

        "Ask" deliberately does not count here: this answers "what may the
        assistant do on its own", which is what callers describe to the user.
        """
        return self.mode(capability) is CapabilityMode.ON

    def require(self, capability: Capability, action: str = "") -> None:
        """Raise :class:`PermissionDenied` unless the action may go ahead.

        In *ask* mode this blocks while the user is asked, so it belongs on a
        worker thread — which is where tool bodies already run. Every outcome
        is audited, including what the user answered.
        """
        what = action or capability.value
        mode = self.mode(capability)

        if mode is CapabilityMode.ON:
            self.record(capability, what, True)
            return

        if mode is CapabilityMode.ASK:
            if self.confirmer is None:
                self.record(capability, what, False, "ask mode, nobody to ask")
                raise PermissionDenied(
                    f"'{capability.value}' needs your confirmation, but there "
                    f"is no interface to ask. Open the app, or set the "
                    f"capability to allowed."
                )
            granted = self.confirmer.request(capability, what)
            self.record(capability, what, granted,
                        "confirmed by user" if granted else "refused by user")
            if not granted:
                raise PermissionDenied(
                    f"You did not confirm '{capability.value}', so nothing "
                    f"was done."
                )
            return

        self.record(capability, what, False)
        raise PermissionDenied(
            f"'{capability.value}' is disabled. Enable it in the security "
            f"settings to allow this action."
        )

    # -- audit --------------------------------------------------------------

    def record(self, capability: Capability, action: str, allowed: bool,
            detail: str = "") -> AuditRecord:
        record = AuditRecord(
            capability=capability,
            action=redact_secrets(action),
            allowed=allowed,
            detail=redact_secrets(detail),
        )
        self._records.append(record)
        self._append_to_file(record)
        logger.debug("audit: %s", record.format())
        return record

    def _append_to_file(self, record: AuditRecord) -> None:
        if not self._audit_log_path:
            return
        try:
            path = Path(self._audit_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(record.format() + "\n")
        except OSError as exc:  # pragma: no cover - disk edge case
            logger.warning("Could not write audit log: %s", exc)

    @property
    def audit_trail(self) -> list[AuditRecord]:
        return list(self._records)
