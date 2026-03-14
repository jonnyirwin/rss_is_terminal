#!/bin/bash
# Install the native messaging host for Firefox and/or Chrome.
# Run this once after installing the extension.
#
# Usage:
#   ./install.sh                          # auto-detect browsers
#   ./install.sh --chrome-id <ext-id>     # specify Chrome extension ID

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST_SCRIPT="$SCRIPT_DIR/rss_is_terminal_host.py"
APP_NAME="rss_is_terminal"

# Extension ID for Firefox (fixed, set in manifest.json)
FIREFOX_EXT_ID="rss-is-terminal-scraper@jonny"

# Chrome extension ID (passed as argument or prompted)
CHROME_EXT_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --chrome-id)
      CHROME_EXT_ID="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

chmod +x "$HOST_SCRIPT"

echo "Installing native messaging host for RSS is Terminal..."
echo "Host script: $HOST_SCRIPT"
echo ""

# ---- Firefox ----

FIREFOX_MANIFEST_DIR="$HOME/.mozilla/native-messaging-hosts"
mkdir -p "$FIREFOX_MANIFEST_DIR"

cat > "$FIREFOX_MANIFEST_DIR/$APP_NAME.json" << EOF
{
  "name": "$APP_NAME",
  "description": "Native messaging host for RSS is Terminal scraper config builder",
  "path": "$HOST_SCRIPT",
  "type": "stdio",
  "allowed_extensions": ["$FIREFOX_EXT_ID"]
}
EOF

echo "Firefox: installed to $FIREFOX_MANIFEST_DIR/$APP_NAME.json"

# ---- Chrome / Chromium / Brave ----

for CHROME_DIR in \
  "$HOME/.config/google-chrome/NativeMessagingHosts" \
  "$HOME/.config/chromium/NativeMessagingHosts" \
  "$HOME/.config/BraveSoftware/Brave-Browser/NativeMessagingHosts"; do

  if [ -d "$(dirname "$CHROME_DIR")" ]; then
    mkdir -p "$CHROME_DIR"

    if [ -n "$CHROME_EXT_ID" ]; then
      ORIGIN="chrome-extension://$CHROME_EXT_ID/"
    else
      ORIGIN="chrome-extension://UPDATE_THIS_WITH_YOUR_EXTENSION_ID/"
      echo ""
      echo "  To find your Chrome extension ID:"
      echo "    1. Go to chrome://extensions"
      echo "    2. Enable Developer Mode"
      echo "    3. Load the unpacked extension or install the .zip"
      echo "    4. Copy the extension ID"
      echo "    5. Re-run: $0 --chrome-id YOUR_ID"
      echo ""
    fi

    cat > "$CHROME_DIR/$APP_NAME.json" << EOF
{
  "name": "$APP_NAME",
  "description": "Native messaging host for RSS is Terminal scraper config builder",
  "path": "$HOST_SCRIPT",
  "type": "stdio",
  "allowed_origins": ["$ORIGIN"]
}
EOF
    echo "Chrome/Chromium: installed to $CHROME_DIR/$APP_NAME.json"
  fi
done

echo ""
echo "Done! Restart your browser to pick up the changes."
