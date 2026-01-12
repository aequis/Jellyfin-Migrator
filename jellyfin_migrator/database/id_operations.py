"""Database operations for Jellyfin ID updates.

Handles updating internal IDs in database tables after path migration.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

from jellyfin_migrator.config.schema import DatabaseIdTableConfig
from jellyfin_migrator.core.exceptions import DatabaseError, TableNotFoundError
from jellyfin_migrator.ids.converter import IdReplacements
from jellyfin_migrator.utils.logging import get_logger


@dataclass
class IdUpdateResult:
    """Result of updating IDs in a database."""
    ids_updated: int
    duplicates_removed: int


def update_db_table_ids(
    db_path: Path,
    table: str,
    config: DatabaseIdTableConfig,
    id_replacements: IdReplacements,
    show_progress: bool = True,
) -> IdUpdateResult:
    """Update Jellyfin IDs in a database table.

    Args:
        db_path: Path to SQLite database
        table: Table name
        config: Column configuration for ID types
        id_replacements: ID replacement mappings
        show_progress: Whether to show progress bar

    Returns:
        IdUpdateResult with statistics

    Raises:
        DatabaseError: On database errors
        TableNotFoundError: If table doesn't exist
    """
    logger = get_logger()
    updated_count = 0
    duplicates_removed = 0

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

        # Get ID type to replacement mapping
        id_type_map = {
            "str": id_replacements.str,
            "str-dash": id_replacements.str_dash,
            "ancestor-str": id_replacements.ancestor_str,
            "ancestor-str-dash": id_replacements.ancestor_str_dash,
            "bin": id_replacements.bin,
        }

        # Process each ID type
        config_dict = config.to_dict()

        for id_type, columns in config_dict.items():
            replacements = id_type_map.get(id_type, {})
            if not replacements or not columns:
                continue

            for column in columns:
                result = _update_column_ids(
                    cur, table, column, replacements, show_progress
                )
                updated_count += result[0]
                duplicates_removed += result[1]

        con.commit()

    finally:
        con.close()

    logger.info(f"Updated {updated_count} IDs, removed {duplicates_removed} duplicates")
    return IdUpdateResult(updated_count, duplicates_removed)


def _update_column_ids(
    cur: sqlite3.Cursor,
    table: str,
    column: str,
    replacements: Dict,
    show_progress: bool,
) -> tuple[int, int]:
    """Update IDs in a single column.

    Args:
        cur: Database cursor
        table: Table name
        column: Column name
        replacements: ID replacements for this type
        show_progress: Whether to show progress

    Returns:
        Tuple of (updated_count, duplicates_removed)
    """
    logger = get_logger()
    updated = 0
    duplicates = 0

    # Get distinct values in column
    rows = list(cur.execute(f"SELECT DISTINCT `{column}` FROM `{table}`"))

    desc = f"Updating {column} in {table}"
    iterator = tqdm(rows, desc=desc, disable=not show_progress)

    for (old_id,) in iterator:
        if old_id not in replacements:
            continue

        new_id = replacements[old_id]

        try:
            cur.execute(
                f"UPDATE `{table}` SET `{column}` = ? WHERE `{column}` = ?",
                (new_id, old_id)
            )
            updated += 1

        except sqlite3.IntegrityError:
            # Duplicate key - need to handle collision
            logger.warning(f"ID collision in {table}.{column}, removing duplicate")

            # Get affected rows for logging
            affected = list(cur.execute(
                f"SELECT * FROM `{table}` WHERE `{column}` = ?",
                (old_id,)
            ))
            for row in affected:
                logger.debug(f"Removing duplicate: {row}")

            # Delete the old entries
            cur.execute(f"DELETE FROM `{table}` WHERE `{column}` = ?", (old_id,))
            duplicates += len(affected)

    return updated, duplicates


def get_id_replacements_from_db(
    db_path: Path,
    path_column: str = "Path",
    type_column: str = "type",
    id_column: str = "Id",
    table: str = "BaseItems",
) -> Dict[bytes, bytes]:
    """Extract ID replacements from database based on path changes.

    Calculates new IDs based on item type and new path, then builds
    a mapping from old IDs to new IDs.

    Handles both binary (BLOB) and string (TEXT) ID storage formats.
    Jellyfin 10.11+ stores IDs as hex strings instead of binary blobs.

    Args:
        db_path: Path to jellyfin.db (after path migration)
        path_column: Column containing file paths
        type_column: Column containing item type
        id_column: Column containing current ID (binary or string)
        table: Table name

    Returns:
        Dict mapping old binary IDs to new binary IDs
    """
    from jellyfin_migrator.ids.converter import get_dotnet_md5, string_to_binary

    logger = get_logger()
    replacements = {}

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    try:
        query = f"SELECT `{id_column}`, `{type_column}`, `{path_column}` FROM `{table}`"
        rows = list(cur.execute(query))

        for guid, item_type, path in tqdm(rows, desc="Computing ID replacements"):
            if not path or path.startswith("%"):
                continue

            # Handle both binary and string ID formats
            # Jellyfin 10.11+ stores IDs as hex strings
            if isinstance(guid, str):
                # Convert hex string to binary for comparison
                guid_bin = string_to_binary(guid)
            else:
                guid_bin = guid

            # Calculate new ID based on type + path
            new_guid = get_dotnet_md5(item_type + path)

            # Only include if changed
            if new_guid != guid_bin:
                replacements[guid_bin] = new_guid

    finally:
        con.close()

    logger.info(f"Computed {len(replacements)} ID replacements")
    return replacements


def check_id_collisions(
    replacements: Dict[bytes, bytes],
) -> List[tuple[bytes, bytes]]:
    """Check for collisions in ID replacements.

    Multiple old IDs mapping to the same new ID indicates paths
    that are being merged (intentional) or a configuration error.

    Args:
        replacements: Dict mapping old IDs to new IDs

    Returns:
        List of (old_id, new_id) tuples that have collisions
    """
    seen = {}
    collisions = []

    for old_id, new_id in replacements.items():
        if new_id in seen:
            collisions.append((old_id, new_id))
            if seen[new_id] not in [c[0] for c in collisions]:
                collisions.append((seen[new_id], new_id))
        else:
            seen[new_id] = old_id

    return collisions
