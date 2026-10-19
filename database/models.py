"""Plain dataclasses for rows returned by the repository.

The UI and business logic work with these instead of raw ``sqlite3.Row`` objects,
so a future PostgreSQL implementation only needs to return the same types.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Preferences:
    proficiency_level: str
    romaji_enabled: bool
    explanation_style: str
    preferred_difficulty: str
    conversation_corrections: bool
    updated_at: str | None = None
    openai_model: str | None = None  # the learner's chosen model; None = server default


@dataclass(frozen=True)
class SavedWord:
    vocabulary_id: int
    word: str
    reading: str
    romaji: str
    meaning: str
    part_of_speech: str
    example_sentence: str
    example_reading: str
    example_romaji: str
    example_translation: str
    usage_note: str | None
    topic: str
    proficiency_level: str
    saved_at: str
    review_count: int
    correct_count: int
    last_reviewed_at: str | None


@dataclass(frozen=True)
class GrammarLessonRecord:
    id: int
    question: str
    title: str
    pattern: str
    proficiency_level: str
    lesson_json: str
    created_at: str


@dataclass(frozen=True)
class QuizResponseRecord:
    question_index: int
    question_type: str
    prompt: str
    japanese_text: str | None
    options: list[str]
    selected_index: int | None
    correct_index: int
    is_correct: bool
    explanation: str


@dataclass(frozen=True)
class QuizAttemptRecord:
    id: int
    client_quiz_id: str
    topic: str
    quiz_type: str
    proficiency_level: str
    difficulty: str
    total_questions: int
    correct_answers: int
    score: float
    attempted_at: str


@dataclass(frozen=True)
class NewQuizAttempt:
    """Input for :meth:`LearningRepository.save_quiz_attempt`."""

    client_quiz_id: str
    topic: str
    quiz_type: str
    proficiency_level: str
    difficulty: str
    total_questions: int
    correct_answers: int
    score: float
    responses: list[QuizResponseRecord] = field(default_factory=list)


@dataclass(frozen=True)
class ActivityRecord:
    activity_type: str
    description: str
    created_at: str


@dataclass(frozen=True)
class LearningStats:
    saved_words: int
    vocabulary_reviews: int
    quizzes_completed: int
    average_score: float | None
    grammar_lessons_saved: int
    grammar_lessons_viewed: int
    sentences_checked: int
    conversations_started: int


@dataclass(frozen=True)
class User:
    """Public account details. Never includes the password hash."""

    id: int
    email: str
    display_name: str
    created_at: str
    last_login_at: str | None = None

    @property
    def initials(self) -> str:
        parts = self.display_name.split()
        letters = "".join(p[0] for p in parts[:2]) if parts else self.email[0]
        return letters.upper()


@dataclass(frozen=True)
class UserCredentials:
    """Login data for one account (used only inside the accounts feature)."""

    user: User
    password_hash: str
    failed_logins: int
    locked_until: str | None


@dataclass(frozen=True)
class StoredApiKey:
    encrypted_api_key: str
    key_hint: str
    updated_at: str
