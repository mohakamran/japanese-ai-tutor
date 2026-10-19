"""Security checks: secret handling, redaction, escaping, and SQL parameterization."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

import pytest

from config.logging_config import REDACTED, RedactingFormatter, configure_logging, redact
from config.settings import load_settings
from core.errors import ConfigurationError, InputValidationError
from database.repository import LearningRepository
from schemas.vocabulary import VocabularyItem
from services.llm_service import LLMService
from tests.conftest import FAKE_KEY, vocab_item
from ui.components import esc, jp_markup

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ secrets


def _settings(**env: str):
    return load_settings(env, use_dotenv=False, use_streamlit_secrets=False)


def test_settings_repr_hides_api_key() -> None:
    settings = _settings(OPENAI_API_KEY=FAKE_KEY, OPENAI_MODEL="m", APP_PASSWORD="hunter22")
    assert settings.ai_configured
    assert FAKE_KEY not in repr(settings) and FAKE_KEY not in str(settings)
    assert "hunter22" not in repr(settings)


def test_llm_service_repr_hides_api_key() -> None:
    assert FAKE_KEY not in repr(LLMService(api_key=FAKE_KEY, model="m"))


def test_missing_settings_reported_by_name_only() -> None:
    settings = _settings()
    assert not settings.ai_configured
    assert settings.missing_ai_settings() == ["OPENAI_API_KEY", "OPENAI_MODEL"]


@pytest.mark.parametrize(
    "env",
    [
        {"OPENAI_TIMEOUT_SECONDS": "abc"},
        {"OPENAI_TIMEOUT_SECONDS": "0"},
        {"OPENAI_MAX_RETRIES": "9"},
        {"LOG_LEVEL": "LOUD"},
        {"OPENAI_MODEL": "bad model; rm -rf"},
    ],
)
def test_invalid_settings_rejected(env: dict) -> None:
    with pytest.raises(ConfigurationError):
        _settings(**env)


def test_importing_and_settings_do_not_require_api_key() -> None:
    settings = _settings(OPENAI_MODEL="m")
    assert not settings.ai_configured
    assert not LLMService.from_settings(settings).is_configured


def test_env_example_has_no_real_secrets() -> None:
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line.startswith(("OPENAI_API_KEY", "APP_PASSWORD", "APP_SECRET_KEY")):
            assert line.split("=", 1)[1].strip() == ""
    assert "sk-" not in (ROOT / ".env.example").read_text()


def test_gitignore_excludes_secrets_and_data() -> None:
    ignored = (ROOT / ".gitignore").read_text()
    for pattern in (".env", ".streamlit/secrets.toml", "*.db"):
        assert pattern in ignored


def test_source_contains_no_hardcoded_keys() -> None:
    """No key-shaped string (sk- followed by 16+ key characters) in any tracked file."""
    key_like = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")
    for path in ROOT.rglob("*"):
        if not path.is_file() or {".venv", ".git", "tests", "data"} & set(path.parts):
            continue
        if path.name == ".env" or path.suffix in {".png", ".svg", ".pyc", ".db"}:
            continue
        assert not key_like.search(path.read_text(errors="ignore")), path


# ---------------------------------------------------------------- logging


def test_redact_masks_keys_and_registered_secrets() -> None:
    text = f"key={FAKE_KEY} pw=hunter22 Authorization: Bearer abc.def"
    out = redact(text, ["hunter22"])
    assert FAKE_KEY not in out and "hunter22" not in out and "abc.def" not in out
    assert out.count(REDACTED) == 3


def test_log_records_and_tracebacks_are_redacted() -> None:
    formatter = RedactingFormatter("%(message)s", secrets=[FAKE_KEY])
    try:
        raise RuntimeError(f"failed with {FAKE_KEY}")
    except RuntimeError:
        import sys

        record = logging.LogRecord(
            "x", logging.ERROR, __file__, 1, "auth %s", (FAKE_KEY,), sys.exc_info()
        )
    output = formatter.format(record)
    assert FAKE_KEY not in output
    assert "RuntimeError" in output


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO", [FAKE_KEY])
    configure_logging("INFO", [FAKE_KEY])
    names = [h.get_name() for h in logging.getLogger().handlers]
    assert names.count("japanese_tutor_handler") == 1


# ------------------------------------------------------------- HTML output


def test_ai_output_is_html_escaped() -> None:
    malicious = '<script>alert("x")</script><img src=x onerror=alert(1)>'
    markup = jp_markup(malicious, reading=malicious, english=malicious)
    assert "<script>" not in markup and "<img" not in markup
    assert "&lt;script&gt;" in markup


def test_escape_neutralizes_markdown_breakouts() -> None:
    assert "\n" not in esc("a\n\n<b>b</b>")
    assert "$" not in esc("$x$")


# --------------------------------------------------------------- database


def test_sql_injection_strings_stored_literally(repo: LearningRepository) -> None:
    evil = "'); DROP TABLE vocabulary; --"
    repo.save_vocabulary(vocab_item(meaning=evil), topic=evil, level="beginner")
    words = repo.list_saved_vocabulary()
    assert words[0].meaning == evil and words[0].topic == evil
    assert repo.get_stats().saved_words == 1


def test_all_sql_is_parameterized() -> None:
    """No execute() call in the database layer may build SQL from runtime values."""
    for path in (ROOT / "database").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"execute", "executemany", "executescript"}
                and node.args
            ):
                sql = node.args[0]
                assert not isinstance(sql, ast.JoinedStr), f"f-string SQL in {path.name}"
                assert not isinstance(sql, ast.BinOp), f"concatenated SQL in {path.name}"
                assert not (
                    isinstance(sql, ast.Call)
                    and isinstance(sql.func, ast.Attribute)
                    and sql.func.attr == "format"
                ), f".format() SQL in {path.name}"


def test_invalid_model_output_never_stored(repo: LearningRepository) -> None:
    unvalidated = VocabularyItem.model_construct(word="<bad>")  # bypasses validation
    data = unvalidated.__dict__
    with pytest.raises(InputValidationError):
        repo.save_vocabulary(data, topic="x", level="beginner")  # type: ignore[arg-type]
    with pytest.raises(InputValidationError):
        repo.save_grammar_lesson(question="q", level="beginner", lesson={"title": "x"})  # type: ignore[arg-type]
    assert repo.get_stats().saved_words == 0
    assert repo.get_stats().grammar_lessons_saved == 0
