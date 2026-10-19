"""Sentence correction."""

from __future__ import annotations

from core.constants import MAX_CONTEXT_LENGTH, MAX_SENTENCE_LENGTH
from core.validation import clean_text, validate_level
from prompts.correction import build_correction_prompt
from schemas.correction import SentenceCorrectionResponse
from services.llm_service import LLMService


def correct_sentence(
    llm: LLMService,
    *,
    sentence: str,
    level: str,
    context: str | None = None,
    style: str = "balanced",
) -> SentenceCorrectionResponse:
    """Review a learner's Japanese sentence and return a validated correction."""
    sentence = clean_text(sentence, field="A Japanese sentence", max_length=MAX_SENTENCE_LENGTH)
    context = (
        clean_text(context, field="Context", max_length=MAX_CONTEXT_LENGTH, required=False) or None
    )
    level = validate_level(level)
    prompt = build_correction_prompt(sentence=sentence, level=level, style=style, context=context)
    result = llm.generate_structured(prompt, SentenceCorrectionResponse)
    # Always show the learner's own text as the original, not the model's echo of it.
    if result.original_sentence != sentence:
        result = result.model_copy(update={"original_sentence": sentence})
    return result
