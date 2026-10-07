"""Tests for competitive battlecard generation."""

import pytest

from category_radar.battlecards import generate_battlecard, render_battlecard_html
from category_radar.config import load_config


@pytest.fixture
def mock_listings():
    return [
        {
            "market": "DE",
            "brand": "Ninja",
            "title": "Ninja Foodi Max Dual Zone",
            "price_eur": 160.0,
            "rank": 1,
            "rating": 4.8,
            "rating_count": 250,
            "claims": ["dual_zone", "viewing_window"],
            "channel": "geizhals_de",
            "test_score": 92.0,
        },
        {
            "market": "DE",
            "brand": "Ninja",
            "title": "Ninja Double Stack XL",
            "price_eur": 210.0,
            "rank": 3,
            "rating": 4.7,
            "rating_count": 100,
            "claims": ["dual_zone"],
            "channel": "otto_de",
            "test_score": 88.0,
        },
        {
            "market": "DE",
            "brand": "Philips",
            "title": "Philips Airfryer XXL 5000",
            "price_eur": 180.0,
            "rank": 2,
            "rating": 4.5,
            "rating_count": 400,
            "claims": ["app_connected", "steam"],
            "channel": "geizhals_de",
            "test_score": 85.0,
        },
        {
            "market": "DE",
            "brand": "Philips",
            "title": "Philips Airfryer Compact",
            "price_eur": 90.0,
            "rank": 10,
            "rating": 4.2,
            "rating_count": 150,
            "claims": [],
            "channel": "mediamarkt_de",
            "test_score": 75.0,
        },
    ]


def test_generate_battlecard(mock_listings):
    cfg = load_config("config/airfryer.yaml")
    card = generate_battlecard(mock_listings, brand="Ninja", competitor="Philips", market="DE", cfg=cfg)

    assert "error" not in card
    assert card["brand"] == "Ninja"
    assert card["competitor"] == "Philips"
    assert card["market"] == "DE"

    summary = card["summary"]
    assert summary["brand_listings"] == 2
    assert summary["competitor_listings"] == 2
    assert summary["brand_median_eur"] == 185.0
    assert summary["competitor_median_eur"] == 135.0
    assert summary["brand_avg_rating"] == 4.75
    assert len(card["sales_hooks"]) > 0


def test_render_battlecard_html(mock_listings):
    cfg = load_config("config/airfryer.yaml")
    card = generate_battlecard(mock_listings, brand="Ninja", competitor="Philips", market="DE", cfg=cfg)
    html = render_battlecard_html(card)

    assert "<!doctype html>" in html
    assert "Sales Battlecard: Ninja vs. Philips" in html
    assert "Key Commercial Pitch Hooks" in html


def test_battlecard_missing_brand(mock_listings):
    cfg = load_config("config/airfryer.yaml")
    card = generate_battlecard(mock_listings, brand="NonExistentBrand", market="DE", cfg=cfg)
    assert "error" in card
