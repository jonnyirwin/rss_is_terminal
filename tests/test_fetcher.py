"""Tests for the RSS/Atom feed fetcher."""

import pytest

from rss_is_terminal.services.fetcher import EntryData, FeedFetcher, FetchResult


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test feed</description>
    <item>
      <title>First Post</title>
      <link>https://example.com/1</link>
      <guid>https://example.com/1</guid>
      <pubDate>Wed, 15 Jan 2026 10:00:00 GMT</pubDate>
      <description>Summary of first post</description>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://example.com/2</link>
      <guid>https://example.com/2</guid>
      <description>Summary of second post</description>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <link href="https://example.com" rel="alternate"/>
  <entry>
    <title>Atom Entry</title>
    <id>urn:uuid:1234</id>
    <link href="https://example.com/atom/1" rel="alternate"/>
    <updated>2026-01-15T10:00:00Z</updated>
    <summary>Atom summary</summary>
  </entry>
</feed>
"""


@pytest.mark.asyncio
async def test_fetch_rss_feed(httpx_mock):
    import httpx

    httpx_mock.add_response(url="https://example.com/feed.xml", text=SAMPLE_RSS)

    async with httpx.AsyncClient() as client:
        fetcher = FeedFetcher(client)
        result = await fetcher.fetch_feed("https://example.com/feed.xml")

    assert result.error is None
    assert result.feed_title == "Test Feed"
    assert result.site_url == "https://example.com"
    assert result.description == "A test feed"
    assert len(result.entries) == 2
    assert result.entries[0].title == "First Post"
    assert result.entries[0].guid == "https://example.com/1"
    assert result.entries[1].title == "Second Post"


@pytest.mark.asyncio
async def test_fetch_atom_feed(httpx_mock):
    import httpx

    httpx_mock.add_response(url="https://example.com/atom.xml", text=SAMPLE_ATOM)

    async with httpx.AsyncClient() as client:
        fetcher = FeedFetcher(client)
        result = await fetcher.fetch_feed("https://example.com/atom.xml")

    assert result.error is None
    assert result.feed_title == "Atom Feed"
    assert len(result.entries) == 1
    assert result.entries[0].title == "Atom Entry"
    assert result.entries[0].guid == "urn:uuid:1234"


@pytest.mark.asyncio
async def test_fetch_feed_http_error(httpx_mock):
    import httpx

    httpx_mock.add_response(url="https://example.com/feed.xml", status_code=404)

    async with httpx.AsyncClient() as client:
        fetcher = FeedFetcher(client)
        result = await fetcher.fetch_feed("https://example.com/feed.xml")

    assert result.error is not None


@pytest.mark.asyncio
async def test_fetch_feed_invalid_xml(httpx_mock):
    import httpx

    httpx_mock.add_response(url="https://example.com/feed.xml", text="not xml at all")

    async with httpx.AsyncClient() as client:
        fetcher = FeedFetcher(client)
        result = await fetcher.fetch_feed("https://example.com/feed.xml")

    # feedparser is lenient — but with no entries and bozo=True, should get an error
    assert result.error is not None or len(result.entries) == 0


@pytest.mark.asyncio
async def test_fetch_all(httpx_mock):
    import httpx

    httpx_mock.add_response(url="https://a.com/feed", text=SAMPLE_RSS)
    httpx_mock.add_response(url="https://b.com/feed", text=SAMPLE_ATOM)

    async with httpx.AsyncClient() as client:
        fetcher = FeedFetcher(client)
        results = await fetcher.fetch_all([
            (1, "https://a.com/feed"),
            (2, "https://b.com/feed"),
        ])

    assert 1 in results
    assert 2 in results
    assert results[1].error is None
    assert results[2].error is None
    assert len(results[1].entries) == 2
    assert len(results[2].entries) == 1


@pytest.mark.asyncio
async def test_fetch_all_partial_failure(httpx_mock):
    import httpx

    httpx_mock.add_response(url="https://a.com/feed", text=SAMPLE_RSS)
    httpx_mock.add_response(url="https://b.com/feed", status_code=500)

    async with httpx.AsyncClient() as client:
        fetcher = FeedFetcher(client)
        results = await fetcher.fetch_all([
            (1, "https://a.com/feed"),
            (2, "https://b.com/feed"),
        ])

    assert results[1].error is None
    assert results[2].error is not None


@pytest.mark.asyncio
async def test_entry_content_extraction(httpx_mock):
    import httpx

    rss_with_content = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Test</title>
        <item>
          <title>Post</title>
          <guid>1</guid>
          <description>&lt;p&gt;Summary text&lt;/p&gt;</description>
        </item>
      </channel>
    </rss>
    """
    httpx_mock.add_response(url="https://example.com/feed", text=rss_with_content)

    async with httpx.AsyncClient() as client:
        fetcher = FeedFetcher(client)
        result = await fetcher.fetch_feed("https://example.com/feed")

    assert len(result.entries) == 1
    # feedparser should provide the summary/content
    entry = result.entries[0]
    assert entry.summary is not None or entry.content is not None


class TestEntryData:
    def test_defaults(self):
        entry = EntryData(guid="1", title="Test")
        assert entry.url is None
        assert entry.author is None
        assert entry.published_at is None
        assert entry.summary is None
        assert entry.content is None

    def test_full_entry(self):
        entry = EntryData(
            guid="1",
            title="Test",
            url="https://example.com",
            author="Alice",
            published_at="2026-01-15T10:00:00+00:00",
            summary="Short",
            content="<p>Full</p>",
        )
        assert entry.title == "Test"
        assert entry.author == "Alice"
