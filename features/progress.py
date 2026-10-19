"""Progress summaries and next-activity recommendations, computed from stored data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from database.models import ActivityRecord, LearningStats, QuizAttemptRecord, SavedWord
from database.repository import LearningRepository

PageKey = Literal["vocabulary", "grammar", "quiz", "correction", "conversation"]


@dataclass(frozen=True)
class Recommendation:
    page: PageKey
    title: str
    reason: str


@dataclass(frozen=True)
class ProgressSummary:
    stats: LearningStats
    recent_attempts: list[QuizAttemptRecord]  # most recent first
    recent_activity: list[ActivityRecord]

    @property
    def is_empty(self) -> bool:
        s = self.stats
        return not (
            s.saved_words
            or s.quizzes_completed
            or s.grammar_lessons_viewed
            or s.sentences_checked
            or s.conversations_started
            or self.recent_activity
        )


def load_progress(repo: LearningRepository, *, attempts: int = 10) -> ProgressSummary:
    return ProgressSummary(
        stats=repo.get_stats(),
        recent_attempts=repo.list_quiz_attempts(limit=attempts),
        recent_activity=repo.list_recent_activity(limit=8),
    )


def recommend_next_activity(summary: ProgressSummary) -> Recommendation:
    """Simple, transparent rules — no AI call — so the suggestion is explainable."""
    s = summary.stats
    if s.saved_words == 0:
        return Recommendation(
            "vocabulary",
            "Build your first word list",
            "Generate vocabulary on a topic you care about and save the words you want to learn.",
        )
    if s.grammar_lessons_viewed == 0:
        return Recommendation(
            "grammar",
            "Ask your first grammar question",
            "Try something like “What is the difference between は and が?”",
        )
    if s.quizzes_completed == 0:
        return Recommendation(
            "quiz",
            "Take your first quiz",
            "A short quiz shows what you already know and what to review next.",
        )
    last = summary.recent_attempts[0] if summary.recent_attempts else None
    if last is not None and last.score < 70:
        return Recommendation(
            "quiz",
            f"Review “{last.topic}”",
            f"Your last quiz score was {last.score:g}%. Review the incorrect answers, then try "
            "another quiz on the same topic.",
        )
    if s.vocabulary_reviews < s.saved_words:
        return Recommendation(
            "vocabulary",
            "Review your flashcards",
            f"You have {s.saved_words} saved words. Regular review helps them stick.",
        )
    if s.conversations_started == 0:
        return Recommendation(
            "conversation",
            "Practise a conversation",
            "Use what you have learned in a role-play, such as ordering at a restaurant.",
        )
    return Recommendation(
        "correction",
        "Write your own sentences",
        "Write a few sentences with new words and get feedback in Sentence Correction.",
    )


def study_streak(active_days: list[str], *, today: date | None = None) -> int:
    """Consecutive days with activity, ending today (or yesterday, so a streak is not
    lost before today's session). ``active_days`` holds ``YYYY-MM-DD`` strings."""
    today = today or datetime.now(UTC).date()
    days = {date.fromisoformat(d) for d in active_days}
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def word_of_the_day(words: list[SavedWord], *, today: date | None = None) -> SavedWord | None:
    """Pick one saved word per day, deterministically, so it stays the same all day."""
    if not words:
        return None
    today = today or datetime.now(UTC).date()
    ordered = sorted(words, key=lambda w: w.vocabulary_id)
    return ordered[today.toordinal() % len(ordered)]
