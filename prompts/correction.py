"""Prompt template for sentence correction."""

from __future__ import annotations

from prompts.base import PromptSpec, build_instructions, wrap_learner_input

MAX_OUTPUT_TOKENS = 4000

TASK = """\
Review a Japanese sentence written by the learner.

Requirements:
- First work out what the learner most likely meant (use the context if they gave one).
- Decide the verdict carefully:
  * "correct": grammatical and natural; no change needed.
  * "natural_but_improvable": grammatical, but a more natural or appropriate phrasing exists.
  * "needs_correction": contains grammatical or word-choice errors.
  * "ambiguous": the meaning cannot be determined without more context.
- Do NOT mark a sentence wrong just because it is unusual, casual, or differs from a textbook
  phrasing. Valid alternatives, dropped subjects and casual speech are not errors.
- corrected_sentence: only when a correction is needed; otherwise null.
- reading / romaji / english_translation describe the corrected sentence if there is one,
  otherwise the original.
- grammar_issues and word_choice_issues: list each problem separately with a severity:
  "error" (ungrammatical), "unnatural" (grammatical but odd), "stylistic" (optional).
  Use empty lists when there are none.
- natural_alternative: a more natural phrasing if useful, otherwise null.
- assumptions: state any assumption you made about meaning or context, otherwise null.
- clarification_question: if the verdict is "ambiguous", ask the learner what they meant.
- If the learner wrote in romaji or English, say so kindly, and show the Japanese.
- learning_tip: one short, practical tip related to this sentence."""


def build_correction_prompt(
    *, sentence: str, level: str, style: str, context: str | None
) -> PromptSpec:
    parts = [f"Sentence to review:\n{wrap_learner_input(sentence)}"]
    if context:
        parts.append(f"Context or intended meaning:\n{wrap_learner_input(context)}")
    else:
        parts.append("No context was given; state any assumptions you make.")
    return PromptSpec(
        task="correction",
        instructions=build_instructions(task=TASK, level=level, style=style),
        input="\n\n".join(parts),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
