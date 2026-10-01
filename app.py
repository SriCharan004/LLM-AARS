"""LLM-AARS Triangle Diagnostics — Streamlit shell.

Serves the diagnostics workbench page unchanged (same design, same logic) and adds
what the page cannot do on its own outside Claude: a live reading of a cell's
adjuster notes through the Claude API, injected into the page as a stored reading.

Run locally:   streamlit run app.py
Deploy:        push this folder to GitHub and point Streamlit Community Cloud at app.py;
               put ANTHROPIC_API_KEY in the app's Secrets (or leave it out and let the
               viewer paste a key in the sidebar).
"""
from __future__ import annotations

import json
import os
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
      .block-container {padding: 0 0 0 0 !important; max-width: 100% !important;}
      section[data-testid="stSidebar"] {min-width: 330px;}
      iframe {border: 0;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_assets():
    head = (ASSETS / "head.html").read_text(encoding="utf-8")
    script = (ASSETS / "script.html").read_text(encoding="utf-8")
    book = json.loads((DATA / "book.json").read_text(encoding="utf-8"))
    prerun = json.loads((DATA / "prerun.json").read_text(encoding="utf-8"))
    return head, script, book, prerun


HEAD, SCRIPT, BOOK, PRERUN = load_assets()
AYS: list[int] = BOOK["meta"]["ays"]
DL: list[str] = BOOK["meta"]["devLabels"]
VAL = 2025

if "readings" not in st.session_state:
    st.session_state.readings = {}  # key -> reading dict, same shape as prerun.json

# ---------------------------------------------------------------- cell helpers
def factor(tri: str, i: int, d: int):
    r = BOOK["triangles"][tri][i]
    if d + 1 >= len(r) or r[d + 1] is None or not r[d]:
        return None
    return r[d + 1] / r[d]


def baseline(tri: str, i: int, d: int):
    n = m = 0.0
    for j, r in enumerate(BOOK["triangles"][tri]):
        if j == i or d + 1 >= len(r) or r[d + 1] is None or not r[d]:
            continue
        n += r[d + 1]
        m += r[d]
    return n / m if m else None


def cell_notes(tri: str, ay: int, d: int):
    key = "paid" if tri == "paid" else "incurred"
    rows = []
    for c in BOOK["claims"]:
        if c["ay"] != ay:
            continue
        paid, case = c["paid"], c["case"]
        if key == "paid":
            inc = paid[d + 1] - paid[d]
        else:
            inc = (paid[d + 1] + case[d + 1]) - (paid[d] + case[d])
        for n in c["notes"]:
            if n["dev"] == d + 1:
                rows.append({"id": c["id"], "movement": round(inc), "note": n["text"]})
    return rows


def all_cells():
    """Every (tri, ay, d) cell that has development, latest diagonal first."""
    out = []
    for tri in ("paid", "incurred"):
        for i, ay in enumerate(AYS):
            nd = VAL - ay + 1
            for d in range(nd - 1):
                if factor(tri, i, d) is not None:
                    out.append((tri, ay, d))
    out.sort(key=lambda t: (-(t[1] + t[2]), t[0] != "paid", -t[1]))
    return out


TRI_NAME = {"paid": "Paid losses", "incurred": "Reported losses"}


def label(tri, ay, d):
    return f"AY {ay} · {DL[d]}→{DL[d + 1]} mo · {TRI_NAME[tri]}"


def build_prompt(tri, ay, d):
    i = AYS.index(ay)
    f, b = factor(tri, i, d), baseline(tri, i, d)
    notes = cell_notes(tri, ay, d)[:60]
    return f"""You are a P&C reserving actuary's assistant. Below are adjuster notes written during one development period of a loss triangle cell. Classify each note to exactly one driver, then write a short reserving memo.

Cell: accident year {ay}, development {DL[d]} to {DL[d + 1]} months, {TRI_NAME[tri]} triangle, Commercial Auto Liability.
Observed age-to-age factor {f:.3f}; volume-weighted norm for this column across other accident years {b:.3f}.

Driver codes:
- "inflation": medical, repair, wage or settlement cost levels rising; demands anchored to recent verdicts; fee schedules above those priced. Recurring and systemic.
- "large_loss": a single outsize verdict or catastrophic loss paid at or near limits. One-off.
- "recovery": subrogation, salvage or other one-time credit reducing paid loss. One-off.
- "speedup": settlement made earlier than the historical pattern (fast-track, early-resolution programme) with no change to the amount. Timing only.
- "strengthening": case reserve raised because of a reserve adequacy review or new reserving guideline, with no new information on the claim. Change of basis, not of expected cost.
- "routine": ordinary claim handling with no cost-level signal.

Notes (JSON): {json.dumps(notes)}

Reply with only a JSON object of this shape:
{{"notes":[{{"id":"CA-...","driver":"inflation|large_loss|recovery|speedup|strengthening|routine","why":"<=12 words"}}],
 "systemic": true|false,
 "treatment": "accept observed|strip one-offs|adjust pattern|restate case reserves|investigate",
 "suggested_ldf": <number>,
 "memo": "<=140 words: what is driving the factor, what is recurring versus one-off, what factor to carry and why. Plain sentences, no bullet points."}}
Use one entry per note (same id may repeat). Keep "why" short."""


def read_with_claude(tri, ay, d, api_key: str, model: str):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[{"role": "user", "content": build_prompt(tri, ay, d)}],
    )
    text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start : end + 1])
    by_id = {}
    for n in data.get("notes", []):
        if not n or "id" not in n:
            continue
        drv = str(n.get("driver", "routine"))
        if n["id"] not in by_id or (by_id[n["id"]]["driver"] == "routine" and drv != "routine"):
            by_id[n["id"]] = {"driver": drv, "why": str(n.get("why", ""))}
    return {
        "byId": by_id,
        "memo": str(data.get("memo", "")),
        "systemic": data.get("systemic"),
        "treatment": data.get("treatment"),
        "suggested_ldf": data.get("suggested_ldf"),
        "pre": True,
        "ranAt": f"live · {model}",
    }


def secret(name: str, default: str = "") -> str:
    """Read a Streamlit secret without failing when no secrets file exists."""
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### LLM-AARS")
    st.caption("Triangle diagnostics with claim-note attribution. Synthetic Commercial Auto book, valued 31 Dec 2025.")

    st.markdown("#### Read a cell's notes with Claude")
    cells = all_cells()
    choice = st.selectbox("Cell", cells, format_func=lambda t: label(*t), index=0,
                          help="Cells are listed latest calendar year first. Pre-run readings already exist for the flagged cells.")
    key_default = os.environ.get("ANTHROPIC_API_KEY") or secret("ANTHROPIC_API_KEY", "")
    api_key = st.text_input("Anthropic API key", value=key_default, type="password",
                            help="Stored only in this session. For a deployment, put ANTHROPIC_API_KEY in Secrets instead.")
    model = st.text_input("Model", value=secret("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
    tri, ay, d = choice
    n_notes = len(cell_notes(tri, ay, d))
    st.caption(f"{n_notes} notes dated to this period.")
    if st.button("Read notes", type="primary", disabled=not api_key or n_notes == 0, use_container_width=True):
        with st.spinner("Claude is reading the notes…"):
            try:
                st.session_state.readings[f"{tri}:{ay}-{d}"] = read_with_claude(tri, ay, d, api_key, model)
                st.success("Reading stored. It now shows on the page for that cell.")
            except Exception as exc:  # surface the real error; nothing else to do here
                st.error(f"Reading failed: {exc}")

    live_keys = list(st.session_state.readings)
    if live_keys:
        st.markdown("#### Live readings this session")
        for k in live_keys:
            t, rest = k.split(":")
            a, dd = rest.split("-")
            st.write("• " + label(t, int(a), int(dd)))
        st.download_button("Download readings (JSON)", json.dumps(st.session_state.readings, indent=2),
                           file_name="readings.json", mime="application/json", use_container_width=True)
        if st.button("Clear live readings", use_container_width=True):
            st.session_state.readings = {}
            st.rerun()

    st.markdown("---")
    st.caption("Pre-run readings were produced by Claude on 2026-10-01 and ship with the page. "
               "A live reading replaces the stored one for that cell in this session only.")

# ---------------------------------------------------------------- page
readings = {**PRERUN, **st.session_state.readings}
book_json = json.dumps(BOOK).replace("</", "<\\/")
pre_json = json.dumps(readings).replace("</", "<\\/")
page = HEAD + SCRIPT.replace("__BOOK__", book_json).replace("__PRERUN__", pre_json)
html = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<style>:root{color-scheme:light}body{margin:0;font:14px system-ui,sans-serif;background:#f7f6f3}"
    "img{max-width:100%}[hidden]{display:none!important}</style></head><body>" + page + "</body></html>"
)
components.html(html, height=3600, scrolling=True)
