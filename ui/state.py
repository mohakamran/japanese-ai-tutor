"""Session-state helpers.

Session state holds *temporary* UI state only (current quiz, conversation,
generated results). Anything that must survive a restart goes to the database.

Input widgets use keys starting with ``keep_`` together with Streamlit's
``persist_state="session"`` (see :data:`PERSIST`), so their values survive
reruns *and* switching to another page and back.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# Pass as **PERSIST to input widgets whose values should survive page switches.
PERSIST: dict[str, Any] = {"persist_state": "session"}

# Widget keys whose defaults come from learner preferences.
PREFERENCE_DEFAULT_KEYS = (
    "keep_vocab_level",
    "keep_grammar_level",
    "keep_quiz_level",
    "keep_quiz_difficulty",
    "keep_correction_level",
    "keep_conv_level",
    "keep_conv_corrections",
)


def default(key: str, value: Any) -> None:
    """Set an initial widget value once, without overriding the learner's choice."""
    if key not in st.session_state:
        st.session_state[key] = value


def reset_preference_defaults() -> None:
    """After preferences change, let preference-driven widgets pick up new defaults."""
    for key in PREFERENCE_DEFAULT_KEYS:
        st.session_state.pop(key, None)
