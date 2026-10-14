"""Smoke tests for the HTML routes."""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from myparcel.db import get_db
from myparcel.db.models import Base, Carrier, Parcel, ParcelStatus, TrackingEvent
from myparcel.main import app


@pytest.fixture
async def client():
    """App client whose requests each get a fresh session, as in production."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        session.add(Carrier(id="relay", name="Relay"))
        parcel = Parcel(tracking_number="RELABCDEFGH1", carrier_id="relay")
        session.add(parcel)
        await session.flush()
        session.add(
            TrackingEvent(
                parcel_id=parcel.id,
                status=ParcelStatus.RECEIVED,
                status_text="Received Your Parcel",
                timestamp=datetime(2026, 10, 10, 16, 28, tzinfo=timezone.utc),
            )
        )
        await session.commit()

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_dashboard_renders(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "RELABCDEFGH1" in response.text
    assert "Relay" in response.text


async def test_delete_parcel_removes_it(client):
    response = await client.post("/parcel/1/delete")
    assert response.status_code == 303

    response = await client.get("/parcel/1")
    assert response.status_code == 404


async def test_parcel_detail_renders(client):
    response = await client.get("/parcel/1")
    assert response.status_code == 200
    assert "Received Your Parcel" in response.text
