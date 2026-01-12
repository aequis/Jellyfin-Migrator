"""JSON file parsing for Jellyfin migration."""

import json
from pathlib import Path
from typing import Callable, Dict

from jellyfin_migrator.path.replacer import ReplacementResult
from jellyfin_migrator.utils.logging import get_logger


def update_json_file(
    file_path: Path,
    replacements: Dict[str, str],
    replace_func: Callable,
) -> ReplacementResult:
    """Update paths in a JSON file.

    Args:
        file_path: Path to the JSON file
        replacements: Path replacement mappings
        replace_func: Function to apply replacements

    Returns:
        ReplacementResult with statistics
    """
    logger = get_logger()

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = replace_func(data, replacements)

    logger.debug(f"Modified {result.modified_count} paths")

    with open(file_path, "w", encoding="utf-8") as f:
        # Use indent=2 to match Jellyfin's default formatting
        json.dump(result.value, f, indent=2)

    return result


def parse_json_paths(file_path: Path) -> list[str]:
    """Extract all potential paths from a JSON file.

    Useful for debugging and validation.

    Args:
        file_path: Path to the JSON file

    Returns:
        List of strings that look like paths
    """
    paths = []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    _extract_paths_recursive(data, paths)
    return paths


def _extract_paths_recursive(data, paths: list) -> None:
    """Recursively extract path-like strings from data."""
    if isinstance(data, dict):
        for value in data.values():
            _extract_paths_recursive(value, paths)
    elif isinstance(data, list):
        for item in data:
            _extract_paths_recursive(item, paths)
    elif isinstance(data, str):
        if ("/" in data or "\\" in data) and not data.startswith("http"):
            paths.append(data)
