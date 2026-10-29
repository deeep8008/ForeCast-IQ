"""
ForecastIQ Backend Configuration Settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE_PATH = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "ForecastIQ Backend"
    API_V1_STR: str = "/api"
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]
    MAX_UPLOAD_SIZE_BYTES: int = 150 * 1024 * 1024  # 150 MB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "forecastiq"
    MONGODB_ENABLED: bool = True
    AUTH_SESSION_TTL_HOURS: int = 24 * 7  # 7 days
    AUTH_COOKIE_NAME: str = "forecastiq_session"
    AUTH_COOKIE_SECURE: bool = False  # Set True in production HTTPS
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=(str(ENV_FILE_PATH), ".env"),
        extra="ignore"
    )


settings = Settings()
