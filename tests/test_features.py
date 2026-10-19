"""Feature workflows with a fake AI service."""

from __future__ import annotations

import pytest

from core.constants import MAX_CONVERSATION_MESSAGES_KEPT
from core.errors import AIResponseError, InputValidationError
from features import conversation as conv
from features import grammar, vocabulary
from features.correction import correct_sentence
from features.progress import load_progress, recommend_next_activity
from schemas.vocabulary import VocabularyItem
from tests.conftest import (
    FakeLLM,
    conversation_response,
    correction_data,
    grammar_lesson,
    grammar_lesson_data,
    vocab_item,
)

# -------------------------------------------------------------- vocabulary


def test_generate_vocabulary_dedupes_and_trims() -> None:
    items = [
        vocab_item().model_dump(),
        vocab_item(meaning="to eat (dup)").model_dump(),
        vocab_item(word="飲む", reading="のむ", romaji="nomu", meaning="to drink").model_dump(),
        vocab_item(word="水", reading="みず", romaji="mizu", meaning="water").model_dump(),
        vocab_item(word="魚", reading="さかな", romaji="sakana", meaning="fish").model_dump(),
    ]
    llm = FakeLLM({"items": items})
    result = vocabulary.generate_vocabulary(llm, topic="Food", level="beginner", count=3)
    assert [i.word for i in result] == ["食べる", "飲む", "水"]
    prompt = llm.calls[0][0]
    assert "<learner_input>" in prompt.input and "Food" in prompt.input
    assert "exactly 3" in prompt.instructions


def test_generate_vocabulary_empty_list_is_an_error() -> None:
    with pytest.raises(AIResponseError):
        vocabulary.generate_vocabulary(
            FakeLLM({"items": []}), topic="Food", level="beginner", count=3
        )


def test_save_vocabulary_item_logs_once(repo) -> None:
    assert vocabulary.save_vocabulary_item(repo, vocab_item(), topic="Food", level="beginner")
    assert not vocabulary.save_vocabulary_item(repo, vocab_item(), topic="Food", level="beginner")
    assert len(repo.list_recent_activity()) == 1


def test_review_deck_prioritizes_unreviewed_and_difficult(repo) -> None:
    words = []
    for w, m in [("一", "one"), ("二", "two"), ("三", "three")]:
        item: VocabularyItem = vocab_item(word=w, reading=w, romaji=w, meaning=m)
        vid, _ = repo.save_vocabulary(item, topic="Numbers", level="beginner")
        words.append(vid)
    repo.record_vocabulary_review(words[0], remembered=True)
    repo.record_vocabulary_review(words[1], remembered=False)
    deck = vocabulary.build_review_deck(repo.list_saved_vocabulary(), size=3)
    assert deck == [words[2], words[1], words[0]]


# ---------------------------------------------------------------- grammar


def test_grammar_history_is_bounded_and_compact() -> None:
    long_lesson = grammar_lesson(explanation="word " * 1000)
    history = [grammar.GrammarTurn(f"q{i}", "beginner", long_lesson) for i in range(6)]
    messages = grammar.build_history_messages(history, max_turns=3)
    assert len(messages) == 6  # 3 turns × (user + assistant)
    assert "q3" in messages[0]["content"]
    assert all(len(m["content"]) < 1200 for m in messages)


def test_explain_grammar_sends_history_and_question() -> None:
    llm = FakeLLM(grammar_lesson_data())
    history = [grammar.GrammarTurn("What is は?", "beginner", grammar_lesson())]
    grammar.explain_grammar(llm, question="And が?", level="beginner", history=history)
    messages = llm.calls[0][0].input
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert "And が?" in messages[-1]["content"]


def test_explain_grammar_validates_inputs() -> None:
    llm = FakeLLM()
    with pytest.raises(InputValidationError):
        grammar.explain_grammar(llm, question="  ", level="beginner")
    with pytest.raises(InputValidationError):
        grammar.explain_grammar(llm, question="x" * 1001, level="beginner")
    with pytest.raises(InputValidationError):
        grammar.explain_grammar(llm, question="ok", level="beginner", topic="Made-up topic")
    assert llm.calls == []


def test_saved_lesson_round_trip(repo) -> None:
    turn = grammar.GrammarTurn("What is は?", "beginner", grammar_lesson())
    assert grammar.save_grammar_lesson(repo, turn)
    record = repo.list_grammar_lessons()[0]
    assert grammar.load_saved_lesson(record.lesson_json) == turn.lesson


# -------------------------------------------------------------- correction


def test_correct_sentence_uses_learner_text_as_original() -> None:
    llm = FakeLLM(correction_data(original_sentence="something else"))
    result = correct_sentence(llm, sentence="わたしは昨日すしを食べるました。", level="beginner")
    assert result.original_sentence == "わたしは昨日すしを食べるました。"
    assert "No context was given" in llm.calls[0][0].input


def test_correct_sentence_includes_context() -> None:
    llm = FakeLLM(correction_data())
    correct_sentence(llm, sentence="すし", level="beginner", context="talking to a friend")
    assert "talking to a friend" in llm.calls[0][0].input


def test_correct_sentence_limits() -> None:
    with pytest.raises(InputValidationError):
        correct_sentence(FakeLLM(), sentence="あ" * 301, level="beginner")
    with pytest.raises(InputValidationError):
        correct_sentence(FakeLLM(), sentence="", level="beginner")


# ------------------------------------------------------------ conversation


def test_conversation_flow_and_history_bounds() -> None:
    llm = FakeLLM(conversation_response(), *[conversation_response() for _ in range(30)])
    c = conv.start_conversation(llm, scenario="restaurant", level="beginner")
    assert len(c.turns) == 1 and c.turns[0].role == "tutor"
    for i in range(30):
        conv.send_message(llm, c, f"メッセージ{i}", corrections_enabled=True)
    assert len(c.turns) == MAX_CONVERSATION_MESSAGES_KEPT
    sent = llm.calls[-1][0].input
    assert len(sent) <= 12 + 1  # bounded history + the new message
    assert sent[-1]["role"] == "user" and "メッセージ29" in sent[-1]["content"]


def test_failed_reply_leaves_conversation_unchanged() -> None:
    llm = FakeLLM(conversation_response(), AIResponseError())
    c = conv.start_conversation(llm, scenario="daily", level="beginner")
    with pytest.raises(AIResponseError):
        conv.send_message(llm, c, "こんにちは", corrections_enabled=False)
    assert len(c.turns) == 1


def test_feedback_dropped_when_corrections_disabled() -> None:
    reply = conversation_response(
        feedback={"has_mistakes": True, "corrected_message": "x", "explanation": "y"}
    )
    llm = FakeLLM(conversation_response(), reply)
    c = conv.start_conversation(llm, scenario="daily", level="beginner")
    result = conv.send_message(llm, c, "こんにちは", corrections_enabled=False)
    assert result.feedback is None
    assert "turned corrections off" in llm.calls[-1][0].instructions


def test_conversation_rejects_unknown_scenario_and_long_message() -> None:
    with pytest.raises(InputValidationError):
        conv.start_conversation(FakeLLM(), scenario="moon base", level="beginner")
    c = conv.Conversation(scenario="daily", level="beginner")
    with pytest.raises(InputValidationError):
        conv.send_message(FakeLLM(), c, "あ" * 501, corrections_enabled=True)


# ---------------------------------------------------------------- progress


def test_recommendations_follow_real_data(repo) -> None:
    assert recommend_next_activity(load_progress(repo)).page == "vocabulary"
    repo.save_vocabulary(vocab_item(), topic="Food", level="beginner")
    assert recommend_next_activity(load_progress(repo)).page == "grammar"
    repo.log_activity("grammar_viewed", "x")
    assert recommend_next_activity(load_progress(repo)).page == "quiz"


def test_empty_progress_is_empty(repo) -> None:
    summary = load_progress(repo)
    assert summary.is_empty
    assert summary.stats.average_score is None
