"""
Sentinel Live Demo — Streamlit frontend for the DriftGuard / Sentinel API
===========================================================================
StrataForge3-branded, share-link-safe: the API key is read from Streamlit
secrets and used SERVER-SIDE only. Anyone opening the deployed link never
sees the key, and it's never sent to their browser — the HTTP calls to
your API happen from Streamlit's own servers, not the visitor's machine.

SECURITY NOTE (read before sharing widely): this demo uses whatever key
you put in SENTINEL_API_KEY. That key can call every endpoint your API
exposes. Hiding it from the UI stops a casual visitor from *seeing* it,
but doesn't scope down what it can *do*. If you want a genuinely
lower-privilege key for public sharing (recommended before wide
distribution), that requires adding role/scope support to main.py's auth
— ask if you want that built. Until then, treat this link as "safe to
click through," not "safe against a determined, technical visitor."

ISOLATION NOTE: the "Drift Detection" and "Threshold Optimization" pages
operate on a dedicated tenant (`public_demo`, via the multi-tenant
/tenants/{model_id}/... endpoints) rather than the shared single-tenant
demo model. This means visitors playing with this public link cannot
corrupt the shared demo model's live threshold or reference data out
from under you (or each other) mid-demo. "Score Transactions" still uses
the single-tenant /predict endpoints, since there's no per-tenant scoring
endpoint (tenants bring their own precomputed scores) — this is lower
risk since it doesn't mutate threshold/reference state, only appends to
the shared alert/compliance log.

Run locally:
    pip install streamlit requests pillow
    streamlit run streamlit_app.py

Deploy on Streamlit Community Cloud:
    Push this file, requirements-streamlit.txt, and the assets/ folder
    (logo) to GitHub. Point share.streamlit.io at it. In the app's
    Settings -> Secrets, set:
        SENTINEL_API_BASE = "https://your-username-your-space.hf.space"
        SENTINEL_API_KEY  = "my-secret-api-key-1317"
    That's it — the deployed link needs no key entry from visitors.
"""

from __future__ import annotations
import random
import time
from pathlib import Path

import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────
# BRAND — approximate StrataForge3 palette (from strataforge3.com /
# the logo mark). Tweak hex values if you want a pixel-exact match —
# these were read off screenshots, not your actual CSS.
# ─────────────────────────────────────────────────────────────

NAVY_DARK   = "#141a3d"
NAVY_DARKER = "#0d1129"
ORANGE      = "#e8642c"
ORANGE_LT   = "#f0a35c"
LAVENDER    = "#b4aede"
WHITE       = "#f5f5fa"

LOGO_PATH = Path(__file__).parent / "assets" / "strataforge3-logo-mark.png"

st.set_page_config(
    page_title="StrataForge3 — Sentinel Live Demo",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🛰️",
    layout="wide",
)

st.markdown(f"""
<style>
    .stApp {{
        background-color: {NAVY_DARKER};
    }}
    section[data-testid="stSidebar"] {{
        background-color: {NAVY_DARK};
        border-right: 1px solid #2a2f5c;
    }}
    h1, h2, h3 {{
        color: {WHITE} !important;
        font-family: 'Inter', -apple-system, sans-serif;
    }}
    p, label, .stMarkdown {{
        color: {WHITE};
    }}
    .stButton > button[kind="primary"] {{
        background-color: {ORANGE};
        border-color: {ORANGE};
        color: white;
        font-weight: 600;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {ORANGE_LT};
        border-color: {ORANGE_LT};
    }}
    .stButton > button:not([kind="primary"]) {{
        background-color: transparent;
        border: 1px solid {LAVENDER};
        color: {LAVENDER};
    }}
    div[data-testid="stMetric"] {{
        background-color: {NAVY_DARK};
        border: 1px solid #2a2f5c;
        border-radius: 8px;
        padding: 12px;
    }}
    div[data-testid="stMetricLabel"] {{
        color: {LAVENDER} !important;
    }}
    .demo-caption {{
        color: {LAVENDER};
        font-size: 0.85rem;
    }}
    a {{ color: {ORANGE_LT} !important; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# CONNECTION — secrets only. No key input is ever rendered when
# secrets are configured, so a shared deployed link never asks a
# visitor for credentials and never puts one in their browser.
# ─────────────────────────────────────────────────────────────

def _secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)  # type: ignore[union-attr]
    except Exception:
        return default


_SECRET_BASE = _secret("SENTINEL_API_BASE")
_SECRET_KEY = _secret("SENTINEL_API_KEY")
_USING_SECRETS = bool(_SECRET_BASE and _SECRET_KEY)

if "base_url" not in st.session_state:
    st.session_state.base_url = _SECRET_BASE
if "api_key" not in st.session_state:
    st.session_state.api_key = _SECRET_KEY

DEMO_TENANT_ID = "public_demo"  # dedicated, isolated tenant for this shared demo


def api(method: str, path: str, auth: bool = True, timeout: int = 30, **kwargs):
    """Never raises — every caller renders success/failure inline."""
    url = st.session_state.base_url.rstrip("/") + path
    headers = kwargs.pop("headers", {})
    if auth and st.session_state.api_key:
        headers["Authorization"] = f"Bearer {st.session_state.api_key}"
    try:
        resp = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        return resp.ok, resp.status_code, body
    except requests.exceptions.RequestException as e:
        return False, None, str(e)


def wake_and_check() -> tuple[bool, str]:
    ok, status, body = api("GET", "/health", auth=False, timeout=5)
    if ok:
        return True, "awake"
    with st.spinner("Space is waking up (cold start can take up to a minute)…"):
        for _ in range(12):
            time.sleep(5)
            ok, status, body = api("GET", "/health", auth=False, timeout=10)
            if ok:
                return True, "woke up"
    return False, f"still unreachable after waiting (last status: {status})"


# ─────────────────────────────────────────────────────────────
# SYNTHETIC DATA HELPERS
# ─────────────────────────────────────────────────────────────

def synth_transaction(shift: float = 0.0) -> dict:
    tx = {f"V{i}": random.gauss(0 + shift, 1.0) for i in range(1, 29)}
    tx["Amount"] = max(0.0, random.gauss(150 + shift * 50, 80))
    return tx


def synth_batch(n: int, shift: float = 0.0) -> list[dict]:
    return [synth_transaction(shift) for _ in range(n)]


def synth_scores(n: int) -> tuple[list[int], list[float]]:
    labels = [1 if random.random() < 0.03 else 0 for _ in range(n)]
    probs = [
        min(1.0, max(0.0, random.gauss(0.8, 0.15))) if y == 1
        else min(1.0, max(0.0, random.gauss(0.2, 0.15)))
        for y in labels
    ]
    return labels, probs


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=64)
    st.markdown(f"<h2 style='color:{WHITE};margin-top:0;'>Sentinel</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p class='demo-caption'>Live demo — every action below hits your real API.</p>",
        unsafe_allow_html=True,
    )

    if _USING_SECRETS:
        st.markdown(
            "<p class='demo-caption'>🔒 Connected — credentials configured by the demo owner, "
            "never exposed to your browser.</p>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No secrets configured — enter connection details for local testing.")
        st.session_state.base_url = st.text_input("API base URL", value=st.session_state.base_url)
        st.session_state.api_key = st.text_input("API key (Bearer token)", value=st.session_state.api_key, type="password")

    if st.button("Check connection", use_container_width=True):
        awake, msg = wake_and_check()
        if awake:
            st.success(f"Connected ({msg}).")
        else:
            st.error(f"Could not reach the Space: {msg}")

    st.divider()
    page = st.radio(
        "Demo section",
        [
            "Overview",
            "Score Transactions",
            "Drift Detection",
            "Threshold Optimization",
            "Compliance Report",
            "Multi-Tenant Onboarding",
            "Multi-Tenant Isolation Proof",
        ],
    )
    st.divider()
    st.markdown("<p class='demo-caption'>strataforge3.com</p>", unsafe_allow_html=True)


def require_key():
    if not st.session_state.api_key:
        st.warning("No API key configured. If you're the demo owner, set SENTINEL_API_KEY in Secrets.")
        st.stop()


# ─────────────────────────────────────────────────────────────
# PAGE: OVERVIEW
# ─────────────────────────────────────────────────────────────

if page == "Overview":
    st.header("System Overview")
    st.write("Public endpoints — no API key needed for this page.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Refresh health", type="primary"):
            st.rerun()
        ok, status, body = api("GET", "/health", auth=False)
        if ok:
            st.success("API reachable")
            st.json(body)
        else:
            st.error("API unreachable — click 'Check connection' in the sidebar (Space may be asleep).")
            st.caption(f"Detail: {body}")

    with col2:
        ok, status, body = api("GET", "/dashboard/summary", auth=False)
        if ok:
            status_color = {"HEALTHY": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}
            st.metric(
                "System status",
                f"{status_color.get(body.get('system_status'), '⚪')} {body.get('system_status', '—')}",
            )
            st.metric("Current threshold", body.get("current_threshold", "—"))
            st.metric("Total alerts logged", body.get("total_alerts", "—"))
            with st.expander("Full dashboard payload"):
                st.json(body)
        else:
            st.info("Dashboard unavailable until the Space is awake.")


# ─────────────────────────────────────────────────────────────
# PAGE: SCORE TRANSACTIONS
# ─────────────────────────────────────────────────────────────

elif page == "Score Transactions":
    require_key()
    st.header("Score Transactions")
    st.write(
        "Calls `/predict` and `/predict/batch` against the model currently "
        "loaded in the Space. This is the one page that uses the shared "
        "single-tenant model rather than the isolated demo tenant — scoring "
        "doesn't mutate the threshold or reference data, so it's low-risk "
        "to share."
    )

    tab_single, tab_batch = st.tabs(["Single transaction", "Batch"])

    with tab_single:
        c1, c2, c3, c4 = st.columns(4)
        v1 = c1.slider("V1", -5.0, 5.0, -1.36, key="v1")
        v4 = c2.slider("V4", -5.0, 5.0, 0.45, key="v4")
        v14 = c3.slider("V14", -5.0, 5.0, -0.31, key="v14")
        amount = c4.number_input("Amount", 0.0, 10000.0, 150.0, key="amount")

        if st.button("Score this transaction", type="primary"):
            ok, status, body = api("POST", "/predict", json={
                "features": {"V1": v1, "V4": v4, "V14": v14, "Amount": amount}
            })
            if ok:
                decision = body["decision"]
                color = "🔴" if decision == "FRAUD" else "🟢"
                st.metric("Decision", f"{color} {decision}", f"p={body['fraud_probability']}")
                st.json(body)
            else:
                st.error(f"Request failed ({status}): {body}")

    with tab_batch:
        n = st.slider("Number of synthetic transactions", 5, 200, 50)
        if st.button("Generate & score batch", type="primary"):
            batch = synth_batch(n)
            ok, status, body = api("POST", "/predict/batch", json={"transactions": batch})
            if ok:
                m1, m2, m3 = st.columns(3)
                m1.metric("Scored", body["count"])
                m2.metric("Flagged fraud", body["fraud_count"])
                m3.metric("Fraud rate", f"{body['fraud_rate']:.2%}")
                st.dataframe(body["results"], use_container_width=True)
            else:
                st.error(f"Request failed ({status}): {body}")


# ─────────────────────────────────────────────────────────────
# PAGE: DRIFT DETECTION — now on the isolated public_demo tenant
# ─────────────────────────────────────────────────────────────

elif page == "Drift Detection":
    require_key()
    st.header("Drift Detection (PSI + KS-test)")
    st.caption(f"Running against isolated tenant `{DEMO_TENANT_ID}` — cannot affect the shared demo model or any other tenant.")
    st.write(
        "Set a reference baseline, then send production-like data that's "
        "deliberately shifted, and watch PSI cross the WARNING/CRITICAL "
        "thresholds in real time."
    )

    ref_size = st.slider("Reference (baseline) size", 100, 2000, 500)
    if st.button("Set reference data"):
        ref_data = synth_batch(ref_size, shift=0.0)
        labels = [1 if random.random() < 0.02 else 0 for _ in range(ref_size)]
        ok, status, body = api("POST", f"/tenants/{DEMO_TENANT_ID}/reference", json={
            "data": ref_data, "labels": labels, "display_name": "Public Demo (shared visitors)",
        })
        if ok:
            st.success(f"Reference set: {body['rows']} rows, {len(body['features'])} features.")
        else:
            st.error(f"Failed ({status}): {body}")

    st.divider()
    shift = st.slider(
        "Distribution shift to simulate", 0.0, 3.0, 0.0, 0.1,
        help="0 = same distribution as reference (expect OK). Higher = more drift.",
    )
    prod_size = st.slider("Production batch size", 50, 1000, 300)
    if st.button("Run drift report", type="primary"):
        prod_data = synth_batch(prod_size, shift=shift)
        ok, status, body = api("POST", f"/tenants/{DEMO_TENANT_ID}/drift/report", json={"transactions": prod_data})
        if ok:
            level_color = {"OK": "🟢", "INFO": "🔵", "WARNING": "🟡", "CRITICAL": "🔴"}
            st.metric(
                "Alert level",
                f"{level_color.get(body['alert_level'], '⚪')} {body['alert_level']}",
                f"mean PSI = {body['mean_psi']}",
            )
            if body["critical_features"]:
                st.error(f"Critical features: {', '.join(body['critical_features'])}")
            if body["warning_features"]:
                st.warning(f"Warning features: {', '.join(body['warning_features'])}")
            with st.expander("Per-feature PSI/KS detail"):
                st.json(body["features"])
        else:
            st.error(f"Failed ({status}): {body} — if this is a 404, click 'Set reference data' above first.")


# ─────────────────────────────────────────────────────────────
# PAGE: THRESHOLD OPTIMIZATION — also on the isolated demo tenant
# ─────────────────────────────────────────────────────────────

elif page == "Threshold Optimization":
    require_key()
    st.header("Cost-Sensitive Threshold Optimization")
    st.caption(f"Running against isolated tenant `{DEMO_TENANT_ID}` — does not touch the shared demo model's live threshold.")
    st.latex(r"\theta^* = \arg\max_\theta \; \text{Recall}(\theta) - \lambda \cdot \text{FPR}(\theta)")

    n = st.slider("Number of labeled samples", 50, 2000, 500)
    lam = st.slider(
        "λ (false-positive cost weight)", 0.0, 1.0, 0.1, 0.05,
        help="Higher λ = more averse to false positives, at the cost of recall.",
    )
    if st.button("Optimize threshold", type="primary"):
        labels, probs = synth_scores(n)
        ok, status, body = api("POST", f"/tenants/{DEMO_TENANT_ID}/threshold/optimize", json={
            "labels": labels, "probabilities": probs, "lambda_cost": lam,
        })
        if ok:
            c1, c2, c3 = st.columns(3)
            c1.metric("Optimal threshold", body["optimal_threshold"])
            c2.metric("Recall at optimum", f"{body['recall_at_optimal']:.2%}")
            c3.metric("FPR at optimum", f"{body['fpr_at_optimal']:.2%}")
        else:
            st.error(f"Failed ({status}): {body}")


# ─────────────────────────────────────────────────────────────
# PAGE: COMPLIANCE REPORT
# ─────────────────────────────────────────────────────────────

elif page == "Compliance Report":
    require_key()
    st.header("Regulatory Evidence & Compliance Report")
    st.write(
        "Pulls a structured, article-mapped report from the persistent, "
        "hash-chained evidence log — not the in-memory alert list."
    )

    framework = st.selectbox("Framework", ["eu_ai_act", "dora"])
    model_id = st.text_input("Model ID (leave blank for the default demo model)", "")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Generate report", type="primary"):
            params = {"model_id": model_id} if model_id else {}
            ok, status, body = api("GET", f"/compliance/report/{framework}", params=params)
            if ok:
                st.metric("Total evidence records", body["total_evidence_records"])
                chain_ok = body["integrity"]["valid"]
                st.metric("Chain integrity", "✅ Valid" if chain_ok else "❌ BROKEN")
                for art_id, section in body["sections"].items():
                    with st.expander(f"{section['title']} — {section['evidence_count']} record(s)"):
                        for ev in section["evidence"]:
                            st.write(f"**{ev['timestamp']}** — {ev['summary']}")
                            st.caption(f"hash: `{ev['record_hash']}`")
            else:
                st.error(f"Failed ({status}): {body}")

    with c2:
        if st.button("Verify tamper-evidence chain"):
            ok, status, body = api("GET", "/compliance/verify")
            if ok:
                if body.get("valid"):
                    st.success(f"Chain valid — {body['records_verified']} records verified.")
                else:
                    st.error(f"CHAIN BROKEN: {body}")
            else:
                st.error(f"Failed ({status}): {body}")


# ─────────────────────────────────────────────────────────────
# PAGE: MULTI-TENANT ONBOARDING
# ─────────────────────────────────────────────────────────────

elif page == "Multi-Tenant Onboarding":
    require_key()
    st.header("Onboard a Customer Model")
    st.write(
        "A customer brings their OWN already-computed scores/labels/features "
        "— Sentinel monitors and documents them without hosting their model."
    )

    with st.form("onboard_form"):
        model_id = st.text_input("model_id (unique identifier)", "acme_credit_risk_v2")
        display_name = st.text_input("Display name", "Acme Credit Risk Model v2")
        n = st.slider("Synthetic reference rows to register", 50, 2000, 300)
        submitted = st.form_submit_button("Register reference data", type="primary")

    if submitted:
        data = synth_batch(n)
        labels = [1 if random.random() < 0.02 else 0 for _ in range(n)]
        ok, status, body = api("POST", f"/tenants/{model_id}/reference", json={
            "data": data, "labels": labels, "display_name": display_name,
        })
        if ok:
            st.success(f"Registered `{model_id}` — {body['rows']} rows, {len(body['features'])} features.")
        else:
            st.error(f"Failed ({status}): {body}")

    st.divider()
    st.subheader("All tenants currently on this Space")
    if st.button("Refresh tenant list"):
        st.rerun()
    ok, status, body = api("GET", "/tenants")
    if ok:
        if body["tenants"]:
            st.dataframe(body["tenants"], use_container_width=True)
        else:
            st.info("No tenants registered yet — use the form above.")
    else:
        st.error(f"Failed ({status}): {body}")


# ─────────────────────────────────────────────────────────────
# PAGE: MULTI-TENANT ISOLATION PROOF
# ─────────────────────────────────────────────────────────────

elif page == "Multi-Tenant Isolation Proof":
    require_key()
    st.header("Isolation Proof: Two Tenants, Side by Side")
    st.write(
        "Registers two independent tenants with very different reference "
        "distributions, drifts one of them hard, and shows their dashboards "
        "and alert logs side by side. (Backed by `test_multitenancy.py` in the repo.)"
    )

    if st.button("Run isolation demo", type="primary"):
        with st.spinner("Registering tenant_alpha and tenant_beta..."):
            api("POST", "/tenants/demo_tenant_alpha/reference", json={
                "data": synth_batch(200, shift=0.0),
                "labels": [1 if random.random() < 0.02 else 0 for _ in range(200)],
                "display_name": "Demo Tenant Alpha",
            })
            api("POST", "/tenants/demo_tenant_beta/reference", json={
                "data": synth_batch(200, shift=0.0),
                "labels": [1 if random.random() < 0.02 else 0 for _ in range(200)],
                "display_name": "Demo Tenant Beta",
            })

        with st.spinner("Drifting alpha hard, leaving beta untouched..."):
            api("POST", "/tenants/demo_tenant_alpha/drift/report", json={
                "transactions": synth_batch(200, shift=3.0),
            })
            api("POST", "/tenants/demo_tenant_beta/drift/report", json={
                "transactions": synth_batch(200, shift=0.0),
            })

        col1, col2 = st.columns(2)
        for col, model_id, label in [(col1, "demo_tenant_alpha", "Alpha (drifted)"),
                                      (col2, "demo_tenant_beta", "Beta (untouched)")]:
            with col:
                st.subheader(label)
                ok, status, dash = api("GET", f"/tenants/{model_id}/dashboard")
                if ok:
                    status_color = {"HEALTHY": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}
                    st.metric("Status", f"{status_color.get(dash['system_status'], '⚪')} {dash['system_status']}")
                    st.metric("Total alerts", dash["total_alerts"])
                ok, status, alerts = api("GET", f"/tenants/{model_id}/alerts")
                if ok:
                    st.caption(f"{alerts['total']} alert(s) logged for this tenant")
                    if alerts["alerts"]:
                        st.dataframe(alerts["alerts"], use_container_width=True)

        st.success(
            "If isolation is working: Alpha shows alerts, Beta shows none — "
            "even though both were registered and drift-checked in the same "
            "run, seconds apart."
        )
