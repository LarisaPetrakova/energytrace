from fastapi import FastAPI
from app.api.routes import router as api_router

def create_app():
    app = FastAPI(title="EnergyTrace API", version="0.1.0")
    app.include_router(api_router, prefix="/api")
    return app

app = create_app()
