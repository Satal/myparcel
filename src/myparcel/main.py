"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from myparcel.api import auth_router, router
from myparcel.api.auth import auth_enabled, require_login
from myparcel.config import settings
from myparcel.db import init_db
from myparcel.db.database import async_session_maker
from myparcel.services.carrier_loader import carrier_loader
from myparcel.services.tracker import TrackerService

logger = logging.getLogger("myparcel")


async def refresh_active_parcels() -> None:
    """Background job: refresh every parcel that hasn't been delivered."""
    async with async_session_maker() as db:
        results = await TrackerService(db).refresh_all_active()
    failed = {pid: r.error for pid, r in results.items() if not r.success}
    logger.info("Refreshed %d parcels, %d failed", len(results), len(failed))
    for parcel_id, error in failed.items():
        logger.warning("Parcel %d refresh failed: %s", parcel_id, error)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("Starting %s", settings.app_name)
    await init_db()
    carrier_loader.load_all()
    logger.info("Loaded %d carriers", len(carrier_loader.list_carriers()))
    async with async_session_maker() as db:
        await TrackerService(db).ensure_carriers_exist()
    if not auth_enabled():
        logger.warning("AUTH_USERNAME/AUTH_PASSWORD not set: the web UI has no login")

    scheduler = AsyncIOScheduler()
    if settings.refresh_interval_minutes > 0:
        scheduler.add_job(
            refresh_active_parcels,
            "interval",
            minutes=settings.refresh_interval_minutes,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Shutting down")


app = FastAPI(
    title=settings.app_name,
    description="Self-hosted parcel tracking aggregator",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware added last runs first, so the session is loaded before the login check
app.middleware("http")(require_login)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="myparcel_session",
    max_age=30 * 24 * 3600,
    same_site="lax",
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routes
app.include_router(auth_router)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "myparcel.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
