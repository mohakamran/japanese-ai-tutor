"""Optional shared-password gate for deployed instances.

When ``APP_PASSWORD`` is set, visitors must enter it before using the app. This
is a simple access barrier for a personal deployment — it is *not* a multi-user
account system and does not separate one learner's data from another's.
"""

from __future__ import annotations

import hmac
import logging

import streamlit as st

from config.settings import Settings

logger = logging.getLogger(__name__)

_AUTH_KEY = "_jt_authenticated"
_ATTEMPTS_KEY = "_jt_auth_attempts"
MAX_ATTEMPTS = 5


def require_password(settings: Settings) -> None:
    """Stop the script until the correct password is entered (no-op if unset)."""
    if settings.app_password is None or st.session_state.get(_AUTH_KEY):
        return

    st.markdown("## Japanese AI Tutor")
    attempts = st.session_state.get(_ATTEMPTS_KEY, 0)
    if attempts >= MAX_ATTEMPTS:
        st.error("Too many incorrect attempts. Reload the page to try again later.")
        st.stop()

    with st.form("login", clear_on_submit=True):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter", type="primary")
    if submitted:
        expected = settings.app_password.get_secret_value().encode()
        if hmac.compare_digest(password.encode(), expected):
            st.session_state[_AUTH_KEY] = True
            st.session_state.pop(_ATTEMPTS_KEY, None)
            st.rerun()
        st.session_state[_ATTEMPTS_KEY] = attempts + 1
        logger.warning("Failed password attempt")
        st.error("Incorrect password.")
    st.stop()
