"""Dashboard: greeting, headline stats, word of the day, next step, and activity."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import streamlit as st

from core.constants import LEVELS
from core.errors import TutorError
from features.progress import (
    load_progress,
    recommend_next_activity,
    study_streak,
    word_of_the_day,
)
from ui import components as c
from ui.navigation import page_link
from ui.services import ai_configured, get_preferences, get_repository, require_user

_TILES = [
    ("vocab", "vocabulary", "語", "Vocabulary", "Build topic word lists and review flashcards."),
    ("grammar", "grammar", "文", "Grammar Tutor", "Ask any grammar question in plain English."),
    ("quiz", "quiz", "試", "Quiz Center", "Seven question types, scored fairly in code."),
    ("correction", "correction", "直", "Sentence Correction", "Write Japanese, get feedback."),
    ("conversation", "conversation", "話", "Conversation", "Role-play real-life situations."),
    ("progress", "progress", "進", "Progress", "See your streak, scores and activity."),
]


def _local_now() -> datetime:
    try:
        tz = st.context.timezone
        return datetime.now(ZoneInfo(tz)) if tz else datetime.now(UTC)
    except Exception:  # unknown timezone name or no browser context
        return datetime.now(UTC)


def _greeting(hour: int) -> tuple[str, str]:
    if 5 <= hour < 11:
        return "おはようございます", "Good morning"
    if 11 <= hour < 18:
        return "こんにちは", "Good afternoon"
    return "こんばんは", "Good evening"


def render() -> None:
    try:
        user = require_user()
        prefs = get_preferences()
        repo = get_repository()
        summary = load_progress(repo, attempts=5)
        active_days = [d for d, _ in repo.activity_counts_by_day(days=400)]
        words = repo.list_saved_vocabulary()
    except TutorError as exc:
        c.show_error(exc)
        return

    japanese, english = _greeting(_local_now().hour)
    first_name = user.display_name.split()[0]
    c.page_header(
        f"{english}, {first_name}!",
        japanese,
        "Every day of practice counts. Pick up where you left off, or try something new.",
        mark="日",
    )
    if not ai_configured():
        c.ai_setup_notice()

    stats = summary.stats
    streak = study_streak(active_days)
    cols = st.columns(4)
    with cols[0]:
        c.stat_tile(
            "Study streak",
            f"{streak} day{'s' if streak != 1 else ''}",
            icon="炎",
            foot="Keep it going today!" if streak else "Study today to start one",
            accent="red",
        )
    with cols[1]:
        c.stat_tile(
            "Words saved",
            stats.saved_words,
            icon="語",
            foot=f"{stats.vocabulary_reviews} flashcard review"
            f"{'s' if stats.vocabulary_reviews != 1 else ''}",
            accent="indigo",
        )
    with cols[2]:
        c.stat_tile(
            "Quizzes completed",
            stats.quizzes_completed,
            icon="試",
            foot=f"{stats.grammar_lessons_viewed} grammar lesson"
            f"{'s' if stats.grammar_lessons_viewed != 1 else ''} viewed",
            accent="gold",
        )
    with cols[3]:
        c.stat_tile(
            "Your level",
            LEVELS[prefs.proficiency_level].split(" (")[0],
            icon="級",
            foot=LEVELS[prefs.proficiency_level].split("(")[-1].rstrip(")"),
            accent="green",
        )

    st.write("")
    left, right = st.columns([1.25, 1], gap="large")
    with left:
        rec = recommend_next_activity(summary)
        c.card(
            c.label("Recommended next")
            + f'<div class="jt-card-title">{c.esc(rec.title)}</div>'
            + c.text(rec.reason, muted=True),
            variant="accent",
        )
        page_link(rec.page, "Start now →", icon=":material/arrow_forward:")

        st.markdown("#### Recent quiz scores")
        if summary.recent_attempts:
            for attempt in summary.recent_attempts[:4]:
                kind = "ok" if attempt.score >= 80 else "warn" if attempt.score >= 50 else "err"
                c.card(
                    c.badge(f"{attempt.score:g}%", kind)
                    + c.badge(attempt.attempted_at[:10], "ai")
                    + c.text(
                        f"{attempt.topic} · {attempt.correct_answers}/"
                        f"{attempt.total_questions} correct"
                    )
                )
        else:
            st.caption("No quizzes yet — your scores will appear here.")

    with right:
        wotd = word_of_the_day(words)
        if wotd is not None:
            c.html_block(
                '<div class="jt-wotd">'
                + c.label("Word of the day")
                + c.jp_markup(
                    wotd.word,
                    reading=wotd.reading,
                    romaji=wotd.romaji,
                    show_romaji=prefs.romaji_enabled,
                    size="lg",
                )
                + f'<div class="jt-en"><b>{c.esc(wotd.meaning)}</b></div>'
                + f'<div class="jt-en" style="opacity:.85;margin-top:.6rem">'
                f'<span lang="ja">{c.esc(wotd.example_sentence)}</span><br>'
                f"{c.esc(wotd.example_translation)}</div></div>"
            )
        else:
            c.card(
                c.label("Word of the day")
                + c.text(
                    "Save a few words in Vocabulary and one will be featured here every day.",
                    muted=True,
                ),
                variant="paper",
            )
        c.card(
            c.progress_ring(
                stats.average_score,
                label="Average quiz score",
                caption=f"across {stats.quizzes_completed} quiz"
                f"{'zes' if stats.quizzes_completed != 1 else ''}"
                if stats.quizzes_completed
                else "Take a quiz to see your score",
            )
        )
        st.markdown("#### Recent activity")
        if summary.recent_activity:
            c.timeline(
                [
                    (a.description, a.created_at.replace("T", " ").rstrip("Z") + " UTC")
                    for a in summary.recent_activity[:6]
                ]
            )
        else:
            st.caption("Nothing yet — your learning activity will appear here.")

    st.markdown("#### Explore")
    for row in (_TILES[:3], _TILES[3:]):
        cols = st.columns(3)
        for col, (key, page, kanji, title, text) in zip(cols, row, strict=True):
            with col:
                c.nav_tile(key, page, kanji=kanji, title=title, text=text)
