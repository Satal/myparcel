"""Tests for per-parcel postcodes."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from myparcel.carriers.base import TrackingResult
from myparcel.db import database
from myparcel.db.models import Carrier, Parcel
from myparcel.services.carrier_loader import carrier_loader
from myparcel.services.tracker import TrackerService


class _RecordingCarrier:
    def __init__(self):
        self.postcodes = []

    async def fetch_status(self, tracking_number, postcode=None):
        self.postcodes.append(postcode)
        return TrackingResult(success=False, error="stub")


@pytest.fixture
def recording_carrier(monkeypatch):
    carrier = _RecordingCarrier()
    monkeypatch.setattr(carrier_loader, "get_carrier", lambda carrier_id: carrier)
    return carrier


@pytest.mark.parametrize(
    ("parcel_postcode", "default", "expected"),
    [
        ("AB1 2CD", "ZZ9 9ZZ", "AB1 2CD"),
        (None, "ZZ9 9ZZ", "ZZ9 9ZZ"),
        (None, None, None),
    ],
)
async def test_refresh_passes_parcel_postcode_or_default(
    db_session, recording_carrier, monkeypatch, parcel_postcode, default, expected
):
    monkeypatch.setattr("myparcel.services.tracker.settings.default_postcode", default)
    db_session.add(Carrier(id="relay", name="Relay"))
    parcel = Parcel(tracking_number="RELABCDEFGH1", carrier_id="relay", postcode=parcel_postcode)
    db_session.add(parcel)
    await db_session.commit()

    await TrackerService(db_session).refresh_parcel(parcel)

    assert recording_carrier.postcodes == [expected]


async def test_add_parcel_normalises_postcode(db_session):
    db_session.add(Carrier(id="relay", name="Relay"))
    await db_session.commit()

    parcel = await TrackerService(db_session).add_parcel(
        "RELABCDEFGH1", carrier_id="relay", postcode=" rm2 5uu "
    )

    assert parcel.postcode == "RM2 5UU"


async def test_init_db_adds_new_columns_to_existing_database(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'old.db'}")
    async with engine.begin() as conn:
        await conn.execute(
            text("CREATE TABLE parcels (id INTEGER PRIMARY KEY, tracking_number VARCHAR(100))")
        )
    monkeypatch.setattr(database, "engine", engine)

    await database.init_db()
    await database.init_db()  # idempotent

    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("parcels")}
        )
    await engine.dispose()
    assert {"postcode", "tracking_url"} <= columns
