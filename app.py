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
                   initial_sidebar_state="expanded")

# Strip Streamlit chrome so the page owns the canvas.
st.markdown(
    """
    <style>
      #MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden; height: 0;}
      .block-container {padding: 0 !important; max-width: 100% !important;}
      section[data-testid="stSidebar"] {min-width: 300px;}
      /* the page fills the viewport and scrolls inside its own frame */
      div[data-testid="stAppViewContainer"] > section.main {overflow: hidden;}
      iframe[title="st.iframe"], div[data-testid="stIFrame"] iframe {border: 0; width: 100% !important; height: 100vh !important; display: block;}
      div[data-testid="element-container"], div[data-testid="stIFrame"], div[data-testid="stVerticalBlock"] {gap: 0 !important;}
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
        ".wrap{max-width:none!important}body{padding-inline:24px!important}"
        "</style></head><body>" + page + "</body></html>"
    )
    return html, book, prerun


HTML, BOOK, PRERUN = load_page()
DL = BOOK["meta"]["devLabels"]
TRI_NAME = {"paid": "Paid losses", "incurred": "Reported losses"}

with st.sidebar:
    st.markdown("### LLM-AARS")
    st.caption("Triangle diagnostics with claim-note attribution. "
               f"{len(BOOK['claims'])} synthetic Commercial Auto claims, AY 2016–2025, valued 31 Dec 2025.")

    st.markdown("#### How to use the page")
    st.markdown(
        "1. Start with the **diagnostic feed** and the **diagonal test**.\n"
        "2. Click a flagged cell (or any factor in a triangle) to open it.\n"
        "3. Read the **signature table**, the **waterfall** and the **AI reading**.\n"
        "4. Review the **column selection**: unadjusted vs AARS-adjusted LDF.\n"
        "5. Record the cell and column decisions; the log is the sign-off record."
    )

    cell_keys = [k for k in PRERUN if not k.startswith("col:")]
    col_keys = [k for k in PRERUN if k.startswith("col:")]
    st.markdown("#### Stored AI readings")
    st.caption("Produced by Claude on 2026-10-01 and shipped with the page.")
    for k in cell_keys:
        tri, rest = k.split(":")
        ay, d = rest.split("-")
        d = int(d)
        st.write(f"• AY {ay} · {DL[d]}→{DL[d + 1]} mo · {TRI_NAME[tri]}")
    st.markdown("**Column memos**")
    for k in col_keys:
        _, tri, d = k.split(":")
        d = int(d)
        st.write(f"• {DL[d]}→{DL[d + 1]} mo · {TRI_NAME[tri]}")

    st.markdown("---")
    st.caption("All claims, notes and amounts are synthetic. The triangle set and the way it is read follow "
               "Friedland, Estimating Unpaid Claims Using Basic Techniques, chapter 6.")

components.html(HTML, height=1200, scrolling=True)
