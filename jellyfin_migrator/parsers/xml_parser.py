"""XML and NFO file parsing for Jellyfin migration."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Dict, Set

from jellyfin_migrator.path.replacer import ReplacementResult
from jellyfin_migrator.utils.logging import get_logger


# Tags that don't contain paths and should be skipped
SKIP_TAGS: Set[str] = {"biography", "outline"}


def update_xml_file(
    file_path: Path,
    replacements: Dict[str, str],
    replace_func: Callable,
) -> ReplacementResult:
    """Update paths in an XML or NFO file.

    Args:
        file_path: Path to the XML/NFO file
        replacements: Path replacement mappings
        replace_func: Function to apply replacements

    Returns:
        ReplacementResult with statistics
    """
    logger = get_logger()
    modified, ignored = 0, 0

    tree = ET.parse(file_path)
    root = tree.getroot()

    for element in root.iter():
        # Skip tags known to not contain paths
        if element.tag in SKIP_TAGS:
            continue

        if element.text:
            result = replace_func(element.text, replacements)
            element.text = result.value
            modified += result.modified_count
            ignored += result.ignored_count

    logger.debug(f"Processed {modified + ignored} elements, {modified} modified")
    tree.write(file_path, encoding="unicode")

    return ReplacementResult(
        value=None,
        modified_count=modified,
        ignored_count=ignored,
    )


def parse_xml_paths(file_path: Path) -> list[str]:
    """Extract all potential paths from an XML file.

    Useful for debugging and validation.

    Args:
        file_path: Path to the XML file

    Returns:
        List of strings that look like paths
    """
    paths = []
    tree = ET.parse(file_path)
    root = tree.getroot()

    for element in root.iter():
        if element.text and ("/" in element.text or "\\" in element.text):
            # Looks like a path
            text = element.text.strip()
            if text and not text.startswith("http"):
                paths.append(text)

    return paths
