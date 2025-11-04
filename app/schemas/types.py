from pydantic import BaseModel
from datetime import datetime

class RegionOut(BaseModel):
    id: int
    name: str
    gsp_code: str
    dno_name: str | None = None

class IntensityPoint(BaseModel):
    ts_utc: datetime
    ci_g_per_kwh: float
    renewable_share_pct: float | None = None
    source: str
