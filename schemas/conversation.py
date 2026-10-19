"""Schemas for conversation practice."""

from __future__ import annotations

from pydantic import Field

from schemas.common import NonEmptyStr, OptionalStr, ResponseModel


class LearnerFeedback(ResponseModel):
    has_mistakes: bool
    corrected_message: OptionalStr = Field(
        description="The learner's message corrected, or null if it was fine."
    )
    explanation: OptionalStr = Field(
        description="Brief, encouraging English explanation of the correction, or null."
    )


class VocabularyNote(ResponseModel):
    japanese: NonEmptyStr
    reading: NonEmptyStr
    english: NonEmptyStr


class ConversationResponse(ResponseModel):
    reply_japanese: NonEmptyStr = Field(description="The tutor's in-character reply in Japanese.")
    reply_reading: NonEmptyStr = Field(description="The reply written in kana.")
    reply_romaji: NonEmptyStr
    reply_english: NonEmptyStr = Field(description="Natural English translation of the reply.")
    feedback: LearnerFeedback | None = Field(
        description="Feedback on the learner's last message; null when corrections are "
        "disabled or there is no learner message yet."
    )
    suggested_response: OptionalStr = Field(
        description="A simple Japanese phrase the learner could say next, or null."
    )
    vocabulary_notes: list[VocabularyNote] = Field(
        description="Up to 3 useful words from the reply."
    )


class SentenceSegment(ResponseModel):
    japanese: NonEmptyStr
    reading: NonEmptyStr
    romaji: NonEmptyStr
    role: NonEmptyStr = Field(description="Grammatical role, e.g. 'topic particle', 'verb'.")
    meaning: NonEmptyStr


class SentenceExplanationResponse(ResponseModel):
    sentence: NonEmptyStr
    translation: NonEmptyStr
    segments: list[SentenceSegment]
    grammar_points: list[NonEmptyStr]
    politeness: NonEmptyStr = Field(description="Register of the sentence and why.")
