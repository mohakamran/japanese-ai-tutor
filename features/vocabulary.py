"""Vocabulary generation, saving, and flashcard review."""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Sequence

from core.constants import MAX_VOCABULARY_COUNT, MIN_VOCABULARY_COUNT
from core.errors import AIResponseError
from core.validation import validate_count, validate_level, validate_topic
from database.models import SavedWord
from database.repository import LearningRepository
from prompts.vocabulary import build_vocabulary_prompt
from schemas.vocabulary import VocabularyGenerationResponse, VocabularyItem
from services.llm_service import LLMService


def vocabulary_key(item: VocabularyItem | SavedWord) -> tuple[str, str, str]:
    """Identity of a vocabulary item, matching the database's unique constraint."""
    return (item.word, item.reading, item.meaning)


def _dedupe_key(item: VocabularyItem) -> tuple[str, str]:
    return (
        unicodedata.normalize("NFKC", item.word),
        unicodedata.normalize("NFKC", item.reading),
    )


def generate_vocabulary(
    llm: LLMService,
    *,
    topic: str,
    level: str,
    count: int,
    style: str = "balanced",
) -> list[VocabularyItem]:
    """Generate ``count`` validated, de-duplicated vocabulary items for a topic."""
    topic = validate_topic(topic)
    level = validate_level(level)
    count = validate_count(
        count, field="Number of words", minimum=MIN_VOCABULARY_COUNT, maximum=MAX_VOCABULARY_COUNT
    )
    prompt = build_vocabulary_prompt(topic=topic, level=level, count=count, style=style)
    response = llm.generate_structured(prompt, VocabularyGenerationResponse)

    items: list[VocabularyItem] = []
    seen: set[tuple[str, str]] = set()
    for item in response.items:
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    if not items:
        raise AIResponseError(detail="vocabulary response contained no items")
    return items[:count]


def save_vocabulary_item(
    repo: LearningRepository, item: VocabularyItem, *, topic: str, level: str
) -> bool:
    """Save an item for review. Returns False if it was already saved."""
    _, created = repo.save_vocabulary(item, topic=validate_topic(topic), level=level)
    if created:
        repo.log_activity("vocabulary_saved", f"Saved {item.word} ({item.meaning})")
    return created


def build_review_deck(
    words: Sequence[SavedWord], *, size: int = 20, rng: random.Random | None = None
) -> list[int]:
    """Choose vocabulary IDs for a flashcard session.

    Words never reviewed, or with the lowest recall rate, come first; ties are
    shuffled so the order varies between sessions.
    """
    rng = rng or random.Random()

    def priority(w: SavedWord) -> tuple[float, int, float]:
        recall = w.correct_count / w.review_count if w.review_count else -1.0
        return (recall, w.review_count, rng.random())

    return [w.vocabulary_id for w in sorted(words, key=priority)[:size]]


def record_review(repo: LearningRepository, vocabulary_id: int, *, remembered: bool) -> None:
    repo.record_vocabulary_review(vocabulary_id, remembered=remembered)
    repo.log_activity("vocabulary_reviewed", "Reviewed flashcards", coalesce_minutes=30)
