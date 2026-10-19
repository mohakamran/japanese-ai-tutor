"""Landing page with log-in and sign-up forms (shown when nobody is logged in)."""

from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from core.errors import TutorError
from core.security import MIN_PASSWORD_LENGTH
from features import accounts as account_features
from ui import components as c
from ui.services import get_accounts
from ui.session import log_in

_FEATURES = [
    (
        "語",
        "Vocabulary that sticks",
        "Topic word lists with readings, romaji, examples and flashcards.",
    ),
    (
        "文",
        "Grammar, explained in English",
        "Ask anything — get patterns, examples and common mistakes.",
    ),
    (
        "試",
        "Quizzes scored fairly",
        "Seven question types, answer keys hidden, scoring done in code.",
    ),
    ("話", "Real conversations", "Role-play a café, a shop or a train station with an AI partner."),
]


def render() -> None:
    settings = get_settings()
    with st.container(key="landing"):
        left, right = st.columns([1.15, 1], gap="large")
    with left:
        _render_pitch()
    with right:
        with st.container(key="auth_card"):
            login_tab, signup_tab = st.tabs(["Log in", "Create account"])
            with login_tab:
                _render_login(settings.session_days)
            with signup_tab:
                if settings.allow_signups:
                    _render_signup(settings.session_days)
                else:
                    st.info("New sign-ups are currently closed on this server.")
        c.html_block(
            '<div class="jt-footnote">Your password is stored only as a salted scrypt hash. '
            "Learning data is private to your account.</div>"
        )


def _render_pitch() -> None:
    features = "".join(
        f'<div class="jt-feature"><div class="jt-feature-icon" lang="ja">{c.esc(k)}</div>'
        f"<div><b>{c.esc(title)}</b><span>{c.esc(text)}</span></div></div>"
        for k, title, text in _FEATURES
    )
    c.html_block(
        '<div class="jt-landing">'
        '<span class="jt-landing-badge"><b>●</b> Your personal AI sensei · 日本語</span>'
        "<h1>Learn Japanese<br>with an AI tutor that <em>explains why.</em></h1>"
        '<p class="lead">Built for English speakers — from your first ひらがな to natural, '
        "fluent conversation. Practise every day, track your progress, and get feedback "
        "that is honest about nuance.</p>"
        f"{features}"
        '<div class="jt-demo-card">'
        '<span class="jt-badge info">verb</span><span class="jt-badge ai">Word of the day</span>'
        '<div class="jt-jp jt-lg" lang="ja">頑張る</div>'
        '<div class="jt-reading" lang="ja">がんばる</div>'
        '<div class="jt-romaji">ganbaru</div>'
        '<div class="jt-en"><b>to do one’s best; to hang in there</b></div>'
        "</div></div>"
    )


def _render_login(session_days: int) -> None:
    c.html_block(
        '<div class="jt-auth-title">おかえりなさい — welcome back</div>'
        '<div class="jt-auth-sub">Log in to continue your streak.</div>'
    )
    with st.form("login_form", border=False):
        email = st.text_input("Email", placeholder="you@example.com", autocomplete="email")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        remember = st.checkbox(
            f"Keep me signed in for {session_days} days",
            value=True,
            disabled=session_days == 0,
        )
        submitted = st.form_submit_button(
            "Log in", type="primary", width="stretch", icon=":material/login:"
        )
    if submitted:
        try:
            user = account_features.authenticate(get_accounts(), email=email, password=password)
        except TutorError as exc:
            st.error(exc.user_message, icon=":material/lock:")
            return
        log_in(user, remember=remember, days=session_days)
        st.rerun()


def _render_signup(session_days: int) -> None:
    c.html_block(
        '<div class="jt-auth-title">はじめまして — nice to meet you</div>'
        '<div class="jt-auth-sub">Create a free account to save your progress.</div>'
    )
    with st.form("signup_form", border=False):
        name = st.text_input("Display name", placeholder="e.g. Alex", max_chars=40)
        email = st.text_input(
            "Email", placeholder="you@example.com", key="signup_email", autocomplete="email"
        )
        password = st.text_input(
            "Password",
            type="password",
            key="signup_password",
            autocomplete="new-password",
            help=f"At least {MIN_PASSWORD_LENGTH} characters, with letters and numbers.",
        )
        confirm = st.text_input(
            "Confirm password", type="password", key="signup_confirm", autocomplete="new-password"
        )
        submitted = st.form_submit_button(
            "Create account", type="primary", width="stretch", icon=":material/person_add:"
        )
    if submitted:
        try:
            user = account_features.sign_up(
                get_accounts(),
                email=email,
                display_name=name,
                password=password,
                confirm_password=confirm,
            )
        except TutorError as exc:
            st.error(exc.user_message, icon=":material/error:")
            return
        log_in(user, remember=True, days=session_days)
        st.rerun()
