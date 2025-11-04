from pydantic import BaseModel
from dotenv import load_dotenv
import os
load_dotenv()
class Settings(BaseModel):
    env: str = os.getenv("ENV", "dev")
    tz: str = os.getenv("TZ", "Europe/London")
    database_url: str = os.getenv("DATABASE_URL")
    carbon_base: str = os.getenv("CARBON_INTENSITY_BASE", "https://api.carbonintensity.org.uk")

settings = Settings()
