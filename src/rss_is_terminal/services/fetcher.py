"""Async RSS/Atom feed fetcher and parser."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx


@dataclass
class EntryData:
    guid: str
    title: str
    url: str | None = None
    author: str | None = None
    published_at: str | None = None
    summary: str | None = None
    content: str | None = None


@dataclass
class FetchResult:
    url: str
    feed_title: str | None = None
    site_url: str | None = None
    description: str | None = None
    entries: list[EntryData] = field(default_factory=list)
    error: str | None = None


class FeedFetcher:
    def __init__(self, client: httpx.AsyncClient, max_concurrent: int = 10) -> None:
        self._client = client
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_feed(self, url: str) -> FetchResult:
        async with self._semaphore:
            try:
                response = await self._client.get(url, follow_redirects=True)
                response.raise_for_status()
            except httpx.HTTPError as e:
                return FetchResult(url=url, error=str(e))

            try:
                parsed = feedparser.parse(response.text)
            except Exception as e:
                return FetchResult(url=url, error=f"Parse error: {e}")

            if parsed.bozo and not parsed.entries:
                return FetchResult(
                    url=url,
                    error=f"Feed error: {parsed.bozo_exception}",
                )

            feed_info = parsed.feed
            entries = []
            for entry in parsed.entries:
                guid = (
                    entry.get("id")
                    or entry.get("link")
                    or entry.get("title", url)
                )
                content_html = None
                if entry.get("content"):
                    content_html = entry.content[0].get("value")
                elif entry.get("summary_detail"):
                    content_html = entry.summary_detail.get("value")

                published_at = None
                for date_field in ("published_parsed", "updated_parsed"):
                    time_struct = entry.get(date_field)
                    if time_struct:
                        try:
                            published_at = datetime.fromtimestamp(
                                mktime(time_struct), tz=timezone.utc
                            ).isoformat()
                        except (ValueError, OverflowError):
                            pass
                        break

                entries.append(EntryData(
                    guid=guid,
                    title=entry.get("title", "(no title)"),
                    url=entry.get("link"),
                    author=entry.get("author"),
                    published_at=published_at,
                    summary=entry.get("summary"),
                    content=content_html or entry.get("summary"),
                ))

            return FetchResult(
                url=url,
                feed_title=feed_info.get("title"),
                site_url=feed_info.get("link"),
                description=feed_info.get("subtitle") or feed_info.get("description"),
                entries=entries,
            )

    async def fetch_all(self, feed_urls: list[tuple[int, str]]) -> dict[int, FetchResult]:
        """Fetch multiple feeds concurrently. Returns {feed_id: FetchResult}."""
        feed_ids = [feed_id for feed_id, _ in feed_urls]
        coros = [self.fetch_feed(url) for _, url in feed_urls]
        fetch_results = await asyncio.gather(*coros)
        return dict(zip(feed_ids, fetch_results))
