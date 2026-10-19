"""Service factories for the UI.

Process-wide, user-independent objects (database initialization, the
encryption box) are cached with ``st.cache_resource``. Everything that belongs
to a learner — their repository, AI credentials and AI client — is created for
the logged-in user only and never shared between users.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import streamlit as st

from config.settings import get_settings
from core.errors import ConfigurationError, DatabaseError
from core.security import SecretBox
from database.models import Preferences, User
from database.repository import AccountRepository, LearningRepository, initialize
from features.accounts import AIConfig, load_secret_box, resolve_ai_config
from services.llm_service import LLMService
from ui.session import current_user

logger = logging.getLogger(__name__)

_LLM_CACHE_KEY = "_jt_llm_service"


@st.cache_resource(show_spinner=False)
def _initialize_database(db_path: str) -> bool:
    initialize(Path(db_path))
    return True


def ensure_database() -> None:
    _initialize_database(str(get_settings().database_path))


def get_accounts() -> AccountRepository:
    ensure_database()
    return AccountRepository(get_settings().database_path)


@st.cache_resource(show_spinner=False)
def _secret_box() -> SecretBox:
    return load_secret_box(get_settings())


def get_secret_box() -> SecretBox:
    return _secret_box()


def require_user() -> User:
    user = current_user()
    if user is None:
        raise ConfigurationError("Please log in again.")
    return user


def get_repository() -> LearningRepository:
    """The learning repository scoped to the logged-in user."""
    ensure_database()
    return LearningRepository(get_settings().database_path, require_user().id)


def get_preferences() -> Preferences:
    return get_repository().get_preferences()


def get_ai_config() -> AIConfig:
    user = require_user()
    return resolve_ai_config(
        get_settings(), get_accounts(), get_secret_box(), user.id, get_preferences()
    )


def ai_configured() -> bool:
    try:
        return get_ai_config().ready
    except (DatabaseError, ConfigurationError):
        return False


def get_llm() -> LLMService:
    """The AI service for the current user, reused across reruns of this session."""
    config = get_ai_config()
    settings = get_settings()
    fingerprint = hashlib.sha256(
        f"{config.api_key or ''}|{config.model or ''}".encode()
    ).hexdigest()
    cached = st.session_state.get(_LLM_CACHE_KEY)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]
    service = LLMService(
        api_key=config.api_key,
        model=config.model,
        reasoning_effort=settings.openai_reasoning_effort,
        timeout_seconds=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    st.session_state[_LLM_CACHE_KEY] = (fingerprint, service)
    return service


def safe_log_activity(activity_type: str, description: str, **kwargs: int) -> None:
    """Log activity without interrupting the learner if the database write fails."""
    try:
        get_repository().log_activity(activity_type, description, **kwargs)
    except (DatabaseError, ConfigurationError):
        logger.warning("Could not log activity %s", activity_type)
