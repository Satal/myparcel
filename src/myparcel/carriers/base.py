"""Base classes for carrier adapters."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from myparcel.db.models import ParcelStatus


@dataclass
class TrackingResult:
    """Result from tracking a parcel."""

    success: bool
    status: ParcelStatus = ParcelStatus.UNKNOWN
    status_text: str = ""
    location: str | None = None
    timestamp: datetime | None = None
    expected_delivery: datetime | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    # Direct link to this parcel on the carrier's site, when the carrier resolved one
    # that the tracking number alone can't build (e.g. DPD's parcel code).
    tracking_url: str | None = None


@dataclass
class CarrierConfig:
    """Configuration loaded from carrier.yaml."""

    id: str
    name: str
    website: str
    tracking_url_template: str
    tracking_patterns: list[dict[str, str]]
    status_mapping: dict[str, str]
    enabled: bool = True

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "CarrierConfig":
        """Load carrier configuration from a YAML file."""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        return cls(
            id=data["id"],
            name=data["name"],
            website=data["website"],
            tracking_url_template=data.get("tracking_url_template", ""),
            tracking_patterns=data.get("tracking_patterns", []),
            status_mapping=data.get("status_mapping", {}),
            enabled=data.get("enabled", True),
        )


class BaseCarrier(ABC):
    """Abstract base class for carrier adapters.

    To create a new carrier adapter:
    1. Create a directory in /carriers/ with the carrier ID
    2. Add a carrier.yaml with configuration
    3. Create a tracker.py that subclasses BaseCarrier
    4. Implement the fetch_status method
    """

    def __init__(self, config: CarrierConfig):
        self.config = config
        self._compiled_patterns: list[tuple[re.Pattern[str], str]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile tracking number regex patterns."""
        for pattern in self.config.tracking_patterns:
            try:
                compiled = re.compile(pattern["regex"])
                self._compiled_patterns.append((compiled, pattern.get("description", "")))
            except re.error as e:
                print(f"Invalid regex in {self.config.id}: {pattern['regex']} - {e}")

    def matches_tracking_number(self, tracking_number: str) -> bool:
        """Check if a tracking number matches this carrier's patterns."""
        normalised = tracking_number.strip().upper()
        return any(pattern.match(normalised) for pattern, _ in self._compiled_patterns)

    def match_specificity(self, tracking_number: str) -> int:
        """Score how specifically this carrier matches a tracking number, or -1 if it doesn't.

        The score is the number of literal characters in the best matching pattern, so
        "^REL[A-Z0-9]{8,12}$" (3) outranks a catch-all like "^[A-Z0-9]{10,20}$" (0).
        """
        normalised = tracking_number.strip().upper()
        scores = [
            len(re.sub(r"\[[^\]]*\]|\{[^}]*\}|\\.|[\^$.*+?()|]", "", pattern.pattern))
            for pattern, _ in self._compiled_patterns
            if pattern.match(normalised)
        ]
        return max(scores, default=-1)

    def get_tracking_url(self, tracking_number: str) -> str:
        """Get the URL to track a parcel on the carrier's website."""
        return self.config.tracking_url_template.format(tracking_number=tracking_number)

    def normalise_status(self, carrier_status: str) -> ParcelStatus:
        """Convert carrier-specific status text to normalised ParcelStatus."""
        # Check exact matches first
        carrier_status_lower = carrier_status.lower().strip()

        for pattern, status_str in self.config.status_mapping.items():
            if pattern.lower() in carrier_status_lower:
                try:
                    return ParcelStatus(status_str)
                except ValueError:
                    continue

        # Default fallbacks based on common keywords
        if any(word in carrier_status_lower for word in ["delivered", "signed"]):
            return ParcelStatus.DELIVERED
        if any(word in carrier_status_lower for word in ["out for delivery", "with driver"]):
            return ParcelStatus.OUT_FOR_DELIVERY
        if any(word in carrier_status_lower for word in ["transit", "on way", "hub"]):
            return ParcelStatus.IN_TRANSIT
        if any(word in carrier_status_lower for word in ["received", "collected", "picked up"]):
            return ParcelStatus.RECEIVED
        if any(word in carrier_status_lower for word in ["attempt", "failed", "unable"]):
            return ParcelStatus.FAILED_ATTEMPT
        if any(word in carrier_status_lower for word in ["held", "customs", "waiting"]):
            return ParcelStatus.HELD
        if any(word in carrier_status_lower for word in ["return", "sender"]):
            return ParcelStatus.RETURNED

        return ParcelStatus.UNKNOWN

    @abstractmethod
    async def fetch_status(
        self, tracking_number: str, postcode: str | None = None
    ) -> TrackingResult:
        """Fetch the current status of a parcel.

        This method must be implemented by each carrier adapter.

        Args:
            tracking_number: The tracking number to look up.
            postcode: Delivery postcode, for carriers that need it to show full details.

        Returns:
            TrackingResult with the current status and any events.
        """
        pass

    async def parse_email(self, email_body: str, email_subject: str) -> str | None:
        """Extract a tracking number from an email.

        Override this method in carrier adapters that support email parsing.

        Args:
            email_body: The email body text (HTML or plain text).
            email_subject: The email subject line.

        Returns:
            The extracted tracking number, or None if not found.
        """
        # Default implementation: try to find any matching tracking number
        for pattern, _ in self._compiled_patterns:
            match = pattern.search(email_body)
            if match:
                return match.group(0)
        return None
