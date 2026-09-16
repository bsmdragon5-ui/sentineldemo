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

1. Push this repo to GitHub — `streamlit_app.py`, `requirements-streamlit.txt`,
   and the `assets/` folder (the StrataForge3 logo) at minimum.
2. Go to [share.streamlit.io](https://share.streamlit.io), connect the repo,
   and set **Main file path** to `streamlit_app.py`.
3. In the app's **Settings → Secrets**, add:
   ```toml
   SENTINEL_API_BASE = "https://your-username-your-space.hf.space"
   SENTINEL_API_KEY  = "the-API_KEY-you-set-in-your-HF-Space-secrets"
   ```
   (Find your Space's exact URL on its HF page — it's the `https://...hf.space`
   link that appears once the Space is running.)

## Sharing the link safely

**The API key never reaches the visitor's browser.** Once secrets are
configured, the app doesn't render an API key input field at all —
anyone who opens your deployed link can use the demo, but the key itself
lives only in Streamlit Cloud's server-side secrets store. The HTTP
calls to your API happen from Streamlit's servers, not the visitor's
machine, so there's nothing to find even in browser dev tools.

**What this does NOT do: scope down what the key can do.** The key you
put in `SENTINEL_API_KEY` is a full-access admin key — same one your
Space's own `API_KEY` secret uses. Hiding it from the UI stops a casual
visitor from seeing it; it doesn't stop a determined, technical visitor
from doing anything your API allows, since the app itself will happily
forward requests. Before sharing this link widely (versus a handful of
known investors), consider:
- Minting a **separate key** just for this demo (so if it's ever
  compromised, your production key isn't), and
- Adding proper role/scope support to `main.py`'s auth if you want a
  genuinely read-only or rate-limited public demo key — this isn't
  built yet and would need real backend changes, not just a Streamlit
  tweak.

**Isolation:** the "Drift Detection" and "Threshold Optimization" pages
run against a dedicated `public_demo` tenant via the multi-tenant API,
not the shared single-tenant fraud model — so visitors playing with the
public link can't change the live demo model's threshold or reference
data out from under you mid-pitch. "Score Transactions" still uses the
shared model (no per-tenant scoring endpoint exists), but scoring alone
doesn't mutate the threshold, so the blast radius there is much smaller.

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
