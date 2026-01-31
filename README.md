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

# Start the application
docker compose up -d

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

# Install dependencies
pip install -e ".[dev]"

# Run the development server
uvicorn myparcel.main:app --reload
```

## Supported Carriers

| Carrier | Status | Notes |
|---------|--------|-------|
| Royal Mail | ✅ Working | UK tracked items |
| DPD | ✅ Working | DPD UK |
| Evri | ✅ Working | Formerly Hermes |
| Amazon Logistics | ⚠️ Limited | Requires login for full tracking |

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
