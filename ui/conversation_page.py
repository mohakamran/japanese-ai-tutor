"""Conversation Practice page: role-play scenarios with an AI conversation partner.

Conversations live in session state only and are not written to the database;
they disappear when the browser session ends or the learner restarts.
"""

from __future__ import annotations

import streamlit as st

from core.constants import CONVERSATION_SCENARIOS, LEVELS, MAX_CHAT_MESSAGE_LENGTH
from core.errors import DatabaseError
from features import conversation as conv
from schemas.conversation import ConversationResponse
from ui import components as c
from ui.services import ai_configured, get_llm, get_preferences, safe_log_activity
from ui.state import PERSIST, default

CONVERSATION_KEY = "conversation"  # conv.Conversation
EXPLAIN_KEY = "conversation_explanations"  # {reply text: SentenceExplanationResponse}


def render() -> None:
    c.page_header(
        "Conversation Practice",
        "会話 · Kaiwa",
        "Practise real-life conversations. Reply in Japanese — mistakes are part of learning!",
        mark="話",
    )
    try:
        prefs = get_preferences()
    except DatabaseError as exc:
        c.show_error(exc)
        return
    configured = ai_configured()
    if not configured:
        c.ai_setup_notice()

    default("keep_conv_scenario", "daily")
    default("keep_conv_level", prefs.proficiency_level)
    default("keep_conv_corrections", prefs.conversation_corrections)
    default("keep_conv_romaji", prefs.romaji_enabled)

    col1, col2 = st.columns(2)
    col1.selectbox(
        "Scenario",
        list(CONVERSATION_SCENARIOS),
        format_func=CONVERSATION_SCENARIOS.get,
        key="keep_conv_scenario",
        **PERSIST,
    )
    col2.selectbox(
        "Proficiency level", list(LEVELS), format_func=LEVELS.get, key="keep_conv_level", **PERSIST
    )
    col1, col2, col3 = st.columns([1, 1, 1])
    col1.toggle("Correct my mistakes", key="keep_conv_corrections", **PERSIST)
    col2.toggle("Show romaji", key="keep_conv_romaji", **PERSIST)

    conversation: conv.Conversation | None = st.session_state.get(CONVERSATION_KEY)
    scenario = st.session_state["keep_conv_scenario"]
    level = st.session_state["keep_conv_level"]
    label = "Restart conversation" if conversation else "Start conversation"
    if col3.button(
        label,
        type="primary",
        disabled=not configured,
        width="stretch",
        icon=":material/restart_alt:" if conversation else ":material/play_arrow:",
    ):
        new = c.call_safely(
            "Starting the conversation…",
            conv.start_conversation,
            get_llm(),
            scenario=scenario,
            level=level,
            style=prefs.explanation_style,
        )
        if new:
            st.session_state[CONVERSATION_KEY] = new
            st.session_state[EXPLAIN_KEY] = {}
            safe_log_activity(
                "conversation_started", f"Conversation: {CONVERSATION_SCENARIOS[scenario]}"
            )
            st.rerun()

    if conversation is None:
        c.empty_state(
            "話",
            "Choose a scenario and press Start",
            "Your conversation partner will speak first. Answer in Japanese — even a few words "
            "is great. Conversations are kept only for this browser session.",
        )
        return

    if (conversation.scenario, conversation.level) != (scenario, level):
        st.info(
            "You changed the scenario or level. Press **Restart conversation** to apply it.",
            icon=":material/info:",
        )
    st.caption(
        f"Scenario: {CONVERSATION_SCENARIOS[conversation.scenario]} · {LEVELS[conversation.level]}"
    )

    show_romaji = st.session_state["keep_conv_romaji"]
    explanations = st.session_state.setdefault(EXPLAIN_KEY, {})
    for index, turn in enumerate(conversation.turns):
        if turn.role == "learner":
            with st.chat_message("user"):
                st.markdown(c.esc(turn.text), unsafe_allow_html=True)
        else:
            with st.chat_message("assistant", avatar="🎎"):
                _render_tutor_turn(
                    index,
                    turn.response,
                    show_romaji,
                    explanations,
                    prefs.explanation_style,
                    conversation.level,
                )

    message = st.chat_input(
        "Reply in Japanese…", max_chars=MAX_CHAT_MESSAGE_LENGTH, disabled=not configured
    )
    if message:
        response = c.call_safely(
            "Your partner is replying…",
            conv.send_message,
            get_llm(),
            conversation,
            message,
            corrections_enabled=st.session_state["keep_conv_corrections"],
            style=prefs.explanation_style,
        )
        if response:
            st.rerun()


def _render_tutor_turn(
    index: int,
    r: ConversationResponse | None,
    show_romaji: bool,
    explanations: dict,
    style: str,
    level: str,
) -> None:
    if r is None:
        return
    if r.feedback and r.feedback.has_mistakes and r.feedback.corrected_message:
        c.card(
            c.badge("Feedback on your message", "warn")
            + c.jp_markup(r.feedback.corrected_message, size="sm")
            + (c.text(r.feedback.explanation, muted=True) if r.feedback.explanation else ""),
            variant="paper",
        )
    elif r.feedback and not r.feedback.has_mistakes:
        c.html_block(c.badge("Your message looked good ✓", "ok"))

    c.html_block(
        c.jp_markup(
            r.reply_japanese,
            reading=r.reply_reading,
            romaji=r.reply_romaji,
            show_romaji=show_romaji,
        )
    )
    with st.expander("English & notes"):
        st.markdown(c.text(r.reply_english), unsafe_allow_html=True)
        if r.vocabulary_notes:
            st.markdown(
                "".join(
                    c.text(f"• {n.japanese}（{n.reading}）— {n.english}")
                    for n in r.vocabulary_notes
                ),
                unsafe_allow_html=True,
            )
        if r.suggested_response:
            st.markdown(
                c.label("You could reply") + c.jp_markup(r.suggested_response, size="sm"),
                unsafe_allow_html=True,
            )

    if r.reply_japanese in explanations:
        e = explanations[r.reply_japanese]
        markup = c.label("Sentence breakdown")
        for seg in e.segments:
            markup += (
                f'<div class="jt-text"><span class="jt-jp jt-sm" lang="ja">{c.esc(seg.japanese)}'
                f'</span> <span class="jt-reading">{c.esc(seg.reading)}</span>'
                + (f' <span class="jt-romaji">{c.esc(seg.romaji)}</span>' if show_romaji else "")
                + f" — <strong>{c.esc(seg.role)}</strong>: {c.esc(seg.meaning)}</div>"
            )
        markup += c.label("Grammar points") + "".join(c.text("• " + g) for g in e.grammar_points)
        markup += c.label("Politeness") + c.text(e.politeness, muted=True)
        c.card(markup, variant="paper")
    elif st.button(
        "Explain this sentence",
        key=f"conv_explain_{index}",
        icon=":material/lightbulb:",
        type="tertiary",
    ):
        result = c.call_safely(
            "Breaking it down…",
            conv.explain_sentence,
            get_llm(),
            sentence=r.reply_japanese,
            level=level,
            style=style,
        )
        if result:
            explanations[r.reply_japanese] = result
            st.rerun()
