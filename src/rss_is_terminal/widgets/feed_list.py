"""Feed list panel with tree-based category/feed navigation."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, Tree


@dataclass
class CategoryData:
    id: int
    name: str


@dataclass
class FeedData:
    id: int
    title: str
    url: str
    unread_count: int = 0
    has_error: bool = False


class FeedTree(Tree):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_cursor", "Select", show=False),
        Binding("o", "toggle_parent", "Toggle", show=False),
        Binding("O", "collapse_all", "Collapse All", show=False),
    ]

    def action_toggle_parent(self) -> None:
        """Toggle the current node if it's a category, or its parent category if it's a feed."""
        node = self.cursor_node
        if node is None:
            return
        if isinstance(node.data, CategoryData):
            node.toggle()
        elif isinstance(node.data, FeedData) and node.parent and isinstance(node.parent.data, CategoryData):
            node.parent.toggle()
        else:
            node.toggle()

    def action_collapse_all(self) -> None:
        """Toggle all category nodes between collapsed and expanded."""
        category_nodes = [n for n in self.root.children if isinstance(n.data, CategoryData)]
        if not category_nodes:
            return
        # If any are expanded, collapse all; otherwise expand all
        any_expanded = any(n.is_expanded for n in category_nodes)
        for node in category_nodes:
            if any_expanded:
                node.collapse()
            else:
                node.expand()


class FeedListPanel(Widget, can_focus=False, can_focus_children=True):
    """Left panel showing feeds organized by category."""

    class FeedSelected(Message):
        def __init__(self, feed_id: int, feed_title: str) -> None:
            super().__init__()
            self.feed_id = feed_id
            self.feed_title = feed_title

    class FeedDeleteRequested(Message):
        def __init__(self, feed_id: int, feed_title: str) -> None:
            super().__init__()
            self.feed_id = feed_id
            self.feed_title = feed_title

    class AllFeedsSelected(Message):
        pass

    class CategorySelected(Message):
        def __init__(self, category_id: int, category_name: str) -> None:
            super().__init__()
            self.category_id = category_id
            self.category_name = category_name

    class StarredSelected(Message):
        pass

    class FeedCategoriesRequested(Message):
        def __init__(self, feed_id: int, feed_title: str) -> None:
            super().__init__()
            self.feed_id = feed_id
            self.feed_title = feed_title

    class CategoryDeleteRequested(Message):
        def __init__(self, category_id: int, category_name: str) -> None:
            super().__init__()
            self.category_id = category_id
            self.category_name = category_name

    class CategoryMoveRequested(Message):
        def __init__(self, category_id: int, direction: int) -> None:
            super().__init__()
            self.category_id = category_id
            self.direction = direction  # -1 = up, +1 = down

    class MarkFeedReadRequested(Message):
        def __init__(self, feed_id: int) -> None:
            super().__init__()
            self.feed_id = feed_id

    class MarkCategoryReadRequested(Message):
        def __init__(self, category_id: int) -> None:
            super().__init__()
            self.category_id = category_id

    class MarkAllFeedsReadRequested(Message):
        pass

    BINDINGS = [
        Binding("d", "delete_item", "Delete", show=False),
        Binding("c", "manage_categories", "Categories", show=False),
        Binding("J", "move_down", "Move Down", show=False),
        Binding("K", "move_up", "Move Up", show=False),
        Binding("A", "mark_read", "Mark Read", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._collapsed_categories: set[int] | None = None  # None = first load, collapse all

    def compose(self):
        tree = FeedTree("Feeds", id="feed-tree")
        tree.show_root = True
        tree.root.expand()
        yield tree

    @property
    def tree(self) -> FeedTree:
        return self.query_one("#feed-tree", FeedTree)

    def _save_collapsed_state(self) -> None:
        """Persist which categories are collapsed."""
        tree = self.tree
        self._collapsed_categories = set()
        for node in tree.root.children:
            if isinstance(node.data, CategoryData) and not node.is_expanded:
                self._collapsed_categories.add(node.data.id)

    async def load_feeds(self, db) -> None:
        tree = self.tree

        # Save collapsed state before clearing
        self._save_collapsed_state()

        tree.clear()
        tree.root.data = None

        # Add "All Feeds" node with total unread count
        total_unread = await db.get_total_unread_count()
        if total_unread > 0:
            all_label = f"[bold]All Feeds[/bold] [cyan]({total_unread})[/cyan]"
        else:
            all_label = "All Feeds"
        all_node = tree.root.add(all_label)
        all_node.data = "all"

        # Add "Starred" node
        starred_count = await db.get_starred_count()
        starred_label = "Starred"
        if starred_count > 0:
            starred_label = f"[bold]Starred[/bold] [yellow]({starred_count})[/yellow]"
        starred_node = tree.root.add(starred_label)
        starred_node.data = "starred"

        categories = await db.get_categories()
        feeds = await db.get_feeds()
        feed_cat_map = await db.get_all_feed_category_mappings()

        # Build a set of feed IDs that belong to at least one category
        categorized_ids: set[int] = set()
        for feed_id, cat_ids in feed_cat_map.items():
            if cat_ids:
                categorized_ids.add(feed_id)

        # Build feed lookup
        feed_by_id = {f["id"]: f for f in feeds}

        # Add categorized feeds (a feed can appear under multiple categories)
        for cat in categories:
            cat_feeds = [
                feed_by_id[fid] for fid, cats in feed_cat_map.items()
                if cat["id"] in cats and fid in feed_by_id
            ]
            unread_total = 0
            cat_node = tree.root.add(cat["name"], data=CategoryData(cat["id"], cat["name"]))
            for feed in sorted(cat_feeds, key=lambda f: (f["sort_order"], f["title"])):
                unread = await db.get_unread_count(feed["id"])
                unread_total += unread
                has_error = bool(feed["fetch_error"])
                label = self._feed_label(feed["title"], unread, has_error)
                cat_node.add_leaf(label, data=FeedData(
                    id=feed["id"], title=feed["title"],
                    url=feed["url"], unread_count=unread, has_error=has_error
                ))
            if unread_total > 0:
                cat_node.label = f"{cat['name']} ({unread_total})"
            if self._collapsed_categories is not None and cat["id"] not in self._collapsed_categories:
                cat_node.expand()

        # Uncategorized feeds (not in any category)
        uncategorized = [f for f in feeds if f["id"] not in categorized_ids]
        if uncategorized:
            for feed in uncategorized:
                unread = await db.get_unread_count(feed["id"])
                has_error = bool(feed["fetch_error"])
                label = self._feed_label(feed["title"], unread, has_error)
                tree.root.add_leaf(label, data=FeedData(
                    id=feed["id"], title=feed["title"],
                    url=feed["url"], unread_count=unread, has_error=has_error
                ))

        tree.root.expand()

    def _feed_label(self, title: str, unread: int, has_error: bool) -> str:
        if has_error:
            label = f"[red]{title}[/red]"
        elif unread > 0:
            label = f"[bold]{title}[/bold] [cyan]({unread})[/cyan]"
        else:
            label = title
        return label

    @on(Tree.NodeSelected)
    def on_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if node.data == "all":
            self.post_message(self.AllFeedsSelected())
        elif node.data == "starred":
            self.post_message(self.StarredSelected())
        elif isinstance(node.data, CategoryData):
            self.post_message(self.CategorySelected(node.data.id, node.data.name))
        elif isinstance(node.data, FeedData):
            self.post_message(self.FeedSelected(node.data.id, node.data.title))

    def action_delete_item(self) -> None:
        tree = self.tree
        node = tree.cursor_node
        if node and isinstance(node.data, FeedData):
            self.post_message(self.FeedDeleteRequested(node.data.id, node.data.title))
        elif node and isinstance(node.data, CategoryData):
            self.post_message(self.CategoryDeleteRequested(node.data.id, node.data.name))

    def action_manage_categories(self) -> None:
        tree = self.tree
        node = tree.cursor_node
        if node and isinstance(node.data, FeedData):
            self.post_message(self.FeedCategoriesRequested(node.data.id, node.data.title))

    def action_move_down(self) -> None:
        tree = self.tree
        node = tree.cursor_node
        if node and isinstance(node.data, CategoryData):
            self.post_message(self.CategoryMoveRequested(node.data.id, 1))

    def action_move_up(self) -> None:
        tree = self.tree
        node = tree.cursor_node
        if node and isinstance(node.data, CategoryData):
            self.post_message(self.CategoryMoveRequested(node.data.id, -1))

    def action_mark_read(self) -> None:
        tree = self.tree
        node = tree.cursor_node
        if node and isinstance(node.data, FeedData):
            self.post_message(self.MarkFeedReadRequested(node.data.id))
        elif node and isinstance(node.data, CategoryData):
            self.post_message(self.MarkCategoryReadRequested(node.data.id))
        elif node and node.data == "all":
            self.post_message(self.MarkAllFeedsReadRequested())
