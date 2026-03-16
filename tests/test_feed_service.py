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


class TestRefreshScraperFeed:
    @pytest.mark.asyncio
    async def test_refresh_scraper_feed(self, service, tmp_path):
        """Test the two-phase scraper refresh: listing + content backfill."""
        import json

        config_data = {
            "name": "Test Blog",
            "url": "https://example.com/blog",
            "article_selector": "div.post",
            "fields": {
                "title": "h2",
                "url": "a @href",
            },
        }
        config_file = tmp_path / "scraper.json"
        config_file.write_text(json.dumps(config_data))

        feed_id = await service.db.add_feed(
            url="https://example.com/blog",
            title="Test Blog",
            feed_type="scraper",
            scraper_config_path=str(config_file),
        )

        # Mock the scraper to return entries
        service.scraper.scrape = AsyncMock(return_value=[
            EntryData(guid="1", title="Post 1", url="https://example.com/1", summary="Short"),
        ])
        service.scraper.fetch_full_content = AsyncMock()

        error = await service.refresh_feed(feed_id)
        assert error is None

        articles = await service.db.get_articles(feed_id)
        assert len(articles) == 1
        assert articles[0]["title"] == "Post 1"

    @pytest.mark.asyncio
    async def test_refresh_scraper_no_scraper(self, db):
        """Refresh should fail gracefully when scraper is unavailable."""
        fetcher = MagicMock(spec=FeedFetcher)
        svc = FeedService(db, fetcher, scraper=None)

        feed_id = await db.add_feed(
            url="https://example.com/blog",
            title="Test",
            feed_type="scraper",
            scraper_config_path="/tmp/fake.json",
        )

        error = await svc.refresh_feed(feed_id)
        assert error == "Scraper not available"

    @pytest.mark.asyncio
    async def test_refresh_scraper_no_config_path(self, service):
        """Refresh should fail if the feed has no scraper config path."""
        feed_id = await service.db.add_feed(
            url="https://example.com/blog",
            title="Test",
            feed_type="scraper",
        )

        error = await service.refresh_feed(feed_id)
        assert error == "No scraper config path"

    @pytest.mark.asyncio
    async def test_refresh_scraper_scrape_error(self, service, tmp_path):
        """Refresh should handle scrape failures gracefully."""
        import json

        config_data = {
            "name": "Test",
            "url": "https://example.com",
            "article_selector": "div",
            "fields": {"title": "h2"},
        }
        config_file = tmp_path / "scraper.json"
        config_file.write_text(json.dumps(config_data))

        feed_id = await service.db.add_feed(
            url="https://example.com",
            title="Test",
            feed_type="scraper",
            scraper_config_path=str(config_file),
        )

        service.scraper.scrape = AsyncMock(side_effect=RuntimeError("Network error"))

        error = await service.refresh_feed(feed_id)
        assert "Network error" in error

        feed = await service.db.get_feed(feed_id)
        assert "Network error" in feed["fetch_error"]

    @pytest.mark.asyncio
    async def test_refresh_scraper_content_backfill_failure_non_fatal(self, service, tmp_path):
        """Content backfill failure should not prevent the refresh from succeeding."""
        import json

        config_data = {
            "name": "Test",
            "url": "https://example.com",
            "article_selector": "div",
            "fields": {"title": "h2"},
        }
        config_file = tmp_path / "scraper.json"
        config_file.write_text(json.dumps(config_data))

        feed_id = await service.db.add_feed(
            url="https://example.com",
            title="Test",
            feed_type="scraper",
            scraper_config_path=str(config_file),
        )

        service.scraper.scrape = AsyncMock(return_value=[
            EntryData(guid="1", title="Post", url="https://example.com/1", summary="Short"),
        ])
        service.scraper.fetch_full_content = AsyncMock(side_effect=RuntimeError("Timeout"))

        error = await service.refresh_feed(feed_id)
        assert error is None  # Content backfill failure is non-fatal

        articles = await service.db.get_articles(feed_id)
        assert len(articles) == 1


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
