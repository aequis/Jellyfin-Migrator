"""Disk space utilities for Jellyfin Migrator."""

import shutil
from pathlib import Path
from typing import Tuple

from jellyfin_migrator.core.exceptions import InsufficientSpaceError
from jellyfin_migrator.utils.logging import get_logger


def get_tree_size(path: Path) -> int:
    """Calculate total size of all files in a directory tree.

    Args:
        path: Root directory to measure

    Returns:
        Total size in bytes
    """
    total_size = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total_size += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total_size


def check_disk_space(
    source_root: Path,
    target_root: Path,
    safety_margin: float = 0.10,
    min_buffer_bytes: int = 500 * 1024 * 1024,
    raise_on_insufficient: bool = False,
) -> Tuple[int, int, bool]:
    """Check if there's enough disk space for the migration.

    Args:
        source_root: Source directory path
        target_root: Target directory path
        safety_margin: Additional safety margin as fraction (default 10%)
        min_buffer_bytes: Minimum buffer size in bytes (default 500MB)
        raise_on_insufficient: If True, raise exception instead of returning False

    Returns:
        Tuple of (required_bytes, available_bytes, is_sufficient)

    Raises:
        InsufficientSpaceError: If raise_on_insufficient is True and space is insufficient
    """
    logger = get_logger()

    logger.info("Checking disk space requirements...")

    # Calculate source size
    logger.debug("Calculating source size...")
    source_size = get_tree_size(source_root)
    logger.info(f"Source size: {source_size / (1024**3):.2f} GB")

    # Calculate existing target size (for resumed migrations)
    target_size = 0
    if target_root.exists():
        logger.debug("Calculating existing target size (progress)...")
        target_size = get_tree_size(target_root)
        logger.info(f"Existing target size: {target_size / (1024**3):.2f} GB")

    # Estimate remaining data to copy
    remaining_size = max(0, source_size - target_size)

    # Add safety buffer
    safety_buffer = int(remaining_size * safety_margin) + min_buffer_bytes
    required_space = remaining_size + safety_buffer

    # Find existing path for disk usage check
    check_path = target_root
    while not check_path.exists():
        check_path = check_path.parent

    total, used, free = shutil.disk_usage(check_path)

    logger.info("-" * 48)
    logger.info(f"Est. Remaining Data to Copy: {remaining_size / (1024**3):.2f} GB")
    logger.info(f"Safety Buffer:               {safety_buffer / (1024**3):.2f} GB")
    logger.info(f"TOTAL Required Free Space:   {required_space / (1024**3):.2f} GB")
    logger.info(f"Actual Available Space:      {free / (1024**3):.2f} GB")
    logger.info("-" * 48)

    is_sufficient = free >= required_space

    if not is_sufficient:
        if raise_on_insufficient:
            raise InsufficientSpaceError(required=int(required_space), available=free)
        logger.warning("Insufficient disk space detected!")
    else:
        logger.info("Disk space check passed.")

    return int(required_space), free, is_sufficient
