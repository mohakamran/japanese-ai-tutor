"""Quiz generation, validation, deterministic scoring, and the quiz session.

Key guarantees:

* Scores are computed here in Python, never by the model.
* :meth:`QuizSession.public_questions` exposes questions *without* answer keys,
  and the UI renders only that view until the quiz is submitted.
* Submitting is idempotent: a quiz is scored and saved at most once.
"""

from __future__ import annotations

import logging
import random
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from core.constants import (
    MAX_QUIZ_OPTIONS,
    MAX_QUIZ_QUESTIONS,
    MIN_QUIZ_OPTIONS,
    MIN_QUIZ_QUESTIONS,
    MIN_SAVED_WORDS_FOR_QUIZ,
    QUIZ_TYPES,
    SAVED_VOCABULARY_QUIZ_TYPE,
)
from core.errors import AIResponseError, DatabaseError, InputValidationError
from core.validation import (
    validate_choice,
    validate_count,
    validate_difficulty,
    validate_level,
    validate_topic,
)
from database.models import NewQuizAttempt, QuizResponseRecord, SavedWord
from database.repository import LearningRepository
from prompts.quiz import build_answer_explanation_prompt, build_quiz_prompt
from schemas.quiz import AnswerExplanationResponse, QuizGenerationResponse, QuizQuestion
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

AnswerStatus = Literal["correct", "incorrect", "unanswered"]


# ----------------------------------------------------------------- data types


@dataclass(frozen=True)
class PublicQuestion:
    """A question as shown before submission: no answer index, no explanation."""

    index: int
    question_type: str
    prompt: str
    japanese_text: str | None
    reading: str | None
    romaji: str | None
    options: tuple[str, ...]


@dataclass(frozen=True)
class QuestionResult:
    index: int
    question: QuizQuestion
    selected_index: int | None
    status: AnswerStatus

    @property
    def is_correct(self) -> bool:
        return self.status == "correct"


@dataclass(frozen=True)
class QuizScore:
    total: int
    correct: int
    unanswered: int
    results: tuple[QuestionResult, ...]

    @property
    def incorrect(self) -> int:
        return self.total - self.correct - self.unanswered

    @property
    def percent(self) -> float:
        return round(100.0 * self.correct / self.total, 1) if self.total else 0.0


# ------------------------------------------------------------------ scoring


def calculate_quiz_score(
    questions: Sequence[QuizQuestion], answers: Mapping[int, int | None]
) -> QuizScore:
    """Score a quiz deterministically.

    ``answers`` maps question index → selected option index (or None / missing
    for an unanswered question). Unanswered questions count as not correct.
    Raises :class:`InputValidationError` for answers that do not fit the quiz.
    """
    if not questions:
        raise InputValidationError("This quiz has no questions.")
    for q_index, selected in answers.items():
        if isinstance(q_index, bool) or not isinstance(q_index, int):
            raise InputValidationError("Invalid question reference in answers.")
        if not 0 <= q_index < len(questions):
            raise InputValidationError("An answer refers to a question that does not exist.")
        if selected is None:
            continue
        if isinstance(selected, bool) or not isinstance(selected, int):
            raise InputValidationError("Invalid answer selection.")
        if not 0 <= selected < len(questions[q_index].options):
            raise InputValidationError("An answer selection is not one of the options.")

    results = []
    correct = unanswered = 0
    for i, question in enumerate(questions):
        selected = answers.get(i)
        if selected is None:
            status: AnswerStatus = "unanswered"
            unanswered += 1
        elif selected == question.correct_option_index:
            status = "correct"
            correct += 1
        else:
            status = "incorrect"
        results.append(QuestionResult(i, question, selected, status))
    return QuizScore(len(questions), correct, unanswered, tuple(results))


# --------------------------------------------------------------- validation


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def question_problems(question: QuizQuestion) -> list[str]:
    """Return reasons a generated question is unusable (empty list = valid)."""
    problems = []
    n = len(question.options)
    if not MIN_QUIZ_OPTIONS <= n <= MAX_QUIZ_OPTIONS:
        problems.append(f"has {n} options")
    if len({_normalize(o) for o in question.options}) != n:
        problems.append("has duplicate options")
    if not 0 <= question.correct_option_index < n:
        problems.append("answer index out of range")
    return problems


def validate_generated_questions(
    questions: Sequence[QuizQuestion], *, quiz_type: str
) -> list[QuizQuestion]:
    """Drop structurally invalid or duplicate questions; keep the rest in order."""
    valid: list[QuizQuestion] = []
    seen: set[str] = set()
    for i, q in enumerate(questions):
        problems = question_problems(q)
        if quiz_type != "mixed" and q.question_type != quiz_type:
            problems.append(f"wrong type {q.question_type}")
        key = _normalize(q.prompt + "|" + (q.japanese_text or ""))
        if key in seen:
            problems.append("duplicate question")
        if problems:
            logger.warning("Discarding generated question %d: %s", i, ", ".join(problems))
            continue
        seen.add(key)
        valid.append(q)
    return valid


def shuffle_options(question: QuizQuestion, rng: random.Random) -> QuizQuestion:
    """Shuffle answer options so the correct answer's position is not predictable."""
    order = list(range(len(question.options)))
    rng.shuffle(order)
    return question.model_copy(
        update={
            "options": [question.options[i] for i in order],
            "correct_option_index": order.index(question.correct_option_index),
        }
    )


# --------------------------------------------------------------- generation


def generate_quiz(
    llm: LLMService,
    *,
    topic: str,
    level: str,
    question_count: int,
    quiz_type: str,
    difficulty: str,
    style: str = "balanced",
    rng: random.Random | None = None,
) -> list[QuizQuestion]:
    """Generate, validate and shuffle quiz questions with the AI model."""
    topic = validate_topic(topic)
    level = validate_level(level)
    difficulty = validate_difficulty(difficulty)
    quiz_type = validate_choice(quiz_type, QUIZ_TYPES, field="Quiz type")
    question_count = validate_count(
        question_count,
        field="Number of questions",
        minimum=MIN_QUIZ_QUESTIONS,
        maximum=MAX_QUIZ_QUESTIONS,
    )

    prompt = build_quiz_prompt(
        topic=topic,
        level=level,
        count=question_count,
        quiz_type=quiz_type,
        difficulty=difficulty,
        style=style,
    )
    response = llm.generate_structured(prompt, QuizGenerationResponse)
    questions = validate_generated_questions(response.questions, quiz_type=quiz_type)
    questions = questions[:question_count]
    if not questions:
        raise AIResponseError(
            "The AI did not produce any usable quiz questions. Please try again.",
            detail="all generated questions failed validation",
        )
    rng = rng or random.Random()
    return [shuffle_options(q, rng) for q in questions]


def build_saved_vocabulary_quiz(
    words: Sequence[SavedWord],
    *,
    question_count: int,
    level: str,
    rng: random.Random | None = None,
) -> QuizSession:
    """Build a vocabulary-recall quiz from saved words locally, without the AI.

    Distractors come from the learner's other saved words, so at least
    ``MIN_SAVED_WORDS_FOR_QUIZ`` distinct words are required.
    """
    rng = rng or random.Random()
    unique: dict[str, SavedWord] = {}
    for w in words:
        unique.setdefault(_normalize(w.meaning), w)
    pool = list(unique.values())
    if len(pool) < MIN_SAVED_WORDS_FOR_QUIZ:
        raise InputValidationError(
            f"Save at least {MIN_SAVED_WORDS_FOR_QUIZ} words with different meanings to "
            "practise them in a quiz."
        )
    count = min(
        validate_count(
            question_count, field="Number of questions", minimum=1, maximum=MAX_QUIZ_QUESTIONS
        ),
        len(pool),
    )
    # Prefer words that have been reviewed least or remembered least.
    pool.sort(key=lambda w: (w.correct_count, w.review_count, rng.random()))
    targets = pool[:count]

    questions: list[QuizQuestion] = []
    for i, word in enumerate(targets):
        others = [w for w in pool if w is not word]
        distractors = rng.sample(others, 3)
        if i % 2 == 0:  # Japanese → English meaning
            correct, wrong = word.meaning, [d.meaning for d in distractors]
            prompt = "What does this word mean?"
            japanese, reading, romaji = word.word, word.reading, word.romaji
        else:  # English → Japanese word
            correct, wrong = word.word, [d.word for d in distractors]
            prompt = f'Which Japanese word means "{word.meaning}"?'
            japanese = reading = romaji = None
        if len({_normalize(o) for o in [correct, *wrong]}) < 4:
            wrong = [d.meaning for d in distractors]
            correct, prompt = word.meaning, "What does this word mean?"
            japanese, reading, romaji = word.word, word.reading, word.romaji
        question = QuizQuestion(
            question_type="vocabulary_recall",
            prompt=prompt,
            japanese_text=japanese,
            reading=reading,
            romaji=romaji,
            options=[correct, *wrong],
            correct_option_index=0,
            explanation=(
                f"{word.word} ({word.reading}, {word.romaji}) means “{word.meaning}”. "
                f"Example: {word.example_sentence} — {word.example_translation}"
            ),
        )
        questions.append(shuffle_options(question, rng))

    return QuizSession(
        topic="Saved vocabulary",
        quiz_type=SAVED_VOCABULARY_QUIZ_TYPE,
        level=level,
        difficulty="medium",
        questions=questions,
    )


def explain_incorrect_answer(
    llm: LLMService,
    *,
    question: QuizQuestion,
    selected_index: int,
    level: str,
    style: str = "balanced",
) -> AnswerExplanationResponse:
    """Ask the AI for a deeper explanation of a wrong answer (after submission only)."""
    level = validate_level(level)
    if not 0 <= selected_index < len(question.options):
        raise InputValidationError("Invalid answer selection.")
    if selected_index == question.correct_option_index:
        raise InputValidationError("That answer was correct.")
    prompt = build_answer_explanation_prompt(
        level=level,
        style=style,
        prompt_text=question.prompt,
        japanese_text=question.japanese_text,
        options=list(question.options),
        correct_option=question.options[question.correct_option_index],
        selected_option=question.options[selected_index],
    )
    return llm.generate_structured(prompt, AnswerExplanationResponse)


# ------------------------------------------------------------------ session


@dataclass
class QuizSession:
    """State for one quiz from generation through submission.

    Stored in Streamlit session state so it survives reruns and page changes.
    """

    topic: str
    quiz_type: str
    level: str
    difficulty: str
    questions: list[QuizQuestion]
    quiz_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    answers: dict[int, int] = field(default_factory=dict)
    current_index: int = 0
    score: QuizScore | None = None
    attempt_id: int | None = None
    save_failed: bool = False

    def __post_init__(self) -> None:
        if not self.questions:
            raise InputValidationError("A quiz needs at least one question.")

    @property
    def submitted(self) -> bool:
        return self.score is not None

    @property
    def total(self) -> int:
        return len(self.questions)

    def public_questions(self) -> list[PublicQuestion]:
        return [
            PublicQuestion(
                index=i,
                question_type=q.question_type,
                prompt=q.prompt,
                japanese_text=q.japanese_text,
                reading=q.reading,
                romaji=q.romaji,
                options=tuple(q.options),
            )
            for i, q in enumerate(self.questions)
        ]

    def select_answer(self, question_index: int, option_index: int | None) -> None:
        if self.submitted:
            raise InputValidationError("This quiz has already been submitted.")
        if not 0 <= question_index < self.total:
            raise InputValidationError("That question does not exist.")
        if option_index is None:
            self.answers.pop(question_index, None)
            return
        if (
            isinstance(option_index, bool)
            or not isinstance(option_index, int)
            or not (0 <= option_index < len(self.questions[question_index].options))
        ):
            raise InputValidationError("Please choose one of the listed options.")
        self.answers[question_index] = option_index

    def go_to(self, question_index: int) -> None:
        self.current_index = max(0, min(question_index, self.total - 1))

    def unanswered_indices(self) -> list[int]:
        return [i for i in range(self.total) if i not in self.answers]

    def submit(self, repo: LearningRepository | None = None) -> QuizScore:
        """Score the quiz once and save it. Repeated calls return the same score."""
        if self.score is None:
            self.score = calculate_quiz_score(self.questions, self.answers)
        if repo is not None and self.attempt_id is None:
            self.persist(repo)
        return self.score

    def persist(self, repo: LearningRepository) -> bool:
        """Save the scored attempt. Safe to retry; the repository dedupes on quiz_id."""
        if self.score is None:
            raise InputValidationError("Submit the quiz before saving it.")
        if self.attempt_id is not None:
            return True
        score = self.score
        attempt = NewQuizAttempt(
            client_quiz_id=self.quiz_id,
            topic=self.topic,
            quiz_type=self.quiz_type,
            proficiency_level=self.level,
            difficulty=self.difficulty,
            total_questions=score.total,
            correct_answers=score.correct,
            score=score.percent,
            responses=[
                QuizResponseRecord(
                    question_index=r.index,
                    question_type=r.question.question_type,
                    prompt=r.question.prompt,
                    japanese_text=r.question.japanese_text,
                    options=list(r.question.options),
                    selected_index=r.selected_index,
                    correct_index=r.question.correct_option_index,
                    is_correct=r.is_correct,
                    explanation=r.question.explanation,
                )
                for r in score.results
            ],
        )
        try:
            self.attempt_id, created = repo.save_quiz_attempt(attempt)
        except DatabaseError:
            self.save_failed = True
            return False
        self.save_failed = False
        if created:
            try:
                repo.log_activity(
                    "quiz_completed",
                    f"Quiz on {self.topic}: {score.correct}/{score.total} ({score.percent:g}%)",
                )
            except DatabaseError:
                logger.warning("Quiz saved but activity log entry failed")
        return True
