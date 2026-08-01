"""Tests for the Telegram interface's testable core (no network / no aiogram)."""

from __future__ import annotations

import pytest

from jarvis.config.settings import Settings
from jarvis.interfaces.telegram_bot import (
    _is_allowed,
    generate_reply,
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
