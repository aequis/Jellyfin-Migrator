"""Date and time conversion utilities for Jellyfin database values.

Jellyfin stores dates in ISO-like format with sub-second precision.
This module handles conversion between Jellyfin's format and Python datetime.
"""

import datetime
from string import ascii_letters


def jellyfin_date_to_ns(date_str: str) -> int:
    """Convert Jellyfin date string to nanoseconds since epoch.

    Jellyfin date format example: '2022-10-21 15:30:45.1234567Z'

    Args:
        date_str: Jellyfin format date string

    Returns:
        Nanoseconds since Unix epoch (can be negative for pre-epoch dates)
    """
    # Python datetime has only support for microseconds.
    # Split off fractional seconds and handle separately.
    subseconds_str = "0"
    if "." in date_str:
        date_str, subseconds_str = date_str.rsplit(".", 1)

    # Strip timezone suffix and any non-numeric chars from subseconds
    # Format may include: .1234567+00:00 or .1234567Z
    subseconds_str = subseconds_str.split("+")[0].rstrip(ascii_letters)

    # Pad to nanoseconds (9 digits), then convert
    subseconds_ns = int(subseconds_str.ljust(9, "0"))

    # Add explicit UTC timezone info
    date_str += "+00:00"

    # Parse and convert to timestamp
    dt = datetime.datetime.fromisoformat(date_str)
    timestamp_s = int(dt.timestamp())

    # Convert to nanoseconds and add subseconds
    return timestamp_s * 1_000_000_000 + subseconds_ns


def ns_to_jellyfin_date(time_ns: int) -> str:
    """Convert nanoseconds since epoch to Jellyfin date string.

    Args:
        time_ns: Nanoseconds since Unix epoch

    Returns:
        Jellyfin format date string (e.g., '2022-10-21 15:30:45.1234567Z')
    """
    # Separate seconds and sub-seconds
    time_s = time_ns // 1_000_000_000
    time_frac_100ns = (time_ns // 100) % 10_000_000

    # Create UTC datetime
    dt = datetime.datetime.utcfromtimestamp(time_s)
    timestamp = dt.isoformat(sep=" ", timespec="seconds")

    # Add sub-seconds in .NET 100ns tick format, trailing zeros stripped
    subsec_str = str(time_frac_100ns).rjust(7, "0").rstrip("0")
    if subsec_str:
        timestamp += "." + subsec_str
    timestamp += "Z"

    return timestamp


def get_file_dates_ns(file_path) -> tuple[int, int]:
    """Get file creation and modification times in nanoseconds.

    Args:
        file_path: Path to file (str or Path object)

    Returns:
        Tuple of (creation_time_ns, modification_time_ns)
    """
    import os
    from pathlib import Path

    path = Path(file_path)
    stats = os.stat(path)

    return stats.st_ctime_ns, stats.st_mtime_ns
