"""Prompt templates for conversation practice and sentence explanations."""

from __future__ import annotations

from typing import Any

from core.constants import CONVERSATION_SCENARIOS
from prompts.base import PromptSpec, build_instructions, wrap_learner_input

MAX_OUTPUT_TOKENS = 4000
EXPLAIN_MAX_OUTPUT_TOKENS = 4000

CONVERSATION_TASK = """\
Role-play a conversation partner so the learner can practise Japanese.

Scenario: {scenario}. Play the natural other person in this scenario (for example the
waiter, shop clerk, classmate or friend) and stay in character in "reply_japanese".

Requirements:
- Reply in Japanese suited to the learner's level: 1–3 short sentences, then usually a
  question or prompt that invites the learner to answer.
- Use the register a real person in this scenario would use (e.g. polite です/ます with a
  clerk, casual speech with a friend).
- Provide reading, romaji and a natural English translation of your reply.
- Encourage the learner to answer in Japanese. If they write in English, respond helpfully
  and show how to say it in Japanese in "suggested_response".
- "suggested_response": a short, level-appropriate Japanese line the learner could say next.
- "vocabulary_notes": up to 3 useful words from your reply.
- {feedback_rule}"""

FEEDBACK_ON = (
    'Feedback: check the learner\'s latest message. If it has mistakes, set "feedback" with '
    "has_mistakes=true, the corrected message, and a brief, encouraging explanation. If it is "
    "fine, set has_mistakes=false with null corrected_message and explanation. Do not "
    "treat casual but valid Japanese as a mistake."
)
FEEDBACK_OFF = 'Feedback: the learner turned corrections off. Always set "feedback" to null.'

OPENING_MESSAGE = (
    "(The learner has just started the conversation. Open the scenario with a natural "
    "first line and a simple question. Set feedback to null.)"
)

EXPLAIN_TASK = """\
Explain a Japanese sentence to the learner, piece by piece.

- Break the sentence into meaningful segments (words, particles, conjugated endings).
- For each segment give the reading, romaji, its grammatical role in plain English, and
  its meaning.
- List the key grammar points used.
- Describe the politeness/register of the sentence and why it is used here.
- Give a natural English translation."""


def build_conversation_prompt(
    *,
    scenario: str,
    level: str,
    style: str,
    corrections_enabled: bool,
    history: list[dict[str, Any]],
    learner_message: str | None,
) -> PromptSpec:
    """``history`` holds prior messages, already bounded by the caller."""
    task = CONVERSATION_TASK.format(
        scenario=CONVERSATION_SCENARIOS[scenario],
        feedback_rule=FEEDBACK_ON if corrections_enabled else FEEDBACK_OFF,
    )
    latest = wrap_learner_input(learner_message) if learner_message else OPENING_MESSAGE
    return PromptSpec(
        task="conversation",
        instructions=build_instructions(task=task, level=level, style=style),
        input=[*history, {"role": "user", "content": latest}],
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def build_sentence_explanation_prompt(*, sentence: str, level: str, style: str) -> PromptSpec:
    return PromptSpec(
        task="sentence_explanation",
        instructions=build_instructions(task=EXPLAIN_TASK, level=level, style=style),
        input=f"Sentence to explain:\n{wrap_learner_input(sentence)}",
        max_output_tokens=EXPLAIN_MAX_OUTPUT_TOKENS,
    )
