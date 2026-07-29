"""Security capabilities and audit records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Capability(str, Enum):
    """Categories of potentially dangerous actions the assistant can take."""

    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    SHELL_EXEC = "shell_exec"
    DESKTOP_CONTROL = "desktop_control"
    NETWORK = "network"


class CapabilityMode(str, Enum):
    """How far a capability is trusted.

    ``ASK`` is the useful middle: the power is available, but every use stops
    and asks first — so a capability can be granted without being handed over
    unconditionally.
    """

    OFF = "off"     # refused outright
    ASK = "ask"     # allowed only when the user says yes, every time
    ON = "on"       # allowed silently

    @classmethod
    def coerce(cls, value: "CapabilityMode | str | bool") -> "CapabilityMode":
        """Read a mode from a mode, its name, or a plain on/off flag.

        Callers configured with booleans keep working: ``True`` is ``ON``.
        Anything unrecognised becomes ``OFF`` — an unreadable setting must
        never widen what the assistant may do.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            return cls.ON if value else cls.OFF
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.OFF


@dataclass
class AuditRecord:
    """A single audited action attempt."""

    capability: Capability
    action: str
    allowed: bool
    detail: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def format(self) -> str:
        verdict = "ALLOW" if self.allowed else "DENY"
        return (
            f"{self.timestamp.isoformat()} | {verdict:5} | "
            f"{self.capability.value} | {self.action} | {self.detail}"
        )
