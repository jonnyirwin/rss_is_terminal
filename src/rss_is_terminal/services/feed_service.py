"""Feed management business logic."""

from __future__ import annotations

from pathlib import Path
from shutil import copy2

from ..config import config_dir
from ..models.database import Database
from .fetcher import FeedFetcher, FetchResult
from .scraper import Scraper
from .scraper_config import load_config


def _scrapers_dir() -> Path:
    path = config_dir() / "scrapers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _entries_to_dicts(entries) -> list[dict]:
    return [
        {
            "guid": e.guid,
            "title": e.title,
            "url": e.url,
            "author": e.author,
            "published_at": e.published_at,
            "summary": e.summary,
            "content": e.content,
        }
        for e in entries
    ]


class FeedService:
    def __init__(self, db: Database, fetcher: FeedFetcher, scraper: Scraper | None = None) -> None:
        self.db = db
        self.fetcher = fetcher
        self.scraper = scraper

    async def add_feed(self, url: str, category_ids: list[int] | None = None) -> tuple[int, str | None]:
        """Add a new feed. Returns (feed_id, error_message)."""
        result = await self.fetcher.fetch_feed(url)
        if result.error:
            return -1, result.error

        title = result.feed_title or url
        try:
            feed_id = await self.db.add_feed(
                url=url,
                title=title,
                site_url=result.site_url,
                description=result.description,
                category_ids=category_ids,
            )
        except Exception as e:
            if "UNIQUE" in str(e):
                return -1, "Feed already exists"
            return -1, str(e)

        await self.db.upsert_articles(feed_id, _entries_to_dicts(result.entries))
        return feed_id, None

    async def add_scraper_feed(
        self, config_path: Path, category_ids: list[int] | None = None
    ) -> tuple[int, str | None]:
        """Add a scraper feed from a JSON config. Returns (feed_id, error_message)."""
        if not self.scraper:
            return -1, "Scraper not available"

        try:
            config = load_config(config_path)
        except Exception as e:
            return -1, f"Invalid config: {e}"

        try:
            entries = await self.scraper.scrape(config)
        except Exception as e:
            return -1, f"Scrape failed: {e}"

        # Copy config to scrapers dir for self-contained storage
        dest = _scrapers_dir() / config_path.name
        if dest != config_path.resolve():
            copy2(config_path, dest)

        try:
            feed_id = await self.db.add_feed(
                url=config.url,
                title=config.name,
                category_ids=category_ids,
                feed_type="scraper",
                scraper_config_path=str(dest),
            )
        except Exception as e:
            if "UNIQUE" in str(e):
                return -1, "Feed already exists"
            return -1, str(e)

        await self.db.upsert_articles(feed_id, _entries_to_dicts(entries))
        return feed_id, None

    async def refresh_feed(self, feed_id: int) -> str | None:
        """Refresh a single feed. Returns error message or None."""
        feed = await self.db.get_feed(feed_id)
        if not feed:
            return "Feed not found"

        if feed["feed_type"] == "scraper":
            return await self._refresh_scraper_feed(feed)

        result = await self.fetcher.fetch_feed(feed["url"])
        if result.error:
            await self.db.update_feed(feed_id, fetch_error=result.error)
            return result.error

        await self.db.upsert_articles(feed_id, _entries_to_dicts(result.entries))
        if result.feed_title:
            await self.db.update_feed(feed_id, title=result.feed_title)
        return None

    async def _refresh_scraper_feed(self, feed) -> str | None:
        """Refresh a scraper-type feed.

        Two phases:
        1. Scrape the listing page and upsert articles (fast — shows up immediately)
        2. Backfill full content for articles that only have a summary
        """
        if not self.scraper:
            return "Scraper not available"

        config_path = feed["scraper_config_path"]
        if not config_path:
            return "No scraper config path"

        # Phase 1: scrape listing and upsert
        try:
            config = load_config(Path(config_path))
            entries = await self.scraper.scrape(config)
        except Exception as e:
            error = str(e)
            await self.db.update_feed(feed["id"], fetch_error=error)
            return error

        await self.db.upsert_articles(feed["id"], _entries_to_dicts(entries))

        # Phase 2: backfill full content for articles missing it
        try:
            rows = await self.db.get_articles_without_content(feed["id"])
            if rows:
                # Build EntryData for articles needing content
                from .fetcher import EntryData
                to_fetch = [
                    EntryData(guid=r["guid"], title=r["title"], url=r["url"])
                    for r in rows if r["url"]
                ]
                if to_fetch:
                    await self.scraper.fetch_full_content(to_fetch)
                    # Update just the content for these articles
                    for entry in to_fetch:
                        if entry.content:
                            await self.db.update_article_content(
                                feed["id"], entry.guid, entry.content
                            )
        except Exception:
            pass  # Content fetch failure shouldn't block the feed

        return None

    async def refresh_all(self) -> dict[int, str | None]:
        """Refresh all feeds. Returns {feed_id: error_or_none}."""
        feeds = await self.db.get_feeds()
        if not feeds:
            return {}

        # Split into RSS and scraper feeds
        rss_feeds = [(f["id"], f["url"]) for f in feeds if f["feed_type"] != "scraper"]
        scraper_feeds = [f for f in feeds if f["feed_type"] == "scraper"]

        errors: dict[int, str | None] = {}

        # Refresh RSS feeds concurrently
        if rss_feeds:
            results = await self.fetcher.fetch_all(rss_feeds)
            for feed_id, result in results.items():
                if result.error:
                    await self.db.update_feed(feed_id, fetch_error=result.error)
                    errors[feed_id] = result.error
                else:
                    await self.db.upsert_articles(feed_id, _entries_to_dicts(result.entries))
                    errors[feed_id] = None

        # Refresh scraper feeds
        for feed in scraper_feeds:
            error = await self._refresh_scraper_feed(feed)
            errors[feed["id"]] = error

        return errors

    async def delete_feed(self, feed_id: int) -> None:
        await self.db.delete_feed(feed_id)
