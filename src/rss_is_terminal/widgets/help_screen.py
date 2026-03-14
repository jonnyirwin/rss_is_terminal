"""Help screen showing keybinding reference."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[bold cyan]RSS is Terminal - Keybindings[/bold cyan]

[bold]Global[/bold]
  [cyan]Tab[/cyan] / [cyan]Shift+Tab[/cyan]  Cycle panels
  [cyan]h[/cyan] / [cyan]l[/cyan]              Panel left / right
  [cyan]a[/cyan]                  Add feed
  [cyan]W[/cyan]                  Add scraper feed
  [cyan]R[/cyan]                  Refresh all feeds
  [cyan]/[/cyan]                  Search articles
  [cyan]I[/cyan]                  Import OPML
  [cyan]E[/cyan]                  Export OPML
  [cyan]?[/cyan]                  This help screen
  [cyan]q[/cyan]                  Quit

[bold]Feed List[/bold]
  [cyan]j[/cyan] / [cyan]k[/cyan]              Move down / up
  [cyan]Enter[/cyan]              Select feed
  [cyan]o[/cyan]                  Collapse / expand category
  [cyan]d[/cyan]                  Delete feed / category
  [cyan]c[/cyan]                  Manage feed categories
  [cyan]C[/cyan]                  Create category
  [cyan]J[/cyan] / [cyan]K[/cyan]              Move category down / up

[bold]Article List[/bold]
  [cyan]j[/cyan] / [cyan]k[/cyan]              Move down / up
  [cyan]Enter[/cyan]              Preview article
  [cyan]r[/cyan]                  Toggle read / unread
  [cyan]s[/cyan]                  Toggle star
  [cyan]o[/cyan]                  Open in browser
  [cyan]A[/cyan]                  Mark all read
  [cyan]u[/cyan]                  Filter: unread only
  [cyan]S[/cyan]                  Filter: starred only
  [cyan]a[/cyan]                  Filter: show all

[bold]Article Preview[/bold]
  [cyan]j[/cyan] / [cyan]k[/cyan]              Scroll down / up
  [cyan]g[/cyan] / [cyan]G[/cyan]              Top / bottom
  [cyan]o[/cyan]                  Open in browser
  [cyan]f[/cyan]                  Fetch full article
  [cyan]n[/cyan] / [cyan]N[/cyan]              Next / previous link
  [cyan]Enter[/cyan]              Open selected link

[dim]Press Escape or ? to close[/dim]
"""


class HelpScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Static(HELP_TEXT)

    def on_key(self, event) -> None:
        if event.key in ("escape", "question_mark"):
            self.dismiss()
