"""File processing orchestration for Jellyfin migration."""

from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from jellyfin_migrator.config.schema import DatabaseTableConfig, TodoJob
from jellyfin_migrator.database.sqlite_handler import update_db_table
from jellyfin_migrator.files.copier import copy_file, move_file
from jellyfin_migrator.parsers.json_parser import update_json_file
from jellyfin_migrator.parsers.mblink_parser import update_mblink_file
from jellyfin_migrator.parsers.xml_parser import update_xml_file
from jellyfin_migrator.path.replacer import ReplacementResult, recursive_id_path_replace, recursive_path_replace
from jellyfin_migrator.path.resolver import resolve_target_path
from jellyfin_migrator.utils.logging import get_logger


def process_file(
    source: Path,
    target: Path,
    replacements: Dict[str, str],
    replace_func: Callable,
    tables: Optional[Dict[str, DatabaseTableConfig]] = None,
    copy_only: bool = False,
    no_log: bool = False,
) -> None:
    """Process a single file: copy and update paths.

    Args:
        source: Source file path
        target: Target file path
        replacements: Path replacement mappings
        replace_func: Function to apply replacements
        tables: Database table configurations (for .db files)
        copy_only: Only copy, don't process
        no_log: Suppress logging
    """
    logger = get_logger()

    if not target or target.is_dir():
        return

    if not no_log:
        logger.info(f"Processing {target}")

    if copy_only:
        return

    suffix = target.suffix.lower()

    if suffix == ".db":
        if tables:
            for table_name, table_config in tables.items():
                if not no_log:
                    logger.info(f"Processing table {table_name}")
                update_db_table(
                    db_path=target,
                    table=table_name,
                    config=table_config,
                    replace_func=replace_func,
                    replacements=replacements,
                    show_progress=not no_log,
                )

    elif suffix in (".xml", ".nfo"):
        result = update_xml_file(target, replacements, replace_func)
        if not no_log:
            logger.info(f"Modified {result.modified_count} paths")

    elif suffix == ".mblink":
        result = update_mblink_file(target, replacements, replace_func)
        if not no_log:
            logger.info(f"Modified {result.modified_count} paths")

    elif suffix == ".json":
        result = update_json_file(target, replacements, replace_func)
        if not no_log:
            logger.info(f"Modified {result.modified_count} paths")

    # For ID path replacement, also check if file path needs renaming
    if replace_func == recursive_id_path_replace:
        result = recursive_id_path_replace(str(target), replacements)
        if result.modified_count > 0:
            new_target = Path(result.value)
            if not no_log:
                logger.info(f"Renaming to {new_target}")
            move_file(target, new_target, no_log=True)


def process_jobs(
    jobs: List[TodoJob],
    source_root: Path,
    original_root: Path,
    target_root: Path,
    path_replacements: Dict[str, str],
    fs_path_replacements: Dict[str, str],
    replace_func: Callable = recursive_path_replace,
) -> Set[Path]:
    """Process a list of migration jobs.

    Handles wildcards and tracks processed files to avoid duplicates.

    Args:
        jobs: List of TodoJob specifications
        source_root: Root directory of source files
        original_root: Original Jellyfin installation path
        target_root: Root directory for migrated files
        path_replacements: Path replacement mappings
        fs_path_replacements: Filesystem path mappings
        replace_func: Function to apply replacements

    Returns:
        Set of processed source paths
    """
    logger = get_logger()
    processed: Set[Path] = set()

    for job in jobs:
        source = job.source
        logger.info(f"Processing job: {source}")

        if "*" in str(source):
            # Wildcard path - process all matching files
            try:
                relative = source.relative_to(source_root)
            except ValueError:
                relative = source

            for src in source_root.glob(str(relative)):
                if src.is_dir() or src in processed:
                    continue
                processed.add(src)

                target, skip_copy = resolve_target_path(
                    source=src,
                    target=job.target,
                    source_root=source_root,
                    original_root=original_root,
                    target_root=target_root,
                    path_replacements=path_replacements,
                    fs_path_replacements=fs_path_replacements,
                )

                if not skip_copy:
                    copy_file(src, target, no_log=job.no_log)

                process_file(
                    source=src,
                    target=target,
                    replacements=path_replacements,
                    replace_func=replace_func,
                    tables=job.tables,
                    copy_only=job.copy_only,
                    no_log=job.no_log,
                )
        else:
            # Single file path
            if source in processed:
                continue
            processed.add(source)

            target, skip_copy = resolve_target_path(
                source=source,
                target=job.target,
                source_root=source_root,
                original_root=original_root,
                target_root=target_root,
                path_replacements=path_replacements,
                fs_path_replacements=fs_path_replacements,
            )

            if not skip_copy:
                copy_file(source, target, no_log=job.no_log)

            process_file(
                source=source,
                target=target,
                replacements=path_replacements,
                replace_func=replace_func,
                tables=job.tables,
                copy_only=job.copy_only,
                no_log=job.no_log,
            )

    return processed
