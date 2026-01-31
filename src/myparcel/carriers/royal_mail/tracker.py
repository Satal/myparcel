"""Royal Mail tracking implementation.

Requires API credentials from the Royal Mail Developer Portal:
https://developer.royalmail.net/

Set these environment variables:
- ROYAL_MAIL_CLIENT_ID: Your X-IBM-Client-Id
- ROYAL_MAIL_CLIENT_SECRET: Your X-IBM-Client-Secret
"""

import os
import re
from datetime import datetime, timezone

import httpx

from myparcel.carriers.base import BaseCarrier, CarrierConfig, TrackingResult


class RoyalMailCarrier(BaseCarrier):
    """Royal Mail carrier adapter.

    Uses the Royal Mail Tracking API v2:
    https://developer.royalmail.net/product/175625/api/76888

    Requires API credentials - register at developer.royalmail.net
    """

    # Royal Mail Tracking API v2 base URL
    API_BASE = "https://api.royalmail.net/mailpieces/v2"

    def __init__(self, config: CarrierConfig):
        super().__init__(config)

        # Load API credentials from environment
        self.client_id = os.getenv("ROYAL_MAIL_CLIENT_ID", "")
        self.client_secret = os.getenv("ROYAL_MAIL_CLIENT_SECRET", "")

        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "MyParcel/1.0",
                "Accept": "application/json",
                "Accept-Language": "en-GB",
            },
            timeout=30.0,
        )

    def _has_credentials(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.client_id and self.client_secret)

    async def fetch_status(self, tracking_number: str) -> TrackingResult:
        """Fetch tracking status from Royal Mail API."""
        tracking_number = tracking_number.strip().upper()

        if not self._has_credentials():
            return TrackingResult(
                success=False,
                error=(
                    "Royal Mail API credentials not configured. "
                    "Set ROYAL_MAIL_CLIENT_ID and ROYAL_MAIL_CLIENT_SECRET environment variables. "
                    "Get credentials from https://developer.royalmail.net/"
                ),
            )

        try:
            return await self._fetch_from_api(tracking_number)
        except Exception as e:
            return TrackingResult(success=False, error=f"Error: {e}")

    async def _fetch_from_api(self, tracking_number: str) -> TrackingResult:
        """Fetch tracking data from the Royal Mail API."""
        # Use the events endpoint for full tracking history
        url = f"{self.API_BASE}/{tracking_number}/events"

        headers = {
            "X-IBM-Client-Id": self.client_id,
            "X-IBM-Client-Secret": self.client_secret,
            "X-Accept-RMG-Terms": "yes",
        }

        response = await self.client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return self._parse_api_response(data)
        elif response.status_code == 404:
            return TrackingResult(
                success=False,
                error="Tracking number not found",
            )
        elif response.status_code == 401:
            return TrackingResult(
                success=False,
                error="Invalid API credentials. Check ROYAL_MAIL_CLIENT_ID and ROYAL_MAIL_CLIENT_SECRET.",
            )
        elif response.status_code == 429:
            return TrackingResult(
                success=False,
                error="Rate limit exceeded. Try again later.",
            )
        else:
            return TrackingResult(
                success=False,
                error=f"API error: {response.status_code} - {response.text[:200]}",
            )

    def _parse_api_response(self, data: dict) -> TrackingResult:
        """Parse Royal Mail API v2 response."""
        try:
            # The response structure for /events endpoint
            mail_pieces = data.get("mailPieces", [])
            if not mail_pieces:
                return TrackingResult(success=False, error="No tracking data found")

            mailpiece = mail_pieces[0]

            # Get summary info
            summary = mailpiece.get("summary", {})
            status_text = summary.get("statusDescription", "Unknown")
            status = self.normalise_status(status_text)

            # Parse events
            events_data = mailpiece.get("events", [])
            events = []

            for event in events_data:
                event_time = event.get("eventDateTime")
                timestamp = datetime.now(timezone.utc)

                if event_time:
                    try:
                        # Handle ISO format with Z suffix
                        if event_time.endswith("Z"):
                            event_time = event_time[:-1] + "+00:00"
                        timestamp = datetime.fromisoformat(event_time)
                    except ValueError:
                        pass

                events.append({
                    "status_text": event.get("eventName", ""),
                    "location": event.get("locationName", ""),
                    "timestamp": timestamp,
                })

            # Get estimated delivery if available
            expected_delivery = None
            estimated = summary.get("estimatedDelivery", {})
            if estimated and estimated.get("date"):
                try:
                    expected_delivery = datetime.fromisoformat(estimated["date"])
                except ValueError:
                    pass

            # Get latest event info
            latest_location = events[0].get("location") if events else None
            latest_timestamp = events[0].get("timestamp") if events else None

            return TrackingResult(
                success=True,
                status=status,
                status_text=status_text,
                location=latest_location,
                timestamp=latest_timestamp,
                expected_delivery=expected_delivery,
                events=events,
            )

        except Exception as e:
            return TrackingResult(success=False, error=f"Error parsing response: {e}")

    async def parse_email(self, email_body: str, email_subject: str) -> str | None:
        """Extract tracking number from Royal Mail emails."""
        # Check if this looks like a Royal Mail email
        combined = f"{email_subject} {email_body}".lower()
        if "royal mail" not in combined:
            return None

        # Try to find tracking numbers in the email
        patterns = [
            r"[A-Z]{2}[0-9]{9}GB",  # International format (e.g., XQ779509088GB)
            r"[A-Z]{2}[0-9]{9}[A-Z]{2}",  # Standard format
            r"[0-9]{16,20}",  # Numeric format
        ]

        for pattern in patterns:
            match = re.search(pattern, email_body.upper())
            if match:
                return match.group(0)

        return None
