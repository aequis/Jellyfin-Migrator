"""Jellyfin Migrator - Migrate Jellyfin databases between systems.

This package provides tools to migrate a Jellyfin media server database
from one system to another (e.g., Windows to Linux/Docker).

Main entry points:
    - CLI: python -m jellyfin_migrator migrate --config config.yaml
    - API: from jellyfin_migrator.core.migrator import run_migration
"""

__version__ = "2.0.0"
__author__ = "Max Zuidberg"
__license__ = "AGPL-3.0"
