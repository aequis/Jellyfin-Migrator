# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jellyfin-Migrator is a Python package that migrates Jellyfin media server databases between systems (typically Windows to Linux/Docker). It handles path adjustments, internal ID recalculation, and file date updates that are required for a successful migration.

## Running the Scripts

### Main Migration Script (New - Modular)
```bash
# Install dependencies
pip install -r requirements.txt

# Start migration with config file
python -m jellyfin_migrator migrate --config config.yaml

# Skip disk space check
python -m jellyfin_migrator migrate --config config.yaml --skip-disk-check

# Reset progress and start over
python -m jellyfin_migrator migrate --config config.yaml --reset
```

### Legacy Script (Original)
```bash
# Edit configuration at top of jellyfin_migrator.py first
python jellyfin_migrator.py migrate
```

### ID Scanner (for analyzing plugin databases)
```bash
python jellyfin_id_scanner.py --library-db "path/to/library.db" --scan-db "path/to/plugin.db"
```

## Package Structure

```
jellyfin_migrator/
├── __init__.py              # Package metadata
├── __main__.py              # Entry point for python -m
├── cli.py                   # Command-line interface
├── config/
│   ├── loader.py            # YAML config loading
│   └── schema.py            # Dataclasses for configuration
├── core/
│   ├── context.py           # MigrationContext (replaces globals)
│   ├── exceptions.py        # Custom exception hierarchy
│   ├── migrator.py          # Main migration orchestration
│   └── state.py             # Checkpoint/resume state management
├── database/
│   ├── id_operations.py     # ID updates in database tables
│   └── sqlite_handler.py    # SQLite path operations
├── files/
│   ├── copier.py            # File copy operations
│   ├── date_updater.py      # File date synchronization
│   └── processor.py         # File processing orchestration
├── ids/
│   ├── converter.py         # ID format conversions
│   ├── generator.py         # ID generation from paths
│   └── scanner.py           # ID scanning utilities
├── parsers/
│   ├── json_parser.py       # JSON file handling
│   ├── mblink_parser.py     # .mblink file handling
│   └── xml_parser.py        # XML/NFO file handling
├── path/
│   ├── replacer.py          # Path replacement logic
│   └── resolver.py          # Target path resolution
└── utils/
    ├── datetime_utils.py    # Date/time conversions
    ├── disk.py              # Disk space checking
    └── logging.py           # Logging setup
```

## Architecture

The migration is a multi-step process with checkpoint-based resume capability:

1. **Step 1 (Path Migration)**: Copies files and updates all hardcoded paths
2. **Step 3 (ID Path Renaming)**: Renames files/folders with IDs in paths
3. **Step 4 (Database ID Updates)**: Updates internal IDs in database tables
4. **Step 5 (Date Updates)**: Synchronizes file dates in the database

Progress is saved to `migration_state.json` allowing resume after interruption.

### Key Components

**MigrationContext** (`core/context.py`): Replaces global variables, holds all mutable state

**MigrationConfig** (`config/schema.py`): Typed configuration from YAML file

**IdReplacements** (`ids/converter.py`): Mappings from old IDs to new in all formats

### ID Format Variants

Jellyfin uses MD5 hashes as IDs in multiple formats:
- Binary (16 bytes)
- String (32 hex chars): `833addde992893e93d0572907f8b4cad`
- String with dashes: `833addde-9928-93e9-3d05-72907f8b4cad`
- "Ancestor" variants (first 8 bytes rearranged): `dedd3a832899e9933d0572907f8b4cad`

IDs are derived from `MD5(item_type + path)` encoded as UTF-16-LE.

### Database Schema (Jellyfin 10.11+)

The script handles Jellyfin 10.11+ schema changes:

**Table renames:**
- `TypedBaseItems` -> `BaseItems`
- `mediastreams` -> `MediaStreamInfos`
- `Chapters2` -> `Chapters`
- `UserDatas` -> `UserData`
- `ItemValues` -> `ItemValuesMap`
- `Peoples` -> `PeopleBaseItemMap`
- New table: `ImageInfos`

**ID storage format:**
- IDs now stored as hex strings (TEXT) instead of binary (BLOB)
- Columns like `Id`, `ItemId`, `ParentId` use string format
- The code handles both formats for backward compatibility

## Configuration

Configuration is in YAML format. See `config.yaml.example` for a complete example.

Key sections:
- `logging`: Log file path and level
- `roots`: original/source/target root directories
- `path_replacements`: Source to target path mappings
- `fs_path_replacements`: Virtual to filesystem path mappings
- `todo_list_*`: Files and tables to process

## Dependencies

- `PyYAML`: YAML configuration parsing
- `tqdm`: Progress bar display

## Limitations

- Script must run on Windows (uses `pathlib.is_absolute()` behavior specific to Windows)
- Subtitle cache files (`data/subtitles`) cannot be migrated
- `network.xml` should typically not be migrated as network config differs between systems
