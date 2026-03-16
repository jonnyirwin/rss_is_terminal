"""Tests for the web scraper engine."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from rss_is_terminal.services.fetcher import EntryData
from rss_is_terminal.services.scraper import Scraper, _parse_date
from rss_is_terminal.services.scraper_config import (
    FieldSelector,
    PaginationConfig,
    ScraperConfig,
)


class TestParseDate:
    def test_iso_format(self):
        assert _parse_date("2026-01-15T10:30:00") is not None
        assert "2026-01-15" in _parse_date("2026-01-15T10:30:00")

    def test_iso_with_z(self):
        result = _parse_date("2026-01-15T10:30:00Z")
        assert result is not None
        assert "2026-01-15" in result

    def test_iso_with_timezone(self):
        result = _parse_date("2026-01-15T10:30:00+05:00")
        assert result is not None

    def test_date_only(self):
        result = _parse_date("2026-01-15")
        assert result is not None
        assert "2026-01-15" in result

    def test_long_month_format(self):
        result = _parse_date("January 15, 2026")
        assert result is not None

    def test_short_month_format(self):
        result = _parse_date("Jan 15, 2026")
        assert result is not None

    def test_european_format(self):
        result = _parse_date("15 January 2026")
        assert result is not None

    def test_none_input(self):
        assert _parse_date(None) is None

    def test_unparseable(self):
        assert _parse_date("not a date") is None

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_whitespace_stripped(self):
        result = _parse_date("  2026-01-15  ")
        assert result is not None


class TestScraperExtraction:
    """Test the scraper's HTML extraction without network calls."""

    def _make_config(self, **overrides):
        defaults = {
            "name": "Test",
            "url": "https://example.com",
            "article_selector": "div.post",
            "fields": {
                "title": FieldSelector(css="h2"),
                "url": FieldSelector(css="a", attribute="href"),
            },
        }
        defaults.update(overrides)
        return ScraperConfig(**defaults)

    def test_extract_basic_entries(self):
        from bs4 import BeautifulSoup

        html = """
        <div class="post">
            <h2>First Post</h2>
            <a href="/post/1">Read</a>
        </div>
        <div class="post">
            <h2>Second Post</h2>
            <a href="/post/2">Read</a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        config = self._make_config()
        scraper = Scraper.__new__(Scraper)

        entries = scraper._extract_entries(soup, config)
        assert len(entries) == 2
        assert entries[0].title == "First Post"
        assert entries[1].title == "Second Post"

    def test_extract_with_attribute(self):
        from bs4 import BeautifulSoup

        html = """
        <div class="post">
            <h2>Post</h2>
            <a href="https://example.com/1">Link</a>
            <time datetime="2026-01-15">Jan 15</time>
        </div>
        """
        config = self._make_config(
            fields={
                "title": FieldSelector(css="h2"),
                "url": FieldSelector(css="a", attribute="href"),
                "date": FieldSelector(css="time", attribute="datetime"),
            }
        )
        soup = BeautifulSoup(html, "html.parser")
        scraper = Scraper.__new__(Scraper)

        entries = scraper._extract_entries(soup, config)
        assert len(entries) == 1
        assert entries[0].url == "https://example.com/1"
        assert entries[0].published_at is not None

    def test_extract_relative_urls_resolved(self):
        from bs4 import BeautifulSoup

        html = """
        <div class="post">
            <h2>Post</h2>
            <a href="/article/1">Link</a>
        </div>
        """
        config = self._make_config()
        soup = BeautifulSoup(html, "html.parser")
        scraper = Scraper.__new__(Scraper)

        entries = scraper._extract_entries(soup, config)
        assert entries[0].url == "https://example.com/article/1"

    def test_extract_missing_field_uses_default(self):
        from bs4 import BeautifulSoup

        html = """
        <div class="post">
            <a href="/1">Link</a>
        </div>
        """
        config = self._make_config()
        soup = BeautifulSoup(html, "html.parser")
        scraper = Scraper.__new__(Scraper)

        entries = scraper._extract_entries(soup, config)
        assert entries[0].title == "(no title)"

    def test_extract_no_matches(self):
        from bs4 import BeautifulSoup

        html = "<div class='other'>Nothing here</div>"
        config = self._make_config()
        soup = BeautifulSoup(html, "html.parser")
        scraper = Scraper.__new__(Scraper)

        entries = scraper._extract_entries(soup, config)
        assert len(entries) == 0

    def test_guid_falls_back_to_title(self):
        from bs4 import BeautifulSoup

        html = """
        <div class="post">
            <h2>Unique Title</h2>
        </div>
        """
        config = self._make_config(
            fields={"title": FieldSelector(css="h2")}
        )
        soup = BeautifulSoup(html, "html.parser")
        scraper = Scraper.__new__(Scraper)

        entries = scraper._extract_entries(soup, config)
        assert entries[0].guid == "Unique Title"


@pytest.mark.asyncio
async def test_scrape_static_page(httpx_mock):
    """Test full scrape pipeline with mocked HTTP."""
    import httpx

    html = """
    <html><body>
        <div class="post">
            <h2><a href="https://example.com/1">First</a></h2>
            <span class="author">Alice</span>
        </div>
        <div class="post">
            <h2><a href="https://example.com/2">Second</a></h2>
            <span class="author">Bob</span>
        </div>
    </body></html>
    """

    async with httpx.AsyncClient() as client:
        httpx_mock.add_response(url="https://example.com/blog", text=html)

        config = ScraperConfig(
            name="Test",
            url="https://example.com/blog",
            article_selector="div.post",
            fields={
                "title": FieldSelector(css="h2 a"),
                "url": FieldSelector(css="h2 a", attribute="href"),
                "author": FieldSelector(css="span.author"),
            },
        )

        scraper = Scraper(client)
        entries = await scraper.scrape(config)

        assert len(entries) == 2
        assert entries[0].title == "First"
        assert entries[0].author == "Alice"
        assert entries[1].title == "Second"
        assert entries[1].url == "https://example.com/2"


@pytest.mark.asyncio
async def test_scrape_with_pagination(httpx_mock):
    """Test scraping with pagination following next links."""

    page1 = """
    <html><body>
        <div class="post"><h2>Page1 Post</h2><a href="https://example.com/1">Link</a></div>
        <a class="next" href="/page/2">Next</a>
    </body></html>
    """
    page2 = """
    <html><body>
        <div class="post"><h2>Page2 Post</h2><a href="https://example.com/2">Link</a></div>
    </body></html>
    """

    async with httpx.AsyncClient() as client:
        httpx_mock.add_response(url="https://example.com/blog", text=page1)
        httpx_mock.add_response(url="https://example.com/page/2", text=page2)

        config = ScraperConfig(
            name="Test",
            url="https://example.com/blog",
            article_selector="div.post",
            fields={
                "title": FieldSelector(css="h2"),
                "url": FieldSelector(css="a", attribute="href"),
            },
            pagination=PaginationConfig(
                next_selector=FieldSelector(css="a.next", attribute="href"),
                max_pages=3,
            ),
        )

        scraper = Scraper(client)
        entries = await scraper.scrape(config)

        assert len(entries) == 2
        assert entries[0].title == "Page1 Post"
        assert entries[1].title == "Page2 Post"


@pytest.mark.asyncio
async def test_scrape_pagination_stops_without_next(httpx_mock):
    """Pagination stops when no next link is found."""

    page1 = """
    <html><body>
        <div class="post"><h2>Only Post</h2><a href="https://example.com/1">Link</a></div>
    </body></html>
    """

    async with httpx.AsyncClient() as client:
        httpx_mock.add_response(url="https://example.com/blog", text=page1)

        config = ScraperConfig(
            name="Test",
            url="https://example.com/blog",
            article_selector="div.post",
            fields={
                "title": FieldSelector(css="h2"),
                "url": FieldSelector(css="a", attribute="href"),
            },
            pagination=PaginationConfig(
                next_selector=FieldSelector(css="a.next", attribute="href"),
                max_pages=5,
            ),
        )

        scraper = Scraper(client)
        entries = await scraper.scrape(config)

        assert len(entries) == 1


@pytest.mark.asyncio
async def test_fetch_full_content():
    """Test that fetch_full_content populates entry content."""

    entries = [
        EntryData(guid="1", title="Post 1", url="https://example.com/1"),
        EntryData(guid="2", title="Post 2", url="https://example.com/2"),
        EntryData(guid="3", title="No URL", url=None),
    ]

    async def mock_extract(client, url):
        return f"<p>Content for {url}</p>"

    with patch("rss_is_terminal.services.scraper.extract_article", side_effect=mock_extract):
        async with httpx.AsyncClient() as client:
            scraper = Scraper(client)
            await scraper.fetch_full_content(entries)

    assert entries[0].content == "<p>Content for https://example.com/1</p>"
    assert entries[1].content == "<p>Content for https://example.com/2</p>"
    assert entries[2].content is None  # no URL, skipped


@pytest.mark.asyncio
async def test_fetch_full_content_handles_extraction_failure():
    """Entries where extraction returns None keep their original content."""

    entries = [
        EntryData(guid="1", title="Post 1", url="https://example.com/1", content="original"),
    ]

    async def mock_extract(client, url):
        return None

    with patch("rss_is_terminal.services.scraper.extract_article", side_effect=mock_extract):
        async with httpx.AsyncClient() as client:
            scraper = Scraper(client)
            await scraper.fetch_full_content(entries)

    assert entries[0].content == "original"


@pytest.mark.asyncio
async def test_fetch_page_static(httpx_mock):
    """Test _fetch_page for non-JS rendered pages."""

    httpx_mock.add_response(url="https://example.com/page", text="<html>content</html>")

    async with httpx.AsyncClient() as client:
        scraper = Scraper(client)
        config = ScraperConfig(
            name="Test",
            url="https://example.com/page",
            article_selector="div",
            fields={},
            js_render=False,
        )
        html = await scraper._fetch_page(config)
        assert "content" in html


@pytest.mark.asyncio
async def test_fetch_page_custom_url(httpx_mock):
    """Test _fetch_page with an explicit URL override."""

    httpx_mock.add_response(url="https://example.com/page2", text="<html>page2</html>")

    async with httpx.AsyncClient() as client:
        scraper = Scraper(client)
        config = ScraperConfig(
            name="Test",
            url="https://example.com/page1",
            article_selector="div",
            fields={},
        )
        html = await scraper._fetch_page(config, url="https://example.com/page2")
        assert "page2" in html
