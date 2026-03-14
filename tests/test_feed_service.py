"""Tests for the feed service business logic."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from rss_is_terminal.models.database import Database
from rss_is_terminal.services.feed_service import FeedService, _entries_to_dicts
from rss_is_terminal.services.fetcher import EntryData, FeedFetcher, FetchResult
from rss_is_terminal.services.scraper import Scraper


@pytest_asyncio.fixture
async def service(db):
    """FeedService with real DB and mocked fetcher/scraper."""
    fetcher = MagicMock(spec=FeedFetcher)
    scraper = MagicMock(spec=Scraper)
    return FeedService(db, fetcher, scraper)


class TestAddFeed:
    @pytest.mark.asyncio
    async def test_add_feed_success(self, service):
        service.fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="https://example.com/feed",
            feed_title="Example",
            site_url="https://example.com",
            description="A feed",
            entries=[
                EntryData(guid="1", title="Post 1", url="https://example.com/1"),
                EntryData(guid="2", title="Post 2", url="https://example.com/2"),
            ],
        ))

        feed_id, error = await service.add_feed("https://example.com/feed")
        assert error is None
        assert feed_id > 0

        feed = await service.db.get_feed(feed_id)
        assert feed["title"] == "Example"

        articles = await service.db.get_articles(feed_id)
        assert len(articles) == 2

    @pytest.mark.asyncio
    async def test_add_feed_with_categories(self, service):
        service.fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="https://example.com/feed",
            feed_title="Example",
            entries=[],
        ))

        cat_id = await service.db.add_category("Tech")
        feed_id, error = await service.add_feed("https://example.com/feed", category_ids=[cat_id])
        assert error is None

        cats = await service.db.get_feed_categories(feed_id)
        assert len(cats) == 1
        assert cats[0]["id"] == cat_id

    @pytest.mark.asyncio
    async def test_add_feed_fetch_error(self, service):
        service.fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="https://example.com/feed",
            error="Connection refused",
        ))

        feed_id, error = await service.add_feed("https://example.com/feed")
        assert error == "Connection refused"
        assert feed_id == -1

    @pytest.mark.asyncio
    async def test_add_feed_duplicate(self, service):
        service.fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="https://example.com/feed",
            feed_title="Example",
            entries=[],
        ))

        await service.add_feed("https://example.com/feed")
        feed_id, error = await service.add_feed("https://example.com/feed")
        assert error == "Feed already exists"

    @pytest.mark.asyncio
    async def test_add_feed_uses_url_as_title_fallback(self, service):
        service.fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="https://example.com/feed",
            feed_title=None,
            entries=[],
        ))

        feed_id, error = await service.add_feed("https://example.com/feed")
        feed = await service.db.get_feed(feed_id)
        assert feed["title"] == "https://example.com/feed"


class TestRefreshFeed:
    @pytest.mark.asyncio
    async def test_refresh_rss_feed(self, service):
        service.fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="https://example.com/feed",
            feed_title="Example",
            entries=[EntryData(guid="1", title="Post")],
        ))

        feed_id = await service.db.add_feed(
            url="https://example.com/feed", title="Example"
        )

        error = await service.refresh_feed(feed_id)
        assert error is None

        articles = await service.db.get_articles(feed_id)
        assert len(articles) == 1

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_feed(self, service):
        error = await service.refresh_feed(9999)
        assert error == "Feed not found"

    @pytest.mark.asyncio
    async def test_refresh_feed_with_error(self, service):
        service.fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="https://example.com/feed",
            error="Timeout",
        ))

        feed_id = await service.db.add_feed(
            url="https://example.com/feed", title="Example"
        )

        error = await service.refresh_feed(feed_id)
        assert error == "Timeout"

        feed = await service.db.get_feed(feed_id)
        assert feed["fetch_error"] == "Timeout"

    @pytest.mark.asyncio
    async def test_refresh_updates_title(self, service):
        service.fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="https://example.com/feed",
            feed_title="New Title",
            entries=[],
        ))

        feed_id = await service.db.add_feed(
            url="https://example.com/feed", title="Old Title"
        )

        await service.refresh_feed(feed_id)
        feed = await service.db.get_feed(feed_id)
        assert feed["title"] == "New Title"


class TestRefreshAll:
    @pytest.mark.asyncio
    async def test_refresh_all(self, service):
        feed1 = await service.db.add_feed(url="https://a.com/feed", title="A")
        feed2 = await service.db.add_feed(url="https://b.com/feed", title="B")

        service.fetcher.fetch_all = AsyncMock(return_value={
            feed1: FetchResult(
                url="https://a.com/feed",
                entries=[EntryData(guid="1", title="Post A")],
            ),
            feed2: FetchResult(
                url="https://b.com/feed",
                error="Failed",
            ),
        })

        errors = await service.refresh_all()
        assert errors[feed1] is None
        assert errors[feed2] == "Failed"

    @pytest.mark.asyncio
    async def test_refresh_all_empty(self, service):
        errors = await service.refresh_all()
        assert errors == {}


class TestDeleteFeed:
    @pytest.mark.asyncio
    async def test_delete_feed(self, service):
        feed_id = await service.db.add_feed(
            url="https://example.com/feed", title="Doomed"
        )
        await service.delete_feed(feed_id)

        feed = await service.db.get_feed(feed_id)
        assert feed is None


class TestAddScraperFeed:
    @pytest.mark.asyncio
    async def test_no_scraper_available(self, db):
        fetcher = MagicMock(spec=FeedFetcher)
        service = FeedService(db, fetcher, scraper=None)

        feed_id, error = await service.add_scraper_feed(Path("/tmp/config.json"))
        assert error == "Scraper not available"

    @pytest.mark.asyncio
    async def test_invalid_config(self, service, tmp_path):
        bad_config = tmp_path / "bad.json"
        bad_config.write_text("not json")

        feed_id, error = await service.add_scraper_feed(bad_config)
        assert "Invalid config" in error


class TestEntriesToDicts:
    def test_converts_entries(self):
        entries = [
            EntryData(guid="1", title="Test", url="https://example.com",
                      author="Alice", published_at="2026-01-15", summary="Short",
                      content="<p>Full</p>"),
        ]
        result = _entries_to_dicts(entries)
        assert len(result) == 1
        assert result[0]["guid"] == "1"
        assert result[0]["title"] == "Test"
        assert result[0]["content"] == "<p>Full</p>"

    def test_handles_none_fields(self):
        entries = [EntryData(guid="1", title="Test")]
        result = _entries_to_dicts(entries)
        assert result[0]["url"] is None
        assert result[0]["author"] is None
