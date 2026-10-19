"""Input validation helpers.

All learner input passes through these functions before it reaches a prompt or
the database. They raise :class:`InputValidationError` with a friendly message.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from core.constants import (
    DIFFICULTIES,
    EXPLANATION_STYLES,
    LEVELS,
    MAX_TOPIC_LENGTH,
)
from core.errors import InputValidationError

# C0/C1 control characters except tab and newline.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_EXCESS_NEWLINES = re.compile(r"\n{3,}")


def clean_text(
    value: object,
    *,
    field: str,
    max_length: int,
    required: bool = True,
) -> str:
    """Strip control characters and whitespace, then enforce length limits.

    Returns an empty string for an empty optional field.
    """
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise InputValidationError(f"{field} must be text.")
    text = _CONTROL_CHARS.sub("", value).replace("\r\n", "\n").replace("\r", "\n")
    text = _EXCESS_NEWLINES.sub("\n\n", text).strip()
    if required and not text:
        raise InputValidationError(f"Please enter {field.lower()}.")
    if len(text) > max_length:
        raise InputValidationError(
            f"{field} is too long ({len(text)} characters). The limit is {max_length}."
        )
    return text


def validate_choice(value: object, allowed: Iterable[str], *, field: str) -> str:
    """Ensure ``value`` is one of the allowed keys."""
    allowed_values = list(allowed)
    if not isinstance(value, str) or value not in allowed_values:
        raise InputValidationError(f"Please choose a valid {field.lower()}.")
    return value


def validate_level(level: object) -> str:
    return validate_choice(level, LEVELS, field="Proficiency level")


def validate_difficulty(difficulty: object) -> str:
    return validate_choice(difficulty, DIFFICULTIES, field="Difficulty")


def validate_explanation_style(style: object) -> str:
    return validate_choice(style, EXPLANATION_STYLES, field="Explanation style")


def validate_count(value: object, *, field: str, minimum: int, maximum: int) -> int:
    """Ensure ``value`` is an integer within ``[minimum, maximum]``."""
    # bool is a subclass of int; reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputValidationError(f"{field} must be a whole number.")
    if not minimum <= value <= maximum:
        raise InputValidationError(f"{field} must be between {minimum} and {maximum}.")
    return value


def validate_topic(topic: object) -> str:
    """Topics may be chosen from a list or typed freely, so only clean and bound them."""
    text = clean_text(topic, field="A topic", max_length=MAX_TOPIC_LENGTH)
    return " ".join(text.split())


def contains_japanese(text: str) -> bool:
    """True if ``text`` contains hiragana, katakana, or CJK ideographs."""
    return bool(re.search(r"[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]", text))
