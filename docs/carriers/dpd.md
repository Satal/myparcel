# DPD Setup Guide

DPD UK tracking works out of the box with no additional configuration required.

## Requirements

None! DPD tracking uses HTTP scraping and works with the standard MyParcel installation.

## How It Works

DPD's tracking page is server-side rendered, which means MyParcel can:

1. Send a simple HTTP request to the tracking page
2. Parse the HTML response
3. Extract tracking information

This is fast and lightweight compared to browser-based scraping.

## Tracking Number Formats

DPD uses numeric tracking numbers:

| Format | Example | Description |
|--------|---------|-------------|
| Standard | `123456789012345` | 14-16 digits |
| Reference | `ABC123DEF456789` | Alphanumeric (10-20 chars) |

## Tracking Stages

DPD parcels typically go through these stages:

1. **Collected** - Picked up from sender
2. **At DPD depot** - At sorting facility
3. **In transit** - On the way
4. **Out for delivery** - With local driver
5. **Delivered** - Successfully delivered

## Features

- **Predict**: DPD often provides 1-hour delivery windows
- **Photo proof**: Delivery photos may be available
- **Redelivery options**: Can be managed via DPD's website

## Configuration

No environment variables are required for DPD.

## Troubleshooting

### "Could not parse tracking page" error

- DPD may have changed their website structure
- Try the tracking number directly on [dpd.co.uk](https://www.dpd.co.uk/tracking)
- Report the issue so we can update the parser

### Tracking number not found

- The parcel may not be in DPD's system yet
- Check the tracking number is correct
- Try without any spaces or dashes

### Rate limiting

DPD may rate-limit requests if you're checking too frequently. The default 30-minute refresh interval should be fine.

## Links

- [DPD UK Tracking](https://www.dpd.co.uk/tracking)
- [DPD Customer Service](https://www.dpd.co.uk/content/about_dpd/contact_us.jsp)
