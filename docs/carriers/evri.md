# Evri (Hermes) Setup Guide

Evri's tracking website is a JavaScript single-page application (SPA) that requires browser automation to scrape. No API credentials are needed, but you must install Playwright.

## Requirements

Evri tracking requires **Playwright** with Chromium browser installed.

### Local Installation

```bash
# Install the browser dependency
pip install playwright

# Install Chromium browser
playwright install chromium
```

Or install MyParcel with browser support:

```bash
pip install -e ".[browser]"
playwright install chromium
```

### Docker Installation

Use the full Docker image which includes Playwright and Chromium:

```bash
# Build and run with browser support
docker compose --profile full up -d myparcel-full
```

Or build manually:

```bash
docker build --target full -t myparcel:full .
docker run --ipc=host -p 8000:8000 myparcel:full
```

> **Important**: The `--ipc=host` flag is required for Chromium to work properly in Docker.

## How It Works

Since Evri doesn't provide a public API, MyParcel:

1. Launches a headless Chromium browser
2. Navigates to the Evri tracking page
3. Waits for JavaScript to render the tracking data
4. Extracts status information from the page

This is slower than API-based tracking (~3-5 seconds per lookup) but works reliably.

## Tracking Number Formats

Evri uses several tracking number formats:

| Format | Example | Description |
|--------|---------|-------------|
| Alphanumeric | `T00D7A9104600744` | Letter + 2 digits + 13 alphanumeric chars |
| Numeric | `1002345678912345` | 16 digits |
| Calling Card | `12345678` | 8 digits (left by courier) |

## Tracking Stages

Evri parcels go through these stages:

1. **We're expecting it** - Label created
2. **We've got it** - Parcel received by Evri
3. **On its way** - In transit to local depot
4. **Out for delivery** - With courier for delivery
5. **Delivered** - Successfully delivered

## Configuration

No environment variables are required for Evri. Just ensure Playwright is installed.

To verify Playwright is working:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://www.evri.com")
    print(page.title())
    browser.close()
```

## Troubleshooting

### "Playwright not installed" error

Run these commands:

```bash
pip install playwright
playwright install chromium
```

### Browser crashes in Docker

Make sure you're running with `--ipc=host`:

```bash
docker run --ipc=host myparcel:full
```

Or use `--cap-add=SYS_ADMIN`:

```bash
docker run --cap-add=SYS_ADMIN myparcel:full
```

### Tracking data not loading

- The page may take a few seconds to load
- Try refreshing manually
- Check if Evri's website is experiencing issues

### High memory usage

Playwright with Chromium uses significant memory (~200-500MB). Consider:

- Using the lightweight Docker image for non-Evri parcels
- Limiting concurrent tracking refreshes

## Links

- [Evri Public Tracking](https://www.evri.com/track-a-parcel)
- [Playwright Documentation](https://playwright.dev/python/)
