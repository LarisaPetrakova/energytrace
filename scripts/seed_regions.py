from app.db.session import SessionLocal
from app.services.region_map import seed_regions

if __name__ == "__main__":
    with SessionLocal() as db:
        seed_regions(db)
        print("Regions & prefixes seeded.")
