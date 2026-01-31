# Royal Mail Setup Guide

Royal Mail tracking requires API credentials from their official developer portal.

## Getting API Credentials

### Step 1: Create a Developer Account

1. Go to [developer.royalmail.net](https://developer.royalmail.net/)
2. Click **Sign Up** or **Register**
3. Complete the registration form with your details
4. Verify your email address

### Step 2: Create an Application

1. Log in to the developer portal
2. Navigate to **Apps** in the main menu
3. Click **Create new app**
4. Fill in the application details:
   - **App Name**: e.g., "MyParcel Tracker"
   - **Description**: e.g., "Personal parcel tracking application"
5. Click **Create**
6. **Important**: Copy your **API Key** (Client ID) and **API Secret** (Client Secret)
   - The secret is only shown once!

### Step 3: Subscribe to the Tracking API

1. Go to [API Products](https://developer.royalmail.net/api)
2. Find **Royal Mail Tracking (for Server-side app) v2**
3. Click on it and then click **Subscribe**
4. Select your application from the dropdown
5. Choose a plan (the free tier should work for personal use)
6. Submit the subscription request

> **Note**: Some plans require approval. This typically takes 1-5 business days.

### Step 4: Configure MyParcel

Add your credentials to the `.env` file:

```bash
ROYAL_MAIL_CLIENT_ID=your-client-id-here
ROYAL_MAIL_CLIENT_SECRET=your-client-secret-here
```

Or set them as environment variables:

```bash
export ROYAL_MAIL_CLIENT_ID=your-client-id-here
export ROYAL_MAIL_CLIENT_SECRET=your-client-secret-here
```

For Docker, add them to your `docker-compose.yml`:

```yaml
services:
  myparcel:
    environment:
      - ROYAL_MAIL_CLIENT_ID=your-client-id-here
      - ROYAL_MAIL_CLIENT_SECRET=your-client-secret-here
```

## Tracking Number Formats

Royal Mail uses several tracking number formats:

| Format | Example | Description |
|--------|---------|-------------|
| International | `XQ779509088GB` | 2 letters + 9 digits + GB |
| Standard | `AB123456789CD` | 2 letters + 9 digits + 2 letters |
| Numeric | `1234567890123456` | 16-20 digits |

## API Limits

- **Rate limits**: The API has rate limiting. If you exceed it, you'll get a 429 error.
- **Tracking items**: You can track items you've sent or received.

## Troubleshooting

### "Invalid API credentials" error

- Double-check your Client ID and Secret are correct
- Ensure there are no extra spaces or newlines
- Verify your subscription to the Tracking API is approved

### "Tracking number not found" error

- The parcel may not be in Royal Mail's system yet
- Check the tracking number format is correct
- Very old tracking numbers may no longer be available

### "Rate limit exceeded" error

- Wait a few minutes before trying again
- Consider reducing the refresh frequency in your settings

## Links

- [Royal Mail Developer Portal](https://developer.royalmail.net/)
- [Tracking API v2 Documentation](https://developer.royalmail.net/product/175625/api/76888)
- [Royal Mail Public Tracking](https://www.royalmail.com/track-your-item)
