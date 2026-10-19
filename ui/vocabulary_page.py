"""Vocabulary page: generate words, save them, browse them, and review with flashcards."""

from __future__ import annotations

import streamlit as st

from core.constants import (
    LEVELS,
    MAX_TOPIC_LENGTH,
    MAX_VOCABULARY_COUNT,
    MIN_SAVED_WORDS_FOR_QUIZ,
    MIN_VOCABULARY_COUNT,
    VOCABULARY_TOPICS,
)
from core.errors import DatabaseError, TutorError
from database.models import Preferences, SavedWord
from features import quiz as quiz_features
from features import vocabulary as vocab
from schemas.vocabulary import VocabularyItem
from ui import components as c
from ui.navigation import switch_to
from ui.services import ai_configured, get_llm, get_preferences, get_repository, safe_log_activity
from ui.state import PERSIST, default

RESULTS_KEY = "vocab_results"  # {"topic", "level", "items": list[VocabularyItem]}
DECK_KEY = "vocab_deck"  # {"ids": list[int], "position": int, "revealed": bool, "stats": {...}}


def render() -> None:
    c.page_header(
        "Vocabulary",
        "語彙 · Goi",
        "Generate useful words for any topic, save them, and review them.",
    )
    try:
        prefs = get_preferences()
    except DatabaseError as exc:
        c.show_error(exc)
        return

    generate_tab, saved_tab, review_tab = st.tabs(
        ["Generate words", "My vocabulary", "Flashcard review"]
    )
    with generate_tab:
        _render_generate(prefs)
    with saved_tab:
        _render_saved(prefs)
    with review_tab:
        _render_review(prefs)


# ------------------------------------------------------------------ generate


def _render_generate(prefs: Preferences) -> None:
    configured = ai_configured()
    if not configured:
        c.ai_setup_notice()

    default("keep_vocab_topic", VOCABULARY_TOPICS[0])
    default("keep_vocab_level", prefs.proficiency_level)
    default("keep_vocab_count", 8)

    with st.form("vocab_form", border=True):
        col1, col2 = st.columns([2, 1])
        col1.selectbox("Topic", VOCABULARY_TOPICS, key="keep_vocab_topic", **PERSIST)
        col2.selectbox(
            "Proficiency level",
            list(LEVELS),
            format_func=LEVELS.get,
            key="keep_vocab_level",
            **PERSIST,
        )
        st.text_input(
            "Or type your own topic (optional)",
            key="keep_vocab_custom",
            **PERSIST,
            max_chars=MAX_TOPIC_LENGTH,
            placeholder="e.g. Japanese festivals, cooking verbs, anime phrases",
        )
        st.slider(
            "Number of words",
            MIN_VOCABULARY_COUNT,
            MAX_VOCABULARY_COUNT,
            key="keep_vocab_count",
            **PERSIST,
        )
        submitted = st.form_submit_button(
            "Generate Vocabulary",
            type="primary",
            disabled=not configured,
            icon=":material/auto_awesome:",
        )

    if submitted:
        topic = (st.session_state.get("keep_vocab_custom") or "").strip() or st.session_state[
            "keep_vocab_topic"
        ]
        level = st.session_state["keep_vocab_level"]
        items = c.call_safely(
            "Creating your vocabulary list…",
            vocab.generate_vocabulary,
            get_llm(),
            topic=topic,
            level=level,
            count=st.session_state["keep_vocab_count"],
            style=prefs.explanation_style,
        )
        if items:
            st.session_state[RESULTS_KEY] = {"topic": topic, "level": level, "items": items}
            safe_log_activity("vocabulary_generated", f"Generated {len(items)} words: {topic}")

    results = st.session_state.get(RESULTS_KEY)
    if not results:
        c.empty_state(
            "語",
            "No words generated yet",
            "Choose a topic and level, then press Generate Vocabulary.",
        )
        return
    _render_results(results, prefs)


def _render_results(results: dict, prefs: Preferences) -> None:
    items: list[VocabularyItem] = results["items"]
    try:
        saved = get_repository().saved_vocabulary_keys()
    except DatabaseError as exc:
        c.show_error(exc)
        saved = set()

    head, action = st.columns([3, 1])
    with head:
        st.markdown(f"#### {c.esc(results['topic'])} · {len(items)} words")
        c.ai_notice()
    with action:
        unsaved = [i for i in items if vocab.vocabulary_key(i) not in saved]
        if st.button(
            "Save all", disabled=not unsaved, width="stretch", icon=":material/bookmark_add:"
        ):
            _save_items(unsaved, results)
            st.rerun()

    cols = st.columns(2, gap="medium")
    for i, item in enumerate(items):
        with cols[i % 2]:
            _vocab_card(item, prefs.romaji_enabled)
            is_saved = vocab.vocabulary_key(item) in saved
            if st.button(
                "Saved" if is_saved else "Save to my vocabulary",
                key=f"save_vocab_{i}_{item.word}",
                disabled=is_saved,
                icon=":material/bookmark_added:" if is_saved else ":material/bookmark_add:",
            ):
                _save_items([item], results)
                st.rerun()


def _save_items(items: list[VocabularyItem], results: dict) -> None:
    repo = get_repository()
    count = 0
    for item in items:
        try:
            if vocab.save_vocabulary_item(
                repo, item, topic=results["topic"], level=results["level"]
            ):
                count += 1
        except TutorError as exc:
            c.show_error(exc)
            return
    st.toast(f"Saved {count} word{'s' if count != 1 else ''}.", icon=":material/bookmark:")


def _vocab_card(item: VocabularyItem | SavedWord, show_romaji: bool) -> None:
    markup = (
        c.badge(item.part_of_speech, "info")
        + c.jp_markup(item.word, reading=item.reading, romaji=item.romaji, show_romaji=show_romaji)
        + f'<div class="jt-en"><strong>{c.esc(item.meaning)}</strong></div>'
        + c.label("Example")
        + c.jp_markup(
            item.example_sentence,
            reading=item.example_reading,
            romaji=item.example_romaji,
            english=item.example_translation,
            show_romaji=show_romaji,
            size="sm",
        )
    )
    if item.usage_note:
        markup += c.label("Note") + c.text(item.usage_note, muted=True)
    c.card(markup)


# --------------------------------------------------------------------- saved


def _load_saved() -> list[SavedWord] | None:
    try:
        return get_repository().list_saved_vocabulary()
    except DatabaseError as exc:
        c.show_error(exc)
        return None


def _render_saved(prefs: Preferences) -> None:
    words = _load_saved()
    if words is None:
        return
    if not words:
        c.empty_state(
            "📒",
            "Your vocabulary list is empty",
            "Generate words in the first tab and press “Save to my vocabulary”.",
        )
        return

    topics = sorted({w.topic for w in words})
    col1, col2 = st.columns([2, 1])
    search = col1.text_input(
        "Search",
        key="keep_vocab_search",
        **PERSIST,
        placeholder="Search Japanese, reading, romaji or English",
    )
    topic = col2.selectbox("Topic", ["All topics", *topics], key="vocab_filter")

    needle = search.strip().casefold()
    filtered = [
        w
        for w in words
        if (topic == "All topics" or w.topic == topic)
        and (
            not needle
            or any(needle in s.casefold() for s in (w.word, w.reading, w.romaji, w.meaning))
        )
    ]
    st.caption(f"Showing {len(filtered)} of {len(words)} saved words.")
    st.dataframe(
        [
            {
                "Japanese": w.word,
                "Reading": w.reading,
                **({"Romaji": w.romaji} if prefs.romaji_enabled else {}),
                "Meaning": w.meaning,
                "Part of speech": w.part_of_speech,
                "Topic": w.topic,
                "Reviews": w.review_count,
                "Remembered": f"{w.correct_count}/{w.review_count}" if w.review_count else "—",
            }
            for w in filtered
        ],
        width="stretch",
        hide_index=True,
    )

    practice, manage = st.columns(2, gap="large")
    with practice:
        st.markdown("##### Practise")
        enough = len({w.meaning for w in words}) >= MIN_SAVED_WORDS_FOR_QUIZ
        if not enough:
            st.caption(f"Save at least {MIN_SAVED_WORDS_FOR_QUIZ} words to unlock a practice quiz.")
        if st.button(
            "Quiz me on my saved words", disabled=not enough, icon=":material/quiz:", type="primary"
        ):
            try:
                session = quiz_features.build_saved_vocabulary_quiz(
                    words, question_count=min(10, len(words)), level=prefs.proficiency_level
                )
            except TutorError as exc:
                c.show_error(exc)
            else:
                st.session_state["quiz_session"] = session
                switch_to("quiz")
    with manage:
        st.markdown("##### Remove words")
        labels = {f"{w.word} — {w.meaning}": w.vocabulary_id for w in filtered}
        chosen = st.multiselect("Select words to remove", list(labels), key="vocab_remove")
        confirm = st.checkbox(
            "I understand this also deletes their review history", key="vocab_remove_confirm"
        )
        if st.button(
            "Remove selected", disabled=not (chosen and confirm), icon=":material/delete:"
        ):
            try:
                n = get_repository().delete_saved_vocabulary([labels[x] for x in chosen])
            except DatabaseError as exc:
                c.show_error(exc)
            else:
                st.session_state.pop(DECK_KEY, None)
                st.toast(f"Removed {n} word{'s' if n != 1 else ''}.")
                st.rerun()


# -------------------------------------------------------------------- review


def _render_review(prefs: Preferences) -> None:
    words = _load_saved()
    if words is None:
        return
    if not words:
        c.empty_state(
            "復",
            "Nothing to review yet",
            "Save some vocabulary first; your flashcards will appear here.",
        )
        return

    by_id = {w.vocabulary_id: w for w in words}
    deck = st.session_state.get(DECK_KEY)
    if deck is not None:
        deck["ids"] = [i for i in deck["ids"] if i in by_id]  # words may have been removed
    if not deck or not deck["ids"]:
        st.markdown(
            "Flashcards show the Japanese first. Try to recall the meaning, then reveal the "
            "answer and mark how you did. Words you find difficult come up first next time."
        )
        size = st.slider(
            "Cards in this session", 1, max(2, min(30, len(words))), min(10, len(words))
        )
        if st.button("Start review", type="primary", icon=":material/style:"):
            st.session_state[DECK_KEY] = {
                "ids": vocab.build_review_deck(words, size=size),
                "position": 0,
                "revealed": False,
                "known": 0,
                "again": 0,
            }
            st.rerun()
        return

    position = deck["position"]
    if position >= len(deck["ids"]):
        total = deck["known"] + deck["again"]
        c.card(
            c.label("Session complete")
            + c.text(f"You remembered {deck['known']} of {total} cards. お疲れさまでした！"),
            variant="accent",
        )
        if st.button("Start another session", type="primary"):
            st.session_state.pop(DECK_KEY, None)
            st.rerun()
        return

    word = by_id[deck["ids"][position]]
    st.progress(position / len(deck["ids"]), text=f"Card {position + 1} of {len(deck['ids'])}")
    if not deck["revealed"]:
        c.card(
            c.label("What does this mean?")
            + c.jp_markup(word.word, size="lg")
            + (
                c.text("Reading: " + word.reading, muted=True)
                if st.session_state.get("keep_deck_hint")
                else ""
            ),
            variant="paper",
        )
        st.toggle("Show reading as a hint", key="keep_deck_hint", **PERSIST)
        if st.button("Reveal answer", type="primary", icon=":material/visibility:"):
            deck["revealed"] = True
            st.rerun()
        return

    _vocab_card(word, prefs.romaji_enabled)
    knew, again = st.columns(2)
    if knew.button("I knew it", type="primary", width="stretch", icon=":material/check:"):
        _answer_card(deck, word, remembered=True)
    if again.button("Still learning", width="stretch", icon=":material/replay:"):
        _answer_card(deck, word, remembered=False)


def _answer_card(deck: dict, word: SavedWord, *, remembered: bool) -> None:
    try:
        vocab.record_review(get_repository(), word.vocabulary_id, remembered=remembered)
    except TutorError as exc:
        c.show_error(exc)
        return
    deck["known" if remembered else "again"] += 1
    deck["position"] += 1
    deck["revealed"] = False
    st.rerun()
