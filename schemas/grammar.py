"""Schemas for grammar lessons."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.common import NonEmptyStr, OptionalStr, ResponseModel


class GrammarExample(ResponseModel):
    japanese: NonEmptyStr
    reading: NonEmptyStr = Field(description="The sentence in kana.")
    romaji: NonEmptyStr
    english: NonEmptyStr = Field(description="Natural English translation.")
    speech_register: Literal["formal", "casual", "neutral"] = Field(
        description="Speech register of this example."
    )


class CommonMistake(ResponseModel):
    incorrect: NonEmptyStr = Field(description="A typical learner mistake in Japanese.")
    correct: NonEmptyStr = Field(description="The corrected Japanese.")
    explanation: NonEmptyStr = Field(description="Why it is wrong, in plain English.")


class GrammarLessonResponse(ResponseModel):
    title: NonEmptyStr = Field(description="Short lesson title, e.g. 'The particle は'.")
    pattern: NonEmptyStr = Field(description="The grammar pattern, e.g. 'Noun + は + ...'.")
    formation: NonEmptyStr = Field(
        description="How to form the pattern step by step, in English with Japanese parts."
    )
    explanation: NonEmptyStr = Field(
        description="Clear English explanation answering the learner's question."
    )
    examples: list[GrammarExample]
    usage_notes: list[NonEmptyStr]
    common_mistakes: list[CommonMistake]
    formality_notes: OptionalStr = Field(
        description="Formal vs. informal usage differences, or null if not relevant."
    )
    related_patterns: list[NonEmptyStr]
    uncertainty_note: OptionalStr = Field(
        description="If the question is ambiguous or the answer depends on context, explain "
        "that here; otherwise null."
    )

    @model_validator(mode="after")
    def _require_examples(self) -> GrammarLessonResponse:
        if not self.examples:
            raise ValueError("a grammar lesson needs at least one example")
        return self
