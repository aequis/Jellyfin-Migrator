"""Path replacement functions for Jellyfin database migration.

This module handles recursive replacement of paths in various data structures
(dicts, lists, strings) and ID-based path renaming.
"""

import pathlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple, Union

from jellyfin_migrator.utils.logging import get_logger


@dataclass
class ReplacementResult:
    """Result of a path replacement operation."""
    value: Any
    modified_count: int
    ignored_count: int


def recursive_path_replace(
    data: Any,
    replacements: Dict[str, str],
    log_warnings: bool = True,
) -> ReplacementResult:
    """Recursively replace all paths in a data structure.

    Handles:
    - Path objects
    - Path strings
    - Dictionaries (values only, not keys)
    - Lists
    - Nested structures of the above

    Args:
        data: Data structure to process (dict, list, str, Path, or other)
        replacements: Dict mapping source paths to target paths.
                     Must include "target_path_slash" key.
        log_warnings: Whether to log warnings for unmapped paths

    Returns:
        ReplacementResult with modified data and counts
    """
    logger = get_logger()
    modified, ignored = 0, 0

    if isinstance(data, dict):
        for key, value in data.items():
            result = recursive_path_replace(value, replacements, log_warnings)
            data[key] = result.value
            modified += result.modified_count
            ignored += result.ignored_count

    elif isinstance(data, list):
        for i, element in enumerate(data):
            result = recursive_path_replace(element, replacements, log_warnings)
            data[i] = result.value
            modified += result.modified_count
            ignored += result.ignored_count

    elif isinstance(data, str) or isinstance(data, pathlib.PurePath):
        try:
            path = Path(data)
        except Exception:
            ignored += 1
        else:
            found = False
            target_slash = replacements.get("target_path_slash", "/")

            for src, dst in replacements.items():
                if src in ("target_path_slash", "log_no_warnings"):
                    continue
                try:
                    src_path = Path(src)
                    if path.is_relative_to(src_path):
                        dst_path = Path(dst)
                        new_path = dst_path / path.relative_to(src_path)
                        # Convert to string with correct slashes
                        data = new_path.as_posix().replace("/", target_slash)
                        found = True
                        break
                except (TypeError, ValueError):
                    continue

            if found:
                modified += 1
            else:
                ignored += 1
                # Log warning for potential unmapped paths
                # Filter out obvious non-paths
                no_warnings = replacements.get("log_no_warnings", False)
                if log_warnings and not no_warnings:
                    if (len(path.parents) > 1
                            and not str(data).startswith("https:")
                            and not str(data).startswith("http:")):
                        logger.warning(f"No entry for this (presumed) path: {data}")

    return ReplacementResult(value=data, modified_count=modified, ignored_count=ignored)


def recursive_id_path_replace(
    data: Any,
    id_replacements: Dict[str, str],
) -> ReplacementResult:
    """Recursively replace ID portions within file paths.

    ID paths have format: '.../83/833addde992893e93d0572907f8b4cad/...'
    The parent folder with first byte(s) of the ID is also updated.

    Args:
        data: Data structure to process
        id_replacements: Dict mapping old IDs to new IDs.
                        Must include "target_path_slash" key.

    Returns:
        ReplacementResult with modified data and counts
    """
    modified, ignored = 0, 0

    if isinstance(data, dict):
        for key, value in data.items():
            result = recursive_id_path_replace(value, id_replacements)
            data[key] = result.value
            modified += result.modified_count
            ignored += result.ignored_count

    elif isinstance(data, list):
        for i, element in enumerate(data):
            result = recursive_id_path_replace(element, id_replacements)
            data[i] = result.value
            modified += result.modified_count
            ignored += result.ignored_count

    elif isinstance(data, str) or isinstance(data, pathlib.PurePath):
        try:
            path = Path(data)
        except Exception:
            ignored += 1
        else:
            found = False
            target_slash = id_replacements.get("target_path_slash", "/")

            # Check if the filename (stem) is an ID
            if _is_potential_id(path.stem):
                new_id = id_replacements.get(path.stem, "")
                if new_id:
                    found = True
                    path = path.with_stem(new_id)

            # Check path parts for IDs
            if not found:
                for part in path.parts[:-1]:
                    if _is_potential_id(part):
                        new_id = id_replacements.get(part, "")
                        if new_id:
                            found = True
                            path = _replace_id_in_path(path, part, new_id)
                            break

            if found:
                modified += 1
                data = path.as_posix().replace("/", target_slash)
            else:
                ignored += 1

    return ReplacementResult(value=data, modified_count=modified, ignored_count=ignored)


def _is_potential_id(s: str) -> bool:
    """Check if a string could be a Jellyfin ID."""
    return set(s).issubset(set("0123456789abcdef-"))


def _replace_id_in_path(path: Path, old_id: str, new_id: str) -> Path:
    """Replace an ID within a path, including parent folder prefix.

    Args:
        path: Original path
        old_id: ID to replace
        new_id: New ID value

    Returns:
        Path with ID replaced
    """
    # Navigate to the part containing the ID
    working = path
    relative_parts = []

    while working.name != old_id:
        relative_parts.insert(0, working.name)
        working = working.parent

    # Replace the ID
    working = working.with_name(new_id)

    # Check if parent folder starts with bytes from the ID
    if old_id.startswith(working.parent.name):
        # Need to update parent folder too
        old_prefix_len = len(working.parent.name)
        new_prefix = new_id[:old_prefix_len]
        working = working.parent.with_name(new_prefix) / working.name

    # Rebuild the path
    for part in relative_parts:
        working = working / part

    return working


def apply_replacements_to_path(
    path: Union[str, Path],
    replacements: Dict[str, str],
) -> str:
    """Apply path replacements to a single path.

    Convenience function for when you just need to transform one path.

    Args:
        path: Path to transform
        replacements: Replacement mapping

    Returns:
        Transformed path as string
    """
    result = recursive_path_replace(str(path), replacements, log_warnings=False)
    return result.value
