"""Settings: learning preferences, AI setup (API key + model), account, and data."""

from __future__ import annotations

import dataclasses

import streamlit as st

from config.settings import get_settings
from core.constants import DIFFICULTIES, EXPLANATION_STYLES, LEVELS
from core.errors import DatabaseError, TutorError
from database.models import Preferences, User
from database.repository import CLEAR_SCOPES
from features import accounts as account_features
from services.llm_service import check_model, list_available_models
from ui import components as c
from ui.services import (
    get_accounts,
    get_ai_config,
    get_llm,
    get_preferences,
    get_repository,
    get_secret_box,
    require_user,
)
from ui.session import TOKEN_KEY, log_out
from ui.state import reset_preference_defaults

MODELS_KEY = "_jt_available_models"  # list[str], cached for this session only
SERVER_DEFAULT = "__server_default__"
_KEY_INPUT = "api_key_input"


def render() -> None:
    c.page_header(
        "Settings",
        "設定 · Settings",
        "Personalise your learning, connect the AI and manage your account.",
        mark="設",
    )
    try:
        user = require_user()
        prefs = get_preferences()
    except TutorError as exc:
        c.show_error(exc)
        return

    prefs_tab, ai_tab, account_tab, data_tab = st.tabs(
        ["Learning preferences", "AI setup", "Account", "Your data"]
    )
    with prefs_tab:
        _render_preferences(prefs)
    with ai_tab:
        _render_ai_setup(user, prefs)
    with account_tab:
        _render_account(user)
    with data_tab:
        _render_data_management()


# ------------------------------------------------------------ preferences


def _render_preferences(prefs: Preferences) -> None:
    with st.form("preferences_form"):
        col1, col2 = st.columns(2)
        level = col1.selectbox(
            "Proficiency level",
            list(LEVELS),
            format_func=LEVELS.get,
            index=list(LEVELS).index(prefs.proficiency_level),
        )
        difficulty = col2.selectbox(
            "Preferred quiz difficulty",
            list(DIFFICULTIES),
            format_func=DIFFICULTIES.get,
            index=list(DIFFICULTIES).index(prefs.preferred_difficulty),
        )
        style = st.radio(
            "Explanation style",
            list(EXPLANATION_STYLES),
            format_func=EXPLANATION_STYLES.get,
            index=list(EXPLANATION_STYLES).index(prefs.explanation_style),
        )
        romaji = st.toggle(
            "Show romaji (Latin-alphabet readings)",
            value=prefs.romaji_enabled,
            help="Helpful for beginners. Turn off to practise reading kana.",
        )
        corrections = st.toggle(
            "Correct my mistakes during conversation practice", value=prefs.conversation_corrections
        )
        saved = st.form_submit_button("Save preferences", type="primary", icon=":material/save:")
    if saved:
        try:
            get_repository().save_preferences(
                dataclasses.replace(
                    prefs,
                    proficiency_level=level,
                    romaji_enabled=romaji,
                    explanation_style=style,
                    preferred_difficulty=difficulty,
                    conversation_corrections=corrections,
                )
            )
        except TutorError as exc:
            c.show_error(exc)
        else:
            reset_preference_defaults()
            st.success(
                "Preferences saved. New lessons and quizzes will use them.", icon=":material/check:"
            )


# ---------------------------------------------------------------- AI setup


def _render_ai_setup(user: User, prefs: Preferences) -> None:
    settings = get_settings()
    accounts = get_accounts()
    config = get_ai_config()

    key_text = {
        "user": f"Your API key {config.key_hint or ''}",
        "server": "Server-provided API key",
        "none": "No API key",
    }[config.key_source]
    model_text = {
        "user": f"{config.model} (your choice)",
        "server": f"{config.model} (server default)",
        "none": "No model selected",
    }[config.model_source]
    status = c.badge("Ready" if config.ready else "Not connected", "ok" if config.ready else "err")
    c.card(
        status
        + c.label("API key")
        + c.text(key_text)
        + c.label("Model")
        + c.text(model_text)
        + c.text("Your key is encrypted before it is stored and is never shown again.", muted=True),
        variant="indigo",
    )
    if config.key_unreadable:
        st.warning(
            "Your saved API key could not be decrypted (the server's encryption key "
            "changed). Please save your key again.",
            icon=":material/warning:",
        )

    # --- API key -----------------------------------------------------------
    st.markdown("##### 1 · Your OpenAI API key")
    st.caption(
        "Create a key at platform.openai.com → API keys. API usage is billed by OpenAI "
        "separately from ChatGPT subscriptions."
    )
    with st.form("api_key_form", clear_on_submit=True):
        new_key = st.text_input(
            "API key", type="password", placeholder="sk-…", autocomplete="off", key=_KEY_INPUT
        )
        save_key = st.form_submit_button("Verify & save key", type="primary", icon=":material/key:")
    if save_key:
        try:
            key = account_features.validate_api_key(new_key)
            with st.spinner("Checking your key with OpenAI…"):
                models = list_available_models(key, timeout_seconds=settings.openai_timeout_seconds)
            hint = account_features.save_user_api_key(accounts, get_secret_box(), user.id, key)
        except TutorError as exc:
            c.show_error(exc)
        else:
            st.session_state[MODELS_KEY] = models
            st.success(
                f"Key {hint} verified and saved. {len(models)} models available.",
                icon=":material/check:",
            )
            st.rerun()
    if config.key_source == "user" and st.button("Remove my saved key", icon=":material/key_off:"):
        try:
            accounts.delete_api_key(user.id)
        except DatabaseError as exc:
            c.show_error(exc)
        else:
            st.session_state.pop(MODELS_KEY, None)
            st.rerun()
    if config.key_source == "server":
        st.caption(
            "This server shares its own API key with signed-in users. Save your own "
            "key to use your OpenAI account instead."
        )

    # --- Model --------------------------------------------------------------
    st.markdown("##### 2 · Choose a model")
    models: list[str] = st.session_state.get(MODELS_KEY, [])
    load_col, test_col = st.columns(2)
    if load_col.button(
        "Load available models",
        icon=":material/refresh:",
        width="stretch",
        disabled=not config.api_key,
    ):
        try:
            with st.spinner("Fetching models from OpenAI…"):
                models = list_available_models(
                    config.api_key or "", timeout_seconds=settings.openai_timeout_seconds
                )
        except TutorError as exc:
            c.show_error(exc)
        else:
            st.session_state[MODELS_KEY] = models
    if not config.api_key:
        st.caption("Save an API key first to see the models available to you.")

    options = [SERVER_DEFAULT] if settings.openai_model else []
    options += models
    if prefs.openai_model and prefs.openai_model not in options:
        options.append(prefs.openai_model)
    if options:
        current = prefs.openai_model or (SERVER_DEFAULT if settings.openai_model else options[0])
        with st.form("model_form"):
            choice = st.selectbox(
                "Model",
                options,
                index=options.index(current) if current in options else 0,
                format_func=lambda m: (
                    f"Server default ({settings.openai_model})" if m == SERVER_DEFAULT else m
                ),
                help="Models are listed newest first. Pick one that supports structured "
                "outputs; use “Test model” to check.",
            )
            custom = st.text_input("Or type a model name (optional)", placeholder="model id")
            save_model = st.form_submit_button("Save model", type="primary", icon=":material/save:")
        if save_model:
            chosen = custom.strip() or choice
            model = None if chosen == SERVER_DEFAULT else chosen
            try:
                if model is not None:
                    model = account_features.validate_model_name(model)
                get_repository().save_preferences(dataclasses.replace(prefs, openai_model=model))
            except TutorError as exc:
                c.show_error(exc)
            else:
                st.success("Model saved.", icon=":material/check:")
                st.rerun()
    if test_col.button(
        "Test model", icon=":material/science:", width="stretch", disabled=not config.ready
    ):
        works = c.call_safely(f"Sending a test request to {config.model}…", check_model, get_llm())
        if works:
            st.success(
                f"{config.model} is working — structured outputs confirmed.",
                icon=":material/check_circle:",
            )


# ----------------------------------------------------------------- account


def _render_account(user: User) -> None:
    accounts = get_accounts()
    c.card(
        f'<div style="display:flex;gap:.9rem;align-items:center">'
        f'<div class="jt-avatar" style="width:52px;height:52px;font-size:1.15rem">'
        f"{c.esc(user.initials)}</div><div>"
        f'<div class="jt-card-title">{c.esc(user.display_name)}</div>'
        f'<div class="jt-muted">{c.esc(user.email)} · member since '
        f"{c.esc(user.created_at[:10])}</div></div></div>"
    )

    st.markdown("##### Profile")
    with st.form("profile_form"):
        name = st.text_input("Display name", value=user.display_name, max_chars=40)
        email = st.text_input("Email", value=user.email)
        current = st.text_input(
            "Current password (required to change your email)",
            type="password",
            autocomplete="current-password",
        )
        save = st.form_submit_button("Update profile", type="primary", icon=":material/save:")
    if save:
        try:
            account_features.update_profile(
                accounts, user, email=email, display_name=name, current_password=current
            )
        except TutorError as exc:
            c.show_error(exc)
        else:
            st.success("Profile updated.", icon=":material/check:")
            st.rerun()

    st.markdown("##### Change password")
    with st.form("password_form", clear_on_submit=True):
        current_pw = st.text_input(
            "Current password", type="password", autocomplete="current-password"
        )
        new_pw = st.text_input(
            "New password",
            type="password",
            autocomplete="new-password",
            help="At least 8 characters, with letters and numbers.",
        )
        confirm_pw = st.text_input(
            "Confirm new password", type="password", autocomplete="new-password"
        )
        change = st.form_submit_button("Change password", icon=":material/lock_reset:")
    if change:
        try:
            account_features.change_password(
                accounts,
                user,
                current_password=current_pw,
                new_password=new_pw,
                confirm_password=confirm_pw,
                keep_session_token=st.session_state.get(TOKEN_KEY),
            )
        except TutorError as exc:
            c.show_error(exc)
        else:
            st.success(
                "Password changed. Other devices have been signed out.", icon=":material/check:"
            )

    st.markdown("##### Danger zone")
    with st.expander("Delete my account", icon=":material/warning:"):
        st.markdown(
            "This permanently deletes your account, saved vocabulary, lessons, quiz history, "
            "preferences and saved API key. **This cannot be undone.**"
        )
        with st.form("delete_account_form", clear_on_submit=True):
            password = st.text_input("Password", type="password", autocomplete="current-password")
            confirmation = st.text_input(
                f'Type "{account_features.DELETE_CONFIRMATION}" to confirm'
            )
            delete = st.form_submit_button(
                "Permanently delete my account", icon=":material/delete_forever:"
            )
        if delete:
            try:
                account_features.delete_account(
                    accounts, user, password=password, confirmation=confirmation
                )
            except TutorError as exc:
                c.show_error(exc)
            else:
                log_out()
                st.rerun()


# -------------------------------------------------------------------- data


def _render_data_management() -> None:
    st.markdown(
        "Your vocabulary, saved lessons, quiz results, preferences and an activity log are "
        "stored in the app's database, linked to your account. Conversations and "
        "generated-but-unsaved content are kept only for the current browser session. "
        "Clearing data is permanent."
    )
    scope = st.selectbox(
        "What do you want to delete?",
        list(CLEAR_SCOPES),
        format_func=CLEAR_SCOPES.get,
        key="clear_scope",
    )
    confirm = st.checkbox(
        f"Yes, permanently delete: {CLEAR_SCOPES[scope].lower()}", key="clear_confirm"
    )
    if st.button("Delete data", disabled=not confirm, icon=":material/delete_forever:"):
        try:
            get_repository().clear_learning_history(scope)
        except TutorError as exc:
            c.show_error(exc)
            return
        for key in ("vocab_deck", "quiz_session", "clear_confirm"):
            st.session_state.pop(key, None)
        st.success("Deleted.", icon=":material/check:")
