"""SQLite database operations for Jellyfin migration.

Handles reading and updating paths in database tables.
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from tqdm import tqdm

from jellyfin_migrator.config.schema import DatabaseTableConfig
from jellyfin_migrator.core.exceptions import DatabaseError, TableNotFoundError
from jellyfin_migrator.path.replacer import ReplacementResult
from jellyfin_migrator.utils.logging import get_logger


@dataclass
class TableUpdateResult:
    """Result of updating a database table."""
    rows_processed: int
    paths_modified: int
    paths_ignored: int


def update_db_table(
    db_path: Path,
    table: str,
    config: DatabaseTableConfig,
    replace_func: Callable[[str, Dict], ReplacementResult],
    replacements: Dict[str, str],
    show_progress: bool = True,
) -> TableUpdateResult:
    """Update paths in a database table.

    Args:
        db_path: Path to SQLite database
        table: Table name
        config: Column configuration
        replace_func: Function to apply replacements
        replacements: Replacement mappings
        show_progress: Whether to show progress bar

    Returns:
        TableUpdateResult with statistics

    Raises:
        DatabaseError: On database errors
        TableNotFoundError: If table doesn't exist
    """
    logger = get_logger()
    modified_total, ignored_total = 0, 0

    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to open database {db_path}: {e}") from e

    try:
        # Verify table exists
        tables = [t[0] for t in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )]
        if table not in tables:
            raise TableNotFoundError(table, db_path)

        # Build column list
        path_columns = list(config.path_columns)
        json_columns = list(config.json_columns)
        jf_image_columns = list(config.jf_image_columns)

        json_stop = len(json_columns)
        path_stop = json_stop + len(path_columns)

        all_columns = json_columns + path_columns + jf_image_columns
        if not all_columns:
            return TableUpdateResult(0, 0, 0)

        columns_str = ", ".join([f"`{c}`" for c in all_columns])

        # Get all row IDs
        row_ids = [r for r in cur.execute(f"SELECT `rowid` FROM `{table}`") if r[0]]
        rows_count = len(row_ids)

        # Process rows
        iterator = tqdm(row_ids, desc=f"Processing {table}", disable=not show_progress)

        for (rowid,) in iterator:
            # Fetch row data
            rows = list(cur.execute(
                f"SELECT {columns_str} FROM `{table}` WHERE `rowid` = ?",
                (rowid,)
            ))

            if len(rows) != 1:
                logger.warning(f"Row {rowid} returned {len(rows)} results, skipping")
                continue

            row = list(rows[0])
            result = {}

            # Process JSON columns
            for i in range(json_stop):
                data = row[i]
                if data:
                    try:
                        parsed = json.loads(data)
                        replacement = replace_func(parsed, replacements)
                        modified_total += replacement.modified_count
                        ignored_total += replacement.ignored_count
                        result[json_columns[i]] = json.dumps(replacement.value)
                    except json.JSONDecodeError:
                        pass

            # Process path columns
            for i in range(json_stop, path_stop):
                data = row[i]
                if data:
                    replacement = replace_func(data, replacements)
                    modified_total += replacement.modified_count
                    ignored_total += replacement.ignored_count
                    result[path_columns[i - json_stop]] = replacement.value

            # Process Jellyfin image columns
            for i in range(path_stop, len(row)):
                data = row[i]
                if data:
                    processed = _process_jf_image_data(
                        data, replace_func, replacements
                    )
                    modified_total += processed[1]
                    ignored_total += processed[2]
                    result[jf_image_columns[i - path_stop]] = processed[0]

            # Update row if changes were made
            if result:
                keys = ", ".join([f"`{k}` = ?" for k in result.keys()])
                query = f"UPDATE `{table}` SET {keys} WHERE `rowid` = ?"
                args = tuple(result.values()) + (rowid,)

                try:
                    cur.execute(query, args)
                except sqlite3.Error as e:
                    logger.error(f"Failed to update row {rowid}: {e}")

        con.commit()

    finally:
        con.close()

    logger.info(f"Processed {rows_count} rows, {modified_total} paths modified")
    return TableUpdateResult(rows_count, modified_total, ignored_total)


def _process_jf_image_data(
    data: str,
    replace_func: Callable,
    replacements: Dict,
) -> Tuple[str, int, int]:
    """Process Jellyfin image metadata format.

    Format: path*last_modified*image_type*width*height*blur_hash
    Multiple entries separated by |

    Args:
        data: Raw image metadata string
        replace_func: Replacement function
        replacements: Replacement mappings

    Returns:
        Tuple of (processed_data, modified_count, ignored_count)
    """
    modified, ignored = 0, 0
    entries = data.split("|")

    for i, entry in enumerate(entries):
        if not entry:
            continue

        parts = entry.split("*")
        # First part is the path
        result = replace_func(parts[0], replacements)
        parts[0] = result.value
        modified += result.modified_count
        ignored += result.ignored_count
        entries[i] = "*".join(parts)

    return "|".join(entries), modified, ignored


def get_table_columns(db_path: Path, table: str) -> List[str]:
    """Get column names for a table.

    Args:
        db_path: Path to database
        table: Table name

    Returns:
        List of column names
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    try:
        columns = [x[0] for x in cur.execute(
            f"SELECT name FROM PRAGMA_TABLE_INFO('{table}')"
        )]
    finally:
        con.close()

    return columns


def get_all_tables(db_path: Path) -> List[str]:
    """Get all table names in a database.

    Args:
        db_path: Path to database

    Returns:
        List of table names
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    try:
        tables = [
            t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if not t[0].startswith("sqlite_")
        ]
    finally:
        con.close()

    return tables
