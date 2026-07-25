"""Tests for the `api` chat command, model search, and VIP tier."""

from __future__ import annotations

from jarvis.config.settings import Settings
from jarvis.interfaces.bot_menu import screen_search
from jarvis.interfaces.chat_api import detect_key_provider, parse_api_command
from jarvis.interfaces.model_search import normalize, search


def _flat(rows):
    return [data for row in rows for _, data in row]


# -- api command parser -------------------------------------------------------


def test_detect_key_provider():
    assert detect_key_provider("sk-or-v1-" + "x" * 20) == "openrouter"
    assert detect_key_provider("sk-ant-" + "x" * 20) == "anthropic"
    assert detect_key_provider("sk-" + "x" * 20) == "openai"
    assert detect_key_provider("deepseek") is None
    assert detect_key_provider("sk-short") is None  # too short


def test_parse_key_command():
    key = "sk-or-v1-" + "a" * 30
    assert parse_api_command(f"api {key}") == ("key", "openrouter", key)
    assert parse_api_command(f"апи = {key}") == ("key", "openrouter", key)


def test_parse_search_command():
    assert parse_api_command("api deepseek") == ("search", "deepseek", "")
    assert parse_api_command("api free") == ("search", "free", "")
    # A provider prefix is stripped from the query.
    assert parse_api_command("api = openrouter/gpt 4o") == ("search", "gpt 4o", "")


def test_parse_ignores_non_command_and_long_questions():
    assert parse_api_command("hello there") is None
    # A long sentence that merely starts with "api" isn't hijacked…
    assert parse_api_command("api documentation for the stripe payments thing") is None
    # …but an explicit "api = …" always searches, however long.
    got = parse_api_command("api = documentation for the stripe payments thing")
    assert got[0] == "search"


def test_parse_help():
    assert parse_api_command("api") == ("help", "", "")


# -- model search -------------------------------------------------------------


def _models():
    return normalize([
        {"id": "deepseek/deepseek-chat", "name": "DeepSeek V3",
        "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "openai/gpt-4o", "name": "GPT-4o",
        "pricing": {"prompt": "0.005", "completion": "0.015"}},
        {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B",
        "pricing": {"prompt": "0", "completion": "0"}},
    ])


def test_normalize_captures_description_and_hint():
    models = normalize([
        {"id": "deepseek/deepseek-coder", "name": "DeepSeek Coder",
        "description": "A model tuned for code.", "pricing": {"prompt": "0"}},
        {"id": "openai/o1", "name": "o1", "pricing": {"prompt": "1"}},
        {"id": "openai/gpt-4o-mini", "name": "GPT-4o mini", "pricing": {"prompt": "1"}},
    ])
    by = {m.slug: m for m in models}
    assert by["deepseek/deepseek-coder"].description == "A model tuned for code."
    assert "coding" in by["deepseek/deepseek-coder"].hint
    assert "reasoning" in by["openai/o1"].hint
    assert "fast" in by["openai/gpt-4o-mini"].hint


def test_normalize_marks_free():
    by = {m.slug: m for m in _models()}
    assert by["deepseek/deepseek-chat"].free is True
    assert by["meta-llama/llama-3.3-70b-instruct:free"].free is True
    assert by["openai/gpt-4o"].free is False


def test_search_by_name_free_and_paid():
    models = _models()
    assert [m.slug for m in search(models, "deepseek")] == ["deepseek/deepseek-chat"]
    assert {m.slug for m in search(models, "free")} == {
        "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct:free"}
    assert [m.slug for m in search(models, "платные")] == ["openai/gpt-4o"]
    assert search(models, "nonexistent-xyz") == []


def test_screen_search_lists_results_with_pick_buttons():
    text, rows = screen_search("en", _models())
    assert "Found" in text
    flat = _flat(rows)
    assert "m:pick:0" in flat and "m:pick:2" in flat
    empty_text, empty_rows = screen_search("en", [])
    assert "Nothing" in empty_text
    assert "m:pick:0" not in _flat(empty_rows)


# -- VIP tier -----------------------------------------------------------------


def test_vip_ids_parsed():
    s = Settings(telegram_vip_users="111, 222, junk", log_file="")
    assert s.telegram_vips() == {111, 222}
    assert Settings(log_file="").telegram_vips() == set()
