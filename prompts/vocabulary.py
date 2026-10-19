"""Prompt template for vocabulary generation."""

from __future__ import annotations

from prompts.base import PromptSpec, build_instructions, wrap_learner_input

MAX_OUTPUT_TOKENS = 6000

TASK = """\
Generate a list of useful Japanese vocabulary for the topic the learner chooses.

Requirements:
- Return exactly {count} distinct words, appropriate for the learner's level.
- Prefer high-frequency, practical words. No duplicates or near-duplicates.
- "word" is the standard written form (kanji if commonly written with kanji, otherwise kana).
- "reading" is the full reading in hiragana (katakana for loanwords).
- "meaning" gives the most common meaning first. If a word has an important
  context-specific meaning, mention it in "usage_note".
- Each example sentence must be short, natural, and use the word in its common sense.
- Romaji uses Hepburn romanization.
- Mark the correct part of speech; use "other" only if nothing else fits."""


def build_vocabulary_prompt(*, topic: str, level: str, count: int, style: str) -> PromptSpec:
    return PromptSpec(
        task="vocabulary",
        instructions=build_instructions(task=TASK.format(count=count), level=level, style=style),
        input=f"Topic for the vocabulary list:\n{wrap_learner_input(topic)}",
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
