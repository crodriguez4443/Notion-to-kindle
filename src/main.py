"""
Notion-to-Kindle weekly sync — entrypoint.

Environment variables required (set in .env locally, or as GitHub Actions secrets):
  NOTION_TOKEN         - Notion integration token (secret_...)
  NOTION_DATABASE_ID   - The ID of the Notion database to sync
  GMAIL_USER           - Gmail address used to send emails
  GMAIL_APP_PASSWORD   - Google App Password (not your login password)
  KINDLE_EMAIL         - Your Kindle email address (name@kindle.com)
"""

import logging
import os
import sys
import tempfile

from epub_builder import build_epub
from kindle_sender import send_to_kindle
from notion_fetcher import get_page_blocks, get_unsynced_pages, mark_page_sent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        logger.error("Required environment variable '%s' is not set.", name)
        sys.exit(1)
    return value


def main() -> None:
    notion_token = _require_env("NOTION_TOKEN")
    database_id = _require_env("NOTION_DATABASE_ID")
    gmail_user = _require_env("GMAIL_USER")
    gmail_app_password = _require_env("GMAIL_APP_PASSWORD")
    kindle_email = _require_env("KINDLE_EMAIL")

    logger.info("Querying Notion database %s for unsynced pages…", database_id)
    pages = get_unsynced_pages(notion_token, database_id)

    if not pages:
        logger.info("No new articles to send. All caught up!")
        return

    logger.info("Found %d article(s) to send.", len(pages))

    failed: list[str] = []

    for page in pages:
        title = page["title"]
        page_id = page["id"]
        url = page["url"]

        logger.info("Processing: %s", title)

        try:
            blocks = get_page_blocks(notion_token, page_id)

            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
                epub_path = tmp.name

            try:
                build_epub(title, blocks, url, epub_path)
                send_to_kindle(
                    epub_path=epub_path,
                    title=title,
                    gmail_user=gmail_user,
                    gmail_app_password=gmail_app_password,
                    kindle_email=kindle_email,
                )
                mark_page_sent(notion_token, page_id)
                logger.info("Done: %s", title)
            finally:
                if os.path.exists(epub_path):
                    os.unlink(epub_path)

        except Exception:
            logger.exception("Failed to process '%s' — skipping.", title)
            failed.append(title)

    if failed:
        logger.error(
            "%d article(s) failed to send:\n  %s",
            len(failed),
            "\n  ".join(failed),
        )
        sys.exit(1)

    logger.info(
        "Sync complete. %d article(s) sent to Kindle.", len(pages) - len(failed)
    )


if __name__ == "__main__":
    main()
