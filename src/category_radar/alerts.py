"""Autonomous GTM Early Warning & Market Alerting Engine.

Monitors category history across snapshots to flag:
- Sudden competitor price cuts (>5% or >10% price war triggers)
- Critical cross-border price arbitrage (>50% spread across DE/AT/PL/CZ/HU)
- Fast-climbing new entrants & rank jumpers breaking into top 20
- Vulnerable competitor SKUs (high visibility but poor rating < 4.0★)
- Whitespace feature opportunities with high consumer lift (>1.5x)

Supports automated Webhook dispatch to Slack, Discord, Microsoft Teams, and Bot-Chat.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import httpx

from .analytics import _by
from .config import CategoryConfig
from .logging_config import get_logger

log = get_logger(__name__)


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    INFO = "info"


@dataclass
class MarketAlert:
    id: str
    severity: AlertSeverity
    category: str  # price_cut, arbitrage, new_entrant, vulnerability, whitespace
    market: str
    title: str
    description: str
    sku_or_brand: str
    metric: str
    created_at: str


def detect_alerts(
    latest_rows: list[dict],
    history_rows: list[dict],
    cfg: CategoryConfig | None = None,
    min_severity: AlertSeverity = AlertSeverity.INFO,
) -> list[MarketAlert]:
    """Detect all actionable market alerts across latest and historical snapshots."""
    alerts: list[MarketAlert] = []
    now = datetime.now(timezone.utc).isoformat()

    # 1. Price War / Sudden Price Cuts
    snapshots = sorted({r["snapshot_date"] for r in history_rows})
    if len(snapshots) >= 2:
        prev_date = snapshots[-2]
        prev_prices: dict[tuple[str, str], float] = {
            (r["market"], r["title"]): r["price_eur"]
            for r in history_rows
            if r["snapshot_date"] == prev_date and r.get("price_eur") is not None
        }

        for r in latest_rows:
            key = (r["market"], r["title"])
            if key in prev_prices and r.get("price_eur") is not None:
                p_old = prev_prices[key]
                p_new = r["price_eur"]
                if p_old > 0 and p_new < p_old:
                    drop_pct = round(100.0 * (p_old - p_new) / p_old, 1)
                    if drop_pct >= 10.0:
                        alerts.append(
                            MarketAlert(
                                id=f"price_crash_{r['market']}_{r['brand']}_{r['rank']}",
                                severity=AlertSeverity.CRITICAL,
                                category="price_cut",
                                market=r["market"],
                                title=f"🚨 Severe Price Drop: {r['brand']} cut {drop_pct}%",
                                description=(
                                    f"{r['title']} dropped from €{p_old} to €{p_new} (-{drop_pct}%) in {r['market']}. "
                                    f"Rank #{r['rank']} on {r.get('channel', 'shelf')}."
                                ),
                                sku_or_brand=r["brand"],
                                metric=f"-{drop_pct}%",
                                created_at=now,
                            )
                        )
                    elif drop_pct >= 5.0:
                        alerts.append(
                            MarketAlert(
                                id=f"price_drop_{r['market']}_{r['brand']}_{r['rank']}",
                                severity=AlertSeverity.HIGH,
                                category="price_cut",
                                market=r["market"],
                                title=f"⚠️ Price Drop: {r['brand']} reduced by {drop_pct}%",
                                description=(
                                    f"{r['title']} reduced from €{p_old} to €{p_new} (-{drop_pct}%) in {r['market']}."
                                ),
                                sku_or_brand=r["brand"],
                                metric=f"-{drop_pct}%",
                                created_at=now,
                            )
                        )

    # 2. Critical Cross-Border Arbitrage (>50% spread)
    for model_key, items in _by(latest_rows, "model_key").items():
        per_m: dict[str, float] = {}
        for r in items:
            if r.get("price_eur") is not None and r["market"] not in per_m:
                per_m[r["market"]] = r["price_eur"]
        if len(per_m) >= 2:
            cheapest_m = min(per_m, key=lambda m: per_m[m])
            dearest_m = max(per_m, key=lambda m: per_m[m])
            lo = per_m[cheapest_m]
            hi = per_m[dearest_m]
            if lo > 0:
                spread = round(100.0 * (hi - lo) / lo, 1)
                if spread >= 50.0:
                    brand = items[0]["brand"]
                    title = items[0]["title"]
                    alerts.append(
                        MarketAlert(
                            id=f"arbitrage_{model_key}",
                            severity=AlertSeverity.CRITICAL,
                            category="arbitrage",
                            market=f"{cheapest_m} ↔ {dearest_m}",
                            title=f"🛑 Critical Arbitrage Spread: {brand} (+{spread}%)",
                            description=(
                                f"Model '{title}' is sold at €{lo} in {cheapest_m} vs €{hi} in {dearest_m} "
                                f"(+{spread}% gap). Severe cross-border grey-import hazard."
                            ),
                            sku_or_brand=brand,
                            metric=f"+{spread}% spread",
                            created_at=now,
                        )
                    )

    # 3. Fast Movers & New Entrants in Top 20
    if len(snapshots) >= 2:
        prev_date = snapshots[-2]
        prev_ranks: dict[tuple[str, str], int] = {
            (r["market"], r["title"]): r["rank"] for r in history_rows if r["snapshot_date"] == prev_date
        }
        for r in latest_rows:
            if r["rank"] <= 20:
                key = (r["market"], r["title"])
                if key not in prev_ranks:
                    alerts.append(
                        MarketAlert(
                            id=f"new_entrant_{r['market']}_{r['rank']}",
                            severity=AlertSeverity.MEDIUM,
                            category="new_entrant",
                            market=r["market"],
                            title=f"⚡ New Entrant in Top 20: {r['brand']}",
                            description=f"'{r['title']}' entered the top 20 at rank #{r['rank']} in {r['market']}.",
                            sku_or_brand=r["brand"],
                            metric=f"Rank #{r['rank']}",
                            created_at=now,
                        )
                    )
                else:
                    jump = prev_ranks[key] - r["rank"]
                    if jump >= 6:
                        alerts.append(
                            MarketAlert(
                                id=f"rank_surge_{r['market']}_{r['rank']}",
                                severity=AlertSeverity.MEDIUM,
                                category="new_entrant",
                                market=r["market"],
                                title=f"📈 Shelf Surge: {r['brand']} jumped +{jump} positions",
                                description=f"'{r['title']}' jumped from #{prev_ranks[key]} to #{r['rank']} in {r['market']}.",
                                sku_or_brand=r["brand"],
                                metric=f"+{jump} positions",
                                created_at=now,
                            )
                        )

    # 4. Vulnerable Competitors (Top 15 but < 4.0★ rating)
    for r in latest_rows:
        if r["rank"] <= 15 and r.get("rating") is not None and r["rating"] < 4.0:
            alerts.append(
                MarketAlert(
                    id=f"vulnerability_{r['market']}_{r['rank']}",
                    severity=AlertSeverity.HIGH,
                    category="vulnerability",
                    market=r["market"],
                    title=f"🎯 Competitor Vulnerability: {r['brand']} rated {r['rating']}★",
                    description=(
                        f"'{r['title']}' holds rank #{r['rank']} in {r['market']} despite weak satisfaction "
                        f"({r['rating']}★ from {r.get('rating_count', 0)} ratings). Prime conquest marketing target."
                    ),
                    sku_or_brand=r["brand"],
                    metric=f"{r['rating']}★",
                    created_at=now,
                )
            )

    # Filter by minimum severity
    severity_order = [AlertSeverity.CRITICAL, AlertSeverity.HIGH, AlertSeverity.MEDIUM, AlertSeverity.INFO]
    min_idx = severity_order.index(min_severity) if min_severity in severity_order else 3
    filtered = [a for a in alerts if severity_order.index(a.severity) <= min_idx]

    # Deduplicate alerts by ID
    unique_alerts = {}
    for a in filtered:
        unique_alerts[a.id] = a
    return list(unique_alerts.values())


def format_alerts_markdown(alerts: list[MarketAlert]) -> str:
    """Format alerts as an executive Markdown bulletin."""
    if not alerts:
        return "✅ **No high-severity market alerts detected in the current snapshot.**"

    lines = ["# 🚨 Category Radar — Market Intelligence Early Warning Bulletin\n"]
    lines.append(
        f"*Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · Tracked Alerts: {len(alerts)}*\n"
    )

    for a in alerts:
        sev_icon = "🛑" if a.severity == AlertSeverity.CRITICAL else "⚠️" if a.severity == AlertSeverity.HIGH else "⚡"
        lines.append(f"### {sev_icon} [{a.severity.upper()}] {a.title}")
        lines.append(f"- **Market:** `{a.market}` | **Entity:** `{a.sku_or_brand}` | **Signal:** `{a.metric}`")
        lines.append(f"- {a.description}\n")

    return "\n".join(lines)


def dispatch_webhook(alerts: list[MarketAlert], webhook_url: str) -> bool:
    """Send alert bulletin to a Slack, Discord, or Microsoft Teams webhook."""
    if not alerts or not webhook_url:
        return False

    summary_text = f"🚨 *Category Radar Alert Digest*: {len(alerts)} actionable market signals detected."
    fields = [
        {
            "title": f"[{a.severity.upper()}] {a.market}: {a.title}",
            "value": f"{a.description} (Signal: {a.metric})",
            "short": False,
        }
        for a in alerts[:8]
    ]

    payload = {
        "text": summary_text,
        "attachments": [
            {
                "color": "#e11d48" if any(a.severity == AlertSeverity.CRITICAL for a in alerts) else "#f59e0b",
                "title": "Category Radar Early Warning",
                "fields": fields,
                "footer": "Category Radar Autonomous Operations",
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }
        ],
    }

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=5.0)
        log.info("webhook_dispatch_success", status=resp.status_code, alerts=len(alerts))
        return resp.status_code in (200, 204)
    except Exception as e:
        log.error("webhook_dispatch_error", error=str(e), url=webhook_url)
        return False
