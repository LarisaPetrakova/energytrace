# app/api/routes.py
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()

NG_BASE = "https://api.carbonintensity.org.uk"


@router.get("/region/by-postcode/{postcode}", summary="Resolve region by UK postcode (stateless)")
async def region_by_postcode(postcode: str):
    """
    Calls National Grid's postcode endpoint and returns a minimal region object:
    { id, name, dno_name }
    """
    url = f"{NG_BASE}/regional/postcode/{postcode}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    # Expected NG shape:
    # { "data": [ { "postcode":"EC1V 0HB", "regionid":18, "region":"London", "dnoregion":"UKPN London", ... } ] }
    try:
        data = payload.get("data")
        item = data[0] if isinstance(data, list) and data else None
        if not item:
            raise ValueError("No region in response")

        return {
            "id": item.get("regionid"),              # Streamlit reads 'id' (or 'region_id' fallback)
            "name": item.get("region"),              # human label (e.g., "London")
            "dno_name": item.get("dnoregion"),       # optional
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected response from National Grid")


@router.get("/intensity/now/{region_id}", summary="Current intensity & renewables share for region (stateless)")
async def intensity_now(region_id: int):
    """
    Calls National Grid's regional intensity endpoint and returns:
    {
      ts_utc, ci_g_per_kwh, renewable_share_pct, source
    }
    Source is 'actual' when present; otherwise 'forecast'.
    Renewable share is approximated from generation mix (wind/solar/hydro/biomass).
    """
    url = f"{NG_BASE}/regional/intensity/{region_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    # Expected NG shape:
    # { "data": [ { "from":"...", "to":"...", "intensity":{"forecast":151,"actual":null}, "generationmix":[{"fuel":"wind","perc":..}, ...] } ] }
    try:
        data = payload.get("data")
        item = data[0] if isinstance(data, list) and data else None
        if not item:
            raise ValueError("No data points in response")

        intensity_block = item.get("intensity") or {}
        # Compute renewables share from mix (approximation consistent with NG dashboard)
        mix = item.get("generationmix") or []
        renewables_pct = 0.0
        for m in mix:
            fuel = (m.get("fuel") or "").lower()
            if fuel in {"wind", "solar", "hydro", "biomass"}:
                try:
                    renewables_pct += float(m.get("perc", 0.0))
                except Exception:
                    pass

        actual = intensity_block.get("actual")
        forecast = intensity_block.get("forecast")
        value = actual if actual is not None else forecast
        source = "actual" if actual is not None else "forecast"

        return {
            "ts_utc": item.get("from"),
            "ci_g_per_kwh": value,
            "renewable_share_pct": round(renewables_pct, 2),
            "source": source,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected response from National Grid")
