"""
Asking the user before doing something powerful.

A capability set to *ask* does not refuse and does not proceed — it stops and
puts the question in front of the person. The tool runs on a worker thread and
blocks in :meth:`ConfirmationBroker.request`; the interface picks the question
up, shows it, and answers with :meth:`resolve`.

Two rules this module exists to enforce:

* **Silence is no.** If nobody answers within the timeout, the action is
  refused. An unattended machine must not grant permissions by waiting.
* **One question, one answer.** Each request is answered once; a late or
  duplicate answer changes nothing.
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field

from jarvis.core.runtime import current_session
from jarvis.security.policy import Capability
from jarvis.utils.logger import get_logger
from jarvis.utils.redaction import redact_secrets

logger = get_logger(__name__)

#: How long to wait for an answer before refusing.
DEFAULT_TIMEOUT = 60.0


def owner_of(session_id: str) -> str:
    """The account a scoped session belongs to.

    HTTP sessions are namespaced ``f"{principal}::{session_id}"`` (see
    ``jarvis.api.app._scoped``); this is that ``principal``, unchanged for
    everything else (a bot session like ``"tg-12345"``, or the bare
    ``"default"`` a local/self-hosted caller uses) — those already name their
    one owner directly, with nothing to split off.
    """
    return session_id.split("::", 1)[0]


@dataclass
class PendingConfirmation:
    """A question waiting for an answer."""

    id: str
    capability: Capability
    action: str
    #: Who this question is for — see :func:`owner_of`. Set from the calling
    #: turn's session, never from anything a caller supplies, so a request
    #: cannot be filed under someone else's name.
    owner: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    _event: threading.Event = field(default_factory=threading.Event, repr=False)
    _answer: bool = False

    def to_dict(self) -> dict:
        """What the interface needs to render the question."""
        return {
            "id": self.id,
            "capability": self.capability.value,
            "action": self.action,
            "seconds_left": max(0, int(self.expires_at - time.time())),
        }


class ConfirmationBroker:
    """Carries permission questions from the engine to whoever is watching.

    One broker is shared by the whole engine process — the same instance
    serves every signed-in account when accounts are enabled — so every
    question is filed under its :attr:`PendingConfirmation.owner` and the
    interface side (:meth:`pending`, :meth:`resolve`) only ever sees or
    answers its own caller's questions once given an ``owner`` to scope by.
    """

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self._lock = threading.Lock()
        self._pending: dict[str, PendingConfirmation] = {}
        self._ids = itertools.count(1)

    # -- the engine side ----------------------------------------------------

    def request(self, capability: Capability, action: str, *,
                timeout: float | None = None) -> bool:
        """Ask, and block this thread until answered, refused or timed out.

        Never call this on the event loop — it is meant for the worker thread a
        tool already runs on. The owner is read from the current turn's
        session (``jarvis.core.runtime.current_session``, set once per turn by
        the engine and propagated across the ``await``/thread boundary by
        ``contextvars``) — not passed in, so a tool cannot claim to be asking
        on someone else's behalf.
        """
        wait = self.timeout if timeout is None else timeout
        item = PendingConfirmation(
            id=f"c{next(self._ids)}",
            capability=capability,
            action=redact_secrets(action)[:400],
            owner=owner_of(current_session()),
            expires_at=time.time() + wait,
        )
        with self._lock:
            self._pending[item.id] = item
        logger.info("Asking permission for %s: %s", capability.value, item.action)
        try:
            answered = item._event.wait(wait)
        finally:
            with self._lock:
                self._pending.pop(item.id, None)
        if not answered:
            logger.info("Permission question %s timed out — refused", item.id)
            return False
        return item._answer

    # -- the interface side -------------------------------------------------

    def pending(self, owner: str | None = None) -> list[dict]:
        """Questions currently on screen (or about to be), oldest first.

        With ``owner`` set, only that owner's own questions are returned —
        otherwise (no accounts on this server; see
        ``jarvis.api.app._tenant_prefix`` for the same reasoning applied to
        memory) every question is shown, matching the single-tenant behaviour
        this had before accounts existed.
        """
        now = time.time()
        with self._lock:
            items = sorted(self._pending.values(), key=lambda p: p.created_at)
            return [p.to_dict() for p in items
                    if p.expires_at > now and (owner is None or p.owner == owner)]

    def resolve(self, request_id: str, allowed: bool, *,
                owner: str | None = None) -> bool:
        """Answer one question. False when there was nothing *this owner*
        could answer — a question that does not exist and one that belongs to
        someone else are reported identically, so a caller cannot use this to
        probe which request ids are real.
        """
        with self._lock:
            item = self._pending.get(request_id)
            if (item is None or item._event.is_set()
                    or (owner is not None and item.owner != owner)):
                return False
            item._answer = bool(allowed)
            item._event.set()
        logger.info("Permission %s: %s", request_id,
                    "granted" if allowed else "refused")
        return True

    def resolve_all(self, allowed: bool, *, owner: str | None = None) -> int:
        """Answer everything outstanding — used when the window goes away.

        Scoped by ``owner`` for the same reason as :meth:`resolve`; unused
        today (the desktop app closes only its own, single-tenant broker), but
        kept consistent so a future multi-tenant caller doesn't reintroduce
        this class of bug by reaching for the one method that lacked it.
        """
        with self._lock:
            items = [p for p in self._pending.values()
                    if not p._event.is_set() and (owner is None or p.owner == owner)]
            for item in items:
                item._answer = bool(allowed)
                item._event.set()
        return len(items)
