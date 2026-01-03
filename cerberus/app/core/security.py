"""
Security Utilities

Password hashing, JWT tokens, API key generation and validation.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.config.settings import settings


# JWT configuration
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token.

    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT token.

    Args:
        token: JWT token to decode

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_api_key(prefix: Optional[str] = None) -> tuple[str, str]:
    """Generate a new API key and its hash.

    Args:
        prefix: Optional custom prefix (e.g., "uak-" for user access keys).
                Defaults to settings.API_KEY_PREFIX.

    Returns:
        Tuple of (plain_key, hashed_key)
        - plain_key: The key to give to the user (shown only once)
        - hashed_key: The hash to store in the database
    """
    # Generate a secure random key
    key_body = secrets.token_urlsafe(32)
    key_prefix = prefix or settings.API_KEY_PREFIX
    plain_key = f"{key_prefix}{key_body}"

    # Create a hash of the key for storage
    hashed_key = hash_api_key(plain_key)

    return plain_key, hashed_key


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage.

    Args:
        api_key: Plain API key

    Returns:
        SHA-256 hash of the API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_api_key_prefix(api_key: str) -> str:
    """Get the prefix portion of an API key for display.

    Args:
        api_key: Full API key

    Returns:
        Prefix with masked remainder (e.g., "sk-xxxx...xxxx")
    """
    if len(api_key) > 12:
        return f"{api_key[:8]}...{api_key[-4:]}"
    return api_key[:8] + "..."


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token.

    Args:
        length: Length of the token in bytes

    Returns:
        URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(length)


def generate_uuid_token() -> str:
    """Generate a UUID-style token.

    Returns:
        UUID-formatted string
    """
    return secrets.token_hex(16)
