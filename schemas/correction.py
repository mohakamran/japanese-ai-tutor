"""Schemas for sentence correction."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.common import NonEmptyStr, OptionalStr, ResponseModel

Verdict = Literal["correct", "natural_but_improvable", "needs_correction", "ambiguous"]


class CorrectionIssue(ResponseModel):
    fragment: NonEmptyStr = Field(description="The part of the original sentence concerned.")
    suggestion: NonEmptyStr = Field(description="What to write instead.")
    explanation: NonEmptyStr = Field(description="Plain-English explanation.")
    severity: Literal["error", "unnatural", "stylistic"] = Field(
        description="'error' = ungrammatical; 'unnatural' = grammatical but odd; "
        "'stylistic' = optional improvement."
    )


class SentenceCorrectionResponse(ResponseModel):
    original_sentence: NonEmptyStr
    verdict: Verdict = Field(
        description="'correct' if no change is needed; 'ambiguous' if meaning is unclear "
        "without more context."
    )
    corrected_sentence: OptionalStr = Field(
        description="Corrected sentence if a correction is needed, otherwise null."
    )
    reading: NonEmptyStr = Field(
        description="Kana reading of the corrected sentence (or the original if correct)."
    )
    romaji: NonEmptyStr
    english_translation: NonEmptyStr
    grammar_issues: list[CorrectionIssue]
    word_choice_issues: list[CorrectionIssue]
    natural_alternative: OptionalStr = Field(
        description="A more natural way to say it, if one exists; otherwise null."
    )
    natural_alternative_romaji: OptionalStr
    assumptions: OptionalStr = Field(
        description="Assumptions made about the intended meaning or context, or null."
    )
    clarification_question: OptionalStr = Field(
        description="A question to ask the learner if the meaning is ambiguous, or null."
    )
    learning_tip: NonEmptyStr

    @model_validator(mode="after")
    def _consistent(self) -> SentenceCorrectionResponse:
        if self.verdict == "needs_correction" and not self.corrected_sentence:
            raise ValueError("needs_correction requires a corrected_sentence")
        if self.corrected_sentence == self.original_sentence:
            self.corrected_sentence = None
        return self

    @property
    def correction_needed(self) -> bool:
        return self.verdict == "needs_correction" or self.corrected_sentence is not None
