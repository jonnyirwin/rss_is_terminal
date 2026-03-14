# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-03-14

### Added

- Three-panel TUI with vim-style keybindings (feeds, articles, preview)
- RSS and Atom feed support via feedparser
- Custom scraper feeds with CSS selector-based extraction
- Optional JavaScript rendering via Playwright for JS-heavy sites
- Scraper pagination support
- Full article content fetching on demand (trafilatura)
- Feed categories with many-to-many assignment
- Category reordering and deletion with orphan handling
- Starred feeds and articles
- Read/unread tracking
- Search across all articles
- Filter by unread or starred
- OPML import (local file or URL) and export
- Configurable refresh interval, timeouts, and concurrency
- Browser extension for Firefox and Chrome
  - Detect RSS/Atom/JSON feeds on any page
  - Point-and-click scraper config builder
  - Category selection when adding feeds
  - Native messaging host for communication with the app
- XDG Base Directory compliant file locations
- HTML-to-Markdown article preview
- Makefile for build, install, and extension packaging
