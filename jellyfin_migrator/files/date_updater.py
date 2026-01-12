"""File date synchronization for Jellyfin database.

Updates DateCreated and DateModified in the database to match
actual file timestamps.
"""

import os
import sqlite3
from pathlib import Path
from typing import Dict

from tqdm import tqdm

from jellyfin_migrator.path.replacer import recursive_path_replace
from jellyfin_migrator.utils.datetime_utils import jellyfin_date_to_ns, ns_to_jellyfin_date
from jellyfin_migrator.utils.logging import get_logger


def update_file_dates(
    db_path: Path,
    target_root: Path,
    fs_path_replacements: Dict[str, str],
    table: str = "BaseItems",
    show_progress: bool = True,
) -> int:
    """Update file dates in database to match filesystem.

    Args:
        db_path: Path to jellyfin.db
        target_root: Root directory for migrated files
        fs_path_replacements: Filesystem path mappings
        table: Table name containing file entries
        show_progress: Whether to show progress bar

    Returns:
        Number of entries updated
    """
    logger = get_logger()
    logger.info("Updating file dates...")

    updated = 0

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    try:
        query = f"SELECT `rowid`, `Path`, `DateCreated`, `DateModified` FROM `{table}`"
        rows = list(cur.execute(query))

        iterator = tqdm(rows, desc="Updating dates", disable=not show_progress)

        for rowid, path, date_created, date_modified in iterator:
            if not path:
                continue

            # Resolve to filesystem path
            result = recursive_path_replace(
                path, fs_path_replacements, log_warnings=False
            )
            fs_path = Path(result.value)

            if not fs_path.is_absolute():
                if fs_path.is_relative_to("/"):
                    fs_path = fs_path.relative_to("/")
                fs_path = target_root / fs_path

            if not fs_path.exists():
                continue

            # Parse current dates
            try:
                created_ns = jellyfin_date_to_ns(date_created)
                modified_ns = jellyfin_date_to_ns(date_modified)
            except (ValueError, AttributeError):
                continue

            # Only update if dates are invalid (negative = before epoch)
            if created_ns >= 0 and modified_ns >= 0:
                continue

            # Get actual file dates
            try:
                stats = os.stat(fs_path)
            except OSError:
                continue

            needs_update = False

            if created_ns < 0:
                new_created = ns_to_jellyfin_date(stats.st_ctime_ns)
                cur.execute(
                    f"UPDATE `{table}` SET `DateCreated` = ? WHERE `rowid` = ?",
                    (new_created, rowid)
                )
                needs_update = True

            if modified_ns < 0:
                new_modified = ns_to_jellyfin_date(stats.st_mtime_ns)
                cur.execute(
                    f"UPDATE `{table}` SET `DateModified` = ? WHERE `rowid` = ?",
                    (new_modified, rowid)
                )
                needs_update = True

            if needs_update:
                updated += 1

        con.commit()

    finally:
        con.close()

    logger.info(f"Updated {updated} file dates")
    return updated
