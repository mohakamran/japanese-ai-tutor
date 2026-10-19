"""Custom CSS for the app's own components.

Streamlit's theme (``.streamlit/config.toml``) handles base colours, fonts and
widgets. This stylesheet styles the ``jt-*`` classes rendered by
:mod:`ui.components`, plus keyed containers (``.st-key-*``), which Streamlit
documents as stable hooks for custom styling.
"""

from __future__ import annotations

import streamlit as st

# Seigaiha (青海波) wave pattern, drawn very faintly behind hero banners.
_SEIGAIHA = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='48' height='24' "
    "viewBox='0 0 48 24'><g fill='none' stroke='%23C8372D' stroke-opacity='0.10' "
    "stroke-width='1.2'><path d='M0 24a24 24 0 0 1 48 0'/><path d='M6 24a18 18 0 0 1 36 0'/>"
    "<path d='M12 24a12 12 0 0 1 24 0'/><path d='M18 24a6 6 0 0 1 12 0'/>"
    "<path d='M-24 12a24 24 0 0 1 48 0'/><path d='M24 12a24 24 0 0 1 48 0'/></g></svg>"
)

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@600;900&family=Noto+Sans+JP:wght@400;500;700&display=swap');

:root {
  --jt-red: #C8372D;
  --jt-red-deep: #A12A22;
  --jt-red-soft: #FBECEA;
  --jt-indigo: #2E4A7D;
  --jt-indigo-deep: #1F3358;
  --jt-indigo-soft: #ECF0F7;
  --jt-gold: #B8873B;
  --jt-gold-soft: #FBF3E4;
  --jt-green: #2F7A55;
  --jt-green-soft: #E8F4EC;
  --jt-ink: #1C1E26;
  --jt-muted: #5A606B;
  --jt-border: #E6DDD0;
  --jt-paper: #FBF8F3;
  --jt-white: #FFFFFF;
  --jt-shadow: 0 1px 2px rgba(28,30,38,.04), 0 6px 20px rgba(28,30,38,.06);
  --jt-shadow-hover: 0 2px 4px rgba(28,30,38,.06), 0 14px 32px rgba(28,30,38,.10);
  --jt-jp-font: "Noto Sans JP", "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", sans-serif;
  --jt-serif-jp: "Noto Serif JP", "Hiragino Mincho ProN", "Yu Mincho", serif;
}

/* ---------- layout polish ---------- */
.block-container { padding-top: 4rem; max-width: 1200px; }
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span { font-weight: 600; }

/* ---------- hero banner ---------- */
.jt-hero {
  position: relative; overflow: hidden; border-radius: 20px; margin: 0 0 1.5rem 0;
  padding: 1.8rem 2rem; background: var(--jt-white); border: 1px solid var(--jt-border);
  box-shadow: var(--jt-shadow);
}
.jt-hero::before {
  content: ""; position: absolute; inset: 0 0 0 45%;
  background-image: url("SEIGAIHA"); background-size: 48px 24px;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 45%);
          mask-image: linear-gradient(90deg, transparent, #000 45%);
}
.jt-hero-sun {
  position: absolute; right: 2.2rem; top: 50%; transform: translateY(-50%);
  width: 132px; height: 132px; border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #E2574C, var(--jt-red) 60%, var(--jt-red-deep));
  box-shadow: 0 10px 30px rgba(200,55,45,.25);
  display: flex; align-items: center; justify-content: center;
}
.jt-hero-sun span { font-family: var(--jt-serif-jp); font-weight: 900; color: #fff;
                    font-size: 3.2rem; line-height: 1; letter-spacing: -0.05em; }
.jt-hero-text { position: relative; max-width: 68%; }
.jt-kicker { display: inline-flex; align-items: center; gap: .45rem;
  font-family: var(--jt-jp-font); color: var(--jt-red); font-weight: 700;
  font-size: .82rem; letter-spacing: .14em; text-transform: uppercase; }
.jt-kicker::before { content: ""; width: 22px; height: 2px; background: var(--jt-red); border-radius: 2px; }
.jt-title { font-size: 2.15rem; font-weight: 800; color: var(--jt-ink); line-height: 1.15;
            margin: .35rem 0 0 0; letter-spacing: -0.02em; }
.jt-subtitle { color: var(--jt-muted); font-size: 1.03rem; margin-top: .45rem; line-height: 1.55; }

/* ---------- cards ---------- */
.jt-card {
  background: var(--jt-white); color: var(--jt-ink); border: 1px solid var(--jt-border);
  border-radius: 16px; padding: 1.1rem 1.3rem; margin-bottom: .85rem; box-shadow: var(--jt-shadow);
  transition: box-shadow .18s ease, transform .18s ease;
}
.jt-card:hover { box-shadow: var(--jt-shadow-hover); }
.jt-card.jt-accent { border-left: 5px solid var(--jt-red); }
.jt-card.jt-indigo { border-left: 5px solid var(--jt-indigo); }
.jt-card.jt-paper { background: var(--jt-paper); box-shadow: none; }
.jt-card-title { font-weight: 800; font-size: 1.2rem; color: var(--jt-ink); margin: .1rem 0 .2rem 0; }

/* ---------- Japanese text ---------- */
.jt-jp { font-family: var(--jt-jp-font); color: var(--jt-ink); font-size: 1.45rem; font-weight: 500;
         line-height: 1.6; overflow-wrap: anywhere; }
.jt-jp.jt-lg { font-size: 2.4rem; font-weight: 700; }
.jt-jp.jt-sm { font-size: 1.12rem; }
.jt-reading { font-family: var(--jt-jp-font); color: var(--jt-muted); font-size: .98rem; }
.jt-romaji { color: var(--jt-indigo); font-size: .9rem; font-style: italic; opacity: .9; }
.jt-en { color: var(--jt-ink); font-size: 1rem; margin-top: .3rem; }
.jt-label { text-transform: uppercase; letter-spacing: .1em; font-size: .7rem; font-weight: 800;
            color: var(--jt-muted); margin: .75rem 0 .2rem 0; }
.jt-text { color: var(--jt-ink); font-size: 1rem; line-height: 1.6; }
.jt-muted { color: var(--jt-muted); font-size: .92rem; line-height: 1.5; }

/* ---------- badges ---------- */
.jt-badge { display: inline-block; font-size: .74rem; font-weight: 700; border-radius: 999px;
            padding: .16rem .65rem; margin: 0 .35rem .4rem 0; border: 1px solid transparent; }
.jt-badge.ok   { color: #1F6644; background: var(--jt-green-soft); border-color: #CBE5D5; }
.jt-badge.warn { color: #7A4F00; background: var(--jt-gold-soft); border-color: #EFD9AE; }
.jt-badge.err  { color: var(--jt-red-deep); background: var(--jt-red-soft); border-color: #F2CBC7; }
.jt-badge.info { color: var(--jt-indigo-deep); background: var(--jt-indigo-soft); border-color: #D5DEEC; }
.jt-badge.ai   { color: var(--jt-muted); background: var(--jt-paper); border-color: var(--jt-border); }

/* ---------- quiz answer rows ---------- */
.jt-option { display: flex; justify-content: space-between; align-items: center; gap: .75rem;
             padding: .5rem .8rem; margin: .35rem 0; border-radius: 12px; border: 1px solid var(--jt-border);
             color: var(--jt-ink); font-family: var(--jt-jp-font); }
.jt-option .jt-badge { margin: 0; flex: none; }
.jt-option.ok  { background: var(--jt-green-soft); border-color: #BFDFCB; }
.jt-option.err { background: var(--jt-red-soft); border-color: #F0C4BF; }

/* ---------- stat tiles ---------- */
.jt-stat { background: var(--jt-white); border: 1px solid var(--jt-border); border-radius: 16px;
           padding: 1rem 1.15rem; box-shadow: var(--jt-shadow); height: 100%; position: relative;
           overflow: hidden; }
.jt-stat::after { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
                  background: var(--accent, var(--jt-red)); }
.jt-stat-top { display: flex; align-items: center; gap: .6rem; }
.jt-stat-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center;
                justify-content: center; font-family: var(--jt-serif-jp); font-weight: 900;
                font-size: 1.05rem; color: var(--accent, var(--jt-red));
                background: var(--accent-soft, var(--jt-red-soft)); }
.jt-stat-label { color: var(--jt-muted); font-size: .82rem; font-weight: 700; }
.jt-stat-value { font-size: 1.9rem; font-weight: 800; color: var(--jt-ink); margin-top: .45rem;
                 letter-spacing: -0.02em; line-height: 1.1; }
.jt-stat-foot { color: var(--jt-muted); font-size: .8rem; margin-top: .2rem; }

/* ---------- progress ring ---------- */
.jt-ring { display: flex; align-items: center; gap: 1rem; }
.jt-ring svg { flex: none; }

/* ---------- word of the day ---------- */
.jt-wotd { border-radius: 18px; padding: 1.3rem 1.4rem; color: #fff; position: relative; overflow: hidden;
           background: linear-gradient(135deg, var(--jt-indigo) 0%, var(--jt-indigo-deep) 100%);
           box-shadow: 0 10px 28px rgba(31,51,88,.28); margin-bottom: .85rem; }
.jt-wotd::after { content: "今日"; position: absolute; right: -8px; bottom: -28px;
                  font-family: var(--jt-serif-jp); font-weight: 900; font-size: 6.5rem;
                  color: rgba(255,255,255,.07); }
.jt-wotd .jt-label { color: rgba(255,255,255,.7); margin-top: 0; }
.jt-wotd .jt-jp, .jt-wotd .jt-en { color: #fff; }
.jt-wotd .jt-reading { color: rgba(255,255,255,.78); }
.jt-wotd .jt-romaji { color: #F6D9A8; }

/* ---------- empty state ---------- */
.jt-empty { text-align: center; border: 1.5px dashed #DCCFBD; border-radius: 18px;
            padding: 2.2rem 1.25rem; background: var(--jt-white); margin: .5rem 0 1rem 0; }
.jt-empty-icon { width: 74px; height: 74px; margin: 0 auto; border-radius: 50%;
                 display: flex; align-items: center; justify-content: center;
                 font-family: var(--jt-serif-jp); font-weight: 900; font-size: 2rem; color: #fff;
                 background: radial-gradient(circle at 35% 35%, #E2574C, var(--jt-red) 60%, var(--jt-red-deep)); }
.jt-empty-title { font-weight: 800; font-size: 1.15rem; color: var(--jt-ink); margin-top: .8rem; }
.jt-empty-text { color: var(--jt-muted); margin-top: .3rem; max-width: 520px; margin-left: auto; margin-right: auto; }

/* ---------- activity timeline ---------- */
.jt-timeline { border-left: 2px solid var(--jt-border); margin-left: .5rem; padding-left: 1rem; }
.jt-tl-item { position: relative; padding: .15rem 0 .75rem 0; }
.jt-tl-item::before { content: ""; position: absolute; left: -1.43rem; top: .45rem; width: 10px; height: 10px;
                      border-radius: 50%; background: var(--jt-white); border: 2px solid var(--jt-red); }
.jt-tl-when { color: var(--jt-muted); font-size: .78rem; }

/* ---------- clickable tiles (keyed containers with a page link) ---------- */
[class*="st-key-tile_"] { background: var(--jt-white); border: 1px solid var(--jt-border); border-radius: 16px;
                          padding: 1rem 1.1rem .6rem 1.1rem; box-shadow: var(--jt-shadow);
                          transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease; }
[class*="st-key-tile_"]:hover { transform: translateY(-3px); box-shadow: var(--jt-shadow-hover);
                                border-color: #D9C9B3; }
.jt-tile-kanji { font-family: var(--jt-serif-jp); font-weight: 900; font-size: 1.9rem; color: var(--jt-red); line-height: 1; }
.jt-tile-title { font-weight: 800; color: var(--jt-ink); margin-top: .45rem; }
.jt-tile-text { color: var(--jt-muted); font-size: .88rem; line-height: 1.45; min-height: 2.6em; }

/* ---------- sidebar user card ---------- */
.jt-user { display: flex; align-items: center; gap: .7rem; padding: .7rem .75rem; border-radius: 14px;
           background: var(--jt-paper); border: 1px solid var(--jt-border); }
.jt-avatar { width: 40px; height: 40px; border-radius: 50%; flex: none; display: flex; align-items: center;
             justify-content: center; color: #fff; font-weight: 800; font-size: .95rem;
             background: linear-gradient(135deg, var(--jt-red), var(--jt-red-deep)); }
.jt-user-name { font-weight: 800; color: var(--jt-ink); font-size: .95rem; line-height: 1.2; }
.jt-user-meta { color: var(--jt-muted); font-size: .78rem; }

/* ---------- landing / auth ---------- */
.jt-landing { position: relative; padding: .5rem 0 0 0; }
.jt-landing-badge { display: inline-flex; align-items: center; gap: .4rem; padding: .3rem .8rem;
                    border-radius: 999px; background: var(--jt-white); border: 1px solid var(--jt-border);
                    color: var(--jt-muted); font-size: .8rem; font-weight: 700; }
.jt-landing-badge b { color: var(--jt-red); }
.jt-landing h1 { font-size: 3rem; line-height: 1.08; font-weight: 800; letter-spacing: -0.035em;
                 color: var(--jt-ink); margin: 1rem 0 .8rem 0; }
.jt-landing h1 em { font-style: normal; color: var(--jt-red); }
.jt-landing p.lead { font-size: 1.12rem; color: var(--jt-muted); line-height: 1.6; max-width: 34rem; }
.jt-feature { display: flex; gap: .85rem; align-items: flex-start; margin: .9rem 0; }
.jt-feature-icon { flex: none; width: 42px; height: 42px; border-radius: 12px; display: flex;
                   align-items: center; justify-content: center; font-family: var(--jt-serif-jp);
                   font-weight: 900; font-size: 1.15rem; color: var(--jt-red); background: var(--jt-red-soft); }
.jt-feature b { color: var(--jt-ink); display: block; }
.jt-feature span { color: var(--jt-muted); font-size: .92rem; }
.jt-demo-card { margin-top: 1.4rem; max-width: 30rem; background: var(--jt-white); border: 1px solid var(--jt-border);
                border-radius: 18px; padding: 1.1rem 1.3rem; box-shadow: var(--jt-shadow-hover);
                transform: rotate(-1.2deg); }
.st-key-auth_card { background: var(--jt-white); border: 1px solid var(--jt-border); border-radius: 22px;
                    padding: 1.6rem 1.6rem 1rem 1.6rem; box-shadow: 0 20px 50px rgba(28,30,38,.10); }
.jt-auth-title { font-weight: 800; font-size: 1.5rem; color: var(--jt-ink); }
.jt-auth-sub { color: var(--jt-muted); font-size: .95rem; margin-bottom: .4rem; }
.jt-footnote { color: var(--jt-muted); font-size: .78rem; text-align: center; margin-top: 1.4rem; }

@media (max-width: 768px) {
  .jt-hero { padding: 1.3rem 1.2rem; }
  .jt-hero-sun { width: 76px; height: 76px; right: 1rem; top: 1.3rem; transform: none; }
  .jt-hero-sun span { font-size: 1.9rem; }
  .jt-hero-text { max-width: 100%; padding-right: 5.5rem; }
  .jt-title { font-size: 1.6rem; }
  .jt-jp { font-size: 1.25rem; }
  .jt-jp.jt-lg { font-size: 1.9rem; }
  .jt-landing { padding-top: 1.6rem; }
  .st-key-auth_card { margin-top: 1.4rem; padding: 1.2rem 1.1rem .6rem 1.1rem; }
  .jt-landing h1 { font-size: 2.2rem; }
  /* On phones, show the log-in card before the marketing copy. */
  .st-key-landing [data-testid="stHorizontalBlock"] { flex-direction: column-reverse; }
  .jt-demo-card { transform: none; }
}
""".replace("SEIGAIHA", _SEIGAIHA.replace("<", "%3C").replace(">", "%3E"))


def inject_styles() -> None:
    st.html(f"<style>{_CSS}</style>")
