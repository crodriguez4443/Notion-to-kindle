"""
Notion API interactions using the REST API directly (no SDK dependency):
- Query the database for unsynced "read later" pages
- Fetch all block content for a page
- Mark a page as "Sent to Kindle"
"""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE = "https://api.notion.com/v1"
_HEADERS_TEMPLATE = {
    "Authorization": "",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _headers(token: str) -> dict:
    h = dict(_HEADERS_TEMPLATE)
    h["Authorization"] = f"Bearer {token}"
    return h


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_unsynced_pages(token: str, database_id: str) -> list[dict[str, Any]]:
    """
    Return pages that have Category == 'read later' AND Sent to Kindle == false.
    """
    results = []
    start_cursor = None

    while True:
        payload: dict[str, Any] = {
            "filter": {
                "and": [
                    {
                        "property": "sent to kindle",
                        "checkbox": {"equals": False},
                    },
                    {
                        "property": "Category",
                        "select": {"equals": "Read Later"},
                    },
                ]
            },
            "page_size": 100,
        }
        if start_cursor:
            payload["start_cursor"] = start_cursor

        resp = requests.post(
            f"{_BASE}/databases/{database_id}/query",
            headers=_headers(token),
            json=payload,
            timeout=30,
        )
        if not resp.ok:
            logger.error("Notion API error %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()

        for page in data.get("results", []):
            results.append(
                {
                    "id": page["id"],
                    "title": _extract_title(page),
                    "url": page.get("url", ""),
                    "created_time": page.get("created_time", ""),
                }
            )

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    logger.info("Found %d unsynced pages", len(results))
    return results


def get_page_blocks(token: str, page_id: str) -> list[dict[str, Any]]:
    """Recursively fetch all blocks for a page."""
    return _fetch_blocks(token, page_id)


def mark_page_sent(token: str, page_id: str) -> None:
    """Set 'Sent to Kindle' checkbox to True."""
    resp = requests.patch(
        f"{_BASE}/pages/{page_id}",
        headers=_headers(token),
        json={"properties": {"sent to kindle": {"checkbox": True}}},
        timeout=30,
    )
    resp.raise_for_status()
    logger.info("Marked page %s as sent", page_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_title(page: dict[str, Any]) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(
                rt.get("plain_text", "") for rt in prop.get("title", [])
            )
    return "Untitled"


def _fetch_blocks(token: str, block_id: str) -> list[dict[str, Any]]:
    blocks = []
    start_cursor = None

    while True:
        params: dict[str, Any] = {"page_size": 100}
        if start_cursor:
            params["start_cursor"] = start_cursor

        resp = requests.get(
            f"{_BASE}/blocks/{block_id}/children",
            headers=_headers(token),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        for block in data.get("results", []):
            if block.get("has_children") and block.get("type") in (
                "bulleted_list_item", "numbered_list_item", "toggle",
                "quote", "callout", "column", "column_list",
            ):
                block["children"] = _fetch_blocks(token, block["id"])
            blocks.append(block)

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return blocks
