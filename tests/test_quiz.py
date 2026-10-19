"""Quiz scoring, generated-question validation, and quiz session behaviour."""

from __future__ import annotations

import random
from dataclasses import fields

import pytest

from core.errors import AIResponseError, DatabaseError, InputValidationError
from database.models import SavedWord
from features.quiz import (
    PublicQuestion,
    QuizSession,
    build_saved_vocabulary_quiz,
    calculate_quiz_score,
    explain_incorrect_answer,
    generate_quiz,
    shuffle_options,
    validate_generated_questions,
)
from tests.conftest import FakeLLM, quiz_question


def _questions(n: int = 3) -> list:
    return [quiz_question(prompt=f"Question {i}?") for i in range(n)]


# ----------------------------------------------------------------- scoring


def test_all_correct() -> None:
    score = calculate_quiz_score(_questions(), {0: 0, 1: 0, 2: 0})
    assert (score.correct, score.incorrect, score.unanswered, score.percent) == (3, 0, 0, 100.0)


def test_mixed_and_missing_answers() -> None:
    score = calculate_quiz_score(_questions(4), {0: 0, 1: 2})
    assert score.correct == 1
    assert score.incorrect == 1
    assert score.unanswered == 2
    assert score.percent == 25.0
    assert [r.status for r in score.results] == ["correct", "incorrect", "unanswered", "unanswered"]


def test_none_answer_counts_as_unanswered() -> None:
    score = calculate_quiz_score(_questions(2), {0: None, 1: 0})
    assert score.unanswered == 1 and score.correct == 1


@pytest.mark.parametrize(
    "answers",
    [{0: 4}, {0: -1}, {5: 0}, {0: "0"}, {0: True}, {"0": 0}, {0: 1.0}],
)
def test_invalid_selections_rejected(answers: dict) -> None:
    with pytest.raises(InputValidationError):
        calculate_quiz_score(_questions(2), answers)


def test_empty_quiz_rejected() -> None:
    with pytest.raises(InputValidationError):
        calculate_quiz_score([], {})


def test_scoring_is_deterministic() -> None:
    qs = _questions(5)
    answers = {0: 0, 1: 1, 3: 0}
    assert calculate_quiz_score(qs, answers) == calculate_quiz_score(qs, answers)


# ---------------------------------------------------- generated questions


def test_invalid_generated_questions_are_dropped() -> None:
    good = quiz_question()
    dup_options = quiz_question(prompt="B?", options=["water", "Water ", "tree"])
    bad_index = quiz_question(prompt="C?", correct_option_index=7)
    one_option = quiz_question(prompt="D?", options=["water"], correct_option_index=0)
    duplicate = quiz_question()
    kept = validate_generated_questions(
        [good, dup_options, bad_index, one_option, duplicate], quiz_type="mixed"
    )
    assert kept == [good]


def test_wrong_type_dropped_when_type_requested() -> None:
    q = quiz_question(question_type="grammar")
    assert validate_generated_questions([q], quiz_type="fill_in_blank") == []
    assert validate_generated_questions([q], quiz_type="grammar") == [q]


def test_shuffle_preserves_correct_answer() -> None:
    q = quiz_question()
    for seed in range(20):
        shuffled = shuffle_options(q, random.Random(seed))
        assert sorted(shuffled.options) == sorted(q.options)
        assert shuffled.options[shuffled.correct_option_index] == "water"


def test_generate_quiz_validates_and_trims() -> None:
    qs = [quiz_question(prompt=f"Q{i}?").model_dump() for i in range(6)]
    llm = FakeLLM({"questions": qs})
    result = generate_quiz(
        llm,
        topic="Food",
        level="beginner",
        question_count=4,
        quiz_type="mixed",
        difficulty="easy",
        rng=random.Random(1),
    )
    assert len(result) == 4
    assert all(q.options[q.correct_option_index] == "water" for q in result)


def test_generate_quiz_all_invalid_raises() -> None:
    bad = quiz_question(correct_option_index=9).model_dump()
    llm = FakeLLM({"questions": [bad]})
    with pytest.raises(AIResponseError):
        generate_quiz(
            llm,
            topic="Food",
            level="beginner",
            question_count=3,
            quiz_type="mixed",
            difficulty="easy",
        )


def test_generate_quiz_validates_inputs_before_calling_ai() -> None:
    llm = FakeLLM()
    with pytest.raises(InputValidationError):
        generate_quiz(
            llm,
            topic="Food",
            level="beginner",
            question_count=99,
            quiz_type="mixed",
            difficulty="easy",
        )
    with pytest.raises(InputValidationError):
        generate_quiz(
            llm,
            topic="Food",
            level="beginner",
            question_count=5,
            quiz_type="essay",
            difficulty="easy",
        )
    assert llm.calls == []


def test_explain_incorrect_answer_rejects_correct_choice() -> None:
    with pytest.raises(InputValidationError):
        explain_incorrect_answer(
            FakeLLM(), question=quiz_question(), selected_index=0, level="beginner"
        )


# ----------------------------------------------------------------- session


def test_public_questions_hide_answer_keys() -> None:
    session = QuizSession("Food", "mixed", "beginner", "easy", _questions())
    public_fields = {f.name for f in fields(PublicQuestion)}
    assert "correct_option_index" not in public_fields
    assert "explanation" not in public_fields
    for pq in session.public_questions():
        rendered = repr(pq)
        assert "explanation" not in rendered
        assert "water means" not in rendered


def test_select_answer_validation() -> None:
    session = QuizSession("Food", "mixed", "beginner", "easy", _questions())
    session.select_answer(0, 2)
    assert session.answers == {0: 2}
    session.select_answer(0, None)
    assert session.answers == {}
    for q_index, option in [(0, 4), (3, 0), (0, -1), (0, True)]:
        with pytest.raises(InputValidationError):
            session.select_answer(q_index, option)


def test_answers_survive_navigation() -> None:
    session = QuizSession("Food", "mixed", "beginner", "easy", _questions())
    session.select_answer(0, 1)
    session.go_to(2)
    session.select_answer(2, 0)
    session.go_to(0)
    assert session.answers == {0: 1, 2: 0}
    assert session.unanswered_indices() == [1]
    session.go_to(99)
    assert session.current_index == 2


def test_duplicate_submission_scores_and_saves_once(repo) -> None:
    session = QuizSession("Food", "mixed", "beginner", "easy", _questions())
    session.select_answer(0, 0)
    first = session.submit(repo)
    second = session.submit(repo)
    assert first is second
    assert len(repo.list_quiz_attempts()) == 1
    assert repo.get_stats().quizzes_completed == 1


def test_no_answer_changes_after_submission(repo) -> None:
    session = QuizSession("Food", "mixed", "beginner", "easy", _questions())
    session.submit(repo)
    with pytest.raises(InputValidationError):
        session.select_answer(0, 0)
    assert session.score.correct == 0


def test_repository_dedupes_same_quiz_id_across_sessions(repo) -> None:
    session = QuizSession("Food", "mixed", "beginner", "easy", _questions())
    session.submit(repo)
    copy = QuizSession("Food", "mixed", "beginner", "easy", _questions(), quiz_id=session.quiz_id)
    copy.submit(repo)
    assert len(repo.list_quiz_attempts()) == 1
    assert copy.attempt_id == session.attempt_id


def test_save_failure_keeps_score_and_allows_retry(repo) -> None:
    class BrokenRepo:
        def save_quiz_attempt(self, attempt):
            raise DatabaseError()

    session = QuizSession("Food", "mixed", "beginner", "easy", _questions())
    score = session.submit(BrokenRepo())
    assert session.submitted and session.save_failed
    assert session.persist(repo) is True
    assert not session.save_failed
    assert session.submit(repo) is score
    assert len(repo.list_quiz_attempts()) == 1


def test_quiz_responses_are_stored(repo) -> None:
    session = QuizSession("Food", "mixed", "beginner", "easy", _questions(2))
    session.select_answer(0, 0)
    session.select_answer(1, 3)
    session.submit(repo)
    responses = repo.get_quiz_responses(session.attempt_id)
    assert [r.is_correct for r in responses] == [True, False]
    assert responses[1].selected_index == 3
    assert len(repo.list_incorrect_responses()) == 1


# ----------------------------------------------------- saved-vocab quiz


def _saved(i: int) -> SavedWord:
    return SavedWord(
        vocabulary_id=i,
        word=f"語{i}",
        reading=f"ご{i}",
        romaji=f"go{i}",
        meaning=f"meaning {i}",
        part_of_speech="noun",
        example_sentence="例文。",
        example_reading="れいぶん。",
        example_romaji="reibun.",
        example_translation="Example.",
        usage_note=None,
        topic="Test",
        proficiency_level="beginner",
        saved_at="2026-01-01T00:00:00Z",
        review_count=0,
        correct_count=0,
        last_reviewed_at=None,
    )


def test_saved_vocabulary_quiz_requires_enough_words() -> None:
    with pytest.raises(InputValidationError):
        build_saved_vocabulary_quiz(
            [_saved(i) for i in range(3)], question_count=3, level="beginner"
        )


def test_saved_vocabulary_quiz_builds_valid_questions() -> None:
    words = [_saved(i) for i in range(6)]
    session = build_saved_vocabulary_quiz(
        words, question_count=5, level="beginner", rng=random.Random(3)
    )
    assert session.total == 5
    assert validate_generated_questions(session.questions, quiz_type="vocabulary_recall") == (
        session.questions
    )
    score = calculate_quiz_score(
        session.questions, {i: q.correct_option_index for i, q in enumerate(session.questions)}
    )
    assert score.percent == 100.0
