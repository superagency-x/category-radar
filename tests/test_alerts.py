"""Tests for autonomous GTM alert engine."""

from category_radar.alerts import (
    AlertSeverity,
    detect_alerts,
    dispatch_webhook,
    format_alerts_markdown,
)


def test_detect_price_war_and_arbitrage():
    prev_rows = [
        {
            "snapshot_date": "2026-10-01",
            "market": "DE",
            "brand": "Ninja",
            "title": "Ninja Dual AF300",
            "price_eur": 180.0,
            "rank": 2,
            "model_key": "ninja:af300",
        },
    ]

    latest_rows = [
        {
            "snapshot_date": "2026-10-08",
            "market": "DE",
            "brand": "Ninja",
            "title": "Ninja Dual AF300",
            "price_eur": 150.0,  # 16.7% drop -> critical alert
            "rank": 2,
            "model_key": "ninja:af300",
            "rating": 4.8,
            "rating_count": 300,
        },
        {
            "snapshot_date": "2026-10-08",
            "market": "PL",
            "brand": "Ninja",
            "title": "Ninja Dual AF300",
            "price_eur": 90.0,  # Cross border spread: €90 vs €150 = +66.7%
            "rank": 1,
            "model_key": "ninja:af300",
            "rating": 4.8,
            "rating_count": 100,
        },
        {
            "snapshot_date": "2026-10-08",
            "market": "DE",
            "brand": "VulnerableBrand",
            "title": "Vulnerable Fryer",
            "price_eur": 50.0,
            "rank": 5,
            "model_key": "vuln:f1",
            "rating": 3.4,  # Poor rating in top 15 -> vulnerability alert
            "rating_count": 80,
        },
    ]

    history = prev_rows + latest_rows
    alerts = detect_alerts(latest_rows, history, min_severity=AlertSeverity.INFO)

    categories = {a.category for a in alerts}
    assert "price_cut" in categories
    assert "arbitrage" in categories
    assert "vulnerability" in categories

    md = format_alerts_markdown(alerts)
    assert "Category Radar — Market Intelligence Early Warning Bulletin" in md
    assert "Ninja cut 16.7%" in md


def test_dispatch_webhook_empty():
    assert dispatch_webhook([], "https://example.com/webhook") is False
    assert dispatch_webhook([], "") is False
