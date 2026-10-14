"""DPD UK tracking implementation."""

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from myparcel.carriers.base import BaseCarrier, CarrierConfig, TrackingResult

API_BASE = "https://apis.track.dpd.co.uk/v1"
UK_TIME = ZoneInfo("Europe/London")
PARCEL_CODE = re.compile(r"^\d+\*\d{5}$")


class DPDCarrier(BaseCarrier):
    """DPD UK carrier adapter.

    Uses the JSON API behind track.dpd.co.uk. The API wants a parcel code
    ("15502055803975*21472"); a parcel or consignment number is resolved to one
    through the reference search first. Postcode-verified details sit behind a
    reCAPTCHA login, so only the public status and event history are fetched.
    """

    def __init__(self, config: CarrierConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            headers={"Accept": "application/json"},
            follow_redirects=True,
            timeout=30.0,
        )

    def get_tracking_url(self, tracking_number: str) -> str:
        """Link straight to the parcel when we have its code, otherwise to the search."""
        tracking_number = tracking_number.strip()
        if PARCEL_CODE.match(tracking_number):
            return f"https://track.dpd.co.uk/parcels/{tracking_number}"
        return f"https://track.dpd.co.uk/search?reference={tracking_number}"

    async def fetch_status(
        self, tracking_number: str, postcode: str | None = None
    ) -> TrackingResult:
        """Fetch tracking status from DPD."""
        reference = re.sub(r"\s+", "", tracking_number)

        try:
            parcel_code = reference if PARCEL_CODE.match(reference) else None
            if parcel_code is None:
                parcel_code = await self._find_parcel_code(reference, postcode)
            if parcel_code is None:
                return TrackingResult(success=False, error="No DPD parcel found for that number")

            parcel = await self._get(f"/parcels/{parcel_code}")
            events = await self._get(f"/parcels/{parcel_code}/parcelevents")
        except httpx.HTTPStatusError as e:
            return TrackingResult(
                success=False, error=f"DPD API returned {e.response.status_code}"
            )
        except httpx.HTTPError as e:
            return TrackingResult(success=False, error=f"HTTP error: {e}")

        try:
            result = self._parse(parcel.get("data") or {}, events.get("data") or [])
        except Exception as e:
            return TrackingResult(success=False, error=f"Could not parse DPD response: {e}")
        result.tracking_url = self.get_tracking_url(parcel_code)
        return result

    async def _find_parcel_code(self, reference: str, postcode: str | None) -> str | None:
        params = {"referenceNumber": reference, "origin": "PRTK"}
        if postcode:
            params["postcode"] = postcode
        try:
            results = (await self._get("/reference", params=params)).get("data") or []
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 404):
                return None
            raise
        return results[0].get("parcelCode") if results else None

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        response = await self.client.get(f"{API_BASE}{path}", params=params)
        response.raise_for_status()
        return response.json()

    def _parse(self, parcel: dict[str, Any], raw_events: list[dict[str, Any]]) -> TrackingResult:
        """Convert DPD parcel and event payloads into a TrackingResult."""
        events = [
            {
                "status_text": event.get("eventText") or "",
                "location": event.get("eventLocation"),
                "timestamp": _parse_datetime(event.get("eventDate")),
            }
            for event in raw_events
        ]
        events.sort(key=lambda e: e["timestamp"] or datetime.min.replace(tzinfo=UK_TIME), reverse=True)

        status_text = parcel.get("trackingStatusCurrent") or (
            events[0]["status_text"] if events else ""
        )
        if not status_text:
            return TrackingResult(success=False, error="DPD returned no status")

        return TrackingResult(
            success=True,
            status=self.normalise_status(status_text),
            status_text=status_text,
            location=events[0]["location"] if events else None,
            timestamp=events[0]["timestamp"] if events else None,
            events=events,
        )

    async def parse_email(self, email_body: str, email_subject: str) -> str | None:
        """Extract tracking number from DPD emails."""
        if "dpd" not in email_subject.lower() and "dpd" not in email_body.lower():
            return None

        match = re.search(r"\b\d{14}\*\d{5}\b|\b[0-9]{14,16}\b", email_body)
        return match.group(0) if match else None


def _parse_datetime(value: str | None) -> datetime | None:
    """DPD event dates are UK local time without an offset."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=UK_TIME)
    except ValueError:
        return None
