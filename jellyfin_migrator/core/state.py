"""Migration state management for checkpoint/resume capability."""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Set

from jellyfin_migrator.utils.logging import get_logger


class MigrationStep(Enum):
    """Migration steps that can be checkpointed."""
    PATHS = "step_paths"
    ID_PATHS = "step_id_paths"
    DB_IDS = "step_db_ids"
    DATES = "step_dates"


@dataclass
class MigrationState:
    """Tracks migration progress for resume capability."""
    completed_steps: Set[MigrationStep] = field(default_factory=set)
    library_db_source_path: Optional[Path] = None
    library_db_target_path: Optional[Path] = None

    @classmethod
    def load(cls, path: Path) -> "MigrationState":
        """Load state from file.

        Args:
            path: Path to state file

        Returns:
            Loaded state, or empty state if file doesn't exist
        """
        logger = get_logger()

        if not path.exists():
            return cls()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            completed = set()
            for step_name in data.get("completed_steps", []):
                try:
                    completed.add(MigrationStep(step_name))
                except ValueError:
                    logger.warning(f"Unknown step in state file: {step_name}")

            state = cls(completed_steps=completed)

            if data.get("library_db_source_path"):
                state.library_db_source_path = Path(data["library_db_source_path"])
            if data.get("library_db_target_path"):
                state.library_db_target_path = Path(data["library_db_target_path"])

            return state

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load state file: {e}")
            return cls()

    def save(self, path: Path) -> None:
        """Persist state to file.

        Args:
            path: Path to state file
        """
        data = {
            "completed_steps": [s.value for s in self.completed_steps],
            "library_db_source_path": str(self.library_db_source_path) if self.library_db_source_path else None,
            "library_db_target_path": str(self.library_db_target_path) if self.library_db_target_path else None,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def mark_complete(self, step: MigrationStep) -> None:
        """Mark a step as completed.

        Args:
            step: The step to mark complete
        """
        self.completed_steps.add(step)

    def is_complete(self, step: MigrationStep) -> bool:
        """Check if a step has been completed.

        Args:
            step: The step to check

        Returns:
            True if step is complete
        """
        return step in self.completed_steps

    def reset(self) -> None:
        """Reset all progress."""
        self.completed_steps.clear()
        self.library_db_source_path = None
        self.library_db_target_path = None


def reset_state_file(path: Path) -> None:
    """Delete state file to reset progress.

    Args:
        path: Path to state file
    """
    logger = get_logger()

    if path.exists():
        path.unlink()
        logger.info("Progress reset. Migration will start from the beginning.")
