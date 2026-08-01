"""Tests for subscription tiers (Free / Plus / Pro) and the Tariffs screens."""

from __future__ import annotations

from jarvis.billing import (
    FREE,
    PLUS,
    PRO,
    build_plans,
    default_plans,
    resolve_plan,
    tier_for,
)
from jarvis.interfaces.bot_menu import (
    limit_screen,
    plan_status,
    screen_plan_detail,
    screen_plans_hub,
)


def _flat(rows):
    return [data for row in rows for _, data in row]


# -- tier logic ---------------------------------------------------------------


def test_tier_for_maps_licence_plans():
    assert tier_for(None) == FREE
    assert tier_for("free") == FREE
    assert tier_for("standard") == PLUS
    assert tier_for("plus") == PLUS
    assert tier_for("premium") == PRO
    assert tier_for("pro") == PRO
    # Unknown but present plan => at least Plus (they paid for something).
    assert tier_for("enterprise") == PLUS


def test_free_plan_has_a_daily_limit():
    free = default_plans()[FREE]
    assert not free.unlimited
    assert free.within_daily(free.daily_messages - 1)
    assert not free.within_daily(free.daily_messages)
    assert free.remaining_daily(free.daily_messages - 2) == 2
    # No image / API access on Free.
    assert free.images is False and free.api_access is False


def test_pro_plan_is_unlimited():
    pro = default_plans()[PRO]
    assert pro.unlimited
    assert pro.within_daily(10_000_000)
    assert pro.remaining_daily(5) is None
    assert pro.all_models and pro.images and pro.api_access


def test_integration_limits_per_tier():
    p = default_plans()
    assert p[FREE].integrations == 2
    assert p[PLUS].integrations == 6
    assert p[PRO].integrations == 0 and p[PRO].unlimited_integrations
    assert not p[FREE].unlimited_integrations


def test_build_plans_applies_overrides():
    plans = build_plans(free_daily=3, plus_daily=50, pro_daily=0,
                        plus_price=999, pro_price=1999)
    assert plans[FREE].daily_messages == 3
    assert plans[PLUS].daily_messages == 50
    assert plans[PLUS].price_stars == 999
    assert plans[PRO].price_stars == 1999
    assert plans[PRO].unlimited


def test_resolve_plan_from_licence_name():
    plans = default_plans()
    assert resolve_plan("premium", plans).name == PRO
    assert resolve_plan(None, plans).name == FREE


# -- screens ------------------------------------------------------------------


def test_plan_status_line():
    plans = default_plans()
    assert "7/10" in plan_status("en", plans[FREE], used_today=3)
    assert "unlimited" in plan_status("en", plans[PRO], used_today=0)


def test_screen_plans_hub_lists_every_tier_and_drills_down():
    plans = default_plans()
    text, rows = screen_plans_hub("en", plans, current_tier=FREE)
    assert "Plans" in text
    flat = _flat(rows)
    # One button per tier, drilling into a detail screen — no card bodies or
    # buy buttons directly on the hub.
    assert "m:plandetail:free" in flat
    assert "m:plandetail:plus" in flat
    assert "m:plandetail:pro" in flat
    assert "m:buy:plus" not in flat and "m:buy:pro" not in flat


def test_screen_plan_detail_offers_upgrades_not_current():
    plans = default_plans()
    text, rows = screen_plan_detail("en", plans, current_tier=FREE, tier="pro")
    assert "Pro" in text
    assert "m:buy:pro" in _flat(rows)
    # Back goes to the hub, not straight to main.
    assert "m:plans" in _flat(rows)
    # A Pro user looking at their own tier is offered nothing to buy.
    _t, rows_pro = screen_plan_detail("en", plans, current_tier=PRO, tier="pro")
    assert "m:buy:pro" not in _flat(rows_pro)


def test_plans_banner_exists_and_caption_fits():
    # The Tariffs screens are sent as a photo; captions cap at 1024 chars.
    from pathlib import Path

    banner = (Path(__file__).resolve().parents[1]
            / "jarvis/interfaces/assets/plans_banner.png")
    assert banner.exists() and banner.stat().st_size > 0
    plans = default_plans()
    for loc in ("en", "ru", "uz"):
        text, _ = screen_plans_hub(loc, plans, current_tier=FREE)
        assert len(text) <= 1024
        for tier in (FREE, "plus", PRO):
            dtext, _ = screen_plan_detail(loc, plans, current_tier=FREE, tier=tier)
            assert len(dtext) <= 1024


def test_limit_screen_points_to_plans():
    plans = default_plans()
    text, rows = screen_plans_hub("ru", plans, current_tier=FREE)
    assert "Тарифы" in text
    ltext, lrows = limit_screen("en", plans[FREE])
    assert "limit" in ltext.lower()
    assert "m:plans" in _flat(lrows)
