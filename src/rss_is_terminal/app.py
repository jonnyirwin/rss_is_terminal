"""Main application - RSS is Terminal."""

from __future__ import annotations

import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import httpx
from textual.suggester import Suggester
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, SelectionList, Static


class PathSuggester(Suggester):
    """Suggest filesystem paths as the user types."""

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
        path = Path(value).expanduser()
        # If it ends with /, list contents of that directory
        if value.endswith("/") and path.is_dir():
            parent = path
            prefix = ""
        else:
            parent = path.parent
            prefix = path.name
        if not parent.is_dir():
            return None
        try:
            matches = sorted(
                p for p in parent.iterdir()
                if p.name.startswith(prefix)
            )
        except PermissionError:
            return None
        if not matches:
            return None
        # Return the first match as full path
        suggestion = str(matches[0])
        if matches[0].is_dir():
            suggestion += "/"
        # Suggester returns the full completed value
        return suggestion

from .config import AppConfig, db_path
from .models.database import Database
from .services.feed_service import FeedService
from .services.fetcher import FeedFetcher
from .services.opml import export_opml, import_opml
from .services.scraper import Scraper
from .widgets.article_list import ArticleListPanel
from .widgets.article_view import ArticleViewPanel
from .widgets.feed_list import FeedListPanel
from .widgets.help_screen import HelpScreen


# -- Modal Screens --

class AddFeedScreen(ModalScreen[tuple[str, list[int]] | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, categories: list[tuple[int, str]] | None = None) -> None:
        super().__init__()
        self._categories = categories or []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Add Feed")
            yield Input(placeholder="Feed URL (RSS/Atom)", id="feed-url")
            if self._categories:
                yield Label("Categories (select multiple):")
                yield SelectionList[int](
                    *((name, cat_id) for cat_id, name in self._categories),
                    id="feed-categories",
                )
            with Horizontal(classes="modal-buttons"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", id="btn-cancel")

    def _get_result(self) -> tuple[str, list[int]] | None:
        url = self.query_one("#feed-url", Input).value.strip()
        if not url:
            return None
        cat_ids: list[int] = []
        try:
            cat_ids = list(self.query_one("#feed-categories", SelectionList).selected)
        except Exception:
            pass
        return (url, cat_ids)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-add":
            result = self._get_result()
            if result:
                self.dismiss(result)
            else:
                self.notify("Please enter a URL", severity="warning")
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "feed-url":
            result = self._get_result()
            if result:
                self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label(self._message)
            with Horizontal(classes="modal-buttons"):
                yield Button("Yes", variant="error", id="btn-yes")
                yield Button("No", variant="primary", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")

    def action_cancel(self) -> None:
        self.dismiss(False)


class DeleteCategoryScreen(ModalScreen[str | None]):
    """Modal for deleting a category with options for orphaned feeds."""
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, category_name: str, orphan_count: int) -> None:
        super().__init__()
        self._category_name = category_name
        self._orphan_count = orphan_count

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label(f"Delete category '{self._category_name}'?")
            if self._orphan_count > 0:
                yield Label(
                    f"{self._orphan_count} feed(s) only belong to this category "
                    "and would become uncategorized."
                )
            with Horizontal(classes="modal-buttons"):
                yield Button("Remove category only", variant="warning", id="btn-keep")
                if self._orphan_count > 0:
                    yield Button("Also delete orphaned feeds", variant="error", id="btn-delete")
                yield Button("Cancel", variant="primary", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-keep":
            self.dismiss("keep")
        elif event.button.id == "btn-delete":
            self.dismiss("delete")
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class CategoryScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str = "Create Category") -> None:
        super().__init__()
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label(self._title)
            yield Input(placeholder="Category name", id="cat-name")
            with Horizontal(classes="modal-buttons"):
                yield Button("Create", variant="primary", id="btn-create")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            name = self.query_one("#cat-name", Input).value.strip()
            if name:
                self.dismiss(name)
            else:
                self.notify("Please enter a name", severity="warning")
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if name:
            self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)


class OPMLScreen(ModalScreen[tuple[str, str] | None]):
    """Modal for OPML import/export. Import accepts a file path or URL."""
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, mode: str = "import") -> None:
        super().__init__()
        self._mode = mode

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            label = "Import OPML" if self._mode == "import" else "Export OPML"
            yield Label(label)
            if self._mode == "import":
                placeholder = "File path or URL (https://...)"
            else:
                placeholder = "File path"
            default = "" if self._mode == "import" else str(Path.home() / "feeds.opml")
            yield Input(
                placeholder=placeholder, value=default, id="opml-path",
                suggester=PathSuggester(case_sensitive=True),
            )
            with Horizontal(classes="modal-buttons"):
                btn_label = "Import" if self._mode == "import" else "Export"
                yield Button(btn_label, variant="primary", id="btn-ok")
                yield Button("Cancel", id="btn-cancel")

    def _submit(self) -> None:
        value = self.query_one("#opml-path", Input).value.strip()
        if value:
            self.dismiss((self._mode, value))
        else:
            self.notify("Please enter a path or URL", severity="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ok":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)


class SearchScreen(ModalScreen[str | None]):
    """Modal for searching articles."""
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Search Articles")
            yield Input(placeholder="Search query...", id="search-query")
            with Horizontal(classes="modal-buttons"):
                yield Button("Search", variant="primary", id="btn-search")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-search":
            query = self.query_one("#search-query", Input).value.strip()
            self.dismiss(query if query else None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        self.dismiss(query if query else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class AddScraperScreen(ModalScreen[tuple[str, list[int]] | None]):
    """Modal for adding a scraper feed from a JSON config file."""
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, categories: list[tuple[int, str]] | None = None) -> None:
        super().__init__()
        self._categories = categories or []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Add Scraper Feed")
            yield Input(
                placeholder="Path to scraper JSON config", id="scraper-path",
                suggester=PathSuggester(case_sensitive=True),
            )
            if self._categories:
                yield Label("Categories (select multiple):")
                yield SelectionList[int](
                    *((name, cat_id) for cat_id, name in self._categories),
                    id="scraper-categories",
                )
            with Horizontal(classes="modal-buttons"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", id="btn-cancel")

    def _get_result(self) -> tuple[str, list[int]] | None:
        path = self.query_one("#scraper-path", Input).value.strip()
        if not path:
            return None
        cat_ids: list[int] = []
        try:
            cat_ids = list(self.query_one("#scraper-categories", SelectionList).selected)
        except Exception:
            pass
        return (path, cat_ids)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-add":
            result = self._get_result()
            if result:
                self.dismiss(result)
            else:
                self.notify("Please enter a config file path", severity="warning")
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "scraper-path":
            result = self._get_result()
            if result:
                self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ManageCategoriesScreen(ModalScreen[list[int] | None]):
    """Modal to assign categories to an existing feed."""
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self, feed_title: str, categories: list[tuple[int, str]], current_ids: list[int]
    ) -> None:
        super().__init__()
        self._feed_title = feed_title
        self._categories = categories
        self._current_ids = current_ids

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label(f"Categories for: {self._feed_title}")
            yield SelectionList[int](
                *((name, cat_id, cat_id in self._current_ids) for cat_id, name in self._categories),
                id="cat-selection",
            )
            with Horizontal(classes="modal-buttons"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            selected = list(self.query_one("#cat-selection", SelectionList).selected)
            self.dismiss(selected)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# -- Main App --

class RSSApp(App):
    TITLE = "RSS is Terminal"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "show_help", "Help", key_display="?"),
        Binding("R", "refresh_all", "Refresh"),
        Binding("a", "add_feed", "Add Feed"),
        Binding("W", "add_scraper", "Scraper", show=False),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("tab", "focus_next_panel", "Next Panel", show=False),
        Binding("shift+tab", "focus_prev_panel", "Prev Panel", show=False),
        Binding("l", "focus_right", "Right", show=False),
        Binding("h", "focus_left", "Left", show=False),
        Binding("I", "import_opml", "Import"),
        Binding("E", "export_opml", "Export"),
        Binding("C", "create_category", "Category"),
        Binding("u", "filter_unread", "Unread", show=False),
        Binding("S", "filter_starred", "Starred", show=False),
        Binding("escape", "clear_search", "Clear", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.db: Database | None = None
        self.feed_service: FeedService | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._config = AppConfig.load()
        self._panels = ["feeds-panel", "articles-panel", "preview-panel"]
        self._current_panel = 0
        self._current_feed_id: int | None = None
        self._current_category_id: int | None = None
        self._search_active = False
        self._filter_mode = "all"
        self._refresh_timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield FeedListPanel(id="feeds-panel")
            with Vertical(id="right-column"):
                yield ArticleListPanel(id="articles-panel")
                yield ArticleViewPanel(id="preview-panel")
        yield Footer()

    def on_ready(self) -> None:
        self.query_one("#feeds-panel").border_title = "Feeds"
        self.query_one("#articles-panel").border_title = "Articles"
        self.query_one("#preview-panel").border_title = "Preview"

    async def on_mount(self) -> None:
        # Init database
        self.db = Database(db_path())
        await self.db.connect()

        # Init HTTP client and services
        self._http_client = httpx.AsyncClient(
            timeout=self._config.fetch_timeout_seconds,
            headers={"User-Agent": "RSS-is-Terminal/0.1"},
        )
        fetcher = FeedFetcher(self._http_client, self._config.concurrent_fetches)
        scraper = Scraper(self._http_client)
        self.feed_service = FeedService(self.db, fetcher, scraper)

        # Load feeds
        await self._reload_feeds()

        # Show welcome if no feeds
        feeds = await self.db.get_feeds()
        if not feeds:
            preview = self.query_one("#preview-panel", ArticleViewPanel)
            await preview.show_welcome()

        # Update status bar
        await self._update_unread_title()

        # Focus feed list
        self._focus_panel(0)

        # Start auto-refresh timer
        if self._config.refresh_interval_minutes > 0:
            self._refresh_timer = self.set_interval(
                self._config.refresh_interval_minutes * 60,
                self._auto_refresh,
            )

    async def on_unmount(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
        if self.db:
            await self.db.close()

    # -- Panel Focus --

    def _focus_panel(self, index: int) -> None:
        self._current_panel = index % len(self._panels)
        panel_id = self._panels[self._current_panel]
        panel = self.query_one(f"#{panel_id}")
        # Focus the first focusable child within the panel
        for child in panel.query("*"):
            if child.can_focus:
                child.focus()
                return
        panel.focus()

    def action_focus_next_panel(self) -> None:
        self._focus_panel(self._current_panel + 1)

    def action_focus_prev_panel(self) -> None:
        self._focus_panel(self._current_panel - 1)

    def action_focus_right(self) -> None:
        if self._current_panel == 0:
            self._focus_panel(1)
        elif self._current_panel == 1:
            self._focus_panel(2)

    def action_focus_left(self) -> None:
        if self._current_panel == 2:
            self._focus_panel(1)
        elif self._current_panel == 1:
            self._focus_panel(0)

    # -- Feed Events --

    async def on_feed_list_panel_feed_selected(self, msg: FeedListPanel.FeedSelected) -> None:
        self._current_feed_id = msg.feed_id
        self._current_category_id = None
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        articles_panel.border_title = f"Articles - {msg.feed_title}"
        await articles_panel.load_articles(
            self.db, msg.feed_id,
            unread_only=self._filter_mode == "unread",
            starred_only=self._filter_mode == "starred",
        )
        self.sub_title = msg.feed_title

    async def on_feed_list_panel_all_feeds_selected(self, msg: FeedListPanel.AllFeedsSelected) -> None:
        self._current_feed_id = None
        self._current_category_id = None
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        articles_panel.border_title = "Articles - All Feeds"
        await articles_panel.load_articles(
            self.db, None,
            unread_only=self._filter_mode == "unread",
            starred_only=self._filter_mode == "starred",
        )
        self.sub_title = "All Feeds"

    async def on_feed_list_panel_category_selected(self, msg: FeedListPanel.CategorySelected) -> None:
        self._current_feed_id = None
        self._current_category_id = msg.category_id
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        articles_panel.border_title = f"Articles - {msg.category_name}"
        await articles_panel.load_articles(
            self.db, None,
            category_id=msg.category_id,
            unread_only=self._filter_mode == "unread",
            starred_only=self._filter_mode == "starred",
        )
        self.sub_title = msg.category_name

    async def on_feed_list_panel_starred_selected(self, msg: FeedListPanel.StarredSelected) -> None:
        self._current_feed_id = None
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        articles_panel.border_title = "Articles - Starred"
        await articles_panel.load_articles(self.db, None, starred_only=True)
        self.sub_title = "Starred"

    async def on_feed_list_panel_feed_delete_requested(self, msg: FeedListPanel.FeedDeleteRequested) -> None:
        def handle_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self.run_worker(self._do_delete_feed(msg.feed_id))

        self.push_screen(ConfirmScreen(f"Delete feed '{msg.feed_title}'?"), handle_confirm)

    async def _do_delete_feed(self, feed_id: int) -> None:
        await self.feed_service.delete_feed(feed_id)
        await self._reload_feeds()
        self.notify("Feed deleted")
        await self._update_unread_title()

    async def on_feed_list_panel_feed_categories_requested(
        self, msg: FeedListPanel.FeedCategoriesRequested
    ) -> None:
        categories = await self.db.get_categories()
        if not categories:
            self.notify("No categories yet. Press C to create one.", severity="warning")
            return
        cat_list = [(c["id"], c["name"]) for c in categories]
        current = await self.db.get_feed_categories(msg.feed_id)
        current_ids = [c["id"] for c in current]

        def handle_result(selected: list[int] | None) -> None:
            if selected is not None:
                self.run_worker(self._do_set_categories(msg.feed_id, selected))

        self.push_screen(
            ManageCategoriesScreen(msg.feed_title, cat_list, current_ids),
            handle_result,
        )

    async def _do_set_categories(self, feed_id: int, category_ids: list[int]) -> None:
        await self.db.set_feed_categories(feed_id, category_ids)
        await self._reload_feeds()
        self.notify("Categories updated")

    async def on_feed_list_panel_category_delete_requested(
        self, msg: FeedListPanel.CategoryDeleteRequested
    ) -> None:
        # Count feeds that ONLY belong to this category
        mappings = await self.db.get_all_feed_category_mappings()
        orphan_count = sum(
            1 for fid, cats in mappings.items()
            if msg.category_id in cats and len(cats) == 1
        )

        def handle_result(choice: str | None) -> None:
            if choice:
                self.run_worker(
                    self._do_delete_category(msg.category_id, choice == "delete")
                )

        self.push_screen(
            DeleteCategoryScreen(msg.category_name, orphan_count),
            handle_result,
        )

    async def _do_delete_category(
        self, category_id: int, delete_orphans: bool
    ) -> None:
        if delete_orphans:
            # Delete feeds that only belong to this category
            mappings = await self.db.get_all_feed_category_mappings()
            for feed_id, cats in mappings.items():
                if category_id in cats and len(cats) == 1:
                    await self.db.delete_feed(feed_id)
        await self.db.delete_category(category_id)
        await self._reload_feeds()
        self.notify("Category deleted")
        await self._update_unread_title()

    async def on_feed_list_panel_category_move_requested(
        self, msg: FeedListPanel.CategoryMoveRequested
    ) -> None:
        categories = await self.db.get_categories()
        cat_ids = [c["id"] for c in categories]
        if msg.category_id not in cat_ids:
            return
        idx = cat_ids.index(msg.category_id)
        new_idx = idx + msg.direction
        if new_idx < 0 or new_idx >= len(cat_ids):
            return
        # Swap sort_order values
        for i, cat in enumerate(categories):
            await self.db.update_category_sort(cat["id"], i)
        # Now swap the two
        await self.db.update_category_sort(cat_ids[idx], new_idx)
        await self.db.update_category_sort(cat_ids[new_idx], idx)
        await self._reload_feeds()

    # -- Article Events --

    async def on_article_list_panel_article_selected(self, msg: ArticleListPanel.ArticleSelected) -> None:
        preview = self.query_one("#preview-panel", ArticleViewPanel)
        await preview.show_article(self.db, msg.article_id, http_client=self._http_client)
        # Update article list to show read status
        article = await self.db.get_article(msg.article_id)
        if article:
            articles_panel = self.query_one("#articles-panel", ArticleListPanel)
            articles_panel.update_article_status(
                msg.article_id, bool(article["is_read"]), bool(article["is_starred"])
            )
        await self._update_unread_title()

    async def on_article_list_panel_article_toggle_read(self, msg: ArticleListPanel.ArticleToggleRead) -> None:
        article = await self.db.get_article(msg.article_id)
        if article:
            new_read = not bool(article["is_read"])
            await self.db.mark_read(msg.article_id, new_read)
            articles_panel = self.query_one("#articles-panel", ArticleListPanel)
            articles_panel.update_article_status(
                msg.article_id, new_read, bool(article["is_starred"])
            )
            await self._reload_feeds()
            await self._update_unread_title()

    async def on_article_list_panel_article_toggle_star(self, msg: ArticleListPanel.ArticleToggleStar) -> None:
        new_starred = await self.db.toggle_star(msg.article_id)
        article = await self.db.get_article(msg.article_id)
        if article:
            articles_panel = self.query_one("#articles-panel", ArticleListPanel)
            articles_panel.update_article_status(
                msg.article_id, bool(article["is_read"]), new_starred
            )

    async def on_article_list_panel_article_open_browser(self, msg: ArticleListPanel.ArticleOpenBrowser) -> None:
        self._open_in_browser(msg.url)

    async def on_article_list_panel_mark_all_read(self, msg: ArticleListPanel.MarkAllRead) -> None:
        await self.db.mark_all_read(msg.feed_id)
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        await articles_panel.load_articles(self.db, msg.feed_id)
        await self._reload_feeds()
        await self._update_unread_title()
        self.notify("All articles marked as read")

    async def on_article_view_panel_article_open_browser(self, msg: ArticleViewPanel.ArticleOpenBrowser) -> None:
        self._open_in_browser(msg.url)

    async def on_article_view_panel_fetch_full_article(self, msg: ArticleViewPanel.FetchFullArticle) -> None:
        self.run_worker(self._do_fetch_full_article(msg.article_id, msg.url))

    async def _do_fetch_full_article(self, article_id: int, url: str) -> None:
        preview = self.query_one("#preview-panel", ArticleViewPanel)
        article = await self.db.get_article(article_id)
        if not article:
            return
        await preview._show_header(article, "*Fetching full article...*")
        from .services.extractor import extract_article
        extracted = await extract_article(self._http_client, url)
        if extracted:
            await self.db.db.execute(
                "UPDATE articles SET content = ? WHERE id = ?",
                (extracted, article_id),
            )
            await self.db.db.commit()
            await preview.show_article(self.db, article_id)
        else:
            self.notify("Could not extract article content", severity="warning")

    # -- Actions --

    async def action_add_feed(self) -> None:
        categories = await self.db.get_categories()
        cat_list = [(c["id"], c["name"]) for c in categories]

        def handle_result(result: tuple[str, list[int]] | None) -> None:
            if result:
                self.run_worker(self._do_add_feed(result[0], result[1]))

        self.push_screen(AddFeedScreen(cat_list), handle_result)

    async def _do_add_feed(self, url: str, category_ids: list[int]) -> None:
        self.notify(f"Adding feed: {url}...")
        feed_id, error = await self.feed_service.add_feed(
            url, category_ids or None
        )
        if error:
            self.notify(f"Error: {error}", severity="error")
        else:
            await self._reload_feeds()
            self.notify("Feed added successfully!")
            await self._update_unread_title()

    async def action_add_scraper(self) -> None:
        categories = await self.db.get_categories()
        cat_list = [(c["id"], c["name"]) for c in categories]

        def handle_result(result: tuple[str, list[int]] | None) -> None:
            if result:
                self.run_worker(self._do_add_scraper(result[0], result[1]))

        self.push_screen(AddScraperScreen(cat_list), handle_result)

    async def _do_add_scraper(self, path_str: str, category_ids: list[int]) -> None:
        path = Path(path_str).expanduser()
        if not path.exists():
            self.notify(f"File not found: {path}", severity="error")
            return
        self.notify(f"Adding scraper feed from {path.name}...")
        feed_id, error = await self.feed_service.add_scraper_feed(
            path, category_ids or None
        )
        if error:
            self.notify(f"Error: {error}", severity="error")
        else:
            await self._reload_feeds()
            self.notify("Scraper feed added successfully!")
            await self._update_unread_title()

    async def action_refresh_all(self) -> None:
        self.notify("Refreshing all feeds...")
        self.run_worker(self._do_refresh_all())

    async def _do_refresh_all(self) -> None:
        errors = await self.feed_service.refresh_all()
        await self._reload_feeds()
        error_count = sum(1 for e in errors.values() if e)
        total = len(errors)
        if error_count:
            self.notify(f"Refreshed {total - error_count}/{total} feeds ({error_count} errors)", severity="warning")
        else:
            self.notify(f"Refreshed {total} feeds")
        await self._update_unread_title()

    async def _auto_refresh(self) -> None:
        await self._do_refresh_all()

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    async def action_search(self) -> None:
        def handle_search(query: str | None) -> None:
            if query:
                self.run_worker(self._do_search(query))

        self.push_screen(SearchScreen(), handle_search)

    async def action_clear_search(self) -> None:
        if self._search_active:
            self._search_active = False
            articles_panel = self.query_one("#articles-panel", ArticleListPanel)
            await articles_panel.load_articles(self.db, self._current_feed_id)
            articles_panel.border_title = "Articles"
            self._focus_panel(1)

    async def _do_search(self, query: str) -> None:
        self._search_active = True
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        await articles_panel.load_articles(
            self.db, self._current_feed_id, search=query
        )
        articles_panel.border_title = f"Articles - Search: {query}"
        self._focus_panel(1)

    async def action_import_opml(self) -> None:
        def handle_result(result: tuple[str, str] | None) -> None:
            if result:
                self.run_worker(self._do_import_opml(result[1]))

        self.push_screen(OPMLScreen("import"), handle_result)

    async def _do_import_opml(self, source: str) -> None:
        import tempfile
        if source.startswith(("http://", "https://")):
            # Download OPML from URL
            self.notify(f"Downloading OPML from {source}...")
            try:
                resp = await self._http_client.get(source, follow_redirects=True)
                resp.raise_for_status()
            except Exception as e:
                self.notify(f"Download failed: {e}", severity="error")
                return
            tmp = tempfile.NamedTemporaryFile(suffix=".opml", delete=False)
            tmp.write(resp.content)
            tmp.close()
            path = Path(tmp.name)
        else:
            path = Path(source).expanduser()
            if not path.exists():
                self.notify(f"File not found: {path}", severity="error")
                return
        self.notify("Importing OPML...")
        result = await import_opml(self.db, self.feed_service, path)
        await self._reload_feeds()
        msg = f"Imported: {result.added} added, {result.skipped} skipped"
        if result.errors:
            msg += f", {len(result.errors)} errors"
        self.notify(msg)
        await self._update_unread_title()

    async def action_export_opml(self) -> None:
        def handle_result(result: tuple[str, str] | None) -> None:
            if result:
                self.run_worker(self._do_export_opml(result[1]))

        self.push_screen(OPMLScreen("export"), handle_result)

    async def _do_export_opml(self, path_str: str) -> None:
        path = Path(path_str).expanduser()
        await export_opml(self.db, path)
        self.notify(f"Exported to {path}")

    async def action_create_category(self) -> None:
        def handle_result(name: str | None) -> None:
            if name:
                self.run_worker(self._do_create_category(name))

        self.push_screen(CategoryScreen(), handle_result)

    async def _do_create_category(self, name: str) -> None:
        try:
            await self.db.add_category(name)
            await self._reload_feeds()
            self.notify(f"Category '{name}' created")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    async def action_filter_unread(self) -> None:
        self._filter_mode = "unread" if self._filter_mode != "unread" else "all"
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        suffix = " (unread)" if self._filter_mode == "unread" else ""
        await articles_panel.load_articles(
            self.db, self._current_feed_id,
            unread_only=self._filter_mode == "unread",
        )
        feed_name = articles_panel.border_title.split(" - ")[1] if " - " in (articles_panel.border_title or "") else "All"
        articles_panel.border_title = f"Articles - {feed_name}{suffix}"

    async def action_filter_starred(self) -> None:
        self._filter_mode = "starred" if self._filter_mode != "starred" else "all"
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        suffix = " (starred)" if self._filter_mode == "starred" else ""
        await articles_panel.load_articles(
            self.db, self._current_feed_id,
            starred_only=self._filter_mode == "starred",
        )
        feed_name = articles_panel.border_title.split(" - ")[1] if " - " in (articles_panel.border_title or "") else "All"
        articles_panel.border_title = f"Articles - {feed_name}{suffix}"

    # -- Helpers --

    def _open_in_browser(self, url: str) -> None:
        if self._config.default_browser_cmd:
            import subprocess
            subprocess.Popen([self._config.default_browser_cmd, url])
        else:
            webbrowser.open(url)

    async def _reload_feeds(self) -> None:
        feed_panel = self.query_one("#feeds-panel", FeedListPanel)
        await feed_panel.load_feeds(self.db)
        # Also reload the currently visible article list
        articles_panel = self.query_one("#articles-panel", ArticleListPanel)
        await articles_panel.load_articles(
            self.db,
            self._current_feed_id,
            category_id=self._current_category_id,
            unread_only=self._filter_mode == "unread",
            starred_only=self._filter_mode == "starred",
        )

    async def _update_unread_title(self) -> None:
        unread = await self.db.get_total_unread_count()
        self.sub_title = f"{unread} unread" if unread else ""


def main():
    app = RSSApp()
    app.run()


if __name__ == "__main__":
    main()
