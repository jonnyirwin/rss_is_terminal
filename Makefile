.PHONY: all build install install-user install-pipx upgrade install-js extension native-host native-host-chrome dev test lint run clean help

PYTHON ?= python3
all: build extension ## Build everything

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- Python app ----

build: ## Build Python wheel
	$(PYTHON) -m venv /tmp/rss-is-terminal-build
	/tmp/rss-is-terminal-build/bin/pip install build
	/tmp/rss-is-terminal-build/bin/python -m build
	rm -rf /tmp/rss-is-terminal-build

install: build ## Install system-wide (may need sudo)
	sudo $(PYTHON) -m pip install dist/rss_is_terminal-*.whl

install-user: build ## Install for current user
	pipx install dist/rss_is_terminal-*.whl || $(PYTHON) -m pip install --user dist/rss_is_terminal-*.whl

install-pipx: build ## Install isolated with pipx
	pipx install dist/rss_is_terminal-*.whl

upgrade: build ## Upgrade existing pipx installation
	pipx install --force dist/rss_is_terminal-*.whl

install-js: build ## Install with Playwright (JS rendering) support
	pipx install "dist/rss_is_terminal-*.whl[js]"
	pipx runpip rss-is-terminal install playwright
	$(PYTHON) -m playwright install chromium || pipx run --spec rss-is-terminal playwright install chromium

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

test: ## Run tests (requires make dev first)
	.venv/bin/pytest

lint: ## Run linter (requires make dev first)
	.venv/bin/ruff check src/

run: ## Run the app (requires make dev first)
	.venv/bin/python -m rss_is_terminal.app

# ---- Cleanup ----

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
