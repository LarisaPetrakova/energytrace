import os
import requests
import pandas as pd
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="EnergyTrace", page_icon="⚡", layout="wide")
st.title("EnergyTrace ⚡")
st.caption("Plan usage when the grid is greenest.")

# ---------- Helpers (cached) ----------
@st.cache_data(ttl=120)
def get_region_by_postcode(pc: str):
    r = requests.get(f"{API_BASE}/api/region/by-postcode/{pc}", timeout=15)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=60)
def get_now(region_id: int):
    r = requests.get(f"{API_BASE}/api/intensity/now/{region_id}", timeout=15)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=300)
def get_forecast(region_id: int):
    r = requests.get(f"{API_BASE}/api/intensity/forecast/{region_id}", timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=300)
def get_windows(region_id: int):
    r = requests.get(f"{API_BASE}/api/intensity/windows/{region_id}", timeout=20)
    r.raise_for_status()
    data = r.json()
    # Some backends wrap windows under {"windows":[...]}
    if isinstance(data, dict) and "windows" in data:
        return data["windows"]
    return data

# ---------- UI ----------
postcode = st.text_input("Enter UK Postcode (e.g., EC1V 0HB)")
region_id = None
region_label = None

if postcode:
    try:
        reg = get_region_by_postcode(postcode.strip())
        # Your API returns: {'id': 18, 'name': 'London', 'gsp_code': '13', 'dno_name': 'UKPN London'}
        region_id = reg.get("id") or reg.get("region_id")
        region_label = reg.get("name", str(region_id))
        st.success(f"Region found: {reg}")
    except Exception as e:
        st.error(f"Error fetching region: {e}")

if region_id:
    st.subheader("Current Intensity")
    try:
        now = get_now(int(region_id))
        ci = now.get("ci_g_per_kwh")
        renew = now.get("renewable_share_pct")
        ts = now.get("ts_utc", "")
        source = (now.get("source") or "").capitalize()  # "Forecast" | "Actual" typically

        cols = st.columns(3)
        with cols[0]:
            st.metric("Carbon intensity", f"{ci} gCO₂/kWh" if ci is not None else "—")
        with cols[1]:
            if isinstance(renew, (int, float)):
                st.metric("Renewables share", f"{renew:.1f}%")
            else:
                st.metric("Renewables share", "—")
        with cols[2]:
            st.metric("Region", region_label or region_id)

        # Clarifying caption (your question 1 + 30-minute cadence)
        st.caption(f"Data for {ts} UTC • Source: {source or 'Unknown'} • Updated every 30 minutes (National Grid).")

        # Optional gentle note if it's forecasted
        if source.lower() == "forecast":
            st.info("Showing forecasted intensity for the current half-hour period. "
                    "Measured (“Actual”) values usually appear after the period ends.")
    except Exception as e:
        st.warning(f"Could not fetch intensity: {e}")

    st.divider()
    st.subheader("Forecast (next hours)")
    try:
        fc = get_forecast(int(region_id))
        # Accept either a plain list of dicts or a wrapped payload
        # Expected keys per point: 'from' (ISO), 'to' (ISO), 'ci_g_per_kwh' (number)
        if isinstance(fc, dict) and "forecast" in fc:
            fc = fc["forecast"]

        df = pd.DataFrame(fc)
        # Try to normalize/rename columns if needed
        if "from" not in df.columns:
            # Sometimes APIs use 'start' or 'ts_utc' for the time axis in forecasts
            if "start" in df.columns:
                df = df.rename(columns={"start": "from"})
            elif "ts_utc" in df.columns:
                df = df.rename(columns={"ts_utc": "from"})
        if "ci_g_per_kwh" not in df.columns:
            # Sometimes returned as 'value' or 'intensity'
            if "value" in df.columns:
                df = df.rename(columns={"value": "ci_g_per_kwh"})
            elif "intensity" in df.columns and isinstance(df["intensity"].iloc[0], (int, float)):
                df = df.rename(columns={"intensity": "ci_g_per_kwh"})

        if "from" in df.columns and "ci_g_per_kwh" in df.columns:
            df["from"] = pd.to_datetime(df["from"])
            df = df.sort_values("from")
            st.line_chart(df.set_index("from")["ci_g_per_kwh"])
            st.caption("Half-hourly periods • values may be forecast for future slots.")
        else:
            st.write("Unexpected forecast format:", df.head())
    except Exception as e:
        st.warning(f"Could not fetch forecast: {e}")

    st.divider()
    st.subheader("Green windows (best times to use electricity)")
    try:
        wins = get_windows(int(region_id))
        if wins:
            grid = st.columns(3)
            for i, w in enumerate(wins[:6]):  # show up to 6 cards
                with grid[i % 3]:
                    start = pd.to_datetime(w.get("start") or w.get("from")).strftime("%a %H:%M")
                    end = pd.to_datetime(w.get("end") or w.get("to")).strftime("%H:%M")
                    avg = w.get("avg_intensity") or w.get("ci_g_per_kwh") or w.get("value")
                    st.success(f"{start} – {end}\n\n**~{avg} gCO₂/kWh**")
        else:
            st.write("No low-carbon windows in the near future.")
    except Exception as e:
        st.warning(f"Could not load green windows: {e}")

# Footer
st.caption("Data via EnergyTrace API • National Grid Carbon Intensity service updates roughly every 30 minutes.")
