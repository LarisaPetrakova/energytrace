# app/ingest/fetch_intensity.py
import asyncio
import pendulum
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.intensity import (
    iso_no_ms,
    fetch_all_regions_pt24h, fetch_all_regions_fw48h,
    upsert_region, upsert_point
)

def process_payload(db: Session, payload: dict) -> None:
    """
    payload['data'] is a list of time blocks:
      { "from": "...Z", "to": "...Z",
        "regions": [
           { "regionid": 13, "shortname": "...", "dnoregion": "...",
             "intensity": {"actual": N} or {"forecast": N},
             "generationmix": [...] (optional)
           }, ...
        ]
      }
    """
    for block in payload.get("data", []):
        ts_from = block.get("from")
        for rr in (block.get("regions") or []):
            region = upsert_region(db, rr.get("regionid"), rr.get("shortname"), rr.get("dnoregion"))
            if region is None:
                continue
            inten = rr.get("intensity") or {}
            if "actual" in inten and inten["actual"] is not None:
                ci, source = inten["actual"], "actual"
            else:
                ci, source = inten.get("forecast"), "forecast"
            if ci is None:
                continue
            upsert_point(db, region.id, ts_from, ci, rr.get("generationmix"), source)

async def ingest_once(db: Session) -> None:
    now = pendulum.now("UTC")
    ts_str = iso_no_ms(now)
    past = await fetch_all_regions_pt24h(ts_str)
    process_payload(db, past)
    db.commit()
    future = await fetch_all_regions_fw48h(ts_str)
    process_payload(db, future)
    db.commit()

async def main():
    with SessionLocal() as db:
        await ingest_once(db)

if __name__ == "__main__":
    asyncio.run(main())
