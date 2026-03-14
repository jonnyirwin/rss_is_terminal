"""Web scraping engine for custom feed definitions."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .extractor import extract_article
from .fetcher import EntryData
from .scraper_config import ScraperConfig


def _parse_date(date_str: str | None) -> str | None:
    """Try to parse a date string into ISO format."""
    if not date_str:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return None


class Scraper:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def scrape(self, config: ScraperConfig) -> list[EntryData]:
        """Scrape the listing page(s) and return entries with summaries only.

        Full content is fetched separately via fetch_full_content().
        """
        html = await self._fetch_page(config)
        soup = BeautifulSoup(html, "html.parser")
        entries = self._extract_entries(soup, config)

        if config.pagination:
            entries += await self._scrape_pages(config, soup)

        return entries

    async def fetch_full_content(
        self, entries: list[EntryData], max_concurrent: int = 5
    ) -> None:
        """Fetch full article content for entries using trafilatura."""
        sem = asyncio.Semaphore(max_concurrent)

        async def fetch_one(entry: EntryData) -> None:
            if not entry.url:
                return
            async with sem:
                content = await extract_article(self._client, entry.url)
                if content:
                    entry.content = content

        await asyncio.gather(*[fetch_one(e) for e in entries])

    async def _fetch_page(self, config: ScraperConfig, url: str | None = None) -> str:
        target = url or config.url
        if config.js_render:
            return await self._fetch_with_playwright(target, config.wait_for)
        response = await self._client.get(target, follow_redirects=True)
        response.raise_for_status()
        return response.text

    async def _fetch_with_playwright(self, url: str, wait_for: str | None = None) -> str:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is required for JS-rendered scraper feeds. "
                "Install it with: pip install 'rss-is-terminal[js]' && playwright install chromium"
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)
            html = await page.content()
            await browser.close()
        return html

    def _extract_entries(self, soup: BeautifulSoup, config: ScraperConfig) -> list[EntryData]:
        items = soup.select(config.article_selector)
        entries = []
        for item in items:
            fields: dict[str, str | None] = {}
            for name, selector in config.fields.items():
                el = item.select_one(selector.css)
                if el:
                    if selector.attribute:
                        fields[name] = el.get(selector.attribute)
                    else:
                        fields[name] = el.get_text(strip=True)
                else:
                    fields[name] = None

            entry_url = fields.get("url")
            if entry_url and not entry_url.startswith("http"):
                entry_url = urljoin(config.url, entry_url)

            entries.append(EntryData(
                guid=entry_url or fields.get("title") or "",
                title=fields.get("title") or "(no title)",
                url=entry_url,
                author=fields.get("author"),
                published_at=_parse_date(fields.get("date")),
                summary=fields.get("summary"),
                content=fields.get("summary"),
            ))
        return entries

    async def _scrape_pages(self, config: ScraperConfig, soup: BeautifulSoup) -> list[EntryData]:
        """Follow pagination links up to max_pages."""
        entries: list[EntryData] = []
        pag = config.pagination
        if not pag:
            return entries

        current_soup = soup
        for _ in range(pag.max_pages - 1):
            next_el = current_soup.select_one(pag.next_selector.css)
            if not next_el:
                break

            if pag.next_selector.attribute:
                next_url = next_el.get(pag.next_selector.attribute)
            else:
                next_url = next_el.get_text(strip=True)

            if not next_url:
                break
            if not next_url.startswith("http"):
                next_url = urljoin(config.url, next_url)

            html = await self._fetch_page(config, url=next_url)
            current_soup = BeautifulSoup(html, "html.parser")
            entries.extend(self._extract_entries(current_soup, config))

        return entries
