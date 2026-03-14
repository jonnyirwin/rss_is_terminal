"""Article preview panel using Markdown rendering."""

from __future__ import annotations

import re
import webbrowser
from datetime import datetime

import html2text
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Markdown, Static


class ArticleScroller(VerticalScroll, can_focus=True):
    """Scrollable container for article content with vim keybindings."""

    BINDINGS = [
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G", "scroll_end", "Bottom", show=False),
    ]


class ArticleViewPanel(Widget, can_focus=False, can_focus_children=True):
    """Bottom-right panel showing article content."""

    class ArticleOpenBrowser(Message):
        def __init__(self, url: str) -> None:
            super().__init__()
            self.url = url

    class FetchFullArticle(Message):
        def __init__(self, article_id: int, url: str) -> None:
            super().__init__()
            self.article_id = article_id
            self.url = url

    BINDINGS = [
        Binding("o", "open_browser", "Open Browser", show=False),
        Binding("f", "fetch_full", "Full Article", show=False),
        Binding("n", "next_link", "Next Link", show=False),
        Binding("N", "prev_link", "Prev Link", show=False),
        Binding("enter", "open_selected_link", "Open Link", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_url: str | None = None
        self._current_article_id: int | None = None
        self._converter = html2text.HTML2Text()
        self._converter.body_width = 0
        self._converter.ignore_images = False
        self._converter.ignore_links = False
        self._converter.protect_links = True
        self._converter.wrap_links = False
        self._links: list[tuple[str, str]] = []  # (text, url)
        self._selected_link: int = -1  # -1 = no selection
        self._md_text: str = ""

    def compose(self):
        with ArticleScroller(id="article-scroller"):
            yield Markdown(id="article-content")

    @property
    def content_widget(self) -> Markdown:
        return self.query_one("#article-content", Markdown)

    async def show_article(self, db, article_id: int, http_client=None) -> None:
        article = await db.get_article(article_id)
        if not article:
            await self.content_widget.update("*Article not found.*")
            return

        self._current_url = article["url"]
        self._current_article_id = article_id

        html_content = article["content"] or article["summary"] or ""

        # Build markdown content
        self._md_text = self._build_markdown(article, html_content)
        self._links = self._extract_links(self._md_text)
        self._selected_link = -1
        await self.content_widget.update(self._md_text)

        # Mark as read
        if not article["is_read"]:
            await db.mark_read(article_id, True)

    def _extract_links(self, md_text: str) -> list[tuple[str, str]]:
        """Extract all markdown links as (display_text, url) tuples."""
        links = []
        for m in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', md_text):
            text, url = m.group(1), m.group(2)
            links.append((text, url))
        return links

    def _highlight_link(self, md_text: str, link_index: int) -> str:
        """Re-render markdown with the selected link highlighted."""
        links = list(re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', md_text))
        if link_index < 0 or link_index >= len(links):
            return md_text

        match = links[link_index]
        text, url = match.group(1), match.group(2)
        start, end = match.start(), match.end()
        highlighted = f"**>>> [{text}]({url}) <<<**"
        return md_text[:start] + highlighted + md_text[end:]

    async def _update_link_highlight(self) -> None:
        """Update the display with the current link highlighted."""
        if self._selected_link >= 0:
            highlighted = self._highlight_link(self._md_text, self._selected_link)
        else:
            highlighted = self._md_text
        await self.content_widget.update(highlighted)

        # Scroll the selected link into view
        if self._selected_link >= 0:
            await self._scroll_to_link()

    async def _scroll_to_link(self) -> None:
        """Scroll so the selected link is visible."""
        md = self.content_widget
        scroller = self.query_one("#article-scroller", ArticleScroller)
        # Find the block containing the link
        links_seen = 0
        target_block = None
        link_text = self._links[self._selected_link][0] if self._selected_link >= 0 else None
        if link_text:
            for block in md.children:
                block_text = str(block.render()) if hasattr(block, 'render') else ""
                if link_text in block_text or f">>> " in block_text:
                    target_block = block
                    break
        if target_block:
            scroller.scroll_to_widget(target_block, animate=False)

    def _build_markdown(self, article, html_content: str) -> str:
        parts = []
        parts.append(f"# {article['title'] or '(no title)'}")
        parts.append("")

        meta = []
        if article["author"]:
            meta.append(f"**{article['author']}**")
        if article["feed_title"]:
            meta.append(f"*{article['feed_title']}*")
        if article["published_at"]:
            try:
                dt = datetime.fromisoformat(article["published_at"])
                meta.append(dt.strftime("%Y-%m-%d %H:%M"))
            except (ValueError, TypeError):
                meta.append(article["published_at"])
        if meta:
            parts.append(" | ".join(meta))
            parts.append("")

        if article["url"]:
            parts.append(f"[Original Article]({article['url']})")
            parts.append("")

        parts.append("---")
        parts.append("")

        if html_content and html_content.strip():
            md_content = self._converter.handle(html_content).strip()
            parts.append(md_content)
        else:
            parts.append("*No content available. Press **o** to open in browser.*")

        return "\n".join(parts)

    @staticmethod
    def _has_meaningful_content(html: str) -> bool:
        """Check if HTML content is real article text, not just a bare link."""
        if not html:
            return False
        stripped = html.strip()
        if len(stripped) < 20:
            return False
        import re
        text_only = re.sub(r"<[^>]+>", "", stripped).strip()
        if len(text_only) < 20:
            return False
        return True

    async def _show_header(self, article, status_text: str) -> None:
        """Show article header with a status message (e.g. loading indicator)."""
        parts = [
            f"# {article['title'] or '(no title)'}",
            "",
            status_text,
        ]
        await self.content_widget.update("\n".join(parts))

    async def show_welcome(self) -> None:
        self._links = []
        self._selected_link = -1
        self._md_text = ""
        await self.content_widget.update(
            "# Welcome to RSS is Terminal\n\n"
            "Get started:\n\n"
            "- Press **a** to add a feed\n"
            "- Press **I** to import an OPML file\n"
            "- Press **?** for help\n\n"
            "Navigate with **Tab** to switch panels, **j/k** to move, **Enter** to select."
        )

    async def clear(self) -> None:
        self._links = []
        self._selected_link = -1
        self._md_text = ""
        await self.content_widget.update("")

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        """Open any clicked link in the browser."""
        event.stop()
        if event.href:
            self.post_message(self.ArticleOpenBrowser(event.href))

    def action_open_browser(self) -> None:
        if self._current_url:
            self.post_message(self.ArticleOpenBrowser(self._current_url))

    def action_fetch_full(self) -> None:
        if self._current_article_id and self._current_url:
            self.post_message(self.FetchFullArticle(self._current_article_id, self._current_url))

    def action_next_link(self) -> None:
        if not self._links:
            return
        self._selected_link = (self._selected_link + 1) % len(self._links)
        self.run_worker(self._update_link_highlight())

    def action_prev_link(self) -> None:
        if not self._links:
            return
        if self._selected_link <= 0:
            self._selected_link = len(self._links) - 1
        else:
            self._selected_link -= 1
        self.run_worker(self._update_link_highlight())

    def action_open_selected_link(self) -> None:
        if self._selected_link >= 0 and self._selected_link < len(self._links):
            url = self._links[self._selected_link][1]
            self.post_message(self.ArticleOpenBrowser(url))
