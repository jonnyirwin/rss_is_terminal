"""Scraper configuration model and loader."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FieldSelector:
    css: str
    attribute: str | None = None  # None = get text, "href"/"datetime"/etc = get attr


@dataclass
class PaginationConfig:
    next_selector: FieldSelector
    max_pages: int = 3


@dataclass
class ScraperConfig:
    name: str
    url: str
    article_selector: str
    fields: dict[str, FieldSelector]
    js_render: bool = False
    wait_for: str | None = None
    pagination: PaginationConfig | None = None


def parse_field_selector(s: str) -> FieldSelector:
    """Parse a selector string like 'h2 a @href' into a FieldSelector."""
    parts = s.rsplit(" @", 1)
    if len(parts) == 2:
        return FieldSelector(css=parts[0].strip(), attribute=parts[1].strip())
    return FieldSelector(css=s.strip())


def load_config(path: Path) -> ScraperConfig:
    """Load a scraper config from a JSON file."""
    with open(path) as f:
        data = json.load(f)

    fields = {}
    for name, selector_str in data.get("fields", {}).items():
        fields[name] = parse_field_selector(selector_str)

    pagination = None
    if data.get("pagination"):
        pag = data["pagination"]
        pagination = PaginationConfig(
            next_selector=parse_field_selector(pag["next_selector"]),
            max_pages=pag.get("max_pages", 3),
        )

    return ScraperConfig(
        name=data["name"],
        url=data["url"],
        article_selector=data["article_selector"],
        fields=fields,
        js_render=data.get("js_render", False),
        wait_for=data.get("wait_for"),
        pagination=pagination,
    )
