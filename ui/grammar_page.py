"""Grammar Tutor page: ask questions, follow up, save lessons, and practise."""

from __future__ import annotations

import streamlit as st

from core.constants import GRAMMAR_TOPICS, LEVELS, MAX_GRAMMAR_QUESTION_LENGTH, MAX_TOPIC_LENGTH
from core.errors import DatabaseError, TutorError
from database.models import Preferences
from features import grammar
from features.quiz import QuizSession, generate_quiz
from schemas.grammar import GrammarLessonResponse
from ui import components as c
from ui.navigation import switch_to
from ui.services import ai_configured, get_llm, get_preferences, get_repository, safe_log_activity
from ui.state import PERSIST, default

HISTORY_KEY = "grammar_history"  # list[grammar.GrammarTurn]
_CLEAR_FLAG = "_grammar_clear_question"
ANY_TOPIC = "Any topic"
_REGISTER_BADGE = {"formal": "info", "casual": "warn", "neutral": "ai"}


def render() -> None:
    c.page_header(
        "Grammar Tutor",
        "文法 · Bunpō",
        "Ask any Japanese grammar question in English and get a structured explanation.",
    )
    try:
        prefs = get_preferences()
    except DatabaseError as exc:
        c.show_error(exc)
        return
    configured = ai_configured()
    if not configured:
        c.ai_setup_notice()

    history: list[grammar.GrammarTurn] = st.session_state.get(HISTORY_KEY, [])

    default("keep_grammar_level", prefs.proficiency_level)
    default("keep_grammar_topic", ANY_TOPIC)
    if st.session_state.pop(_CLEAR_FLAG, False):
        st.session_state["keep_grammar_question"] = ""

    with st.form("grammar_form"):
        st.text_area(
            "Ask a follow-up or a new question" if history else "Your grammar question",
            key="keep_grammar_question",
            max_chars=MAX_GRAMMAR_QUESTION_LENGTH,
            height=110,
            placeholder="e.g. What is the difference between は and が?  "
            "/  When do I use て-form?  /  How do I say “I want to…”?",
            **PERSIST,
        )
        col1, col2 = st.columns(2)
        col1.selectbox(
            "Proficiency level",
            list(LEVELS),
            format_func=LEVELS.get,
            key="keep_grammar_level",
            **PERSIST,
        )
        col2.selectbox(
            "Topic (optional)", [ANY_TOPIC, *GRAMMAR_TOPICS], key="keep_grammar_topic", **PERSIST
        )
        submitted = st.form_submit_button(
            "Explain Grammar",
            type="primary",
            disabled=not configured,
            icon=":material/auto_awesome:",
        )

    if history:
        info, reset = st.columns([3, 1])
        info.caption("Follow-up mode: the tutor remembers your last few questions in this session.")
        if reset.button("Start a new topic", icon=":material/restart_alt:", width="stretch"):
            st.session_state[HISTORY_KEY] = []
            st.rerun()

    if submitted:
        _ask(prefs, history)
        history = st.session_state.get(HISTORY_KEY, [])

    if not history:
        c.empty_state(
            "文",
            "Ask your first grammar question",
            "Questions can be broad (“How do particles work?”) or specific "
            "(“Why is it 好きです and not 好きます?”).",
        )
    else:
        latest = history[-1]
        _render_lesson(latest.lesson, prefs.romaji_enabled)
        _render_lesson_actions(latest, prefs)
        if len(history) > 1:
            with st.expander(f"Earlier in this session ({len(history) - 1})"):
                for turn in reversed(history[:-1]):
                    st.markdown(f"**Q:** {c.esc(turn.question)}")
                    st.markdown(f"**{c.esc(turn.lesson.title)}** — {c.esc(turn.lesson.pattern)}")
                    st.caption(grammar.summarize_lesson(turn.lesson).split("Explanation: ")[-1])
                    st.divider()

    _render_saved_lessons(prefs)


def _ask(prefs: Preferences, history: list[grammar.GrammarTurn]) -> None:
    question = st.session_state.get("keep_grammar_question", "")
    level = st.session_state["keep_grammar_level"]
    topic = st.session_state["keep_grammar_topic"]
    lesson = c.call_safely(
        "Preparing your explanation…",
        grammar.explain_grammar,
        get_llm(),
        question=question,
        level=level,
        history=history,
        topic=None if topic == ANY_TOPIC else topic,
        style=prefs.explanation_style,
    )
    if lesson is None:
        return
    turn = grammar.GrammarTurn(question=question.strip(), level=level, lesson=lesson)
    st.session_state[HISTORY_KEY] = grammar.append_turn(history, turn)
    st.session_state[_CLEAR_FLAG] = True
    safe_log_activity("grammar_viewed", f"Grammar: {lesson.title}")
    st.rerun()


def _render_lesson(lesson: GrammarLessonResponse, show_romaji: bool) -> None:
    c.ai_notice()
    c.card(
        f'<div class="jt-title" style="font-size:1.4rem">{c.esc(lesson.title)}</div>'
        + c.label("Pattern")
        + c.jp_markup(lesson.pattern, size="sm")
        + c.label("How to form it")
        + c.text(lesson.formation),
        variant="accent",
    )
    c.card(c.label("Explanation") + c.text(lesson.explanation))
    if lesson.uncertainty_note:
        st.info(lesson.uncertainty_note, icon=":material/help:")

    st.markdown("##### Examples")
    cols = st.columns(2, gap="medium")
    for i, ex in enumerate(lesson.examples):
        with cols[i % 2]:
            c.card(
                c.badge(ex.speech_register, _REGISTER_BADGE.get(ex.speech_register, "ai"))
                + c.jp_markup(
                    ex.japanese,
                    reading=ex.reading,
                    romaji=ex.romaji,
                    english=ex.english,
                    show_romaji=show_romaji,
                    size="sm",
                )
            )

    if lesson.usage_notes:
        st.markdown("##### Usage notes")
        c.card("".join(c.text("• " + note) for note in lesson.usage_notes))

    if lesson.common_mistakes:
        st.markdown("##### Common mistakes")
        for m in lesson.common_mistakes:
            c.card(
                c.badge("Incorrect", "err")
                + c.jp_markup(m.incorrect, size="sm")
                + c.badge("Correct", "ok")
                + c.jp_markup(m.correct, size="sm")
                + c.text(m.explanation, muted=True)
            )

    if lesson.formality_notes:
        st.markdown("##### Formal vs. casual")
        c.card(c.text(lesson.formality_notes))

    if lesson.related_patterns:
        st.markdown("##### Related patterns")
        c.html_block("".join(c.badge(p, "info") for p in lesson.related_patterns))


def _render_lesson_actions(turn: grammar.GrammarTurn, prefs: Preferences) -> None:
    configured = ai_configured()
    save_col, quiz_col = st.columns(2)
    if save_col.button("Save this lesson", icon=":material/bookmark_add:", width="stretch"):
        try:
            created = grammar.save_grammar_lesson(get_repository(), turn)
        except TutorError as exc:
            c.show_error(exc)
        else:
            st.toast("Lesson saved." if created else "This lesson is already saved.")
    if quiz_col.button(
        "Generate Practice Quiz",
        icon=":material/quiz:",
        type="primary",
        disabled=not configured,
        width="stretch",
        help="Creates a 5-question grammar quiz on this pattern. Replaces any unfinished quiz.",
    ):
        topic = turn.lesson.title[:MAX_TOPIC_LENGTH]
        questions = c.call_safely(
            "Writing practice questions…",
            generate_quiz,
            get_llm(),
            topic=topic,
            level=turn.level,
            question_count=5,
            quiz_type="grammar",
            difficulty=prefs.preferred_difficulty,
            style=prefs.explanation_style,
        )
        if questions:
            st.session_state["quiz_session"] = QuizSession(
                topic=topic,
                quiz_type="grammar",
                level=turn.level,
                difficulty=prefs.preferred_difficulty,
                questions=questions,
            )
            switch_to("quiz")


def _render_saved_lessons(prefs: Preferences) -> None:
    try:
        lessons = get_repository().list_grammar_lessons()
    except DatabaseError as exc:
        c.show_error(exc)
        return
    with st.expander(f"Saved lessons ({len(lessons)})", icon=":material/bookmarks:"):
        if not lessons:
            st.caption("Lessons you save appear here so you can review them later.")
            return
        options = {
            f"{rec.title} · {LEVELS[rec.proficiency_level].split(' (')[0]}": rec for rec in lessons
        }
        choice = st.selectbox("Choose a lesson", list(options), key="grammar_saved_choice")
        record = options[choice]
        st.caption(f"Your question: {record.question}")
        try:
            lesson = grammar.load_saved_lesson(record.lesson_json)
        except ValueError:
            st.error("This saved lesson could not be read. You can delete it below.")
        else:
            _render_lesson(lesson, prefs.romaji_enabled)
        if st.button(
            "Delete this saved lesson", icon=":material/delete:", key=f"delete_lesson_{record.id}"
        ):
            try:
                get_repository().delete_grammar_lesson(record.id)
            except DatabaseError as exc:
                c.show_error(exc)
            else:
                st.rerun()
