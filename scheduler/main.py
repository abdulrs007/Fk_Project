"""Main entry point for the scheduler service."""
import asyncio
import sys
import signal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from utilities.logger import setup_logger
from scheduler.scheduler import CrawlerScheduler


# Global scheduler instance for signal handling
scheduler_instance = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    if scheduler_instance:
        scheduler_instance.stop()
    sys.exit(0)


async def main(run_now: bool = False):
    """
    Main function to run the scheduler.

    Args:
        run_now: If True, run job immediately instead of waiting for schedule
    """
    global scheduler_instance

    logger.info("Starting Crawler Scheduler Service")

    # Create scheduler
    scheduler_instance = CrawlerScheduler()

    if run_now:
        # Run immediately and exit
        logger.info("Running job immediately (--now mode)")
        await scheduler_instance.run_now()
        logger.info("Job completed, exiting...")
        return

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the scheduler
    scheduler_instance.start()

    # Get next run time
    next_run = scheduler_instance.get_next_run_time()
    logger.info(f"Next scheduled run: {next_run}")

    logger.info("Scheduler is running. Press Ctrl+C to exit.")

    # Keep the program running
    try:
        # Run forever
        while True:
            await asyncio.sleep(60)  # Check every minute

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        scheduler_instance.stop()


if __name__ == "__main__":
    # Check for flags
    run_now = "--now" in sys.argv or "-n" in sys.argv

    # Run the scheduler
    asyncio.run(main(run_now=run_now))