"""Main FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from myparcel.api import router
from myparcel.config import settings
from myparcel.db import init_db
from myparcel.services.carrier_loader import carrier_loader


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print(f"Starting {settings.app_name}...")
    await init_db()
    carrier_loader.load_all()
    print(f"Loaded {len(carrier_loader.list_carriers())} carriers")

    yield

    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="Self-hosted parcel tracking aggregator",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "myparcel.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
