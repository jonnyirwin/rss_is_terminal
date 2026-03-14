"""Tests for scraper config parsing and loading."""

import json

import pytest

from rss_is_terminal.services.scraper_config import (
    FieldSelector,
    PaginationConfig,
    ScraperConfig,
    load_config,
    parse_field_selector,
)


class TestParseFieldSelector:
    def test_text_selector(self):
        fs = parse_field_selector("h2 a")
        assert fs.css == "h2 a"
        assert fs.attribute is None

    def test_attribute_selector(self):
        fs = parse_field_selector("h2 a @href")
        assert fs.css == "h2 a"
        assert fs.attribute == "href"

    def test_datetime_attribute(self):
        fs = parse_field_selector("time @datetime")
        assert fs.css == "time"
        assert fs.attribute == "datetime"

    def test_whitespace_handling(self):
        fs = parse_field_selector("  div.post  h2  ")
        assert fs.css == "div.post  h2"

    def test_complex_selector_with_attribute(self):
        fs = parse_field_selector("div.content > a.link @href")
        assert fs.css == "div.content > a.link"
        assert fs.attribute == "href"

    def test_at_sign_in_selector_not_attribute(self):
        # @ only treated as attribute when preceded by space
        fs = parse_field_selector("div@media")
        assert fs.css == "div@media"
        assert fs.attribute is None


class TestLoadConfig:
    def test_minimal_config(self, tmp_path):
        config = {
            "name": "Test",
            "url": "https://example.com",
            "article_selector": "div.post",
            "fields": {"title": "h2"},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))

        result = load_config(path)
        assert result.name == "Test"
        assert result.url == "https://example.com"
        assert result.article_selector == "div.post"
        assert "title" in result.fields
        assert result.js_render is False
        assert result.wait_for is None
        assert result.pagination is None

    def test_full_config(self, scraper_config_file):
        result = load_config(scraper_config_file)
        assert result.name == "Test Blog"
        assert result.fields["url"].attribute == "href"
        assert result.fields["title"].attribute is None
        assert result.fields["published_at"].attribute == "datetime"

    def test_config_with_pagination(self, tmp_path):
        config = {
            "name": "Paginated",
            "url": "https://example.com",
            "article_selector": "article",
            "fields": {"title": "h2"},
            "pagination": {
                "next_selector": "a.next @href",
                "max_pages": 5,
            },
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))

        result = load_config(path)
        assert result.pagination is not None
        assert result.pagination.next_selector.css == "a.next"
        assert result.pagination.next_selector.attribute == "href"
        assert result.pagination.max_pages == 5

    def test_config_with_js_render(self, tmp_path):
        config = {
            "name": "JS Site",
            "url": "https://example.com",
            "article_selector": "div",
            "fields": {"title": "h2"},
            "js_render": True,
            "wait_for": ".loaded",
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))

        result = load_config(path)
        assert result.js_render is True
        assert result.wait_for == ".loaded"

    def test_pagination_default_max_pages(self, tmp_path):
        config = {
            "name": "Test",
            "url": "https://example.com",
            "article_selector": "div",
            "fields": {"title": "h2"},
            "pagination": {"next_selector": "a.next @href"},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))

        result = load_config(path)
        assert result.pagination.max_pages == 3

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        with pytest.raises(Exception):
            load_config(path)

    def test_missing_required_field_raises(self, tmp_path):
        config = {"name": "Test"}  # missing url, article_selector, fields
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))
        with pytest.raises(Exception):
            load_config(path)
