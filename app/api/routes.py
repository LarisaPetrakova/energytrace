# app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from statistics import mean
from urllib.parse import quote
import httpx, re

from app.api.deps import get_db
from app.schemas.types import RegionOut, IntensityPoint
from app.db.models import Region, GridIntensity
from app.core.config import settings
from app.utils.postcode import normalize_outward
from app.services.region_map import find_region_by_outward

# 🔸 you were missing this line
router = APIRouter()

# ---------- Region by postcode (robust: upstream + fallback) ----------
# keep your imports; add re and quote if missing
import re
from urllib.parse import quote
import httpx
from sqlalchemy import select
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.types import RegionOut
from app.db.models import Region
from app.core.config import settings

@router.get("/region/by-postcode/{postcode}", response_model=RegionOut, summary="Region By Postcode")
async def region_by_postcode(postcode: str, db: Session = Depends(get_db)):
    # --- 1) Try upstream in several formats ---
    candidates = [
        postcode,
        re.sub(r"\s+", "", postcode),
        re.sub(r"\s+", "", postcode).upper(),
    ]
    payload = None
    async with httpx.AsyncClient(timeout=15) as client:
        for pc in candidates:
            url = f"{settings.carbon_base}/regional/postcode/{quote(pc, safe='')}"
            r = await client.get(url, headers={"Accept": "application/json"})
            if r.status_code in (400, 404):
                continue
            r.raise_for_status()
            payload = r.json()
            break

    if payload:
        data = payload.get("data")
        item = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
        if item and item.get("regionid") is not None:
            regionid = str(item["regionid"])
            shortname = item.get("shortname") or f"Region {regionid}"
            dno = item.get("dnoregion")
            existing = db.execute(select(Region).where(Region.gsp_code == regionid)).scalars().first()
            if existing:
                changed = False
                if existing.name != shortname:
                    existing.name = shortname; changed = True
                if dno and existing.dno_name != dno:
                    existing.dno_name = dno; changed = True
                if changed: db.commit()
                region = existing
            else:
                region = Region(name=shortname, gsp_code=regionid, dno_name=dno)
                db.add(region); db.commit(); db.refresh(region)
            return RegionOut(id=region.id, name=region.name, gsp_code=region.gsp_code, dno_name=region.dno_name)

    # --- 2) Fallback: country/metro guesser (no DB seeds required) ---
    nospace = re.sub(r"\s+", "", postcode).upper()

    # London outcodes → regionid "13"
    london_prefixes = ("EC", "WC", "E", "W", "N", "NW", "SE", "SW")
    # Wales outcodes (common ones)
    wales_prefixes = ("CF", "NP", "SA", "LL", "LD")
    # Scotland outcodes (common ones)
    scot_prefixes = ("AB", "DD", "DG", "EH", "FK", "G", "HS", "IV", "KA", "KW", "ML", "PA", "PH", "ZE")

    # extract outward letters (1–2 letters at start)
    m = re.match(r"^[A-Z]{1,2}", nospace)
    ow = m.group(0) if m else ""

    fallback_regionid = None
    if ow in london_prefixes:
        fallback_regionid = "13"   # London
    elif ow in wales_prefixes:
        fallback_regionid = "17"   # Wales
    elif ow in scot_prefixes:
        fallback_regionid = "16"   # Scotland
    else:
        fallback_regionid = "15"   # England (generic)

    # find that region row (ingest already created them with gsp_code = numeric id)
    region = db.execute(select(Region).where(Region.gsp_code == fallback_regionid)).scalars().first()
    if region:
        return RegionOut(id=region.id, name=region.name, gsp_code=region.gsp_code, dno_name=region.dno_name)

    # If even that’s missing (shouldn't happen with your DB), be explicit:
    raise HTTPException(404, "No postcode match can be found.")


# ---------- Intensity: now ----------
@router.get("/intensity/now/{region_id}", response_model=IntensityPoint)
def intensity_now(region_id: int, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(GridIntensity)
        .where(GridIntensity.region_id == region_id)
        .where(GridIntensity.ts_utc <= now)
        .order_by(GridIntensity.ts_utc.desc())
        .limit(1)
    ).scalars().first()
    if not row:
        raise HTTPException(404, "No intensity data. Run ingest job first.")
    return IntensityPoint(
        ts_utc=row.ts_utc,
        ci_g_per_kwh=row.ci_g_per_kwh,
        renewable_share_pct=row.renewable_share_pct,
        source=row.source,
    )

# ---------- Intensity: forecast ----------
@router.get("/intensity/forecast/{region_id}", response_model=list[IntensityPoint])
def intensity_forecast(region_id: int, hours: int = 48, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    rows = db.execute(
        select(GridIntensity)
        .where(GridIntensity.region_id == region_id)
        .where(GridIntensity.ts_utc >= now)
        .where(GridIntensity.ts_utc <= end)
        .where(GridIntensity.source == "forecast")
        .order_by(GridIntensity.ts_utc.asc())
    ).scalars().all()
    return [
        IntensityPoint(
            ts_utc=r.ts_utc,
            ci_g_per_kwh=r.ci_g_per_kwh,
            renewable_share_pct=r.renewable_share_pct,
            source=r.source,
        )
        for r in rows
    ]

# ---------- Intensity: green windows ----------
@router.get("/intensity/windows/{region_id}")
def green_windows(region_id: int, hours: int = 48, top_n: int = 3, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    rows = db.execute(
        select(GridIntensity)
        .where(GridIntensity.region_id == region_id)
        .where(GridIntensity.ts_utc >= now)
        .where(GridIntensity.ts_utc <= end)
        .where(GridIntensity.source == "forecast")
        .order_by(GridIntensity.ts_utc.asc())
    ).scalars().all()
    if not rows:
        return []
    cis = [r.ci_g_per_kwh for r in rows if r.ci_g_per_kwh is not None]
    if not cis:
        return []
    sorted_cis = sorted(cis)
    q25 = sorted_cis[max(0, int(0.25 * len(sorted_cis)) - 1)]

    windows, cur = [], []
    for r in rows:
        if r.ci_g_per_kwh is not None and r.ci_g_per_kwh <= q25:
            cur.append(r)
        else:
            if cur: windows.append(cur); cur = []
    if cur: windows.append(cur)

    from statistics import mean
    scored = [{
        "start": w[0].ts_utc,
        "end": w[-1].ts_utc,
        "avg_ci": mean([x.ci_g_per_kwh for x in w if x.ci_g_per_kwh is not None]),
        "hours": (w[-1].ts_utc - w[0].ts_utc + timedelta(minutes=30)).total_seconds() / 3600.0,
	"slots": len(w)
    } for w in windows]
    scored.sort(key=lambda x: (x["avg_ci"], -x["hours"]))
    return scored[:top_n]
