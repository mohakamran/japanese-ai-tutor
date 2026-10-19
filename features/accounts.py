"""Accounts: sign-up, login, sessions, profile changes, deletion, and AI credentials."""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from config.settings import Settings
from core.errors import InputValidationError
from core.security import (
    DUMMY_PASSWORD_HASH,
    SecretBox,
    api_key_hint,
    hash_password,
    hash_session_token,
    new_session_token,
    validate_display_name,
    validate_email,
    validate_new_password,
    verify_password,
)
from database.models import Preferences, User
from database.repository import AccountRepository

logger = logging.getLogger(__name__)

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 10
DELETE_CONFIRMATION = "DELETE"
_API_KEY = re.compile(r"^[A-Za-z0-9_\-]{20,300}$")
_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-/]{0,99}$")
_GENERIC_LOGIN_ERROR = "Incorrect email or password."


# ------------------------------------------------------------- sign up / in


def sign_up(
    accounts: AccountRepository,
    *,
    email: str,
    display_name: str,
    password: str,
    confirm_password: str,
) -> User:
    """Create an account. The very first account inherits any pre-account data."""
    email = validate_email(email)
    display_name = validate_display_name(display_name)
    validate_new_password(password, email=email)
    if password != confirm_password:
        raise InputValidationError("The two passwords do not match.")
    first_user = accounts.count_users() == 0
    user = accounts.create_user(
        email=email, display_name=display_name, password_hash=hash_password(password)
    )
    if first_user:
        accounts.claim_unowned_data(user.id)
    logger.info("New account created (id=%d)", user.id)
    return user


def authenticate(accounts: AccountRepository, *, email: str, password: str) -> User:
    """Return the user for valid credentials, or raise a deliberately vague error.

    After ``MAX_FAILED_LOGINS`` wrong passwords the account is locked for
    ``LOCKOUT_MINUTES``. Unknown emails take the same time as wrong passwords.
    """
    try:
        email = validate_email(email)
    except InputValidationError:
        raise InputValidationError(_GENERIC_LOGIN_ERROR) from None
    if not password:
        raise InputValidationError("Please enter your password.")

    creds = accounts.get_credentials(email=email)
    if creds is None:
        verify_password(password, DUMMY_PASSWORD_HASH)  # equalize timing
        raise InputValidationError(_GENERIC_LOGIN_ERROR)

    if creds.locked_until:
        remaining = _minutes_until(creds.locked_until)
        if remaining > 0:
            raise InputValidationError(
                f"Too many failed attempts. Please try again in {remaining} minute"
                f"{'s' if remaining != 1 else ''}."
            )

    if not verify_password(password, creds.password_hash):
        locked = accounts.record_login_failure(
            creds.user.id, lock_after=MAX_FAILED_LOGINS, lock_minutes=LOCKOUT_MINUTES
        )
        logger.warning("Failed login (user id=%d, locked=%s)", creds.user.id, locked)
        if locked:
            raise InputValidationError(
                f"Too many failed attempts. Your account is locked for {LOCKOUT_MINUTES} minutes."
            )
        raise InputValidationError(_GENERIC_LOGIN_ERROR)

    accounts.record_login_success(creds.user.id)
    return accounts.get_user(creds.user.id) or creds.user


def _minutes_until(timestamp: str) -> int:
    until = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    seconds = (until - datetime.now(UTC)).total_seconds()
    return math.ceil(seconds / 60) if seconds > 0 else 0


# ---------------------------------------------------------------- sessions


def start_session(accounts: AccountRepository, user_id: int, *, days: int) -> str:
    """Create a 'remember me' session and return the raw token (stored only hashed)."""
    token = new_session_token()
    accounts.create_session(user_id, hash_session_token(token), days=days)
    return token


def resume_session(accounts: AccountRepository, token: str | None) -> User | None:
    if not isinstance(token, str) or not token or len(token) > 200:
        return None
    return accounts.get_session_user(hash_session_token(token))


def end_session(accounts: AccountRepository, token: str | None) -> None:
    if token:
        accounts.delete_session(hash_session_token(token))


# ----------------------------------------------------------------- profile


def _require_password(accounts: AccountRepository, user_id: int, password: str) -> None:
    creds = accounts.get_credentials(user_id=user_id)
    if creds is None or not verify_password(password or "", creds.password_hash):
        raise InputValidationError("Your current password is incorrect.")


def update_profile(
    accounts: AccountRepository,
    user: User,
    *,
    email: str,
    display_name: str,
    current_password: str = "",
) -> User:
    """Change name and/or email. Changing the email requires the current password."""
    email = validate_email(email)
    display_name = validate_display_name(display_name)
    if email != user.email:
        _require_password(accounts, user.id, current_password)
    return accounts.update_profile(user.id, email=email, display_name=display_name)


def change_password(
    accounts: AccountRepository,
    user: User,
    *,
    current_password: str,
    new_password: str,
    confirm_password: str,
    keep_session_token: str | None = None,
) -> None:
    """Change the password and sign out every other remembered session."""
    _require_password(accounts, user.id, current_password)
    validate_new_password(new_password, email=user.email)
    if new_password != confirm_password:
        raise InputValidationError("The two new passwords do not match.")
    if new_password == current_password:
        raise InputValidationError("Choose a password different from your current one.")
    accounts.update_password(user.id, hash_password(new_password))
    accounts.delete_user_sessions(
        user.id, except_hash=hash_session_token(keep_session_token) if keep_session_token else None
    )


def delete_account(
    accounts: AccountRepository, user: User, *, password: str, confirmation: str
) -> None:
    """Permanently delete the account and, through cascades, all of its data."""
    if confirmation.strip() != DELETE_CONFIRMATION:
        raise InputValidationError(f'Type "{DELETE_CONFIRMATION}" to confirm.')
    _require_password(accounts, user.id, password)
    accounts.delete_user(user.id)
    logger.info("Account deleted (id=%d)", user.id)


# ---------------------------------------------------------- AI credentials


def load_secret_box(settings: Settings) -> SecretBox:
    """Encryption for saved API keys.

    Uses ``APP_SECRET_KEY`` when set. Otherwise a key is generated once and kept
    in a private file next to the database (git-ignored, permissions 0600).
    """
    if settings.app_secret_key is not None:
        return SecretBox(settings.app_secret_key.get_secret_value())
    key_file = Path(settings.database_path).parent / ".app_secret_key"
    if key_file.exists():
        return SecretBox(key_file.read_text().strip())
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key = SecretBox.generate_key()
    fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(key)
    logger.warning(
        "APP_SECRET_KEY is not set; generated an encryption key at %s. Back it up, or set "
        "APP_SECRET_KEY, or saved API keys cannot be decrypted after it is lost.",
        key_file.name,
    )
    return SecretBox(key)


def validate_api_key(api_key: object) -> str:
    if not isinstance(api_key, str) or not api_key.strip():
        raise InputValidationError("Please paste your OpenAI API key.")
    api_key = api_key.strip()
    if not _API_KEY.match(api_key):
        raise InputValidationError(
            "That does not look like an OpenAI API key. Keys usually start with “sk-”."
        )
    return api_key


def validate_model_name(model: object) -> str:
    if not isinstance(model, str) or not _MODEL_NAME.match(model.strip()):
        raise InputValidationError("Please choose a valid model name.")
    return model.strip()


def save_user_api_key(
    accounts: AccountRepository, box: SecretBox, user_id: int, api_key: str
) -> str:
    """Encrypt and store the user's key. Returns the display hint (e.g. ``…a1b2``)."""
    api_key = validate_api_key(api_key)
    hint = api_key_hint(api_key)
    accounts.save_api_key(user_id, encrypted_api_key=box.encrypt(api_key), key_hint=hint)
    return hint


@dataclass(frozen=True)
class AIConfig:
    """The credentials and model to use for one user's AI requests."""

    api_key: str | None
    model: str | None
    key_source: Literal["user", "server", "none"]
    model_source: Literal["user", "server", "none"]
    key_hint: str | None = None
    key_unreadable: bool = False

    @property
    def ready(self) -> bool:
        return bool(self.api_key and self.model)

    def __repr__(self) -> str:  # never include the key
        return (
            f"AIConfig(model={self.model!r}, key_source={self.key_source!r}, "
            f"model_source={self.model_source!r})"
        )


def resolve_ai_config(
    settings: Settings,
    accounts: AccountRepository,
    box: SecretBox,
    user_id: int,
    prefs: Preferences,
) -> AIConfig:
    """User settings win; the server's key/model are fallbacks.

    The server key is shared only when ``SHARE_SERVER_API_KEY`` is true.
    """
    api_key, key_source, hint, unreadable = None, "none", None, False
    stored = accounts.get_api_key(user_id)
    if stored is not None:
        api_key = box.decrypt(stored.encrypted_api_key)
        if api_key:
            key_source, hint = "user", stored.key_hint
        else:
            unreadable = True
            logger.warning("Saved API key for user %d could not be decrypted", user_id)
    if api_key is None and settings.openai_api_key and settings.share_server_api_key:
        api_key, key_source = settings.openai_api_key.get_secret_value(), "server"

    if prefs.openai_model:
        model, model_source = prefs.openai_model, "user"
    elif settings.openai_model:
        model, model_source = settings.openai_model, "server"
    else:
        model, model_source = None, "none"

    return AIConfig(
        api_key=api_key,
        model=model,
        key_source=key_source,  # type: ignore[arg-type]
        model_source=model_source,  # type: ignore[arg-type]
        key_hint=hint,
        key_unreadable=unreadable,
    )
