"""ID generation utilities for Jellyfin migration.

Generates new IDs based on updated paths and item types.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

from tqdm import tqdm

from jellyfin_migrator.ids.converter import (
    IdReplacements,
    binary_to_string,
    get_dotnet_md5,
)
from jellyfin_migrator.utils.logging import get_logger


def generate_id_replacements(
    db_path: Path,
    table: str = "BaseItems",
    id_column: str = "Id",
    type_column: str = "type",
    path_column: str = "Path",
    show_progress: bool = True,
) -> IdReplacements:
    """Generate ID replacements based on updated paths in database.

    Jellyfin IDs are MD5(item_type + path) encoded as UTF-16-LE.
    After path migration, we need to recalculate IDs.

    Args:
        db_path: Path to jellyfin.db (after path migration)
        table: Table containing items
        id_column: Column with current binary IDs
        type_column: Column with item types
        path_column: Column with file paths
        show_progress: Whether to show progress bar

    Returns:
        IdReplacements with all format variants
    """
    logger = get_logger()
    replacements: Dict[bytes, bytes] = {}

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    try:
        query = f"SELECT `{id_column}`, `{type_column}`, `{path_column}` FROM `{table}`"
        rows = list(cur.execute(query))

        iterator = tqdm(rows, desc="Computing IDs", disable=not show_progress)

        for old_id, item_type, path in iterator:
            if not path or path.startswith("%"):
                continue

            # Calculate new ID
            new_id = get_dotnet_md5(item_type + path)

            # Only include if changed
            if new_id != old_id:
                replacements[old_id] = new_id

    finally:
        con.close()

    logger.info(f"Computed {len(replacements)} ID replacements")
    return IdReplacements.from_binary_replacements(replacements)


def check_id_collisions(
    replacements: IdReplacements,
    db_path: Path,
    table: str = "BaseItems",
    id_column: str = "Id",
    path_column: str = "Path",
) -> List[Tuple[str, str, str]]:
    """Check for ID collisions and return details.

    Multiple old IDs mapping to the same new ID indicates paths
    being merged (intentional) or configuration error.

    Args:
        replacements: ID replacement mappings
        db_path: Path to database for path lookup
        table: Table containing items
        id_column: Column with binary IDs
        path_column: Column with paths

    Returns:
        List of (new_id, old_path1, old_path2) collision tuples
    """
    logger = get_logger()

    # Find collisions in string format
    seen: Dict[str, str] = {}
    collision_ids: List[Tuple[str, str]] = []

    for old_id, new_id in replacements.str.items():
        if new_id in seen:
            collision_ids.append((old_id, new_id))
            if seen[new_id] not in [c[0] for c in collision_ids]:
                collision_ids.append((seen[new_id], new_id))
        else:
            seen[new_id] = old_id

    if not collision_ids:
        return []

    # Look up paths for collision IDs
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    collisions = []
    for old_id_str, new_id_str in collision_ids:
        old_id_bin = bytes.fromhex(old_id_str)
        row = cur.execute(
            f"SELECT `{path_column}` FROM `{table}` WHERE `{id_column}` = ?",
            (old_id_bin,)
        ).fetchone()
        path = row[0] if row else "unknown"
        collisions.append((new_id_str, old_id_str, path))

    con.close()

    logger.warning(f"Detected {len(collisions)} ID collisions")
    return collisions
