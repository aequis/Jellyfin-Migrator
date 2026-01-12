"""Command-line interface for Jellyfin Migrator."""

import argparse
import sys
from pathlib import Path

from jellyfin_migrator.config.loader import load_config
from jellyfin_migrator.core.context import MigrationContext
from jellyfin_migrator.core.exceptions import ConfigError, JellyfinMigratorError
from jellyfin_migrator.core.migrator import run_migration
from jellyfin_migrator.core.state import MigrationState, reset_state_file
from jellyfin_migrator.utils.disk import check_disk_space
from jellyfin_migrator.utils.logging import setup_logging


DEFAULT_STATE_FILE = Path("migration_state.json")


def main(args: list[str] = None) -> int:
    """Main entry point for CLI.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 for success)
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not hasattr(parsed, "command") or parsed.command is None:
        parser.print_help()
        return 0

    try:
        if parsed.command == "migrate":
            return cmd_migrate(parsed)
        else:
            parser.print_help()
            return 0

    except JellyfinMigratorError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="jellyfin-migrator",
        description="Migrate Jellyfin database between systems",
    )

    subparsers = parser.add_subparsers(dest="command", title="Commands")

    # migrate command
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Run the migration process",
    )
    migrate_parser.add_argument(
        "--config", "-c",
        type=Path,
        required=True,
        help="Path to YAML configuration file",
    )
    migrate_parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset progress and start migration from beginning",
    )
    migrate_parser.add_argument(
        "--skip-disk-check",
        action="store_true",
        help="Skip the free space calculation",
    )
    migrate_parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help=f"Path to state file for resume (default: {DEFAULT_STATE_FILE})",
    )

    return parser


def cmd_migrate(args: argparse.Namespace) -> int:
    """Execute the migrate command.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    # Load configuration
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    # Setup logging
    logger = setup_logging(
        log_file=config.logging.file,
        backup_count=config.logging.backup_count,
        level=config.logging.level,
    )

    logger.info("")
    logger.info("Starting Jellyfin Database Migration")

    # Handle reset
    if args.reset:
        reset_state_file(args.state_file)

    # Load or create state
    state = MigrationState.load(args.state_file)

    # Create context
    ctx = MigrationContext(
        config=config,
        state=state,
        logger=logger,
    )

    # Verify source exists
    if not config.roots.source.exists():
        logger.error(f"Source root not found: {config.roots.source}")
        return 1

    # Disk space check
    if not args.skip_disk_check:
        required, available, sufficient = check_disk_space(
            source_root=config.roots.source,
            target_root=config.roots.target,
        )
        if not sufficient:
            response = input("Insufficient disk space. Continue anyway? [y/N] ")
            if response.lower() != "y":
                logger.info("Aborting.")
                return 1
    else:
        logger.info("Skipping disk space check as requested.")

    # Run migration
    run_migration(ctx, args.state_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
