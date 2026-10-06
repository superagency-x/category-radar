#!/usr/bin/env bash
# Weekly snapshot: scrape -> analyse -> publish. Scheduled by launchd (see README).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
mkdir -p data/logs
{
  echo "=== $(date) ==="
  radar run && radar publish
} >> data/logs/weekly.log 2>&1
