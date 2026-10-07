# Running Category Radar

## CLI Commands

### `radar run`
Scrapes all configured channels, extracts ECB exchange rates, stores raw HTML, normalises listings into SQLite, performs analytics, and generates dashboard bundles.

Flags:
- `--channels`: Subset of channel IDs (e.g., `geizhals_de,ceneo_pl`).
- `--no-reviews`: Skip scraping detailed product review pages for speed.
- `--no-export`: Skip generating static dashboard exports.
- `--async`: Enable concurrent channel scraping with `asyncio`.

### `radar reparse`
Re-runs normalisation and analytics on previously saved raw HTML snapshots without hitting retailer websites:

```bash
radar reparse --date 2026-10-06
```

### `radar export`
Re-builds JSON dashboard artifacts and analytical CSV files from the local SQLite database.

### `radar report`
Generates and prints executive market intelligence dossiers.

### `radar migrate`
Applies pending Alembic database schema migrations.
