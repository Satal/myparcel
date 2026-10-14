"""Database connection and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from myparcel.config import settings
from myparcel.db.models import Base

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize the database, creating all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


# Columns added to parcels after release, with their DDL type
_PARCEL_COLUMNS = {
    "postcode": "VARCHAR(16)",
    "tracking_url": "VARCHAR(512)",
}


def _add_missing_columns(conn) -> None:
    """Add columns introduced after a database was created (create_all skips existing tables)."""
    columns = {column["name"] for column in inspect(conn).get_columns("parcels")}
    for name, ddl_type in _PARCEL_COLUMNS.items():
        if name not in columns:
            conn.execute(text(f"ALTER TABLE parcels ADD COLUMN {name} {ddl_type}"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
