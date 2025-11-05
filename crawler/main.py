"""Main entry point for running the web crawler."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from utilities.database import db
from utilities.logger import setup_logger
from crawler.scraper import BookScraper


async def main(resume: bool = False):
    """
    Main function to run the crawler.

    Args:
        resume: Whether to resume from last checkpoint
    """
    try:
        # Connect to database
        logger.info("Connecting to MongoDB...")
        await db.connect()

        # Create scraper
        scraper = BookScraper(max_concurrent_requests=10)

        # Run the crawl
        await scraper.scrape_all_books(resume=resume)

        # Print final stats
        stats = scraper.get_stats()
        logger.info("Crawl statistics:")
        logger.info(f"  Total books: {stats['total_books']}")
        logger.info(f"  Successful: {stats['successful']}")
        logger.info(f"  Failed: {stats['failed']}")

    except KeyboardInterrupt:
        logger.warning("Crawl interrupted by user. Progress has been saved.")
        logger.info("Run with --resume flag to continue from checkpoint.")

    except Exception as e:
        logger.error(f"Crawl failed with error: {e}")
        raise

    finally:
        # Disconnect from database
        await db.disconnect()


if __name__ == "__main__":
    # Check for resume flag
    resume = "--resume" in sys.argv or "-r" in sys.argv

    if resume:
        logger.info("Resume mode enabled - will continue from last checkpoint")

    # Run the crawler
    asyncio.run(main(resume=resume))