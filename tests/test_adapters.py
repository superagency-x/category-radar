from pathlib import Path

import pytest

from category_radar.channels import get_adapter
from category_radar.channels.base import parse_price

FX = Path(__file__).parent / "fixtures"


def parse(adapter, fixture, market, currency):
    return get_adapter(adapter).parse((FX / fixture).read_text(encoding="utf-8"),
                                      channel=f"{adapter}_{market.lower()}", market=market, currency=currency)


@pytest.mark.parametrize("raw,dec,expected", [
    ("€ 159,00", ",", 159.0),
    ("€ 1.159,90", ",", 1159.9),
    ("CHF 1'299.90", ".", 1299.9),
    ("CHF 75.90", ".", 75.9),
    ("3\xa0998,-", ",", 3998.0),
    ("29 200 Ft-tól", ",", 29200.0),
    ("od 1 049,99 zł", ",", 1049.99),
    ("", ",", None),
    (None, ",", None),
])
def test_parse_price(raw, dec, expected):
    assert parse_price(raw, decimal=dec) == expected


def test_geizhals():
    items = parse("geizhals", "geizhals.html", "DE", "EUR")
    assert len(items) == 3
    a = items[0]
    assert a.title == "Ninja AF500EU Foodi FlexDrawer"
    assert a.price == 159.0 and a.offers == 29
    assert a.rating == 4.86 and a.rating_count == 410
    assert a.capacity_text == "10.4l" and a.power_text == "2470W"
    assert a.extra["test_score"] == 80
    assert a.url == "https://geizhals.de/ninja-af500eu-foodi-flexdrawer-a3337334.html"
    assert a.external_id == "3337334"
    assert items[1].extra["price_change_30d_pct"] == -6.0
    assert items[2].rating is None and items[2].extra["mpn"] == "19170"
    assert [i.rank for i in items] == [1, 2, 3]


def test_toppreise():
    items = parse("toppreise", "toppreise.html", "CH", "CHF")
    assert [i.title for i in items] == ["MEDION MD 11780 (50072992)", "PHILIPS Airfryer 3000 Series, Schwarz (NA330/00)"]
    assert items[0].price == 75.9 and items[0].offers == 18
    assert items[0].capacity_text == "5l" and items[0].power_text == "1500W"
    assert items[0].brand_hint == "MEDION"
    assert items[1].extra["is_variant"] is True
    assert items[1].url.endswith("-p825129")


def test_ceneo():
    items = parse("ceneo", "ceneo.html", "PL", "PLN")
    assert len(items) == 2
    a, b = items
    assert a.title.startswith("Tefal frytkownica") and a.brand_hint == "Tefal"
    assert a.price == 449 and a.offers == 18 and a.rating == 4.8 and a.rating_count == 8
    assert a.sponsored is True and b.sponsored is False
    assert a.extra["recent_purchases_90d"] == 69
    assert a.capacity_text == "11 l" and a.power_text == "2700 W"
    assert b.price == 1049.99 and b.rating_count == 214
    nxt = get_adapter("ceneo").next_page_url((FX / "ceneo.html").read_text(), "https://www.ceneo.pl/Frytkownice/Typ:Airfryer.htm")
    assert nxt == "https://www.ceneo.pl/Frytkownice/Typ:Airfryer;0020-30-0-0-1.htm"


def test_alza():
    items = parse("alza", "alza.html", "CZ", "CZK")
    a, b = items
    assert a.title == "Tefal EY905B10 Dual Easy Fry & Grill 8,3 l"
    assert a.price == 3998 and a.rating == 4.9 and a.rating_count == 830
    assert a.capacity_text == "8,3l" and a.power_text == "2700W"
    assert a.extra["coupon_price"] == 3198 and a.extra["in_stock"] is True
    assert not a.sponsored and b.sponsored
    assert "šetří" in a.specs_text


def test_arukereso_filters_sponsored_and_links():
    items = parse("arukereso", "arukereso.html", "HU", "HUF")
    assert len(items) == 3
    assert items[0].sponsored and items[0].price == 34990 and items[0].offers == 6
    assert items[0].external_id == "1321286044" and items[0].brand_hint == "gorenje"
    assert items[1].url.startswith("https://www.arukereso.hu/olajsuto-c4109/philips/")
    nxt = get_adapter("arukereso").next_page_url((FX / "arukereso.html").read_text(), "https://www.arukereso.hu/olajsuto-c4109/")
    assert nxt.endswith("?start=25")
