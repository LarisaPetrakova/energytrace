⚡️ EnergyTrace — Electricity Origin & Carbon Intensity Explorer

EnergyTrace is a sustainability analytics prototype that helps users explore the carbon intensity of the UK electricity grid by region and by time.
It connects to the official National Grid Carbon Intensity API
 and stores results locally, enabling fast lookup, postcode-based queries, and clean energy window recommendations.

🌍 Purpose

Consumers and communities rarely know when or where their electricity is cleanest.
EnergyTrace fills that gap by:

Mapping postcodes to their corresponding grid supply region (GSP),

Fetching and caching real-time & forecast carbon intensity data for all regions,

Computing low-carbon time windows (when grid power is greenest).

This provides a foundation for future tools like:

Household apps that schedule devices for low-carbon hours,

Local dashboards that visualize renewable share and grid impact,

APIs for sustainability education or energy research.

🧠 Architecture Overview

The project has two main parts:

EnergyTrace/
│
├── app/
│   ├── api/              # FastAPI routes (REST endpoints)
│   │   ├── routes.py     # Region, intensity, and window endpoints
│   │   └── deps.py       # Dependency helpers (DB session)
│   │
│   ├── core/             # App configuration (env, base URLs)
│   │   └── config.py
│   │
│   ├── db/               # Database logic
│   │   ├── models.py     # SQLAlchemy ORM models
│   │   ├── session.py    # DB engine + session factory
│   │   └── init.sql      # optional setup script
│   │
│   ├── ingest/           # Data fetching and ingestion jobs
│   │   └── fetch_intensity.py
│   │
│   ├── services/         # External API connectors + data handling
│   │   └── intensity.py  # Fetching, upserting intensity data
│   │
│   ├── schemas/          # Pydantic schemas for API I/O
│   │   └── types.py
│   │
│   └── main.py           # FastAPI app entry point
│
├── scripts/              # One-off setup / DB seeding
│
├── ui/                   # (optional) Streamlit dashboard
│   └── app.py
│
└── README.md             # You are here

⚙️ How It Works
1. Data Ingestion (app/ingest/fetch_intensity.py)

Uses the Carbon Intensity API to download:

24 hours of past data (pt24h)

48 hours of forecast data (fw48h)

Extracts:

regionid (numeric code for each GSP region)

intensity.actual or intensity.forecast

generationmix (used to calculate renewable share %)

Inserts data into PostgreSQL (or local SQLite) using SQLAlchemy.

✅ Technical highlight:
Instead of re-downloading duplicates, the code uses PostgreSQL’s ON CONFLICT upsert, so it updates existing records safely:

ON CONFLICT (region_id, ts_utc, source) DO UPDATE


The ingest script is fully idempotent — you can run it any time, and it will refresh existing data without errors.

2. Regional Mapping (Postcode → Region)

The /api/region/by-postcode/{postcode} route:

Queries the Carbon Intensity API for the region ID corresponding to a postcode (e.g., “SW1A 1AA”).

If the upstream lookup fails, uses an internal fallback mapping based on the postcode prefix:

EC, W, NW, SW → London

CF, LL, NP → Wales

EH, G, AB, IV → Scotland

otherwise → England

Ensures the region exists in the local database (so intensity data can be linked).

✅ Example:

{
  "id": 18,
  "name": "London",
  "gsp_code": "13",
  "dno_name": "UKPN London"
}

3. Carbon Intensity API (FastAPI Endpoints)
Endpoint	Description
/api/region/by-postcode/{postcode}	Map postcode → region
/api/intensity/now/{region_id}	Get the latest CI value
/api/intensity/forecast/{region_id}?hours=48	48-hour forecast
/api/intensity/windows/{region_id}	Identify greenest periods
/api/region/list	List all known regions
/api/region/by-name/{name}	Lookup by region name

✅ Green Windows Algorithm:
Calculates time windows where carbon intensity ≤ 25th percentile of all forecast values.
These periods are grouped into continuous blocks and sorted by:

Lowest average intensity

Longest duration

4. Data Model
Table	Description
region	One row per grid region (GSP), with gsp_code, name, dno_name
grid_intensity	Half-hourly carbon intensity + renewable share per region

Each half-hour interval is unique per (region_id, ts_utc, source).

5. Example Outputs
✅ Region lookup
GET /api/region/by-postcode/SW1A%201AA
→ id=18 (London)

✅ Intensity now
{
  "ts_utc": "2025-11-04T11:00:00Z",
  "ci_g_per_kwh": 95,
  "renewable_share_pct": 46.4,
  "source": "forecast"
}

✅ Green windows
[
  {
    "start": "2025-11-05T22:30:00+00:00",
    "end": "2025-11-06T02:30:00+00:00",
    "avg_ci": 82.6,
    "hours": 4.0
  },
  {
    "start": "2025-11-04T22:30:00+00:00",
    "end": "2025-11-05T02:30:00+00:00",
    "avg_ci": 85.1,
    "hours": 4.0
  }
]

🖥️ Running Locally
Prerequisites

Python ≥ 3.10

PostgreSQL or SQLite

FastAPI + Uvicorn

(Optional) Streamlit for the UI

Setup
git clone <your-repo-url>
cd EnergyTrace
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn sqlalchemy httpx pendulum psycopg2-binary pydantic

Initialize database
python -m scripts.init_db
python -m app.ingest.fetch_intensity

Run API
python -m uvicorn app.main:app --reload


Open http://127.0.0.1:8000/docs

📊 (Optional) Streamlit Dashboard

Soon you’ll add a UI (in ui/app.py) that:

lets users enter a postcode,

fetches the intensity forecast via REST,

plots a line chart of gCO₂/kWh,

highlights green windows visually.

Run it with:

streamlit run ui/app.py

🔄 Automating Data Updates

Add a cron job or GitHub Actions task to run hourly:

python -m app.ingest.fetch_intensity


This keeps your database synchronized with the latest grid forecasts.

🚀 Current Result

✅ Functional API:

Fully operational FastAPI backend

Real data for 17 UK grid regions

Working ingestion and upsert logic

Reliable postcode mapping (via API + fallback)

Computation of “greenest hours”

✅ Database:

177 data points per region (past 24h + forecast 48h)

Region table populated automatically

✅ Ready for next phase:

Add UI layer (Streamlit)

Extend to Europe or other APIs

Add authentication and analytics