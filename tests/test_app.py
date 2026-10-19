"""End-to-end UI tests with Streamlit's AppTest (AI calls are mocked).

These run the real page code in a headless Streamlit runtime, using a
temporary database and a fake API key that must never appear in the output.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config.settings as settings_module
from config.settings import get_settings
from core.security import SecretBox
from database.repository import AccountRepository, LearningRepository, initialize
from features.quiz import QuizSession
from schemas.vocabulary import VocabularyGenerationResponse
from services.llm_service import LLMService
from tests.conftest import FAKE_KEY, TEST_PASSWORD, make_user, quiz_question, vocab_item
from ui.session import USER_KEY

ROOT = Path(__file__).resolve().parent.parent
PAGES = [
    "dashboard",
    "vocabulary",
    "grammar",
    "quiz",
    "correction",
    "conversation",
    "progress",
    "settings",
]
MODULES = {
    "dashboard": "dashboard",
    "vocabulary": "vocabulary_page",
    "grammar": "grammar_page",
    "quiz": "quiz_page",
    "correction": "correction_page",
    "conversation": "conversation_page",
    "progress": "progress_page",
    "settings": "settings_page",
}

# Renders one page as a logged-in user, with navigation registered so links work.
HARNESS = """
import streamlit as st
from ui import {module} as target
from ui.navigation import register_pages
from ui.styles import inject_styles

keys = {keys!r}
pages = {{k: st.Page(lambda: None, title=k, url_path=k, default=(k == "dashboard")) for k in keys}}
register_pages(pages)
st.navigation(list(pages.values()), position="hidden")
inject_styles()
target.render()
"""


def _reset_caches() -> None:
    get_settings.cache_clear()
    st.cache_resource.clear()


@pytest.fixture
def app_env(monkeypatch, tmp_path) -> Iterator[Path]:
    # Isolate from any real .env file or secrets.toml on the developer's machine.
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(settings_module, "_read_streamlit_secret", lambda name: None)
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("APP_SECRET_KEY", SecretBox.generate_key())
    for name in ("APP_PASSWORD", "SHARE_SERVER_API_KEY", "ALLOW_SIGNUPS"):
        monkeypatch.delenv(name, raising=False)
    initialize(db_path)
    _reset_caches()
    yield db_path
    _reset_caches()


@pytest.fixture
def user(app_env):
    return make_user(AccountRepository(app_env))


def page_app(name: str, user=None) -> AppTest:
    at = AppTest.from_string(HARNESS.format(module=MODULES[name], keys=PAGES), default_timeout=30)
    if user is not None:
        at.session_state[USER_KEY] = user.id
    return at


def full_app() -> AppTest:
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)


def rendered_text(at: AppTest) -> str:
    """Every string rendered on the page (values, labels, captions, alerts)."""
    parts: list[str] = []

    def walk(node) -> None:
        for attr in ("value", "label", "body", "placeholder", "help"):
            value = getattr(node, attr, None)
            if isinstance(value, str):
                parts.append(value)
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(at._tree)
    return "\n".join(parts)


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


# ------------------------------------------------------------- auth flows


def test_logged_out_visitors_see_landing_page(app_env) -> None:
    at = full_app().run()
    assert not at.exception
    text = rendered_text(at)
    assert "Learn Japanese" in text and "Log in" in text and "Create account" in text
    assert FAKE_KEY not in text
    assert "Dashboard" not in [p for p in text.splitlines()]  # no app navigation yet


def test_sign_up_through_the_ui_logs_in(app_env) -> None:
    at = full_app().run()
    at.text_input(key="signup_email").set_value("new@example.com")
    next(t for t in at.text_input if t.label == "Display name").set_value("Hana Sato")
    at.text_input(key="signup_password").set_value("Sakura2026")
    at.text_input(key="signup_confirm").set_value("Sakura2026")
    button(at, "Create account").click().run()
    assert not at.exception
    assert at.session_state[USER_KEY] is not None
    text = rendered_text(at)
    assert "Hana" in text and "Learn Japanese" not in text


def test_login_logout_flow(app_env, user) -> None:
    at = full_app().run()
    next(t for t in at.text_input if t.label == "Email").set_value(user.email)
    next(t for t in at.text_input if t.label == "Password").set_value("wrong-password1")
    button(at, "Log in").click().run()
    assert any("Incorrect email or password" in e.value for e in at.error)

    next(t for t in at.text_input if t.label == "Password").set_value(TEST_PASSWORD)
    button(at, "Log in").click().run()
    assert at.session_state[USER_KEY] == user.id
    assert "Test Learner" in rendered_text(at)

    button(at, "Log out").click().run()
    assert USER_KEY not in at.session_state
    assert "Learn Japanese" in rendered_text(at)


def test_logged_in_full_app_renders_dashboard(app_env, user) -> None:
    at = full_app()
    at.session_state[USER_KEY] = user.id
    at.run()
    assert not at.exception
    text = rendered_text(at)
    assert "Test" in text and "Study streak" in text
    assert FAKE_KEY not in text


# ------------------------------------------------------------------ pages


@pytest.mark.parametrize("name", PAGES)
def test_every_page_renders_without_errors_or_secrets(app_env, user, name) -> None:
    at = page_app(name, user).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    assert FAKE_KEY not in rendered_text(at)


def test_missing_api_key_shows_setup_instructions(app_env, user, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    _reset_caches()
    at = page_app("settings", user).run()
    text = rendered_text(at)
    assert "Not connected" in text and "No API key" in text
    at = page_app("grammar", user).run()
    assert any("Connect your AI tutor" in i.value for i in at.info)
    assert button(at, "Explain Grammar").disabled


def test_settings_shows_status_but_never_the_key(app_env, user) -> None:
    at = page_app("settings", user).run()
    text = rendered_text(at)
    assert "Server-provided API key" in text
    assert "test-model" in text
    assert FAKE_KEY not in text and FAKE_KEY[:12] not in text


def test_saving_own_api_key_through_settings(app_env, user, monkeypatch) -> None:
    import ui.settings_page as settings_page

    monkeypatch.setattr(
        settings_page, "list_available_models", lambda key, **kw: ["gpt-test-a", "gpt-test-b"]
    )
    at = page_app("settings", user).run()
    next(t for t in at.text_input if t.label == "API key").set_value(FAKE_KEY)
    button(at, "Verify & save key").click().run()
    assert not at.exception
    text = rendered_text(at)
    assert f"Your API key …{FAKE_KEY[-4:]}" in text
    # AppTest re-sends the value the test typed into the password box, so ignore
    # that input; nothing else on the page may contain the key.
    typed = {t.value for t in at.text_input if t.label == "API key"}
    assert FAKE_KEY not in text.replace(FAKE_KEY, "", len(typed & {FAKE_KEY}))
    assert AccountRepository(app_env).get_api_key(user.id) is not None


def test_users_only_see_their_own_data_in_the_ui(app_env, user) -> None:
    other = make_user(AccountRepository(app_env), email="other@example.com", name="Other")
    LearningRepository(app_env, user.id).save_vocabulary(
        vocab_item(word="秘密", reading="ひみつ", romaji="himitsu", meaning="secret"),
        topic="Private",
        level="beginner",
    )
    at = page_app("vocabulary", other).run()
    assert not at.dataframe  # the other user has no saved words: empty state, no table
    at = page_app("vocabulary", user).run()
    assert "秘密" in at.dataframe[0].value["Japanese"].tolist()


# ------------------------------------------------------------------- quiz


def test_quiz_hides_answers_until_submitted(app_env, user) -> None:
    question = quiz_question(explanation="SECRET-EXPLANATION", options=["a", "b", "c", "d"])
    session = QuizSession("Food", "mixed", "beginner", "easy", [question, question])
    at = page_app("quiz", user)
    at.session_state["quiz_session"] = session
    at.run()
    text = rendered_text(at)
    assert "SECRET-EXPLANATION" not in text
    assert "Correct answer" not in text

    at.radio[0].set_value(1).run()  # wrong answer to question 1
    assert session.answers == {0: 1}
    at.checkbox(key=f"quiz_confirm_{session.quiz_id}").check().run()
    button(at, "Submit quiz").click().run()

    assert session.submitted
    assert session.score.correct == 0 and session.score.unanswered == 1
    text = rendered_text(at)
    assert "SECRET-EXPLANATION" in text
    assert "Correct answer" in text


def test_quiz_submission_saved_once_across_reruns(app_env, user) -> None:
    session = QuizSession("Food", "mixed", "beginner", "easy", [quiz_question()])
    at = page_app("quiz", user)
    at.session_state["quiz_session"] = session
    at.run()
    at.radio[0].set_value(0).run()
    button(at, "Submit quiz").click().run()
    at.run()
    at.run()
    attempts = LearningRepository(app_env, user.id).list_quiz_attempts()
    assert len(attempts) == 1 and attempts[0].score == 100.0


# -------------------------------------------------------------- AI flows


def test_vocabulary_generate_and_save_with_mocked_ai(app_env, user, monkeypatch) -> None:
    def fake_generate(self, prompt, schema):
        assert schema is VocabularyGenerationResponse
        return VocabularyGenerationResponse(
            items=[
                vocab_item(),
                vocab_item(word="水", reading="みず", romaji="mizu", meaning="water"),
            ]
        )

    monkeypatch.setattr(LLMService, "generate_structured", fake_generate)
    at = page_app("vocabulary", user).run()
    button(at, "Generate Vocabulary").click().run()
    assert not at.exception
    text = rendered_text(at)
    assert "食べる" in text and "water" in text
    button(at, "Save all").click().run()
    assert LearningRepository(app_env, user.id).get_stats().saved_words == 2
    assert any(b.label == "Saved" and b.disabled for b in at.button)


def test_ai_error_shows_friendly_message(app_env, user, monkeypatch) -> None:
    from core.errors import AIRateLimitError

    def failing(self, prompt, schema):
        raise AIRateLimitError(detail=f"internal detail {FAKE_KEY}")

    monkeypatch.setattr(LLMService, "generate_structured", failing)
    at = page_app("correction", user)
    at.session_state["keep_correction_sentence"] = "すしを食べます"
    at.run()
    button(at, "Check my sentence").click().run()
    assert not at.exception
    assert any("too many requests" in e.value for e in at.error)
    text = rendered_text(at)
    assert FAKE_KEY not in text and "internal detail" not in text
    # The learner's input is preserved for a retry.
    assert at.text_area(key="keep_correction_sentence").value == "すしを食べます"


def test_unexpected_exception_is_not_shown_raw(app_env, user, monkeypatch) -> None:
    def crash(self, prompt, schema):
        raise RuntimeError(f"Traceback secret {FAKE_KEY}")

    monkeypatch.setattr(LLMService, "generate_structured", crash)
    at = page_app("grammar", user)
    at.session_state["keep_grammar_question"] = "What is は?"
    at.run()
    button(at, "Explain Grammar").click().run()
    assert not at.exception
    assert any("unexpected error" in e.value for e in at.error)
    text = rendered_text(at)
    assert "Traceback" not in text and FAKE_KEY not in text
