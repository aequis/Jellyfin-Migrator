"""File copying utilities for Jellyfin migration."""

from pathlib import Path
from shutil import copy
from typing import Optional

from jellyfin_migrator.utils.logging import get_logger


def copy_file(
    source: Path,
    target: Path,
    no_log: bool = False,
    overwrite: bool = False,
) -> bool:
    """Copy a file from source to target.

    Creates parent directories if needed.

    Args:
        source: Source file path
        target: Target file path
        no_log: Suppress logging
        overwrite: Overwrite existing files

    Returns:
        True if file was copied, False if skipped
    """
    logger = get_logger()

    if not source.is_file():
        return False

    if target.exists() and not overwrite:
        return False

    # Create parent directories
    target.parent.mkdir(parents=True, exist_ok=True)

    if not no_log:
        logger.debug(f"Copying {source} -> {target}")

    copy(source, target)
    return True


def move_file(
    source: Path,
    target: Path,
    no_log: bool = False,
) -> bool:
    """Move a file from source to target.

    Creates parent directories if needed.

    Args:
        source: Source file path
        target: Target file path
        no_log: Suppress logging

    Returns:
        True if file was moved, False if skipped
    """
    logger = get_logger()

    if not source.is_file():
        return False

    if source == target:
        return False

    # Create parent directories
    target.parent.mkdir(parents=True, exist_ok=True)

    if not no_log:
        logger.debug(f"Moving {source} -> {target}")

    source.replace(target)
    return True


def delete_empty_folders(root: Path) -> int:
    """Recursively delete empty folders.

    Args:
        root: Root directory to clean

    Returns:
        Number of folders deleted
    """
    logger = get_logger()
    deleted = 0

    done = False
    while not done:
        done = True
        for path in root.glob("**"):
            if path.is_dir() and not list(path.iterdir()):
                logger.debug(f"Removing empty folder: {path}")
                path.rmdir()
                deleted += 1
                done = False

    return deleted
