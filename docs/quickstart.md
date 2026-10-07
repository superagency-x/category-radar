# Quick Start

## 1. Verify Channels (`doctor`)

Before initiating a scrape, run the channel diagnostic tool:

```bash
radar doctor
```

This verifies HTTP fetching, robots.txt access, and CSS/HTML parsing across all registered channels.

## 2. Execute Market Run

Run the automated pipeline:

```bash
# Standard pipeline
radar run

# High-performance concurrent scraping
radar run --async

# Subset of channels
radar run --channels geizhals_de,ceneo_pl
```

## 3. View the Dashboard

Launch the local interactive dashboard:

```bash
radar serve --port 8000
```

## 4. REST API & Health Monitoring

Start the background monitoring and query APIs:

```bash
# Health check server (port 8765)
radar health --port 8765

# REST API (port 8000)
radar api --port 8000
```
