# Sentinel Live Demo (Streamlit)

A click-through demo UI for investors/prospects, backed by **live calls**
to your deployed HuggingFace Space — nothing in this app is mocked.

## Run locally

```bash
pip install -r requirements-streamlit.txt
streamlit run streamlit_app.py
```

Then enter your Space's URL and API key in the sidebar (or see below to
pre-fill them via secrets).

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub (this file, `streamlit_app.py`, and
   `requirements-streamlit.txt` at minimum — the rest of the repo, i.e.
   `main.py`/`tenants.py`/`compliance.py`, doesn't need to be in the same
   repo as the Streamlit app, though it can be).
2. Go to [share.streamlit.io](https://share.streamlit.io), connect the repo,
   and set **Main file path** to `streamlit_app.py`.
3. In the app's **Settings → Secrets**, add:
   ```toml
   SENTINEL_API_BASE = "https://your-username-your-space.hf.space"
   SENTINEL_API_KEY  = "the-API_KEY-you-set-in-your-HF-Space-secrets"
   ```
   (Find your Space's exact URL on its HF page — it's the `https://...hf.space`
   link that appears once the Space is running.)

## What's in the demo

| Section | What it shows |
|---|---|
| Overview | Live `/health` + `/dashboard/summary` — public, no key needed |
| Score Transactions | `/predict`, `/predict/batch` against whatever model is loaded |
| Drift Detection | Set a reference baseline, inject a simulated shift, watch PSI/KS fire |
| Threshold Optimization | Cost-weighted recall/FPR tradeoff, live |
| Compliance Report | Article-mapped EU AI Act / DORA report + hash-chain verification |
| Multi-Tenant Onboarding | Register a new customer `model_id`, see the tenant list |
| Multi-Tenant Isolation Proof | Registers two tenants, drifts one hard, shows both dashboards side by side — the alerts don't cross over |

## A note on HF Spaces cold starts

Free-tier Spaces sleep after inactivity. The first request after a sleep
can take 30-60 seconds while it reboots (restoring the compliance DB,
tenant registry, and model). The sidebar's "Check connection" button
polls `/health` with retries and gives clear feedback instead of the UI
just looking frozen — worth clicking that first if you're about to demo
live and the Space has been idle.
