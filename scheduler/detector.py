"""Change detection logic for monitoring book updates."""
from typing import List, Dict, Any, Tuple
from datetime import datetime
from loguru import logger

from utilities.database import db
from utilities.models import ChangeLog, ChangeType, Book
from crawler.parser import BookParser
import httpx


class ChangeDetector:
    """
    Detects changes in book data by comparing current scrape with stored data.

    Uses content hashing for efficient change detection.
    Properly implements the requirements:
    - Detects newly added books
    - Compares stored data with current site
    - Maintains change log with what was updated
    """

    def __init__(self):
        """Initialize change detector."""
        self.changes: List[ChangeLog] = []
        self.parser = BookParser()
        self.stats = {
            "new_books": 0,
            "price_changes": 0,
            "availability_changes": 0,
            "content_changes": 0,
            "unchanged": 0,
        }

    async def detect_changes(self) -> Dict[str, Any]:
        """
        Run a full crawl and detect changes.

        **Process:**
        1. Crawl current data from website
        2. For each book:
           - Check if it exists in DB
           - If new: log as new_book
           - If exists: compare content hash
           - If hash differs: detect specific changes
        3. Generate summary report

        Returns:
            Summary dict with change statistics
        """
        logger.info("Starting change detection...")
        start_time = datetime.utcnow()

        # Get initial book count
        initial_count = await db.count_books()
        logger.info(f"Initial book count: {initial_count}")

        # Crawl and compare books
        await self._crawl_and_compare()

        # Get final book count
        final_count = await db.count_books()

        # Log changes to changelog collection
        await self._log_changes()

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        summary = {
            "detection_time": start_time,
            "duration_seconds": duration,
            "initial_book_count": initial_count,
            "final_book_count": final_count,
            "new_books": self.stats["new_books"],
            "price_changes": self.stats["price_changes"],
            "availability_changes": self.stats["availability_changes"],
            "content_changes": self.stats["content_changes"],
            "unchanged": self.stats["unchanged"],
            "total_changes": len(self.changes),
        }

        logger.info("="*60)
        logger.info("Change Detection Summary:")
        logger.info(f"  Duration: {duration:.2f} seconds")
        logger.info(f"  New books: {self.stats['new_books']}")
        logger.info(f"  Price changes: {self.stats['price_changes']}")
        logger.info(f"  Availability changes: {self.stats['availability_changes']}")
        logger.info(f"  Content changes: {self.stats['content_changes']}")
        logger.info(f"  Unchanged: {self.stats['unchanged']}")
        logger.info(f"  Total changes logged: {len(self.changes)}")
        logger.info("="*60)

        return summary

    async def _crawl_and_compare(self):
        """
        Crawl the website and compare each book with stored data.

        This implements proper change detection:
        - Check if book exists in DB
        - Compare content hashes
        - Detect specific changes
        """
        base_url = "https://books.toscrape.com"
        current_page_url = f"{base_url}/catalogue/page-1.html"
        page_num = 1

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            while current_page_url:
                logger.info(f"Checking catalog page {page_num}: {current_page_url}")

                try:
                    # Fetch catalog page
                    response = await client.get(current_page_url)
                    response.raise_for_status()
                    html = response.text

                    # Extract book URLs
                    book_urls = self.parser.parse_book_list_page(html, current_page_url)
                    logger.info(f"Found {len(book_urls)} books on page {page_num}")

                    # Process each book
                    for book_url in book_urls:
                        await self._check_book(client, book_url)

                    # Get next page
                    current_page_url = self.parser.get_next_page_url(html, current_page_url)
                    page_num += 1

                    # Small delay to be polite
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"Error crawling page {page_num}: {e}")
                    break

    async def _check_book(self, client: httpx.AsyncClient, book_url: str):
        """
        Check a single book for changes.

        Args:
            client: HTTP client
            book_url: URL of book detail page
        """
        try:
            # Fetch book page
            response = await client.get(book_url, timeout=30.0)
            response.raise_for_status()
            html = response.text

            # Parse book data
            new_book = self.parser.parse_book_detail_page(html, book_url)
            if not new_book:
                logger.warning(f"Failed to parse book: {book_url}")
                return

            # Compute content hash
            new_book.content_hash = db.compute_content_hash(new_book)

            # Check if book exists in database
            old_book = await db.get_book_by_url(book_url)

            if not old_book:
                # NEW BOOK - doesn't exist in DB yet
                logger.info(f"New book detected: {new_book.name}")

                # Save to database
                book_id, _ = await db.upsert_book(new_book)

                # Log as new book
                change = ChangeLog(
                    book_id=book_id,
                    book_name=new_book.name,
                    change_type=ChangeType.NEW_BOOK,
                    new_value={
                        "name": new_book.name,
                        "price": new_book.price_incl_tax,
                        "category": new_book.category
                    },
                    description=f"New book added: {new_book.name}"
                )
                self.changes.append(change)
                self.stats["new_books"] += 1

            else:
                # EXISTING BOOK - check for changes
                if old_book.content_hash != new_book.content_hash:
                    # Something changed - detect what
                    logger.info(f"Changes detected for: {new_book.name}")

                    book_changes = await self.compare_books(old_book, new_book)
                    self.changes.extend(book_changes)

                    # Update stats
                    for change in book_changes:
                        if change.change_type == ChangeType.PRICE_CHANGE:
                            self.stats["price_changes"] += 1
                        elif change.change_type == ChangeType.AVAILABILITY_CHANGE:
                            self.stats["availability_changes"] += 1
                        elif change.change_type == ChangeType.CONTENT_CHANGE:
                            self.stats["content_changes"] += 1

                    # Update book in database
                    await db.upsert_book(new_book)

                else:
                    # No changes
                    logger.debug(f"No changes for: {new_book.name}")
                    self.stats["unchanged"] += 1

                    # Still update timestamp
                    new_book.crawl_timestamp = datetime.utcnow()
                    await db.upsert_book(new_book)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {book_url}: {e}")
        except Exception as e:
            logger.error(f"Error checking book {book_url}: {e}")

    async def compare_books(self, old_book: Book, new_book: Book) -> List[ChangeLog]:
        """
        Compare two versions of a book and detect specific changes.

        Args:
            old_book: Previous version from database
            new_book: Current version from website

        Returns:
            List of ChangeLog entries for each change detected
        """
        changes = []
        book_id = old_book.id or str(old_book.source_url)
        book_name = old_book.name

        # Detect price changes
        if old_book.price_incl_tax != new_book.price_incl_tax:
            change = ChangeLog(
                book_id=book_id,
                book_name=book_name,
                change_type=ChangeType.PRICE_CHANGE,
                old_value={"price_incl_tax": old_book.price_incl_tax},
                new_value={"price_incl_tax": new_book.price_incl_tax},
                description=f"Price changed from £{old_book.price_incl_tax:.2f} to £{new_book.price_incl_tax:.2f}"
            )
            changes.append(change)
            logger.info(f"Price change: '{book_name}' - {change.description}")

        # Detect availability changes
        if old_book.num_available != new_book.num_available:
            change = ChangeLog(
                book_id=book_id,
                book_name=book_name,
                change_type=ChangeType.AVAILABILITY_CHANGE,
                old_value={
                    "num_available": old_book.num_available,
                    "availability": old_book.availability
                },
                new_value={
                    "num_available": new_book.num_available,
                    "availability": new_book.availability
                },
                description=f"Availability changed from {old_book.num_available} to {new_book.num_available}"
            )
            changes.append(change)
            logger.info(f"Availability change: '{book_name}' - {change.description}")

        # Detect review count changes
        if old_book.num_reviews != new_book.num_reviews:
            change = ChangeLog(
                book_id=book_id,
                book_name=book_name,
                change_type=ChangeType.CONTENT_CHANGE,
                old_value={"num_reviews": old_book.num_reviews},
                new_value={"num_reviews": new_book.num_reviews},
                description=f"Reviews changed from {old_book.num_reviews} to {new_book.num_reviews}"
            )
            changes.append(change)
            logger.info(f"Review count change: '{book_name}' - {change.description}")

        # Detect other content changes (rating, description, etc.)
        if not changes and old_book.content_hash != new_book.content_hash:
            # Something changed but not price/availability/reviews
            change = ChangeLog(
                book_id=book_id,
                book_name=book_name,
                change_type=ChangeType.CONTENT_CHANGE,
                description=f"Content changed for '{book_name}' (rating or other field)"
            )
            changes.append(change)
            logger.info(f"Content change: '{book_name}'")

        return changes

    async def _log_changes(self):
        """Save all detected changes to the changelog collection."""
        if not self.changes:
            logger.info("No changes detected - database is up to date")
            return

        logger.info(f"Logging {len(self.changes)} changes to database...")

        for change in self.changes:
            await db.insert_change(change)

        logger.info(f"Successfully logged {len(self.changes)} changes")

    def get_changes(self) -> List[ChangeLog]:
        """Get all detected changes."""
        return self.changes.copy()


# Import asyncio for sleep
import asyncio