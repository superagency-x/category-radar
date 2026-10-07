# Installation

## Prerequisites

- Python 3.10 or higher (Python 3.12+ recommended)
- `uv` (recommended) or `pip`

## Setup

```bash
git clone https://github.com/berksaraloglu/category-radar.git
cd category-radar

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with development, documentation, and browser support
pip install -e ".[browser,dev,docs]"

# Optional: Install Playwright browser engines for complex dynamic sites
playwright install chromium
```

## Environment Variables

Copy the example configuration to `.env`:

```bash
cp .env.example .env
```

Available environment variables:
- `RADAR_USER_AGENT`: Custom crawler user agent string.
- `SLACK_WEBHOOK_URL`: Optional webhook URL for notifications.
- `ECB_API_KEY`: Optional European Central Bank API credentials.
