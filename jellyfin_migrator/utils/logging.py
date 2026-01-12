"""Logging setup for Jellyfin Migrator."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    log_file: Path,
    backup_count: int = 20,
    level: str = "INFO",
    console_level: Optional[str] = None,
) -> logging.Logger:
    """Configure logging with file rotation and console output.

    Args:
        log_file: Path to the log file
        backup_count: Number of backup log files to keep
        level: Logging level for file output
        console_level: Logging level for console output (defaults to INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("jellyfin_migrator")
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    logger.handlers.clear()

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB per file
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    file_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(
        getattr(logging, (console_level or "INFO").upper(), logging.INFO)
    )
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the jellyfin_migrator logger instance.

    Returns:
        The configured logger (or a default one if not yet configured)
    """
    return logging.getLogger("jellyfin_migrator")
