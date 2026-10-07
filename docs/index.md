# Category Radar

Central European category intelligence from public shelf data.

## What is Category Radar?

Category Radar monitors the dominant price-comparison engines and leading retailers across six Central European markets (DE · AT · CH · PL · CZ · HU), normalises product listings and consumer feedback into a unified data structure, and answers key strategic questions:

- **Price**: Where does the category sit, and how are price distributions shifting?
- **Positioning**: Who claims which feature space, and how does price correlate with ratings?
- **Competitive Landscape**: Who owns shelf visibility, review volume, and regional footprint?
- **Market Needs**: What features and consumer sentiments does the shelf actively reward?

## Quick Start

```bash
pip install -e ".[browser,dev]"
radar doctor
radar run
radar serve
```

## Core Principles

- **Zero cost**: Built purely on open-source Python, SQLite, and static web dashboards.
- **Polite scraping**: Honours `robots.txt`, respects domain-specific rate limits, and uses raw HTML local auditing.
- **Traceable data**: Every insight traces directly to shelf listings or published exchange rates.
- **Offline reproducibility**: Saved raw HTML snapshots allow instant offline re-parsing and algorithmic refinements.
