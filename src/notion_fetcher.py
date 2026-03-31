"""
Notion API interactions:
- Query the database for unsynced "read later" pages
- Fetch all block content for a page
- Mark a page as "Sent to Kindle"
"""

import logging
from typing import Any

from notion_client import Client

logger = logging.getLogger(__name__)


def get_unsynced_pages(client: Client, database_id: str) -> list[dict[str, Any]]:
    """
    Query the Notion database for pages that:
      - have the Category / Tag property equal to 'read later'
      - have the 'Sent to Kindle' checkbox set to False (or unchecked)

    Returns a list of simplified page dicts with id, title, and url.
    """
    results = []
    start_cursor = None

    while True:
        query_params: dict[str, Any] = {
            "database_id": database_id,
            "filter": {
                "and": [
                    {
                        "property": "Sent to Kindle",
                        "checkbox": {"equals": False},
                    },
                    # Notion multi-select / select filter for the category tag.
                    # Adjust the property name and type below if yours differs.
                    # Common options: "select" or "multi_select"
                    {
                        "property": "Category",
                        "select": {"equals": "read later"},
                    },
                ]
            },
            "page_size": 100,
        }
        if start_cursor:
            query_params["start_cursor"] = start_cursor

        response = client.databases.query(**query_params)

        for page in response.get("results", []):
            title = _extract_title(page)
            results.append(
                {
                    "id": page["id"],
                    "title": title or "Untitled",
                    "url": page.get("url", ""),
                    "created_time": page.get("created_time", ""),
                }
            )

        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")

    logger.info("Found %d unsynced pages", len(results))
    return results


def get_page_blocks(client: Client, page_id: str) -> list[dict[str, Any]]:
    """
    Recursively fetch all blocks for a page, handling pagination.
    Returns a flat list of block dicts (children are inlined under
    a 'children' key for list items).
    """
    return _fetch_blocks(client, page_id)


def mark_page_sent(client: Client, page_id: str) -> None:
    """Set the 'Sent to Kindle' checkbox to True on the given page."""
    client.pages.update(
        page_id=page_id,
        properties={
            "Sent to Kindle": {"checkbox": True},
        },
    )
    logger.info("Marked page %s as sent", page_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_title(page: dict[str, Any]) -> str:
    """Pull the page title from its properties."""
    props = page.get("properties", {})
    # Notion stores the title in a property of type "title".
    for prop in props.values():
        if prop.get("type") == "title":
            rich_text = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_text)
    return ""


def _fetch_blocks(client: Client, block_id: str) -> list[dict[str, Any]]:
    """Fetch child blocks for a block/page, recursively expanding children."""
    blocks = []
    start_cursor = None

    while True:
        params: dict[str, Any] = {"block_id": block_id, "page_size": 100}
        if start_cursor:
            params["start_cursor"] = start_cursor

        response = client.blocks.children.list(**params)

        for block in response.get("results", []):
            block_type = block.get("type", "")
            # Fetch children for block types that support nesting
            if block.get("has_children") and block_type in (
                "bulleted_list_item",
                "numbered_list_item",
                "toggle",
                "quote",
                "callout",
                "synced_block",
                "column",
                "column_list",
            ):
                block["children"] = _fetch_blocks(client, block["id"])
            blocks.append(block)

        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")

    return blocks
