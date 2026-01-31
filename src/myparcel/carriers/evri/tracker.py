"""Evri tracking implementation.

Note: Evri's tracking page is a JavaScript SPA (Nuxt/Vue) and their API
is protected by AWS WAF. This tracker requires Playwright for browser
automation to work reliably.

The tracking API endpoint is:
    https://tracking.platform-apis.evri.com/v1/parcels/reference/{tracking_number}

But it requires:
1. A rotating API key from https://www.evri.com/protected/keys.json
2. A valid AWS WAF challenge token (only obtainable via browser)
"""

import re
from datetime import datetime, timezone

import httpx

from myparcel.carriers.base import BaseCarrier, CarrierConfig, TrackingResult
from myparcel.db.models import ParcelStatus

# Try to import playwright - it's optional
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class EvriCarrier(BaseCarrier):
    """Evri (formerly Hermes) carrier adapter.

    This carrier requires Playwright for reliable tracking due to
    Evri's JavaScript-rendered pages and WAF-protected API.

    Install with: pip install playwright && playwright install chromium
    """

    # Evri tracking stages in order
    STAGES = [
        "We're expecting it",
        "We've got it",
        "On its way",
        "Out for delivery",
        "Delivered",
    ]

    def __init__(self, config: CarrierConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "en-GB,en;q=0.9",
            },
            follow_redirects=True,
            timeout=30.0,
        )

    async def fetch_status(self, tracking_number: str) -> TrackingResult:
        """Fetch tracking status from Evri using Playwright."""
        tracking_number = tracking_number.strip().upper()

        if not PLAYWRIGHT_AVAILABLE:
            return TrackingResult(
                success=False,
                error="Playwright not installed. Run: pip install playwright && playwright install chromium",
            )

        try:
            return await self._fetch_with_playwright(tracking_number)
        except Exception as e:
            return TrackingResult(success=False, error=f"Error: {e}")

    async def _fetch_with_playwright(self, tracking_number: str) -> TrackingResult:
        """Use Playwright to load the tracking page and extract data."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                # Navigate to tracking page
                url = f"https://www.evri.com/track/parcel/{tracking_number}"
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for tracking content to load
                await page.wait_for_timeout(2000)

                # Extract status from the page
                return await self._extract_status_from_page(page)

            finally:
                await browser.close()

    async def _extract_status_from_page(self, page) -> TrackingResult:
        """Extract tracking status from the loaded page."""
        events = []

        # Try to get the main status heading (e.g., "On its way")
        status_text = "Unknown"
        try:
            status_elem = await page.query_selector("h3")
            if status_elem:
                status_text = await status_elem.inner_text()
        except Exception:
            pass

        # Try to get the status description
        description = ""
        try:
            desc_elem = await page.query_selector("h3 + p")
            if desc_elem:
                description = await desc_elem.inner_text()
        except Exception:
            pass

        # Try to extract timeline stages
        try:
            # Find completed stages (have "ticked" in their label)
            completed_buttons = await page.query_selector_all(
                'button[aria-label*="ticked"], button:has-text("ticked")'
            )
            for btn in completed_buttons:
                text = await btn.inner_text()
                # Clean up the text
                text = text.replace("ticked parcel stage complete", "").strip()
                if text:
                    events.append({
                        "status_text": f"✓ {text}",
                        "location": None,
                        "timestamp": datetime.now(timezone.utc),
                    })
        except Exception:
            pass

        # Determine normalised status
        status = self._status_from_stage(status_text)

        # Combine status with description
        full_status = status_text
        if description:
            full_status = f"{status_text}: {description}"

        if status_text != "Unknown" or events:
            return TrackingResult(
                success=True,
                status=status,
                status_text=full_status,
                events=events,
            )

        return TrackingResult(
            success=False,
            error="Could not extract tracking data from page",
        )

    def _status_from_stage(self, stage_text: str) -> ParcelStatus:
        """Convert Evri stage text to normalised status."""
        stage_lower = stage_text.lower()

        if "delivered" in stage_lower:
            return ParcelStatus.DELIVERED
        if "out for delivery" in stage_lower:
            return ParcelStatus.OUT_FOR_DELIVERY
        if "on its way" in stage_lower or "in transit" in stage_lower:
            return ParcelStatus.IN_TRANSIT
        if "got it" in stage_lower or "we have" in stage_lower:
            return ParcelStatus.RECEIVED
        if "expecting" in stage_lower:
            return ParcelStatus.PENDING

        return self.normalise_status(stage_text)

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
