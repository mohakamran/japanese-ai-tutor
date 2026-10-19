"""Learning Progress page. Every number here is computed from stored records."""

from __future__ import annotations

from collections import Counter

import plotly.graph_objects as go
import streamlit as st

from core.constants import QUIZ_TYPES, SAVED_VOCABULARY_QUIZ_TYPE
from core.errors import DatabaseError
from features.progress import load_progress
from ui import components as c
from ui.services import get_repository

SERIES_COLOR = "#38506B"  # one neutral hue; red is reserved for brand accents
GRID_COLOR = "#ECE8E3"
INK = "#1F2328"
MUTED = "#5B6168"


def _layout(
    fig: go.Figure,
    *,
    y_title: str,
    y_range: list[float] | None = None,
    height: int = 300,
    bars: int = 0,
) -> go.Figure:
    # Few bars would otherwise stretch into wide slabs; widen the gap instead.
    bargap = 0.35 if bars >= 6 else 0.85 - 0.08 * bars
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": INK},
        showlegend=False,
        hoverlabel={"bgcolor": "white", "font_color": INK},
        bargap=bargap,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID_COLOR, tickfont={"color": MUTED})
    if bars:
        fig.update_xaxes(type="category")
    fig.update_yaxes(
        title=y_title,
        gridcolor=GRID_COLOR,
        zeroline=False,
        tickfont={"color": MUTED},
        range=y_range,
    )
    return fig


def render() -> None:
    c.page_header(
        "Learning Progress", "進歩 · Shinpo", "Your real learning history, from saved records."
    )
    repo = get_repository()
    try:
        summary = load_progress(repo, attempts=100)
        daily = repo.activity_counts_by_day(days=30)
        words = repo.list_saved_vocabulary()
    except DatabaseError as exc:
        c.show_error(exc)
        return

    if summary.is_empty and not summary.stats.vocabulary_reviews:
        c.empty_state(
            "進",
            "No progress recorded yet",
            "Your statistics appear here as soon as you save words, view grammar lessons, or "
            "complete quizzes. Nothing here is estimated — it is all from your own activity.",
        )
        return

    s = summary.stats
    tiles = [
        ("Words saved", s.saved_words, "語", "indigo"),
        ("Flashcard reviews", s.vocabulary_reviews, "復", "indigo"),
        ("Quizzes completed", s.quizzes_completed, "試", "gold"),
        (
            "Average quiz score",
            f"{s.average_score:.1f}%" if s.average_score is not None else "—",
            "点",
            "green",
        ),
        ("Grammar lessons viewed", s.grammar_lessons_viewed, "文", "red"),
        ("Grammar lessons saved", s.grammar_lessons_saved, "保", "red"),
        ("Sentences checked", s.sentences_checked, "直", "gold"),
        ("Conversations started", s.conversations_started, "話", "green"),
    ]
    for row in (tiles[:4], tiles[4:]):
        cols = st.columns(4)
        for col, (label, value, icon, accent) in zip(cols, row, strict=True):
            with col:
                c.stat_tile(label, value, icon=icon, accent=accent)
        st.write("")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### Quiz scores over time")
        attempts = list(reversed(summary.recent_attempts))  # oldest first
        if len(attempts) >= 2:
            fig = go.Figure(
                go.Scatter(
                    x=[f"#{i}" for i in range(1, len(attempts) + 1)],
                    y=[a.score for a in attempts],
                    mode="lines+markers",
                    line={"color": SERIES_COLOR, "width": 2},
                    marker={
                        "size": 8,
                        "color": SERIES_COLOR,
                        "line": {"color": "white", "width": 2},
                    },
                    customdata=[
                        [a.topic, a.correct_answers, a.total_questions, a.attempted_at[:10]]
                        for a in attempts
                    ],
                    hovertemplate="%{customdata[0]} · %{customdata[3]}<br>%{y:.0f}% "
                    "(%{customdata[1]}/%{customdata[2]})<extra></extra>",
                )
            )
            st.plotly_chart(
                _layout(fig, y_title="Score (%)", y_range=[0, 105]).update_xaxes(
                    type="category", title="Quiz (oldest → newest)"
                ),
                config={"displayModeBar": False},
            )
        else:
            st.caption("Complete at least two quizzes to see a trend.")
    with right:
        st.markdown("#### Activity in the last 30 days")
        if daily:
            fig = go.Figure(
                go.Bar(
                    x=[d for d, _ in daily],
                    y=[n for _, n in daily],
                    marker={"color": SERIES_COLOR, "cornerradius": 4},
                    hovertemplate="%{x}<br>%{y} activities<extra></extra>",
                )
            )
            st.plotly_chart(
                _layout(fig, y_title="Activities", bars=len(daily)),
                config={"displayModeBar": False},
            )
        else:
            st.caption("No activity in the last 30 days.")

    if words:
        st.markdown("#### Saved words by topic")
        by_topic = Counter(w.topic for w in words).most_common(12)
        fig = go.Figure(
            go.Bar(
                x=[n for _, n in by_topic][::-1],
                y=[t for t, _ in by_topic][::-1],
                orientation="h",
                marker={"color": SERIES_COLOR, "cornerradius": 4},
                hovertemplate="%{y}: %{x} words<extra></extra>",
            )
        )
        fig = _layout(fig, y_title="", height=90 + 40 * len(by_topic), bars=len(by_topic))
        fig.update_xaxes(type="linear", gridcolor=GRID_COLOR, showgrid=True)
        fig.update_yaxes(type="category", gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, config={"displayModeBar": False})

    if summary.recent_attempts:
        st.markdown("#### Quiz history")
        st.dataframe(
            [
                {
                    "Date (UTC)": a.attempted_at.replace("T", " ").rstrip("Z"),
                    "Topic": a.topic,
                    "Type": "Saved vocabulary"
                    if a.quiz_type == SAVED_VOCABULARY_QUIZ_TYPE
                    else QUIZ_TYPES.get(a.quiz_type, a.quiz_type),
                    "Correct": f"{a.correct_answers}/{a.total_questions}",
                    "Score (%)": a.score,
                }
                for a in summary.recent_attempts
            ],
            hide_index=True,
        )

    if daily:
        with st.expander("Activity table"):
            st.dataframe([{"Date (UTC)": d, "Activities": n} for d, n in daily], hide_index=True)

    st.markdown("#### Recent activity")
    c.timeline(
        [
            (item.description, item.created_at.replace("T", " ").rstrip("Z") + " UTC")
            for item in summary.recent_activity
        ]
    )
