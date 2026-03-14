"""OPML import/export for feed lists."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from ..models.database import Database
from .feed_service import FeedService


@dataclass
class ImportResult:
    added: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


async def import_opml(
    db: Database, feed_service: FeedService, file_path: Path
) -> ImportResult:
    """Import feeds from an OPML file."""
    result = ImportResult()
    tree = ET.parse(file_path)
    root = tree.getroot()
    body = root.find("body")
    if body is None:
        result.errors.append("Invalid OPML: no <body> element")
        return result

    async def process_outline(outline: ET.Element, category_id: int | None = None):
        xml_url = outline.get("xmlUrl")
        if xml_url:
            cat_ids = [category_id] if category_id is not None else None
            feed_id, error = await feed_service.add_feed(xml_url, cat_ids)
            if error:
                if "already exists" in error.lower():
                    result.skipped += 1
                else:
                    result.errors.append(f"{xml_url}: {error}")
            else:
                result.added += 1
                # Override title if provided in OPML
                title = outline.get("title") or outline.get("text")
                if title and feed_id > 0:
                    await db.update_feed(feed_id, title=title)
        else:
            # This is a category folder
            cat_name = outline.get("title") or outline.get("text") or "Imported"
            cat_id = category_id
            try:
                cat_id = await db.add_category(cat_name)
            except Exception:
                # Category may already exist
                cats = await db.get_categories()
                for c in cats:
                    if c["name"] == cat_name:
                        cat_id = c["id"]
                        break

            for child in outline:
                await process_outline(child, cat_id)

    for outline in body:
        await process_outline(outline)

    return result


async def export_opml(db: Database, file_path: Path) -> None:
    """Export all feeds to an OPML file."""
    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "RSS is Terminal - Feed Export"
    body = ET.SubElement(opml, "body")

    categories = await db.get_categories()
    feeds = await db.get_feeds()
    feed_cat_map = await db.get_all_feed_category_mappings()

    feed_by_id = {f["id"]: f for f in feeds}
    categorized_ids: set[int] = set()

    # Write categorized feeds (each feed under its first category for OPML compat)
    for cat in categories:
        cat_feeds = [
            feed_by_id[fid] for fid, cats in feed_cat_map.items()
            if cat["id"] in cats and fid in feed_by_id
        ]
        if not cat_feeds:
            continue
        cat_el = ET.SubElement(body, "outline", text=cat["name"], title=cat["name"])
        for feed in cat_feeds:
            categorized_ids.add(feed["id"])
            ET.SubElement(
                cat_el, "outline",
                type="rss",
                text=feed["title"],
                title=feed["title"],
                xmlUrl=feed["url"],
                htmlUrl=feed["site_url"] or "",
            )

    # Uncategorized feeds
    for feed in feeds:
        if feed["id"] not in categorized_ids:
            ET.SubElement(
                body, "outline",
                type="rss",
                text=feed["title"],
                title=feed["title"],
                xmlUrl=feed["url"],
                htmlUrl=feed["site_url"] or "",
            )

    tree = ET.ElementTree(opml)
    ET.indent(tree, space="  ")
    tree.write(file_path, encoding="unicode", xml_declaration=True)
