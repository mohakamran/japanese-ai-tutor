"""Schemas for vocabulary generation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from schemas.common import NonEmptyStr, OptionalStr, ResponseModel

PartOfSpeech = Literal[
    "noun",
    "verb",
    "i-adjective",
    "na-adjective",
    "adverb",
    "particle",
    "pronoun",
    "counter",
    "conjunction",
    "expression",
    "other",
]


class VocabularyItem(ResponseModel):
    word: NonEmptyStr = Field(
        description="The word as normally written in Japanese (kanji where standard, "
        "otherwise kana)."
    )
    reading: NonEmptyStr = Field(description="Full reading in hiragana (katakana for loanwords).")
    romaji: NonEmptyStr = Field(description="Hepburn romaji of the reading.")
    meaning: NonEmptyStr = Field(description="Most common English meaning(s), concise.")
    part_of_speech: PartOfSpeech
    example_sentence: NonEmptyStr = Field(
        description="A short, natural Japanese sentence using the word."
    )
    example_reading: NonEmptyStr = Field(description="The example sentence written in kana.")
    example_romaji: NonEmptyStr = Field(description="Hepburn romaji of the example sentence.")
    example_translation: NonEmptyStr = Field(description="Natural English translation.")
    usage_note: OptionalStr = Field(
        description="Optional short note on nuance, formality, or context-specific meanings; "
        "null if not needed."
    )


class VocabularyGenerationResponse(ResponseModel):
    items: list[VocabularyItem]
