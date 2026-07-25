"""Tests for the Search Manager framework (parsing, availability, routing)."""

from __future__ import annotations

import pytest

from jarvis.config.settings import Settings
from jarvis.search import SearchError, SearchManager, SearchResult
from jarvis.search.base import SearchProvider
from jarvis.search.providers import (
    BraveProvider,
    DuckDuckGoProvider,
    GoogleCSEProvider,
    TavilyProvider,
)


# -- parsing (pure, no network) ----------------------------------------------


def test_tavily_parse():
    raw = {"results": [
        {"title": "A", "url": "https://a.com", "content": "about a"},
        {"title": "B", "url": "https://b.com", "content": "about b"},
        {"title": "no url", "content": "skip"},
    ]}
    res = TavilyProvider.parse(raw)
    assert [r.url for r in res] == ["https://a.com", "https://b.com"]
    assert res[0].source == "tavily" and res[0].snippet == "about a"


def test_brave_parse():
    raw = {"web": {"results": [
        {"title": "T", "url": "https://t.com", "description": "d"}]}}
    res = BraveProvider.parse(raw)
    assert res[0].url == "https://t.com" and res[0].source == "brave"


def test_duckduckgo_parse_html_results():
    # A trimmed sample of DuckDuckGo's HTML results page.
    page = (
        '<a class="result__a" href="https://x.com/page">X <b>thing</b></a>'
        '<a class="result__snippet">About X thing.</a>'
        '<a class="result__a" href="//duckduckgo.com/l/?uddg='
        'https%3A%2F%2Fy.com%2Fdoc&rut=1">Y thing</a>'
        '<a class="result__snippet">Details on Y.</a>')
    res = DuckDuckGoProvider.parse(page)
    assert [r.url for r in res] == ["https://x.com/page", "https://y.com/doc"]
    assert res[0].title == "X thing"                 # HTML tags stripped
    assert res[0].snippet == "About X thing."
    assert res[1].url == "https://y.com/doc"          # uddg redirect unwrapped


# -- availability -------------------------------------------------------------


def test_availability_depends_on_key():
    assert TavilyProvider("").available() is False
    assert TavilyProvider("k").available() is True
    assert DuckDuckGoProvider().available() is True     # no key needed
    # Google needs both key and cx.
    assert GoogleCSEProvider("k").available() is False
    assert GoogleCSEProvider("k", cx="c").available() is True


# -- manager routing ----------------------------------------------------------


def test_manager_lists_and_falls_back_to_ddg():
    mgr = SearchManager.from_settings(Settings(log_file=""))
    # With no keys the only ready backends are the keyless ones: DuckDuckGo
    # always, plus the browser provider when Playwright happens to be installed.
    expected = ["duckduckgo"]
    from jarvis.search.providers import PlaywrightProvider
    if PlaywrightProvider().available():
        expected.append("playwright")
    assert mgr.available() == expected
    assert mgr.providers()[0] == "tavily"       # priority order preserved


def test_manager_prefers_named_and_available_first():
    s = Settings(log_file="", tavily_api_key="k", brave_api_key="k")
    mgr = SearchManager.from_settings(s)
    avail = mgr.available()
    assert "tavily" in avail and "brave" in avail and "duckduckgo" in avail
    # auto → first available in priority order = tavily
    assert mgr._pick("auto").name == "tavily"
    # named pick honoured when available
    assert mgr._pick("brave").name == "brave"
    # named but unavailable → None
    assert mgr._pick("exa") is None


@pytest.mark.asyncio
async def test_manager_search_uses_provider(monkeypatch):
    class FakeProvider(SearchProvider):
        name = "fake"
        requires_key = False

        async def search(self, query, *, limit=5):
            return [SearchResult("hit", "https://z.com", query, "fake")]

    mgr = SearchManager([FakeProvider()], default="auto")
    res = await mgr.search("weather", limit=3)
    assert res[0].url == "https://z.com" and res[0].snippet == "weather"


@pytest.mark.asyncio
async def test_manager_raises_when_nothing_available():
    class Off(SearchProvider):
        name = "off"
        requires_key = True

        async def search(self, query, *, limit=5):
            return []

    mgr = SearchManager([Off("")])   # no key → unavailable
    with pytest.raises(SearchError):
        await mgr.search("x")
