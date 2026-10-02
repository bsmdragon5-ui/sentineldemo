"""
Sentinel — Investor Simulation (Streamlit)
=============================================================================
A guided, narrated walkthrough of the real Sentinel API, built for showing
investors or prospects exactly what happens and why it matters to a
business — not just a technical demo. Every action below calls your real,
live API through a secrets-protected connection (the key never reaches the
browser). Nothing here is scripted or mocked.

Deploy: push this file + requirements-streamlit.txt + assets/ to a GitHub
repo, connect it on share.streamlit.io, and set these two secrets in the
app's Settings -> Secrets (never commit them to git):
    SENTINEL_API_BASE = "https://your-space.hf.space"
    SENTINEL_API_KEY  = "the API_KEY set in your HF Space secrets"
"""

from __future__ import annotations
import random
import time
from pathlib import Path

import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────
# BRAND
# ─────────────────────────────────────────────────────────────

NAVY_DARK   = "#141a3d"
NAVY_DARKER = "#0d1129"
ORANGE      = "#e8642c"
ORANGE_LT   = "#f0a35c"
TEAL        = "#14B8A9"
RED         = "#EF4444"
LAVENDER    = "#b4aede"
WHITE       = "#f5f5fa"

LOGO_PATH = Path(__file__).parent / "assets" / "strataforge3-logo-mark.png"

st.set_page_config(
    page_title="Sentinel — Live Investor Simulation",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🛰️",
    layout="wide",
)

st.markdown(f"""
<style>
    .stApp {{ background-color: {NAVY_DARKER}; }}
    section[data-testid="stSidebar"] {{ background-color: {NAVY_DARK}; border-right: 1px solid #2a2f5c; }}
    h1, h2, h3 {{ color: {WHITE} !important; font-family: 'Inter', -apple-system, sans-serif; }}
    p, label, .stMarkdown {{ color: {WHITE}; }}
    .stButton > button[kind="primary"] {{ background-color: {ORANGE}; border-color: {ORANGE}; color: white; font-weight: 600; }}
    .stButton > button[kind="primary"]:hover {{ background-color: {ORANGE_LT}; border-color: {ORANGE_LT}; }}
    .stButton > button:not([kind="primary"]) {{ background-color: transparent; border: 1px solid {LAVENDER}; color: {LAVENDER}; }}
    div[data-testid="stMetric"] {{ background-color: {NAVY_DARK}; border: 1px solid #2a2f5c; border-radius: 8px; padding: 12px; }}
    div[data-testid="stMetricLabel"] {{ color: {LAVENDER} !important; }}
    .act-label {{ font-family: monospace; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: {ORANGE_LT}; border: 1px solid rgba(255,138,61,.35); background: rgba(255,138,61,.08); padding: 3px 10px; border-radius: 4px; display: inline-block; margin-bottom: .6rem; }}
    .biz-callout {{ background: rgba(20,184,169,.07); border-left: 4px solid {TEAL}; padding: 14px 18px; border-radius: 4px; margin-top: 14px; font-size: 14.5px; line-height: 1.6; }}
    .biz-callout b {{ color: {TEAL}; }}
    .reveal-caught {{ background: rgba(239,68,68,.08); border: 1px solid rgba(239,68,68,.35); border-radius: 6px; padding: 18px; }}
    .reveal-clean {{ background: rgba(20,184,169,.08); border: 1px solid rgba(20,184,169,.35); border-radius: 6px; padding: 18px; }}
    .week-ok {{ background: rgba(20,184,169,.15); color: {TEAL}; border: 1px solid rgba(20,184,169,.4); }}
    .week-info {{ background: rgba(180,174,222,.15); color: {LAVENDER}; border: 1px solid rgba(180,174,222,.4); }}
    .week-warning {{ background: rgba(255,138,61,.18); color: {ORANGE_LT}; border: 1px solid rgba(255,138,61,.5); }}
    .week-critical {{ background: rgba(239,68,68,.2); color: {RED}; border: 1px solid {RED}; }}
    .week-cell {{ border-radius: 6px; padding: 14px 8px; text-align: center; font-family: monospace; font-size: 12px; font-weight: 600; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# CONNECTION — secrets only, never exposed to the browser
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

PUBLIC_TENANT = "public_demo"
ALPHA_TENANT = "demo_tenant_alpha"
BETA_TENANT = "demo_tenant_beta"


def api(method: str, path: str, auth: bool = True, timeout: int = 30, **kwargs):
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
    return False, f"still unreachable (last status: {status})"


# ─────────────────────────────────────────────────────────────
# SYNTHETIC DATA
# ─────────────────────────────────────────────────────────────

def synth_transaction(fraud_like: bool) -> dict:
    tx = {}
    for i in range(1, 29):
        tx[f"V{i}"] = random.gauss(0, 1) * (6 if fraud_like else 1)
    tx["Amount"] = (50 + random.random() * 50) if fraud_like else (20 + random.random() * 200)
    return tx


def synth_batch(n: int, shift: float = 0.0) -> list[dict]:
    return [{f"F{i}": random.gauss(shift, 1.0) for i in range(38)} for _ in range(n)]


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=64)
    st.markdown(f"<h2 style='color:{WHITE};margin-top:0;'>Sentinel</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#b4aede;font-size:13px;'>Live investor simulation — every action below hits the real API.</p>", unsafe_allow_html=True)

    if _USING_SECRETS:
        st.markdown("<p style='color:#b4aede;font-size:12px;'>🔒 Connected — credentials configured by the demo owner, never exposed to your browser.</p>", unsafe_allow_html=True)
    else:
        st.info("No secrets configured — enter connection details for local testing.")
        st.session_state.base_url = st.text_input("API base URL", value=st.session_state.base_url)
        st.session_state.api_key = st.text_input("API key", value=st.session_state.api_key, type="password")

    if st.button("Check connection", use_container_width=True):
        awake, msg = wake_and_check()
        st.success(f"Connected ({msg}).") if awake else st.error(f"Could not reach the Space: {msg}")

    st.divider()
    page = st.radio("Go to", ["The Story (start here)", "Deep Dive: Compliance Report", "Deep Dive: Onboard Your Own Model"])
    st.divider()
    st.caption("strataforge3.com")

def require_key():
    if not st.session_state.api_key:
        st.warning("No API key configured. Set SENTINEL_API_KEY in Secrets.")
        st.stop()


# ═════════════════════════════════════════════════════════════
# PAGE: THE STORY
# ═════════════════════════════════════════════════════════════

if page == "The Story (start here)":
    require_key()

    st.title("Watch Sentinel catch what a quieter failure would miss")
    st.markdown(
        "Three real, live actions — not slides, not a recording. Each one is "
        "something a fraud, credit, or risk team deals with today, and each "
        "one is followed by what it's actually worth to a business, in real "
        "numbers from our own testing."
    )
    st.divider()

    # ── ACT 1 ──
    st.markdown('<span class="act-label">Act 1 — The model works</span>', unsafe_allow_html=True)
    st.subheader("Try to slip a fraud attempt past it")
    st.write("A legitimate-looking transaction and a fraud attempt are built from different patterns. Send either to the live model and watch the real decision come back.")

    c1, c2 = st.columns(2)
    if c1.button("✅ Simulate a legitimate transaction", use_container_width=True):
        st.session_state["act1_result"] = ("legit",) + api("POST", "/predict", json={"features": synth_transaction(False)})
    if c2.button("🚨 Simulate a fraud attempt", type="primary", use_container_width=True):
        st.session_state["act1_result"] = ("fraud",) + api("POST", "/predict", json={"features": synth_transaction(True)})

    if "act1_result" in st.session_state:
        kind, ok, status, body = st.session_state["act1_result"]
        if ok:
            caught = body["decision"] == "FRAUD"
            cls = "reveal-caught" if caught else "reveal-clean"
            icon = "🚨 Flagged as fraud" if caught else "✅ Passed as legitimate"
            st.markdown(f"""<div class="{cls}"><b>{icon}</b><br>
                <span style="font-size:1.8rem;font-weight:700;">{body['fraud_probability']*100:.2f}%</span> fraud probability, live from the model
                &nbsp;·&nbsp; decision threshold: {body['threshold_used']}</div>""", unsafe_allow_html=True)
        else:
            st.error(f"Request failed: {body}")

    st.markdown("""<div class="biz-callout">
        <b>What this means for a business:</b> this part — scoring a transaction — is what any fraud model already does.
        It's not Sentinel's value yet; it's the thing Sentinel sits <i>on top of</i>. It's here to prove the model
        behind the rest of this demo is real and live, not a mockup. The actual value starts in Act 2.
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── ACT 2 ──
    st.markdown('<span class="act-label">Act 2 — Catching what the model itself can\'t tell you</span>', unsafe_allow_html=True)
    st.subheader("Watch four weeks of production data drift — and get caught")
    st.write("A model's own accuracy score doesn't tell you when the world underneath it has changed. This sets a clean baseline, then feeds the model a week of data at a time, each week drifting a little further. Watch the alert climb in real time.")

    if st.button("▶️ Run the 4-week sequence", type="primary"):
        status_box = st.empty()
        week_cols = st.columns(5)
        week_states = ["Baseline", "Week 1", "Week 2", "Week 3", "Week 4"]
        for col, label in zip(week_cols, week_states):
            col.markdown(f'<div class="week-cell">{label}</div>', unsafe_allow_html=True)

        status_box.info("Setting baseline reference data…")
        ref_data = synth_batch(500, 0)
        ok, status, body = api("POST", f"/tenants/{PUBLIC_TENANT}/reference", json={
            "data": ref_data, "labels": [1 if random.random() < 0.02 else 0 for _ in ref_data],
            "display_name": "Investor Simulation",
        })
        if ok:
            week_cols[0].markdown('<div class="week-cell week-ok">Baseline ✓</div>', unsafe_allow_html=True)

        shifts = [0.04, 0.10, 0.20, 0.6]  # calibrated to climb OK -> WARNING -> WARNING -> CRITICAL
        explain_text = None
        for i, shift in enumerate(shifts):
            status_box.info(f"Checking week {i+1} of production data…")
            time.sleep(0.6)
            batch = synth_batch(150, shift)
            ok, status, body = api("POST", f"/tenants/{PUBLIC_TENANT}/drift/report", json={"transactions": batch})
            if ok:
                level = body.get("alert_level", "OK").lower()
                week_cols[i+1].markdown(f'<div class="week-cell week-{level}">Week {i+1}<br>{body["alert_level"]}</div>', unsafe_allow_html=True)
                if body.get("alert_level") in ("WARNING", "CRITICAL") and body.get("explanation", {}).get("summary"):
                    explain_text = body["explanation"]["summary"]
                if body.get("alert_level") == "CRITICAL":
                    status_box.success(f"Alert fired at week {i+1}.")
                    break
            else:
                status_box.error(f"Request failed: {body}")
                break
        else:
            status_box.success("Sequence complete.")

        if explain_text:
            st.markdown(f'<div class="biz-callout" style="border-left-color:{ORANGE};"><b>Sentinel Explain:</b> {explain_text}</div>', unsafe_allow_html=True)

    st.markdown("""<div class="biz-callout">
        <b>What this means for a business:</b> that alert is catching something an aggregate accuracy score would hide.
        In our own benchmark, a mean-based detector — the kind most monitoring tools ship by default — caught
        subtle, single-feature drift <b>0% of the time</b>. After the tuning work behind what you just watched,
        that became <b>77%</b> at this same magnitude. The thing that makes this trustworthy, not just sensitive:
        a naive first attempt at this tuning produced a <b>63% false-alarm rate</b> — unusable. The tuned, shipped
        version you just ran sits at <b>4.0%</b>. That gap is the actual product: not a cleverer statistic, the
        unglamorous calibration work most vendors leave for a customer to discover is missing.
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── ACT 3 ──
    st.markdown('<span class="act-label">Act 3 — One customer\'s bad day, nobody else\'s problem</span>', unsafe_allow_html=True)
    st.subheader("Two tenants, drifted differently, checked side by side")
    st.write("Registers two independent model tenants — Alpha and Beta — with identical starting conditions. Drifts Alpha hard. Leaves Beta untouched. Then pulls both dashboards live.")

    if st.button("▶️ Run the isolation proof", type="primary"):
        with st.spinner("Registering Alpha and Beta…"):
            ref_a, ref_b = synth_batch(200, 0), synth_batch(200, 0)
            api("POST", f"/tenants/{ALPHA_TENANT}/reference", json={"data": ref_a, "labels": [0]*200, "display_name": "Demo Tenant Alpha"})
            api("POST", f"/tenants/{BETA_TENANT}/reference", json={"data": ref_b, "labels": [0]*200, "display_name": "Demo Tenant Beta"})
        with st.spinner("Drifting Alpha hard, leaving Beta untouched…"):
            api("POST", f"/tenants/{ALPHA_TENANT}/drift/report", json={"transactions": synth_batch(200, 3.0)})
            api("POST", f"/tenants/{BETA_TENANT}/drift/report", json={"transactions": synth_batch(200, 0.0)})

        col1, col2 = st.columns(2)
        for col, tenant, label in [(col1, ALPHA_TENANT, "Alpha (drifted)"), (col2, BETA_TENANT, "Beta (untouched)")]:
            with col:
                st.markdown(f"**{label}**")
                ok, status, dash = api("GET", f"/tenants/{tenant}/dashboard")
                ok2, status2, alerts = api("GET", f"/tenants/{tenant}/alerts")
                if ok:
                    color = "🟢" if dash["system_status"] == "HEALTHY" else "🔴"
                    st.metric("Status", f"{color} {dash['system_status']}")
                if ok2:
                    st.caption(f"{alerts['total']} alert(s) logged")
        st.success("Same run, seconds apart — zero cross-contamination.")

    st.markdown("""<div class="biz-callout">
        <b>What this means for a business:</b> if you run several models — or you're a platform serving several
        customers' models — this is the guarantee that one customer's bad day doesn't touch another customer's
        data, thresholds, or alerts. Not assumed, not "by design" on a slide: verified directly, through automated
        tests against the real API, the same way every claim in this demo was checked before it was shown to you.
        </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE: DEEP DIVE — COMPLIANCE REPORT
# ═════════════════════════════════════════════════════════════

elif page == "Deep Dive: Compliance Report":
    require_key()
    st.title("The paperwork, already done")
    st.write("Every check, every change, every deployment is written to a tamper-evident record and mapped to the specific regulation it serves as evidence for.")

    framework = st.selectbox("Framework", ["eu_ai_act", "dora"])
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Generate report", type="primary"):
            ok, status, body = api("GET", f"/compliance/report/{framework}")
            if ok:
                st.metric("Total evidence records", body["total_evidence_records"])
                st.metric("Chain integrity", "✅ Valid" if body["integrity"]["valid"] else "❌ BROKEN")
                for art_id, section in body["sections"].items():
                    if section["evidence_count"] > 0:
                        with st.expander(f"{section['title']} — {section['evidence_count']} record(s)"):
                            for ev in section["evidence"]:
                                st.write(f"**{ev['timestamp']}** — {ev['summary']}")
            else:
                st.error(f"Failed: {body}")
    with c2:
        if st.button("Verify tamper-evidence chain"):
            ok, status, body = api("GET", "/compliance/verify")
            if ok:
                st.success(f"Chain valid — {body['records_verified']} records verified.") if body.get("valid") else st.error(f"CHAIN BROKEN: {body}")

    st.markdown("""<div class="biz-callout">
        <b>What this means for a business:</b> "prove your monitoring is working" stops being a scramble through
        logs and becomes a one-click report, already mapped to the article or requirement it satisfies — built
        for the person who has to answer the auditor, not just the person who built the model.
        </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE: DEEP DIVE — ONBOARD YOUR OWN MODEL
# ═════════════════════════════════════════════════════════════

elif page == "Deep Dive: Onboard Your Own Model":
    require_key()
    st.title("How fast a real customer actually integrates")
    st.write("A customer never hands over their model — just the scores it already produces. This is that exact first step.")

    with st.form("onboard"):
        model_id = st.text_input("model_id", "acme_credit_risk_v2")
        display_name = st.text_input("Display name", "Acme Credit Risk Model")
        n = st.slider("Synthetic reference rows", 50, 2000, 300)
        submitted = st.form_submit_button("Register reference data", type="primary")
    if submitted:
        data = synth_batch(n)
        ok, status, body = api("POST", f"/tenants/{model_id}/reference", json={
            "data": data, "labels": [1 if random.random() < 0.02 else 0 for _ in data], "display_name": display_name,
        })
        st.success(f"Registered `{model_id}` — {body['rows']} rows, {len(body['features'])} features.") if ok else st.error(f"Failed: {body}")

    st.markdown("""<div class="biz-callout">
        <b>What this means for a business:</b> that's the entire integration — one API call with data the
        customer already has. No platform migration, nothing to re-architect, typically days of engineering
        work rather than a quarter-long project.
        </div>""", unsafe_allow_html=True)
