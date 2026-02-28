"""Fernet encryption utility for sensitive configuration values.

Provides encrypt/decrypt functions with a graceful plaintext fallback
when no encryption key is configured (development/testing convenience).
"""

from __future__ import annotations

import os

import structlog
from cryptography.fernet import Fernet

logger = structlog.get_logger()

_PLAIN_PREFIX = "plain:"


def get_fernet() -> Fernet | None:
    """Return a Fernet instance from the ``EVENT_DEDUP_ENCRYPTION_KEY`` env var.

    Returns ``None`` if the env var is not set or empty.
    """
    key = os.environ.get("EVENT_DEDUP_ENCRYPTION_KEY", "")
    if not key:
        return None
    return Fernet(key.encode())


def encrypt_value(value: str) -> str:
    """Encrypt *value* with Fernet, falling back to plain-text prefix.

    When no encryption key is configured, the value is stored with a
    ``plain:`` prefix so that :func:`decrypt_value` can recover it.
    A warning is logged in this case.
    """
    fernet = get_fernet()
    if fernet is None:
        logger.warning(
            "encryption_key_not_set",
            hint="Set EVENT_DEDUP_ENCRYPTION_KEY for production use",
        )
        return f"{_PLAIN_PREFIX}{value}"
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt *token* with Fernet, handling the ``plain:`` prefix fallback.

    If the token starts with ``plain:``, the remainder is returned as-is
    (backward compatibility with values stored without encryption).
    """
    if token.startswith(_PLAIN_PREFIX):
        return token[len(_PLAIN_PREFIX):]
    fernet = get_fernet()
    if fernet is None:
        # Token appears encrypted but we have no key -- this is an error
        raise RuntimeError(
            "Cannot decrypt value: EVENT_DEDUP_ENCRYPTION_KEY is not set "
            "but the stored token is not plain-text."
        )
    return fernet.decrypt(token.encode()).decode()
