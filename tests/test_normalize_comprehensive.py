"""Comprehensive normalization tests."""

from category_radar.normalize import Normalizer, slug


def test_slug_handles_unicode():
    assert slug("Ninja Air Fryer") == "ninja-air-fryer"
    assert slug("Tefal Easy Fry") == "tefal-easy-fry"
    assert slug("Philips NA352/00") == "philips-na352-00"


def test_model_key_extraction():
    norm = Normalizer(cfg=None, fx_to_eur={})

    # Direct model code
    assert norm.model_key("Ninja", "Ninja AF400EU Foodi") == "ninja:AF400"
    assert norm.model_key("Philips", "Philips NA352/00 Dual Basket") == "philips:NA352"

    # Fallback to words
    key = norm.model_key("Unknown", "Some Fryer 2000W Black")
    assert "unknown" in key


def test_capacity_extraction():
    norm = Normalizer(cfg=None, fx_to_eur={})

    assert norm.capacity_l("5l") == 5.0
    assert norm.capacity_l("5.5 l") == 5.5
    assert norm.capacity_l("8,3l") == 8.3
    assert norm.capacity_l("10.4 Liter") == 10.4
    assert norm.capacity_l("invalid") is None
    assert norm.capacity_l("100l") is None  # Out of range


def test_power_extraction():
    norm = Normalizer(cfg=None, fx_to_eur={})

    assert norm.power_w("1800W") == 1800
    assert norm.power_w("2 000 W") == 2000
    assert norm.power_w("2470W") == 2470
    assert norm.power_w("400W") is None  # Too low
    assert norm.power_w("5000W") is None  # Too high


def test_currency_conversion():
    norm = Normalizer(cfg=None, fx_to_eur={"EUR": 1.0, "PLN": 4.27, "CHF": 0.94})

    assert norm.to_eur(100.0, "EUR") == 100.0
    assert norm.to_eur(427.0, "PLN") == 100.0
    assert norm.to_eur(94.0, "CHF") == 100.0
    assert norm.to_eur(None, "EUR") is None
