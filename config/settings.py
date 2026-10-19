"""Load and validate application settings.

Settings come from (highest priority first):

1. Process environment variables.
2. A local ``.env`` file (loaded with python-dotenv; never overrides real env vars).
3. Streamlit secrets (``.streamlit/secrets.toml`` locally, or the host's secret store).

Importing this module never requires an API key. A missing key only disables
the AI features; the rest of the app (and the test suite) keeps working.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

from core.errors import ConfigurationError

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "japanese_tutor.db"
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-/]{0,99}$")
_EFFORT = re.compile(r"^[a-z]{1,20}$")


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings. Secrets are wrapped in ``SecretStr``."""

    openai_api_key: SecretStr | None
    openai_model: str | None
    openai_reasoning_effort: str | None
    openai_timeout_seconds: float
    openai_max_retries: int
    database_path: Path
    log_level: str
    app_password: SecretStr | None
    app_secret_key: SecretStr | None = None
    share_server_api_key: bool = True
    allow_signups: bool = True
    session_days: int = 14

    @property
    def ai_configured(self) -> bool:
        """True when the *server* provides both a key and a model.

        Learners can still use AI features with their own key and model saved
        in Settings; see ``features.accounts.resolve_ai_config``.
        """
        return self.openai_api_key is not None and self.openai_model is not None

    def missing_ai_settings(self) -> list[str]:
        missing = []
        if self.openai_api_key is None:
            missing.append("OPENAI_API_KEY")
        if self.openai_model is None:
            missing.append("OPENAI_MODEL")
        return missing

    def secret_values(self) -> list[str]:
        """Raw secret values, used only to register them for log redaction."""
        return [
            secret.get_secret_value()
            for secret in (self.openai_api_key, self.app_password, self.app_secret_key)
            if secret is not None
        ]


def _read_streamlit_secret(name: str) -> str | None:
    """Return a top-level Streamlit secret, or None when unavailable."""
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception as exc:  # no secrets file, or not running under Streamlit
        logger.debug("Streamlit secrets unavailable (%s)", type(exc).__name__)
        return None
    return str(value) if value is not None else None


def _get(name: str, env: Mapping[str, str], use_streamlit_secrets: bool) -> str | None:
    value = env.get(name)
    if (value is None or not value.strip()) and use_streamlit_secrets:
        value = _read_streamlit_secret(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_bool(raw: str | None, *, name: str, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false.")


def _parse_float(raw: str | None, *, name: str, default: float, low: float, high: float) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigurationError(f"{name} must be a number (got an invalid value).") from None
    if not low <= value <= high:
        raise ConfigurationError(f"{name} must be between {low:g} and {high:g}.")
    return value


def _parse_int(raw: str | None, *, name: str, default: int, low: int, high: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigurationError(f"{name} must be a whole number.") from None
    if not low <= value <= high:
        raise ConfigurationError(f"{name} must be between {low} and {high}.")
    return value


def load_settings(
    env: Mapping[str, str] | None = None,
    *,
    use_dotenv: bool = True,
    use_streamlit_secrets: bool = True,
) -> Settings:
    """Build a validated :class:`Settings` object.

    Raises :class:`ConfigurationError` for values that are present but invalid.
    Missing AI credentials are *not* an error here; see ``Settings.ai_configured``.
    """
    if env is None:
        if use_dotenv:
            load_dotenv(PROJECT_ROOT / ".env", override=False)
        env = os.environ

    api_key = _get("OPENAI_API_KEY", env, use_streamlit_secrets)
    model = _get("OPENAI_MODEL", env, use_streamlit_secrets)
    if model is not None and not _MODEL_NAME.match(model):
        raise ConfigurationError("OPENAI_MODEL contains unexpected characters.")

    effort = _get("OPENAI_REASONING_EFFORT", env, use_streamlit_secrets)
    if effort is not None:
        effort = effort.lower()
        if not _EFFORT.match(effort):
            raise ConfigurationError("OPENAI_REASONING_EFFORT must be a single word, e.g. low.")

    log_level = (_get("LOG_LEVEL", env, use_streamlit_secrets) or "INFO").upper()
    if log_level not in _VALID_LOG_LEVELS:
        raise ConfigurationError(
            f"LOG_LEVEL must be one of {', '.join(sorted(_VALID_LOG_LEVELS))}."
        )

    db_raw = _get("DATABASE_PATH", env, use_streamlit_secrets)
    if db_raw:
        db_path = Path(db_raw).expanduser()
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
    else:
        db_path = DEFAULT_DATABASE_PATH

    password = _get("APP_PASSWORD", env, use_streamlit_secrets)
    secret_key = _get("APP_SECRET_KEY", env, use_streamlit_secrets)

    return Settings(
        openai_api_key=SecretStr(api_key) if api_key else None,
        openai_model=model,
        openai_reasoning_effort=effort,
        openai_timeout_seconds=_parse_float(
            _get("OPENAI_TIMEOUT_SECONDS", env, use_streamlit_secrets),
            name="OPENAI_TIMEOUT_SECONDS",
            default=60.0,
            low=5.0,
            high=600.0,
        ),
        openai_max_retries=_parse_int(
            _get("OPENAI_MAX_RETRIES", env, use_streamlit_secrets),
            name="OPENAI_MAX_RETRIES",
            default=2,
            low=0,
            high=5,
        ),
        database_path=db_path.resolve(),
        log_level=log_level,
        app_password=SecretStr(password) if password else None,
        app_secret_key=SecretStr(secret_key) if secret_key else None,
        share_server_api_key=_parse_bool(
            _get("SHARE_SERVER_API_KEY", env, use_streamlit_secrets),
            name="SHARE_SERVER_API_KEY",
            default=True,
        ),
        allow_signups=_parse_bool(
            _get("ALLOW_SIGNUPS", env, use_streamlit_secrets), name="ALLOW_SIGNUPS", default=True
        ),
        session_days=_parse_int(
            _get("SESSION_DAYS", env, use_streamlit_secrets),
            name="SESSION_DAYS",
            default=14,
            low=0,
            high=90,
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, loaded once."""
    return load_settings()
