.PHONY: all build install install-user install-pipx install-js extension native-host native-host-chrome dev test lint run clean help

PYTHON ?= python3
PIP ?= pip3

all: build extension ## Build everything

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- Python app ----

build: ## Build Python wheel
	$(PIP) install build
	$(PYTHON) -m build

install: build ## Install system-wide (may need sudo)
	$(PIP) install dist/rss_is_terminal-*.whl

install-user: build ## Install for current user
	$(PIP) install --user dist/rss_is_terminal-*.whl

install-pipx: build ## Install isolated with pipx
	pipx install dist/rss_is_terminal-*.whl

install-js: build ## Install with Playwright (JS rendering) support
	$(PIP) install --user "dist/rss_is_terminal-*.whl[js]"
	$(PYTHON) -m playwright install chromium

# ---- Browser extension ----

extension: ## Build browser extension packages (.xpi + .zip)
	$(PYTHON) browser_extension/build.py

native-host: ## Install native messaging host for browser extension
	bash browser_extension/native_host/install.sh

native-host-chrome: ## Install native host with Chrome extension ID
	@read -p "Chrome extension ID: " ext_id; \
	bash browser_extension/native_host/install.sh --chrome-id "$$ext_id"

# ---- Development ----

dev: ## Set up development environment
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e ".[dev,js]"
	@echo ""
	@echo "Activate with: source .venv/bin/activate"

test: ## Run tests
	$(PIP) install -e ".[dev]"
	$(PYTHON) -m pytest

lint: ## Run linter
	$(PIP) install -e ".[dev]"
	$(PYTHON) -m ruff check src/

run: ## Run the app
	$(PIP) install -e .
	$(PYTHON) -m rss_is_terminal.app

# ---- Cleanup ----

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
