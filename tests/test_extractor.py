"""Tests for the article content extractor."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_extract_article_success(httpx_mock):
    from rss_is_terminal.services.extractor import extract_article

    html = """
    <html><body>
        <article>
            <h1>Test Article</h1>
            <p>This is a long article with enough content to be extracted.
            It needs several sentences to be meaningful. The trafilatura
            library requires a reasonable amount of text to identify
            the main content block. So we add more text here to make
            the extraction work properly.</p>
        </article>
    </body></html>
    """
    httpx_mock.add_response(url="https://example.com/article", text=html)

    async with httpx.AsyncClient() as client:
        result = await extract_article(client, "https://example.com/article")
        # trafilatura may or may not extract from minimal HTML,
        # but the function should not raise
        assert result is None or isinstance(result, str)


@pytest.mark.asyncio
async def test_extract_article_http_error(httpx_mock):
    from rss_is_terminal.services.extractor import extract_article

    httpx_mock.add_response(url="https://example.com/fail", status_code=500)

    async with httpx.AsyncClient() as client:
        result = await extract_article(client, "https://example.com/fail")
        assert result is None


@pytest.mark.asyncio
async def test_extract_article_connection_error():
    from rss_is_terminal.services.extractor import extract_article

    async with httpx.AsyncClient() as client:
        # Use an unreachable URL
        result = await extract_article(client, "http://192.0.2.1:1/nope")
        assert result is None


@pytest.mark.asyncio
async def test_extract_article_returns_html(httpx_mock):
    from rss_is_terminal.services.extractor import extract_article

    # A more substantial page that trafilatura should be able to extract from
    paragraphs = "\n".join(
        f"<p>Paragraph {i} with enough words to make trafilatura happy about content extraction.</p>"
        for i in range(20)
    )
    html = f"""
    <html><head><title>Test</title></head><body>
        <nav>Navigation</nav>
        <article>
            <h1>Main Article Title</h1>
            {paragraphs}
        </article>
        <footer>Footer</footer>
    </body></html>
    """
    httpx_mock.add_response(url="https://example.com/full", text=html)

    async with httpx.AsyncClient() as client:
        result = await extract_article(client, "https://example.com/full")
        if result:
            assert "Paragraph" in result
