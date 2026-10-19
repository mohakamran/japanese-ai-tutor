"""Accounts, sessions, per-user isolation, API-key encryption, and model selection."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import openai
import pytest

from config.settings import load_settings
from core.errors import AIAuthenticationError, InputValidationError
from core.security import (
    SecretBox,
    hash_password,
    hash_session_token,
    validate_email,
    validate_new_password,
    verify_password,
)
from database.initialization import MIGRATIONS
from database.models import NewQuizAttempt
from database.repository import AccountRepository, LearningRepository, initialize
from features import accounts as acc
from services.llm_service import filter_text_models, list_available_models
from tests.conftest import FAKE_KEY, TEST_PASSWORD, grammar_lesson, make_user, vocab_item

# ------------------------------------------------------------ passwords


def test_password_hash_roundtrip_and_salting() -> None:
    first, second = hash_password("Secret123"), hash_password("Secret123")
    assert first != second  # random salt
    assert first.startswith("scrypt$") and "Secret123" not in first
    assert verify_password("Secret123", first)
    assert not verify_password("secret123", first)
    assert not verify_password("Secret123", "garbage")


@pytest.mark.parametrize("password", ["short1", "lettersonly", "12345678901", "a" * 129 + "1"])
def test_weak_passwords_rejected(password: str) -> None:
    with pytest.raises(InputValidationError):
        validate_new_password(password)


def test_password_cannot_equal_email() -> None:
    with pytest.raises(InputValidationError):
        validate_new_password("me1@example.com", email="me1@example.com")


@pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "<script>@x.com", "a b@c.com"])
def test_invalid_emails_rejected(email: str) -> None:
    with pytest.raises(InputValidationError):
        validate_email(email)


def test_email_is_normalized() -> None:
    assert validate_email("  Alex@Example.COM ") == "alex@example.com"


# ------------------------------------------------------------- sign up/in


def test_sign_up_and_log_in(accounts: AccountRepository) -> None:
    user = acc.sign_up(
        accounts,
        email="Alex@Example.com",
        display_name=" Alex  Smith ",
        password="Sakura2026",
        confirm_password="Sakura2026",
    )
    assert user.email == "alex@example.com" and user.display_name == "Alex Smith"
    assert user.initials == "AS"
    logged_in = acc.authenticate(accounts, email="ALEX@example.com", password="Sakura2026")
    assert logged_in.id == user.id and logged_in.last_login_at is not None


def test_sign_up_rejects_duplicates_and_mismatch(accounts: AccountRepository) -> None:
    acc.sign_up(
        accounts,
        email="a@example.com",
        display_name="A",
        password="Sakura2026",
        confirm_password="Sakura2026",
    )
    with pytest.raises(InputValidationError, match="already exists"):
        acc.sign_up(
            accounts,
            email="A@EXAMPLE.com",
            display_name="B",
            password="Sakura2026",
            confirm_password="Sakura2026",
        )
    with pytest.raises(InputValidationError, match="do not match"):
        acc.sign_up(
            accounts,
            email="b@example.com",
            display_name="B",
            password="Sakura2026",
            confirm_password="Sakura2027",
        )


def test_login_errors_are_generic(accounts: AccountRepository, user) -> None:
    with pytest.raises(InputValidationError) as unknown:
        acc.authenticate(accounts, email="nobody@example.com", password="whatever1")
    with pytest.raises(InputValidationError) as wrong:
        acc.authenticate(accounts, email=user.email, password="wrong-password1")
    assert unknown.value.user_message == wrong.value.user_message


def test_account_locks_after_repeated_failures(accounts: AccountRepository, user) -> None:
    for _ in range(acc.MAX_FAILED_LOGINS - 1):
        with pytest.raises(InputValidationError, match="Incorrect"):
            acc.authenticate(accounts, email=user.email, password="wrong-password1")
    with pytest.raises(InputValidationError, match="locked"):
        acc.authenticate(accounts, email=user.email, password="wrong-password1")
    # Even the correct password is refused while locked.
    with pytest.raises(InputValidationError, match="try again"):
        acc.authenticate(accounts, email=user.email, password=TEST_PASSWORD)


def test_successful_login_resets_failure_count(accounts: AccountRepository, user) -> None:
    for _ in range(acc.MAX_FAILED_LOGINS - 1):
        with pytest.raises(InputValidationError):
            acc.authenticate(accounts, email=user.email, password="wrong-password1")
    acc.authenticate(accounts, email=user.email, password=TEST_PASSWORD)
    assert accounts.get_credentials(user_id=user.id).failed_logins == 0


# ---------------------------------------------------------------- sessions


def test_sessions_resume_end_and_store_only_hashes(
    accounts: AccountRepository, user, db_path
) -> None:
    token = acc.start_session(accounts, user.id, days=7)
    assert acc.resume_session(accounts, token).id == user.id
    with sqlite3.connect(db_path) as conn:
        stored = [r[0] for r in conn.execute("SELECT token_hash FROM user_sessions")]
    assert stored == [hash_session_token(token)] and token not in stored
    acc.end_session(accounts, token)
    assert acc.resume_session(accounts, token) is None
    assert acc.resume_session(accounts, "forged-token") is None
    assert acc.resume_session(accounts, None) is None


def test_expired_session_is_rejected(accounts: AccountRepository, user, db_path) -> None:
    token = acc.start_session(accounts, user.id, days=7)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE user_sessions SET expires_at = '2000-01-01T00:00:00Z'")
    assert acc.resume_session(accounts, token) is None


# ----------------------------------------------------------------- profile


def test_update_profile_requires_password_for_email_change(accounts, user) -> None:
    renamed = acc.update_profile(accounts, user, email=user.email, display_name="New Name")
    assert renamed.display_name == "New Name"
    with pytest.raises(InputValidationError, match="current password"):
        acc.update_profile(accounts, renamed, email="new@example.com", display_name="New Name")
    moved = acc.update_profile(
        accounts,
        renamed,
        email="new@example.com",
        display_name="New Name",
        current_password=TEST_PASSWORD,
    )
    assert moved.email == "new@example.com"


def test_email_change_cannot_take_another_users_email(accounts, user) -> None:
    other = make_user(accounts, email="other@example.com")
    with pytest.raises(InputValidationError, match="already uses"):
        acc.update_profile(
            accounts, other, email=user.email, display_name="x", current_password=TEST_PASSWORD
        )


def test_change_password_revokes_other_sessions(accounts, user) -> None:
    current = acc.start_session(accounts, user.id, days=7)
    other_device = acc.start_session(accounts, user.id, days=7)
    acc.change_password(
        accounts,
        user,
        current_password=TEST_PASSWORD,
        new_password="Fuji-san-2026",
        confirm_password="Fuji-san-2026",
        keep_session_token=current,
    )
    assert acc.resume_session(accounts, current) is not None
    assert acc.resume_session(accounts, other_device) is None
    acc.authenticate(accounts, email=user.email, password="Fuji-san-2026")
    with pytest.raises(InputValidationError):
        acc.authenticate(accounts, email=user.email, password=TEST_PASSWORD)


def test_change_password_validations(accounts, user) -> None:
    with pytest.raises(InputValidationError, match="current password"):
        acc.change_password(
            accounts,
            user,
            current_password="nope",
            new_password="Abcdefg12",
            confirm_password="Abcdefg12",
        )
    with pytest.raises(InputValidationError, match="different"):
        acc.change_password(
            accounts,
            user,
            current_password=TEST_PASSWORD,
            new_password=TEST_PASSWORD,
            confirm_password=TEST_PASSWORD,
        )


def test_delete_account_removes_all_data(accounts, user, repo, db_path) -> None:
    repo.save_vocabulary(vocab_item(), topic="Food", level="beginner")
    repo.save_grammar_lesson(question="q", level="beginner", lesson=grammar_lesson())
    repo.save_quiz_attempt(NewQuizAttempt("q1", "Food", "mixed", "beginner", "easy", 1, 1, 100))
    repo.log_activity("grammar_viewed", "x")
    acc.start_session(accounts, user.id, days=7)
    accounts.save_api_key(user.id, encrypted_api_key="x", key_hint="…1234")

    with pytest.raises(InputValidationError, match="DELETE"):
        acc.delete_account(accounts, user, password=TEST_PASSWORD, confirmation="delete")
    with pytest.raises(InputValidationError, match="current password"):
        acc.delete_account(accounts, user, password="wrong", confirmation="DELETE")
    acc.delete_account(accounts, user, password=TEST_PASSWORD, confirmation="DELETE")

    assert accounts.get_user(user.id) is None
    with sqlite3.connect(db_path) as conn:
        for table in (
            "vocabulary",
            "saved_vocabulary",
            "grammar_lessons",
            "quiz_attempts",
            "quiz_responses",
            "activity_log",
            "user_sessions",
            "user_api_credentials",
        ):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table  # noqa: S608


# --------------------------------------------------------------- isolation


def test_users_cannot_see_or_change_each_others_data(db_path, accounts, user, repo) -> None:
    other = make_user(accounts, email="other@example.com")
    other_repo = LearningRepository(db_path, other.id)

    vid, _ = repo.save_vocabulary(vocab_item(), topic="Food", level="beginner")
    repo.save_grammar_lesson(question="q", level="beginner", lesson=grammar_lesson())
    attempt_id, _ = repo.save_quiz_attempt(
        NewQuizAttempt("mine", "Food", "mixed", "beginner", "easy", 1, 1, 100.0)
    )
    repo.log_activity("grammar_viewed", "private")

    s = other_repo.get_stats()
    assert (
        s.saved_words,
        s.quizzes_completed,
        s.grammar_lessons_saved,
        s.grammar_lessons_viewed,
    ) == (0, 0, 0, 0)
    assert other_repo.list_saved_vocabulary() == []
    assert other_repo.list_recent_activity() == []
    assert other_repo.get_quiz_responses(attempt_id) == []
    # Writes against another user's records do nothing.
    assert other_repo.delete_saved_vocabulary([vid]) == 0
    with pytest.raises(InputValidationError):
        other_repo.record_vocabulary_review(vid, remembered=True)
    other_repo.clear_learning_history("all")
    assert repo.get_stats().saved_words == 1
    # The same word can be saved independently by both users.
    _, created = other_repo.save_vocabulary(vocab_item(), topic="Food", level="beginner")
    assert created
    # Re-using another user's quiz id cannot hijack their attempt.
    with pytest.raises(InputValidationError):
        other_repo.save_quiz_attempt(
            NewQuizAttempt("mine", "Food", "mixed", "beginner", "easy", 1, 0, 0.0)
        )


def test_preferences_are_per_user(db_path, accounts, user, repo) -> None:
    other = LearningRepository(db_path, make_user(accounts, email="o@example.com").id)
    prefs = repo.get_preferences()
    repo.save_preferences(
        prefs.__class__(
            **{**prefs.__dict__, "proficiency_level": "advanced", "openai_model": "my-model"}
        )
    )
    assert repo.get_preferences().openai_model == "my-model"
    assert other.get_preferences().proficiency_level == "beginner"
    assert other.get_preferences().openai_model is None


def test_learning_repository_requires_a_user(db_path) -> None:
    for bad in (0, -1, None, True, "1"):
        with pytest.raises(InputValidationError):
            LearningRepository(db_path, bad)  # type: ignore[arg-type]


# ---------------------------------------------------------------- migration


def test_upgrade_from_single_user_schema_keeps_data(tmp_path) -> None:
    """A v1 (pre-accounts) database is migrated and its data goes to the first account."""
    path = tmp_path / "v1.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, "
        "description TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT 'x')"
    )
    for statement in MIGRATIONS[0][2]:
        conn.execute(statement)
    conn.execute("INSERT INTO schema_migrations (version, description) VALUES (1, 'initial')")
    conn.execute(
        "INSERT INTO vocabulary (word, reading, romaji, meaning, part_of_speech, "
        "example_sentence, example_reading, example_romaji, example_translation, topic, "
        "proficiency_level, created_at) VALUES ('水','みず','mizu','water','noun','e','e','e',"
        "'e','Food','beginner','2026-01-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO saved_vocabulary (vocabulary_id, saved_at) VALUES (1, 'x')")
    conn.execute(
        "INSERT INTO learner_preferences VALUES (1, 'advanced', 0, 'detailed', 'hard', 1, 'x', 'x')"
    )
    conn.commit()
    conn.close()

    initialize(path)
    accounts = AccountRepository(path)
    first = acc.sign_up(
        accounts,
        email="first@example.com",
        display_name="First",
        password="Sakura2026",
        confirm_password="Sakura2026",
    )
    second = acc.sign_up(
        accounts,
        email="second@example.com",
        display_name="Second",
        password="Sakura2026",
        confirm_password="Sakura2026",
    )
    first_repo = LearningRepository(path, first.id)
    assert [w.word for w in first_repo.list_saved_vocabulary()] == ["水"]
    assert first_repo.get_preferences().proficiency_level == "advanced"
    assert LearningRepository(path, second.id).list_saved_vocabulary() == []


# ------------------------------------------------------------- API keys


def test_api_key_is_encrypted_at_rest(accounts, user, db_path) -> None:
    box = SecretBox(SecretBox.generate_key())
    hint = acc.save_user_api_key(accounts, box, user.id, FAKE_KEY)
    assert hint == "…" + FAKE_KEY[-4:]
    with sqlite3.connect(db_path) as conn:
        raw = conn.execute("SELECT encrypted_api_key FROM user_api_credentials").fetchone()[0]
    assert FAKE_KEY not in raw
    assert box.decrypt(raw) == FAKE_KEY
    assert SecretBox(SecretBox.generate_key()).decrypt(raw) is None  # wrong key


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "short", "sk-has spaces in it 123456789", "<script>alert(1)</script>xxxxxxxx"],
)
def test_invalid_api_keys_rejected(bad: str) -> None:
    with pytest.raises(InputValidationError):
        acc.validate_api_key(bad)


def test_secret_box_generates_private_key_file(tmp_path) -> None:
    settings = load_settings(
        {"DATABASE_PATH": str(tmp_path / "db" / "x.db")},
        use_dotenv=False,
        use_streamlit_secrets=False,
    )
    box = acc.load_secret_box(settings)
    key_file = tmp_path / "db" / ".app_secret_key"
    assert key_file.exists() and oct(key_file.stat().st_mode)[-3:] == "600"
    token = box.encrypt("hello")
    assert acc.load_secret_box(settings).decrypt(token) == "hello"  # same key reused


def _settings(**env: str):
    return load_settings(env, use_dotenv=False, use_streamlit_secrets=False)


def test_ai_config_precedence(accounts, user, repo) -> None:
    box = SecretBox(SecretBox.generate_key())
    server = _settings(OPENAI_API_KEY="sk-server-key-000000000000", OPENAI_MODEL="server-model")
    prefs = repo.get_preferences()

    config = acc.resolve_ai_config(server, accounts, box, user.id, prefs)
    assert (config.key_source, config.model, config.model_source) == (
        "server",
        "server-model",
        "server",
    )
    assert "sk-server" not in repr(config)

    acc.save_user_api_key(accounts, box, user.id, FAKE_KEY)
    prefs = repo.save_preferences(prefs.__class__(**{**prefs.__dict__, "openai_model": "mine"}))
    config = acc.resolve_ai_config(server, accounts, box, user.id, prefs)
    assert (config.api_key, config.key_source, config.model, config.model_source) == (
        FAKE_KEY,
        "user",
        "mine",
        "user",
    )
    assert config.ready


def test_server_key_not_shared_when_disabled(accounts, user, repo) -> None:
    box = SecretBox(SecretBox.generate_key())
    server = _settings(
        OPENAI_API_KEY="sk-server-key-000000000000", OPENAI_MODEL="m", SHARE_SERVER_API_KEY="false"
    )
    config = acc.resolve_ai_config(server, accounts, box, user.id, repo.get_preferences())
    assert config.api_key is None and not config.ready


def test_undecryptable_key_is_reported(accounts, user, repo) -> None:
    acc.save_user_api_key(accounts, SecretBox(SecretBox.generate_key()), user.id, FAKE_KEY)
    config = acc.resolve_ai_config(
        _settings(), accounts, SecretBox(SecretBox.generate_key()), user.id, repo.get_preferences()
    )
    assert config.key_unreadable and config.api_key is None


# --------------------------------------------------------------- models


def test_filter_text_models_keeps_chat_models_newest_first() -> None:
    models = [
        ("gpt-old", 100),
        ("gpt-new-mini", 300),
        ("text-embedding-3-large", 400),
        ("whisper-1", 500),
        ("o4-mini", 200),
        ("gpt-image-1", 600),
        ("dall-e-3", 50),
        ("gpt-4o-realtime-preview", 700),
        ("tts-1", 10),
        ("omni-moderation-latest", 800),
    ]
    assert filter_text_models(models) == ["gpt-new-mini", "o4-mini", "gpt-old"]


def test_list_available_models_uses_client_and_maps_errors() -> None:
    fake = SimpleNamespace(
        models=SimpleNamespace(
            list=lambda: [
                SimpleNamespace(id="gpt-a", created=2),
                SimpleNamespace(id="whisper-1", created=3),
            ]
        )
    )
    assert list_available_models(FAKE_KEY, client=fake) == ["gpt-a"]

    import httpx2

    def boom():
        response = httpx2.Response(401, request=httpx2.Request("GET", "https://x"))
        raise openai.AuthenticationError(f"bad key {FAKE_KEY}", response=response, body=None)

    with pytest.raises(AIAuthenticationError) as info:
        list_available_models(FAKE_KEY, client=SimpleNamespace(models=SimpleNamespace(list=boom)))
    assert FAKE_KEY not in info.value.user_message


def test_model_name_validation() -> None:
    assert acc.validate_model_name(" gpt-x ") == "gpt-x"
    for bad in ("", "has space", "<x>", "a" * 200):
        with pytest.raises(InputValidationError):
            acc.validate_model_name(bad)
