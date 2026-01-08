"""ID scanning utilities for Jellyfin databases.

Scans database files for occurrences of Jellyfin IDs in various formats.
Useful for analyzing plugin databases.
"""

import sqlite3
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Set, Tuple

from jellyfin_migrator.ids.converter import (
    binary_to_string,
    convert_ancestor_id,
    string_to_binary,
    string_to_dashed,
)


def load_ids_from_library(library_db: Path) -> Tuple[Dict[str, List[str]], Dict[str, List[bytes]]]:
    """Load all IDs from Jellyfin's library.db and generate format variants.

    Args:
        library_db: Path to library.db file

    Returns:
        Tuple of (string_ids, byte_ids) dicts, keyed by format type
    """
    con = sqlite3.connect(library_db)
    cur = con.cursor()

    # Try both old and new table names
    try:
        id_binary = [x[0] for x in cur.execute("SELECT `Id` FROM `BaseItems`")]
    except sqlite3.OperationalError:
        id_binary = [x[0] for x in cur.execute("SELECT `guid` FROM `TypedBaseItems`")]

    con.close()

    # Generate all format variants
    id_str = [binary_to_string(k) for k in id_binary]
    id_str_dash = [string_to_dashed(k) for k in id_str]
    id_ancestor_str = [convert_ancestor_id(k) for k in id_str]
    id_ancestor_bin = [string_to_binary(k) for k in id_ancestor_str]
    id_ancestor_str_dash = [string_to_dashed(k) for k in id_ancestor_str]

    string_ids = {
        "str": id_str,
        "str-dash": id_str_dash,
        "ancestor-str": id_ancestor_str,
        "ancestor-str-dash": id_ancestor_str_dash,
    }

    byte_ids = {
        "bin": id_binary,
        "ancestor-bin": id_ancestor_bin,
        "str": [s.encode("ascii") for s in id_str],
        "str-dash": [s.encode("ascii") for s in id_str_dash],
        "ancestor-str": [s.encode("ascii") for s in id_ancestor_str],
        "ancestor-str-dash": [s.encode("ascii") for s in id_ancestor_str_dash],
    }

    print(f"{len(id_binary)} IDs loaded from library.db")
    return string_ids, byte_ids


def load_db_tables_columns(db_path: Path) -> Dict[str, List[str]]:
    """Get all tables and their columns from a database.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dict mapping table names to column name lists
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Get table names, excluding indexes
    table_names = [
        x[0] for x in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not x[0].startswith("idx")
        and not x[0].startswith("sqlite_autoindex")
        and "index" not in x[0].lower()
    ]

    # Get columns for each table
    table_info = {
        name: [x[0] for x in cur.execute(f"SELECT name FROM PRAGMA_TABLE_INFO('{name}')")]
        for name in table_names
    }

    con.close()
    return table_info


def load_all_column_values(db_path: Path) -> List[Tuple[str, str, Set]]:
    """Load all values from all columns in a database.

    Args:
        db_path: Path to SQLite database

    Returns:
        List of (table, column, values_set) tuples
    """
    table_info = load_db_tables_columns(db_path)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    results = []
    for table, columns in table_info.items():
        for column in columns:
            values = {x[0] for x in cur.execute(f"SELECT `{column}` FROM `{table}`") if x[0]}
            if values:
                results.append((table, column, values))

    con.close()
    return results


def scan_for_ids(
    library_db: Path,
    scan_db: Path,
) -> List[Tuple[str, str, Set[str]]]:
    """Scan a database for occurrences of Jellyfin IDs.

    Args:
        library_db: Path to Jellyfin's library.db
        scan_db: Path to database to scan

    Returns:
        List of (table, column, id_types_found) tuples
    """
    print("Loading IDs from library.db")
    string_ids, byte_ids = load_ids_from_library(library_db)

    print("Loading database to scan")
    column_data = load_all_column_values(scan_db)
    total_values = sum(len(data[2]) for data in column_data)
    print(f"Loaded {total_values} values")

    print("Scanning... This may take a while.")
    results = []

    # Check binary IDs
    for table, column, values in column_data:
        if not values:
            continue

        sample = next(iter(values))
        if isinstance(sample, bytes):
            id_types = _check_binary_ids(values, byte_ids)
            if id_types:
                results.append((table, column, id_types))

    # Check string IDs
    for table, column, values in column_data:
        if not values:
            continue

        # Extract potential ID candidates from values
        candidates = set()
        for value in values:
            if isinstance(value, (str, bytes)):
                col_type, found = _get_id_candidates(value)
                for candidate in found:
                    candidates.add((col_type, candidate))

        if candidates:
            id_types = _check_string_ids(candidates, string_ids)
            if id_types:
                results.append((table, column, id_types))

    return results


def _check_binary_ids(values: Set, byte_ids: Dict[str, List[bytes]]) -> Set[str]:
    """Check for binary ID matches."""
    id_types = set()

    for id_type, id_list in byte_ids.items():
        if "bin" not in id_type:
            continue
        for id_val in id_list:
            if id_val in values:
                id_types.add(f"{id_type} (pure)")
                break

    return id_types


def _check_string_ids(
    candidates: Set[Tuple[str, str]],
    string_ids: Dict[str, List[str]],
) -> Set[str]:
    """Check for string ID matches."""
    id_types = set()

    for id_type, id_list in string_ids.items():
        for id_val in id_list:
            for col_type, candidate in candidates:
                if id_val == candidate or id_val in candidate:
                    id_types.add(f"{id_type} ({col_type})")
                    break
            else:
                continue
            break

    return id_types


def _get_id_candidates(value) -> Tuple[str, Set[str]]:
    """Extract potential ID strings from a value."""
    result = ""
    if isinstance(value, bytes):
        result = "".join(chr(c) if c in b"0123456789abcdef-" else " " for c in value)
    elif isinstance(value, str):
        result = "".join(c if c in "0123456789abcdef-" else " " for c in value)

    col_type = "pure" if result == str(value) else "embedded"

    candidates = {piece for piece in result.split() if len(piece) >= 32}
    return col_type, candidates


def format_results(results: List[Tuple[str, str, Set[str]]]) -> str:
    """Format scan results for display.

    Args:
        results: List of (table, column, id_types) tuples

    Returns:
        Formatted string for display
    """
    if not results:
        return "No IDs found."

    # Sort and format
    formatted = [[table, column, ", ".join(sorted(types))] for table, column, types in results]
    formatted.sort(key=lambda x: "".join(x))

    # Add header
    header = ["Table", "Column", "ID Type(s) found"]
    all_rows = [header] + formatted

    # Calculate column widths
    widths = [max(len(row[i]) for row in all_rows) for i in range(3)]

    # Format output
    lines = []
    for row in all_rows:
        line = "  ".join(row[i].ljust(widths[i]) for i in range(3))
        lines.append(line)

    return "\n".join(lines)
