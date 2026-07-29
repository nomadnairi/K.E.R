"""A tier is a set of capabilities.

These tests pin the shape of the model, not the marketing: that tiers nest, that
the operator is not a tier anyone can buy, and — most importantly — that the
code is honest about which capabilities the server can actually refuse.
"""

from __future__ import annotations

from jarvis.billing import FREE, PLUS, PRO
from jarvis.billing.entitlements import (
    ALL_FEATURES,
    CHAT,
    LOCAL_ONLY,
    MCP,
    MEMORY,
    ORDER,
    PC_ACCESS,
    SEARCH,
    SERVER_ENFORCED,
    VOICE,
    describe,
    features_for,
    tier_that_unlocks,
)


def test_tiers_nest():
    """Paying more never takes a capability away."""
    free, plus, pro = (features_for(t) for t in (FREE, PLUS, PRO))
    assert free < plus < pro


def test_free_can_talk_and_remember():
    free = features_for(FREE)
    assert CHAT in free and MEMORY in free
    assert SEARCH not in free and VOICE not in free


def test_local_powers_belong_to_the_top_tier():
    assert PC_ACCESS not in features_for(PLUS)
    assert LOCAL_ONLY <= features_for(PRO)


def test_the_operator_is_not_a_tier():
    """The owner's account gets everything without buying anything."""
    assert features_for(FREE, owner=True) == ALL_FEATURES
    assert features_for("nonsense", owner=True) == ALL_FEATURES


def test_an_unknown_tier_falls_back_to_free():
    """An unreadable plan name must not hand out capabilities."""
    assert features_for("enterprise-gold") == features_for(FREE)


def test_every_capability_says_where_it_starts():
    for name in ORDER:
        assert tier_that_unlocks(name) in (FREE, PLUS, PRO), name


def test_the_split_between_enforced_and_packaged_is_clean():
    """A capability cannot be both server-enforced and purely local."""
    assert not (SERVER_ENFORCED & LOCAL_ONLY)


def test_local_capabilities_are_never_claimed_as_enforced():
    """Files, shell, MCP and a local model run on the user's own machine.

    Marking them "server-enforced" would be a lie: the server never sees those
    calls, so it cannot refuse them.
    """
    for name in (PC_ACCESS, MCP):
        assert name not in SERVER_ENFORCED


def test_describe_marks_what_is_included_and_what_is_local():
    rows = {row["name"]: row for row in describe(PLUS)}
    assert rows[SEARCH]["included"] is True
    assert rows[PC_ACCESS]["included"] is False
    assert rows[PC_ACCESS]["local"] is True
    assert rows[SEARCH]["local"] is False
    assert all(row["label"] for row in rows.values())
