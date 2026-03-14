#!/usr/bin/env python3
"""Native messaging host for the RSS is Terminal browser extension.

Receives scraper configs from the extension and saves them to the
scrapers directory. Optionally adds the feed to the database.

No third-party dependencies — uses only the stdlib so it works with
the system Python without needing the project's virtualenv.
"""

import json
import os
import sqlite3
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path


def config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg) / "rss_is_terminal"


def data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return Path(xdg) / "rss_is_terminal"


def scrapers_dir() -> Path:
    path = config_dir() / "scrapers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "rss.db"


def read_message():
    """Read a native messaging message from stdin."""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length or len(raw_length) < 4:
        return None
    length = struct.unpack("=I", raw_length)[0]
    data = sys.stdin.buffer.read(length)
    return json.loads(data)


def send_message(msg):
    """Send a native messaging message to stdout."""
    encoded = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def save_config(config):
    """Save a scraper config to the scrapers directory."""
    name = (config.get("name") or "scraper").lower()
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    safe_name = safe_name.strip("_") or "scraper"

    dest = scrapers_dir() / f"{safe_name}.json"

    counter = 1
    while dest.exists():
        dest = scrapers_dir() / f"{safe_name}_{counter}.json"
        counter += 1

    dest.write_text(json.dumps(config, indent=2))
    return str(dest)


def try_add_to_db(config_path: str, config: dict, category_ids: list[int] | None = None) -> str | None:
    """Try to add the feed to the database using stdlib sqlite3.
    Returns error message or None on success."""
    db_file = db_path()
    if not db_file.exists():
        return "Database not found — open RSS is Terminal first, then retry"

    try:
        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA foreign_keys=ON")

        # Check if feed already exists
        row = conn.execute(
            "SELECT id FROM feeds WHERE url = ?", (config["url"],)
        ).fetchone()
        if row:
            return "Feed already exists in app"

        # Ensure columns exist (migration may not have run yet)
        try:
            conn.execute("ALTER TABLE feeds ADD COLUMN feed_type TEXT NOT NULL DEFAULT 'rss'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE feeds ADD COLUMN scraper_config_path TEXT")
        except Exception:
            pass

        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO feeds (url, title, feed_type, scraper_config_path, created_at)
               VALUES (?, ?, 'scraper', ?, ?)""",
            (config["url"], config.get("name", config["url"]), config_path, now),
        )
        feed_id = cur.lastrowid
        if category_ids:
            add_to_category(conn, feed_id, category_ids)
        conn.commit()
        conn.close()
        return None
    except Exception as e:
        return str(e)


def get_categories() -> list[dict]:
    """Return all categories from the database."""
    db_file = db_path()
    if not db_file.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_file))
        rows = conn.execute(
            "SELECT id, name FROM categories ORDER BY sort_order, name"
        ).fetchall()
        conn.close()
        return [{"id": r[0], "name": r[1]} for r in rows]
    except Exception:
        return []


def add_to_category(conn, feed_id: int, category_ids: list[int]) -> None:
    """Add feed to categories via the junction table."""
    # Ensure junction table exists
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS feed_categories (
                feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                PRIMARY KEY (feed_id, category_id)
            )"""
        )
    except Exception:
        pass
    for cat_id in category_ids:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO feed_categories (feed_id, category_id) VALUES (?, ?)",
                (feed_id, cat_id),
            )
        except Exception:
            pass


def try_add_rss_feed(url: str, title: str, category_ids: list[int] | None = None) -> dict:
    """Add a standard RSS/Atom feed to the database.
    Returns a response dict."""
    db_file = db_path()
    if not db_file.exists():
        return {"error": "Database not found — open RSS is Terminal first"}

    try:
        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA foreign_keys=ON")

        # Ensure columns exist
        for sql in [
            "ALTER TABLE feeds ADD COLUMN feed_type TEXT NOT NULL DEFAULT 'rss'",
            "ALTER TABLE feeds ADD COLUMN scraper_config_path TEXT",
        ]:
            try:
                conn.execute(sql)
            except Exception:
                pass

        # Check duplicate
        row = conn.execute(
            "SELECT id FROM feeds WHERE url = ?", (url,)
        ).fetchone()
        if row:
            return {"error": "Feed already exists"}

        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO feeds (url, title, feed_type, created_at)
               VALUES (?, ?, 'rss', ?)""",
            (url, title or url, now),
        )
        feed_id = cur.lastrowid
        if category_ids:
            add_to_category(conn, feed_id, category_ids)
        conn.commit()
        conn.close()
        return {"success": True, "message": "Feed added! Refresh RSS is Terminal to see it."}
    except Exception as e:
        return {"error": str(e)}


def main():
    msg = read_message()
    if not msg:
        send_message({"error": "No message received"})
        return

    action = msg.get("action")

    if action == "save":
        config = msg.get("config")
        if not config:
            send_message({"error": "No config provided"})
            return

        try:
            cat_ids = msg.get("category_ids") or None
            path = save_config(config)
            db_error = try_add_to_db(path, config, cat_ids)

            if db_error:
                send_message({
                    "success": True,
                    "path": path,
                    "db_added": False,
                    "db_note": db_error,
                })
            else:
                send_message({
                    "success": True,
                    "path": path,
                    "db_added": True,
                })
        except Exception as e:
            send_message({"error": str(e)})

    elif action == "add_feed":
        url = msg.get("url")
        title = msg.get("title", "")
        cat_ids = msg.get("category_ids") or None
        if not url:
            send_message({"error": "No URL provided"})
            return
        send_message(try_add_rss_feed(url, title, cat_ids))

    elif action == "get_categories":
        send_message({"categories": get_categories()})

    elif action == "ping":
        send_message({"pong": True, "scrapers_dir": str(scrapers_dir())})

    else:
        send_message({"error": f"Unknown action: {action}"})


if __name__ == "__main__":
    main()
