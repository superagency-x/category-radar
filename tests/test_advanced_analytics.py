"""Unit tests for advanced analytics: seasonality, elasticity, outliers, brand velocity."""

from category_radar.analytics import (
    brand_velocity,
    cross_elasticity,
    detect_outliers,
    seasonality_analysis,
)


def test_seasonality_analysis():
    history = [
        {"snapshot_date": "2026-01-15", "price_eur": 100.0, "rank": 1},
        {"snapshot_date": "2026-01-20", "price_eur": 110.0, "rank": 2},
        {"snapshot_date": "2026-02-15", "price_eur": 120.0, "rank": 1},
        {"snapshot_date": "2026-03-15", "price_eur": 90.0, "rank": 1},
        {"snapshot_date": "2026-04-15", "price_eur": 130.0, "rank": 1},
    ]
    res = seasonality_analysis(history)
    assert "monthly" in res
    assert "01" in res["monthly"]
    assert "02" in res["monthly"]
    assert "03" in res["monthly"]
    assert "04" in res["monthly"]
    assert res["peak_month"] == "04"
    assert res["trough_month"] == "03"
    assert res["seasonality_strength_pct"] > 0
    assert "interpretation" in res


def test_cross_elasticity():
    # Insufficient history
    assert cross_elasticity([])["note"] == "Insufficient history"

    history = [
        # Day 1
        {
            "snapshot_date": "2026-10-01",
            "market": "DE",
            "brand": "Ninja",
            "model_key": "ninja:af400",
            "price_local": 200.0,
            "rank": 5,
        },
        {
            "snapshot_date": "2026-10-01",
            "market": "DE",
            "brand": "Philips",
            "model_key": "philips:na352",
            "price_local": 150.0,
            "rank": 2,
        },
        # Day 2: Ninja cuts price by 10% (to 180), rank improves to 2 (rank_change = 3)
        {
            "snapshot_date": "2026-10-02",
            "market": "DE",
            "brand": "Ninja",
            "model_key": "ninja:af400",
            "price_local": 180.0,
            "rank": 2,
        },
        # Philips keeps price same (150), rank drops to 4
        {
            "snapshot_date": "2026-10-02",
            "market": "DE",
            "brand": "Philips",
            "model_key": "philips:na352",
            "price_local": 150.0,
            "rank": 4,
        },
    ]
    res = cross_elasticity(history)
    assert "elasticity_by_brand" in res
    assert "Ninja" in res["elasticity_by_brand"]
    ninja_stats = res["elasticity_by_brand"]["Ninja"]
    assert ninja_stats["sample_size"] == 1
    assert "interpretation" in ninja_stats


def test_detect_outliers():
    rows = [{"market": "DE", "brand": f"Brand{i}", "title": f"Fryer {i}", "price_eur": 100.0} for i in range(10)]
    # Add an extreme undercut and an extreme premium
    rows.append({"market": "DE", "brand": "CheapBrand", "title": "Cheap Fryer", "price_eur": 15.0})
    rows.append({"market": "DE", "brand": "LuxuryBrand", "title": "Luxury Fryer", "price_eur": 500.0})

    res = detect_outliers(rows)
    assert "outliers" in res
    assert res["count"] > 0
    outlier_types = {o["type"] for o in res["outliers"]}
    assert "price_undercut" in outlier_types or "price_premium" in outlier_types


def test_brand_velocity():
    # Insufficient history
    assert brand_velocity([])["note"] == "Insufficient history"

    history = [
        # Day 1: BrandA, BrandB
        {"snapshot_date": "2026-10-01", "brand": "BrandA", "rank": 10},
        {"snapshot_date": "2026-10-01", "brand": "BrandB", "rank": 1},
        # Day 2: BrandA grows, BrandB disappears, BrandC enters
        {"snapshot_date": "2026-10-02", "brand": "BrandA", "rank": 1},
        {"snapshot_date": "2026-10-02", "brand": "BrandA", "rank": 2},
        {"snapshot_date": "2026-10-02", "brand": "BrandC", "rank": 3},
    ]
    res = brand_velocity(history)
    assert "velocity" in res
    vel = res["velocity"]
    assert vel["BrandC"]["status"] == "new_entrant"
    assert vel["BrandB"]["status"] == "departed"
    assert vel["BrandA"]["status"] == "rising_star"
    assert res["summary"]["new_entrants"] == 1
    assert res["summary"]["departed"] == 1
    assert res["summary"]["rising_stars"] == 1
