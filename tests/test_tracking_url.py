"""Tests for carrier-resolved tracking links."""

from myparcel.carriers.base import TrackingResult
from myparcel.db.models import Carrier, Parcel
from myparcel.services.carrier_loader import carrier_loader
from myparcel.services.tracker import TrackerService


class _StubCarrier:
    def __init__(self, tracking_url):
        self.tracking_url = tracking_url

    async def fetch_status(self, tracking_number, postcode=None):
        return TrackingResult(success=True, status_text="On its way", tracking_url=self.tracking_url)

    def normalise_status(self, text):
        return None


async def test_refresh_stores_resolved_url_and_keeps_it(db_session, monkeypatch):
    db_session.add(Carrier(id="dpd", name="DPD"))
    parcel = Parcel(tracking_number="15500000000001", carrier_id="dpd")
    db_session.add(parcel)
    await db_session.commit()
    service = TrackerService(db_session)

    url = "https://track.dpd.co.uk/parcels/15500000000001*12345"
    monkeypatch.setattr(carrier_loader, "get_carrier", lambda _: _StubCarrier(url))
    await service.refresh_parcel(parcel)
    assert parcel.tracking_url == url

    # A later refresh that resolves nothing doesn't wipe the link
    monkeypatch.setattr(carrier_loader, "get_carrier", lambda _: _StubCarrier(None))
    await service.refresh_parcel(parcel)
    assert parcel.tracking_url == url
