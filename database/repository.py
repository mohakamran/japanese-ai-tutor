"""Data access layer.

All SQL lives here and every query is parameterized. The rest of the
application calls repository methods and receives dataclasses from
:mod:`database.models`, so the storage engine can be swapped (e.g. for
PostgreSQL) without touching the UI or business logic.

* :class:`AccountRepository` manages users, login sessions and saved API keys.
* :class:`LearningRepository` is **scoped to one user**: every query filters on
  that user's id, so one learner can never read or change another's data.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Literal, ParamSpec, TypeVar

from core.constants import (
    DEFAULT_DIFFICULTY,
    DEFAULT_EXPLANATION_STYLE,
    DEFAULT_LEVEL,
)
from core.errors import DatabaseError, InputValidationError
from core.validation import (
    validate_difficulty,
    validate_explanation_style,
    validate_level,
)
from database.connection import connect
from database.initialization import initialize_database
from database.models import (
    ActivityRecord,
    GrammarLessonRecord,
    LearningStats,
    NewQuizAttempt,
    Preferences,
    QuizAttemptRecord,
    QuizResponseRecord,
    SavedWord,
    StoredApiKey,
    User,
    UserCredentials,
)
from schemas.grammar import GrammarLessonResponse
from schemas.vocabulary import VocabularyItem

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

ActivityType = Literal[
    "vocabulary_generated",
    "vocabulary_saved",
    "vocabulary_reviewed",
    "grammar_viewed",
    "grammar_saved",
    "quiz_completed",
    "sentence_checked",
    "conversation_started",
]
ACTIVITY_TYPES: frozenset[str] = frozenset(ActivityType.__args__)  # type: ignore[attr-defined]

ClearScope = Literal["quizzes", "vocabulary", "grammar", "activity", "all"]
CLEAR_SCOPES: dict[str, str] = {
    "quizzes": "Quiz history",
    "vocabulary": "Saved vocabulary and review history",
    "grammar": "Saved grammar lessons",
    "activity": "Activity log",
    "all": "All learning history (your account stays)",
}

_TS = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    """Current UTC time as an ISO-8601 string, e.g. ``2026-01-31T09:15:00Z``."""
    return datetime.now(UTC).strftime(_TS)


def utc_in(**delta: float) -> str:
    return (datetime.now(UTC) + timedelta(**delta)).strftime(_TS)


def _db_errors(func: Callable[P, R]) -> Callable[P, R]:
    """Convert sqlite3 errors into :class:`DatabaseError` (logged, never shown raw)."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as exc:
            logger.error("Database error in %s: %s", func.__name__, type(exc).__name__)
            raise DatabaseError(detail=f"{func.__name__}: {type(exc).__name__}") from exc

    return wrapper


def initialize(db_path: Path) -> None:
    """Create or migrate the database, converting failures to a friendly error."""
    try:
        initialize_database(Path(db_path))
    except sqlite3.Error as exc:
        logger.error("Could not initialize database: %s", type(exc).__name__)
        raise DatabaseError(
            "The learning database could not be opened. Check DATABASE_PATH and file permissions."
        ) from exc


def _user_from_row(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        created_at=row["created_at"],
        last_login_at=row["last_login_at"],
    )


# ============================================================== accounts


class AccountRepository:
    """Users, login sessions, and encrypted API keys."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    @_db_errors
    def count_users(self) -> int:
        with connect(self.db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    @_db_errors
    def create_user(self, *, email: str, display_name: str, password_hash: str) -> User:
        now = utc_now()
        with connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (email, display_name, password_hash, created_at, "
                    "updated_at) VALUES (?, ?, ?, ?, ?)",
                    (email, display_name, password_hash, now, now),
                )
            except sqlite3.IntegrityError:
                raise InputValidationError(
                    "An account with this email already exists. Try logging in instead."
                ) from None
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _user_from_row(row)

    @_db_errors
    def get_user(self, user_id: int) -> User | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
        return _user_from_row(row) if row else None

    @_db_errors
    def get_credentials(
        self, *, email: str | None = None, user_id: int | None = None
    ) -> UserCredentials | None:
        with connect(self.db_path) as conn:
            if email is not None:
                row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return UserCredentials(
            user=_user_from_row(row),
            password_hash=row["password_hash"],
            failed_logins=row["failed_logins"],
            locked_until=row["locked_until"],
        )

    @_db_errors
    def record_login_success(self, user_id: int) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET failed_logins = 0, locked_until = NULL, last_login_at = ? "
                "WHERE id = ?",
                (utc_now(), user_id),
            )

    @_db_errors
    def record_login_failure(self, user_id: int, *, lock_after: int, lock_minutes: int) -> bool:
        """Count a failed login; lock the account after ``lock_after`` failures.
        Returns True if the account is now locked."""
        with connect(self.db_path) as conn:
            failures = conn.execute(
                "UPDATE users SET failed_logins = failed_logins + 1 WHERE id = ? "
                "RETURNING failed_logins",
                (user_id,),
            ).fetchone()[0]
            if failures >= lock_after:
                conn.execute(
                    "UPDATE users SET locked_until = ?, failed_logins = 0 WHERE id = ?",
                    (utc_in(minutes=lock_minutes), user_id),
                )
                return True
        return False

    @_db_errors
    def update_profile(self, user_id: int, *, email: str, display_name: str) -> User:
        with connect(self.db_path) as conn:
            try:
                conn.execute(
                    "UPDATE users SET email = ?, display_name = ?, updated_at = ? WHERE id = ?",
                    (email, display_name, utc_now(), user_id),
                )
            except sqlite3.IntegrityError:
                raise InputValidationError("Another account already uses this email.") from None
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_from_row(row)

    @_db_errors
    def update_password(self, user_id: int, password_hash: str) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, utc_now(), user_id),
            )

    @_db_errors
    def delete_user(self, user_id: int) -> bool:
        """Delete the account; foreign keys cascade to all of the user's data."""
        with connect(self.db_path) as conn:
            return conn.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount == 1

    @_db_errors
    def claim_unowned_data(self, user_id: int) -> None:
        """Assign data created before accounts existed to this (first) user."""
        with connect(self.db_path) as conn:
            for statement in (
                "UPDATE vocabulary SET user_id = ? WHERE user_id IS NULL",
                "UPDATE grammar_lessons SET user_id = ? WHERE user_id IS NULL",
                "UPDATE quiz_attempts SET user_id = ? WHERE user_id IS NULL",
                "UPDATE activity_log SET user_id = ? WHERE user_id IS NULL",
            ):
                conn.execute(statement, (user_id,))
            conn.execute(
                "UPDATE learner_preferences SET user_id = ? WHERE user_id IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM learner_preferences WHERE user_id = ?)",
                (user_id, user_id),
            )

    # ------------------------------------------------------------ sessions

    @_db_errors
    def create_session(self, user_id: int, token_hash: str, *, days: int) -> None:
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (utc_now(),))
            conn.execute(
                "INSERT INTO user_sessions (token_hash, user_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token_hash, user_id, utc_now(), utc_in(days=days)),
            )

    @_db_errors
    def get_session_user(self, token_hash: str) -> User | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT u.* FROM user_sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ? AND s.expires_at > ?",
                (token_hash, utc_now()),
            ).fetchone()
        return _user_from_row(row) if row else None

    @_db_errors
    def delete_session(self, token_hash: str) -> None:
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))

    @_db_errors
    def delete_user_sessions(self, user_id: int, *, except_hash: str | None = None) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM user_sessions WHERE user_id = ? AND token_hash != ?",
                (user_id, except_hash or ""),
            )

    # ------------------------------------------------------------ API keys

    @_db_errors
    def save_api_key(self, user_id: int, *, encrypted_api_key: str, key_hint: str) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_api_credentials (user_id, encrypted_api_key, key_hint, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET
                    encrypted_api_key = excluded.encrypted_api_key,
                    key_hint = excluded.key_hint,
                    updated_at = excluded.updated_at
                """,
                (user_id, encrypted_api_key, key_hint, utc_now()),
            )

    @_db_errors
    def get_api_key(self, user_id: int) -> StoredApiKey | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT encrypted_api_key, key_hint, updated_at FROM user_api_credentials "
                "WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return StoredApiKey(**dict(row)) if row else None

    @_db_errors
    def delete_api_key(self, user_id: int) -> None:
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_api_credentials WHERE user_id = ?", (user_id,))


# ============================================================== learning


class LearningRepository:
    """Learning records for **one** user. Every query is filtered by ``user_id``."""

    def __init__(self, db_path: Path, user_id: int) -> None:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise InputValidationError("A valid user is required.")
        self.db_path = Path(db_path)
        self.user_id = user_id

    # ------------------------------------------------------------ preferences

    @_db_errors
    def get_preferences(self) -> Preferences:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM learner_preferences WHERE user_id = ?", (self.user_id,)
            ).fetchone()
        if row is None:
            return Preferences(
                proficiency_level=DEFAULT_LEVEL,
                romaji_enabled=True,
                explanation_style=DEFAULT_EXPLANATION_STYLE,
                preferred_difficulty=DEFAULT_DIFFICULTY,
                conversation_corrections=True,
            )
        return Preferences(
            proficiency_level=row["proficiency_level"],
            romaji_enabled=bool(row["romaji_enabled"]),
            explanation_style=row["explanation_style"],
            preferred_difficulty=row["preferred_difficulty"],
            conversation_corrections=bool(row["conversation_corrections"]),
            updated_at=row["updated_at"],
            openai_model=row["openai_model"],
        )

    @_db_errors
    def save_preferences(self, prefs: Preferences) -> Preferences:
        validate_level(prefs.proficiency_level)
        validate_explanation_style(prefs.explanation_style)
        validate_difficulty(prefs.preferred_difficulty)
        now = utc_now()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO learner_preferences (
                    user_id, proficiency_level, romaji_enabled, explanation_style,
                    preferred_difficulty, conversation_corrections, openai_model,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET
                    proficiency_level = excluded.proficiency_level,
                    romaji_enabled = excluded.romaji_enabled,
                    explanation_style = excluded.explanation_style,
                    preferred_difficulty = excluded.preferred_difficulty,
                    conversation_corrections = excluded.conversation_corrections,
                    openai_model = excluded.openai_model,
                    updated_at = excluded.updated_at
                """,
                (
                    self.user_id,
                    prefs.proficiency_level,
                    int(prefs.romaji_enabled),
                    prefs.explanation_style,
                    prefs.preferred_difficulty,
                    int(prefs.conversation_corrections),
                    prefs.openai_model,
                    now,
                    now,
                ),
            )
        return self.get_preferences()

    # ------------------------------------------------------------- vocabulary

    @_db_errors
    def save_vocabulary(self, item: VocabularyItem, *, topic: str, level: str) -> tuple[int, bool]:
        """Save a validated vocabulary item for review.

        Returns ``(vocabulary_id, newly_saved)``. Saving the same word twice is a no-op.
        """
        if not isinstance(item, VocabularyItem):
            raise InputValidationError("Only validated vocabulary items can be saved.")
        validate_level(level)
        now = utc_now()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO vocabulary (
                    user_id, word, reading, romaji, meaning, part_of_speech, example_sentence,
                    example_reading, example_romaji, example_translation, usage_note,
                    topic, proficiency_level, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (user_id, word, reading, meaning) DO NOTHING
                """,
                (
                    self.user_id,
                    item.word,
                    item.reading,
                    item.romaji,
                    item.meaning,
                    item.part_of_speech,
                    item.example_sentence,
                    item.example_reading,
                    item.example_romaji,
                    item.example_translation,
                    item.usage_note,
                    topic,
                    level,
                    now,
                ),
            )
            vocab_id = conn.execute(
                "SELECT id FROM vocabulary WHERE user_id = ? AND word = ? AND reading = ? "
                "AND meaning = ?",
                (self.user_id, item.word, item.reading, item.meaning),
            ).fetchone()["id"]
            cursor = conn.execute(
                """
                INSERT INTO saved_vocabulary (vocabulary_id, saved_at) VALUES (?, ?)
                ON CONFLICT (vocabulary_id) DO NOTHING
                """,
                (vocab_id, now),
            )
            created = cursor.rowcount == 1
        return int(vocab_id), created

    @_db_errors
    def saved_vocabulary_keys(self) -> set[tuple[str, str, str]]:
        """(word, reading, meaning) for every saved item — used to mark 'already saved'."""
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT v.word, v.reading, v.meaning FROM saved_vocabulary s
                JOIN vocabulary v ON v.id = s.vocabulary_id
                WHERE v.user_id = ?
                """,
                (self.user_id,),
            ).fetchall()
        return {(r["word"], r["reading"], r["meaning"]) for r in rows}

    @_db_errors
    def list_saved_vocabulary(self, *, limit: int = 1000) -> list[SavedWord]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT v.*, v.id AS vocabulary_id, s.saved_at, s.review_count,
                       s.correct_count, s.last_reviewed_at
                FROM saved_vocabulary s JOIN vocabulary v ON v.id = s.vocabulary_id
                WHERE v.user_id = ?
                ORDER BY s.saved_at DESC, s.id DESC
                LIMIT ?
                """,
                (self.user_id, limit),
            ).fetchall()
        return [
            SavedWord(
                vocabulary_id=r["vocabulary_id"],
                word=r["word"],
                reading=r["reading"],
                romaji=r["romaji"],
                meaning=r["meaning"],
                part_of_speech=r["part_of_speech"],
                example_sentence=r["example_sentence"],
                example_reading=r["example_reading"],
                example_romaji=r["example_romaji"],
                example_translation=r["example_translation"],
                usage_note=r["usage_note"],
                topic=r["topic"],
                proficiency_level=r["proficiency_level"],
                saved_at=r["saved_at"],
                review_count=r["review_count"],
                correct_count=r["correct_count"],
                last_reviewed_at=r["last_reviewed_at"],
            )
            for r in rows
        ]

    @_db_errors
    def delete_saved_vocabulary(self, vocabulary_ids: list[int]) -> int:
        """Remove the user's words (and their review history). Returns the number deleted."""
        if not vocabulary_ids:
            return 0
        with connect(self.db_path) as conn:
            deleted = 0
            for vocab_id in vocabulary_ids:
                deleted += conn.execute(
                    "DELETE FROM vocabulary WHERE id = ? AND user_id = ?",
                    (int(vocab_id), self.user_id),
                ).rowcount
        return deleted

    @_db_errors
    def record_vocabulary_review(self, vocabulary_id: int, *, remembered: bool) -> None:
        now = utc_now()
        with connect(self.db_path) as conn:
            updated = conn.execute(
                """
                UPDATE saved_vocabulary
                SET review_count = review_count + 1,
                    correct_count = correct_count + ?,
                    last_reviewed_at = ?
                WHERE vocabulary_id = ?
                  AND vocabulary_id IN (SELECT id FROM vocabulary WHERE user_id = ?)
                """,
                (int(remembered), now, int(vocabulary_id), self.user_id),
            ).rowcount
            if updated != 1:
                raise InputValidationError("That word is no longer in your saved vocabulary.")
            conn.execute(
                "INSERT INTO vocabulary_reviews (vocabulary_id, remembered, reviewed_at) "
                "VALUES (?, ?, ?)",
                (int(vocabulary_id), int(remembered), now),
            )

    # ---------------------------------------------------------------- grammar

    @_db_errors
    def save_grammar_lesson(
        self, *, question: str, level: str, lesson: GrammarLessonResponse
    ) -> tuple[int, bool]:
        """Save a validated lesson. Returns ``(lesson_id, newly_saved)``."""
        if not isinstance(lesson, GrammarLessonResponse):
            raise InputValidationError("Only validated grammar lessons can be saved.")
        validate_level(level)
        with connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO grammar_lessons (
                    user_id, question, title, pattern, proficiency_level, lesson_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (user_id, title, pattern, proficiency_level) DO NOTHING
                """,
                (
                    self.user_id,
                    question,
                    lesson.title,
                    lesson.pattern,
                    level,
                    lesson.model_dump_json(),
                    utc_now(),
                ),
            )
            created = cursor.rowcount == 1
            lesson_id = conn.execute(
                "SELECT id FROM grammar_lessons WHERE user_id = ? AND title = ? AND pattern = ? "
                "AND proficiency_level = ?",
                (self.user_id, lesson.title, lesson.pattern, level),
            ).fetchone()["id"]
        return int(lesson_id), created

    @_db_errors
    def list_grammar_lessons(self, *, limit: int = 200) -> list[GrammarLessonRecord]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, question, title, pattern, proficiency_level, lesson_json, created_at "
                "FROM grammar_lessons WHERE user_id = ? ORDER BY created_at DESC, id DESC "
                "LIMIT ?",
                (self.user_id, limit),
            ).fetchall()
        return [GrammarLessonRecord(**dict(r)) for r in rows]

    @_db_errors
    def delete_grammar_lesson(self, lesson_id: int) -> bool:
        with connect(self.db_path) as conn:
            return (
                conn.execute(
                    "DELETE FROM grammar_lessons WHERE id = ? AND user_id = ?",
                    (int(lesson_id), self.user_id),
                ).rowcount
                == 1
            )

    # ------------------------------------------------------------------ quiz

    @_db_errors
    def save_quiz_attempt(self, attempt: NewQuizAttempt) -> tuple[int, bool]:
        """Persist a scored quiz and its per-question responses in one transaction.

        ``client_quiz_id`` is unique, so a repeated submission of the same quiz
        returns the existing attempt instead of creating a duplicate.
        Returns ``(attempt_id, newly_saved)``.
        """
        if not 0 <= attempt.correct_answers <= attempt.total_questions:
            raise InputValidationError("Invalid quiz result.")
        with connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO quiz_attempts (
                    user_id, client_quiz_id, topic, quiz_type, proficiency_level, difficulty,
                    total_questions, correct_answers, score, attempted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (client_quiz_id) DO NOTHING
                """,
                (
                    self.user_id,
                    attempt.client_quiz_id,
                    attempt.topic,
                    attempt.quiz_type,
                    attempt.proficiency_level,
                    attempt.difficulty,
                    attempt.total_questions,
                    attempt.correct_answers,
                    attempt.score,
                    utc_now(),
                ),
            )
            created = cursor.rowcount == 1
            row = conn.execute(
                "SELECT id FROM quiz_attempts WHERE client_quiz_id = ? AND user_id = ?",
                (attempt.client_quiz_id, self.user_id),
            ).fetchone()
            if row is None:  # the id belongs to another user's attempt
                raise InputValidationError("This quiz could not be saved.")
            attempt_id = row["id"]
            if created:
                conn.executemany(
                    """
                    INSERT INTO quiz_responses (
                        attempt_id, question_index, question_type, prompt, japanese_text,
                        options_json, selected_index, correct_index, is_correct, explanation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            attempt_id,
                            r.question_index,
                            r.question_type,
                            r.prompt,
                            r.japanese_text,
                            json.dumps(r.options, ensure_ascii=False),
                            r.selected_index,
                            r.correct_index,
                            int(r.is_correct),
                            r.explanation,
                        )
                        for r in attempt.responses
                    ],
                )
        return int(attempt_id), created

    @_db_errors
    def list_quiz_attempts(self, *, limit: int = 100) -> list[QuizAttemptRecord]:
        """Most recent first."""
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, client_quiz_id, topic, quiz_type, proficiency_level, difficulty, "
                "total_questions, correct_answers, score, attempted_at FROM quiz_attempts "
                "WHERE user_id = ? ORDER BY attempted_at DESC, id DESC LIMIT ?",
                (self.user_id, limit),
            ).fetchall()
        return [QuizAttemptRecord(**dict(r)) for r in rows]

    @staticmethod
    def _response_from_row(row: sqlite3.Row) -> QuizResponseRecord:
        return QuizResponseRecord(
            question_index=row["question_index"],
            question_type=row["question_type"],
            prompt=row["prompt"],
            japanese_text=row["japanese_text"],
            options=json.loads(row["options_json"]),
            selected_index=row["selected_index"],
            correct_index=row["correct_index"],
            is_correct=bool(row["is_correct"]),
            explanation=row["explanation"],
        )

    @_db_errors
    def get_quiz_responses(self, attempt_id: int) -> list[QuizResponseRecord]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT r.* FROM quiz_responses r JOIN quiz_attempts a ON a.id = r.attempt_id "
                "WHERE r.attempt_id = ? AND a.user_id = ? ORDER BY r.question_index",
                (int(attempt_id), self.user_id),
            ).fetchall()
        return [self._response_from_row(r) for r in rows]

    @_db_errors
    def list_incorrect_responses(
        self, *, limit: int = 50
    ) -> list[tuple[QuizAttemptRecord, QuizResponseRecord]]:
        """Recent wrong or unanswered questions, for review."""
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT r.*, a.id AS a_id, a.client_quiz_id, a.topic, a.quiz_type,
                       a.proficiency_level, a.difficulty, a.total_questions,
                       a.correct_answers, a.score, a.attempted_at
                FROM quiz_responses r JOIN quiz_attempts a ON a.id = r.attempt_id
                WHERE r.is_correct = 0 AND a.user_id = ?
                ORDER BY a.attempted_at DESC, r.question_index
                LIMIT ?
                """,
                (self.user_id, limit),
            ).fetchall()
        results = []
        for r in rows:
            attempt = QuizAttemptRecord(
                id=r["a_id"],
                client_quiz_id=r["client_quiz_id"],
                topic=r["topic"],
                quiz_type=r["quiz_type"],
                proficiency_level=r["proficiency_level"],
                difficulty=r["difficulty"],
                total_questions=r["total_questions"],
                correct_answers=r["correct_answers"],
                score=r["score"],
                attempted_at=r["attempted_at"],
            )
            results.append((attempt, self._response_from_row(r)))
        return results

    # -------------------------------------------------------------- activity

    @_db_errors
    def log_activity(
        self, activity_type: str, description: str, *, coalesce_minutes: int = 0
    ) -> bool:
        """Record an activity. With ``coalesce_minutes``, skip it when the same
        activity type was already logged within that window. Returns True if logged."""
        if activity_type not in ACTIVITY_TYPES:
            raise InputValidationError("Unknown activity type.")
        now = datetime.now(UTC)
        with connect(self.db_path) as conn:
            if coalesce_minutes > 0:
                since = (now - timedelta(minutes=coalesce_minutes)).strftime(_TS)
                recent = conn.execute(
                    "SELECT 1 FROM activity_log WHERE user_id = ? AND activity_type = ? "
                    "AND created_at >= ? LIMIT 1",
                    (self.user_id, activity_type, since),
                ).fetchone()
                if recent:
                    return False
            conn.execute(
                "INSERT INTO activity_log (user_id, activity_type, description, created_at) "
                "VALUES (?, ?, ?, ?)",
                (self.user_id, activity_type, description[:200], now.strftime(_TS)),
            )
        return True

    @_db_errors
    def list_recent_activity(self, *, limit: int = 10) -> list[ActivityRecord]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT activity_type, description, created_at FROM activity_log "
                "WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (self.user_id, limit),
            ).fetchall()
        return [ActivityRecord(**dict(r)) for r in rows]

    @_db_errors
    def activity_counts_by_day(self, *, days: int = 30) -> list[tuple[str, int]]:
        """(YYYY-MM-DD, count) for days with activity, including flashcard reviews."""
        since = (datetime.now(UTC) - timedelta(days=days)).strftime(_TS)
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT day, COUNT(*) AS n FROM (
                    SELECT substr(created_at, 1, 10) AS day FROM activity_log
                    WHERE user_id = ? AND created_at >= ?
                      AND activity_type != 'vocabulary_reviewed'
                    UNION ALL
                    SELECT substr(r.reviewed_at, 1, 10) AS day FROM vocabulary_reviews r
                    JOIN vocabulary v ON v.id = r.vocabulary_id
                    WHERE v.user_id = ? AND r.reviewed_at >= ?
                ) GROUP BY day ORDER BY day
                """,
                (self.user_id, since, self.user_id, since),
            ).fetchall()
        return [(r["day"], r["n"]) for r in rows]

    @_db_errors
    def get_stats(self) -> LearningStats:
        uid = self.user_id
        with connect(self.db_path) as conn:

            def scalar(sql: str, params: tuple = ()) -> int | float | None:
                return conn.execute(sql, params).fetchone()[0]

            def activity(kind: str) -> int:
                return int(
                    scalar(
                        "SELECT COUNT(*) FROM activity_log WHERE user_id = ? AND activity_type = ?",
                        (uid, kind),
                    )
                )

            return LearningStats(
                saved_words=int(
                    scalar(
                        "SELECT COUNT(*) FROM saved_vocabulary s JOIN vocabulary v "
                        "ON v.id = s.vocabulary_id WHERE v.user_id = ?",
                        (uid,),
                    )
                ),
                vocabulary_reviews=int(
                    scalar(
                        "SELECT COUNT(*) FROM vocabulary_reviews r JOIN vocabulary v "
                        "ON v.id = r.vocabulary_id WHERE v.user_id = ?",
                        (uid,),
                    )
                ),
                quizzes_completed=int(
                    scalar("SELECT COUNT(*) FROM quiz_attempts WHERE user_id = ?", (uid,))
                ),
                average_score=scalar(
                    "SELECT AVG(score) FROM quiz_attempts WHERE user_id = ?", (uid,)
                ),
                grammar_lessons_saved=int(
                    scalar("SELECT COUNT(*) FROM grammar_lessons WHERE user_id = ?", (uid,))
                ),
                grammar_lessons_viewed=activity("grammar_viewed"),
                sentences_checked=activity("sentence_checked"),
                conversations_started=activity("conversation_started"),
            )

    # ---------------------------------------------------------------- delete

    @_db_errors
    def clear_learning_history(self, scope: str) -> None:
        """Permanently delete this user's records in ``scope`` (one transaction)."""
        if scope not in CLEAR_SCOPES:
            raise InputValidationError("Unknown data category.")
        statements = {
            # quiz_responses and vocabulary_reviews/saved_vocabulary cascade from their parents.
            "quizzes": ["DELETE FROM quiz_attempts WHERE user_id = ?"],
            "vocabulary": ["DELETE FROM vocabulary WHERE user_id = ?"],
            "grammar": ["DELETE FROM grammar_lessons WHERE user_id = ?"],
            "activity": ["DELETE FROM activity_log WHERE user_id = ?"],
        }
        selected = (
            [s for group in statements.values() for s in group]
            if scope == "all"
            else statements[scope]
        )
        with connect(self.db_path) as conn:
            for statement in selected:
                conn.execute(statement, (self.user_id,))
        logger.info("Cleared learning history: %s", scope)
