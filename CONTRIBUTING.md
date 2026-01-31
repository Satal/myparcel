# Contributing to MyParcel

Thank you for your interest in contributing to MyParcel! This guide will help you add new carrier adapters or improve existing ones.

## Adding a New Carrier

Adding a new carrier is the most common contribution. Here's how to do it:

### 1. Create the Carrier Directory

Create a new directory in `src/myparcel/carriers/` with the carrier ID (lowercase, hyphens for spaces):

```bash
mkdir src/myparcel/carriers/your-carrier
touch src/myparcel/carriers/your-carrier/__init__.py
```

### 2. Create carrier.yaml

This file defines the carrier's metadata, tracking number patterns, and status mappings:

```yaml
# src/myparcel/carriers/your-carrier/carrier.yaml

id: your-carrier
name: Your Carrier Name
website: https://www.yourcarrier.com
tracking_url_template: "https://www.yourcarrier.com/track?id={tracking_number}"
enabled: true

# Tracking number patterns (regex)
# These help auto-detect which carrier a tracking number belongs to
tracking_patterns:
  - regex: "^[A-Z]{2}[0-9]{9}[A-Z]{2}$"
    description: "Standard format"
  - regex: "^[0-9]{12,16}$"
    description: "Numeric format"

# Map carrier status text to normalised status
# Keys are substrings to match (case-insensitive)
status_mapping:
  "delivered": "delivered"
  "out for delivery": "out_for_delivery"
  "in transit": "in_transit"
  "collected": "received"
  "attempted": "failed_attempt"
  "held": "held"
  "returned": "returned"

# Optional: Email parsing hints
email_patterns:
  subject_contains:
    - "Your Carrier"
    - "Delivery notification"
  tracking_regex: "[A-Z]{2}[0-9]{9}[A-Z]{2}"
```

### 3. Create tracker.py

This file contains the actual tracking logic:

```python
# src/myparcel/carriers/your-carrier/tracker.py

from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup

from myparcel.carriers.base import BaseCarrier, CarrierConfig, TrackingResult


class YourCarrier(BaseCarrier):
    """Your Carrier tracking implementation."""

    def __init__(self, config: CarrierConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/json",
            },
            follow_redirects=True,
            timeout=30.0,
        )

    async def fetch_status(self, tracking_number: str) -> TrackingResult:
        """Fetch tracking status from the carrier."""
        tracking_number = tracking_number.strip().upper()

        try:
            # Option 1: If carrier has an API
            # response = await self.client.get(
            #     f"https://api.yourcarrier.com/track/{tracking_number}"
            # )
            # data = response.json()
            # return self._parse_api_response(data)

            # Option 2: Scrape the tracking page
            url = f"https://www.yourcarrier.com/track?id={tracking_number}"
            response = await self.client.get(url)

            if response.status_code == 200:
                return self._parse_html(response.text)

        except Exception as e:
            return TrackingResult(success=False, error=str(e))

        return TrackingResult(success=False, error="Could not fetch tracking data")

    def _parse_html(self, html: str) -> TrackingResult:
        """Parse the tracking page HTML."""
        soup = BeautifulSoup(html, "lxml")
        events = []

        # Find tracking events - adjust selectors for your carrier
        # timeline = soup.find(class_="tracking-timeline")
        # for item in timeline.find_all(class_="event"):
        #     events.append({
        #         "status_text": item.find(class_="status").text,
        #         "location": item.find(class_="location").text,
        #         "timestamp": parse_datetime(item.find(class_="time").text),
        #     })

        # Find current status
        status_text = "Unknown"
        # status_elem = soup.find(class_="current-status")
        # if status_elem:
        #     status_text = status_elem.text.strip()

        return TrackingResult(
            success=True,
            status=self.normalise_status(status_text),
            status_text=status_text,
            events=events,
        )
```

### 4. Test Your Adapter

```bash
# Run the test suite
pytest tests/carriers/test_your_carrier.py

# Or test manually
python -c "
import asyncio
from myparcel.services.carrier_loader import carrier_loader

async def test():
    carrier_loader.load_all()
    carrier = carrier_loader.get_carrier('your-carrier')
    result = await carrier.fetch_status('YOUR_TEST_TRACKING_NUMBER')
    print(result)

asyncio.run(test())
"
```

### 5. Submit a Pull Request

1. Fork the repository
2. Create a branch: `git checkout -b add-your-carrier`
3. Commit your changes
4. Push and create a pull request

## Normalised Status Values

Use these status values in your `status_mapping`:

| Status | Description |
|--------|-------------|
| `pending` | Label created, not yet with carrier |
| `received` | Carrier has the parcel |
| `in_transit` | On the way |
| `out_for_delivery` | With local driver |
| `delivered` | Successfully delivered |
| `failed_attempt` | Delivery attempted but failed |
| `held` | Held at depot/customs |
| `returned` | Returned to sender |
| `exception` | Problem with delivery |
| `unknown` | Status not recognised |

## Code Style

- Use [ruff](https://github.com/astral-sh/ruff) for linting
- Type hints are encouraged
- Follow existing patterns in the codebase

```bash
# Format and lint
ruff check --fix .
ruff format .
```

## Testing Guidelines

When adding a carrier:

1. **Include sample responses**: Add example HTML/JSON responses in `tests/carriers/fixtures/`
2. **Test pattern matching**: Verify tracking number patterns work correctly
3. **Test status mapping**: Ensure statuses are normalised correctly
4. **Handle errors gracefully**: Test what happens when tracking fails

## Questions?

Open an issue on GitHub if you need help or have questions about contributing.
