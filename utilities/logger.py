"""Logging configuration using loguru."""
import sys
from pathlib import Path
from loguru import logger

from utilities.config import settings


def setup_logger():
    """
    Configure loguru logger with file and console output.

    **Logging Levels:**
    - DEBUG: Detailed info for debugging
    - INFO: General info about program execution
    - WARNING: Something unexpected but not critical
    - ERROR: Error that needs attention
    - CRITICAL: Serious error, program may crash
    """
    # Remove default handler
    logger.remove()

    # Console handler - colorized output
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # File handler - rotating logs
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        settings.log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level,
        rotation="10 MB",  # Create new file when current reaches 10 MB
        retention="30 days",  # Keep logs for 30 days
        compression="zip",  # Compress old logs
        enqueue=True,  # Thread-safe logging
    )

    logger.info("Logger initialized")
    logger.info(f"Log level: {settings.log_level}")
    logger.info(f"Log file: {settings.log_file}")


# Initialize logger on import
setup_logger()