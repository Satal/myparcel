"""Tests for the DPD carrier adapter."""

import httpx
import pytest

from myparcel.db.models import ParcelStatus
from myparcel.services.carrier_loader import CarrierLoader

PARCEL = {
    "parcelCode": "15500000000001*12345",
    "trackingStatusCurrent": "Your parcel is on its way",
    "shipperDetails": {"organisation": "Example Ltd"},
}
EVENTS = [
    {"eventDate": "2026-10-14 06:26:00", "eventLocation": "Example Ltd",
     "eventText": "We've received your order details, and we're expecting your parcel shortly"},
    {"eventDate": "2026-10-15 09:10:00", "eventLocation": "Hinckley Hub",
     "eventText": "Your parcel is on its way"},
]


@pytest.fixture
def dpd():
    loader = CarrierLoader()
    loader.load_all()
    return loader.get_carrier("dpd")


@pytest.fixture
def fake_api(dpd, monkeypatch):
    calls = []

    async def fake_get(url, params=None):
        calls.append((url.removeprefix("https://apis.track.dpd.co.uk/v1"), params))
        request = httpx.Request("GET", url)
        if url.endswith("/reference"):
            body = {"data": [{"parcelCode": "15500000000001*12345"}]}
        elif url.endswith("/parcelevents"):
            body = {"data": EVENTS}
        else:
            body = {"data": PARCEL}
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(dpd.client, "get", fake_get)
    return calls


@pytest.mark.parametrize("number", ["15500000000001*12345", "15500000000001", "1550000000"])
def test_detects_dpd_formats(number):
    loader = CarrierLoader()
    loader.load_all()
    assert loader.detect_carrier(number)[0].config.id == "dpd"


def test_does_not_claim_other_carriers_numbers():
    loader = CarrierLoader()
    loader.load_all()
    assert "dpd" not in [c.config.id for c in loader.detect_carrier("RELR2WTNJG1N")]


async def test_parcel_code_is_fetched_directly(dpd, fake_api):
    result = await dpd.fetch_status("15500000000001*12345")

    assert result.success
    assert [path for path, _ in fake_api] == [
        "/parcels/15500000000001*12345",
        "/parcels/15500000000001*12345/parcelevents",
    ]


async def test_parcel_number_is_resolved_with_postcode(dpd, fake_api):
    result = await dpd.fetch_status("1550 0000 0000 01", postcode="AB1 2CD")

    assert result.success
    assert fake_api[0] == (
        "/reference",
        {"referenceNumber": "15500000000001", "origin": "PRTK", "postcode": "AB1 2CD"},
    )
    assert fake_api[1][0] == "/parcels/15500000000001*12345"
    assert result.tracking_url == "https://track.dpd.co.uk/parcels/15500000000001*12345"


async def test_parse(dpd, fake_api):
    result = await dpd.fetch_status("15500000000001*12345")

    assert result.status == ParcelStatus.IN_TRANSIT
    assert result.status_text == "Your parcel is on its way"
    assert result.location == "Hinckley Hub"
    assert result.events[0]["status_text"] == "Your parcel is on its way"
    assert result.events[0]["timestamp"].utcoffset() is not None


async def test_unknown_reference(dpd, monkeypatch):
    async def fake_get(url, params=None):
        return httpx.Response(200, json={"data": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(dpd.client, "get", fake_get)
    result = await dpd.fetch_status("15599999999999")

    assert not result.success
    assert "No DPD parcel" in result.error


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("We've received your order details, and we're expecting your parcel shortly", ParcelStatus.PENDING),
        ("We have your parcel", ParcelStatus.RECEIVED),
        ("Your parcel is on its way", ParcelStatus.IN_TRANSIT),
        ("Out for delivery", ParcelStatus.OUT_FOR_DELIVERY),
        (
            "Your Atlantic Shopping order will be delivered today by Muhammad, your DPD driver, "
            "between 14:58 and 15:58. Your one hour timeslot can't be changed",
            ParcelStatus.OUT_FOR_DELIVERY,
        ),
        ("Your parcel will be with you today  between 14:58 and 15:58", ParcelStatus.OUT_FOR_DELIVERY),
        ("Your parcel will be delivered on Monday", ParcelStatus.IN_TRANSIT),
        ("Your parcel has been delivered", ParcelStatus.DELIVERED),
    ],
)
def test_status_mapping(dpd, text, expected):
    assert dpd.normalise_status(text) == expected
