# AGENTS.md — Central European Air Fryer Brand Program

> **Context:** Global air fryer brand, Central Europe (DE · AT · CH · PL · CZ · HU)  
> **Stack:** Category Radar (Python, SQLite, static dashboard) + Hermes Agent team  
> **Cadence:** 24/7 autonomous monitoring, weekly WBR (Mon 09:00 CEST), monthly deep-dive

---

## Program Roster (6 agents)

| Agent | Profile | Role | Primary Skills | Delivers To |
|-------|---------|------|----------------|-------------|
| **Program Orchestrator** | `@osman` | Weekly cadence, gates, approval trail, cross-agent coordination | `eb-cadence`, `eb-diretrice`, `eb-doctrine` (repurposed) | All |
| **Intelligence Hub** | `@orhan` | Competitive/retail intel, promo calendars, price alerts beyond shelf data | `competitor-news-monitor`, `grounded-citations`, `blogwatcher`, `product-price-monitor` | All (feeds) |
| **Category Strategy Lead** | `@category-lead-ce` | Portfolio lifecycle, positioning, competitive landscape, assortment roadmap | `competitor-news-monitor`, `grounded-citations`, `xlsx`, `airtable`, `web_extract` | Marketing, Retail, Insights |
| **Omnichannel Marketing Lead** | `@marketing-lead-ce` | CE strategy → in-store/online execution → KPI/ROI tracking | `google-workspace`, `meeting-action-items`, `document-to-action-items`, `xlsx` | Retail, Insights |
| **Retail Activation Lead** | `@retail-activation-ce` | Sales tools, key-account activation, JBP support, win-win distribution | `google-workspace`, `meeting-action-items`, `document-to-action-items`, `himalaya` | Category, Marketing, Insights |
| **Insights & Reporting Analyst** | `@insights-analyst-ce` | **OWNER of Category Radar** — runs, maintains, extends, alerts | `xlsx`, `airtable`, `pdf`, `web_extract`, `obsidian` | All (infrastructure) |

---

## Category Radar — Technical Backbone (Pillar D)

**Repo:** `/Users/berksaraloglu/Projects/category-radar`  
**Dashboard:** `radar.saralogy.com` (GitHub Pages, auto-deploy on `radar publish`)  
**Schedule:** Weekly snapshot every Monday 07:30 via `launchd` (`scripts/weekly.sh`)  
**Run manually:** `radar run && radar publish` (~5–8 min)

### Radar Outputs → Task Mapping

| Radar Tab | Metrics | Your Tasks | Consumers |
|-----------|---------|------------|-----------|
| **Price** | Median/P10–P90, brand price index, cross-market gaps, weekly trend, movers | 3, 10 | All |
| **Positioning** | Brand map (price index × rating/claims), claim heatmap, tier mix | 3, 5 | Category, Marketing |
| **Competition** | Visibility share, review/purchase share, HHI, sponsored share, footprint | 3, 11 | Category, Retail |
| **Market Needs** | Feature lift (top-20 vs shelf), review salience (DE/PL/CS/HU), capacity sweet spot, demand signals | 3, 12 | Category, Marketing |
| **radar.json + CSVs** | Portable data for any BI tool | 8 | Insights (extends), All (consume) |

### Radar Runbook (for @insights-analyst-ce)

```bash
# Full snapshot
cd ~/Projects/category-radar
source .venv/bin/activate
radar run && radar publish

# Doctor check (all channels fetch+parse)
radar doctor

# Re-parse after parser fix (no network)
radar reparse --date 2026-10-06

# Single channel
radar run --channels geizhals_de,ceneo_pl

# Export CSVs for Excel
radar export
```

### Adding a Channel / Market

1. Add channel block to `config/airfryer.yaml`
2. If new site: create `src/category_radar/channels/<site>.py` with `@register("<site>")` class
3. Save fixture: `tests/fixtures/<site>.html` + test
4. `radar doctor --channels <id>`

---

## 24/7 Autonomous Operations

### Cron Jobs (managed via `cronjob_manage`)

| Job | Schedule | Owner | Purpose |
|-----|----------|-------|---------|
| **Radar Weekly Snapshot** | `0 7 * * 1` (Mon 07:30) | `@insights-analyst-ce` | Full scrape → store → analyse → export → publish |
| **Price Mover Alert** | `every 4h` | `@insights-analyst-ce` | Check `radar.json` for >5% price moves, alert via Bot Chat |
| **Competitive News Digest** | `0 6 * * *` (daily 06:00) | `@orhan` | Scan trade press, retailer news, competitor launches |
| **Retailer Promo Calendar Sync** | `0 8 * * 1` (Mon 08:00) | `@orhan` | Update promo calendar from retailer portals |
| **WBR Prep Package** | `0 7 * * 1` (Mon 07:00) | `@osman` | Compile Radar insights + news + action items for 09:00 WBR |
| **Monthly Deep-Dive** | `0 9 1 * *` (1st of month 09:00) | `@category-lead-ce` | Portfolio lifecycle review, white-space analysis |

### Bot Chat Channel

All agents communicate via **Bot Chat** (Hermes gateway).  
Channel: `bot-chat` (multiplexed across all profiles).  
Delivery: `deliver: "bot-chat"` in cron jobs.

---

## Key Retailers & Systems (CE Markets)

| Market | Top Retailers | Media Networks | JBP Cycle | Key Portals |
|--------|---------------|----------------|-----------|-------------|
| **DE** | MediaMarkt/Saturn, Amazon DE, Otto, Expert, Euronics, Conrad | MediaMarkt Ads, Amazon DSP, Otto Media | Annual (Q4 for next year) | MediaMarkt Vendor Portal, Amazon Vendor Central, Otto Partner Portal |
| **AT** | MediaMarkt, Amazon AT, Eduscho, Universal, Expert | MediaMarkt Ads, Amazon DSP | Annual | Same as DE |
| **CH** | MediaMarkt, Digitec/Galaxus, Amazon CH, Fust, Interdiscount | Digitec Ads, Amazon DSP | Annual | Galaxus Partner Portal |
| **PL** | Media Expert, RTV Euro AGD, Amazon PL, Allegro, x-kom | Allegro Ads, Amazon DSP | Quarterly | Allegro Seller Center, Amazon Vendor Central |
| **CZ** | Alza, Mall.cz, Amazon DE (cross-border), Datart, CZC | Alza Ads, Mall Ads | Semi-annual | Alza Partner Portal |
| **HU** | Extreme Digital, Alza HU, MediaMarkt HU, Emag | Emag Ads, Alza Ads | Semi-annual | Emag Seller Center |

---

## Data Sources & Whitelists

| Source | Type | Access | Used By |
|--------|------|--------|---------|
| **Category Radar** | Shelf data (price, specs, ratings, purchases) | Local SQLite + `radar.json` | All |
| **Geizhals DE/AT** | Price comparison | Public, polite scrape | Radar |
| **Toppreise CH** | Price comparison | Public, polite scrape | Radar |
| **Ceneo PL** | Price comparison + purchase counts | Public, polite scrape | Radar |
| **Alza CZ** | Retailer best-seller | Public, polite scrape | Radar |
| **Árukereső HU** | Price comparison | Public, polite scrape | Radar |
| **GFK / NPD** | Sell-out panels | Subscription (if available) | Category, Insights |
| **Retailer Portals** | Sell-in, stock, promo calendars | API / manual download | Retail, Marketing, Insights |
| **Trade Press** | ESM, LSA, Distribucion, RetailDetail, channel-specific | Web / RSS | Intelligence Hub |

---

## Weekly WBR Agenda (Mon 09:00 CEST, 45 min)

1. **Radar Snapshot** (5 min) — @insights-analyst-ce: price movers, new entrants, claim shifts
2. **Competitive Digest** (5 min) — @orhan: launches, promos, retailer changes
3. **Pipeline Health** (10 min) — @category-lead-ce: NPD status, EOL decisions, assortment gaps
4. **Activation Status** (10 min) — @retail-activation-ce: key-account wins/blocks, JBP progress
5. **Marketing Performance** (10 min) — @marketing-lead-ce: ROAS by channel, promo effectiveness
6. **Decisions & Gates** (5 min) — @osman: approve/reject items >€50k, new SKU intro, campaign launch

**Gate Definitions** (require @osman sign-off):
- Campaign budget >€50k
- New SKU introduction / EOL
- Retailer JBP commitment changes
- Promo mechanics outside approved calendar

---

## Communication Protocols

- **Bot Chat** = primary channel for all agent-to-agent and agent-to-human
- **Cron job outputs** → delivered to `bot-chat` with `attach_to_session: true` for continuity
- **Urgent alerts** (price crash, stock-out, competitor launch) → `@orhan` fires immediate `cronjob_manage run` with `deliver: "bot-chat"`
- **Human decisions** → @osman creates kanban task with `assignee: <profile>`, `initial_status: "blocked"`, `kind: "needs_input"`

---

## File Layout

```
/Users/berksaraloglu/Projects/category-radar/
├── AGENTS.md                    # This file
├── config/airfryer.yaml         # Radar category config (markets, channels, brands, claims, needs)
├── src/category_radar/          # Radar Python package
├── data/radar.sqlite            # Full history (gitignored)
├── data/raw/<date>/<channel>/   # Raw HTML audit trail (gitignored)
├── data/exports/*.csv           # Listings + brand scorecards
├── site/data/radar.json         # Dashboard bundle (published to radar.saralogy.com)
├── scripts/weekly.sh            # Cron: radar run && radar publish
└── docs/adr/                    # Architecture decisions
```

---

## Escalation Paths

| Issue | First Responder | Escalation |
|-------|-----------------|------------|
| Radar channel blocked | @insights-analyst-ce | @osman (decide: wait / switch channel / manual) |
| Competitor launch not in Radar | @orhan | @category-lead-ce (assess impact) |
| Key-account activation blocked | @retail-activation-ce | @osman (engage country sales lead) |
| Promo ROI below threshold | @marketing-lead-ce | @osman (reallocate / pause) |
| Data quality anomaly | @insights-analyst-ce | @category-lead-ce (validate vs source) |

---

## Quality Standards

- **No fabricated data** — every claim traces to Radar, retailer portal, or named source
- **Proxy labels** — if sell-out unavailable, label "shelf proxy" explicitly
- **German informal "du"** for all internal comms; local language for retailer-facing
- **Stand: dates** on any pricing/promo/assortment doc that changes
- **Batch discipline** — max 20 SKUs per analysis batch; verify before next

---

## Onboarding for New Agents

1. Read this `AGENTS.md`
2. Run `radar doctor` — verify all 6 channels fetch + parse
3. Open `radar.saralogy.com` — understand the 4 tabs
4. Join `bot-chat` — introduce yourself, state your charter
5. First deliverable due Week 1 (see Sprint 1 below)

---

## Sprint 1 (Week 1–2) Deliverables

| Agent | Deliverable | Due |
|-------|-------------|-----|
| `@insights-analyst-ce` | Radar v1.1: add Amazon DE best-sellers channel, price-mover alerts (>5%), weekly email digest | Fri W1 |
| `@orhan` | Retail Promo Calendar 2025/26 for top 10 CE retailers (promo windows, media deadlines) | Wed W1 |
| `@category-lead-ce` | Portfolio Lifecycle Dashboard: current SKUs → intro/growth/mature/decline by market, EOL candidates, white-space claims | Fri W1 |
| `@marketing-lead-ce` | CE Marketing Calendar H1 2026: aligned to retailer promos, hero SKU per wave, media budget split | Fri W2 |
| `@retail-activation-ce` | Sales Battlecards v1: top 5 competitors × 6 markets (price index, claims, ratings, distribution, retailer hooks) | Fri W1 |
| `@osman` | Program Charter: WBR agenda, gate definitions, RACI, escalation paths | Mon W1 |

---

## Model & Provider

- **Default:** `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter
- **Pinned for cron jobs:** whatever `hermes model` is set to at job creation (use `pinned: true` for stability)
- **Override per-agent:** `hermes -p <profile> model` to select

---

## SOUL.md Customization

Each profile has a cloned `SOUL.md` from `@jarvis`. Edit per role:

- `@category-lead-ce` → analytical, portfolio-first, "what does the shelf reward?"
- `@marketing-lead-ce` → execution-oriented, "what moves the needle in-store and online?"
- `@retail-activation-ce` → retailer-empathetic, "win-win or no deal"
- `@insights-analyst-ce` → evidence-driven, "the numbers say X, here's why"
- `@orhan` → vigilant, "I saw this coming"
- `@osman` → steady, "here is the decision, here is the trail"

---

*Updated: 2026-10-06 | Program: CE Air Fryer Brand | Owner: Berk Saraloglu*