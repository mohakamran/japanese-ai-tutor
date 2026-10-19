"""Logging setup with secret redaction.

Every log line passes through :class:`RedactingFormatter`, which masks anything
that looks like an OpenAI key plus any secret value registered at startup.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+")
REDACTED = "[REDACTED]"
_HANDLER_NAME = "japanese_tutor_handler"


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Mask API-key-like strings and the given secret values in ``text``."""
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, REDACTED)
    text = _KEY_PATTERN.sub(REDACTED, text)
    return _BEARER_PATTERN.sub(r"\1" + REDACTED, text)


class RedactingFormatter(logging.Formatter):
    """A formatter that redacts secrets from the fully formatted record,
    including exception tracebacks."""

    def __init__(self, fmt: str, secrets: Iterable[str] = ()) -> None:
        super().__init__(fmt)
        self._secrets = [s for s in secrets if s]

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record), self._secrets)


def configure_logging(level: str = "INFO", secrets: Iterable[str] = ()) -> None:
    """Install a single redacting console handler on the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level)
    formatter = RedactingFormatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", secrets=secrets
    )
    for handler in root.handlers:
        if handler.get_name() == _HANDLER_NAME:
            handler.setFormatter(formatter)
            break
    else:
        handler = logging.StreamHandler()
        handler.set_name(_HANDLER_NAME)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # HTTP client libraries are noisy at INFO; keep them at WARNING.
    for noisy in ("httpx", "httpx2", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))
