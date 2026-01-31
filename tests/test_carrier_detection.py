"""Tests for carrier detection."""

import pytest

from myparcel.services.carrier_loader import CarrierLoader


class TestCarrierDetection:
    """Test carrier auto-detection from tracking numbers."""

    @pytest.fixture
    def loader(self):
        """Create a carrier loader."""
        loader = CarrierLoader()
        loader.load_all()
        return loader

    def test_detect_royal_mail_international(self, loader):
        """Test detection of Royal Mail international format."""
        matches = loader.detect_carrier("RR123456789GB")
        assert len(matches) > 0
        carrier_ids = [m.config.id for m in matches]
        assert "royal-mail" in carrier_ids

    def test_detect_royal_mail_numeric(self, loader):
        """Test detection of Royal Mail numeric format."""
        matches = loader.detect_carrier("1234567890123456")
        assert len(matches) > 0
        # This format may match multiple carriers

    def test_detect_dpd(self, loader):
        """Test detection of DPD format."""
        matches = loader.detect_carrier("123456789012345")
        assert len(matches) > 0
        carrier_ids = [m.config.id for m in matches]
        assert "dpd" in carrier_ids

    def test_detect_evri(self, loader):
        """Test detection of Evri format."""
        matches = loader.detect_carrier("H123456789012345")
        assert len(matches) > 0
        carrier_ids = [m.config.id for m in matches]
        assert "evri" in carrier_ids

    def test_no_match(self, loader):
        """Test that invalid tracking numbers return no matches."""
        matches = loader.detect_carrier("INVALID")
        assert len(matches) == 0

    def test_case_insensitive(self, loader):
        """Test that detection is case-insensitive."""
        upper = loader.detect_carrier("RR123456789GB")
        lower = loader.detect_carrier("rr123456789gb")
        assert len(upper) == len(lower)
