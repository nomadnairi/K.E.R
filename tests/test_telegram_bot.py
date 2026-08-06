"""Tests for the Telegram interface's testable core (no network / no aiogram)."""

from __future__ import annotations

import pytest

from jarvis.config.settings import Settings
from jarvis.interfaces.telegram_bot import (
    _is_allowed,
    menu_action_is_gated,
    generate_reply,
    principal_session_id,
    session_id_for,
    split_message,
)


def test_session_id_is_per_user():
    assert session_id_for(42) == "tg-42"
    assert session_id_for(1) != session_id_for(2)


def test_split_message_short_passthrough():
    assert split_message("hello") == ["hello"]


def test_split_message_respects_limit():
    text = "\n".join(f"line {i}" for i in range(1000))
    chunks = split_message(text, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_split_message_handles_one_very_long_line():
    chunks = split_message("x" * 250, limit=100)
    assert len(chunks) == 3
    assert "".join(chunks) == "x" * 250


def test_allowlist_open_by_default():
    s = Settings(telegram_allowed_users="")
    assert _is_allowed(s, 12345) is True


def test_allowlist_restricts():
    s = Settings(telegram_allowed_users="111, 222")
    assert _is_allowed(s, 111) is True
    assert _is_allowed(s, 999) is False


@pytest.mark.asyncio
async def test_generate_reply_routes_to_engine(engine):
    reply = await generate_reply(engine, user_id=7, text="hello there")
    assert reply == "Certainly, Sir."


@pytest.mark.asyncio
async def test_generate_reply_uses_per_user_session(engine):
    await generate_reply(engine, user_id=1, text="I am user one")
    await generate_reply(engine, user_id=2, text="I am user two")
    assert engine.session(session_id_for(1)) is not engine.session(session_id_for(2))
    assert len(engine.session(session_id_for(1)).conversation) == 2


@pytest.mark.asyncio
async def test_generate_reply_sets_language_on_session(engine):
    await generate_reply(engine, user_id=5, text="privet", locale="ru")
    assert engine.session(session_id_for(5)).scratch["language"] == "ru"


@pytest.mark.asyncio
async def test_empty_model_profile_unpins_session(engine):
    # A pinned model, then an explicit "Auto" (empty profile) clears the pin.
    engine.session(session_id_for(3)).scratch["model_profile"] = "gpt"
    await generate_reply(engine, user_id=3, text="hi", model_profile="")
    assert "model_profile" not in engine.session(session_id_for(3)).scratch


@pytest.mark.asyncio
async def test_match_input_language_clears_forced_language(engine):
    # A prior text turn forced Russian; a voice turn should reply in whatever
    # language was spoken, so the forced language is cleared.
    engine.session(session_id_for(9)).scratch["language"] = "ru"
    await generate_reply(engine, user_id=9, text="hello in english",
                        locale="ru", match_input_language=True)
    assert "language" not in engine.session(session_id_for(9)).scratch


@pytest.mark.asyncio
async def test_return_metadata_false_keeps_the_plain_string_return(engine):
    # Default behaviour is unchanged — every existing caller keeps working.
    reply = await generate_reply(engine, user_id=11, text="hi")
    assert isinstance(reply, str)


# -- principal_session_id: unifying Telegram with a linked account's session --
#
# See jarvis.interfaces.telegram_bot.principal_session_id and the audit that
# found the bot and the API used two permanently different session-key
# schemes even after /link. These tests use a tiny fake in place of
# LicenseService — the real class needs a SQLite file and pairing flow
# already covered by tests/test_licensing.py; this only needs its two-method
# shape (get_account_by_telegram) to prove the key-resolution logic itself.

class _FakeAccount:
    def __init__(self, username: str) -> None:
        self.username = username


class _FakeLicenseService:
    def __init__(self, linked: dict[int, str] | None = None, *, boom: bool = False):
        self._linked = linked or {}
        self._boom = boom

    def get_account_by_telegram(self, telegram_user_id: int):
        if self._boom:
            raise RuntimeError("database is on fire")
        username = self._linked.get(telegram_user_id)
        return _FakeAccount(username) if username else None


def test_principal_session_id_with_no_service_is_unchanged():
    assert principal_session_id(42, None) == session_id_for(42)


def test_principal_session_id_unlinked_user_falls_back():
    service = _FakeLicenseService(linked={})
    assert principal_session_id(42, service) == "tg-42"


def test_principal_session_id_linked_user_shares_the_api_scheme():
    # Must match jarvis.api.app._scoped's own f"{principal}::{session_id}"
    # shape exactly, or the two sides still never see the same rows.
    service = _FakeLicenseService(linked={555: "alice"})
    assert principal_session_id(555, service) == "user:alice::default"


def test_principal_session_id_survives_a_lookup_failure():
    # A broken auth DB must never take chat down with it — fall back exactly
    # like an unlinked user rather than raising into the caller.
    service = _FakeLicenseService(boom=True)
    assert principal_session_id(1, service) == "tg-1"


@pytest.mark.asyncio
async def test_generate_reply_honours_an_explicit_session_id(engine):
    # This is what run()'s handlers now pass — principal_session_id's output —
    # so a linked account's chat lands in the shared session, not tg-<id>.
    await generate_reply(engine, user_id=999, text="hello from telegram",
                        session_id="user:alice::default")
    assert engine.session("user:alice::default").conversation
    # And the old per-telegram-id session was never touched.
    assert not engine.session(session_id_for(999)).conversation


@pytest.mark.asyncio
async def test_generate_reply_without_session_id_keeps_old_behaviour(engine):
    # No session_id given (every pre-existing test above, and any caller that
    # hasn't been updated) — falls back to tg-<user_id>, unchanged.
    await generate_reply(engine, user_id=1000, text="hi")
    assert engine.session(session_id_for(1000)).conversation


@pytest.mark.asyncio
async def test_return_metadata_true_returns_a_tuple(engine):
    reply, metadata = await generate_reply(
        engine, user_id=12, text="hi", return_metadata=True)
    assert reply == "Certainly, Sir."
    assert isinstance(metadata, dict)


@pytest.mark.asyncio
async def test_plan_images_defaults_to_allowed(engine):
    await generate_reply(engine, user_id=13, text="hi")
    assert engine.session(session_id_for(13)).scratch["plan_images"] is True


@pytest.mark.asyncio
async def test_plan_images_false_is_stashed_on_scratch(engine):
    await generate_reply(engine, user_id=14, text="hi", plan_images=False)
    assert engine.session(session_id_for(14)).scratch["plan_images"] is False


@pytest.mark.asyncio
async def test_source_flows_onto_the_request(engine, fake_provider):
    # source="voice" is what tells the engine to use the fast model / shorter
    # tool-round budget / concise-reply hint (see test_engine.py for that).
    await generate_reply(engine, user_id=15, text="hi", source="voice")
    assert fake_provider.calls  # sanity: the engine actually ran a completion


# --- subscription gate on menu buttons -------------------------------------
#
# The gate used to guard /start, free text and voice but not callbacks, so the
# whole menu stayed reachable by button for someone who had never joined the
# channel — or who had joined once and left.


def test_menu_buttons_are_gated_for_ordinary_users():
    assert menu_action_is_gated("memory", is_admin=False) is True
    assert menu_action_is_gated("tariffs", is_admin=False) is True
    assert menu_action_is_gated("main", is_admin=False) is True


def test_checksub_is_never_gated():
    # Gating it would make the only way out of the gate screen unreachable.
    assert menu_action_is_gated("checksub", is_admin=False) is False


def test_admins_bypass_the_gate():
    # An owner who has not joined their own channel must still reach the panel.
    assert menu_action_is_gated("adminpanel", is_admin=True) is False
    assert menu_action_is_gated("memory", is_admin=True) is False
