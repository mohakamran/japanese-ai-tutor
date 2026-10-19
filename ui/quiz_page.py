"""Quiz Center: generate a quiz, answer one question at a time, submit, and review.

Before submission this page renders only ``QuizSession.public_questions()``, which
contains no answer keys or explanations. Answers live on the ``QuizSession``
object (not only in widget state), so switching pages does not lose them.
"""

from __future__ import annotations

import logging

import streamlit as st

from core.constants import (
    DIFFICULTIES,
    LEVELS,
    MAX_QUIZ_QUESTIONS,
    MAX_TOPIC_LENGTH,
    MIN_QUIZ_QUESTIONS,
    QUESTION_TYPES,
    QUIZ_TOPICS,
    QUIZ_TYPES,
    SAVED_VOCABULARY_QUIZ_TYPE,
)
from core.errors import DatabaseError, TutorError
from database.models import Preferences
from features import quiz as quiz_features
from features.quiz import PublicQuestion, QuizSession
from ui import components as c
from ui.services import ai_configured, get_llm, get_preferences, get_repository
from ui.state import PERSIST, default

logger = logging.getLogger(__name__)

SESSION_KEY = "quiz_session"
EXPLANATIONS_KEY = "quiz_ai_explanations"  # {(quiz_id, index): AnswerExplanationResponse}
LETTERS = "ABCDEF"


def render() -> None:
    c.page_header(
        "Quiz Center",
        "試験 · Shiken",
        "Test yourself with quizzes generated for your level and topic.",
    )
    try:
        prefs = get_preferences()
    except DatabaseError as exc:
        c.show_error(exc)
        return

    session: QuizSession | None = st.session_state.get(SESSION_KEY)
    in_progress = session is not None and not session.submitted

    with st.expander("Create a new quiz", expanded=session is None, icon=":material/add_circle:"):
        _render_generator(prefs, replacing=in_progress)

    if session is None:
        c.empty_state(
            "試",
            "No quiz in progress",
            "Create a quiz above, or practise your saved words from the Vocabulary page.",
        )
    elif session.submitted:
        _render_results(session, prefs)
    else:
        _render_active_quiz(session, prefs)

    _render_past_mistakes()


# --------------------------------------------------------------- generator


def _render_generator(prefs: Preferences, *, replacing: bool) -> None:
    configured = ai_configured()
    if not configured:
        c.ai_setup_notice()

    default("keep_quiz_topic", QUIZ_TOPICS[0])
    default("keep_quiz_level", prefs.proficiency_level)
    default("keep_quiz_difficulty", prefs.preferred_difficulty)
    default("keep_quiz_type", "mixed")
    default("keep_quiz_count", 5)

    with st.form("quiz_form", border=False):
        col1, col2 = st.columns(2)
        col1.selectbox("Topic", QUIZ_TOPICS, key="keep_quiz_topic", **PERSIST)
        col2.text_input(
            "Or type your own topic (optional)",
            key="keep_quiz_custom",
            max_chars=MAX_TOPIC_LENGTH,
            placeholder="e.g. て-form, colours, train travel",
            **PERSIST,
        )
        col1, col2, col3 = st.columns(3)
        col1.selectbox(
            "Quiz type",
            list(QUIZ_TYPES),
            format_func=QUIZ_TYPES.get,
            key="keep_quiz_type",
            **PERSIST,
        )
        col2.selectbox(
            "Proficiency level",
            list(LEVELS),
            format_func=LEVELS.get,
            key="keep_quiz_level",
            **PERSIST,
        )
        col3.selectbox(
            "Difficulty",
            list(DIFFICULTIES),
            format_func=DIFFICULTIES.get,
            key="keep_quiz_difficulty",
            **PERSIST,
        )
        st.slider(
            "Number of questions",
            MIN_QUIZ_QUESTIONS,
            MAX_QUIZ_QUESTIONS,
            key="keep_quiz_count",
            **PERSIST,
        )
        if replacing:
            st.checkbox("Replace my unfinished quiz", key="quiz_replace_confirm")
        submitted = st.form_submit_button(
            "Generate Quiz",
            type="primary",
            disabled=not configured,
            icon=":material/auto_awesome:",
        )

    if not submitted:
        return
    if replacing and not st.session_state.get("quiz_replace_confirm"):
        st.warning("You have an unfinished quiz. Tick “Replace my unfinished quiz” to continue.")
        return

    ss = st.session_state
    topic = (ss.get("keep_quiz_custom") or "").strip() or ss["keep_quiz_topic"]
    questions = c.call_safely(
        "Writing your quiz…",
        quiz_features.generate_quiz,
        get_llm(),
        topic=topic,
        level=ss["keep_quiz_level"],
        question_count=ss["keep_quiz_count"],
        quiz_type=ss["keep_quiz_type"],
        difficulty=ss["keep_quiz_difficulty"],
        style=prefs.explanation_style,
    )
    if not questions:
        return
    ss[SESSION_KEY] = QuizSession(
        topic=topic,
        quiz_type=ss["keep_quiz_type"],
        level=ss["keep_quiz_level"],
        difficulty=ss["keep_quiz_difficulty"],
        questions=questions,
    )
    ss.pop("quiz_replace_confirm", None)
    if len(questions) < ss["keep_quiz_count"]:
        st.toast(
            f"{len(questions)} of {ss['keep_quiz_count']} questions passed quality checks; "
            "the rest were discarded."
        )
    st.rerun()


# ------------------------------------------------------------ active quiz


def _on_select(session: QuizSession, index: int, key: str) -> None:
    choice = st.session_state.get(key)
    try:
        session.select_answer(index, choice)
    except TutorError as exc:
        # Quiz already submitted or a stale widget; the page re-renders from session state.
        logger.debug("Ignored answer selection: %s", exc)


def _quiz_title(session: QuizSession) -> str:
    kind = (
        "Saved vocabulary practice"
        if session.quiz_type == SAVED_VOCABULARY_QUIZ_TYPE
        else QUIZ_TYPES.get(session.quiz_type, session.quiz_type)
    )
    return f"{session.topic} · {kind} · {LEVELS[session.level].split(' (')[0]}"


def _render_question(q: PublicQuestion, show_romaji: bool) -> None:
    markup = c.badge(QUESTION_TYPES.get(q.question_type, q.question_type), "info")
    markup += f'<div class="jt-text" style="font-weight:600">{c.esc(q.prompt)}</div>'
    if q.japanese_text:
        markup += c.jp_markup(
            q.japanese_text, reading=q.reading, romaji=q.romaji, show_romaji=show_romaji
        )
    c.card(markup, variant="accent")


def _render_active_quiz(session: QuizSession, prefs: Preferences) -> None:
    questions = session.public_questions()  # answer keys are NOT included
    answered = session.total - len(session.unanswered_indices())

    st.markdown(f"#### {c.esc(_quiz_title(session))}")
    if session.quiz_type != SAVED_VOCABULARY_QUIZ_TYPE:
        c.ai_notice()
    st.progress(answered / session.total, text=f"{answered} of {session.total} answered")

    q = questions[session.current_index]
    st.caption(f"Question {q.index + 1} of {session.total}")
    _render_question(q, prefs.romaji_enabled)

    key = f"quiz_{session.quiz_id}_{q.index}"
    st.radio(
        "Choose your answer",
        options=list(range(len(q.options))),
        format_func=lambda i, opts=q.options: f"{LETTERS[i]}.  {opts[i]}",
        index=session.answers.get(q.index),
        key=key,
        on_change=_on_select,
        args=(session, q.index, key),
    )

    prev_col, next_col = st.columns(2)
    if prev_col.button("← Previous", disabled=session.current_index == 0, width="stretch"):
        session.go_to(session.current_index - 1)
        st.rerun()
    if next_col.button(
        "Next →", disabled=session.current_index >= session.total - 1, width="stretch"
    ):
        session.go_to(session.current_index + 1)
        st.rerun()

    # Jump straight to any question; unanswered ones are marked.
    jump = st.pills(
        "Go to question",
        options=list(range(session.total)),
        format_func=lambda i: f"{i + 1}{'' if i in session.answers else ' ·'}",
        default=session.current_index,
        key=f"quiz_jump_{session.quiz_id}_{session.current_index}",
        help="Questions marked with · are unanswered.",
    )
    if jump is not None and jump != session.current_index:
        session.go_to(jump)
        st.rerun()

    st.divider()
    unanswered = session.unanswered_indices()
    confirm = True
    if unanswered:
        numbers = ", ".join(str(i + 1) for i in unanswered)
        st.warning(f"Unanswered: question {numbers}. Unanswered questions are marked incorrect.")
        confirm = st.checkbox("Submit anyway", key=f"quiz_confirm_{session.quiz_id}")
    submit_col, abandon_col = st.columns([2, 1])
    if submit_col.button(
        "Submit quiz",
        type="primary",
        disabled=not confirm,
        width="stretch",
        icon=":material/task_alt:",
    ):
        _submit(session)
    if abandon_col.button("Abandon quiz", width="stretch", icon=":material/close:"):
        st.session_state.pop(SESSION_KEY, None)
        st.rerun()


def _submit(session: QuizSession) -> None:
    try:
        repo = get_repository()
    except DatabaseError:
        repo = None
    try:
        session.submit(repo)  # idempotent: scores and saves at most once
    except TutorError as exc:
        c.show_error(exc)
        return
    st.rerun()


# ----------------------------------------------------------------- results


def _render_results(session: QuizSession, prefs: Preferences) -> None:
    score = session.submit()  # returns the stored score; never re-scores or re-saves
    st.markdown(f"#### Results · {c.esc(_quiz_title(session))}")

    kind = "ok" if score.percent >= 80 else "warn" if score.percent >= 50 else "err"
    cols = st.columns(4)
    cols[0].metric("Score", f"{score.percent:g}%")
    cols[1].metric("Correct", score.correct)
    cols[2].metric("Incorrect", score.incorrect)
    cols[3].metric("Unanswered", score.unanswered)
    message = {
        "ok": "素晴らしい！ Excellent work.",
        "warn": "いいですね！ Good effort — review the questions you missed.",
        "err": "がんばって！ Keep going — reviewing your mistakes is the fastest way to improve.",
    }[kind]
    c.html_block(c.badge(message, kind))

    if session.save_failed:
        st.warning("Your result could not be saved to your progress history.")
        if st.button("Retry saving", icon=":material/refresh:"):
            try:
                session.persist(get_repository())
            except TutorError as exc:
                c.show_error(exc)
            st.rerun()

    only_wrong = st.toggle("Show only questions I missed", key="keep_quiz_only_wrong", **PERSIST)
    explanations = st.session_state.setdefault(EXPLANATIONS_KEY, {})
    for r in score.results:
        if only_wrong and r.is_correct:
            continue
        q = r.question
        status_badge = {
            "correct": c.badge("Correct", "ok"),
            "incorrect": c.badge("Incorrect", "err"),
            "unanswered": c.badge("Unanswered", "warn"),
        }[r.status]
        markup = status_badge + c.badge(f"Question {r.index + 1}", "ai")
        markup += f'<div class="jt-text" style="font-weight:600">{c.esc(q.prompt)}</div>'
        if q.japanese_text:
            markup += c.jp_markup(
                q.japanese_text,
                reading=q.reading,
                romaji=q.romaji,
                show_romaji=prefs.romaji_enabled,
                size="sm",
            )
        for i, option in enumerate(q.options):
            is_correct = i == q.correct_option_index
            is_selected = i == r.selected_index
            if is_correct:
                row, tag = "ok", c.badge("Your answer ✓" if is_selected else "Correct answer", "ok")
            elif is_selected:
                row, tag = "err", c.badge("Your answer", "err")
            else:
                row, tag = "", ""
            markup += (
                f'<div class="jt-option {row}"><span lang="ja">{c.esc(LETTERS[i])}. '
                f"{c.esc(option)}</span>{tag}</div>"
            )
        markup += c.label("Explanation") + c.text(q.explanation, muted=True)
        c.card(markup)

        if r.status == "incorrect" and session.quiz_type != SAVED_VOCABULARY_QUIZ_TYPE:
            exp_key = (session.quiz_id, r.index)
            if exp_key in explanations:
                e = explanations[exp_key]
                c.card(
                    c.label("Why the correct answer is right")
                    + c.text(e.why_correct)
                    + c.label("About your answer")
                    + c.text(e.why_learner_answer_is_wrong)
                    + c.label("Another example")
                    + c.jp_markup(
                        e.extra_example_japanese,
                        romaji=e.extra_example_romaji,
                        english=e.extra_example_english,
                        show_romaji=prefs.romaji_enabled,
                        size="sm",
                    )
                    + c.label("Tip")
                    + c.text(e.tip),
                    variant="paper",
                )
            elif st.button(
                "Explain my mistake",
                key=f"explain_{session.quiz_id}_{r.index}",
                icon=":material/lightbulb:",
                disabled=not ai_configured(),
            ):
                result = c.call_safely(
                    "Looking at your answer…",
                    quiz_features.explain_incorrect_answer,
                    get_llm(),
                    question=q,
                    selected_index=r.selected_index,
                    level=session.level,
                    style=prefs.explanation_style,
                )
                if result:
                    explanations[exp_key] = result
                    st.rerun()

    if st.button("Start a new quiz", type="primary", icon=":material/add_circle:"):
        st.session_state.pop(SESSION_KEY, None)
        st.rerun()


# ------------------------------------------------------------ past mistakes


def _render_past_mistakes() -> None:
    try:
        mistakes = get_repository().list_incorrect_responses(limit=30)
    except DatabaseError:
        return
    if not mistakes:
        return
    with st.expander(
        f"Review mistakes from past quizzes ({len(mistakes)})", icon=":material/history:"
    ):
        for attempt, r in mistakes:
            your = (
                r.options[r.selected_index]
                if r.selected_index is not None and r.selected_index < len(r.options)
                else "(unanswered)"
            )
            markup = c.badge(attempt.topic, "info") + c.badge(attempt.attempted_at[:10], "ai")
            markup += c.text(r.prompt)
            if r.japanese_text:
                markup += c.jp_markup(r.japanese_text, size="sm")
            markup += c.text(f"Your answer: {your}", muted=True)
            markup += c.text(f"Correct answer: {r.options[r.correct_index]}")
            markup += c.text(r.explanation, muted=True)
            c.card(markup)
