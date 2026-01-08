"""Mblink file parsing for Jellyfin migration.

.mblink files contain a single path pointing to the linked item.
"""

from pathlib import Path
from typing import Callable, Dict

from jellyfin_migrator.path.replacer import ReplacementResult
from jellyfin_migrator.utils.logging import get_logger


def update_mblink_file(
    file_path: Path,
    replacements: Dict[str, str],
    replace_func: Callable,
) -> ReplacementResult:
    """Update the path in an .mblink file.

    .mblink files contain only a path, nothing else.

    Args:
        file_path: Path to the .mblink file
        replacements: Path replacement mappings
        replace_func: Function to apply replacements

    Returns:
        ReplacementResult with statistics
    """
    logger = get_logger()

    with open(file_path, "r", encoding="utf-8") as f:
        path = f.read()

    result = replace_func(path, replacements)

    logger.debug(f"Modified {result.modified_count} paths")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(result.value)

    return result


def read_mblink(file_path: Path) -> str:
    """Read the path from an .mblink file.

    Args:
        file_path: Path to the .mblink file

    Returns:
        The path contained in the file
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()
