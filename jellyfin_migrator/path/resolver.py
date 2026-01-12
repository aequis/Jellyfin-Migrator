"""Path resolution utilities for migration targets.

Handles resolving "auto" and "auto-existing" target paths,
as well as filesystem path mapping.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple

from jellyfin_migrator.path.replacer import recursive_path_replace
from jellyfin_migrator.utils.logging import get_logger


def resolve_target_path(
    source: Path,
    target: str,
    source_root: Path,
    original_root: Path,
    target_root: Path,
    path_replacements: Dict[str, str],
    fs_path_replacements: Dict[str, str],
) -> Tuple[Path, bool]:
    """Resolve the target path for a file.

    Args:
        source: Source file path
        target: Target specification ("auto", "auto-existing", or explicit path)
        source_root: Root directory of source files
        original_root: Original Jellyfin installation path
        target_root: Root directory for migrated files
        path_replacements: Path replacement mappings
        fs_path_replacements: Filesystem path mappings

    Returns:
        Tuple of (resolved_path, skip_copy) where skip_copy is True for "auto-existing"
    """
    logger = get_logger()
    skip_copy = False

    if target.startswith("auto"):
        if target == "auto-existing":
            skip_copy = True

        # Convert source to original path if needed
        try:
            original_source = original_root / source.relative_to(source_root)
        except ValueError:
            original_source = source

        # Apply path replacements
        result = recursive_path_replace(
            str(original_source), path_replacements, log_warnings=False
        )
        target_str = result.value

        # Apply filesystem path replacements
        result = recursive_path_replace(
            target_str, fs_path_replacements, log_warnings=False
        )
        target_str = result.value

        resolved = Path(target_str)

        # If not absolute, make relative to target_root
        if not resolved.is_absolute():
            # Handle paths starting with /
            if resolved.is_relative_to("/"):
                resolved = resolved.relative_to("/")
            resolved = target_root / resolved
    else:
        resolved = Path(target)

    return resolved, skip_copy


def resolve_fs_path(
    jellyfin_path: str,
    target_root: Path,
    fs_path_replacements: Dict[str, str],
) -> Path:
    """Resolve a Jellyfin virtual path to actual filesystem path.

    Used for accessing media files and updating file dates.

    Args:
        jellyfin_path: Path as seen by Jellyfin
        target_root: Root directory for migrated files
        fs_path_replacements: Filesystem path mappings

    Returns:
        Actual filesystem path
    """
    result = recursive_path_replace(
        jellyfin_path, fs_path_replacements, log_warnings=False
    )
    resolved = Path(result.value)

    if not resolved.is_absolute():
        if resolved.is_relative_to("/"):
            resolved = resolved.relative_to("/")
        resolved = target_root / resolved

    return resolved


def check_inplace_warning(
    source: Path,
    target: Path,
    warn_callback: Optional[callable] = None,
) -> bool:
    """Check if source and target are the same (in-place operation).

    Args:
        source: Source file path
        target: Target file path
        warn_callback: Optional callback for user confirmation.
                      Should return True to continue, False to skip.

    Returns:
        True if operation should proceed, False to skip this file
    """
    logger = get_logger()

    if source == target:
        logger.warning(f"Source and target are the same: {source}")
        if warn_callback:
            return warn_callback(source, target)
        return True

    return True
