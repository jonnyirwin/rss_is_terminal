"""Full-text article extraction for link-only feeds."""

from __future__ import annotations

import asyncio
from functools import lru_cache

import httpx
import trafilatura


async def extract_article(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a URL and extract the main article content as HTML.

    Returns HTML string or None on failure.
    """
    try:
        response = await client.get(url, follow_redirects=True, timeout=15)
        response.raise_for_status()
    except (httpx.HTTPError, Exception):
        return None

    # Run trafilatura in a thread since it's CPU-bound
    html = response.text
    result = await asyncio.to_thread(
        trafilatura.extract,
        html,
        include_links=True,
        include_images=True,
        include_formatting=True,
        output_format="html",
        favor_recall=True,
    )
    return result
