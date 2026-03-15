"""Async SQLite database layer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .schema import SCHEMA_SQL


class Database:
    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(SCHEMA_SQL)
        await self._run_migrations()
        await self._db.commit()

    async def _run_migrations(self) -> None:
        """Run migrations, ignoring already-applied ones."""
        # Column migrations
        alter_migrations = [
            "ALTER TABLE feeds ADD COLUMN feed_type TEXT NOT NULL DEFAULT 'rss'",
            "ALTER TABLE feeds ADD COLUMN scraper_config_path TEXT",
        ]
        for sql in alter_migrations:
            try:
                await self._db.execute(sql)
            except Exception:
                pass

        # Migrate existing category_id data to junction table
        try:
            await self._db.execute(
                """INSERT OR IGNORE INTO feed_categories (feed_id, category_id)
                   SELECT id, category_id FROM feeds WHERE category_id IS NOT NULL"""
            )
        except Exception:
            pass

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    @property
    def db(self) -> aiosqlite.Connection:
        assert self._db is not None, "Database not connected"
        return self._db

    # -- Categories --

    async def get_categories(self) -> list[aiosqlite.Row]:
        async with self.db.execute(
            "SELECT * FROM categories ORDER BY sort_order, name"
        ) as cur:
            return await cur.fetchall()

    async def add_category(self, name: str) -> int:
        async with self.db.execute(
            "INSERT INTO categories (name) VALUES (?)", (name,)
        ) as cur:
            await self.db.commit()
            return cur.lastrowid

    async def rename_category(self, category_id: int, name: str) -> None:
        await self.db.execute(
            "UPDATE categories SET name = ? WHERE id = ?", (name, category_id)
        )
        await self.db.commit()

    async def update_category_sort(self, category_id: int, sort_order: int) -> None:
        await self.db.execute(
            "UPDATE categories SET sort_order = ? WHERE id = ?",
            (sort_order, category_id),
        )
        await self.db.commit()

    async def delete_category(self, category_id: int) -> None:
        # Junction table rows deleted by ON DELETE CASCADE
        await self.db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await self.db.commit()

    # -- Feed-Category junction --

    async def set_feed_categories(self, feed_id: int, category_ids: list[int]) -> None:
        """Replace all category assignments for a feed."""
        await self.db.execute(
            "DELETE FROM feed_categories WHERE feed_id = ?", (feed_id,)
        )
        for cat_id in category_ids:
            await self.db.execute(
                "INSERT OR IGNORE INTO feed_categories (feed_id, category_id) VALUES (?, ?)",
                (feed_id, cat_id),
            )
        await self.db.commit()

    async def add_feed_to_category(self, feed_id: int, category_id: int) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO feed_categories (feed_id, category_id) VALUES (?, ?)",
            (feed_id, category_id),
        )
        await self.db.commit()

    async def remove_feed_from_category(self, feed_id: int, category_id: int) -> None:
        await self.db.execute(
            "DELETE FROM feed_categories WHERE feed_id = ? AND category_id = ?",
            (feed_id, category_id),
        )
        await self.db.commit()

    async def get_feed_categories(self, feed_id: int) -> list[aiosqlite.Row]:
        async with self.db.execute(
            """SELECT c.* FROM categories c
               JOIN feed_categories fc ON c.id = fc.category_id
               WHERE fc.feed_id = ?
               ORDER BY c.sort_order, c.name""",
            (feed_id,),
        ) as cur:
            return await cur.fetchall()

    async def get_all_feed_category_mappings(self) -> dict[int, list[int]]:
        """Return {feed_id: [category_id, ...]} for all feeds."""
        async with self.db.execute(
            "SELECT feed_id, category_id FROM feed_categories"
        ) as cur:
            rows = await cur.fetchall()
        mappings: dict[int, list[int]] = {}
        for row in rows:
            mappings.setdefault(row["feed_id"], []).append(row["category_id"])
        return mappings

    # -- Feeds --

    async def get_feeds(self, category_id: int | None = None) -> list[aiosqlite.Row]:
        if category_id is not None:
            async with self.db.execute(
                """SELECT f.* FROM feeds f
                   JOIN feed_categories fc ON f.id = fc.feed_id
                   WHERE fc.category_id = ?
                   ORDER BY f.sort_order, f.title""",
                (category_id,),
            ) as cur:
                return await cur.fetchall()
        async with self.db.execute(
            "SELECT * FROM feeds ORDER BY sort_order, title"
        ) as cur:
            return await cur.fetchall()

    async def get_feed(self, feed_id: int) -> aiosqlite.Row | None:
        async with self.db.execute(
            "SELECT * FROM feeds WHERE id = ?", (feed_id,)
        ) as cur:
            return await cur.fetchone()

    async def add_feed(
        self,
        url: str,
        title: str,
        site_url: str | None = None,
        description: str | None = None,
        category_ids: list[int] | None = None,
        feed_type: str = "rss",
        scraper_config_path: str | None = None,
    ) -> int:
        async with self.db.execute(
            """INSERT INTO feeds (url, title, site_url, description,
                                  feed_type, scraper_config_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url, title, site_url, description, feed_type, scraper_config_path),
        ) as cur:
            feed_id = cur.lastrowid
        if category_ids:
            for cat_id in category_ids:
                await self.db.execute(
                    "INSERT OR IGNORE INTO feed_categories (feed_id, category_id) VALUES (?, ?)",
                    (feed_id, cat_id),
                )
        await self.db.commit()
        return feed_id

    async def update_feed(self, feed_id: int, **kwargs) -> None:
        allowed = {"title", "url", "site_url", "description",
                    "last_fetched_at", "fetch_error", "sort_order",
                    "feed_type", "scraper_config_path"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [feed_id]
        await self.db.execute(
            f"UPDATE feeds SET {set_clause} WHERE id = ?", values
        )
        await self.db.commit()

    async def delete_feed(self, feed_id: int) -> None:
        await self.db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        await self.db.commit()

    # -- Articles --

    async def get_articles(
        self,
        feed_id: int | None = None,
        *,
        category_id: int | None = None,
        unread_only: bool = False,
        starred_only: bool = False,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[aiosqlite.Row]:
        conditions = []
        params: list = []
        extra_joins = ""

        if feed_id is not None:
            conditions.append("a.feed_id = ?")
            params.append(feed_id)
        if category_id is not None:
            extra_joins = "JOIN feed_categories fc ON a.feed_id = fc.feed_id"
            conditions.append("fc.category_id = ?")
            params.append(category_id)
        if unread_only:
            conditions.append("a.is_read = 0")
        if starred_only:
            conditions.append("a.is_starred = 1")
        if search:
            conditions.append("(a.title LIKE ? OR a.content LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT a.*, f.title as feed_title
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            {extra_joins}
            {where}
            ORDER BY a.published_at DESC, a.fetched_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        async with self.db.execute(sql, params) as cur:
            return await cur.fetchall()

    async def get_article(self, article_id: int) -> aiosqlite.Row | None:
        async with self.db.execute(
            """SELECT a.*, f.title as feed_title
               FROM articles a JOIN feeds f ON a.feed_id = f.id
               WHERE a.id = ?""",
            (article_id,),
        ) as cur:
            return await cur.fetchone()

    async def upsert_articles(self, feed_id: int, articles: list[dict]) -> int:
        if not articles:
            return 0
        inserted = 0
        for article in articles:
            try:
                await self.db.execute(
                    """INSERT INTO articles
                       (feed_id, guid, title, url, author, published_at, summary, content)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(feed_id, guid) DO UPDATE SET
                           title = excluded.title,
                           url = excluded.url,
                           author = excluded.author,
                           summary = excluded.summary,
                           content = COALESCE(excluded.content, content)""",
                    (
                        feed_id,
                        article["guid"],
                        article["title"],
                        article.get("url"),
                        article.get("author"),
                        article.get("published_at"),
                        article.get("summary"),
                        article.get("content"),
                    ),
                )
                inserted += 1
            except Exception:
                continue
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE feeds SET last_fetched_at = ?, fetch_error = NULL WHERE id = ?",
            (now, feed_id),
        )
        await self.db.commit()
        return inserted

    async def get_articles_without_content(self, feed_id: int, limit: int = 20) -> list[aiosqlite.Row]:
        async with self.db.execute(
            """SELECT id, guid, title, url, summary, content FROM articles
               WHERE feed_id = ? AND (content IS NULL OR content = summary)
               ORDER BY fetched_at DESC LIMIT ?""",
            (feed_id, limit),
        ) as cur:
            return await cur.fetchall()

    async def update_article_content(self, feed_id: int, guid: str, content: str) -> None:
        await self.db.execute(
            "UPDATE articles SET content = ? WHERE feed_id = ? AND guid = ?",
            (content, feed_id, guid),
        )
        await self.db.commit()

    async def mark_read(self, article_id: int, read: bool = True) -> None:
        await self.db.execute(
            "UPDATE articles SET is_read = ? WHERE id = ?",
            (1 if read else 0, article_id),
        )
        await self.db.commit()

    async def mark_all_read(self, feed_id: int) -> None:
        await self.db.execute(
            "UPDATE articles SET is_read = 1 WHERE feed_id = ? AND is_read = 0",
            (feed_id,),
        )
        await self.db.commit()

    async def mark_all_feeds_read(self) -> None:
        await self.db.execute(
            "UPDATE articles SET is_read = 1 WHERE is_read = 0",
        )
        await self.db.commit()

    async def mark_category_read(self, category_id: int) -> None:
        await self.db.execute(
            """UPDATE articles SET is_read = 1
               WHERE is_read = 0 AND feed_id IN (
                   SELECT feed_id FROM feed_categories WHERE category_id = ?
               )""",
            (category_id,),
        )
        await self.db.commit()

    async def toggle_star(self, article_id: int) -> bool:
        async with self.db.execute(
            "SELECT is_starred FROM articles WHERE id = ?", (article_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return False
        new_val = 0 if row["is_starred"] else 1
        await self.db.execute(
            "UPDATE articles SET is_starred = ? WHERE id = ?",
            (new_val, article_id),
        )
        await self.db.commit()
        return bool(new_val)

    async def get_unread_count(self, feed_id: int) -> int:
        async with self.db.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE feed_id = ? AND is_read = 0",
            (feed_id,),
        ) as cur:
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    async def get_starred_count(self) -> int:
        async with self.db.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE is_starred = 1"
        ) as cur:
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    async def get_total_unread_count(self) -> int:
        async with self.db.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE is_read = 0"
        ) as cur:
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    async def search_articles(self, query: str, limit: int = 100) -> list[aiosqlite.Row]:
        return await self.get_articles(search=query, limit=limit)
