"""
Sentinel Live Demo — Streamlit frontend for the DriftGuard / Sentinel API
===========================================================================
A click-through demo for investors and prospective customers, backed by
LIVE calls to your deployed HuggingFace Space — nothing here is mocked.
Every screenshot/GIF you'd want for the deck can be produced by walking
through this app against the real API.

Two halves, matching what the API actually offers:
  1. Full walkthrough  — score transactions, run drift detection, optimize
     a threshold, pull a compliance report, verify the tamper-evidence chain.
     Uses the built-in demo fraud model (or your real model, if the Space
     has one loaded from HF_REPO).
  2. Multi-tenant       — onboard a "customer" model_id with its own
     reference data, run an isolated drift check, see its own dashboard/
     alerts/compliance report. Demonstrates the isolation guarantee
     covered by test_multitenancy.py.

Run locally:
    pip install streamlit requests
    streamlit run streamlit_app.py

Deploy on Streamlit Community Cloud:
    Push this repo to GitHub, point share.streamlit.io at it, and set two
    secrets in the app's Settings -> Secrets:
        SENTINEL_API_BASE = "https://<your-space>.hf.space"
        SENTINEL_API_KEY  = "<the API_KEY you set in the HF Space secrets>"
    (Both can also be typed into the sidebar at runtime instead — secrets
    just save you re-typing the key every time you open the app.)
"""

from __future__ import annotations
import json
import time
from typing import Optional

import requests
import streamlit as st

st.set_page_config(
    page_title="Sentinel — Live Demo",
    page_icon="🛰️",
    layout="wide",
)

DEFAULT_BASE_URL = "https://syedascientist72-mlops-maci.hf.space"


# ─────────────────────────────────────────────────────────────
# CONNECTION / SESSION STATE
# ─────────────────────────────────────────────────────────────

def _secret_or_default(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)  # type: ignore[union-attr]
    except Exception:
        return default


if "base_url" not in st.session_state:
    st.session_state.base_url = _secret_or_default("SENTINEL_API_BASE", DEFAULT_BASE_URL)
if "api_key" not in st.session_state:
    st.session_state.api_key = _secret_or_default("SENTINEL_API_KEY", "")


def api(method: str, path: str, auth: bool = True, timeout: int = 30, **kwargs):
    """Thin wrapper around requests that returns (ok, status_code, json_or_text).
    Never raises — every caller renders success/failure inline instead of
    the app crashing mid-demo, which matters a lot when the audience is an
    investor watching over your shoulder."""
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
    """HF Spaces on the free tier sleep after inactivity — the first call
    after a sleep can take 30-60s while it boots. This gives clear feedback
    instead of the UI looking hung, and matches what the app's own
    lifespan startup does (restore DBs, reload registry, load model)."""
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
# SYNTHETIC DATA HELPERS (for demoing without needing real customer data)
# ─────────────────────────────────────────────────────────────

import random


def synth_transaction(shift: float = 0.0) -> dict:
    """One fake transaction matching the demo model's expected raw fields.
    `shift` moves the distribution — used to manufacture visible drift."""
    tx = {f"V{i}": random.gauss(0 + shift, 1.0) for i in range(1, 29)}
    tx["Amount"] = max(0.0, random.gauss(150 + shift * 50, 80))
    return tx


def synth_batch(n: int, shift: float = 0.0) -> list[dict]:
    return [synth_transaction(shift) for _ in range(n)]


def synth_scores(n: int, model_id: str = "demo") -> tuple[list[int], list[float]]:
    """Fake labels + probabilities for threshold optimization / reference
    registration, shaped like a realistic low-base-rate fraud problem."""
    labels = [1 if random.random() < 0.03 else 0 for _ in range(n)]
    probs = [
        min(1.0, max(0.0, random.gauss(0.8, 0.15))) if y == 1
        else min(1.0, max(0.0, random.gauss(0.2, 0.15)))
        for y in labels
    ]
    return labels, probs


# ─────────────────────────────────────────────────────────────
# SIDEBAR — connection config, shown on every page
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🛰️ Sentinel")
    st.caption("Live demo — every action below hits your real API.")

    st.session_state.base_url = st.text_input(
        "API base URL", value=st.session_state.base_url,
        help="Your HF Space URL, e.g. https://your-username-your-space.hf.space",
    )
    st.session_state.api_key = st.text_input(
        "API key (Bearer token)", value=st.session_state.api_key, type="password",
        help="The API_KEY secret set in your HF Space's Settings -> Variables & Secrets.",
    )

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
    st.caption("strataforge3.com")


def require_key():
    if not st.session_state.api_key:
        st.warning("Enter your API key in the sidebar to use protected endpoints.")
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
        "loaded in the Space (real model if `HF_REPO` has one, otherwise "
        "the built-in demo model)."
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
# PAGE: DRIFT DETECTION
# ─────────────────────────────────────────────────────────────

elif page == "Drift Detection":
    require_key()
    st.header("Drift Detection (PSI + KS-test)")
    st.write(
        "Set a reference baseline, then send production-like data that's "
        "deliberately shifted, and watch PSI cross the WARNING/CRITICAL "
        "thresholds in real time."
    )

    ref_size = st.slider("Reference (baseline) size", 100, 2000, 500)
    if st.button("Set reference data"):
        ref_data = synth_batch(ref_size, shift=0.0)
        labels = [1 if random.random() < 0.02 else 0 for _ in range(ref_size)]
        ok, status, body = api("POST", "/reference", json={"data": ref_data, "labels": labels})
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
        ok, status, body = api("POST", "/drift/report", json={"transactions": prod_data})
        if ok:
            level_color = {"OK": "🟢", "INFO": "🔵", "WARNING": "🟡", "CRITICAL": "🔴"}
            st.metric(
                "Alert level",
                f"{level_color.get(body['alert_level'], '⚪')} {body['alert_level']}",
                f"mean PSI = {body['mean_psi']}",
            )
            st.write(f"**Recommended action:** {body['recommended_action']}")
            if body["critical_features"]:
                st.error(f"Critical features: {', '.join(body['critical_features'])}")
            if body["warning_features"]:
                st.warning(f"Warning features: {', '.join(body['warning_features'])}")
            with st.expander("Per-feature PSI/KS detail"):
                st.json(body["per_feature"])
        else:
            st.error(f"Failed ({status}): {body}")


# ─────────────────────────────────────────────────────────────
# PAGE: THRESHOLD OPTIMIZATION
# ─────────────────────────────────────────────────────────────

elif page == "Threshold Optimization":
    require_key()
    st.header("Cost-Sensitive Threshold Optimization")
    st.latex(r"\theta^* = \arg\max_\theta \; \text{Recall}(\theta) - \lambda \cdot \text{FPR}(\theta)")

    n = st.slider("Number of labeled samples", 50, 2000, 500)
    lam = st.slider(
        "λ (false-positive cost weight)", 0.0, 1.0, 0.1, 0.05,
        help="Higher λ = more averse to false positives, at the cost of recall.",
    )
    if st.button("Optimize threshold", type="primary"):
        labels, probs = synth_scores(n)
        ok, status, body = api("POST", "/threshold/optimize", json={
            "labels": labels, "probabilities": probs, "lambda_cost": lam,
        })
        if ok:
            c1, c2, c3 = st.columns(3)
            c1.metric("Optimal threshold", body["optimal_threshold"])
            c2.metric("Recall at optimum", f"{body['recall_at_optimal']:.2%}")
            c3.metric("FPR at optimum", f"{body['fpr_at_optimal']:.2%}")
            st.info(body["message"])
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
        "hash-chained evidence log — not the in-memory alert list. This is "
        "what turns raw monitoring events into audit documentation."
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
        "— Sentinel monitors and documents them without hosting their model. "
        "This is the generalizable part of the product (fraud, credit, AML, "
        "insurance, churn, LLM-triage — any scored model)."
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
        "and alert logs side by side — demonstrating that one customer's "
        "data and alerts never bleed into another's. (Backed by "
        "`test_multitenancy.py` in the repo.)"
    )

    if st.button("Run isolation demo", type="primary"):
        with st.spinner("Registering tenant_alpha and tenant_beta..."):
            ok_a, _, body_a = api("POST", "/tenants/demo_tenant_alpha/reference", json={
                "data": synth_batch(200, shift=0.0),
                "labels": [1 if random.random() < 0.02 else 0 for _ in range(200)],
                "display_name": "Demo Tenant Alpha",
            })
            ok_b, _, body_b = api("POST", "/tenants/demo_tenant_beta/reference", json={
                "data": synth_batch(200, shift=0.0),
                "labels": [1 if random.random() < 0.02 else 0 for _ in range(200)],
                "display_name": "Demo Tenant Beta",
            })

        with st.spinner("Drifting alpha hard, leaving beta untouched..."):
            api("POST", "/tenants/demo_tenant_alpha/drift/report", json={
                "transactions": synth_batch(200, shift=3.0),  # big shift -> should alert
            })
            api("POST", "/tenants/demo_tenant_beta/drift/report", json={
                "transactions": synth_batch(200, shift=0.0),  # no shift -> should stay quiet
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
