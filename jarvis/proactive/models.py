"""The proactive engine's data model: a raw fact a sensor noticed.

A :class:`Signal` is deliberately not a message. It's a small, serializable
fact record; whether it's worth interrupting the user, and what to actually
say, is always an LLM decision downstream (see ``jarvis/proactive/decision.py``)
-- never branched on here. This keeps "no hardcoded trigger table" real: a
sensor's only job is "is the raw state outside normal bounds," not "is this
worth telling the user."
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Signal:
    """A single fact a :class:`~jarvis.proactive.sensors.base.ProactiveSensor`
    noticed, to be handed to the decision step alongside any others from the
    same tick."""

    sensor: str
    summary: str
    detail: str = ""
    #: A hint for the prompt/logs only ("info" | "notable" | "urgent") --
    #: never branched on in code (that would just be a hardcoded trigger
    #: table under a different name).
    severity: str = "info"
