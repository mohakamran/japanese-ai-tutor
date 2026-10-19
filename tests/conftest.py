"""Shared fixtures. No test here calls the real OpenAI API."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.security import hash_password  # noqa: E402
from database.models import User  # noqa: E402
from database.repository import (  # noqa: E402
    AccountRepository,
    LearningRepository,
    initialize,
)
from prompts.base import PromptSpec  # noqa: E402
from schemas.conversation import ConversationResponse  # noqa: E402
from schemas.grammar import GrammarLessonResponse  # noqa: E402
from schemas.quiz import QuizQuestion  # noqa: E402
from schemas.vocabulary import VocabularyItem  # noqa: E402

FAKE_KEY = "sk-test-FAKE0123456789abcdefSECRET"


# ------------------------------------------------------------- sample data


def vocab_item(**overrides: Any) -> VocabularyItem:
    data = {
        "word": "食べる",
        "reading": "たべる",
        "romaji": "taberu",
        "meaning": "to eat",
        "part_of_speech": "verb",
        "example_sentence": "毎朝パンを食べます。",
        "example_reading": "まいあさパンをたべます。",
        "example_romaji": "maiasa pan o tabemasu.",
        "example_translation": "I eat bread every morning.",
        "usage_note": None,
    }
    data.update(overrides)
    return VocabularyItem.model_validate(data)


def grammar_lesson_data(**overrides: Any) -> dict[str, Any]:
    data = {
        "title": "The topic particle は",
        "pattern": "Noun + は + comment",
        "formation": "Put は (pronounced 'wa') after the topic noun.",
        "explanation": "は marks what the sentence is about.",
        "examples": [
            {
                "japanese": "私は学生です。",
                "reading": "わたしはがくせいです。",
                "romaji": "watashi wa gakusei desu.",
                "english": "I am a student.",
                "speech_register": "formal",
            }
        ],
        "usage_notes": ["は is written with the hiragana for 'ha' but read 'wa'."],
        "common_mistakes": [
            {"incorrect": "私わ学生です。", "correct": "私は学生です。", "explanation": "Spelling."}
        ],
        "formality_notes": None,
        "related_patterns": ["が"],
        "uncertainty_note": None,
    }
    data.update(overrides)
    return data


def grammar_lesson(**overrides: Any) -> GrammarLessonResponse:
    return GrammarLessonResponse.model_validate(grammar_lesson_data(**overrides))


def quiz_question(**overrides: Any) -> QuizQuestion:
    data = {
        "question_type": "multiple_choice",
        "prompt": "What does 水 mean?",
        "japanese_text": "水",
        "reading": "みず",
        "romaji": "mizu",
        "options": ["water", "fire", "tree", "mountain"],
        "correct_option_index": 0,
        "explanation": "水 (mizu) means water.",
    }
    data.update(overrides)
    return QuizQuestion.model_validate(data)


def correction_data(**overrides: Any) -> dict[str, Any]:
    data = {
        "original_sentence": "わたしは昨日すしを食べるました。",
        "verdict": "needs_correction",
        "corrected_sentence": "わたしは昨日すしを食べました。",
        "reading": "わたしはきのうすしをたべました。",
        "romaji": "watashi wa kinō sushi o tabemashita.",
        "english_translation": "I ate sushi yesterday.",
        "grammar_issues": [
            {
                "fragment": "食べるました",
                "suggestion": "食べました",
                "explanation": "Attach ました to the verb stem 食べ, not the dictionary form.",
                "severity": "error",
            }
        ],
        "word_choice_issues": [],
        "natural_alternative": None,
        "natural_alternative_romaji": None,
        "assumptions": None,
        "clarification_question": None,
        "learning_tip": "Polite past = stem + ました.",
    }
    data.update(overrides)
    return data


def conversation_response(**overrides: Any) -> ConversationResponse:
    data = {
        "reply_japanese": "いらっしゃいませ。何名様ですか。",
        "reply_reading": "いらっしゃいませ。なんめいさまですか。",
        "reply_romaji": "irasshaimase. nanmei-sama desu ka.",
        "reply_english": "Welcome. How many people?",
        "feedback": None,
        "suggested_response": "二人です。",
        "vocabulary_notes": [{"japanese": "何名", "reading": "なんめい", "english": "how many"}],
    }
    data.update(overrides)
    return ConversationResponse.model_validate(data)


# ---------------------------------------------------------------- fakes


class FakeLLM:
    """Stands in for LLMService in feature tests: returns queued results."""

    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.calls: list[tuple[PromptSpec, type]] = []
        self.is_configured = True

    def generate_structured(self, prompt: PromptSpec, schema: type) -> Any:
        self.calls.append((prompt, schema))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, schema) else schema.model_validate(result)


TEST_PASSWORD = "correct-horse-42"


def make_user(
    accounts: AccountRepository, email: str = "learner@example.com", name: str = "Test Learner"
) -> User:
    return accounts.create_user(
        email=email, display_name=name, password_hash=hash_password(TEST_PASSWORD)
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    initialize(path)
    return path


@pytest.fixture
def accounts(db_path: Path) -> AccountRepository:
    return AccountRepository(db_path)


@pytest.fixture
def user(accounts: AccountRepository) -> User:
    return make_user(accounts)


@pytest.fixture
def repo(db_path: Path, user: User) -> LearningRepository:
    return LearningRepository(db_path, user.id)
