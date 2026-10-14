"""Relay tracking implementation."""

import re
from datetime import datetime
from typing import Any

import httpx

from myparcel.carriers.base import BaseCarrier, CarrierConfig, TrackingResult

API_URL = "https://relay-production.relaytechapis.co/v0/customer-portal/shipments/{tracking_number}"


class RelayCarrier(BaseCarrier):
    """Relay carrier adapter.

    Uses the JSON API behind track.relaytech.co. The web page asks for a postcode,
    but the API returns the same tracking data without one.
    """

    def __init__(self, config: CarrierConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            headers={"Accept": "application/json"},
            follow_redirects=True,
            timeout=30.0,
        )

    async def fetch_status(self, tracking_number: str) -> TrackingResult:
        """Fetch tracking status from Relay."""
        tracking_number = tracking_number.strip().upper()

        try:
            response = await self.client.get(API_URL.format(tracking_number=tracking_number))
        except httpx.HTTPError as e:
            return TrackingResult(success=False, error=f"HTTP error: {e}")

        if response.status_code == 404:
            return TrackingResult(success=False, error="No order found for that tracking number")
        if response.status_code != 200:
            return TrackingResult(success=False, error=f"Relay API returned {response.status_code}")

        try:
            return self._parse_shipment(response.json())
        except Exception as e:
            return TrackingResult(success=False, error=f"Could not parse Relay response: {e}")

    def _parse_shipment(self, data: dict[str, Any]) -> TrackingResult:
        """Convert a Relay shipment payload into a TrackingResult."""
        events = [
            {
                "status_text": event.get("status_display_slug") or event["status"],
                "location": None,
                "timestamp": _parse_datetime(event.get("timestamp")),
            }
            for event in data.get("events") or []
        ]
        events.sort(key=lambda e: e["timestamp"] or datetime.min, reverse=True)

        delivery_status = data.get("delivery_status") or ""
        status_text = events[0]["status_text"] if events else delivery_status.replace("_", " ")

        if data.get("objective") == "customer_collection" and data.get("pitstop_name"):
            status_text = f"{status_text} (collect from {data['pitstop_name']})"

        return TrackingResult(
            success=True,
            status=self.normalise_status(delivery_status),
            status_text=status_text,
            location=data.get("pitstop_name"),
            timestamp=events[0]["timestamp"] if events else None,
            expected_delivery=_parse_datetime(
                data.get("estimated_arrival_window_end_at") or data.get("expected_delivery_date")
            ),
            events=events,
        )

    async def parse_email(self, email_body: str, email_subject: str) -> str | None:
        """Extract tracking number from Relay emails."""
        match = re.search(r"\bREL[A-Z0-9]{8,12}\b", email_body)
        return match.group(0) if match else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
