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

    try:
        data = payload.get("data")
        # Some NG responses wrap the object in a list
        item = data[0] if isinstance(data, list) and data else data
        if not item or item.get("regionid") is None:
            raise ValueError("No region in response")

        name = item.get("region") or item.get("shortname") or f"Region {item.get('regionid')}"
        dno = item.get("dnoregion") or item.get("dno")
        return {"id": item.get("regionid"), "name": name, "dno_name": dno}
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected response from National Grid")



@router.get("/intensity/now/{region_id}", summary="Current intensity & renewables share for region (stateless)")
async def intensity_now(region_id: int):
    url = f"{NG_BASE}/regional/regionid/{region_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    try:
        outer = (payload.get("data") or [])
        if not outer:
            raise ValueError("Missing outer data list")

        # NG nests the time series under .data[0].data[0]
        region_block = outer[0]
        inner_list = region_block.get("data") or []
        if not inner_list:
            raise ValueError("Missing inner data list")

        point = inner_list[0]  # current half-hour
        intensity_block = point.get("intensity") or {}
        actual = intensity_block.get("actual")
        forecast = intensity_block.get("forecast")
        value = actual if actual is not None else forecast
        source = "actual" if actual is not None else "forecast"

        # Renewables share from generation mix
        renewables_pct = 0.0
        for m in (point.get("generationmix") or []):
            fuel = (m.get("fuel") or "").lower()
            if fuel in {"wind", "solar", "hydro", "biomass"}:
                try:
                    renewables_pct += float(m.get("perc", 0.0))
                except Exception:
                    pass

        return {
            "ts_utc": point.get("from"),
            "ci_g_per_kwh": value,
            "renewable_share_pct": round(renewables_pct, 2),
            "source": source,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected response from National Grid")
