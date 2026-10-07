import pytest

from category_radar.models import RawListing
from category_radar.normalize import Normalizer

FX = {"EUR": 1.0, "CHF": 0.94, "PLN": 4.27, "CZK": 24.4, "HUF": 395.0}


@pytest.fixture
def norm(cfg):
    return Normalizer(cfg, FX)


@pytest.mark.parametrize(
    "title,brand,expected",
    [
        ("Ninja AF400EU Foodi MAX Dual Zone", "Ninja", "ninja:AF400"),
        ("NINJA Foodi MAX Dual Zone AF400EUWH", "Ninja", "ninja:AF400"),
        ("Cosori Turbo Tower Pro Smart (CAF-DC123S-DDER)", "Cosori", "cosori:CAFDC123"),
        ("PHILIPS Steam Airfryer Dual Basket 5000 Series (NA555/09)", "Philips", "philips:NA555"),
        ("Philips NA555/00 Steam 5000 Series", "Philips", "philips:NA555"),
        ("Tefal EY905B10 Dual Easy Fry & Grill 8,3 l", "Tefal", "tefal:EY905"),
        ("TEFAL Dual Easy Fry & Grill (EY905N)", "Tefal", "tefal:EY905"),
        ("Cosori Iconic Single", "Cosori", "cosori:iconic-single"),
    ],
)
def test_model_key_matches_across_markets(norm, title, brand, expected):
    assert norm.model_key(brand, title) == expected


@pytest.mark.parametrize(
    "title,hint,expected",
    [
        ("Tefal EY90JD Jamie Oliver Dual Drawer", None, "Tefal"),
        ("BRAUN HOUSEHOLD MultiFry 5 HF5073", "BRAUN HOUSEHOLD", "Braun"),
        ("Russell Hobbs SatisFry 4.3l", None, "Russell Hobbs"),
        ("Acme Turbo 5000", None, "Acme"),
        ("Gorenje AF1800ST Airfryer", "gorenje", "Gorenje"),
    ],
)
def test_brand(norm, title, hint, expected):
    assert norm.brand(title, hint) == expected


def test_capacity_and_power(norm):
    assert norm.capacity_l("10.8l (1x 4.3l, 1x 6.5l)") == 10.8
    assert norm.capacity_l("11 l") == 11.0
    assert norm.capacity_l(None, "Horkovzdušná fritéza - objem 8,3l / 2,2 kg") == 8.3
    assert norm.capacity_l("2470W") is None
    assert norm.power_w("2700 W") == 2700
    assert norm.power_w("2470W") == 2470


def test_normalize_end_to_end(norm):
    raw = RawListing(
        channel="ceneo_pl",
        market="PL",
        rank=1,
        title="Philips Airfryer 3000 Series NA352/00 Dual Basket",
        url="u",
        price=427.0,
        currency="PLN",
        specs_text="Typ: Airfryer | Pojemność: 9 l | Funkcje: okienko, zmywarka",
        capacity_text="9 l",
        power_text="2750 W",
    )
    [l] = norm.normalize([raw], run_id="r", snapshot_date="2026-10-06")
    assert l.price_eur == 100.0
    assert l.dual_zone and "dual_zone" in l.claims and "window" in l.claims and "easy_clean" in l.claims
    assert l.capacity_l == 9.0 and l.power_w == 2750 and l.model_key == "philips:NA352"


def test_channel_title_filter_drops_oil_fryers(norm):
    keep = RawListing(
        channel="arukereso_hu", market="HU", rank=1, title="Philips Airfryer 2000", url="u", price=29987, currency="HUF"
    )
    drop = RawListing(
        channel="arukereso_hu",
        market="HU",
        rank=2,
        title="Tefal FF2200 Minifryer olajsütő",
        url="u",
        price=17990,
        currency="HUF",
    )
    out = norm.normalize([keep, drop], run_id="r", snapshot_date="d")
    assert [l.title for l in out] == ["Philips Airfryer 2000"]
