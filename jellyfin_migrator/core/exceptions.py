"""Custom exceptions for Jellyfin Migrator."""

from pathlib import Path
from typing import List, Tuple


class JellyfinMigratorError(Exception):
    """Base exception for all migrator errors."""
    pass


# Configuration Errors

class ConfigError(JellyfinMigratorError):
    """Configuration-related errors."""
    pass


class ConfigFileNotFoundError(ConfigError):
    """Configuration file does not exist."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Configuration file not found: {path}")


class ConfigValidationError(ConfigError):
    """Configuration validation failed."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Configuration validation failed: {'; '.join(errors)}")


# Path Errors

class PathError(JellyfinMigratorError):
    """Path-related errors."""
    pass


class SourceNotFoundError(PathError):
    """Source path does not exist."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Source path not found: {path}")


class PathMappingError(PathError):
    """No mapping found for a path."""

    def __init__(self, path: str, context: str = ""):
        self.path = path
        self.context = context
        msg = f"No mapping for path: {path}"
        if context:
            msg += f" ({context})"
        super().__init__(msg)


# Database Errors

class DatabaseError(JellyfinMigratorError):
    """Database operation errors."""
    pass


class TableNotFoundError(DatabaseError):
    """Table does not exist in database."""

    def __init__(self, table: str, database: Path):
        self.table = table
        self.database = database
        super().__init__(f"Table '{table}' not found in {database}")


class ColumnNotFoundError(DatabaseError):
    """Column does not exist in table."""

    def __init__(self, column: str, table: str, database: Path):
        self.column = column
        self.table = table
        self.database = database
        super().__init__(f"Column '{column}' not found in table '{table}' in {database}")


# ID Errors

class IdError(JellyfinMigratorError):
    """ID-related errors."""
    pass


class IdCollisionError(IdError):
    """Multiple paths resolve to the same ID."""

    def __init__(self, collisions: List[Tuple[str, str, str]]):
        """
        Args:
            collisions: List of (id, old_path, new_path) tuples
        """
        self.collisions = collisions
        super().__init__(f"Detected {len(collisions)} ID collisions")


# Disk Errors

class DiskError(JellyfinMigratorError):
    """Disk-related errors."""
    pass


class InsufficientSpaceError(DiskError):
    """Not enough disk space."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient disk space: {available / (1024**3):.2f}GB available, "
            f"{required / (1024**3):.2f}GB required"
        )
