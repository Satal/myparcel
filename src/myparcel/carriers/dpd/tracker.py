"""DPD UK tracking implementation."""

import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from myparcel.carriers.base import BaseCarrier, CarrierConfig, TrackingResult


class DPDCarrier(BaseCarrier):
    """DPD UK carrier adapter."""

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
        """Fetch tracking status from DPD."""
        tracking_number = tracking_number.strip()

        try:
            # DPD tracking page
            url = f"https://www.dpd.co.uk/tracking/trackingSearch.do?parcelCode={tracking_number}"
            response = await self.client.get(url)

            if response.status_code == 200:
                return self._parse_tracking_page(response.text)

        except httpx.HTTPError as e:
            return TrackingResult(success=False, error=f"HTTP error: {e}")
        except Exception as e:
            return TrackingResult(success=False, error=f"Error: {e}")

        return TrackingResult(success=False, error="Could not retrieve tracking data")

    def _parse_tracking_page(self, html: str) -> TrackingResult:
        """Parse DPD tracking page HTML."""
        soup = BeautifulSoup(html, "lxml")

        # Look for tracking status
        # DPD's page structure may vary - this is a best-effort approach
        events = []

        # Try to find the tracking timeline/history
        timeline = soup.find(class_=re.compile(r"timeline|tracking|history", re.I))
        if timeline:
            items = timeline.find_all(class_=re.compile(r"item|event|step", re.I))
            for item in items:
                text = item.get_text(strip=True)
                if text:
                    events.append({
                        "status_text": text,
                        "location": None,
                        "timestamp": datetime.now(timezone.utc),
                    })

        # Try to find current status
        status_elem = soup.find(class_=re.compile(r"status|current", re.I))
        status_text = status_elem.get_text(strip=True) if status_elem else "Unknown"

        if events or status_text != "Unknown":
            return TrackingResult(
                success=True,
                status=self.normalise_status(status_text),
                status_text=status_text,
                events=events,
            )

        # Check for error messages
        error_elem = soup.find(class_=re.compile(r"error|not-found", re.I))
        if error_elem:
            return TrackingResult(
                success=False,
                error=error_elem.get_text(strip=True),
            )

        return TrackingResult(
            success=False,
            error="Could not parse tracking page",
        )

    async def parse_email(self, email_body: str, email_subject: str) -> str | None:
        """Extract tracking number from DPD emails."""
        if "dpd" not in email_subject.lower() and "dpd" not in email_body.lower():
            return None

        # Look for 14-16 digit tracking numbers
        match = re.search(r"\b[0-9]{14,16}\b", email_body)
        if match:
            return match.group(0)

        return None
