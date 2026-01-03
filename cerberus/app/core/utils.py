"""
Common Utilities

Helper functions used throughout the application.
"""

import math
import re
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any, TypeVar

from slugify import slugify as python_slugify

T = TypeVar("T")


def generate_uuid() -> str:
    """Generate a new UUID string.

    Returns:
        UUID4 string
    """
    return str(uuid.uuid4())


def generate_short_id(prefix: str = "") -> str:
    """Generate a short, URL-safe ID.

    Args:
        prefix: Optional prefix for the ID

    Returns:
        Short ID string (e.g., "usr-abc123")
    """
    short_uuid = uuid.uuid4().hex[:12]
    if prefix:
        return f"{prefix}-{short_uuid}"
    return short_uuid


def utc_now() -> datetime:
    """Get current UTC datetime.

    Returns:
        Current datetime with UTC timezone
    """
    return datetime.now(UTC)


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to URL-safe slug.

    Args:
        text: Text to slugify
        max_length: Maximum length of the slug

    Returns:
        URL-safe slug string
    """
    try:
        slug = python_slugify(text, max_length=max_length)
    except (TypeError, ValueError, AttributeError):
        # Fallback for edge cases or invalid input
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")
        slug = slug[:max_length]
    return slug


def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
    merge_lists: bool = True,
) -> dict[str, Any]:
    """Deep merge two dictionaries.

    For nested dicts, recursively merges. For lists, behavior depends on merge_lists:
    - If merge_lists=True (default): Lists are concatenated (base + override),
      with duplicates removed for lists of dicts that have a 'name' key.
    - If merge_lists=False: Override list replaces base list entirely.

    Args:
        base: Base dictionary
        override: Dictionary to merge on top
        merge_lists: Whether to merge lists (True) or replace them (False)

    Returns:
        Merged dictionary

    Example:
        base = {"rbac": {"default_action": "deny", "allowed_tools": ["read_file"]}}
        override = {"rbac": {"allowed_tools": ["write_file"]}}
        result = deep_merge(base, override)
        # result = {
        #     "rbac": {"default_action": "deny", "allowed_tools": ["read_file", "write_file"]}
        # }
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value, merge_lists=merge_lists)
        elif (
            merge_lists
            and key in result
            and isinstance(result[key], list)
            and isinstance(value, list)
        ):
            # Merge lists - concatenate and deduplicate by 'name' if items are dicts
            result[key] = _merge_lists(result[key], value)
        else:
            result[key] = value
    return result


def _merge_lists(base_list: list[Any], override_list: list[Any]) -> list[Any]:
    """Merge two lists, deduplicating dicts by 'name' key if present.

    For lists of dicts with 'name' keys, later items
    override earlier items with the same name. For other lists, simply concatenate.

    Args:
        base_list: Base list
        override_list: Override list

    Returns:
        Merged list
    """
    # Check if these are lists of dicts with 'name' keys
    all_are_named_dicts = all(
        isinstance(item, dict) and "name" in item
        for item in base_list + override_list
        if item is not None
    )

    if all_are_named_dicts and (base_list or override_list):
        # Deduplicate by name - override wins
        seen_names: dict[str, dict[str, Any]] = {}
        for item in base_list:
            if isinstance(item, dict) and "name" in item:
                seen_names[item["name"]] = item
        for item in override_list:
            if isinstance(item, dict) and "name" in item:
                seen_names[item["name"]] = item
        return list(seen_names.values())
    # Simple concatenation for other list types
    return base_list + override_list


def mask_sensitive_data(
    data: str,
    visible_chars: int = 4,
    mask_char: str = "*",
) -> str:
    """Mask sensitive data, showing only first/last few characters.

    Args:
        data: Data to mask
        visible_chars: Number of characters to show at start and end
        mask_char: Character to use for masking

    Returns:
        Masked string
    """
    if len(data) <= visible_chars * 2:
        return mask_char * len(data)
    return f"{data[:visible_chars]}{mask_char * 8}{data[-visible_chars:]}"


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate a string to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to append if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def parse_list_from_string(value: str, separator: str = ",") -> list[str]:
    """Parse a comma-separated string into a list.

    Args:
        value: String to parse
        separator: Separator character

    Returns:
        List of trimmed strings
    """
    if not value:
        return []
    return [item.strip() for item in value.split(separator) if item.strip()]


def safe_get(
    dictionary: dict[str, Any],
    *keys: str,
    default: T | None = None,
) -> T | Any | None:
    """Safely get a nested value from a dictionary.

    Args:
        dictionary: Dictionary to search
        *keys: Sequence of keys to traverse
        default: Default value if not found

    Returns:
        Found value or default
    """
    result = dictionary
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
        if result is None:
            return default
    return result


def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID.

    Args:
        value: String to check

    Returns:
        True if valid UUID
    """
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string.

    Used for secret detection - high entropy strings are more likely to be secrets.

    Args:
        text: String to analyze

    Returns:
        Entropy value (higher = more random)
    """
    if not text:
        return 0.0

    # Count character frequencies
    freq = Counter(text)
    length = len(text)

    # Calculate entropy
    entropy = 0.0
    for char_count in freq.values():
        probability = char_count / length
        entropy -= probability * math.log2(probability)

    return entropy


def batch_list(items: list[T], batch_size: int) -> list[list[T]]:
    """Split a list into batches.

    Args:
        items: List to split
        batch_size: Size of each batch

    Returns:
        List of batches
    """
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
