"""Login state for the current browser session.

* The logged-in user's id lives in Streamlit session state (server-side).
* "Keep me signed in" stores a random token in a ``jt_session`` cookie. Only a
  SHA-256 hash of the token is kept in the database, and it expires after
  ``SESSION_DAYS``. On a new page load the cookie restores the login.
"""

from __future__ import annotations

import json
import logging

import streamlit as st

from core.errors import DatabaseError
from database.models import User
from features import accounts as account_features

logger = logging.getLogger(__name__)

COOKIE_NAME = "jt_session"
USER_KEY = "_jt_user_id"
TOKEN_KEY = "_jt_session_token"  # noqa: S105 — a session-state key name, not a secret
_COOKIE_CHECKED = "_jt_cookie_checked"
_PENDING_COOKIE = "_jt_pending_cookie"  # ("set", token, seconds) or ("clear",)
# Session keys that survive login/logout (e.g. the optional site password gate).
_PRESERVED_PREFIXES = ("_jt_authenticated", "_jt_auth_attempts")


def _accounts():
    from ui.services import get_accounts  # local import: ui.services imports this module

    return get_accounts()


def _reset_session_state() -> None:
    for key in list(st.session_state.keys()):
        if not str(key).startswith(_PRESERVED_PREFIXES):
            del st.session_state[key]


def restore_from_cookie() -> None:
    """Log the user in from a valid 'remember me' cookie (checked once per session)."""
    if USER_KEY in st.session_state or st.session_state.get(_COOKIE_CHECKED):
        return
    st.session_state[_COOKIE_CHECKED] = True
    try:
        token = st.context.cookies.get(COOKIE_NAME)
    except Exception:  # cookies unavailable (e.g. in tests)
        token = None
    if not isinstance(token, str) or not token:
        return
    try:
        user = account_features.resume_session(_accounts(), token)
    except DatabaseError:
        logger.warning("Could not restore session from cookie")
        return
    if user is None:
        st.session_state[_PENDING_COOKIE] = ("clear",)  # expired or revoked
        return
    st.session_state[USER_KEY] = user.id
    st.session_state[TOKEN_KEY] = token


def current_user() -> User | None:
    user_id = st.session_state.get(USER_KEY)
    if user_id is None:
        return None
    user = _accounts().get_user(user_id)
    if user is None:  # account was deleted elsewhere
        _reset_session_state()
        st.session_state[_COOKIE_CHECKED] = True
    return user


def log_in(user: User, *, remember: bool, days: int) -> None:
    """Start a fresh session for ``user`` (clears any previous user's temporary state)."""
    _reset_session_state()
    st.session_state[_COOKIE_CHECKED] = True
    st.session_state[USER_KEY] = user.id
    if remember and days > 0:
        token = account_features.start_session(_accounts(), user.id, days=days)
        st.session_state[TOKEN_KEY] = token
        st.session_state[_PENDING_COOKIE] = ("set", token, days * 86400)


def log_out() -> None:
    token = st.session_state.get(TOKEN_KEY)
    try:
        account_features.end_session(_accounts(), token)
    except DatabaseError:
        logger.warning("Could not delete the session record on logout")
    _reset_session_state()
    st.session_state[_COOKIE_CHECKED] = True
    st.session_state[_PENDING_COOKIE] = ("clear",)


def apply_cookie_changes() -> None:
    """Write or clear the session cookie in the browser, if a change is pending."""
    action = st.session_state.pop(_PENDING_COOKIE, None)
    if action is None:
        return
    if action[0] == "set":
        _, token, seconds = action
        value = f"{COOKIE_NAME}={token}; Max-Age={int(seconds)}; Path=/; SameSite=Strict"
    else:
        value = f"{COOKIE_NAME}=; Max-Age=0; Path=/; SameSite=Strict"
    # json.dumps produces a safely quoted JS string literal.
    script = (
        "<script>(function(){var c=" + json.dumps(value) + ";"
        "if(location.protocol==='https:'){c+='; Secure';}document.cookie=c;})();</script>"
    )
    st.html(script, unsafe_allow_javascript=True)
