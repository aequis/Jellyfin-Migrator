"""Main migration orchestration."""

from pathlib import Path
from typing import Optional

from jellyfin_migrator.config.schema import MigrationConfig
from jellyfin_migrator.core.context import MigrationContext
from jellyfin_migrator.core.state import MigrationState, MigrationStep
from jellyfin_migrator.database.id_operations import get_id_replacements_from_db, update_db_table_ids
from jellyfin_migrator.files.date_updater import update_file_dates
from jellyfin_migrator.files.processor import process_jobs
from jellyfin_migrator.ids.converter import IdReplacements
from jellyfin_migrator.path.replacer import recursive_id_path_replace, recursive_path_replace
from jellyfin_migrator.path.resolver import resolve_target_path
from jellyfin_migrator.utils.logging import get_logger


def run_migration(
    ctx: MigrationContext,
    state_file: Path,
) -> None:
    """Run the complete migration process.

    This is the main entry point for the migration.
    Handles all steps with checkpoint/resume support.

    Args:
        ctx: Migration context with config and state
        state_file: Path to save state for resume capability
    """
    logger = get_logger()
    config = ctx.config

    # Step 1: Copy files and update paths
    if ctx.state.is_complete(MigrationStep.PATHS):
        logger.info("Step 1 (Path Migration) already completed. Skipping.")
        _restore_db_paths(ctx)
    else:
        logger.info(">>> Executing Step 1: Copying files and updating paths...")
        _run_step_paths(ctx)
        ctx.state.mark_complete(MigrationStep.PATHS)
        ctx.state.save(state_file)
        logger.info("Step 1 Complete.")

    # Calculate ID replacements (needed for subsequent steps)
    logger.info(">>> Loading/Calculating IDs...")
    _calculate_id_replacements(ctx)

    # Step 3: Rename files/folders based on new IDs
    if ctx.state.is_complete(MigrationStep.ID_PATHS):
        logger.info("Step 3 (ID Path Renaming) already completed. Skipping.")
    else:
        logger.info(">>> Executing Step 3: Renaming files/folders based on new IDs...")
        _run_step_id_paths(ctx)
        ctx.state.mark_complete(MigrationStep.ID_PATHS)
        ctx.state.save(state_file)
        logger.info("Step 3 Complete.")

    # Step 4: Update IDs in database tables
    if ctx.state.is_complete(MigrationStep.DB_IDS):
        logger.info("Step 4 (Database ID Updates) already completed. Skipping.")
    else:
        logger.info(">>> Executing Step 4: Updating IDs inside database tables...")
        _run_step_db_ids(ctx)
        ctx.state.mark_complete(MigrationStep.DB_IDS)
        ctx.state.save(state_file)
        logger.info("Step 4 Complete.")

    # Step 5: Update file dates
    if ctx.state.is_complete(MigrationStep.DATES):
        logger.info("Step 5 (Date Updates) already completed. Skipping.")
    else:
        logger.info(">>> Executing Step 5: Updating file modification dates...")
        _run_step_dates(ctx)
        ctx.state.mark_complete(MigrationStep.DATES)
        ctx.state.save(state_file)
        logger.info("Step 5 Complete.")

    logger.info("")
    logger.info("Jellyfin Database Migration complete.")


def _run_step_paths(ctx: MigrationContext) -> None:
    """Execute Step 1: Copy files and update paths."""
    config = ctx.config

    # Convert config to dict format for replacer functions
    path_replacements = config.path_replacements.to_dict()
    fs_path_replacements = config.fs_path_replacements.to_dict()

    processed = process_jobs(
        jobs=config.todo_list_paths,
        source_root=config.roots.source,
        original_root=config.roots.original,
        target_root=config.roots.target,
        path_replacements=path_replacements,
        fs_path_replacements=fs_path_replacements,
        replace_func=recursive_path_replace,
    )

    # Find and save jellyfin.db paths
    for job in config.todo_list_paths:
        if job.source.name == "jellyfin.db":
            target, _ = resolve_target_path(
                source=job.source,
                target=job.target,
                source_root=config.roots.source,
                original_root=config.roots.original,
                target_root=config.roots.target,
                path_replacements=path_replacements,
                fs_path_replacements=fs_path_replacements,
            )
            ctx.set_library_db_paths(job.source, target)
            break


def _restore_db_paths(ctx: MigrationContext) -> None:
    """Restore jellyfin.db paths from state when resuming."""
    logger = get_logger()
    config = ctx.config

    if ctx.state.library_db_target_path:
        ctx.library_db_source_path = ctx.state.library_db_source_path
        ctx.library_db_target_path = ctx.state.library_db_target_path
        logger.info(f"Restored DB target path: {ctx.library_db_target_path}")
    else:
        # Recalculate from config
        path_replacements = config.path_replacements.to_dict()
        fs_path_replacements = config.fs_path_replacements.to_dict()

        for job in config.todo_list_paths:
            if job.source.name == "jellyfin.db":
                target, _ = resolve_target_path(
                    source=job.source,
                    target=job.target,
                    source_root=config.roots.source,
                    original_root=config.roots.original,
                    target_root=config.roots.target,
                    path_replacements=path_replacements,
                    fs_path_replacements=fs_path_replacements,
                )
                ctx.set_library_db_paths(job.source, target)
                break


def _calculate_id_replacements(ctx: MigrationContext) -> None:
    """Calculate ID replacements from the migrated database."""
    if not ctx.library_db_target_path:
        raise RuntimeError("Library database path not set")

    bin_replacements = get_id_replacements_from_db(ctx.library_db_target_path)
    ctx.id_replacements = IdReplacements.from_binary_replacements(bin_replacements)


def _run_step_id_paths(ctx: MigrationContext) -> None:
    """Execute Step 3: Rename files/folders with IDs in paths."""
    config = ctx.config

    if not ctx.id_replacements:
        raise RuntimeError("ID replacements not calculated")

    path_replacements = config.path_replacements.to_dict()
    fs_path_replacements = config.fs_path_replacements.to_dict()
    id_path_replacements = ctx.id_replacements.get_path_replacements(
        config.path_replacements.target_slash.value
    )

    # Combine path and ID replacements
    combined_replacements = {**path_replacements, **id_path_replacements}

    process_jobs(
        jobs=config.todo_list_id_paths,
        source_root=config.roots.source,
        original_root=config.roots.original,
        target_root=config.roots.target,
        path_replacements=combined_replacements,
        fs_path_replacements=fs_path_replacements,
        replace_func=recursive_id_path_replace,
    )


def _run_step_db_ids(ctx: MigrationContext) -> None:
    """Execute Step 4: Update IDs in database tables."""
    config = ctx.config

    if not ctx.id_replacements:
        raise RuntimeError("ID replacements not calculated")

    path_replacements = config.path_replacements.to_dict()
    fs_path_replacements = config.fs_path_replacements.to_dict()

    for job in config.todo_list_ids:
        target, _ = resolve_target_path(
            source=job.source,
            target=job.target,
            source_root=config.roots.source,
            original_root=config.roots.original,
            target_root=config.roots.target,
            path_replacements=path_replacements,
            fs_path_replacements=fs_path_replacements,
        )

        if not target.exists():
            continue

        for table_name, table_config in job.tables.items():
            update_db_table_ids(
                db_path=target,
                table=table_name,
                config=table_config,
                id_replacements=ctx.id_replacements,
            )


def _run_step_dates(ctx: MigrationContext) -> None:
    """Execute Step 5: Update file dates in database."""
    config = ctx.config

    if not ctx.library_db_target_path:
        raise RuntimeError("Library database path not set")

    fs_path_replacements = config.fs_path_replacements.to_dict()

    update_file_dates(
        db_path=ctx.library_db_target_path,
        target_root=config.roots.target,
        fs_path_replacements=fs_path_replacements,
    )
