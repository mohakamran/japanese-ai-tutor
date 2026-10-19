"""Grammar explanations with a bounded follow-up history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from core.constants import GRAMMAR_TOPICS, MAX_GRAMMAR_HISTORY_TURNS, MAX_GRAMMAR_QUESTION_LENGTH
from core.validation import clean_text, validate_choice, validate_level
from database.repository import LearningRepository
from prompts.base import wrap_learner_input
from prompts.grammar import build_grammar_prompt
from schemas.grammar import GrammarLessonResponse
from services.llm_service import LLMService

# How much of an earlier lesson is sent back as context for a follow-up.
_SUMMARY_CHARS = 700


@dataclass(frozen=True)
class GrammarTurn:
    question: str
    level: str
    lesson: GrammarLessonResponse


def summarize_lesson(lesson: GrammarLessonResponse) -> str:
    """A compact version of a lesson, used as context instead of the full JSON."""
    explanation = lesson.explanation
    if len(explanation) > _SUMMARY_CHARS:
        explanation = explanation[:_SUMMARY_CHARS].rsplit(" ", 1)[0] + " …"
    examples = "; ".join(f"{e.japanese} ({e.english})" for e in lesson.examples[:2])
    return (
        f"Lesson: {lesson.title}\nPattern: {lesson.pattern}\n"
        f"Explanation: {explanation}\nExamples: {examples}"
    )


def build_history_messages(
    history: Sequence[GrammarTurn], *, max_turns: int = MAX_GRAMMAR_HISTORY_TURNS
) -> list[dict[str, Any]]:
    """Convert the last ``max_turns`` turns into chat messages for the model."""
    messages: list[dict[str, Any]] = []
    for turn in list(history)[-max_turns:] if max_turns > 0 else []:
        messages.append(
            {"role": "user", "content": f"Grammar question:\n{wrap_learner_input(turn.question)}"}
        )
        messages.append({"role": "assistant", "content": summarize_lesson(turn.lesson)})
    return messages


def explain_grammar(
    llm: LLMService,
    *,
    question: str,
    level: str,
    history: Sequence[GrammarTurn] = (),
    topic: str | None = None,
    style: str = "balanced",
) -> GrammarLessonResponse:
    """Answer a grammar question (or follow-up) as a validated structured lesson."""
    question = clean_text(
        question, field="A grammar question", max_length=MAX_GRAMMAR_QUESTION_LENGTH
    )
    level = validate_level(level)
    if topic:
        topic = validate_choice(topic, GRAMMAR_TOPICS, field="Grammar topic")
    prompt = build_grammar_prompt(
        question=question,
        level=level,
        style=style,
        topic=topic,
        history=build_history_messages(history),
    )
    return llm.generate_structured(prompt, GrammarLessonResponse)


def append_turn(
    history: Sequence[GrammarTurn], turn: GrammarTurn, *, keep: int = 10
) -> list[GrammarTurn]:
    """Add a turn, keeping at most ``keep`` turns for display."""
    return [*history, turn][-keep:]


def save_grammar_lesson(repo: LearningRepository, turn: GrammarTurn) -> bool:
    """Save a lesson for later review. Returns False if already saved."""
    _, created = repo.save_grammar_lesson(
        question=turn.question, level=turn.level, lesson=turn.lesson
    )
    if created:
        repo.log_activity("grammar_saved", f"Saved lesson: {turn.lesson.title}")
    return created


def load_saved_lesson(lesson_json: str) -> GrammarLessonResponse:
    """Re-validate a stored lesson before displaying it."""
    return GrammarLessonResponse.model_validate_json(lesson_json)
