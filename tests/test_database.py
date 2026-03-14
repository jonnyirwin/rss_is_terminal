"""Tests for the database layer."""

import pytest
import pytest_asyncio


# -- Categories --


@pytest.mark.asyncio
async def test_add_category(db):
    cat_id = await db.add_category("Tech")
    assert cat_id > 0

    categories = await db.get_categories()
    assert len(categories) == 1
    assert categories[0]["name"] == "Tech"


@pytest.mark.asyncio
async def test_add_duplicate_category_fails(db):
    await db.add_category("Tech")
    with pytest.raises(Exception):
        await db.add_category("Tech")


@pytest.mark.asyncio
async def test_rename_category(db):
    cat_id = await db.add_category("Old Name")
    await db.rename_category(cat_id, "New Name")

    categories = await db.get_categories()
    assert categories[0]["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_category(db):
    cat_id = await db.add_category("Doomed")
    await db.delete_category(cat_id)

    categories = await db.get_categories()
    assert len(categories) == 0


@pytest.mark.asyncio
async def test_category_sort_order(db):
    id_b = await db.add_category("B")
    id_a = await db.add_category("A")
    await db.update_category_sort(id_a, 0)
    await db.update_category_sort(id_b, 1)

    categories = await db.get_categories()
    assert categories[0]["name"] == "A"
    assert categories[1]["name"] == "B"


# -- Feeds --


@pytest.mark.asyncio
async def test_add_feed(db):
    feed_id = await db.add_feed(
        url="https://example.com/feed.xml",
        title="Example Feed",
    )
    assert feed_id > 0

    feed = await db.get_feed(feed_id)
    assert feed["title"] == "Example Feed"
    assert feed["url"] == "https://example.com/feed.xml"
    assert feed["feed_type"] == "rss"


@pytest.mark.asyncio
async def test_add_feed_with_categories(db):
    cat1 = await db.add_category("Tech")
    cat2 = await db.add_category("News")

    feed_id = await db.add_feed(
        url="https://example.com/feed.xml",
        title="Example",
        category_ids=[cat1, cat2],
    )

    cats = await db.get_feed_categories(feed_id)
    cat_ids = {c["id"] for c in cats}
    assert cat_ids == {cat1, cat2}


@pytest.mark.asyncio
async def test_add_scraper_feed(db):
    feed_id = await db.add_feed(
        url="https://example.com",
        title="Scraped Site",
        feed_type="scraper",
        scraper_config_path="/tmp/scraper.json",
    )

    feed = await db.get_feed(feed_id)
    assert feed["feed_type"] == "scraper"
    assert feed["scraper_config_path"] == "/tmp/scraper.json"


@pytest.mark.asyncio
async def test_add_duplicate_feed_fails(db):
    await db.add_feed(url="https://example.com/feed.xml", title="First")
    with pytest.raises(Exception):
        await db.add_feed(url="https://example.com/feed.xml", title="Duplicate")


@pytest.mark.asyncio
async def test_update_feed(db):
    feed_id = await db.add_feed(url="https://example.com/feed.xml", title="Old")
    await db.update_feed(feed_id, title="New Title", fetch_error="some error")

    feed = await db.get_feed(feed_id)
    assert feed["title"] == "New Title"
    assert feed["fetch_error"] == "some error"


@pytest.mark.asyncio
async def test_update_feed_ignores_unknown_fields(db):
    feed_id = await db.add_feed(url="https://example.com/feed.xml", title="Test")
    await db.update_feed(feed_id, evil_field="drop table")

    feed = await db.get_feed(feed_id)
    assert feed["title"] == "Test"


@pytest.mark.asyncio
async def test_delete_feed(db):
    feed_id = await db.add_feed(url="https://example.com/feed.xml", title="Doomed")
    await db.delete_feed(feed_id)

    feed = await db.get_feed(feed_id)
    assert feed is None


@pytest.mark.asyncio
async def test_get_feeds_by_category(db):
    cat_id = await db.add_category("Tech")
    feed1 = await db.add_feed(url="https://a.com/feed", title="A", category_ids=[cat_id])
    feed2 = await db.add_feed(url="https://b.com/feed", title="B")

    feeds = await db.get_feeds(category_id=cat_id)
    assert len(feeds) == 1
    assert feeds[0]["id"] == feed1


@pytest.mark.asyncio
async def test_get_feed_nonexistent(db):
    feed = await db.get_feed(9999)
    assert feed is None


# -- Feed-Category junction --


@pytest.mark.asyncio
async def test_set_feed_categories(db):
    cat1 = await db.add_category("A")
    cat2 = await db.add_category("B")
    cat3 = await db.add_category("C")
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test", category_ids=[cat1])

    await db.set_feed_categories(feed_id, [cat2, cat3])

    cats = await db.get_feed_categories(feed_id)
    cat_ids = {c["id"] for c in cats}
    assert cat_ids == {cat2, cat3}


@pytest.mark.asyncio
async def test_add_remove_feed_from_category(db):
    cat_id = await db.add_category("Tech")
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")

    await db.add_feed_to_category(feed_id, cat_id)
    cats = await db.get_feed_categories(feed_id)
    assert len(cats) == 1

    await db.remove_feed_from_category(feed_id, cat_id)
    cats = await db.get_feed_categories(feed_id)
    assert len(cats) == 0


@pytest.mark.asyncio
async def test_get_all_feed_category_mappings(db):
    cat1 = await db.add_category("A")
    cat2 = await db.add_category("B")
    feed1 = await db.add_feed(url="https://a.com/feed", title="A", category_ids=[cat1, cat2])
    feed2 = await db.add_feed(url="https://b.com/feed", title="B", category_ids=[cat1])

    mappings = await db.get_all_feed_category_mappings()
    assert set(mappings[feed1]) == {cat1, cat2}
    assert mappings[feed2] == [cat1]


@pytest.mark.asyncio
async def test_delete_category_cascades_junction(db):
    cat_id = await db.add_category("Doomed")
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test", category_ids=[cat_id])

    await db.delete_category(cat_id)

    cats = await db.get_feed_categories(feed_id)
    assert len(cats) == 0
    # Feed itself should still exist
    feed = await db.get_feed(feed_id)
    assert feed is not None


# -- Articles --


@pytest.mark.asyncio
async def test_upsert_articles(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    count = await db.upsert_articles(feed_id, sample_articles)
    assert count == 3

    articles = await db.get_articles(feed_id)
    assert len(articles) == 3


@pytest.mark.asyncio
async def test_upsert_articles_dedup(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    # Upsert same articles again — should update, not duplicate
    await db.upsert_articles(feed_id, sample_articles)
    articles = await db.get_articles(feed_id)
    assert len(articles) == 3


@pytest.mark.asyncio
async def test_upsert_preserves_existing_content(db):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")

    # First upsert with content
    await db.upsert_articles(feed_id, [{
        "guid": "a1",
        "title": "Article",
        "url": "https://example.com/1",
        "content": "Original content",
        "summary": None,
    }])

    # Second upsert without content — should keep original
    await db.upsert_articles(feed_id, [{
        "guid": "a1",
        "title": "Article Updated",
        "url": "https://example.com/1",
        "content": None,
        "summary": None,
    }])

    article = (await db.get_articles(feed_id))[0]
    assert article["content"] == "Original content"
    assert article["title"] == "Article Updated"


@pytest.mark.asyncio
async def test_upsert_empty_list(db):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    count = await db.upsert_articles(feed_id, [])
    assert count == 0


@pytest.mark.asyncio
async def test_get_article(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    articles = await db.get_articles(feed_id)
    article = await db.get_article(articles[0]["id"])
    assert article is not None
    assert article["feed_title"] == "Test"


@pytest.mark.asyncio
async def test_get_articles_unread_filter(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    articles = await db.get_articles(feed_id)
    await db.mark_read(articles[0]["id"])

    unread = await db.get_articles(feed_id, unread_only=True)
    assert len(unread) == 2


@pytest.mark.asyncio
async def test_get_articles_starred_filter(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    articles = await db.get_articles(feed_id)
    await db.toggle_star(articles[0]["id"])

    starred = await db.get_articles(starred_only=True)
    assert len(starred) == 1


@pytest.mark.asyncio
async def test_get_articles_search(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    results = await db.get_articles(search="First")
    assert len(results) == 1
    assert results[0]["title"] == "First Article"


@pytest.mark.asyncio
async def test_get_articles_by_category(db, sample_articles):
    cat_id = await db.add_category("Tech")
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test", category_ids=[cat_id])
    await db.upsert_articles(feed_id, sample_articles)

    articles = await db.get_articles(category_id=cat_id)
    assert len(articles) == 3

    # Different category should return nothing
    cat2 = await db.add_category("Other")
    articles = await db.get_articles(category_id=cat2)
    assert len(articles) == 0


@pytest.mark.asyncio
async def test_get_articles_limit_offset(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    page1 = await db.get_articles(feed_id, limit=2, offset=0)
    assert len(page1) == 2

    page2 = await db.get_articles(feed_id, limit=2, offset=2)
    assert len(page2) == 1


@pytest.mark.asyncio
async def test_mark_read(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    articles = await db.get_articles(feed_id)
    article_id = articles[0]["id"]

    await db.mark_read(article_id)
    article = await db.get_article(article_id)
    assert article["is_read"] == 1

    await db.mark_read(article_id, read=False)
    article = await db.get_article(article_id)
    assert article["is_read"] == 0


@pytest.mark.asyncio
async def test_mark_all_read(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    await db.mark_all_read(feed_id)

    unread = await db.get_articles(feed_id, unread_only=True)
    assert len(unread) == 0


@pytest.mark.asyncio
async def test_toggle_star(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    articles = await db.get_articles(feed_id)
    article_id = articles[0]["id"]

    result = await db.toggle_star(article_id)
    assert result is True

    result = await db.toggle_star(article_id)
    assert result is False


@pytest.mark.asyncio
async def test_toggle_star_nonexistent(db):
    result = await db.toggle_star(9999)
    assert result is False


@pytest.mark.asyncio
async def test_unread_count(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    count = await db.get_unread_count(feed_id)
    assert count == 3

    articles = await db.get_articles(feed_id)
    await db.mark_read(articles[0]["id"])

    count = await db.get_unread_count(feed_id)
    assert count == 2


@pytest.mark.asyncio
async def test_total_unread_count(db, sample_articles):
    feed1 = await db.add_feed(url="https://a.com/feed", title="A")
    feed2 = await db.add_feed(url="https://b.com/feed", title="B")
    await db.upsert_articles(feed1, sample_articles[:2])
    await db.upsert_articles(feed2, sample_articles[2:])

    count = await db.get_total_unread_count()
    assert count == 3


@pytest.mark.asyncio
async def test_starred_count(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    assert await db.get_starred_count() == 0

    articles = await db.get_articles(feed_id)
    await db.toggle_star(articles[0]["id"])
    await db.toggle_star(articles[1]["id"])

    assert await db.get_starred_count() == 2


@pytest.mark.asyncio
async def test_get_articles_without_content(db):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, [
        {"guid": "a1", "title": "Has Content", "content": "Full text", "summary": "Short"},
        {"guid": "a2", "title": "No Content", "content": None, "summary": "Short"},
        {"guid": "a3", "title": "Same Content", "content": "Short", "summary": "Short"},
    ])

    rows = await db.get_articles_without_content(feed_id)
    guids = {r["guid"] for r in rows}
    assert "a2" in guids
    assert "a3" in guids  # content == summary
    assert "a1" not in guids


@pytest.mark.asyncio
async def test_update_article_content(db):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, [
        {"guid": "a1", "title": "Test", "content": None},
    ])

    await db.update_article_content(feed_id, "a1", "<p>Full article</p>")

    articles = await db.get_articles(feed_id)
    assert articles[0]["content"] == "<p>Full article</p>"


@pytest.mark.asyncio
async def test_delete_feed_cascades_articles(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    await db.delete_feed(feed_id)

    articles = await db.get_articles(feed_id)
    assert len(articles) == 0


@pytest.mark.asyncio
async def test_search_articles(db, sample_articles):
    feed_id = await db.add_feed(url="https://example.com/feed", title="Test")
    await db.upsert_articles(feed_id, sample_articles)

    results = await db.search_articles("Second")
    assert len(results) == 1
    assert results[0]["title"] == "Second Article"
