"""Sentence Correction page."""

from __future__ import annotations

import streamlit as st

from core.constants import LEVELS, MAX_CONTEXT_LENGTH, MAX_SENTENCE_LENGTH
from core.errors import DatabaseError
from core.validation import contains_japanese
from features.correction import correct_sentence
from schemas.correction import CorrectionIssue, SentenceCorrectionResponse
from ui import components as c
from ui.services import ai_configured, get_llm, get_preferences, safe_log_activity
from ui.state import PERSIST, default

RESULT_KEY = "correction_result"

_VERDICTS = {
    "correct": ("Looks correct", "ok", "No correction needed — this is grammatical and natural."),
    "natural_but_improvable": (
        "Correct, could be more natural",
        "info",
        "This is grammatical. The suggestions below are optional improvements.",
    ),
    "needs_correction": ("Needs correction", "err", "There are mistakes worth fixing."),
    "ambiguous": (
        "Meaning unclear",
        "warn",
        "This could mean different things. Adding context helps the tutor give better feedback.",
    ),
}
_SEVERITY = {
    "error": ("Error", "err"),
    "unnatural": ("Unnatural", "warn"),
    "stylistic": ("Optional", "info"),
}


def render() -> None:
    c.page_header(
        "Sentence Correction",
        "添削 · Tensaku",
        "Write a sentence in Japanese and get feedback on grammar, word choice and naturalness.",
        mark="直",
    )
    try:
        prefs = get_preferences()
    except DatabaseError as exc:
        c.show_error(exc)
        return
    configured = ai_configured()
    if not configured:
        c.ai_setup_notice()

    default("keep_correction_level", prefs.proficiency_level)
    with st.form("correction_form"):
        st.text_area(
            "Your Japanese sentence",
            key="keep_correction_sentence",
            max_chars=MAX_SENTENCE_LENGTH,
            height=100,
            placeholder="例：わたしは昨日すしを食べるました。",
            **PERSIST,
        )
        col1, col2 = st.columns([2, 1])
        col1.text_input(
            "What did you mean to say? (optional, in English)",
            key="keep_correction_context",
            max_chars=MAX_CONTEXT_LENGTH,
            placeholder="e.g. I ate sushi yesterday — talking to a friend",
            **PERSIST,
        )
        col2.selectbox(
            "Proficiency level",
            list(LEVELS),
            format_func=LEVELS.get,
            key="keep_correction_level",
            **PERSIST,
        )
        submitted = st.form_submit_button(
            "Check my sentence",
            type="primary",
            disabled=not configured,
            icon=":material/spellcheck:",
        )
    st.caption(
        "Tip: Context helps. Japanese sentences can be correct but sound different depending "
        "on who you are talking to."
    )

    if submitted:
        sentence = st.session_state.get("keep_correction_sentence", "")
        if sentence.strip() and not contains_japanese(sentence):
            st.info(
                "Your sentence has no Japanese characters. The tutor will still try to "
                "help, but feedback works best on Japanese script.",
                icon=":material/info:",
            )
        result = c.call_safely(
            "Checking your sentence…",
            correct_sentence,
            get_llm(),
            sentence=sentence,
            level=st.session_state["keep_correction_level"],
            context=st.session_state.get("keep_correction_context"),
            style=prefs.explanation_style,
        )
        if result:
            st.session_state[RESULT_KEY] = result
            # Only a generic description is logged — never the learner's sentence.
            safe_log_activity("sentence_checked", "Checked a Japanese sentence")

    result: SentenceCorrectionResponse | None = st.session_state.get(RESULT_KEY)
    if result is None:
        c.empty_state(
            "直",
            "Ready when you are",
            "Type a sentence above. Mistakes are welcome — that is how you learn!",
        )
        return
    _render_result(result, prefs.romaji_enabled)


def _issues(title: str, issues: list[CorrectionIssue]) -> None:
    if not issues:
        return
    st.markdown(f"##### {title}")
    for issue in issues:
        name, kind = _SEVERITY[issue.severity]
        c.card(
            c.badge(name, kind)
            + c.jp_markup(issue.fragment, size="sm")
            + c.text("→ " + issue.suggestion)
            + c.text(issue.explanation, muted=True)
        )


def _render_result(r: SentenceCorrectionResponse, show_romaji: bool) -> None:
    title, kind, summary = _VERDICTS[r.verdict]
    c.ai_notice()
    c.card(
        c.badge(title, kind)
        + c.text(summary, muted=True)
        + c.label("Your sentence")
        + c.jp_markup(r.original_sentence, size="sm"),
        variant="accent",
    )
    if r.clarification_question:
        st.warning(
            f"**Question from your tutor:** {r.clarification_question}", icon=":material/help:"
        )
    if r.assumptions:
        st.caption(f"Assumption: {r.assumptions}")

    c.card(
        c.label("Corrected sentence" if r.corrected_sentence else "Reading and meaning")
        + c.jp_markup(
            r.corrected_sentence or r.original_sentence,
            reading=r.reading,
            romaji=r.romaji,
            english=r.english_translation,
            show_romaji=show_romaji,
        )
    )
    _issues("Grammar", r.grammar_issues)
    _issues("Word choice", r.word_choice_issues)
    if r.natural_alternative:
        c.card(
            c.label("A more natural alternative")
            + c.jp_markup(
                r.natural_alternative,
                romaji=r.natural_alternative_romaji,
                show_romaji=show_romaji,
                size="sm",
            ),
            variant="paper",
        )
    c.card(c.label("Learning tip") + c.text(r.learning_tip), variant="paper")
