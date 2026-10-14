# MyParcel

A self-hosted parcel tracking aggregator with community-maintained carrier adapters.

Track all your parcels from Royal Mail, DPD, Evri, and more in one place.

## Features

- **Multi-carrier support**: Track parcels from multiple carriers in a single dashboard
- **Auto-detection**: Automatically detect which carrier a tracking number belongs to
- **Community adapters**: Easy-to-add carrier adapters using YAML configuration and Python
- **Self-hosted**: Run on your own server, keep your data private
- **Simple UI**: Clean, responsive web interface

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/satal/myparcel.git
cd myparcel

# Set the login and session key (compose refuses to start without them)
cat > .env <<ENV
SECRET_KEY=$(openssl rand -hex 32)
AUTH_USERNAME=me
AUTH_PASSWORD=choose-something
DEFAULT_POSTCODE=AB1 2CD
ENV

# Lightweight image (Relay, DPD, Royal Mail)
docker compose up -d --build

# Or the full image with Chromium, for Evri
MYPARCEL_TARGET=full MYPARCEL_MEMORY=1g docker compose up -d --build

# Access at http://localhost:8000
```

### Portainer

Create a stack from this repository (compose path `docker-compose.yml`) and set
these environment variables on the stack:

| Variable | Required | Notes |
|----------|----------|-------|
| `SECRET_KEY` | yes | Random string; signs the login cookie |
| `AUTH_USERNAME` / `AUTH_PASSWORD` | yes | The web UI login |
| `MYPARCEL_DATA` | yes | Absolute host path for the SQLite database, e.g. `/volume2/docker/myparcel` |
| `MYPARCEL_PORT` | no | Host port, default 8000 |
| `DEFAULT_POSTCODE` | no | Used for parcels added without a postcode |
| `MYPARCEL_TARGET` | no | `full` to include Chromium for Evri (raise `MYPARCEL_MEMORY` to `1g`) |
| `ROYAL_MAIL_CLIENT_ID` / `ROYAL_MAIL_CLIENT_SECRET` | no | Royal Mail tracking API |

Portainer builds the image from the repository on the target host. The
container healthcheck uses `/health`, which needs no login.

### Local Development

```bash
# Clone and enter directory
git clone https://github.com/satal/myparcel.git
cd myparcel

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (lightweight)
pip install -e .

# Or install with browser automation support (for Evri, etc.)
pip install -e ".[browser]"
playwright install chromium

# Run the development server
uvicorn myparcel.main:app --reload
```

## Supported Carriers

| Carrier | Status | Requirements | Notes |
|---------|--------|--------------|-------|
| Royal Mail | ✅ Working | API credentials | [Get API keys](https://developer.royalmail.net/) |
| DPD | ✅ Working | None | Parcel code, parcel number or consignment number |
| Relay | ✅ Working | Postcode for home deliveries | Collect-from-shop orders need none |
| Evri | ✅ Working | Playwright | Formerly Hermes, JS-heavy site |
| Amazon Logistics | ⚠️ Limited | - | Requires login for full tracking |

### Royal Mail API Setup

Royal Mail requires API credentials from their developer portal:

1. Register at [developer.royalmail.net](https://developer.royalmail.net/)
2. Create an application to get your Client ID and Secret
3. Subscribe to the [Tracking API v2](https://developer.royalmail.net/product/175625/api/76888)
4. Add credentials to your `.env` file:

```bash
ROYAL_MAIL_CLIENT_ID=your-client-id
ROYAL_MAIL_CLIENT_SECRET=your-client-secret
```

### Browser Automation (Evri)

Some carriers (like Evri) have JavaScript-heavy tracking pages that require browser automation via [Playwright](https://playwright.dev/).

- **Lightweight Docker image**: Works with DPD (and Royal Mail with API keys)
- **Full Docker image**: Includes Chromium for Evri and similar carriers

The full image is larger (~1GB vs ~200MB) but supports all carriers.

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key settings:
- `SECRET_KEY`: Change this to a random string in production
- `AUTH_USERNAME` / `AUTH_PASSWORD`: Login for the web UI; without both, there is no login
- `DEFAULT_POSTCODE`: Used for parcels added without their own postcode
- `REFRESH_INTERVAL_MINUTES`: How often active parcels are refreshed in the background (default: 30, 0 disables)

## Project Structure

```
myparcel/
├── src/myparcel/
│   ├── api/              # API routes
│   ├── carriers/         # Carrier adapters
│   │   ├── royal_mail/   # Royal Mail adapter
│   │   ├── dpd/          # DPD adapter
│   │   └── evri/         # Evri adapter
│   ├── db/               # Database models
│   ├── services/         # Business logic
│   └── templates/        # HTML templates
├── static/               # CSS, JS, images
├── tests/                # Test suite
└── data/                 # SQLite database (created at runtime)
```

## Adding a New Carrier

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed instructions.

Quick overview:
1. Create a directory in `src/myparcel/carriers/` with the carrier ID
2. Add a `carrier.yaml` with tracking patterns and status mappings
3. Create a `tracker.py` implementing the `BaseCarrier` class
4. Test your adapter
5. Submit a pull request

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/login`, `/logout` | GET/POST | Web UI login (when enabled) |
| `/health` | GET | Liveness check, no login needed |
| `/parcel/{id}` | GET | Parcel details |
| `/parcel/add` | POST | Add new parcel |
| `/parcel/{id}/refresh` | POST | Refresh tracking |
| `/parcel/{id}/delete` | POST | Delete parcel |
| `/api/detect-carrier` | GET | Detect carrier from tracking number |
| `/api/carriers` | GET | List available carriers |

## Roadmap

- [ ] Email forwarding integration
- [ ] Push notifications
- [ ] Mobile-friendly PWA
- [ ] Household/multi-user support
- [ ] More carriers (UPS, FedEx, etc.)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
