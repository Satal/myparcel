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

# Option 1: Lightweight (Royal Mail, DPD - no browser automation)
docker compose up -d

# Option 2: Full version with browser support (ALL carriers including Evri)
docker compose --profile full up -d myparcel-full

# Access at http://localhost:8000
```

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

| Carrier | Status | Requires Browser | Notes |
|---------|--------|------------------|-------|
| Royal Mail | ✅ Working | No | UK tracked items |
| DPD | ✅ Working | No | DPD UK |
| Evri | ✅ Working | **Yes** | Formerly Hermes, JS-heavy site |
| Amazon Logistics | ⚠️ Limited | - | Requires login for full tracking |

### Browser Automation Note

Some carriers (like Evri) have JavaScript-heavy tracking pages that require browser automation via [Playwright](https://playwright.dev/).

- **Lightweight Docker image**: Works with Royal Mail, DPD
- **Full Docker image**: Includes Chromium for Evri and similar carriers

The full image is larger (~1GB vs ~200MB) but supports all carriers.

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key settings:
- `SECRET_KEY`: Change this to a random string in production
- `REFRESH_INTERVAL_MINUTES`: How often to refresh tracking (default: 30)

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
