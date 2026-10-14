"""Tests for the Relay carrier adapter."""

import pytest

from myparcel.db.models import ParcelStatus
from myparcel.services.carrier_loader import CarrierLoader

SHIPMENT = {
    "tracking_number": "RELABCDEFGH1",
    "delivery_status": "driver_collected_parcel_from_pitstop",
    "objective": "customer_collection",
    "pitstop_name": "Corner Shop",
    "estimated_arrival_window_end_at": None,
    "expected_delivery_date": None,
    "events": [
        {
            "status": "order_created",
            "status_display_slug": "Awaiting your parcel",
            "timestamp": "2026-10-04T08:16:42.828612+00:00",
        },
        {
            "status": "received_at_pitstop",
            "status_display_slug": "Received Your Parcel",
            "timestamp": "2026-10-10T16:28:00+00:00",
        },
        {
            "status": "driver_collected_parcel_from_pitstop",
            "status_display_slug": "Courier Collected Your Parcel",
            "timestamp": "2026-10-11T08:44:00+00:00",
        },
    ],
}


@pytest.fixture
def loader():
    loader = CarrierLoader()
    loader.load_all()
    return loader


@pytest.fixture
def relay(loader):
    return loader.get_carrier("relay")


def test_relay_number_detects_relay_first(loader):
    """The catch-all DPD pattern also matches, but Relay's prefix is more specific."""
    matches = loader.detect_carrier("RELR2WTNJG1N")
    assert matches[0].config.id == "relay"


def test_royal_mail_international_detects_royal_mail_first(loader):
    matches = loader.detect_carrier("RR123456789GB")
    assert matches[0].config.id == "royal-mail"


def test_parse_shipment(relay):
    result = relay._parse_shipment(SHIPMENT)

    assert result.success
    assert result.status == ParcelStatus.IN_TRANSIT
    assert result.status_text == "Courier Collected Your Parcel (collect from Corner Shop)"
    assert result.location == "Corner Shop"
    assert [e["status_text"] for e in result.events][0] == "Courier Collected Your Parcel"
    assert len(result.events) == 3


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("order_created", ParcelStatus.PENDING),
        ("awaiting_parcel_drop_off", ParcelStatus.PENDING),
        ("received_at_pitstop", ParcelStatus.RECEIVED),
        ("driver_collected_parcel_from_pitstop", ParcelStatus.IN_TRANSIT),
        ("out_for_delivery", ParcelStatus.OUT_FOR_DELIVERY),
        ("awaiting_customer_collection", ParcelStatus.HELD),
        ("collected_by_customer", ParcelStatus.DELIVERED),
        ("home_delivery_delivered", ParcelStatus.DELIVERED),
        ("delivery_failed_will_reattempt", ParcelStatus.FAILED_ATTEMPT),
        ("return_to_sender_pending", ParcelStatus.RETURNED),
        ("lost_in_transit", ParcelStatus.EXCEPTION),
    ],
)
def test_status_mapping(relay, code, expected):
    assert relay.normalise_status(code) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Awaiting your Vinted parcel", ParcelStatus.PENDING),
        ("Received Your Parcel", ParcelStatus.RECEIVED),
        ("Courier Collected Your Parcel", ParcelStatus.IN_TRANSIT),
    ],
)
def test_event_text_mapping(relay, text, expected):
    assert relay.normalise_status(text) == expected
