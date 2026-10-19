"""Prompt templates for quiz generation and wrong-answer explanations."""

from __future__ import annotations

from core.constants import QUESTION_TYPES
from prompts.base import PromptSpec, build_instructions, wrap_learner_input

MAX_OUTPUT_TOKENS = 8000
EXPLANATION_MAX_OUTPUT_TOKENS = 3000

QUESTION_TYPE_GUIDE = """\
Question types (every question is answered by choosing ONE option):
- multiple_choice: a general question about meaning, usage or grammar.
- translation_ja_en: show a Japanese sentence in japanese_text; options are English
  translations.
- translation_en_ja: put the English sentence in the prompt; options are Japanese sentences.
- fill_in_blank: japanese_text contains a sentence with ＿＿ for the blank; options are the
  words or particles that could fill it.
- sentence_construction: options are different word orders / constructions of the same
  sentence; exactly one is natural and grammatical.
- vocabulary_recall: ask for the meaning of a Japanese word or the Japanese for an English
  word.
- grammar: ask which form or pattern is correct in a given situation."""

QUIZ_TASK = """\
Write a Japanese quiz for the learner.

Requirements:
- Write exactly {count} questions on the learner's topic.
- Question type: {type_rule}
- Difficulty: {difficulty} for the learner's level.
- Each question has 4 options (sentence_construction may use 3), all distinct.
- Exactly one option is correct and defensible. Distractors must be plausible but clearly
  wrong to a careful learner — never a second answer that is also acceptable, and never
  merely a different but valid word order or synonym.
- correct_option_index is the zero-based index of the correct option. Vary its position.
- Do not reveal the answer in the prompt, japanese_text, reading or romaji. Set reading and
  romaji to null if they would give the answer away (for example, in reading questions).
- "explanation" says why the answer is right and briefly why the others are wrong.
- Questions should not repeat each other.

{type_guide}"""

EXPLANATION_TASK = """\
The learner answered a quiz question incorrectly. Help them understand the mistake.

- Explain why the correct answer is right.
- Explain what is wrong with the learner's choice, or what it would actually mean.
- Give one extra example sentence that uses the correct form, with romaji and English.
- End with one short tip that helps them remember.
- If the learner's choice could be acceptable in some context, say so honestly."""


def build_quiz_prompt(
    *, topic: str, level: str, count: int, quiz_type: str, difficulty: str, style: str
) -> PromptSpec:
    if quiz_type == "mixed":
        type_rule = "mix several different question types from the list below."
    else:
        type_rule = f'use only "{quiz_type}" ({QUESTION_TYPES[quiz_type]}) questions.'
    task = QUIZ_TASK.format(
        count=count, type_rule=type_rule, difficulty=difficulty, type_guide=QUESTION_TYPE_GUIDE
    )
    return PromptSpec(
        task="quiz",
        instructions=build_instructions(task=task, level=level, style=style),
        input=f"Quiz topic:\n{wrap_learner_input(topic)}",
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def build_answer_explanation_prompt(
    *,
    level: str,
    style: str,
    prompt_text: str,
    japanese_text: str | None,
    options: list[str],
    correct_option: str,
    selected_option: str,
) -> PromptSpec:
    # Quiz content is model-generated, but it is still wrapped as data.
    question_block = "\n".join(
        [
            f"Question: {prompt_text}",
            f"Japanese text: {japanese_text or '(none)'}",
            "Options: " + " | ".join(options),
            f"Correct answer: {correct_option}",
            f"Learner's answer: {selected_option}",
        ]
    )
    return PromptSpec(
        task="answer_explanation",
        instructions=build_instructions(task=EXPLANATION_TASK, level=level, style=style),
        input=wrap_learner_input(question_block),
        max_output_tokens=EXPLANATION_MAX_OUTPUT_TOKENS,
    )
