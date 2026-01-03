"""
PII Detection Patterns

Regex patterns and validators for detecting various PII types.
"""

import re
from typing import Any


def validate_email(value: str) -> bool:
    """Validate email format."""
    return "@" in value and "." in value.split("@")[-1]


def validate_phone(value: str) -> bool:
    """Validate phone number format."""
    digits = re.sub(r"\D", "", value)
    return len(digits) >= 10


def validate_ssn(value: str) -> bool:
    """Validate SSN format and basic rules."""
    digits = re.sub(r"\D", "", value)
    if len(digits) != 9:
        return False
    # SSN area number can't be 000, 666, or 900-999
    area = int(digits[:3])
    if area == 0 or area == 666 or 900 <= area <= 999:
        return False
    return True


def validate_credit_card(value: str) -> bool:
    """Validate credit card using Luhn algorithm."""
    digits = re.sub(r"\D", "", value)
    if len(digits) < 13 or len(digits) > 19:
        return False

    # Luhn check
    total = 0
    for i, digit in enumerate(reversed(digits)):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def validate_ip_address(value: str) -> bool:
    """Validate IP address format."""
    parts = value.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        try:
            n = int(part)
            if n < 0 or n > 255:
                return False
        except ValueError:
            return False
    return True


# PII patterns with regex and optional validators
PII_PATTERNS: dict[str, dict[str, Any]] = {
    "email": {
        "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "validator": validate_email,
    },
    "phone": {
        "pattern": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "validator": validate_phone,
    },
    "ssn": {
        "pattern": r"\d{3}[-\s]?\d{2}[-\s]?\d{4}",
        "validator": validate_ssn,
    },
    "credit_card": {
        "pattern": r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",
        "validator": validate_credit_card,
    },
    "ip_address": {
        "pattern": r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
        "validator": validate_ip_address,
    },
}
