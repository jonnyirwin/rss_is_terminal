"""Shared fixtures for tests."""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from rss_is_terminal.models.database import Database


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db(tmp_path):
    """Create a fresh in-memory-like database for each test."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def sample_articles():
    return [
        {
            "guid": "article-1",
            "title": "First Article",
            "url": "https://example.com/1",
            "author": "Alice",
            "published_at": "2026-01-15T10:00:00+00:00",
            "summary": "Summary of first article",
            "content": "<p>Full content of first article</p>",
        },
        {
            "guid": "article-2",
            "title": "Second Article",
            "url": "https://example.com/2",
            "author": "Bob",
            "published_at": "2026-01-16T12:00:00+00:00",
            "summary": "Summary of second article",
            "content": None,
        },
        {
            "guid": "article-3",
            "title": "Third Article",
            "url": "https://example.com/3",
            "author": None,
            "published_at": None,
            "summary": None,
            "content": None,
        },
    ]


@pytest.fixture
def scraper_config_dict():
    return {
        "name": "Test Blog",
        "url": "https://example.com/blog",
        "article_selector": "div.post",
        "fields": {
            "title": "h2 a",
            "url": "h2 a @href",
            "author": "span.author",
            "published_at": "time @datetime",
            "summary": "p.excerpt",
        },
    }


@pytest.fixture
def scraper_config_file(tmp_path, scraper_config_dict):
    import json

    path = tmp_path / "test_scraper.json"
    path.write_text(json.dumps(scraper_config_dict, indent=2))
    return path
