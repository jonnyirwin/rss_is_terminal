"""Article list panel with DataTable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from textual import on
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static


@dataclass
class ArticleRow:
    id: int
    feed_id: int
    title: str
    url: str | None
    is_read: bool
    is_starred: bool
    published_at: str | None


class ArticleTable(DataTable):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_cursor", "Select", show=False),
    ]


class ArticleListPanel(Widget, can_focus=False, can_focus_children=True):
    """Top-right panel showing articles for the selected feed."""

    class ArticleSelected(Message):
        def __init__(self, article_id: int) -> None:
            super().__init__()
            self.article_id = article_id

    class ArticleToggleRead(Message):
        def __init__(self, article_id: int) -> None:
            super().__init__()
            self.article_id = article_id

    class ArticleToggleStar(Message):
        def __init__(self, article_id: int) -> None:
            super().__init__()
            self.article_id = article_id

    class ArticleOpenBrowser(Message):
        def __init__(self, url: str) -> None:
            super().__init__()
            self.url = url

    class MarkAllRead(Message):
        def __init__(self, feed_id: int) -> None:
            super().__init__()
            self.feed_id = feed_id

    BINDINGS = [
        Binding("r", "toggle_read", "Toggle Read", show=False),
        Binding("s", "toggle_star", "Toggle Star", show=False),
        Binding("o", "open_browser", "Open Browser", show=False),
        Binding("A", "mark_all_read", "Mark All Read", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._articles: dict[str, ArticleRow] = {}  # row_key -> ArticleRow
        self._row_order: list[str] = []  # ordered row keys
        self._current_feed_id: int | None = None
        self._filter_mode: str = "all"  # "all", "unread", "starred"
        self._status_column_key = None

    def compose(self):
        table = ArticleTable(id="article-table", cursor_type="row")
        yield table

    @property
    def table(self) -> ArticleTable:
        return self.query_one("#article-table", ArticleTable)

    async def load_articles(
        self,
        db,
        feed_id: int | None = None,
        *,
        category_id: int | None = None,
        unread_only: bool = False,
        starred_only: bool = False,
        search: str | None = None,
    ) -> None:
        self._current_feed_id = feed_id
        table = self.table
        table.clear(columns=True)
        self._articles.clear()

        col_keys = table.add_columns(" ", "Title", "Date", "Feed")
        self._status_column_key = col_keys[0]
        self._row_order.clear()

        articles = await db.get_articles(
            feed_id,
            category_id=category_id,
            unread_only=unread_only,
            starred_only=starred_only,
            search=search,
        )

        for article in articles:
            status = self._status_icon(article["is_read"], article["is_starred"])
            date_str = self._format_date(article["published_at"])
            title = article["title"] or "(no title)"
            # Truncate long titles
            if len(title) > 80:
                title = title[:77] + "..."
            feed_title = article["feed_title"] or ""
            if len(feed_title) > 20:
                feed_title = feed_title[:17] + "..."

            row_key = str(article["id"])
            table.add_row(status, title, date_str, feed_title, key=row_key)
            self._row_order.append(row_key)
            self._articles[row_key] = ArticleRow(
                id=article["id"],
                feed_id=article["feed_id"],
                title=article["title"],
                url=article["url"],
                is_read=bool(article["is_read"]),
                is_starred=bool(article["is_starred"]),
                published_at=article["published_at"],
            )

    def _status_icon(self, is_read: bool, is_starred: bool) -> str:
        if is_starred:
            return "[yellow]\u2605[/yellow]"
        if not is_read:
            return "[cyan]\u25cf[/cyan]"
        return " "

    def _format_date(self, date_str: str | None) -> str:
        if not date_str:
            return ""
        try:
            dt = datetime.fromisoformat(date_str)
            now = datetime.now(dt.tzinfo)
            if dt.date() == now.date():
                return dt.strftime("%H:%M")
            if dt.year == now.year:
                return dt.strftime("%b %d")
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return date_str[:10] if len(date_str) >= 10 else date_str

    def _get_current_article(self) -> ArticleRow | None:
        table = self.table
        if table.cursor_row is not None and table.row_count > 0:
            try:
                key = self._row_order[table.cursor_row]
                return self._articles.get(key)
            except (IndexError, KeyError):
                return None
        return None

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        article = self._articles.get(key)
        if article:
            self.post_message(self.ArticleSelected(article.id))

    def action_toggle_read(self) -> None:
        article = self._get_current_article()
        if article:
            self.post_message(self.ArticleToggleRead(article.id))

    def action_toggle_star(self) -> None:
        article = self._get_current_article()
        if article:
            self.post_message(self.ArticleToggleStar(article.id))

    def action_open_browser(self) -> None:
        article = self._get_current_article()
        if article and article.url:
            self.post_message(self.ArticleOpenBrowser(article.url))

    def action_mark_all_read(self) -> None:
        if self._current_feed_id is not None:
            self.post_message(self.MarkAllRead(self._current_feed_id))

    def update_article_status(self, article_id: int, is_read: bool, is_starred: bool) -> None:
        for key, article in self._articles.items():
            if article.id == article_id:
                article.is_read = is_read
                article.is_starred = is_starred
                if self._status_column_key is not None:
                    table = self.table
                    status = self._status_icon(is_read, is_starred)
                    try:
                        table.update_cell(key, self._status_column_key, status)
                    except Exception:
                        pass
                break
