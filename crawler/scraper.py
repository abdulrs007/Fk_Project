"""Async web scraper with retry logic and checkpoint support."""
import asyncio
from typing import Optional, List
from datetime import datetime
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from loguru import logger

from utilities.config import settings
from utilities.database import db
from utilities.models import CrawlStatus, CrawlCheckpoint
from crawler.parser import BookParser


class BookScraper:
    """
    Async web scraper for books.toscrape.com

    Features:
    - Async HTTP requests for speed
    - Retry logic with exponential backoff
    - Checkpoint support for resuming failed crawls
    - Concurrent request limiting
    """

    def __init__(self, max_concurrent_requests: int = 10):
        """
        Initialize scraper.

        Args:
            max_concurrent_requests: Max number of concurrent HTTP requests
        """
        self.base_url = settings.target_url
        self.parser = BookParser(base_url=self.base_url)
        self.max_concurrent_requests = max_concurrent_requests

        # Semaphore to limit concurrent requests
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Statistics
        self.stats = {
            "total_books": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    async def fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        """
        Fetch a page with retry logic.

        **Retry Logic:**
        - Attempts: 3 tries
        - Wait: Exponential backoff (2s, 4s, 8s)
        - Retries on: HTTP errors and timeouts

        Args:
            client: HTTP client
            url: URL to fetch

        Returns:
            HTML content

        Raises:
            httpx.HTTPError: If request fails after retries
        """
        async with self.semaphore:  # Limit concurrent requests
            logger.debug(f"Fetching: {url}")
            response = await client.get(url, timeout=settings.crawler_timeout)
            response.raise_for_status()
            return response.text

    async def scrape_book(self, client: httpx.AsyncClient, book_url: str) -> Optional[dict]:
        """
        Scrape a single book detail page.

        Args:
            client: HTTP client
            book_url: URL of book detail page

        Returns:
            Book data as dict, or None if scraping fails
        """
        try:
            # Fetch the page
            html = await self.fetch_page(client, book_url)

            # Parse the book data
            book = self.parser.parse_book_detail_page(html, book_url)

            if book:
                # Compute content hash for change detection
                book.content_hash = db.compute_content_hash(book)

                # Save to database
                book_id, is_new = await db.upsert_book(book)

                if is_new:
                    logger.info(f"New book added: {book.name}")
                else:
                    logger.debug(f"Updated book: {book.name}")

                self.stats["successful"] += 1
                return {"book_id": book_id, "name": book.name, "is_new": is_new}

            else:
                logger.warning(f"Failed to parse book: {book_url}")
                self.stats["failed"] += 1
                return None

        except Exception as e:
            logger.error(f"Error scraping book {book_url}: {e}")
            self.stats["failed"] += 1
            return None

    async def scrape_catalog_page(self, client: httpx.AsyncClient, page_url: str) -> tuple[List[str], Optional[str]]:
        """
        Scrape a catalog page to get book URLs and next page URL.

        Args:
            client: HTTP client
            page_url: URL of catalog page

        Returns:
            (list of book URLs, next page URL)
        """
        try:
            html = await self.fetch_page(client, page_url)

            # Extract book URLs
            book_urls = self.parser.parse_book_list_page(html, page_url)

            # Extract next page URL
            next_page_url = self.parser.get_next_page_url(html, page_url)

            return book_urls, next_page_url

        except Exception as e:
            logger.error(f"Error scraping catalog page {page_url}: {e}")
            return [], None

    async def scrape_all_books(self, start_url: Optional[str] = None, resume: bool = False):
        """
        Scrape all books from the site with pagination.

        Args:
            start_url: Starting URL (defaults to base_url)
            resume: Whether to resume from last checkpoint
        """
        self.stats["start_time"] = datetime.utcnow()
        logger.info("Starting book scraping...")

        # Determine starting point
        if resume:
            checkpoint = await db.get_checkpoint("main_crawl")
            if checkpoint:
                start_url = checkpoint.last_page_url
                logger.info(f"Resuming from checkpoint: {start_url}")
                logger.info(f"Previously crawled: {checkpoint.total_books_crawled} books")
                self.stats["total_books"] = checkpoint.total_books_crawled

        if not start_url:
            start_url = f"{self.base_url}/catalogue/page-1.html"

        # Create async HTTP client
        async with httpx.AsyncClient(follow_redirects=True) as client:
            current_page_url = start_url
            page_num = 1

            while current_page_url:
                logger.info(f"Scraping catalog page {page_num}: {current_page_url}")

                # Get all book URLs from this catalog page
                book_urls, next_page_url = await self.scrape_catalog_page(client, current_page_url)

                if not book_urls:
                    logger.warning(f"No books found on page {page_num}")
                    break

                logger.info(f"Found {len(book_urls)} books on page {page_num}")

                # Scrape all books from this page concurrently
                tasks = [self.scrape_book(client, book_url) for book_url in book_urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count results
                for result in results:
                    if result and not isinstance(result, Exception):
                        self.stats["total_books"] += 1

                # Save checkpoint after each page
                checkpoint = CrawlCheckpoint(
                    checkpoint_id="main_crawl",
                    last_page_url=current_page_url,
                    last_book_url=book_urls[-1] if book_urls else None,
                    total_books_crawled=self.stats["total_books"],
                    status=CrawlStatus.PARTIAL if next_page_url else CrawlStatus.SUCCESS
                )
                await db.save_checkpoint(checkpoint)

                logger.info(f"Page {page_num} completed. Total books: {self.stats['total_books']}")

                # Move to next page
                current_page_url = next_page_url
                page_num += 1

                # Small delay to be polite to the server
                await asyncio.sleep(0.5)

        # Mark crawl as complete
        checkpoint = CrawlCheckpoint(
            checkpoint_id="main_crawl",
            last_page_url=current_page_url or start_url,
            total_books_crawled=self.stats["total_books"],
            status=CrawlStatus.SUCCESS
        )
        await db.save_checkpoint(checkpoint)

        self.stats["end_time"] = datetime.utcnow()
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        logger.info("="*60)
        logger.info("Scraping completed!")
        logger.info(f"Total books crawled: {self.stats['total_books']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Rate: {self.stats['total_books']/duration:.2f} books/second")
        logger.info("="*60)

    def get_stats(self) -> dict:
        """Get scraping statistics."""
        return self.stats.copy()