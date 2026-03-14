"""Tests for OPML import and export."""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import pytest_asyncio

from rss_is_terminal.models.database import Database
from rss_is_terminal.services.feed_service import FeedService
from rss_is_terminal.services.fetcher import FeedFetcher, FetchResult
from rss_is_terminal.services.opml import ImportResult, export_opml, import_opml
from unittest.mock import AsyncMock, MagicMock


SAMPLE_OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Test Feeds</title></head>
  <body>
    <outline text="Tech" title="Tech">
      <outline type="rss" text="Blog A" title="Blog A"
               xmlUrl="https://a.com/feed" htmlUrl="https://a.com"/>
      <outline type="rss" text="Blog B" title="Blog B"
               xmlUrl="https://b.com/feed" htmlUrl="https://b.com"/>
    </outline>
    <outline type="rss" text="Uncategorized" title="Uncategorized"
             xmlUrl="https://c.com/feed" htmlUrl="https://c.com"/>
  </body>
</opml>
"""


@pytest_asyncio.fixture
async def feed_service(db):
    fetcher = MagicMock(spec=FeedFetcher)
    fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
        url="mock",
        feed_title="Mock Feed",
        entries=[],
    ))
    return FeedService(db, fetcher)


class TestImportOpml:
    @pytest.mark.asyncio
    async def test_import_basic(self, db, feed_service, tmp_path):
        opml_file = tmp_path / "feeds.opml"
        opml_file.write_text(SAMPLE_OPML)

        result = await import_opml(db, feed_service, opml_file)
        assert result.added == 3
        assert result.skipped == 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_import_creates_categories(self, db, feed_service, tmp_path):
        opml_file = tmp_path / "feeds.opml"
        opml_file.write_text(SAMPLE_OPML)

        await import_opml(db, feed_service, opml_file)

        categories = await db.get_categories()
        names = {c["name"] for c in categories}
        assert "Tech" in names

    @pytest.mark.asyncio
    async def test_import_categorizes_feeds(self, db, feed_service, tmp_path):
        opml_file = tmp_path / "feeds.opml"
        opml_file.write_text(SAMPLE_OPML)

        await import_opml(db, feed_service, opml_file)

        categories = await db.get_categories()
        tech_cat = next(c for c in categories if c["name"] == "Tech")
        feeds = await db.get_feeds(category_id=tech_cat["id"])
        assert len(feeds) == 2

    @pytest.mark.asyncio
    async def test_import_skips_duplicates(self, db, feed_service, tmp_path):
        opml_file = tmp_path / "feeds.opml"
        opml_file.write_text(SAMPLE_OPML)

        # Import twice
        await import_opml(db, feed_service, opml_file)
        result = await import_opml(db, feed_service, opml_file)
        assert result.skipped == 3
        assert result.added == 0

    @pytest.mark.asyncio
    async def test_import_handles_fetch_errors(self, db, tmp_path):
        fetcher = MagicMock(spec=FeedFetcher)
        fetcher.fetch_feed = AsyncMock(return_value=FetchResult(
            url="mock",
            error="Connection refused",
        ))
        service = FeedService(db, fetcher)

        opml_file = tmp_path / "feeds.opml"
        opml_file.write_text(SAMPLE_OPML)

        result = await import_opml(db, service, opml_file)
        assert len(result.errors) == 3

    @pytest.mark.asyncio
    async def test_import_invalid_opml(self, db, feed_service, tmp_path):
        opml_file = tmp_path / "bad.opml"
        opml_file.write_text("<opml><head/></opml>")

        result = await import_opml(db, feed_service, opml_file)
        assert len(result.errors) > 0
        assert "no <body>" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def test_import_sets_title_from_opml(self, db, feed_service, tmp_path):
        opml_file = tmp_path / "feeds.opml"
        opml_file.write_text(SAMPLE_OPML)

        await import_opml(db, feed_service, opml_file)

        feeds = await db.get_feeds()
        titles = {f["title"] for f in feeds}
        assert "Blog A" in titles


class TestExportOpml:
    @pytest.mark.asyncio
    async def test_export_basic(self, db, tmp_path):
        cat_id = await db.add_category("Tech")
        await db.add_feed(
            url="https://example.com/feed",
            title="Example",
            site_url="https://example.com",
            category_ids=[cat_id],
        )
        await db.add_feed(
            url="https://other.com/feed",
            title="Other",
        )

        out_file = tmp_path / "export.opml"
        await export_opml(db, out_file)

        assert out_file.exists()
        tree = ET.parse(out_file)
        root = tree.getroot()
        assert root.tag == "opml"

        body = root.find("body")
        # Should have a Tech category outline + uncategorized feed
        outlines = list(body)
        assert len(outlines) == 2  # Tech folder + uncategorized feed

    @pytest.mark.asyncio
    async def test_export_preserves_structure(self, db, tmp_path):
        cat_id = await db.add_category("News")
        await db.add_feed(
            url="https://news.com/feed",
            title="News Feed",
            site_url="https://news.com",
            category_ids=[cat_id],
        )

        out_file = tmp_path / "export.opml"
        await export_opml(db, out_file)

        tree = ET.parse(out_file)
        body = tree.getroot().find("body")

        category_outline = body.find("outline")
        assert category_outline.get("text") == "News"

        feed_outline = category_outline.find("outline")
        assert feed_outline.get("xmlUrl") == "https://news.com/feed"
        assert feed_outline.get("title") == "News Feed"

    @pytest.mark.asyncio
    async def test_export_empty_db(self, db, tmp_path):
        out_file = tmp_path / "empty.opml"
        await export_opml(db, out_file)

        tree = ET.parse(out_file)
        body = tree.getroot().find("body")
        assert len(list(body)) == 0

    @pytest.mark.asyncio
    async def test_roundtrip(self, db, feed_service, tmp_path):
        """Import then export should preserve feeds."""
        opml_in = tmp_path / "in.opml"
        opml_in.write_text(SAMPLE_OPML)

        await import_opml(db, feed_service, opml_in)

        opml_out = tmp_path / "out.opml"
        await export_opml(db, opml_out)

        tree = ET.parse(opml_out)
        body = tree.getroot().find("body")

        # Should have Tech category + uncategorized feed
        all_feeds = list(body.iter("outline"))
        # Filter to actual feed entries (have xmlUrl)
        feed_entries = [o for o in all_feeds if o.get("xmlUrl")]
        assert len(feed_entries) == 3
