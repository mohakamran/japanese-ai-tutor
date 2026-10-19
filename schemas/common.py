"""Reusable field types for the response schemas."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def _strip_non_empty(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


NonEmptyStr = Annotated[str, AfterValidator(_strip_non_empty)]
OptionalStr = Annotated[str | None, AfterValidator(_strip_optional)]


class ResponseModel(BaseModel):
    """Base for AI response models: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")
