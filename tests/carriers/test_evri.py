"""Tests for the Evri carrier adapter."""

import pytest

from myparcel.db.models import ParcelStatus
from myparcel.services.carrier_loader import CarrierLoader


class _Element:
    def __init__(self, text):
        self.text = text

    async def inner_text(self):
        return self.text


class _Page:
    """Just enough of a Playwright page for _extract_status_from_page."""

    def __init__(self, heading, stages=()):
        self.heading = heading
        self.stages = stages

    async def query_selector(self, selector):
        return _Element(self.heading) if selector == "h3" else None

    async def query_selector_all(self, selector):
        return [_Element(f"{s} ticked parcel stage complete") for s in self.stages]


@pytest.fixture
def evri():
    loader = CarrierLoader()
    loader.load_all()
    return loader.get_carrier("evri")


async def test_cookie_banner_is_not_a_status(evri):
    result = await evri._extract_status_from_page(_Page("Manage your preferences"))
    assert not result.success
    assert "bot protection" in result.error


async def test_recognised_status(evri):
    result = await evri._extract_status_from_page(_Page("On its way", ["We've got it"]))
    assert result.success
    assert result.status == ParcelStatus.IN_TRANSIT
    assert len(result.events) == 1
