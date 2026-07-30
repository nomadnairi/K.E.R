"""
Per-tier metering for the hosted LLM proxy.

The proxy spends the *operator's* provider credits on behalf of a signed-in
account, so it has to be counted and it has to be stoppable. This module is the
counter: it maps a tier to a daily token allowance, reads how much the account
has already spent today, and answers one question — may this request proceed?
It also records what a finished request actually cost.

Deliberately framework-free and network-free. It reasons over a
:class:`~jarvis.interfaces.usage.UsageStore` (or anything with the same
``record``/``stats`` shape), so the same logic is testable without a server and
reusable from the bot, the API and any future client. Proxy spend is kept in
its own namespace so it never collides with the bot's message counter.

A quota of ``0`` means *unlimited* — that is how Pro's "API от меня" is
expressed: an allowance of zero is not "nothing", it is "no ceiling", matching
how :class:`~jarvis.billing.plans.Plan` already reads ``daily_messages``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _Ledger(Protocol):
    """The slice of :class:`UsageStore` the meter needs."""

    def record(self, user_id: str, tokens: int = 0) -> None: ...

    def stats(self, user_id: str, *, now: float | None = None) -> dict: ...


@dataclass(frozen=True)
class Quota:
    """A tier's daily token allowance. ``0`` means unlimited."""

    daily_tokens: int

    @property
    def unlimited(self) -> bool:
        return self.daily_tokens <= 0

    def remaining(self, used_today: int) -> int | None:
        """Tokens left today, or ``None`` when unlimited."""
        if self.unlimited:
            return None
        return max(0, self.daily_tokens - used_today)

    def within(self, used_today: int) -> bool:
        """Is the account still under today's ceiling?"""
        return self.unlimited or used_today < self.daily_tokens


@dataclass(frozen=True)
class MeterDecision:
    """The meter's answer about one account, right now."""

    allowed: bool
    #: A machine-readable reason when refused: "quota_exceeded" | "not_enabled".
    reason: str = ""
    used_today: int = 0
    #: The tier's ceiling; ``0`` means unlimited.
    limit: int = 0
    #: Tokens left today, or ``None`` when unlimited.
    remaining: int | None = None
    unlimited: bool = False

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "used_today": self.used_today,
            "limit": self.limit,
            "remaining": self.remaining,
            "unlimited": self.unlimited,
        }


class UsageMeter:
    """Enforces per-tier daily token allowances against a shared ledger."""

    def __init__(self, ledger: _Ledger, quotas: dict[str, Quota], *,
                 namespace: str = "proxy") -> None:
        self._ledger = ledger
        self._quotas = quotas
        #: Keeps proxy spend distinct from the bot's message counter.
        self._ns = namespace

    def _key(self, principal: str) -> str:
        return f"{self._ns}:{principal}"

    def _quota(self, tier: str) -> Quota:
        # An unknown tier gets the tightest known allowance rather than a free
        # pass — a mislabelled account must never accidentally become unlimited.
        if tier in self._quotas:
            return self._quotas[tier]
        if not self._quotas:
            return Quota(0)
        return min(self._quotas.values(),
                   key=lambda q: (q.unlimited, q.daily_tokens))

    def _used_today(self, principal: str, *, now: float | None = None) -> int:
        try:
            return int(self._ledger.stats(self._key(principal),
                                          now=now)["tokens_today"])
        except Exception:  # noqa: BLE001 - a broken ledger must not open the gate
            return 0

    def snapshot(self, principal: str, tier: str, *,
                 now: float | None = None) -> MeterDecision:
        """Where this account stands today — without deciding a new request."""
        quota = self._quota(tier)
        used = self._used_today(principal, now=now)
        return MeterDecision(
            allowed=quota.within(used),
            reason="" if quota.within(used) else "quota_exceeded",
            used_today=used,
            limit=quota.daily_tokens,
            remaining=quota.remaining(used),
            unlimited=quota.unlimited,
        )

    def check(self, principal: str, tier: str, *,
              now: float | None = None) -> MeterDecision:
        """May this account make another proxied request right now?

        A pre-flight over the numeric ceiling only — *whether* the account may
        use the proxy at all is the endpoint's decision, made from the
        ``api_access`` entitlement before the meter is ever consulted. The true
        cost is not known until the call returns, so this refuses only an
        account already at or over its ceiling; one final request may cross the
        line by its own size, which is recorded so the next check refuses.
        Unlimited tiers (quota ``0``) always pass.
        """
        return self.snapshot(principal, tier, now=now)

    def record(self, principal: str, tokens: int) -> None:
        """Book what a finished request actually spent."""
        if tokens > 0:
            self._ledger.record(self._key(principal), int(tokens))


def quotas_from_settings(settings) -> dict[str, Quota]:
    """Build the tier→quota table for the proxy from a :class:`Settings`.

    A tier with a positive allowance is metered; ``0`` is unlimited (Pro). Free
    carries no ``api_access`` entitlement, so it never reaches the meter — its
    quota number is moot, which is why the on/off lives in the entitlement, not
    in a number that could read as "unlimited" by accident.
    """
    from jarvis.billing.plans import FREE, PLUS, PRO
    return {
        FREE: Quota(settings.proxy_free_daily_tokens),
        PLUS: Quota(settings.proxy_plus_daily_tokens),
        PRO: Quota(settings.proxy_pro_daily_tokens),
    }
