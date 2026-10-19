"""Page registry so pages can link to each other without circular imports.

``app.py`` registers the ``st.Page`` objects on every run; page modules look
them up by key.
"""

from __future__ import annotations

import streamlit as st
from streamlit.navigation.page import StreamlitPage

_REGISTRY_KEY = "_jt_pages"


def register_pages(pages: dict[str, StreamlitPage]) -> None:
    st.session_state[_REGISTRY_KEY] = pages


def get_page(key: str) -> StreamlitPage:
    return st.session_state[_REGISTRY_KEY][key]


def page_link(key: str, label: str, icon: str | None = None) -> None:
    st.page_link(get_page(key), label=label, icon=icon)


def switch_to(key: str) -> None:
    st.switch_page(get_page(key))
