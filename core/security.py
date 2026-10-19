"""Password hashing, account input rules, and secret encryption.

* Passwords are hashed with scrypt (memory-hard, from the standard library)
  using a random 16-byte salt per password. Hashes are self-describing, so the
  cost parameters can be raised later without breaking existing accounts.
* API keys that learners save are encrypted with Fernet (AES-128-CBC + HMAC)
  before they reach the database.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

from cryptography.fernet import Fernet, InvalidToken

from core.errors import InputValidationError

# scrypt cost parameters (≈16 MB memory, tens of ms per hash).
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 254
MAX_DISPLAY_NAME_LENGTH = 40

_EMAIL = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[A-Za-z]{2,}$")


# ------------------------------------------------------------------ passwords


def hash_password(password: str) -> str:
    """Return a self-describing scrypt hash: ``scrypt$n$r$p$salt$hash``."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DKLEN
    )
    return "$".join(
        [
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        ]
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of ``password`` against a stored hash."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Used to keep login timing similar whether or not an account exists.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


# --------------------------------------------------------------- validation


def validate_email(email: object) -> str:
    if not isinstance(email, str):
        raise InputValidationError("Please enter your email address.")
    email = email.strip().lower()
    if not email:
        raise InputValidationError("Please enter your email address.")
    if len(email) > MAX_EMAIL_LENGTH or not _EMAIL.match(email):
        raise InputValidationError("Please enter a valid email address.")
    return email


def validate_display_name(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        raise InputValidationError("Please enter a display name.")
    name = " ".join(name.split())
    if len(name) > MAX_DISPLAY_NAME_LENGTH:
        raise InputValidationError(
            f"Display names can be at most {MAX_DISPLAY_NAME_LENGTH} characters."
        )
    if any(ch in name for ch in "<>"):
        raise InputValidationError("Display names cannot contain < or >.")
    return name


def validate_new_password(password: object, *, email: str | None = None) -> str:
    """Enforce a reasonable password policy (length + letters and digits)."""
    if not isinstance(password, str) or not password:
        raise InputValidationError("Please choose a password.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InputValidationError(
            f"Passwords must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise InputValidationError(
            f"Passwords can be at most {MAX_PASSWORD_LENGTH} characters long."
        )
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise InputValidationError("Passwords must contain at least one letter and one number.")
    if email and password.lower() == email.lower():
        raise InputValidationError("Your password must be different from your email address.")
    return password


# --------------------------------------------------------------- encryption


class SecretBox:
    """Encrypts and decrypts small secrets (API keys) for storage."""

    def __init__(self, key: str | bytes) -> None:
        try:
            self._fernet = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise ValueError("APP_SECRET_KEY must be a valid Fernet key") from exc

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str | None:
        """Return the plaintext, or None if the token cannot be decrypted
        (for example after the encryption key was changed)."""
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            return None


# ----------------------------------------------------------------- sessions


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Session tokens are stored hashed, so a leaked database cannot be replayed."""
    return hashlib.sha256(token.encode()).hexdigest()


def api_key_hint(api_key: str) -> str:
    """A non-sensitive hint such as ``…a1b2`` for showing which key is saved."""
    return "…" + api_key[-4:] if len(api_key) >= 12 else "…"
