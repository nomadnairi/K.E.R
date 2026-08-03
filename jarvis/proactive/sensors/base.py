"""The one extension point for the proactive engine.

A new trigger source ("anything else, even things not on the list") is a new
class implementing :class:`ProactiveSensor` -- nothing else in the engine
needs to change. Mirrors how skills/integrations/providers are all pluggable
in this codebase; a sensor is the proactive-engine equivalent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from jarvis.proactive.models import Signal


class ProactiveSensor(ABC):
    """Checks one source of "is something worth noticing right now."""

    #: Unique sensor name (used as ``Signal.sensor`` and in logs).
    name: str = "base"

    @abstractmethod
    async def check(self, *, user_id: str, scratch: dict) -> Signal | None:
        """Return a :class:`Signal` if there's something to report, else ``None``.

        This must stay cheap and mechanical ("is the raw state outside normal
        bounds") -- never "is this worth telling the user" or "what to say."
        That judgement always happens in the decision step, using the LLM, so
        a sensor can't become a hardcoded trigger table by another name. A
        sensor that raises must not take down the whole tick for other
        sensors/users -- the caller (:class:`~jarvis.proactive.engine.ProactiveEngine`)
        wraps each call, but a well-behaved sensor should still fail closed
        (return ``None``) on its own errors where practical.
        """
        raise NotImplementedError
