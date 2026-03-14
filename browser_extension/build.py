#!/usr/bin/env python3
"""Build browser extension packages for Firefox (.xpi) and Chrome (.zip)."""

import json
import shutil
import zipfile
from pathlib import Path

EXT_DIR = Path(__file__).parent
DIST_DIR = EXT_DIR.parent / "dist" / "extension"

# Files to include in the extension package
EXTENSION_FILES = [
    "background.js",
    "content.js",
    "icons/icon16.png",
    "icons/icon48.png",
    "icons/icon128.png",
]

BASE_MANIFEST = {
    "manifest_version": 3,
    "name": "RSS is Terminal - Scraper Config Builder",
    "version": "0.1.0",
    "description": "Point-and-click scraper config generator for RSS is Terminal",
    "permissions": ["activeTab", "scripting", "nativeMessaging"],
    "action": {
        "default_icon": {
            "16": "icons/icon16.png",
            "48": "icons/icon48.png",
            "128": "icons/icon128.png",
        }
    },
    "icons": {
        "16": "icons/icon16.png",
        "48": "icons/icon48.png",
        "128": "icons/icon128.png",
    },
}


def build_firefox():
    """Build Firefox .xpi package."""
    manifest = {
        **BASE_MANIFEST,
        "background": {"scripts": ["background.js"]},
        "browser_specific_settings": {
            "gecko": {
                "id": "rss-is-terminal-scraper@jonny",
                "strict_min_version": "109.0",
            }
        },
    }

    out_dir = DIST_DIR / "firefox"
    out_dir.mkdir(parents=True, exist_ok=True)

    xpi_path = DIST_DIR / "rss_is_terminal-firefox.xpi"
    with zipfile.ZipFile(xpi_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for f in EXTENSION_FILES:
            zf.write(EXT_DIR / f, f)

    print(f"Firefox: {xpi_path}")
    return xpi_path


def build_chrome():
    """Build Chrome .zip package."""
    manifest = {
        **BASE_MANIFEST,
        "background": {"service_worker": "background.js"},
    }

    zip_path = DIST_DIR / "rss_is_terminal-chrome.zip"
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for f in EXTENSION_FILES:
            zf.write(EXT_DIR / f, f)

    print(f"Chrome:  {zip_path}")
    return zip_path


if __name__ == "__main__":
    print("Building browser extensions...")
    build_firefox()
    build_chrome()
    print("Done.")
