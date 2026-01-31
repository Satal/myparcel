"""Royal Mail tracking implementation."""

import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from myparcel.carriers.base import BaseCarrier, CarrierConfig, TrackingResult
from myparcel.db.models import ParcelStatus


class RoyalMailCarrier(BaseCarrier):
    """Royal Mail carrier adapter.

    Note: Royal Mail's tracking page is JavaScript-heavy. This implementation
    attempts to fetch data from their API endpoints. If this stops working,
    it may need to be updated to use browser automation.
    """

    # Royal Mail's tracking API endpoint (may change)
    API_URL = "https://www.royalmail.com/track-your-item/tracking-api"

    def __init__(self, config: CarrierConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-GB,en;q=0.9",
            },
            follow_redirects=True,
            timeout=30.0,
        )

    async def fetch_status(self, tracking_number: str) -> TrackingResult:
        """Fetch tracking status from Royal Mail."""
        tracking_number = tracking_number.strip().upper()

        # Try the direct tracking page first
        try:
            result = await self._fetch_from_tracking_page(tracking_number)
            if result.success:
                return result
        except Exception as e:
            print(f"Error fetching from tracking page: {e}")

        # Fallback: return error
        return TrackingResult(
            success=False,
            error="Unable to fetch tracking information from Royal Mail",
        )

    async def _fetch_from_tracking_page(self, tracking_number: str) -> TrackingResult:
        """Attempt to scrape the tracking page."""
        url = f"https://www.royalmail.com/track-your-item#/tracking-results/{tracking_number}"

        # Royal Mail's tracking is heavily JS-based, so we need to hit their API
        # This is a simplified approach - the actual API may require additional headers
        api_url = f"https://api.royalmail.net/mailpieces/v3.3/summary?mailPieceId={tracking_number}"

        try:
            response = await self.client.get(
                api_url,
                headers={
                    "Accept": "application/json",
                    "x-ibm-client-id": "a]ePT7~RW]dno=^=r=f+Y@qDJLyL)MHDvlNRdc:j",  # Public client ID
                    "x-ibm-client-secret": "V^dXgD~]dBfyW)p@=Q@)giTNJryA]rANLIrJcKw[QafoMHdt]Bq]NrRPt[WjgF)c",  # Public secret
                },
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_api_response(data)

        except httpx.HTTPError as e:
            print(f"HTTP error: {e}")
        except Exception as e:
            print(f"Error parsing response: {e}")

        # If API fails, try scraping the HTML page
        # Note: This is a fallback and may not work well due to JS rendering
        try:
            page_url = f"https://www.royalmail.com/track-your-item#/tracking-results/{tracking_number}"
            response = await self.client.get(page_url)
            if response.status_code == 200:
                return self._parse_html_response(response.text, tracking_number)
        except Exception as e:
            print(f"Error scraping HTML: {e}")

        return TrackingResult(success=False, error="Could not retrieve tracking data")

    def _parse_api_response(self, data: dict) -> TrackingResult:
        """Parse Royal Mail API response."""
        try:
            mailpieces = data.get("mailPieces", [])
            if not mailpieces:
                return TrackingResult(success=False, error="No tracking data found")

            mailpiece = mailpieces[0]
            summary = mailpiece.get("summary", {})
            events_data = mailpiece.get("events", [])

            # Get the latest status
            status_text = summary.get("statusDescription", "Unknown")
            status = self.normalise_status(status_text)

            # Parse events
            events = []
            for event in events_data:
                event_time = event.get("eventDateTime")
                if event_time:
                    try:
                        timestamp = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                    except ValueError:
                        timestamp = datetime.now(timezone.utc)
                else:
                    timestamp = datetime.now(timezone.utc)

                events.append({
                    "status_text": event.get("eventName", ""),
                    "location": event.get("locationName", ""),
                    "timestamp": timestamp,
                })

            # Get expected delivery if available
            expected_delivery = None
            estimated_delivery = summary.get("estimatedDelivery", {})
            if estimated_delivery:
                date_str = estimated_delivery.get("date")
                if date_str:
                    try:
                        expected_delivery = datetime.fromisoformat(date_str)
                    except ValueError:
                        pass

            return TrackingResult(
                success=True,
                status=status,
                status_text=status_text,
                location=events[0].get("location") if events else None,
                timestamp=events[0].get("timestamp") if events else None,
                expected_delivery=expected_delivery,
                events=events,
            )

        except Exception as e:
            return TrackingResult(success=False, error=f"Error parsing response: {e}")

    def _parse_html_response(self, html: str, tracking_number: str) -> TrackingResult:
        """Fallback HTML parsing (limited due to JS rendering)."""
        soup = BeautifulSoup(html, "lxml")

        # Look for any tracking status elements
        # This is a best-effort fallback
        status_elem = soup.find(class_=re.compile(r"status|tracking", re.I))
        if status_elem:
            status_text = status_elem.get_text(strip=True)
            return TrackingResult(
                success=True,
                status=self.normalise_status(status_text),
                status_text=status_text,
            )

        return TrackingResult(
            success=False,
            error="Could not parse tracking page (JS rendering required)",
        )

    async def parse_email(self, email_body: str, email_subject: str) -> str | None:
        """Extract tracking number from Royal Mail emails."""
        # Check if this looks like a Royal Mail email
        if "royal mail" not in email_subject.lower() and "royal mail" not in email_body.lower():
            return None

        # Try to find tracking numbers in the email
        patterns = [
            r"[A-Z]{2}[0-9]{9}GB",  # International format
            r"[A-Z]{2}[0-9]{9}[A-Z]{2}",  # Standard format
            r"[0-9]{16,20}",  # Numeric format
        ]

        for pattern in patterns:
            match = re.search(pattern, email_body.upper())
            if match:
                return match.group(0)

        return None
