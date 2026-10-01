"""LLM-AARS Triangle Diagnostics — Streamlit shell.

Serves the diagnostics workbench page unchanged (same design, same logic), with the
AI readings that ship in data/prerun.json. No API key, no network calls.

Run locally:   streamlit run app.py
Deploy:        push this folder to GitHub and point Streamlit Community Cloud at app.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent
ASSETS, DATA = ROOT / "assets", ROOT / "data"

st.set_page_config(page_title="LLM-AARS Triangle Diagnostics", page_icon="📐", layout="wide",
                   initial_sidebar_state="collapsed")

# No sidebar, no Streamlit chrome: the page owns the whole window and scrolls as itself.
st.markdown(
    """
    <style>
      #MainMenu, footer, header[data-testid="stHeader"] {display: none !important;}
      section[data-testid="stSidebar"], div[data-testid="collapsedControl"] {display: none !important;}
      div[data-testid="stAppViewContainer"], section[data-testid="stMain"], section.main {margin: 0 !important; padding: 0 !important; width: 100vw !important; max-width: 100vw !important; left: 0 !important;}
      .block-container {padding: 0 !important; margin: 0 !important; max-width: 100vw !important; width: 100vw !important;}
      div[data-testid="stVerticalBlock"], div[data-testid="element-container"], div[data-testid="stIFrame"] {gap: 0 !important; width: 100% !important;}
      iframe {border: 0; display: block; width: 100vw !important; height: 100vh !important;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_page() -> tuple[str, dict, dict]:
    head = (ASSETS / "head.html").read_text(encoding="utf-8")
    script = (ASSETS / "script.html").read_text(encoding="utf-8")
    book = json.loads((DATA / "book.json").read_text(encoding="utf-8"))
    prerun = json.loads((DATA / "prerun.json").read_text(encoding="utf-8"))
    book_json = json.dumps(book).replace("</", "<\\/")
    pre_json = json.dumps(prerun).replace("</", "<\\/")
    page = head + script.replace("__BOOK__", book_json).replace("__PRERUN__", pre_json)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<style>:root{color-scheme:light}body{margin:0;font:14px system-ui,sans-serif;background:#f7f6f3}"
        "img{max-width:100%}[hidden]{display:none!important}"
        # inside Streamlit the page owns the whole main area: use the full width with even gutters
        ".wrap{max-width:1680px!important}body{padding-inline:24px!important}"
        "</style></head><body>" + page + "</body></html>"
    )
    return html, book, prerun


HTML, BOOK, PRERUN = load_page()

components.html(HTML, height=1400, scrolling=True)
