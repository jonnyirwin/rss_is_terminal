# RSS is Terminal

A terminal-based RSS reader with a lazygit-style TUI, built with [Textual](https://textual.textualize.io/).

Read RSS/Atom feeds, scrape sites that don't offer feeds, manage categories, star articles, and browse everything from your terminal with vim-style keybindings.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## Features

- **Three-panel layout** — feeds, articles, and preview side by side
- **RSS & Atom** — subscribe to any standard feed
- **Custom scrapers** — scrape sites without feeds using CSS selectors
- **JavaScript rendering** — optional Playwright support for JS-heavy sites
- **Categories** — organise feeds into categories (many-to-many)
- **OPML import/export** — migrate from other readers (file or URL)
- **Full article fetch** — pull complete article content on demand
- **Search & filter** — search across all articles, filter by unread or starred
- **Vim keybindings** — navigate entirely from the keyboard
- **Browser extension** — detect feeds on any page and build scraper configs with point-and-click
- **XDG compliant** — config in `~/.config/rss_is_terminal/`, data in `~/.local/share/rss_is_terminal/`

## Installation

### From source (recommended)

```bash
git clone https://github.com/jonnyirwin/rss_is_terminal.git
cd rss_is_terminal
```

**Option A — pipx (isolated environment, recommended):**

```bash
make install-pipx
```

**Option B — user install:**

```bash
make install-user
```

**Option C — development mode:**

```bash
make dev
source .venv/bin/activate
```

### Upgrading

After pulling new changes:

```bash
make upgrade
```

### With JavaScript rendering support

For scraping JS-heavy sites that need a headless browser:

```bash
make install-js
```

This installs [Playwright](https://playwright.dev/python/) and downloads Chromium.

### Requirements

- Python 3.11 or newer
- pip or pipx

## Usage

```bash
rss-terminal
```

Or in development mode:

```bash
make run
```

### Adding feeds

Press `a` to add an RSS/Atom feed by URL. Press `W` to add a scraper feed from a JSON config file.

### Importing from another reader

Press `I` to import an OPML file. You can provide a local file path or a URL.

### Exporting

Press `E` to export all feeds and categories to an OPML file.

## Keyboard shortcuts

### Global

| Key | Action |
|-----|--------|
| `q` | Quit |
| `?` | Help |
| `Tab` / `Shift+Tab` | Cycle panels |
| `l` / `h` | Panel right / left |
| `R` | Refresh all feeds |
| `a` | Add feed (RSS/Atom) |
| `W` | Add scraper feed |
| `C` | Create category |
| `I` | Import OPML |
| `E` | Export OPML |
| `/` | Search articles |
| `u` | Filter: unread only |
| `S` | Filter: starred only |
| `Escape` | Clear search / filter |

### Feed list

| Key | Action |
|-----|--------|
| `j` / `k` | Move down / up |
| `Enter` | Select feed |
| `o` | Collapse / expand category (works on feeds too) |
| `d` | Delete feed or category |
| `c` | Manage feed categories |
| `J` / `K` | Move category up / down |

### Article list

| Key | Action |
|-----|--------|
| `j` / `k` | Move down / up |
| `Enter` | Preview article |
| `r` | Toggle read / unread |
| `s` | Toggle star |
| `o` | Open in browser |
| `A` | Mark all as read |

### Article preview

| Key | Action |
|-----|--------|
| `j` / `k` | Scroll down / up |
| `g` / `G` | Jump to top / bottom |
| `o` | Open in browser |
| `f` | Fetch full article content |
| `n` / `N` | Next / previous link |
| `Enter` | Open selected link in browser |

## Custom scraper feeds

For sites that don't provide RSS feeds, you can create a JSON scraper config:

```json
{
  "name": "Example Blog",
  "url": "https://example.com/blog",
  "article_selector": "div.post",
  "fields": {
    "title": "h2 a",
    "url": "h2 a @href",
    "author": "span.author",
    "published_at": "time @datetime",
    "summary": "p.excerpt"
  }
}
```

### Config reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Display name for the feed |
| `url` | yes | Page URL to scrape |
| `article_selector` | yes | CSS selector matching each article on the page |
| `fields` | yes | Map of field name to CSS selector (see below) |
| `js_render` | no | `true` to render JavaScript with Playwright |
| `wait_for` | no | CSS selector to wait for before scraping (JS sites) |
| `pagination` | no | Pagination config (see below) |

### Field selectors

Each field value is a CSS selector, optionally with an `@attribute` suffix:

- `"h2 a"` — extracts the text content of the element
- `"h2 a @href"` — extracts the `href` attribute
- `"time @datetime"` — extracts the `datetime` attribute

Supported field names: `title`, `url`, `author`, `published_at`, `summary`.

### Pagination

```json
{
  "pagination": {
    "next_selector": "a.next @href",
    "max_pages": 3
  }
}
```

### JavaScript rendering

Set `"js_render": true` for sites that load content via JavaScript. Requires the `js` extra:

```bash
pip install "rss-is-terminal[js]"
python -m playwright install chromium
```

Store scraper configs in `~/.config/rss_is_terminal/scrapers/`.

## Browser extension

A companion browser extension lets you detect feeds on any page and build scraper configs with point-and-click.

### Building

```bash
make extension
```

This produces:
- `dist/extension/rss_is_terminal-firefox.xpi` — Firefox add-on
- `dist/extension/rss_is_terminal-chrome.zip` — Chrome/Chromium extension

### Installing

**Firefox:** Open `about:addons` > gear icon > "Install Add-on From File" > select the `.xpi` file.

**Chrome:** Open `chrome://extensions` > enable "Developer mode" > "Load unpacked" or drag the `.zip` file.

### Native messaging host

The extension communicates with the app via native messaging. Install the host after installing the extension:

```bash
# Firefox (auto-detected)
make native-host

# Chrome / Chromium / Brave (needs extension ID)
make native-host-chrome
```

For Chrome, you'll be prompted for your extension ID — find it at `chrome://extensions` with Developer Mode enabled.

## Configuration

Optional config file at `~/.config/rss_is_terminal/config.toml`:

```toml
refresh_interval_minutes = 30
max_articles_per_feed = 200
fetch_timeout_seconds = 30
concurrent_fetches = 10
vim_mode = true
# default_browser_cmd = "firefox"
```

## File locations

| Path | Contents |
|------|----------|
| `~/.config/rss_is_terminal/config.toml` | App configuration |
| `~/.config/rss_is_terminal/scrapers/` | Scraper config JSON files |
| `~/.local/share/rss_is_terminal/rss.db` | SQLite database (feeds, articles, categories) |

These follow the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/). Set `XDG_CONFIG_HOME` or `XDG_DATA_HOME` to override.

## Development

```bash
# Option A: use a venv (recommended for development)
make dev
source .venv/bin/activate

# Option B: just run targets directly (installs deps as needed)
make test
make lint
make run
```

## License

[MIT](LICENSE)
