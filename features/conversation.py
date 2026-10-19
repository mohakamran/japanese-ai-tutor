"""Conversation practice with a bounded message history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from core.constants import (
    CONVERSATION_SCENARIOS,
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_CONVERSATION_MESSAGES_KEPT,
    MAX_CONVERSATION_MESSAGES_SENT,
    MAX_SENTENCE_LENGTH,
)
from core.validation import clean_text, validate_choice, validate_level
from prompts.base import wrap_learner_input
from prompts.conversation import build_conversation_prompt, build_sentence_explanation_prompt
from schemas.conversation import ConversationResponse, SentenceExplanationResponse
from services.llm_service import LLMService


@dataclass(frozen=True)
class ConversationTurn:
    role: Literal["learner", "tutor"]
    text: str  # learner message, or the tutor's Japanese reply
    response: ConversationResponse | None = None  # set for tutor turns


@dataclass
class Conversation:
    """One practice conversation. Lives in session state only (not persisted)."""

    scenario: str
    level: str
    turns: list[ConversationTurn] = field(default_factory=list)

    def add(self, turn: ConversationTurn) -> None:
        self.turns.append(turn)
        if len(self.turns) > MAX_CONVERSATION_MESSAGES_KEPT:
            self.turns = self.turns[-MAX_CONVERSATION_MESSAGES_KEPT:]


def build_model_messages(
    turns: Sequence[ConversationTurn], *, max_messages: int = MAX_CONVERSATION_MESSAGES_SENT
) -> list[dict[str, Any]]:
    """Convert the most recent turns into chat messages for the model.

    Only the Japanese text of tutor replies is sent back, not translations or
    notes, to keep requests small.
    """
    recent = list(turns)[-max_messages:] if max_messages > 0 else []
    messages = []
    for turn in recent:
        if turn.role == "learner":
            messages.append({"role": "user", "content": wrap_learner_input(turn.text)})
        else:
            messages.append({"role": "assistant", "content": turn.text})
    return messages


def _validate_context(scenario: str, level: str) -> tuple[str, str]:
    return (
        validate_choice(scenario, CONVERSATION_SCENARIOS, field="Scenario"),
        validate_level(level),
    )


def start_conversation(
    llm: LLMService, *, scenario: str, level: str, style: str = "balanced"
) -> Conversation:
    """Create a conversation and get the tutor's opening line."""
    scenario, level = _validate_context(scenario, level)
    prompt = build_conversation_prompt(
        scenario=scenario,
        level=level,
        style=style,
        corrections_enabled=False,
        history=[],
        learner_message=None,
    )
    response = llm.generate_structured(prompt, ConversationResponse)
    conversation = Conversation(scenario=scenario, level=level)
    conversation.add(ConversationTurn("tutor", response.reply_japanese, response))
    return conversation


def send_message(
    llm: LLMService,
    conversation: Conversation,
    message: str,
    *,
    corrections_enabled: bool,
    style: str = "balanced",
) -> ConversationResponse:
    """Send a learner message and append both turns to ``conversation``.

    The conversation is only modified after a valid reply arrives, so a failed
    request leaves it unchanged and the learner can retry.
    """
    message = clean_text(message, field="A message", max_length=MAX_CHAT_MESSAGE_LENGTH)
    scenario, level = _validate_context(conversation.scenario, conversation.level)
    prompt = build_conversation_prompt(
        scenario=scenario,
        level=level,
        style=style,
        corrections_enabled=corrections_enabled,
        history=build_model_messages(conversation.turns),
        learner_message=message,
    )
    response = llm.generate_structured(prompt, ConversationResponse)
    if not corrections_enabled and response.feedback is not None:
        response = response.model_copy(update={"feedback": None})
    conversation.add(ConversationTurn("learner", message))
    conversation.add(ConversationTurn("tutor", response.reply_japanese, response))
    return response


def explain_sentence(
    llm: LLMService, *, sentence: str, level: str, style: str = "balanced"
) -> SentenceExplanationResponse:
    """Break a Japanese sentence down piece by piece."""
    sentence = clean_text(sentence, field="A sentence", max_length=MAX_SENTENCE_LENGTH)
    level = validate_level(level)
    prompt = build_sentence_explanation_prompt(sentence=sentence, level=level, style=style)
    return llm.generate_structured(prompt, SentenceExplanationResponse)
