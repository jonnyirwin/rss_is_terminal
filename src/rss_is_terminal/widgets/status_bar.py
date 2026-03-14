"""Status bar widget."""

from __future__ import annotations

from textual.widgets import Static


class StatusBar(Static):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._context = ""
        self._last_refresh = ""
        self._unread_count = 0

    def set_context(self, text: str) -> None:
        self._context = text
        self._update_display()

    def set_last_refresh(self, text: str) -> None:
        self._last_refresh = text
        self._update_display()

    def set_unread_count(self, count: int) -> None:
        self._unread_count = count
        self._update_display()

    def _update_display(self) -> None:
        parts = []
        if self._context:
            parts.append(self._context)
        if self._last_refresh:
            parts.append(f"Last refresh: {self._last_refresh}")
        if self._unread_count > 0:
            parts.append(f"{self._unread_count} unread")
        self.update(" | ".join(parts) if parts else "RSS is Terminal")
