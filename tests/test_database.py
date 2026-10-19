"""Repository CRUD, deduplication, transactions, and migrations."""

from __future__ import annotations

import sqlite3

import pytest

from core.errors import DatabaseError, InputValidationError
from database.initialization import LATEST_SCHEMA_VERSION, initialize_database
from database.models import NewQuizAttempt, Preferences
from database.repository import AccountRepository, LearningRepository, initialize
from tests.conftest import grammar_lesson, make_user, vocab_item


def test_initialization_is_idempotent_and_preserves_data(tmp_path) -> None:
    path = tmp_path / "nested" / "db.sqlite"
    initialize(path)  # creates missing parent folder
    user = make_user(AccountRepository(path))
    LearningRepository(path, user.id).save_vocabulary(vocab_item(), topic="Food", level="beginner")
    assert initialize_database(path) == LATEST_SCHEMA_VERSION
    assert LearningRepository(path, user.id).get_stats().saved_words == 1


def test_default_preferences_then_update(repo) -> None:
    prefs = repo.get_preferences()
    assert prefs.proficiency_level == "beginner" and prefs.romaji_enabled
    updated = repo.save_preferences(
        Preferences(
            proficiency_level="intermediate",
            romaji_enabled=False,
            explanation_style="detailed",
            preferred_difficulty="hard",
            conversation_corrections=False,
        )
    )
    assert updated.proficiency_level == "intermediate"
    assert not updated.romaji_enabled and not updated.conversation_corrections
    assert repo.get_preferences() == updated


def test_invalid_preferences_rejected(repo) -> None:
    with pytest.raises(InputValidationError):
        repo.save_preferences(Preferences("guru", True, "balanced", "medium", True))


def test_save_vocabulary_prevents_duplicates(repo) -> None:
    item = vocab_item()
    vid1, created1 = repo.save_vocabulary(item, topic="Food", level="beginner")
    vid2, created2 = repo.save_vocabulary(item, topic="Food", level="beginner")
    assert vid1 == vid2 and created1 and not created2
    assert len(repo.list_saved_vocabulary()) == 1
    assert repo.saved_vocabulary_keys() == {("食べる", "たべる", "to eat")}


def test_unvalidated_vocabulary_rejected(repo) -> None:
    with pytest.raises(InputValidationError):
        repo.save_vocabulary({"word": "x"}, topic="Food", level="beginner")  # type: ignore[arg-type]
    assert repo.get_stats().saved_words == 0


def test_review_updates_counts_and_history(repo) -> None:
    vid, _ = repo.save_vocabulary(vocab_item(), topic="Food", level="beginner")
    repo.record_vocabulary_review(vid, remembered=True)
    repo.record_vocabulary_review(vid, remembered=False)
    word = repo.list_saved_vocabulary()[0]
    assert (word.review_count, word.correct_count) == (2, 1)
    assert word.last_reviewed_at is not None
    assert repo.get_stats().vocabulary_reviews == 2
    assert sum(n for _, n in repo.activity_counts_by_day()) == 2


def test_review_of_missing_word_rolls_back(repo) -> None:
    with pytest.raises(InputValidationError):
        repo.record_vocabulary_review(999, remembered=True)
    assert repo.get_stats().vocabulary_reviews == 0


def test_delete_vocabulary_cascades(repo) -> None:
    vid, _ = repo.save_vocabulary(vocab_item(), topic="Food", level="beginner")
    repo.record_vocabulary_review(vid, remembered=True)
    assert repo.delete_saved_vocabulary([vid]) == 1
    stats = repo.get_stats()
    assert stats.saved_words == 0 and stats.vocabulary_reviews == 0


def test_grammar_lesson_save_list_delete(repo) -> None:
    lesson = grammar_lesson()
    lid, created = repo.save_grammar_lesson(question="What is は?", level="beginner", lesson=lesson)
    _, again = repo.save_grammar_lesson(question="What is は?", level="beginner", lesson=lesson)
    assert created and not again
    records = repo.list_grammar_lessons()
    assert len(records) == 1 and records[0].title == lesson.title
    assert repo.delete_grammar_lesson(lid)
    assert repo.list_grammar_lessons() == []


def test_quiz_attempt_rejects_impossible_score(repo) -> None:
    with pytest.raises(InputValidationError):
        repo.save_quiz_attempt(
            NewQuizAttempt("q1", "Food", "mixed", "beginner", "easy", 3, 5, 100.0)
        )


def test_quiz_attempt_ordering_and_stats(repo) -> None:
    repo.save_quiz_attempt(NewQuizAttempt("a", "Food", "mixed", "beginner", "easy", 4, 2, 50.0))
    repo.save_quiz_attempt(NewQuizAttempt("b", "Family", "mixed", "beginner", "easy", 4, 4, 100.0))
    attempts = repo.list_quiz_attempts()
    assert [a.client_quiz_id for a in attempts] == ["b", "a"]
    assert repo.get_stats().average_score == 75.0


def test_activity_log_and_coalescing(repo) -> None:
    assert repo.log_activity("vocabulary_reviewed", "Reviewed", coalesce_minutes=30)
    assert not repo.log_activity("vocabulary_reviewed", "Reviewed", coalesce_minutes=30)
    assert repo.log_activity("grammar_viewed", "Grammar: は")
    assert [a.activity_type for a in repo.list_recent_activity()] == [
        "grammar_viewed",
        "vocabulary_reviewed",
    ]
    with pytest.raises(InputValidationError):
        repo.log_activity("hacked", "x")


@pytest.mark.parametrize("scope", ["quizzes", "vocabulary", "grammar", "activity", "all"])
def test_clear_learning_history(repo, scope) -> None:
    repo.save_vocabulary(vocab_item(), topic="Food", level="beginner")
    repo.save_grammar_lesson(question="q", level="beginner", lesson=grammar_lesson())
    repo.save_quiz_attempt(NewQuizAttempt("a", "Food", "mixed", "beginner", "easy", 1, 1, 100.0))
    repo.log_activity("grammar_viewed", "x")
    repo.clear_learning_history(scope)
    s = repo.get_stats()
    assert (s.quizzes_completed == 0) == (scope in {"quizzes", "all"})
    assert (s.saved_words == 0) == (scope in {"vocabulary", "all"})
    assert (s.grammar_lessons_saved == 0) == (scope in {"grammar", "all"})
    assert (s.grammar_lessons_viewed == 0) == (scope in {"activity", "all"})


def test_clear_rejects_unknown_scope(repo) -> None:
    with pytest.raises(InputValidationError):
        repo.clear_learning_history("users; DROP TABLE vocabulary")


def test_sqlite_errors_become_database_error(repo) -> None:
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute("DROP TABLE activity_log")
    with pytest.raises(DatabaseError) as info:
        repo.list_recent_activity()
    assert "sqlite" not in info.value.user_message.lower()
    assert "activity_log" not in info.value.user_message


def test_unopenable_database_gives_friendly_error(tmp_path) -> None:
    (tmp_path / "dir.db").mkdir()  # a directory cannot be opened as a database
    with pytest.raises(DatabaseError, match="could not be opened"):
        initialize(tmp_path / "dir.db")
