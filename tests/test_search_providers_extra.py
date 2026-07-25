"""Tests for the Perplexity + Playwright providers and search tool."""

from __future__ import annotations

import pytest

from jarvis.config.settings import Settings
from jarvis.search.manager import SearchManager
from jarvis.search.providers import PerplexityProvider, PlaywrightProvider
from jarvis.search.tools import WebSearchSkill


# -- Perplexity (pure parse) --------------------------------------------------


def test_perplexity_parse_answer_and_citations():
    raw = {
        "choices": [{"message": {"content": "Paris is the capital of France."}}],
        "citations": ["https://a.com", "https://b.com"],
    }
    res = PerplexityProvider.parse(raw)
    assert res[0].source == "perplexity"
    assert "Paris" in res[0].snippet
    assert {r.url for r in res} >= {"https://a.com", "https://b.com"}


def test_perplexity_parse_empty():
    assert PerplexityProvider.parse({}) == []


def test_perplexity_requires_key():
    assert PerplexityProvider("").available() is False
    assert PerplexityProvider("k").available() is True


# -- Playwright (availability + pure parse) -----------------------------------


def test_playwright_available_only_when_installed():
    """Readiness must track the real import, in either direction."""
    try:
        import playwright  # noqa: F401
        installed = True
    except ImportError:
        installed = False
    assert PlaywrightProvider().available() is installed


def test_playwright_parse_pure():
    items = [{"title": " A ", "url": "https://a.com", "snippet": " s "},
            {"title": "no url"}]
    res = PlaywrightProvider.parse(items)
    assert len(res) == 1 and res[0].title == "A" and res[0].snippet == "s"


# -- routing includes new providers ------------------------------------------


def test_manager_includes_perplexity_and_playwright():
    mgr = SearchManager.from_settings(Settings(log_file=""))
    provs = mgr.providers()
    assert "perplexity" in provs and "playwright" in provs
    # DuckDuckGo still the keyless fallback; tavily still first.
    assert provs[0] == "tavily"
    # Keyless backends only: DuckDuckGo, plus the browser if Playwright is there.
    expected = ["duckduckgo"]
    if PlaywrightProvider().available():
        expected.append("playwright")
    assert mgr.available() == expected


# -- web search tool ----------------------------------------------------------


class _FakeManager:
    async def search(self, query, *, limit=5):
        from jarvis.search.base import SearchResult
        return [SearchResult("Title", "https://x.com", "snippet", "fake")]


@pytest.mark.asyncio
async def test_web_search_skill_formats_results():
    skill = WebSearchSkill(_FakeManager())
    out = await skill.execute(query="weather")
    assert "https://x.com" in out.text and "Title" in out.text


@pytest.mark.asyncio
async def test_web_search_skill_empty_query():
    out = await WebSearchSkill(_FakeManager()).execute(query="  ")
    assert "provide a search query" in out.text.lower()
