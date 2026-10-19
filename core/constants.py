"""Application-wide constants: allowed values, labels, and input limits.

Keeping these in one place means the UI, the business logic, the prompts and the
tests all agree on what a "valid" level, topic or quiz type is.
"""

from __future__ import annotations

from typing import Final, Literal

# --- Proficiency levels -----------------------------------------------------

ProficiencyLevel = Literal[
    "beginner", "elementary", "intermediate", "upper_intermediate", "advanced"
]

LEVELS: Final[dict[str, str]] = {
    "beginner": "Beginner (≈ JLPT N5)",
    "elementary": "Elementary (≈ JLPT N4)",
    "intermediate": "Intermediate (≈ JLPT N3)",
    "upper_intermediate": "Upper intermediate (≈ JLPT N2)",
    "advanced": "Advanced (≈ JLPT N1)",
}
DEFAULT_LEVEL: Final = "beginner"

# --- Learner preferences ----------------------------------------------------

ExplanationStyle = Literal["concise", "balanced", "detailed"]
EXPLANATION_STYLES: Final[dict[str, str]] = {
    "concise": "Concise — short and to the point",
    "balanced": "Balanced — clear explanation with examples",
    "detailed": "Detailed — in-depth explanations and nuance",
}
DEFAULT_EXPLANATION_STYLE: Final = "balanced"

Difficulty = Literal["easy", "medium", "hard"]
DIFFICULTIES: Final[dict[str, str]] = {
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
}
DEFAULT_DIFFICULTY: Final = "medium"

# --- Topics -----------------------------------------------------------------

VOCABULARY_TOPICS: Final[list[str]] = [
    "Greetings and introductions",
    "Food and drink",
    "Family",
    "Numbers and counting",
    "Time and dates",
    "Shopping",
    "Travel and transportation",
    "School and study",
    "Work and office",
    "Weather and seasons",
    "Hobbies and free time",
    "Body and health",
    "Home and furniture",
    "Emotions and feelings",
    "Nature and animals",
    "City and directions",
    "Common verbs",
    "Common adjectives",
]

GRAMMAR_TOPICS: Final[list[str]] = [
    "Particles (は, が, を, に, で, へ, と, も)",
    "Verb conjugation (ます-form, て-form, past, negative)",
    "Adjectives (い-adjectives and な-adjectives)",
    "Polite vs. casual speech",
    "Questions and question words",
    "Giving and receiving (あげる, くれる, もらう)",
    "Conditionals (たら, ば, と, なら)",
    "Potential, passive and causative forms",
    "Expressing desire and intention",
    "Comparisons",
    "Keigo (honorific and humble language)",
    "Sentence-ending particles (よ, ね, よね)",
]

QUIZ_TOPICS: Final[list[str]] = [
    *VOCABULARY_TOPICS,
    "Particles",
    "Verb conjugation",
    "Adjectives",
    "Polite vs. casual speech",
    "Counters",
    "Keigo",
]

# --- Quizzes ----------------------------------------------------------------

QuestionType = Literal[
    "multiple_choice",
    "translation_ja_en",
    "translation_en_ja",
    "fill_in_blank",
    "sentence_construction",
    "vocabulary_recall",
    "grammar",
]

QUESTION_TYPES: Final[dict[str, str]] = {
    "multiple_choice": "Multiple choice",
    "translation_ja_en": "Japanese → English translation",
    "translation_en_ja": "English → Japanese translation",
    "fill_in_blank": "Fill in the blank",
    "sentence_construction": "Sentence construction",
    "vocabulary_recall": "Vocabulary recall",
    "grammar": "Grammar exercise",
}

# The quiz types a learner can request: every question type plus a mix.
QUIZ_TYPES: Final[dict[str, str]] = {"mixed": "Mixed (all types)", **QUESTION_TYPES}
SAVED_VOCABULARY_QUIZ_TYPE: Final = "saved_vocabulary"

# --- Conversation -----------------------------------------------------------

CONVERSATION_SCENARIOS: Final[dict[str, str]] = {
    "daily": "Daily conversation with a friend",
    "self_introduction": "Introducing yourself",
    "restaurant": "Ordering at a restaurant",
    "shopping": "Shopping at a store",
    "convenience_store": "At a convenience store (コンビニ)",
    "school": "At school with a classmate",
    "travel": "Travel — asking for directions",
    "hotel": "Checking in at a hotel",
    "train_station": "Buying a ticket at a train station",
    "doctor": "Visiting a doctor",
    "work": "Small talk with a coworker",
}

# --- Input limits -----------------------------------------------------------

MAX_TOPIC_LENGTH: Final = 60
MAX_GRAMMAR_QUESTION_LENGTH: Final = 1000
MAX_SENTENCE_LENGTH: Final = 300
MAX_CONTEXT_LENGTH: Final = 500
MAX_CHAT_MESSAGE_LENGTH: Final = 500

MIN_VOCABULARY_COUNT: Final = 3
MAX_VOCABULARY_COUNT: Final = 15
MIN_QUIZ_QUESTIONS: Final = 3
MAX_QUIZ_QUESTIONS: Final = 15
MIN_SAVED_WORDS_FOR_QUIZ: Final = 4

MIN_QUIZ_OPTIONS: Final = 2
MAX_QUIZ_OPTIONS: Final = 6

# Bounded histories keep API cost predictable.
MAX_GRAMMAR_HISTORY_TURNS: Final = 3
MAX_CONVERSATION_MESSAGES_SENT: Final = 12
MAX_CONVERSATION_MESSAGES_KEPT: Final = 40
