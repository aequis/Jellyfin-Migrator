"""Migration context - encapsulates all mutable state during migration."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from jellyfin_migrator.config.schema import MigrationConfig
from jellyfin_migrator.core.state import MigrationState
from jellyfin_migrator.ids.converter import IdReplacements


@dataclass
class MigrationContext:
    """Encapsulates all mutable state needed during migration.

    This replaces global variables from the original script.
    Passed explicitly through the call chain.
    """
    config: MigrationConfig
    state: MigrationState
    logger: logging.Logger

    # Discovered during migration
    library_db_source_path: Optional[Path] = None
    library_db_target_path: Optional[Path] = None
    id_replacements: Optional[IdReplacements] = None

    # User preferences during this run
    warn_on_inplace: bool = True

    # Statistics
    files_processed: int = 0
    paths_modified: int = 0
    ids_updated: int = 0

    def set_library_db_paths(self, source: Path, target: Path) -> None:
        """Set the library database paths discovered during Step 1.

        Args:
            source: Source path to jellyfin.db
            target: Target path for jellyfin.db
        """
        self.library_db_source_path = source
        self.library_db_target_path = target
        self.state.library_db_source_path = source
        self.state.library_db_target_path = target

    def log(self, level: int, message: str, *args) -> None:
        """Log a message.

        Args:
            level: Logging level (e.g., logging.INFO)
            message: Message format string
            *args: Format arguments
        """
        self.logger.log(level, message, *args)

    def info(self, message: str, *args) -> None:
        """Log an info message."""
        self.logger.info(message, *args)

    def warning(self, message: str, *args) -> None:
        """Log a warning message."""
        self.logger.warning(message, *args)

    def error(self, message: str, *args) -> None:
        """Log an error message."""
        self.logger.error(message, *args)

    def debug(self, message: str, *args) -> None:
        """Log a debug message."""
        self.logger.debug(message, *args)
