"""YAML configuration loader for Jellyfin Migrator."""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from jellyfin_migrator.config.schema import (
    DatabaseIdTableConfig,
    DatabaseTableConfig,
    FilesystemPathConfig,
    LoggingConfig,
    MigrationConfig,
    PathMapping,
    PathReplacementsConfig,
    PathSlash,
    RootPaths,
    SpecialPaths,
    TodoIdJob,
    TodoIdPathJob,
    TodoJob,
)
from jellyfin_migrator.core.exceptions import ConfigFileNotFoundError, ConfigValidationError


def load_config(config_path: Path) -> MigrationConfig:
    """Load and parse a YAML configuration file.

    Args:
        config_path: Path to the YAML config file

    Returns:
        Parsed MigrationConfig object

    Raises:
        ConfigFileNotFoundError: If config file doesn't exist
        ConfigValidationError: If config is invalid
    """
    if not config_path.exists():
        raise ConfigFileNotFoundError(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    return _parse_config(raw_config, config_path.parent)


def _parse_config(raw: Dict[str, Any], base_path: Path) -> MigrationConfig:
    """Parse raw YAML dict into MigrationConfig."""
    errors: List[str] = []

    # Logging
    if "logging" not in raw:
        errors.append("Missing 'logging' section")
        logging_config = LoggingConfig(file=Path("migrator.log"))
    else:
        logging_config = _parse_logging(raw["logging"])

    # Roots
    if "roots" not in raw:
        errors.append("Missing 'roots' section")
        roots = RootPaths(original=Path("."), source=Path("."), target=Path("."))
    else:
        roots = _parse_roots(raw["roots"])

    # Path replacements
    if "path_replacements" not in raw:
        errors.append("Missing 'path_replacements' section")
        path_replacements = PathReplacementsConfig(
            target_slash=PathSlash.UNIX, mappings=[]
        )
    else:
        path_replacements = _parse_path_replacements(raw["path_replacements"])

    # Filesystem path replacements
    if "fs_path_replacements" not in raw:
        errors.append("Missing 'fs_path_replacements' section")
        fs_path_replacements = FilesystemPathConfig(
            target_slash=PathSlash.UNIX, mappings=[]
        )
    else:
        fs_path_replacements = _parse_fs_path_replacements(raw["fs_path_replacements"])

    # Todo lists
    todo_list_paths = _parse_todo_list_paths(
        raw.get("todo_list_paths", []), roots.source
    )
    todo_list_id_paths = _parse_todo_list_id_paths(
        raw.get("todo_list_id_paths", []), roots.source
    )
    todo_list_ids = _parse_todo_list_ids(raw.get("todo_list_ids", []), roots.source)

    if errors:
        raise ConfigValidationError(errors)

    return MigrationConfig(
        logging=logging_config,
        roots=roots,
        path_replacements=path_replacements,
        fs_path_replacements=fs_path_replacements,
        todo_list_paths=todo_list_paths,
        todo_list_id_paths=todo_list_id_paths,
        todo_list_ids=todo_list_ids,
    )


def _parse_logging(raw: Dict[str, Any]) -> LoggingConfig:
    """Parse logging section."""
    return LoggingConfig(
        file=Path(raw.get("file", "migrator.log")),
        backup_count=raw.get("backup_count", 20),
        level=raw.get("level", "INFO"),
    )


def _parse_roots(raw: Dict[str, Any]) -> RootPaths:
    """Parse roots section."""
    return RootPaths(
        original=Path(raw.get("original", ".")),
        source=Path(raw.get("source", ".")),
        target=Path(raw.get("target", ".")),
    )


def _parse_path_replacements(raw: Dict[str, Any]) -> PathReplacementsConfig:
    """Parse path_replacements section."""
    target_slash = PathSlash.from_string(raw.get("target_slash", "/"))

    mappings = []
    for mapping in raw.get("mappings", []):
        mappings.append(PathMapping(
            source=Path(mapping["source"]),
            target=Path(mapping["target"]),
        ))

    special = raw.get("special_paths", {})
    special_paths = SpecialPaths(
        app_data_path=special.get("AppDataPath"),
        metadata_path=special.get("MetadataPath"),
    )

    return PathReplacementsConfig(
        target_slash=target_slash,
        mappings=mappings,
        special_paths=special_paths,
    )


def _parse_fs_path_replacements(raw: Dict[str, Any]) -> FilesystemPathConfig:
    """Parse fs_path_replacements section."""
    target_slash = PathSlash.from_string(raw.get("target_slash", "/"))

    mappings = []
    for mapping in raw.get("mappings", []):
        mappings.append(PathMapping(
            source=Path(mapping["source"]),
            target=Path(mapping["target"]),
        ))

    special = raw.get("special_paths", {})
    special_paths = SpecialPaths(
        app_data_path=special.get("AppDataPath"),
        metadata_path=special.get("MetadataPath"),
    )

    return FilesystemPathConfig(
        target_slash=target_slash,
        mappings=mappings,
        log_no_warnings=raw.get("log_no_warnings", False),
        special_paths=special_paths,
    )


def _parse_table_config(raw: Dict[str, Any]) -> DatabaseTableConfig:
    """Parse table configuration for path processing."""
    return DatabaseTableConfig(
        path_columns=raw.get("path_columns", []),
        json_columns=raw.get("json_columns", []),
        jf_image_columns=raw.get("jf_image_columns", []),
    )


def _parse_id_table_config(raw: Dict[str, Any]) -> DatabaseIdTableConfig:
    """Parse table configuration for ID processing."""
    return DatabaseIdTableConfig(
        str_columns=raw.get("str", []),
        str_dash_columns=raw.get("str_dash", []),
        ancestor_str_columns=raw.get("ancestor_str", []),
        ancestor_str_dash_columns=raw.get("ancestor_str_dash", []),
        bin_columns=raw.get("bin", []),
    )


def _parse_todo_list_paths(
    raw_list: List[Dict[str, Any]], source_root: Path
) -> List[TodoJob]:
    """Parse todo_list_paths section."""
    jobs = []
    for raw in raw_list:
        source = raw.get("source", "")
        # If source is relative, make it relative to source_root
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = source_root / source_path

        tables = {}
        for table_name, table_config in raw.get("tables", {}).items():
            tables[table_name] = _parse_table_config(table_config)

        jobs.append(TodoJob(
            source=source_path,
            target=raw.get("target", "auto"),
            tables=tables,
            copy_only=raw.get("copy_only", False),
            no_log=raw.get("no_log", False),
        ))
    return jobs


def _parse_todo_list_id_paths(
    raw_list: List[Dict[str, Any]], source_root: Path
) -> List[TodoIdPathJob]:
    """Parse todo_list_id_paths section."""
    jobs = []
    for raw in raw_list:
        source = raw.get("source", "")
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = source_root / source_path

        tables = {}
        for table_name, table_config in raw.get("tables", {}).items():
            tables[table_name] = _parse_table_config(table_config)

        jobs.append(TodoIdPathJob(
            source=source_path,
            target=raw.get("target", "auto-existing"),
            tables=tables,
        ))
    return jobs


def _parse_todo_list_ids(
    raw_list: List[Dict[str, Any]], source_root: Path
) -> List[TodoIdJob]:
    """Parse todo_list_ids section."""
    jobs = []
    for raw in raw_list:
        source = raw.get("source", "")
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = source_root / source_path

        tables = {}
        for table_name, table_config in raw.get("tables", {}).items():
            tables[table_name] = _parse_id_table_config(table_config)

        jobs.append(TodoIdJob(
            source=source_path,
            target=raw.get("target", "auto-existing"),
            tables=tables,
        ))
    return jobs
