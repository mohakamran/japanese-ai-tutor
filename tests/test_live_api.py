"""Optional live test against the real OpenAI API.

Skipped unless RUN_LIVE_TESTS=1 and OPENAI_API_KEY / OPENAI_MODEL are configured.
Running it makes one small, billed API request:

    RUN_LIVE_TESTS=1 pytest -m live
"""

from __future__ import annotations

import os

import pytest

from config.settings import load_settings
from features.vocabulary import generate_vocabulary
from services.llm_service import LLMService

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.environ.get("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1")
def test_live_vocabulary_generation() -> None:
    settings = load_settings()
    if not settings.ai_configured:
        pytest.skip("OPENAI_API_KEY and OPENAI_MODEL are not configured")
    items = generate_vocabulary(
        LLMService.from_settings(settings), topic="Food and drink", level="beginner", count=3
    )
    assert 1 <= len(items) <= 3
    assert all(item.word and item.reading and item.meaning for item in items)
