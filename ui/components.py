"""Reusable UI building blocks.

Every piece of dynamic text (AI output, learner input, stored data) that goes
into HTML passes through :func:`esc`, so model output can never inject markup
or scripts into the page.
"""

from __future__ import annotations

import html
import logging
from collections.abc import Callable
from typing import ParamSpec, TypeVar

import streamlit as st

from core.errors import ConfigurationError, TutorError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

AI_NOTICE = "AI-generated · may contain mistakes — verify important details"


def esc(text: object) -> str:
    """HTML-escape text and neutralise characters Streamlit treats specially."""
    escaped = html.escape("" if text is None else str(text), quote=True)
    # Newlines become <br> so a blank line cannot end the HTML block; $ would start LaTeX.
    return escaped.replace("$", "&#36;").replace("\n", "<br>")


def html_block(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def page_header(title: str, kicker: str, subtitle: str, *, mark: str | None = None) -> None:
    """Hero banner: kicker, title, subtitle, and a 'rising sun' with one kanji."""
    mark = mark or kicker[:1]
    html_block(
        f'<div class="jt-hero"><div class="jt-hero-text">'
        f'<div class="jt-kicker" lang="ja">{esc(kicker)}</div>'
        f'<h1 class="jt-title">{esc(title)}</h1>'
        f'<div class="jt-subtitle">{esc(subtitle)}</div></div>'
        f'<div class="jt-hero-sun" aria-hidden="true"><span lang="ja">{esc(mark)}</span></div>'
        "</div>"
    )


_ACCENTS = {
    "red": ("var(--jt-red)", "var(--jt-red-soft)"),
    "indigo": ("var(--jt-indigo)", "var(--jt-indigo-soft)"),
    "gold": ("var(--jt-gold)", "var(--jt-gold-soft)"),
    "green": ("var(--jt-green)", "var(--jt-green-soft)"),
}


def stat_tile(label: str, value: object, *, icon: str, foot: str = "", accent: str = "red") -> None:
    """A KPI tile. ``icon`` is a single kanji/character shown in a coloured chip."""
    color, soft = _ACCENTS.get(accent, _ACCENTS["red"])
    html_block(
        f'<div class="jt-stat" style="--accent:{color};--accent-soft:{soft}">'
        f'<div class="jt-stat-top"><div class="jt-stat-icon" lang="ja">{esc(icon)}</div>'
        f'<div class="jt-stat-label">{esc(label)}</div></div>'
        f'<div class="jt-stat-value">{esc(value)}</div>'
        + (f'<div class="jt-stat-foot">{esc(foot)}</div>' if foot else "")
        + "</div>"
    )


def progress_ring(percent: float | None, *, label: str, caption: str, size: int = 92) -> str:
    """An SVG ring showing a percentage (or an empty ring when there is no data)."""
    stroke = 9
    radius = (size - stroke) / 2
    circumference = 2 * 3.14159265 * radius
    value = 0.0 if percent is None else max(0.0, min(100.0, float(percent)))
    dash = circumference * value / 100
    color = "#2F7A55" if value >= 80 else "#B8873B" if value >= 50 else "#C8372D"
    center = size / 2
    text = "—" if percent is None else f"{value:.0f}%"
    arc = (
        f'<circle cx="{center}" cy="{center}" r="{radius}" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-dasharray="{dash:.1f} {circumference:.1f}" '
        f'transform="rotate(-90 {center} {center})"/>'
        if dash > 0
        else ""
    )
    return (
        f'<div class="jt-ring"><svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'role="img" aria-label="{esc(label)} {esc(text)}">'
        f'<circle cx="{center}" cy="{center}" r="{radius}" fill="none" stroke="#EFE7DB" '
        f'stroke-width="{stroke}"/>'
        + arc
        + f'<text x="50%" y="54%" text-anchor="middle" font-size="19" font-weight="800" '
        f'fill="#1C1E26">{esc(text)}</text></svg>'
        f'<div><div class="jt-stat-label">{esc(label)}</div>'
        f'<div class="jt-muted">{esc(caption)}</div></div></div>'
    )


def timeline(items: list[tuple[str, str]]) -> None:
    """A vertical activity timeline of (description, when) pairs."""
    html_block(
        '<div class="jt-timeline">'
        + "".join(
            f'<div class="jt-tl-item"><div class="jt-text">{esc(text)}</div>'
            f'<div class="jt-tl-when">{esc(when)}</div></div>'
            for text, when in items
        )
        + "</div>"
    )


def nav_tile(key: str, page_key: str, *, kanji: str, title: str, text: str) -> None:
    """A clickable feature tile: styled keyed container with a native page link."""
    from ui.navigation import page_link  # local import avoids a cycle at module load

    with st.container(key=f"tile_{key}"):
        html_block(
            f'<div class="jt-tile-kanji" lang="ja">{esc(kanji)}</div>'
            f'<div class="jt-tile-title">{esc(title)}</div>'
            f'<div class="jt-tile-text">{esc(text)}</div>'
        )
        page_link(page_key, "Open →")


def badge(text: str, kind: str = "info") -> str:
    kind = kind if kind in {"ok", "warn", "err", "info", "ai"} else "info"
    return f'<span class="jt-badge {kind}">{esc(text)}</span>'


def ai_notice() -> None:
    html_block(badge(AI_NOTICE, "ai"))


def jp_markup(
    japanese: str,
    *,
    reading: str | None = None,
    romaji: str | None = None,
    english: str | None = None,
    show_romaji: bool = True,
    size: str = "",
) -> str:
    """Japanese text with optional reading, romaji and translation lines."""
    size_class = {"lg": " jt-lg", "sm": " jt-sm"}.get(size, "")
    parts = [f'<div class="jt-jp{size_class}" lang="ja">{esc(japanese)}</div>']
    if reading and reading != japanese:
        parts.append(f'<div class="jt-reading" lang="ja">{esc(reading)}</div>')
    if romaji and show_romaji:
        parts.append(f'<div class="jt-romaji">{esc(romaji)}</div>')
    if english:
        parts.append(f'<div class="jt-en">{esc(english)}</div>')
    return "".join(parts)


def card(inner_markup: str, *, variant: str = "") -> None:
    classes = "jt-card" + "".join(f" jt-{v}" for v in variant.split() if v)
    html_block(f'<div class="{classes}">{inner_markup}</div>')


def label(text: str) -> str:
    return f'<div class="jt-label">{esc(text)}</div>'


def text(content: str, *, muted: bool = False) -> str:
    return f'<div class="{"jt-muted" if muted else "jt-text"}">{esc(content)}</div>'


def empty_state(icon: str, title: str, message: str) -> None:
    html_block(
        f'<div class="jt-empty"><div class="jt-empty-icon" lang="ja">{esc(icon[:1])}</div>'
        f'<div class="jt-empty-title">{esc(title)}</div>'
        f'<div class="jt-empty-text">{esc(message)}</div></div>'
    )


def show_error(exc: TutorError) -> None:
    """Display a learner-safe error message (never raw exception text)."""
    if isinstance(exc, ConfigurationError):
        st.warning(exc.user_message, icon=":material/key:")
    else:
        st.error(exc.user_message, icon=":material/error:")
        if exc.retryable:
            st.caption("You can try again — your inputs have been kept.")


def call_safely(
    spinner_text: str, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
) -> R | None:
    """Run ``func`` with a spinner. Expected errors show a friendly message;
    unexpected ones are logged (redacted) and shown generically. Returns None on failure."""
    try:
        with st.spinner(spinner_text):
            return func(*args, **kwargs)
    except TutorError as exc:
        logger.info("Handled error: %s", type(exc).__name__)
        show_error(exc)
    except Exception:
        logger.exception("Unexpected error while running %s", getattr(func, "__name__", func))
        st.error(
            "An unexpected error occurred. Please try again. If it keeps happening, check the "
            "application logs.",
            icon=":material/error:",
        )
    return None


def ai_setup_notice() -> None:
    from ui.navigation import page_link  # local import avoids a cycle at module load

    st.info(
        "**Connect your AI tutor.** Add your OpenAI API key and choose a model in "
        "**Settings → AI setup**. Your saved vocabulary, flashcards and progress work "
        "without it.",
        icon=":material/key:",
    )
    page_link("settings", "Open AI setup →", icon=":material/settings:")
