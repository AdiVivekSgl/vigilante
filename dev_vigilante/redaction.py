"""Redaction of secrets from configuration before it is exported.

Pure and dependency-free so it is unit-testable outside a bench. Snapshots are meant
to be committed to Git and handed to AI assistants, so this errs on the side of
over-redacting.
"""

from __future__ import annotations

import re

# Keys whose values must never appear in an exported snapshot (substring match on the
# lower-cased key).
SECRET_MARKERS = (
    "password",
    "passwd",
    "secret",
    "api_key",
    "access_key",
    "token",
    "encryption_key",
    "private",
    "credential",
    "webhook",
    "signing",
    "salt",
    "dsn",
)

REDACTED = "***REDACTED***"

# scheme://user:password@host  ->  scheme://user:***REDACTED***@host
_URL_CREDENTIALS = re.compile(r"(?P<prefix>[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]*:)[^@\s/]+(?=@)")


def is_secret_key(key) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def redact(value):
    """Return a copy of ``value`` with secret keys and URL credentials masked.

    Walks nested dicts and lists; dict keys are emitted in sorted order so output is
    deterministic.
    """
    if isinstance(value, dict):
        return {
            key: REDACTED if is_secret_key(key) else redact(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _URL_CREDENTIALS.sub(lambda m: m.group("prefix") + REDACTED, value)
    return value
