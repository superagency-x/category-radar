# CLI Reference

The Category Radar CLI entry point is `radar`.

## Synopsis

```bash
radar [command] [options]
```

## Commands

### `run`
Scrapes all channels, stores data, executes analytics, and exports output.

```bash
radar run [--channels CHANNELS] [--no-reviews] [--no-export] [--async]
```

### `doctor`
Checks channel health, robots compliance, and selector validity without saving to database.

```bash
radar doctor [--channels CHANNELS]
```

### `export`
Rebuilds dashboard bundle (`radar.json`) and analytical CSVs from SQLite.

```bash
radar export
```

### `report`
Outputs executive category intelligence dossier and confirms generated artifacts.

```bash
radar report
```

### `reparse`
Re-parses cached HTML from a past date offline without network access.

```bash
radar reparse --date YYYY-MM-DD
```

### `serve`
Launches the local static web dashboard.

```bash
radar serve [--port PORT] [--no-browser]
```

### `publish`
Commits and pushes dashboard data to trigger GitHub Pages redeployment.

```bash
radar publish
```

### `health`
Starts the monitoring health check web server.

```bash
radar health [--port PORT]
```

### `api`
Starts the REST API server.

```bash
radar api [--port PORT]
```

### `migrate`
Executes Alembic database migrations.

```bash
radar migrate
```
