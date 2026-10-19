"""Application error hierarchy.

Every error carries a ``user_message`` that is safe to show in the UI. Internal
details (exception text, request IDs, SQL) go to the logs only, never to the
learner.
"""

from __future__ import annotations


class TutorError(Exception):
    """Base class for every expected, user-reportable failure."""

    default_message = "Something went wrong. Please try again."
    retryable = True

    def __init__(self, user_message: str | None = None, *, detail: str | None = None) -> None:
        self.user_message = user_message or self.default_message
        # ``detail`` is for logs; it is never rendered in the UI.
        super().__init__(detail or self.user_message)


class InputValidationError(TutorError):
    default_message = "Please check your input and try again."
    retryable = False


class ConfigurationError(TutorError):
    default_message = (
        "The AI tutor is not configured yet. Open the Settings page for setup instructions."
    )
    retryable = False


class AIAuthenticationError(TutorError):
    default_message = (
        "The OpenAI API rejected the configured API key. Check that the key is correct, "
        "active, and has API access, then restart the app."
    )
    retryable = False


class AIModelError(TutorError):
    default_message = (
        "The configured AI model is unavailable or does not support this request. "
        "Check the OPENAI_MODEL setting."
    )
    retryable = False


class AIRateLimitError(TutorError):
    default_message = (
        "The AI service is receiving too many requests right now. Wait a moment and try again."
    )


class AIQuotaError(TutorError):
    default_message = (
        "Your OpenAI account has no remaining API quota. Check your billing settings on the "
        "OpenAI platform. (A ChatGPT subscription does not include API usage.)"
    )
    retryable = False


class AIConnectionError(TutorError):
    default_message = (
        "Could not reach the AI service. Check your internet connection and try again."
    )


class AIResponseError(TutorError):
    default_message = (
        "The AI returned a response that could not be used. Please try again — "
        "rephrasing your request can help."
    )


class DatabaseError(TutorError):
    default_message = "Your learning data could not be saved or loaded. Please try again."
