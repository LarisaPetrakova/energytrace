from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import Region, RegionPrefix

# Minimal seed for demo — extend later
SEED_REGIONS = [
    {"name": "London", "gsp_code": "_LOND", "dno_name": "UK Power Networks"},
    {"name": "South East", "gsp_code": "_SEEA", "dno_name": "UK Power Networks"},
    {"name": "East England", "gsp_code": "_EAST", "dno_name": "UK Power Networks"},
]

SEED_PREFIXES = {
    "_LOND": ["E", "EC", "N", "NW", "SE", "SW", "W", "WC"],
    "_SEEA": ["BN", "BR", "CT", "CR", "DA", "GU", "ME", "PO", "RH", "SM", "KT", "TW"],
    "_EAST": ["CB", "CM", "CO", "IP", "LU", "NR", "PE", "SG", "SS"],
}

def seed_regions(db: Session):
    existing = {r.gsp_code for r in db.query(Region).all()}
    for r in SEED_REGIONS:
        if r["gsp_code"] not in existing:
            db.add(Region(**r))
    db.commit()
    code_to_id = {r.gsp_code: r.id for r in db.query(Region).all()}
    for code, prefixes in SEED_PREFIXES.items():
        rid = code_to_id[code]
        present = {p.prefix for p in db.query(RegionPrefix).filter_by(region_id=rid).all()}
        for p in prefixes:
            if p not in present:
                db.add(RegionPrefix(region_id=rid, prefix=p))
    db.commit()

def find_region_by_outward(db: Session, outward: str) -> Region | None:
    candidates = [outward, outward[:3], outward[:2], outward[:1]]
    stmt = (
        select(Region).join(RegionPrefix, Region.id == RegionPrefix.region_id)
        .where(RegionPrefix.prefix.in_(candidates))
        .limit(1)
    )
    return db.execute(stmt).scalars().first()
