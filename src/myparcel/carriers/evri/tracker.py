"""Evri tracking implementation."""

import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from myparcel.carriers.base import BaseCarrier, CarrierConfig, TrackingResult


class EvriCarrier(BaseCarrier):
    """Evri (formerly Hermes) carrier adapter."""

    def __init__(self, config: CarrierConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
            },
            follow_redirects=True,
            timeout=30.0,
        )

    async def fetch_status(self, tracking_number: str) -> TrackingResult:
        """Fetch tracking status from Evri."""
        tracking_number = tracking_number.strip().upper()

        try:
            # Evri tracking page
            url = f"https://www.evri.com/track-a-parcel/{tracking_number}"
            response = await self.client.get(url)

            if response.status_code == 200:
                return self._parse_tracking_page(response.text)

        except httpx.HTTPError as e:
            return TrackingResult(success=False, error=f"HTTP error: {e}")
        except Exception as e:
            return TrackingResult(success=False, error=f"Error: {e}")

        return TrackingResult(success=False, error="Could not retrieve tracking data")

    def _parse_tracking_page(self, html: str) -> TrackingResult:
        """Parse Evri tracking page HTML."""
        soup = BeautifulSoup(html, "lxml")
        events = []

        # Try to find tracking events
        # Evri's page structure varies - this is best-effort
        tracking_section = soup.find(class_=re.compile(r"tracking|timeline|history", re.I))

        if tracking_section:
            items = tracking_section.find_all(
                class_=re.compile(r"event|step|item|status", re.I)
            )
            for item in items:
                text = item.get_text(strip=True)
                if text and len(text) > 5:  # Filter out empty/tiny items
                    events.append({
                        "status_text": text,
                        "location": None,
                        "timestamp": datetime.now(timezone.utc),
                    })

        # Try to find current status
        status_elem = soup.find(class_=re.compile(r"current-status|main-status", re.I))
        if not status_elem:
            status_elem = soup.find("h1", class_=re.compile(r"status", re.I))

        status_text = status_elem.get_text(strip=True) if status_elem else "Unknown"

        if events or status_text != "Unknown":
            return TrackingResult(
                success=True,
                status=self.normalise_status(status_text),
                status_text=status_text,
                events=events,
            )

        # Check for not found
        if "not found" in html.lower() or "no results" in html.lower():
            return TrackingResult(
                success=False,
                error="Tracking number not found",
            )

        return TrackingResult(
            success=False,
            error="Could not parse tracking page",
        )

    async def parse_email(self, email_body: str, email_subject: str) -> str | None:
        """Extract tracking number from Evri/Hermes emails."""
        body_lower = email_body.lower()
        subject_lower = email_subject.lower()

        if not any(x in subject_lower or x in body_lower for x in ["evri", "hermes"]):
            return None

        # Look for Evri tracking patterns
        patterns = [
            r"[A-Z0-9]{16}",
            r"H[0-9]{15}",
        ]

        for pattern in patterns:
            match = re.search(pattern, email_body.upper())
            if match:
                return match.group(0)

        return None
