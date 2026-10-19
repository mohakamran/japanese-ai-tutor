"""The single place where the application talks to the language model.

Every feature calls :meth:`LLMService.generate_structured` with a prompt and a
Pydantic schema. The service:

* uses the OpenAI Responses API with structured outputs (``responses.parse``),
* lets the SDK retry transient failures (rate limits, 5xx, connection errors),
* retries *invalid or truncated* output a small, fixed number of times,
* maps SDK exceptions to :mod:`core.errors` types with learner-safe messages,
* never logs prompts, learner text, or credentials.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

import openai
from pydantic import BaseModel, ValidationError

from config.settings import Settings
from core.errors import (
    AIAuthenticationError,
    AIConnectionError,
    AIModelError,
    AIQuotaError,
    AIRateLimitError,
    AIResponseError,
    ConfigurationError,
    TutorError,
)
from prompts.base import PromptSpec

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Extra attempts after an invalid / truncated response. Kept small to bound cost.
DEFAULT_INVALID_OUTPUT_RETRIES = 1
# When a response is cut off by the token limit, the retry gets this much more room.
TRUNCATION_BUDGET_MULTIPLIER = 1.5


class _InvalidOutput(Exception):
    """Internal signal: the response was unusable but a retry may help."""


class LLMService:
    """Thin, testable wrapper around the OpenAI client."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None,
        reasoning_effort: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        invalid_output_retries: int = DEFAULT_INVALID_OUTPUT_RETRIES,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.reasoning_effort = reasoning_effort
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._invalid_output_retries = max(0, invalid_output_retries)
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> LLMService:
        return cls(
            api_key=(
                settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
            ),
            model=settings.openai_model,
            reasoning_effort=settings.openai_reasoning_effort,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )

    def __repr__(self) -> str:  # never include the key
        return f"LLMService(model={self.model!r}, configured={self.is_configured})"

    @property
    def is_configured(self) -> bool:
        return bool(self.model) and (self._client is not None or bool(self._api_key))

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = openai.OpenAI(
                api_key=self._api_key,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        return self._client

    # ------------------------------------------------------------------ public

    def generate_structured(self, prompt: PromptSpec, schema: type[T]) -> T:
        """Send ``prompt`` and return a validated instance of ``schema``.

        Raises a :class:`core.errors.TutorError` subclass on any failure. Never
        returns placeholder or fabricated content.
        """
        if not self.is_configured:
            raise ConfigurationError()

        client = self._get_client()
        budget = prompt.max_output_tokens
        attempts = 1 + self._invalid_output_retries

        for attempt in range(1, attempts + 1):
            request: dict[str, Any] = {
                "model": self.model,
                "instructions": prompt.instructions,
                "input": prompt.input,
                "text_format": schema,
                "max_output_tokens": budget,
                # Do not retain learner content on the provider side.
                "store": False,
            }
            if self.reasoning_effort:
                request["reasoning"] = {"effort": self.reasoning_effort}

            try:
                response = client.responses.parse(**request)
                return self._extract(response, schema)
            except _InvalidOutput as exc:
                logger.warning(
                    "Invalid AI output for %s (attempt %d/%d): %s",
                    prompt.task,
                    attempt,
                    attempts,
                    exc,
                )
                if "max_output_tokens" in str(exc):
                    budget = int(budget * TRUNCATION_BUDGET_MULTIPLIER)
            except (ValidationError, ValueError) as exc:
                # The SDK raises these when the JSON does not match the schema.
                logger.warning(
                    "Schema validation failed for %s (attempt %d/%d): %s",
                    prompt.task,
                    attempt,
                    attempts,
                    type(exc).__name__,
                )
            except TutorError:
                raise
            except openai.OpenAIError as exc:
                raise self._map_api_error(exc, prompt.task) from None

        raise AIResponseError(detail=f"{prompt.task}: invalid output after {attempts} attempts")

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _extract(response: Any, schema: type[T]) -> T:
        status = getattr(response, "status", None)
        if status == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", None) or "unknown"
            if reason == "content_filter":
                raise AIResponseError(
                    "The AI could not answer this request. Try rephrasing it.",
                    detail="incomplete: content_filter",
                )
            raise _InvalidOutput(f"response incomplete ({reason})")
        if status == "failed":
            raise _InvalidOutput("response status failed")

        for item in getattr(response, "output", None) or []:
            for content in getattr(item, "content", None) or []:
                if getattr(content, "type", None) == "refusal":
                    raise AIResponseError(
                        "The AI declined to answer this request. Try asking about a "
                        "different Japanese topic.",
                        detail="model refusal",
                    )

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise _InvalidOutput("empty response")
        if not isinstance(parsed, schema):
            try:
                parsed = schema.model_validate(parsed)
            except ValidationError as exc:
                raise _InvalidOutput(f"unexpected output type: {type(parsed).__name__}") from exc
        return parsed

    @staticmethod
    def _map_api_error(exc: openai.OpenAIError, task: str) -> TutorError:
        """Convert an SDK exception to a learner-safe error. Logs type and status only."""
        status = getattr(exc, "status_code", None)
        code = getattr(exc, "code", None)
        logger.error(
            "OpenAI API error during %s: %s (status=%s, code=%s)",
            task,
            type(exc).__name__,
            status,
            code,
        )

        if isinstance(exc, openai.AuthenticationError):
            return AIAuthenticationError()
        if isinstance(exc, openai.PermissionDeniedError):
            return AIAuthenticationError(
                "Your API key does not have permission for this model or project. "
                "Check the key's permissions or choose another model."
            )
        if isinstance(exc, openai.NotFoundError):
            return AIModelError(
                "The configured model was not found. Check that OPENAI_MODEL is a model "
                "your account can use."
            )
        if isinstance(exc, openai.RateLimitError):
            if code == "insufficient_quota":
                return AIQuotaError()
            return AIRateLimitError()
        if isinstance(exc, openai.APITimeoutError):
            return AIConnectionError("The AI service took too long to respond. Please try again.")
        if isinstance(exc, openai.APIConnectionError):
            return AIConnectionError()
        if isinstance(exc, openai.BadRequestError | openai.UnprocessableEntityError):
            return AIModelError(
                "The AI service rejected the request. The configured model may not support "
                "structured outputs or one of the settings (such as OPENAI_REASONING_EFFORT)."
            )
        if isinstance(exc, openai.InternalServerError):
            return AIConnectionError(
                "The AI service is temporarily unavailable. Please try again shortly."
            )
        if isinstance(exc, openai.LengthFinishReasonError | openai.ContentFilterFinishReasonError):
            return AIResponseError()
        return AIResponseError(
            "An unexpected error occurred while contacting the AI service. Please try again."
        )


# ------------------------------------------------------------ model discovery

# Model families that cannot generate structured text through the Responses API.
_EXCLUDED_MODEL_MARKERS = (
    "embedding",
    "tts",
    "whisper",
    "dall-e",
    "image",
    "audio",
    "realtime",
    "transcribe",
    "moderation",
    "search",
    "instruct",
    "computer-use",
    "deep-research",
    "codex",
    "babbage",
    "davinci",
    "sora",
    "live",
)
_TEXT_MODEL_PREFIXES = ("gpt-", "o1", "o3", "o4", "o5", "chatgpt-")


def filter_text_models(models: list[tuple[str, int]]) -> list[str]:
    """Keep likely text-generation models, newest first.

    ``models`` is a list of ``(model_id, created_timestamp)`` pairs. This is a
    heuristic — use :func:`check_model` to confirm a model actually works.
    """
    keep = [
        (model_id, created)
        for model_id, created in models
        if model_id.startswith(_TEXT_MODEL_PREFIXES)
        and not any(marker in model_id for marker in _EXCLUDED_MODEL_MARKERS)
    ]
    keep.sort(key=lambda pair: (-pair[1], pair[0]))
    return [model_id for model_id, _ in keep]


def list_available_models(
    api_key: str, *, timeout_seconds: float = 20.0, client: Any | None = None
) -> list[str]:
    """Return text-generation models the key can access (newest first).

    Also serves as an API-key check: an invalid key raises AIAuthenticationError.
    """
    client = client or openai.OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
    try:
        models = [(m.id, int(getattr(m, "created", 0) or 0)) for m in client.models.list()]
    except openai.OpenAIError as exc:
        raise LLMService._map_api_error(exc, "list_models") from None
    return filter_text_models(models)


class _ModelCheck(BaseModel):
    reply: str


def check_model(llm: LLMService) -> bool:
    """Send a tiny structured-output request. Returns True, or raises a TutorError."""
    prompt = PromptSpec(
        task="model_check",
        instructions="Reply with a JSON object whose 'reply' field is the Japanese word for "
        "'hello'.",
        input="Say hello.",
        max_output_tokens=2000,
    )
    llm.generate_structured(prompt, _ModelCheck)
    return True
