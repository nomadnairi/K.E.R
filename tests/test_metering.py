"""The proxy's meter: per-tier daily token allowances against a shared ledger.

The meter is what makes "API от меня" safe to hand out — it counts the
operator's spend per account and refuses once a tier's ceiling is reached, with
Pro unlimited. These tests are the contract for that arithmetic; no server, no
network.
"""

from __future__ import annotations

import pytest

from jarvis.billing.metering import Quota, UsageMeter, quotas_from_settings
from jarvis.billing.plans import FREE, PLUS, PRO
from jarvis.config.settings import Settings
from jarvis.interfaces.usage import UsageStore


@pytest.fixture()
def store():
    s = UsageStore(":memory:")
    yield s
    s.close()


@pytest.fixture()
def meter(store):
    return UsageMeter(store, {
        FREE: Quota(0),           # unlimited number, but Free never gets here
        PLUS: Quota(1000),
        PRO: Quota(0),            # unlimited
    })


# -- Quota arithmetic --------------------------------------------------------

def test_a_zero_quota_is_unlimited():
    q = Quota(0)
    assert q.unlimited is True
    assert q.remaining(999999) is None
    assert q.within(999999) is True


def test_a_real_quota_counts_down():
    q = Quota(1000)
    assert q.unlimited is False
    assert q.remaining(0) == 1000
    assert q.remaining(400) == 600
    assert q.within(999) is True
    assert q.within(1000) is False          # at the ceiling is over
    assert q.remaining(1200) == 0           # never negative


# -- the meter ---------------------------------------------------------------

def test_a_fresh_account_is_allowed_with_the_full_allowance(meter):
    d = meter.check("user:ann", PLUS)
    assert d.allowed is True
    assert d.used_today == 0
    assert d.remaining == 1000
    assert d.unlimited is False


def test_spend_is_recorded_and_counted_down(meter):
    meter.record("user:ann", 400)
    d = meter.snapshot("user:ann", PLUS)
    assert d.used_today == 400
    assert d.remaining == 600
    assert d.allowed is True


def test_the_ceiling_refuses_the_next_request(meter):
    meter.record("user:ann", 1000)
    d = meter.check("user:ann", PLUS)
    assert d.allowed is False
    assert d.reason == "quota_exceeded"
    assert d.remaining == 0


def test_one_last_request_may_cross_the_line_then_the_next_is_refused(meter):
    # 990 used, still under 1000 → allowed. That call spends 500 (overshoot).
    meter.record("user:ann", 990)
    assert meter.check("user:ann", PLUS).allowed is True
    meter.record("user:ann", 500)
    assert meter.check("user:ann", PLUS).allowed is False


def test_pro_is_never_refused(meter):
    meter.record("user:boss", 10_000_000)
    d = meter.check("user:boss", PRO)
    assert d.allowed is True
    assert d.unlimited is True
    assert d.remaining is None


def test_accounts_are_metered_independently(meter):
    meter.record("user:ann", 1000)
    assert meter.check("user:ann", PLUS).allowed is False
    assert meter.check("user:bob", PLUS).allowed is True


def test_proxy_spend_does_not_touch_the_bots_message_counter(store, meter):
    """The proxy namespace is separate, so chat stats stay clean."""
    meter.record("user:ann", 500)
    # The bot records under the bare principal; the meter under "proxy:...".
    assert store.stats("user:ann")["tokens_today"] == 0
    assert store.stats("proxy:user:ann")["tokens_today"] == 500


def test_an_unknown_tier_gets_the_tightest_allowance_never_a_free_pass():
    store = UsageStore(":memory:")
    try:
        meter = UsageMeter(store, {PLUS: Quota(1000), PRO: Quota(0)})
        meter.record("user:x", 1000)
        # A mislabelled tier must not become unlimited by default.
        d = meter.check("user:x", "mystery-tier")
        assert d.allowed is False
        assert d.limit == 1000
    finally:
        store.close()


def test_a_broken_ledger_keeps_the_gate_shut_not_open():
    class Broken:
        def record(self, *_a, **_k): ...
        def stats(self, *_a, **_k):
            raise RuntimeError("db gone")

    meter = UsageMeter(Broken(), {PLUS: Quota(1000)})
    d = meter.snapshot("user:ann", PLUS)
    # Reads as zero-used (not unlimited) — a failure cannot mint free tokens.
    assert d.used_today == 0
    assert d.remaining == 1000


# -- wiring from settings ----------------------------------------------------

def test_quotas_come_from_settings():
    s = Settings(anthropic_api_key="k", log_file="",
                proxy_plus_daily_tokens=250_000, proxy_pro_daily_tokens=0)
    quotas = quotas_from_settings(s)
    assert quotas[PLUS].daily_tokens == 250_000
    assert quotas[PRO].unlimited is True
