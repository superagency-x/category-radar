"""Tests for portfolio lifecycle and retailer assortment gap analyzer."""

from category_radar.assortment import (
    analyze_portfolio_lifecycle,
    analyze_retailer_assortment_gap,
    classify_sku_lifecycle,
)
from category_radar.config import load_config


def test_classify_sku_lifecycle():
    hero = {"rank": 5, "rating": 4.8, "price_eur": 180.0, "claims": ["dual_zone"]}
    assert classify_sku_lifecycle(hero) == "Hero / Verified Winner"

    value = {"rank": 22, "rating": 4.2, "price_eur": 79.0, "claims": []}
    assert classify_sku_lifecycle(value) == "Volume Driver / Value Challenger"

    niche = {"rank": 35, "rating": 4.6, "price_eur": 250.0, "claims": ["dual_zone", "steam", "viewing_window"]}
    assert classify_sku_lifecycle(niche) == "Spec Specialist / Premium Niche"

    at_risk = {"rank": 45, "rating": 3.7, "price_eur": 120.0, "claims": []}
    assert classify_sku_lifecycle(at_risk) == "At-Risk / EOL Candidate"


def test_analyze_portfolio_lifecycle():
    rows = [
        {"brand": "Ninja", "rank": 2, "rating": 4.8, "price_eur": 190.0, "claims": []},
        {"brand": "Ninja", "rank": 45, "rating": 3.5, "price_eur": 80.0, "claims": []},
    ]
    res = analyze_portfolio_lifecycle(rows, brand="Ninja")
    assert res["total_listings"] == 2
    summary = res["lifecycle_summary"]
    assert summary["Hero / Verified Winner"]["count"] == 1
    assert summary["At-Risk / EOL Candidate"]["count"] == 1


def test_analyze_retailer_assortment_gap():
    cfg = load_config("config/airfryer.yaml")
    rows = [
        {
            "channel": "geizhals_de",
            "model_key": "ninja:af400",
            "brand": "Ninja",
            "title": "Ninja AF400",
            "rank": 1,
            "price_eur": 180.0,
            "claims": ["dual_zone"],
        },
        {
            "channel": "geizhals_de",
            "model_key": "philips:hd9270",
            "brand": "Philips",
            "title": "Philips HD9270",
            "rank": 2,
            "price_eur": 120.0,
            "claims": [],
        },
        {
            "channel": "mediamarkt_de",
            "model_key": "philips:hd9270",
            "brand": "Philips",
            "title": "Philips HD9270",
            "rank": 1,
            "price_eur": 129.0,
            "claims": [],
        },
    ]

    gap = analyze_retailer_assortment_gap(rows, "mediamarkt_de", "geizhals_de", cfg=cfg)
    assert "error" not in gap
    assert gap["retailer_listings"] == 1
    assert gap["benchmark_listings"] == 2
    assert gap["missing_top20_count"] == 1
    assert gap["missing_top20_models"][0]["model_key"] == "ninja:af400"
    assert len(gap["jbp_pitch_hooks"]) > 0
