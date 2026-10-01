# LLM-AARS Triangle Diagnostics — Streamlit app

A reserving workbench that rolls a claim-level book into nine Friedland-style diagnostic
triangles, flags cells, matches each cell's cross-triangle pattern to a known cause, reads the
adjuster notes behind it, decomposes the development factor into named drivers, and proposes
the factor to carry. The actuary decides; the decision log is the sign-off record.

The page itself is the same single-file workbench used in the prototype, so the design is
unchanged. The AI readings (per-cell note classifications and memos, and per-column selection
memos) ship with the page in `data/prerun.json`; the app makes no network calls and needs no key.

## Run locally

    pip install -r requirements.txt
    streamlit run app.py

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. At share.streamlit.io choose the repo, branch and `app.py`.
3. Deploy. Nothing else to configure.

## Layout

    app.py                 Streamlit shell: serves the page
    assets/head.html       page markup and styles
    assets/script.html     page logic (triangles, signatures, waterfall, decision log)
    data/book.json         synthetic claim-level book (744 claims, AY 2016–2025, valued 31 Dec 2025)
    data/prerun.json       stored AI readings: flagged cells and column memos (Claude, 2026-10-01)
    generate_book.py       regenerates data/book.json with the seeded effects

## Replacing the synthetic book with real data

`book.json` is the only data contract. Produce the same shape from your claim extract
(claims with cumulative paid and case outstanding by development year, dated notes, and the
triangle roll-ups) and the whole page, including attribution, works unchanged. The driver
`events` on each claim are what the waterfall sums; on real data they come from the note
classifications rather than from the generator.

All claims, notes and amounts in the shipped book are synthetic.
