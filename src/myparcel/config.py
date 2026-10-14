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
    # Run from the project root (or /app in Docker); carriers ship inside the package
    base_dir: Path = Path.cwd()
    carriers_dir: Path = Path(__file__).parent / "carriers"
    data_dir: Path = base_dir / "data"

    # Login for the web UI; leave either unset to run without one (local use only)
    auth_username: str | None = None
    auth_password: str | None = None

    # Carriers
    # Used for parcels added without a postcode (e.g. Relay home deliveries 404 without one)
    default_postcode: str | None = None
    royal_mail_client_id: str = ""
    royal_mail_client_secret: str = ""

    # Tracking; active parcels are refreshed in the background, 0 disables it
    refresh_interval_minutes: int = 30
    max_tracking_age_days: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure data directory exists
settings.data_dir.mkdir(parents=True, exist_ok=True)
