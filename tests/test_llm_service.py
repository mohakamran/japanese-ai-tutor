"""AI service behaviour with a mocked OpenAI client (no network, no cost)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest
from pydantic import ValidationError

from core.errors import (
    AIAuthenticationError,
    AIConnectionError,
    AIModelError,
    AIQuotaError,
    AIRateLimitError,
    AIResponseError,
    ConfigurationError,
)
from prompts.base import PromptSpec
from schemas.vocabulary import VocabularyGenerationResponse
from services.llm_service import LLMService
from tests.conftest import FAKE_KEY, vocab_item

PROMPT = PromptSpec(task="test", instructions="Be a tutor.", input="hello", max_output_tokens=100)
REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/responses")


def ok_response(parsed: Any) -> SimpleNamespace:
    return SimpleNamespace(status="completed", output=[], output_parsed=parsed)


def status_error(cls: type, status: int, code: str | None = None) -> Exception:
    body = {"error": {"message": f"boom {FAKE_KEY}", "code": code}}
    response = httpx2.Response(status, request=REQUEST, json=body)
    return cls(f"Error code: {status} - {FAKE_KEY}", response=response, body=body["error"])


class FakeClient:
    """Mimics ``client.responses.parse`` with queued results or exceptions."""

    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def service(*results: Any, **kwargs: Any) -> tuple[LLMService, FakeClient]:
    client = FakeClient(*results)
    return LLMService(api_key=FAKE_KEY, model="test-model", client=client, **kwargs), client


def valid_vocab() -> VocabularyGenerationResponse:
    return VocabularyGenerationResponse(items=[vocab_item()])


# --------------------------------------------------------------- success


def test_valid_response_returned_and_request_shape() -> None:
    llm, client = service(ok_response(valid_vocab()))
    result = llm.generate_structured(PROMPT, VocabularyGenerationResponse)
    assert result.items[0].word == "食べる"
    call = client.calls[0]
    assert call["model"] == "test-model"
    assert call["text_format"] is VocabularyGenerationResponse
    assert call["max_output_tokens"] == 100
    assert call["store"] is False
    assert "reasoning" not in call


def test_reasoning_effort_sent_only_when_configured() -> None:
    llm, client = service(ok_response(valid_vocab()), reasoning_effort="low")
    llm.generate_structured(PROMPT, VocabularyGenerationResponse)
    assert client.calls[0]["reasoning"] == {"effort": "low"}


def test_dict_output_is_validated_into_schema() -> None:
    llm, _ = service(ok_response({"items": [vocab_item().model_dump()]}))
    assert isinstance(
        llm.generate_structured(PROMPT, VocabularyGenerationResponse), VocabularyGenerationResponse
    )


# ------------------------------------------------- invalid output / retries


def test_malformed_output_retries_then_succeeds() -> None:
    error = ValidationError.from_exception_data("VocabularyGenerationResponse", [])
    llm, client = service(error, ok_response(valid_vocab()))
    assert llm.generate_structured(PROMPT, VocabularyGenerationResponse).items
    assert len(client.calls) == 2


def test_empty_response_retries_then_fails() -> None:
    llm, client = service(ok_response(None), ok_response(None))
    with pytest.raises(AIResponseError):
        llm.generate_structured(PROMPT, VocabularyGenerationResponse)
    assert len(client.calls) == 2  # 1 attempt + 1 retry, no more


def test_retry_limit_is_respected() -> None:
    llm, client = service(*[ok_response(None)] * 5, invalid_output_retries=2)
    with pytest.raises(AIResponseError):
        llm.generate_structured(PROMPT, VocabularyGenerationResponse)
    assert len(client.calls) == 3


def test_unexpected_output_shape_is_rejected() -> None:
    llm, _ = service(ok_response({"wrong": 1}), ok_response(["not", "a", "dict"]))
    with pytest.raises(AIResponseError):
        llm.generate_structured(PROMPT, VocabularyGenerationResponse)


def test_truncated_response_retries_with_bigger_budget() -> None:
    truncated = SimpleNamespace(
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        output=[],
        output_parsed=None,
    )
    llm, client = service(truncated, ok_response(valid_vocab()))
    llm.generate_structured(PROMPT, VocabularyGenerationResponse)
    assert client.calls[1]["max_output_tokens"] == 150


def test_refusal_is_not_retried() -> None:
    refusal = SimpleNamespace(
        status="completed",
        output=[SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal="no")])],
        output_parsed=None,
    )
    llm, client = service(refusal, ok_response(valid_vocab()))
    with pytest.raises(AIResponseError) as info:
        llm.generate_structured(PROMPT, VocabularyGenerationResponse)
    assert "declined" in info.value.user_message
    assert len(client.calls) == 1


# ------------------------------------------------------------- API errors


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (status_error(openai.AuthenticationError, 401), AIAuthenticationError),
        (status_error(openai.PermissionDeniedError, 403), AIAuthenticationError),
        (status_error(openai.NotFoundError, 404), AIModelError),
        (status_error(openai.BadRequestError, 400), AIModelError),
        (status_error(openai.RateLimitError, 429), AIRateLimitError),
        (status_error(openai.RateLimitError, 429, "insufficient_quota"), AIQuotaError),
        (status_error(openai.InternalServerError, 500), AIConnectionError),
        (openai.APITimeoutError(request=REQUEST), AIConnectionError),
        (openai.APIConnectionError(request=REQUEST), AIConnectionError),
    ],
)
def test_api_errors_are_mapped_without_leaking_details(exc: Exception, expected: type) -> None:
    llm, client = service(exc)
    with pytest.raises(expected) as info:
        llm.generate_structured(PROMPT, VocabularyGenerationResponse)
    assert FAKE_KEY not in info.value.user_message
    assert FAKE_KEY not in str(info.value)
    assert "Error code" not in info.value.user_message
    assert len(client.calls) == 1  # API errors are not retried by our loop (the SDK does that)


def test_rate_limit_message_is_actionable() -> None:
    llm, _ = service(status_error(openai.RateLimitError, 429))
    with pytest.raises(AIRateLimitError) as info:
        llm.generate_structured(PROMPT, VocabularyGenerationResponse)
    assert info.value.retryable and "try again" in info.value.user_message


# ---------------------------------------------------------- configuration


def test_missing_configuration_raises_before_any_call() -> None:
    llm = LLMService(api_key=None, model=None)
    assert not llm.is_configured
    with pytest.raises(ConfigurationError):
        llm.generate_structured(PROMPT, VocabularyGenerationResponse)


def test_missing_model_is_not_configured() -> None:
    assert not LLMService(api_key=FAKE_KEY, model=None).is_configured


def test_real_client_is_created_lazily_with_settings() -> None:
    llm = LLMService(api_key=FAKE_KEY, model="m", timeout_seconds=12, max_retries=1)
    client = llm._get_client()
    assert isinstance(client, openai.OpenAI)
    assert client.max_retries == 1
