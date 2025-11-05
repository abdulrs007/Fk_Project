"""Report generation for daily change summaries."""
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

from utilities.config import settings
from utilities.database import db
from utilities.models import DailyReport, ChangeType


class ReportGenerator:
    """Generates daily reports in JSON and CSV formats."""

    def __init__(self):
        """Initialize report generator."""
        self.output_dir = Path(settings.report_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_daily_report(self, changes_summary: Dict[str, Any]) -> DailyReport:
        """
        Generate a daily report from change detection summary.

        Args:
            changes_summary: Summary dict from ChangeDetector

        Returns:
            DailyReport object
        """
        # Get recent changes details
        changes = await db.get_recent_changes(limit=1000)

        # Count by change type
        new_books = sum(1 for c in changes if c.get("change_type") == ChangeType.NEW_BOOK)
        price_changes = sum(1 for c in changes if c.get("change_type") == ChangeType.PRICE_CHANGE)
        availability_changes = sum(1 for c in changes if c.get("change_type") == ChangeType.AVAILABILITY_CHANGE)
        other_changes = sum(1 for c in changes if c.get("change_type") == ChangeType.CONTENT_CHANGE)

        # Get total book count
        total_books = await db.count_books()

        report = DailyReport(
            report_date=datetime.utcnow(),
            total_books=total_books,
            new_books=new_books,
            price_changes=price_changes,
            availability_changes=availability_changes,
            other_changes=other_changes,
            changes_details=changes[:50]  # Include top 50 changes
        )

        return report

    async def save_report_json(self, report: DailyReport, filename: str = None) -> str:
        """
        Save report as JSON file.

        Args:
            report: DailyReport object
            filename: Custom filename (optional)

        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"daily_report_{timestamp}.json"

        filepath = self.output_dir / filename

        report_dict = report.model_dump(mode='json')

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, default=str)

        logger.info(f"JSON report saved to: {filepath}")
        return str(filepath)

    async def save_report_csv(self, report: DailyReport, filename: str = None) -> str:
        """
        Save report as CSV file (changes details only).

        Args:
            report: DailyReport object
            filename: Custom filename (optional)

        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"daily_report_{timestamp}.csv"

        filepath = self.output_dir / filename

        if not report.changes_details:
            logger.warning("No changes to write to CSV")
            return str(filepath)

        # Extract field names from first change
        fieldnames = ["change_type", "book_id", "book_name", "change_timestamp", "description"]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()

            for change in report.changes_details:
                writer.writerow({
                    "change_type": change.get("change_type", ""),
                    "book_id": change.get("book_id", ""),
                    "book_name": change.get("book_name", ""),
                    "change_timestamp": change.get("change_timestamp", ""),
                    "description": change.get("description", ""),
                })

        logger.info(f"CSV report saved to: {filepath}")
        return str(filepath)

    async def generate_and_save_report(self, changes_summary: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate report and save in configured format(s).

        Args:
            changes_summary: Summary from change detection

        Returns:
            Dict with paths to saved files
        """
        report = await self.generate_daily_report(changes_summary)

        saved_files = {}

        # Save in configured format
        report_format = settings.report_format.lower()

        if report_format == "json" or report_format == "both":
            json_path = await self.save_report_json(report)
            saved_files["json"] = json_path

        if report_format == "csv" or report_format == "both":
            csv_path = await self.save_report_csv(report)
            saved_files["csv"] = csv_path

        # Always save JSON by default if format is not recognized
        if not saved_files:
            json_path = await self.save_report_json(report)
            saved_files["json"] = json_path

        return saved_files

    def get_latest_report(self) -> str:
        """
        Get path to the most recent report file.

        Returns:
            Path to latest report, or empty string if none found
        """
        json_files = list(self.output_dir.glob("daily_report_*.json"))

        if not json_files:
            return ""

        # Sort by modification time
        latest = max(json_files, key=lambda p: p.stat().st_mtime)
        return str(latest)