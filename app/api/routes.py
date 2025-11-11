# app/api/routes.py
from fastapi import APIRouter, HTTPException
import httpx
import re

router = APIRouter()

NG_BASE = "https://api.carbonintensity.org.uk"


def to_outward(postcode: str) -> str:
    """Return the outward part (area+district) of a UK postcode, uppercased."""
    if not postcode:
        return ""
    # strip spaces, upper, then take leading letters+digits up to first digit/space boundary
    pc = postcode.strip().upper()
    # simplest robust way: outward is token before the space if present
    if " " in pc:
        pc = pc.split(" ")[0]
    return pc


@router.get("/region/by-postcode/{postcode}", summary="Resolve region by UK postcode (stateless)")
async def region_by_postcode(postcode: str):
    """
    Calls National Grid's postcode endpoint with the OUTWARD postcode and returns:
    { id, name, dno_name }
    """
    outward = to_outward(postcode)
    if not outward:
        raise HTTPException(status_code=400, detail="Invalid postcode")

    url = f"{NG_BASE}/regional/postcode/{outward}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    # Expected NG shape:
    # { "data": [ { "postcode":"W4", "regionid":13, "region":"London", "dnoregion":"UKPN London", ... } ] }
    try:
        data = payload.get("data")
        item = data[0] if isinstance(data, list) and data else None
        if not item or item.get("regionid") is None:
            raise ValueError("No region in response")

        return {
            "id": item.get("regionid"),
            "name": item.get("region"),
            "dno_name": item.get("dnoregion"),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected response from National Grid")


@router.get("/intensity/now/{region_id}", summary="Current intensity & renewables share for region (stateless)")
async def intensity_now(region_id: int):
    """
    Calls National Grid's *current* regional endpoint for the given region_id:
    GET /regional/regionid/{regionid}
    Returns:
      { ts_utc, ci_g_per_kwh, renewable_share_pct, source }
    """
    url = f"{NG_BASE}/regional/regionid/{region_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    # Expected NG shape:
    # { "data": [ { "from":"...", "to":"...", "intensity":{"forecast":..,"actual":..}, "generationmix":[{"fuel":"wind","perc":..}, ...] } ] }
    try:
        data = payload.get("data")
        item = data[0] if isinstance(data, list) and data else None
        if not item:
            raise ValueError("No data points in response")

        intensity_block = item.get("intensity") or {}
        actual = intensity_block.get("actual")
        forecast = intensity_block.get("forecast")
        value = actual if actual is not None else forecast
        source = "actual" if actual is not None else "forecast"

        # Compute renewables share from generation mix (wind/solar/hydro/biomass)
        renewables_pct = 0.0
        for m in (item.get("generationmix") or []):
            fuel = (m.get("fuel") or "").lower()
            if fuel in {"wind", "solar", "hydro", "biomass"}:
                try:
                    renewables_pct += float(m.get("perc", 0.0))
                except Exception:
                    pass

        return {
            "ts_utc": item.get("from"),
            "ci_g_per_kwh": value,
            "renewable_share_pct": round(renewables_pct, 2),
            "source": source,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected response from National Grid")
