from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router

def create_app():
    app = FastAPI(title="EnergyTrace API", version="0.1.0")

    # Allow your deployed Streamlit site + local dev UI
    ALLOWED_ORIGINS = [
        "https://energytrace.streamlit.app",  # Streamlit Cloud app
        "http://localhost:8501",              # local Streamlit
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include all API routes
    app.include_router(api_router, prefix="/api")

    return app

app = create_app()
