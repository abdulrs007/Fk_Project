"""Scheduler for automated daily crawls and change detection."""
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from utilities.config import settings
from utilities.database import db
from scheduler.detector import ChangeDetector
from scheduler.reporter import ReportGenerator


class CrawlerScheduler:
    """
    Automated scheduler for daily crawls and change detection.

    Uses APScheduler to run tasks at specified times.
    """

    def __init__(self):
        """Initialize scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.detector = ChangeDetector()
        self.reporter = ReportGenerator()
        self.is_running = False

    async def scheduled_crawl_job(self):
        """
        Job that runs on schedule to crawl and detect changes.

        **What it does:**
        1. Connects to database
        2. Runs change detection (which includes crawling)
        3. Generates daily report
        4. Logs summary
        """
        logger.info("="*60)
        logger.info("Starting scheduled crawl job")
        logger.info(f"Timestamp: {datetime.utcnow()}")
        logger.info("="*60)

        try:
            # Connect to database
            await db.connect()

            # Run change detection
            changes_summary = await self.detector.detect_changes()

            # Generate and save report
            report_files = await self.reporter.generate_and_save_report(changes_summary)

            logger.info("Scheduled job completed successfully")
            logger.info(f"Reports saved: {report_files}")

            # Check for significant changes and alert
            if changes_summary.get("new_books", 0) > 0:
                await self._send_alert(
                    f"New books detected: {changes_summary['new_books']}",
                    changes_summary
                )

            if changes_summary.get("price_changes", 0) > 10:
                await self._send_alert(
                    f"Significant price changes: {changes_summary['price_changes']}",
                    changes_summary
                )

        except Exception as e:
            logger.error(f"Scheduled job failed: {e}")
            await self._send_alert(f"Scheduled crawl failed: {e}", {"error": str(e)})

        finally:
            await db.disconnect()

    async def _send_alert(self, subject: str, data: dict):
        """
        Send alert notification.

        **For now:** Just logs the alert
        **Future:** Can integrate with email, Slack, Discord, etc.

        Args:
            subject: Alert subject/title
            data: Alert data
        """
        logger.warning(f"ALERT: {subject}")
        logger.info(f"Alert data: {data}")

        # TODO: Implement email alerts if SMTP settings are configured
        if settings.smtp_host and settings.alert_email:
            logger.info(f"Would send email to {settings.alert_email}")
            # Email implementation here
        else:
            logger.debug("Email alerts not configured")

    def start(self):
        """
        Start the scheduler.

        **Schedule:**
        Runs daily at configured time (default: 2:00 AM)
        """
        if not settings.scheduler_enabled:
            logger.warning("Scheduler is disabled in configuration")
            return

        # Add the crawl job with cron trigger
        trigger = CronTrigger(
            hour=settings.scheduler_cron_hour,
            minute=settings.scheduler_cron_minute,
        )

        self.scheduler.add_job(
            self.scheduled_crawl_job,
            trigger=trigger,
            id="daily_crawl",
            name="Daily Book Crawl and Change Detection",
            replace_existing=True,
        )

        # Start the scheduler
        self.scheduler.start()
        self.is_running = True

        logger.info("="*60)
        logger.info("Scheduler started successfully")
        logger.info(f"Daily crawl scheduled at: {settings.scheduler_cron_hour:02d}:{settings.scheduler_cron_minute:02d}")
        logger.info("="*60)

    def stop(self):
        """Stop the scheduler."""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped")

    async def run_now(self):
        """
        Run the crawl job immediately (manual trigger).

        Useful for testing without waiting for scheduled time.
        """
        logger.info("Running crawl job manually...")
        await self.scheduled_crawl_job()

    def get_next_run_time(self) -> str:
        """Get the next scheduled run time."""
        job = self.scheduler.get_job("daily_crawl")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        return "Not scheduled"