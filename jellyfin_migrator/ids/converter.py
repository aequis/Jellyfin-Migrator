"""ID format conversion utilities for Jellyfin IDs.

Jellyfin uses MD5 hashes as IDs in multiple formats:
- Binary (16 bytes)
- String (32 hex chars): '833addde992893e93d0572907f8b4cad'
- String with dashes: '833addde-9928-93e9-3d05-72907f8b4cad'
- "Ancestor" variants (first 8 bytes rearranged): 'dedd3a832899e9933d0572907f8b4cad'

IDs are derived from MD5(item_type + path) encoded as UTF-16-LE.
"""

import binascii
import hashlib
from dataclasses import dataclass, field
from typing import Dict, NewType


# Type aliases for clarity
BinaryId = NewType('BinaryId', bytes)
StringId = NewType('StringId', str)
DashedId = NewType('DashedId', str)


def convert_ancestor_id(id_str: str) -> str:
    """Regroup bytes to convert from/to ancestor ID format (symmetric operation).

    The ancestor format rearranges the first 8 bytes in a specific order.
    This operation is its own inverse.

    Args:
        id_str: 32-character hex string ID

    Returns:
        Converted 32-character hex string ID
    """
    # Group by bytes (2 hex chars each)
    id_bytes = [id_str[i:i+2] for i in range(0, len(id_str), 2)]

    # Reorder first 8 bytes, keep rest unchanged
    byte_order = (3, 2, 1, 0, 5, 4, 7, 6)
    swapped = [id_bytes[i] for i in byte_order]
    swapped.extend(id_bytes[8:])

    return "".join(swapped)


def binary_to_string(id_bytes: bytes) -> str:
    """Convert binary ID to hex string.

    Args:
        id_bytes: 16-byte binary ID

    Returns:
        32-character hex string
    """
    return binascii.b2a_hex(id_bytes).decode("ascii")


def string_to_binary(id_str: str) -> bytes:
    """Convert hex string ID to binary.

    Args:
        id_str: 32-character hex string

    Returns:
        16-byte binary ID
    """
    return binascii.a2b_hex(id_str)


def string_to_dashed(id_str: str) -> str:
    """Convert hex string ID to dashed format.

    Args:
        id_str: 32-character hex string

    Returns:
        Dashed format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    """
    return "-".join([
        id_str[:8],
        id_str[8:12],
        id_str[12:16],
        id_str[16:20],
        id_str[20:]
    ])


def dashed_to_string(id_dashed: str) -> str:
    """Convert dashed format ID to hex string.

    Args:
        id_dashed: Dashed format ID

    Returns:
        32-character hex string
    """
    return id_dashed.replace("-", "")


def get_dotnet_md5(s: str) -> bytes:
    """Calculate MD5 hash the way .NET does (UTF-16-LE encoding).

    Args:
        s: String to hash

    Returns:
        16-byte MD5 hash
    """
    return hashlib.md5(s.encode("utf-16-le")).digest()


# Aliases for backward compatibility with original script
bid2sid = binary_to_string
sid2bid = string_to_binary
sid2did = string_to_dashed


@dataclass
class IdReplacements:
    """Mapping from old IDs to new IDs in all formats."""

    bin: Dict[bytes, bytes] = field(default_factory=dict)
    str: Dict[str, str] = field(default_factory=dict)
    str_dash: Dict[str, str] = field(default_factory=dict)
    ancestor_bin: Dict[bytes, bytes] = field(default_factory=dict)
    ancestor_str: Dict[str, str] = field(default_factory=dict)
    ancestor_str_dash: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_binary_replacements(cls, bin_replacements: Dict[bytes, bytes]) -> "IdReplacements":
        """Create IdReplacements from binary ID mappings.

        Generates all format variants from the binary mappings.

        Args:
            bin_replacements: Dict mapping old binary IDs to new binary IDs

        Returns:
            IdReplacements with all format variants populated
        """
        str_replacements = {
            binary_to_string(k): binary_to_string(v)
            for k, v in bin_replacements.items()
        }
        str_dash_replacements = {
            string_to_dashed(k): string_to_dashed(v)
            for k, v in str_replacements.items()
        }
        ancestor_str_replacements = {
            convert_ancestor_id(k): convert_ancestor_id(v)
            for k, v in str_replacements.items()
        }
        ancestor_bin_replacements = {
            string_to_binary(k): string_to_binary(v)
            for k, v in ancestor_str_replacements.items()
        }
        ancestor_str_dash_replacements = {
            string_to_dashed(k): string_to_dashed(v)
            for k, v in ancestor_str_replacements.items()
        }

        return cls(
            bin=bin_replacements,
            str=str_replacements,
            str_dash=str_dash_replacements,
            ancestor_bin=ancestor_bin_replacements,
            ancestor_str=ancestor_str_replacements,
            ancestor_str_dash=ancestor_str_dash_replacements,
        )

    def get_path_replacements(self, target_slash: str) -> Dict[str, str]:
        """Get combined replacements suitable for path operations.

        Args:
            target_slash: Target path separator ("/" or "\\")

        Returns:
            Dict with all string-based ID replacements plus target_path_slash
        """
        return {
            **self.ancestor_str,
            **self.ancestor_str_dash,
            **self.str,
            **self.str_dash,
            "target_path_slash": target_slash,
        }

    def __len__(self) -> int:
        """Return number of ID mappings."""
        return len(self.bin)
