"""Japanese AI Tutor — Streamlit entry point.

Run with:  streamlit run app.py

This file only wires things together: page config, settings, logging, styles,
the optional site password, login state, and navigation. Pages live in ``ui/``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from config.logging_config import configure_logging
from config.settings import get_settings
from core.constants import LEVELS
from core.errors import ConfigurationError, DatabaseError
from database.models import User
from ui import (
    auth_page,
    conversation_page,
    correction_page,
    dashboard,
    grammar_page,
    progress_page,
    quiz_page,
    settings_page,
    vocabulary_page,
)
from ui import components as c
from ui.auth import require_password
from ui.navigation import register_pages
from ui.services import ensure_database, get_ai_config, get_preferences
from ui.session import apply_cookie_changes, current_user, log_out, restore_from_cookie
from ui.styles import inject_styles

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="Japanese AI Tutor",
    page_icon=str(ASSETS / "icon.svg"),
    layout="wide",
    initial_sidebar_state="auto",
)

# (key, render function, title, material icon)
PAGES = [
    ("dashboard", dashboard.render, "Dashboard", ":material/home:"),
    ("vocabulary", vocabulary_page.render, "Vocabulary", ":material/translate:"),
    ("grammar", grammar_page.render, "Grammar Tutor", ":material/menu_book:"),
    ("quiz", quiz_page.render, "Quiz Center", ":material/quiz:"),
    ("correction", correction_page.render, "Sentence Correction", ":material/spellcheck:"),
    ("conversation", conversation_page.render, "Conversation Practice", ":material/forum:"),
    ("progress", progress_page.render, "Learning Progress", ":material/insights:"),
    ("settings", settings_page.render, "Settings", ":material/settings:"),
]


def _logged_out_navigation() -> None:
    """Every app URL shows the landing page until the visitor logs in, so a
    bookmarked link (e.g. /quiz) opens the right page right after login."""
    pages = []
    for key, _, title, _ in PAGES:
        if key == "dashboard":
            pages.append(st.Page(auth_page.render, title="Welcome", url_path=key, default=True))
        else:
            pages.append(st.Page(lambda: auth_page.render(), title=title, url_path=key))
    st.navigation(pages, position="hidden").run()


def _sidebar(user: User) -> None:
    with st.sidebar:
        try:
            level = LEVELS[get_preferences().proficiency_level].split(" (")[0]
            config = get_ai_config()
            model = config.model if config.ready else None
        except (DatabaseError, ConfigurationError):
            level, model = "", None
        c.html_block(
            f'<div class="jt-user"><div class="jt-avatar">{c.esc(user.initials)}</div>'
            f'<div><div class="jt-user-name">{c.esc(user.display_name)}</div>'
            f'<div class="jt-user-meta">{c.esc(level)} learner</div></div></div>'
        )
        st.caption(f"AI model: {model}" if model else "AI not connected — see Settings")
        if st.button("Log out", icon=":material/logout:", width="stretch", key="logout"):
            log_out()
            st.rerun()


def main() -> None:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        configure_logging()
        st.error(f"Configuration problem: {exc.user_message}")
        st.stop()

    configure_logging(settings.log_level, settings.secret_values())
    inject_styles()
    st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icon.svg"), size="large")
    require_password(settings)

    try:
        ensure_database()  # creates the database and applies migrations on first run
    except DatabaseError as exc:
        st.error(exc.user_message)
        st.stop()

    restore_from_cookie()
    user = current_user()
    apply_cookie_changes()

    if user is None:
        _logged_out_navigation()
        return

    pages = {
        key: st.Page(render, title=title, icon=icon, url_path=key, default=(key == "dashboard"))
        for key, render, title, icon in PAGES
    }
    register_pages(pages)
    navigation = st.navigation(list(pages.values()), position="sidebar")
    _sidebar(user)
    navigation.run()


main()
