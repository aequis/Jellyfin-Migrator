"""Configuration dataclasses for Jellyfin Migrator."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class PathSlash(Enum):
    """Target path separator style."""
    UNIX = "/"
    WINDOWS = "\\"

    @classmethod
    def from_string(cls, s: str) -> "PathSlash":
        """Create from string value."""
        if s == "/":
            return cls.UNIX
        elif s == "\\":
            return cls.WINDOWS
        else:
            raise ValueError(f"Invalid path slash: {s}")


@dataclass
class PathMapping:
    """A single source -> target path mapping."""
    source: Path
    target: Path

    def __post_init__(self):
        if isinstance(self.source, str):
            self.source = Path(self.source)
        if isinstance(self.target, str):
            self.target = Path(self.target)


@dataclass
class SpecialPaths:
    """Jellyfin special path variables."""
    app_data_path: Optional[str] = None
    metadata_path: Optional[str] = None


@dataclass
class PathReplacementsConfig:
    """Configuration for path replacements as seen by Jellyfin."""
    target_slash: PathSlash
    mappings: List[PathMapping]
    special_paths: SpecialPaths = field(default_factory=SpecialPaths)

    def to_dict(self) -> Dict[str, str]:
        """Convert to the dictionary format used by the replacer functions."""
        result = {
            "target_path_slash": self.target_slash.value,
        }
        for mapping in self.mappings:
            result[str(mapping.source)] = str(mapping.target)
        if self.special_paths.app_data_path:
            result["%AppDataPath%"] = self.special_paths.app_data_path
        if self.special_paths.metadata_path:
            result["%MetadataPath%"] = self.special_paths.metadata_path
        return result


@dataclass
class FilesystemPathConfig:
    """Maps Jellyfin virtual paths to actual filesystem paths."""
    target_slash: PathSlash
    mappings: List[PathMapping]
    log_no_warnings: bool = False
    special_paths: SpecialPaths = field(default_factory=SpecialPaths)

    def to_dict(self) -> Dict[str, str]:
        """Convert to the dictionary format used by the replacer functions."""
        result = {
            "target_path_slash": self.target_slash.value,
            "log_no_warnings": self.log_no_warnings,
        }
        for mapping in self.mappings:
            result[str(mapping.source)] = str(mapping.target)
        if self.special_paths.app_data_path:
            result["%AppDataPath%"] = self.special_paths.app_data_path
        if self.special_paths.metadata_path:
            result["%MetadataPath%"] = self.special_paths.metadata_path
        return result


@dataclass
class RootPaths:
    """Root directory configuration."""
    original: Path  # Original Jellyfin installation path
    source: Path    # Where the script reads files from
    target: Path    # Where the script writes files to

    def __post_init__(self):
        if isinstance(self.original, str):
            self.original = Path(self.original)
        if isinstance(self.source, str):
            self.source = Path(self.source)
        if isinstance(self.target, str):
            self.target = Path(self.target)


@dataclass
class LoggingConfig:
    """Logging configuration."""
    file: Path
    backup_count: int = 20
    level: str = "INFO"

    def __post_init__(self):
        if isinstance(self.file, str):
            self.file = Path(self.file)


@dataclass
class DatabaseTableConfig:
    """Configuration for a database table's columns to process for paths."""
    path_columns: List[str] = field(default_factory=list)
    json_columns: List[str] = field(default_factory=list)
    jf_image_columns: List[str] = field(default_factory=list)


@dataclass
class DatabaseIdTableConfig:
    """Configuration for ID columns in a database table."""
    str_columns: List[str] = field(default_factory=list)
    str_dash_columns: List[str] = field(default_factory=list)
    ancestor_str_columns: List[str] = field(default_factory=list)
    ancestor_str_dash_columns: List[str] = field(default_factory=list)
    bin_columns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, List[str]]:
        """Convert to format expected by update_db_table_ids."""
        return {
            "str": self.str_columns,
            "str-dash": self.str_dash_columns,
            "ancestor-str": self.ancestor_str_columns,
            "ancestor-str-dash": self.ancestor_str_dash_columns,
            "bin": self.bin_columns,
        }


@dataclass
class TodoJob:
    """A single migration job specification for path processing."""
    source: Path
    target: str  # "auto", "auto-existing", or explicit path
    tables: Dict[str, DatabaseTableConfig] = field(default_factory=dict)
    copy_only: bool = False
    no_log: bool = False

    def __post_init__(self):
        if isinstance(self.source, str):
            self.source = Path(self.source)


@dataclass
class TodoIdPathJob:
    """A single migration job for ID path renaming."""
    source: Path
    target: str  # "auto-existing" typically
    tables: Dict[str, DatabaseTableConfig] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.source, str):
            self.source = Path(self.source)


@dataclass
class TodoIdJob:
    """A single ID migration job specification."""
    source: Path
    target: str
    tables: Dict[str, DatabaseIdTableConfig] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.source, str):
            self.source = Path(self.source)


@dataclass
class MigrationConfig:
    """Complete migration configuration."""
    logging: LoggingConfig
    roots: RootPaths
    path_replacements: PathReplacementsConfig
    fs_path_replacements: FilesystemPathConfig
    todo_list_paths: List[TodoJob]
    todo_list_id_paths: List[TodoIdPathJob]
    todo_list_ids: List[TodoIdJob]
