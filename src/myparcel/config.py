"""Application configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "MyParcel"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/myparcel.db"

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent.parent
    carriers_dir: Path = base_dir / "src" / "myparcel" / "carriers"
    data_dir: Path = base_dir / "data"

    # Tracking
    refresh_interval_minutes: int = 30
    max_tracking_age_days: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure data directory exists
settings.data_dir.mkdir(parents=True, exist_ok=True)
