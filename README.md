# LLM-AARS Triangle Diagnostics — Streamlit app

A reserving workbench that rolls a claim-level book into nine Friedland-style diagnostic
triangles, flags cells, matches each cell's cross-triangle pattern to a known cause, reads the
adjuster notes behind it, decomposes the development factor into named drivers, and proposes
the factor to carry. The actuary decides; the decision log is the sign-off record.

The page itself is the same single-file workbench used in the prototype, so the design is
unchanged. Streamlit adds a sidebar that calls the Claude API with your key to read any cell's
notes live and injects the result into the page as a stored reading.

## Run locally

    pip install -r requirements.txt
    streamlit run app.py

Optional: copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add your key,
or paste a key into the sidebar at runtime.

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. At share.streamlit.io choose the repo, branch and `app.py`.
3. In App settings → Secrets, add `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`).
4. Deploy. The page works without a key; the key only enables live readings.

## Layout

    app.py                 Streamlit shell: serves the page, runs live readings
    assets/head.html       page markup and styles
    assets/script.html     page logic (triangles, signatures, waterfall, decision log)
    data/book.json         synthetic claim-level book (744 claims, AY 2016–2025, valued 31 Dec 2025)
    data/prerun.json       stored AI readings for the flagged cells (Claude, 2026-10-01)
    generate_book.py       regenerates data/book.json with the seeded effects

## Replacing the synthetic book with real data

`book.json` is the only data contract. Produce the same shape from your claim extract
(claims with cumulative paid and case outstanding by development year, dated notes, and the
triangle roll-ups) and the whole page, including attribution, works unchanged. The driver
`events` on each claim are what the waterfall sums; on real data they come from the note
classifications rather than from the generator.

All claims, notes and amounts in the shipped book are synthetic.
