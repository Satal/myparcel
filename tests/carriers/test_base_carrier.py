"""Tests for base carrier functionality."""

import pytest

from myparcel.carriers.base import CarrierConfig
from myparcel.db.models import ParcelStatus


class TestStatusNormalisation:
    """Test status normalisation across carriers."""

    @pytest.fixture
    def config(self):
        """Create a test carrier config."""
        return CarrierConfig(
            id="test-carrier",
            name="Test Carrier",
            website="https://test.com",
            tracking_url_template="https://test.com/track/{tracking_number}",
            tracking_patterns=[{"regex": "^TEST[0-9]+$", "description": "Test format"}],
            status_mapping={
                "item delivered": "delivered",
                "out for delivery": "out_for_delivery",
                "in transit": "in_transit",
            },
        )

    def test_exact_status_match(self, config):
        """Test exact status matching."""
        from myparcel.carriers.base import BaseCarrier

        class TestCarrier(BaseCarrier):
            async def fetch_status(self, tracking_number):
                pass

        carrier = TestCarrier(config)

        assert carrier.normalise_status("Item Delivered") == ParcelStatus.DELIVERED
        assert carrier.normalise_status("OUT FOR DELIVERY") == ParcelStatus.OUT_FOR_DELIVERY
        assert carrier.normalise_status("in transit to hub") == ParcelStatus.IN_TRANSIT

    def test_fallback_status_detection(self, config):
        """Test fallback status detection from keywords."""
        from myparcel.carriers.base import BaseCarrier

        class TestCarrier(BaseCarrier):
            async def fetch_status(self, tracking_number):
                pass

        carrier = TestCarrier(config)

        # These aren't in the mapping but should be detected by keywords
        assert carrier.normalise_status("Package signed for") == ParcelStatus.DELIVERED
        assert carrier.normalise_status("With driver") == ParcelStatus.OUT_FOR_DELIVERY
        assert carrier.normalise_status("At customs") == ParcelStatus.HELD

    def test_unknown_status(self, config):
        """Test that unknown statuses return UNKNOWN."""
        from myparcel.carriers.base import BaseCarrier

        class TestCarrier(BaseCarrier):
            async def fetch_status(self, tracking_number):
                pass

        carrier = TestCarrier(config)

        assert carrier.normalise_status("Something random") == ParcelStatus.UNKNOWN
