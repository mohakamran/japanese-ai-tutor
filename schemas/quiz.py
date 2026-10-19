"""Schemas for quizzes.

Every question — including translation and sentence-construction exercises — is
answered by choosing one option. That keeps scoring deterministic and computed in
Python rather than by the model.
"""

from __future__ import annotations

from pydantic import Field

from core.constants import QuestionType
from schemas.common import NonEmptyStr, OptionalStr, ResponseModel


class QuizQuestion(ResponseModel):
    question_type: QuestionType
    prompt: NonEmptyStr = Field(
        description="The instruction or question in English, e.g. 'Choose the correct translation.'"
    )
    japanese_text: OptionalStr = Field(
        description="Japanese text the question is about (use ＿＿ for a blank), or null."
    )
    reading: OptionalStr = Field(
        description="Kana reading of japanese_text, or null if it would reveal the answer."
    )
    romaji: OptionalStr = Field(
        description="Romaji of japanese_text, or null if it would reveal the answer."
    )
    options: list[NonEmptyStr] = Field(
        description="Answer choices: exactly one correct, the rest plausible but clearly wrong."
    )
    correct_option_index: int = Field(description="Zero-based index of the correct option.")
    explanation: NonEmptyStr = Field(
        description="Why the correct answer is right and why the distractors are wrong."
    )


class QuizGenerationResponse(ResponseModel):
    questions: list[QuizQuestion]


class AnswerExplanationResponse(ResponseModel):
    """A deeper explanation of a question the learner got wrong."""

    why_correct: NonEmptyStr = Field(description="Why the correct answer is right.")
    why_learner_answer_is_wrong: NonEmptyStr = Field(
        description="What is wrong with the learner's choice, or what it would actually mean."
    )
    extra_example_japanese: NonEmptyStr
    extra_example_romaji: NonEmptyStr
    extra_example_english: NonEmptyStr
    tip: NonEmptyStr = Field(description="One short tip to remember the point.")
