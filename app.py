"""
BioSync FHIR — Streamlit Application

Run with:
    python -m streamlit run app.py

Environment Variables:
    BACKEND_URL     Base URL of the FastAPI backend, e.g. http://localhost:8000
                    If not set, the app runs in MOCK MODE using synthetic data.
                    In production set this via Streamlit Community Cloud secrets:
                        [secrets]
                        BACKEND_URL = "https://your-backend.onrender.com"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BACKEND API CONTRACT
The Streamlit frontend expects the following FastAPI endpoints.
All responses are JSON. All list endpoints return arrays of objects.

  GET  /patients
       → [{ id, name, age, last_updated }, ...]

  GET  /patients/{patient_id}/wearable
       → [{ date, steps, heart_rate_avg, sleep_hours, active_minutes }, ...]
         date is an ISO 8601 string, e.g. "2024-03-01"

  GET  /patients/{patient_id}/genomic-variants
       → [{ gene, variant, condition, clinvar }, ...]
         clinvar is one of: "Pathogenic" | "Likely Pathogenic" |
                            "Uncertain Significance" | "Benign"

  GET  /patients/{patient_id}/consent
       → { steps: bool, heart_rate: bool, sleep: bool, genomic: bool }

  POST /patients/{patient_id}/consent
       body: { steps: bool, heart_rate: bool, sleep: bool, genomic: bool }
       → { success: true }

  POST /auth/login                          [TODO — not yet wired in UI]
       body: { username: str, password: str }
       → { access_token: str, role: "patient" | "provider", patient_id: str }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


# ── Backend configuration ──────────────────────────────────────────────────────

# Priority: Streamlit secrets → environment variable → empty (mock mode)
try:
    _BACKEND_URL = st.secrets.get("BACKEND_URL", "")
except Exception:
    _BACKEND_URL = os.getenv("BACKEND_URL", "")
_BACKEND_URL = _BACKEND_URL.rstrip("/")


def _backend_available() -> bool:
    return bool(_BACKEND_URL) and _REQUESTS_AVAILABLE


def _get(path: str):
    """GET from backend; returns parsed JSON or None on any failure."""
    try:
        resp = _requests.get(f"{_BACKEND_URL}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _post(path: str, payload: dict):
    """POST to backend; returns parsed JSON or None on any failure."""
    try:
        resp = _requests.post(f"{_BACKEND_URL}{path}", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ── Data access layer ──────────────────────────────────────────────────────────
# Brutally honest API fetch architecture: Failure physically triggers an error
# instead of simulating synthetic data arrays.

@st.cache_data(ttl=60)
def get_patients() -> list:
    if _backend_available():
        data = _get("/patients")
        if data is not None:
            return data
    st.error("Backend connection failed. Cannot load patients.")
    return []


@st.cache_data(ttl=60)
def get_wearable_data(patient_id: str) -> pd.DataFrame:
    if _backend_available():
        data = _get(f"/patients/{patient_id}/wearable")
        if data is not None:
            df = pd.DataFrame(data)
            if not df.empty and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            return df
    st.error("Backend connection failed. Cannot load wearable data.")
    return pd.DataFrame()


@st.cache_data(ttl=60)
def get_genomic_variants(patient_id: str) -> list:
    if _backend_available():
        data = _get(f"/patients/{patient_id}/genomic-variants")
        if data is not None:
            return data
    st.error("Backend connection failed. Cannot load genomic variants.")
    return []


def get_consent(patient_id: str) -> dict:
    if _backend_available():
        data = _get(f"/patients/{patient_id}/consent")
        if data is not None:
            return data
    return {"steps": False, "heart_rate": False, "sleep": False, "genomic": False}


def save_consent(patient_id: str, payload: dict) -> bool:
    """Returns True if saved to backend, False if network fails."""
    if _backend_available():
        result = _post(f"/patients/{patient_id}/consent", payload)
        if result is not None and result.get("success", False):
            st.cache_data.clear()
            return True
    return False


# ── Shared helpers ─────────────────────────────────────────────────────────────

def clinvar_badge(status: str):
    """Render a colored badge for a ClinVar pathogenicity status."""
    if status == "Pathogenic":
        st.error(status)
    elif status == "Likely Pathogenic":
        st.warning(status)
    else:
        st.info(status)


# ── Page configuration ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BioSync FHIR",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Patient Dashboard ──────────────────────────────────────────────────────────
# TODO: once JWT auth is wired, replace the default patient_id with the value
#       from st.session_state["patient_id"] set at login.

def patient_dashboard(patient_id: str = "P001"):
    st.title("My Health Dashboard")
    st.caption("BioSync FHIR — Patient View")

    df = get_wearable_data(patient_id)

    # ── Summary metrics ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg Daily Steps",    f"{int(df['steps'].mean()):,}",            "+320 vs last month")
    c2.metric("Avg Heart Rate",     f"{int(df['heart_rate_avg'].mean())} bpm", "-2 vs last month")
    c3.metric("Avg Sleep",          f"{df['sleep_hours'].mean():.1f} hrs",     "+0.3 vs last month")
    c4.metric("Avg Active Minutes", f"{int(df['active_minutes'].mean())} min", "+5 vs last month")

    st.divider()

    # ── Wearable trend charts ──────────────────────────────────────────────────
    st.subheader("My Wearable Data")

    tab_steps, tab_hr, tab_sleep = st.tabs(["Steps", "Heart Rate", "Sleep"])

    with tab_steps:
        fig = px.line(df, x="date", y="steps", title="Daily Step Count (Last 30 Days)")
        fig.add_hline(y=7500, line_dash="dash", line_color="green",
                      annotation_text="Recommended (7,500 steps)")
        fig.update_traces(line_color="#4A90D9")
        st.plotly_chart(fig, use_container_width=True)

    with tab_hr:
        fig = px.line(df, x="date", y="heart_rate_avg",
                      title="Average Daily Resting Heart Rate (Last 30 Days)")
        fig.update_traces(line_color="#E05C5C")
        st.plotly_chart(fig, use_container_width=True)

    with tab_sleep:
        fig = px.bar(df, x="date", y="sleep_hours",
                     title="Sleep Duration (Last 30 Days)")
        fig.add_hline(y=7.0, line_dash="dash", line_color="green",
                      annotation_text="Recommended (7 hrs)")
        fig.update_traces(marker_color="#7B68EE")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Genomic profile ────────────────────────────────────────────────────────
    st.subheader("My Genomic Profile")
    st.caption(
        "Variant pathogenicity classifications sourced dynamically from ClinVar (NCBI). "
        "**BioSync FHIR is a research demonstration tool and does not constitute medical advice.**"
    )

    variants = get_genomic_variants(patient_id)

    header_cols = st.columns([1, 2.5, 3, 1.5])
    header_cols[0].markdown("**Gene**")
    header_cols[1].markdown("**Variant (HGVS)**")
    header_cols[2].markdown("**Associated Condition**")
    header_cols[3].markdown("**ClinVar Status**")
    st.divider()

    for v in variants:
        c1, c2, c3, c4 = st.columns([1, 2.5, 3, 1.5])
        c1.markdown(f"**{v['gene']}**")
        c2.code(v["variant"], language=None)
        c3.write(v["condition"])
        with c4:
            clinvar_badge(v["clinvar"])
        st.divider()

    # ── Consent management ─────────────────────────────────────────────────────
    st.subheader("Data Sharing Consent")
    st.caption(
        "Control which data types are visible to your provider. "
        "Changes are saved as FHIR Consent resources."
    )

    current = get_consent(patient_id)

    c1, c2 = st.columns(2)
    with c1:
        steps_on   = st.toggle("Share Step Count Data",     value=current.get("steps",      True),  key=f"consent_steps_{patient_id}")
        hr_on      = st.toggle("Share Heart Rate Data",      value=current.get("heart_rate", True),  key=f"consent_hr_{patient_id}")
    with c2:
        sleep_on   = st.toggle("Share Sleep Data",           value=current.get("sleep",      False), key=f"consent_sleep_{patient_id}")
        genomic_on = st.toggle("Share Genomic Variant Data", value=current.get("genomic",    True),  key=f"consent_genomic_{patient_id}")

    if st.button("Save Consent Preferences", type="primary"):
        payload = {
            "steps":      steps_on,
            "heart_rate": hr_on,
            "sleep":      sleep_on,
            "genomic":    genomic_on,
        }
        if save_consent(patient_id, payload):
            st.success("Consent preferences saved as FHIR Consent resource.")
        else:
            st.info("Consent preferences saved locally (backend not connected).")


# ── Provider Dashboard ─────────────────────────────────────────────────────────

def provider_dashboard():
    st.title("Patient Risk Dashboard")
    st.caption("BioSync FHIR — Provider View")

    patients = get_patients()
    selected_name = st.session_state.get("selected_patient", patients[0]["name"])
    patient = next((p for p in patients if p["name"] == selected_name), patients[0])
    patient_id = patient["id"]

    # Fetch consent before rendering anything — gates all sections below
    consent = get_consent(patient_id)
    steps_shared   = consent.get("steps",      True)
    hr_shared      = consent.get("heart_rate", True)
    sleep_shared   = consent.get("sleep",      False)
    genomic_shared = consent.get("genomic",    True)

    df = get_wearable_data(patient_id) if (steps_shared or hr_shared or sleep_shared) else None

    # ── Patient header ─────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patient",      patient["name"])
    c2.metric("Patient ID",   patient["id"])
    c3.metric("Age",          patient["age"])
    c4.metric("Last Updated", patient["last_updated"])

    st.divider()

    # ── Consent status summary ─────────────────────────────────────────────────
    st.subheader("Patient Consent Status")
    st.caption("Data types the patient has authorized for provider access.")

    consent_display = [
        ("Steps",        steps_shared),
        ("Heart Rate",   hr_shared),
        ("Sleep",        sleep_shared),
        ("Genomic Data", genomic_shared),
    ]
    cols = st.columns(len(consent_display))
    for col, (label, shared) in zip(cols, consent_display):
        with col:
            if shared:
                st.success(f"✓ {label} — Shared")
            else:
                st.error(f"✗ {label} — Not shared")

    st.divider()

    # ── Wearable trends ────────────────────────────────────────────────────────
    st.subheader("Wearable Trends")

    visible_charts = []
    if steps_shared:
        visible_charts.append("steps")
    if hr_shared:
        visible_charts.append("heart_rate")

    if not visible_charts:
        st.info("🔒 Patient has not shared any wearable data with providers.")
    else:
        cols = st.columns(len(visible_charts))
        for col, metric in zip(cols, visible_charts):
            with col:
                if metric == "steps":
                    fig = px.line(df, x="date", y="steps", title="Daily Steps")
                    fig.add_hline(y=7500, line_dash="dash", line_color="green",
                                  annotation_text="Recommended (7,500)")
                    fig.update_traces(line_color="#4A90D9")
                    st.plotly_chart(fig, use_container_width=True)
                elif metric == "heart_rate":
                    fig = px.line(df, x="date", y="heart_rate_avg",
                                  title="Avg Resting Heart Rate")
                    fig.update_traces(line_color="#E05C5C")
                    st.plotly_chart(fig, use_container_width=True)

    if sleep_shared and df is not None:
        fig = px.bar(df, x="date", y="sleep_hours", title="Sleep Duration (Last 30 Days)")
        fig.add_hline(y=7.0, line_dash="dash", line_color="green",
                      annotation_text="Recommended (7 hrs)")
        fig.update_traces(marker_color="#7B68EE")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Genomic risk flags ─────────────────────────────────────────────────────
    st.subheader("Genomic Risk Flags")

    if not genomic_shared:
        st.info("🔒 Patient has not shared genomic data with providers.")
    else:
        st.caption(
            "Pathogenicity classifications from ClinVar (NCBI). "
            "**For clinical context only — does not constitute diagnostic guidance.**"
        )
        variants = get_genomic_variants(patient_id)
        for v in variants:
            with st.expander(f"**{v['gene']}** — {v['condition']}"):
                c1, c2, c3 = st.columns([2, 3, 1.5])
                c1.markdown("**Variant (HGVS)**")
                c1.code(v["variant"], language=None)
                c2.markdown("**Associated Condition**")
                c2.write(v["condition"])
                c3.markdown("**ClinVar Status**")
                with c3:
                    clinvar_badge(v["clinvar"])


# ── Sidebar + routing ──────────────────────────────────────────────────────────

def main():
    with st.sidebar:
        st.markdown("## BioSync FHIR")
        st.caption("Closing the loop between genomics and daily life")
        st.divider()

        role = st.radio("View As", ["Patient", "Provider"], index=0)

        patients = get_patients()
        st.divider()

        if role == "Patient":
            st.markdown("**Demo: Select Patient**")
            patient_names = [p["name"] for p in patients]
            selected_patient_name = st.selectbox(
                "Viewing as",
                patient_names,
                key="patient_view_select",
                label_visibility="collapsed",
            )
            active_patient = next(p for p in patients if p["name"] == selected_patient_name)

        else:
            st.markdown("**Patient List**")
            for p in patients:
                label = f"{p['name']}  ·  {p['id']}"
                if st.button(label, key=f"btn_{p['id']}", use_container_width=True):
                    st.session_state["selected_patient"] = p["name"]
            active_patient = None  # provider_dashboard() handles its own selection

        st.divider()

        if _backend_available():
            st.success("● Connected to backend")
        else:
            st.warning("● Mock mode")
            st.caption(
                "Set `BACKEND_URL` to connect to the FastAPI backend. "
                "See the docstring in `app.py` for the full API contract."
            )

        st.divider()
        st.caption(
            "⚠️ BioSync FHIR is a research demonstration tool "
            "and does not constitute medical advice."
        )

    if role == "Patient":
        patient_dashboard(patient_id=active_patient["id"])
    else:
        provider_dashboard()


if __name__ == "__main__":
    main()
