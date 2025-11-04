# app/services/intensity.py
import pendulum
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.db.models import GridIntensity, Region

# ---- helpers ---------------------------------------------------------------

def iso_no_ms(dt) -> str:
    """Strict UTC ISO8601 without milliseconds (e.g., 2025-11-03T18:00Z)."""
    return pendulum.instance(dt).in_timezone("UTC").format("YYYY-MM-DD[T]HH:mm[Z]")

async def fetch_all_regions_pt24h(from_ts: str) -> dict:
    """Past 24h (from 'from_ts') for ALL regions."""
    url = f"{settings.carbon_base}/regional/intensity/{from_ts}/pt24h"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()

async def fetch_all_regions_fw48h(from_ts: str) -> dict:
    """Next 48h (from 'from_ts') for ALL regions."""
    url = f"{settings.carbon_base}/regional/intensity/{from_ts}/fw48h"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()

def upsert_region(db: Session, regionid: int | str | None, shortname: str | None, dno: str | None) -> Region | None:
    if regionid is None:
        return None
    rid_str = str(regionid)  # store numeric id as string in gsp_code
    existing = db.execute(select(Region).where(Region.gsp_code == rid_str)).scalars().first()
    if existing:
        changed = False
        if shortname and existing.name != shortname:
            existing.name = shortname; changed = True
        if dno and existing.dno_name != dno:
            existing.dno_name = dno; changed = True
        if changed:
            db.commit()
        return existing
    region = Region(name=shortname or f"Region {rid_str}", gsp_code=rid_str, dno_name=dno)
    db.add(region); db.commit(); db.refresh(region)
    return region

def upsert_point(db: Session, region_id: int, ts_from: str, ci_value: float,
                 ren_mix: list[dict] | None, source: str) -> None:
    """Idempotent upsert of a single half-hour point using ON CONFLICT."""
    ts = pendulum.parse(ts_from).in_timezone("UTC")
    ren_pct = None
    if ren_mix:
        total = sum(g.get("perc", 0.0) for g in ren_mix) or 1.0
        ren_share = sum(
            g.get("perc", 0.0) for g in ren_mix
            if g.get("fuel") in ["wind", "solar", "hydro", "biomass"]
        ) / total
        ren_pct = ren_share * 100.0

    stmt = pg_insert(GridIntensity).values(
        region_id=region_id,
        ts_utc=ts,  # tz-aware; model column is TIMESTAMP WITH TIME ZONE
        ci_g_per_kwh=float(ci_value),
        renewable_share_pct=ren_pct,
        source=source,
    ).on_conflict_do_update(
        constraint="uq_intensity_region_ts_source",
        set_={
            "ci_g_per_kwh": float(ci_value),
            "renewable_share_pct": ren_pct,
            "source": source,
        }
    )
    db.execute(stmt)
