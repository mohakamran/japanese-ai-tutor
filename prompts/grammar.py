"""Prompt template for grammar explanations (with bounded follow-up history)."""

from __future__ import annotations

from typing import Any

from prompts.base import PromptSpec, build_instructions, wrap_learner_input

MAX_OUTPUT_TOKENS = 6000

TASK = """\
Answer the learner's grammar question as a structured mini-lesson.

Requirements:
- "explanation" directly answers the question in plain English first, then adds detail.
- "pattern" and "formation" show exactly how the grammar is built (e.g. "Verb (dictionary
  form) + ことができる").
- Give 3–5 examples that use the pattern naturally, each with reading, romaji, a natural
  English translation, and its register (formal / casual / neutral).
- "common_mistakes": 1–3 realistic mistakes English speakers make, with corrections.
- "formality_notes": explain formal vs. casual usage when relevant, otherwise null.
- "related_patterns": 0–4 closely related patterns worth comparing.
- If the question is ambiguous, unclear, or depends on context, explain that in
  "uncertainty_note" and answer the most likely interpretation.
- If this is a follow-up question, build on the earlier lesson instead of repeating it.
{topic_line}"""


def build_grammar_prompt(
    *,
    question: str,
    level: str,
    style: str,
    topic: str | None,
    history: list[dict[str, Any]],
) -> PromptSpec:
    """``history`` is a list of prior {"role", "content"} messages, already bounded."""
    topic_line = f"- The learner is studying this area: {topic}." if topic else ""
    messages = [
        *history,
        {"role": "user", "content": f"Grammar question:\n{wrap_learner_input(question)}"},
    ]
    return PromptSpec(
        task="grammar",
        instructions=build_instructions(
            task=TASK.format(topic_line=topic_line), level=level, style=style
        ),
        input=messages,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
