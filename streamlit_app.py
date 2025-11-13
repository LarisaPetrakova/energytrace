import os
import requests
import streamlit as st

import time


def fetch_json(url: str, retries: int = 5, timeout: int = 10):
    """
    Small helper that retries a GET several times.
    Useful when the Render backend is waking up.
    """
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            # simple backoff: 1s, 2s, 3s, ...
            time.sleep(1 * (attempt + 1))
    # if we get here, all retries failed
    raise last_err



st.caption(f"DEBUG API_BASE: {API_BASE}")

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

# ---------- Page setup ----------
st.set_page_config(page_title="EnergyTrace UK", page_icon="⚡", layout="centered")

st.markdown(
    """
    # ⚡ EnergyTrace UK
    *Check how clean the electricity is in your area — right now.*

    > **Note:** EnergyTrace currently works for **UK postcodes only** and updates roughly **every 30 minutes**.
    """
)

# ---------- Helpers (cached) ----------
@st.cache_data(ttl=300)
def get_region_by_postcode(pc: str):
    url = f"{API_BASE}/api/region/by-postcode/{pc}"
    return fetch_json(url, retries=5, timeout=10)

@st.cache_data(ttl=60)
def get_now(region_id: int):
    url = f"{API_BASE}/api/intensity/now/{region_id}"
    return fetch_json(url, retries=5, timeout=10)


# ---------- UI ----------
# Persist inputs between reruns
if "postcode" not in st.session_state:
    st.session_state.postcode = ""

with st.form("postcode_form", clear_on_submit=False):
    st.text_input("Enter UK Postcode (e.g., EC1V 0HB)", key="postcode")
    submitted = st.form_submit_button("Check intensity")

region_id = None
region_label = None

if submitted and st.session_state.postcode.strip():
    pc = st.session_state.postcode.strip()
    with st.spinner("Looking up your region…"):
        try:
            reg = get_region_by_postcode(pc)
            # Expected: {'id': 18, 'name': 'London', 'gsp_code': '13', 'dno_name': 'UKPN London'}
            region_id = reg.get("id") or reg.get("region_id")
            region_label = reg.get("name", str(region_id))
            st.success(f"Region: {region_label} · DNO: {reg.get('dno_name','—')}")
        except Exception:
            st.error("❌ Couldn't find this postcode. EnergyTrace currently supports UK regions only.")
            region_id = None

# If we have a region, fetch the current intensity
if region_id:
    st.markdown("## Current intensity")

    with st.spinner("Fetching current carbon intensity…"):
        try:
            now = get_now(int(region_id))
            ci = now.get("ci_g_per_kwh")
            renew = now.get("renewable_share_pct")
            ts = now.get("ts_utc", "")
            source = (now.get("source") or "").capitalize()  # "Forecast" or "Actual"

            # Metrics row
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Carbon intensity", f"{ci} gCO₂/kWh" if ci is not None else "—")
            with col2:
                st.metric("Renewables share", f"{renew:.1f}%" if isinstance(renew, (int, float)) else "—")
            with col3:
                st.metric("Region", region_label or region_id)

            # Clarifying caption + cadence
            st.caption(f"Data for {ts} UTC • Source: {source or 'Unknown'} • Updates every 30 minutes (National Grid).")

            if source.lower() == "forecast":
                st.info(
                    "Showing **forecasted** intensity for the current half-hour period. "
                    "Measured (**Actual**) values usually appear after the period ends."
                )
        # except Exception:
            # st.warning("Data temporarily unavailable. Please try again in a few minutes.")
	  except Exception as e:
    		st.error(f"Request failed: {e}")

st.markdown("---")
st.caption("Data via EnergyTrace API • National Grid Carbon Intensity service.")
