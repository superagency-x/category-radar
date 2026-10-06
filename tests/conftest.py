"""Shared fixtures, including a synthetic multi-market shelf for analytics tests.

The synthetic generator is used ONLY by tests (and `scripts/sample_db.py` for
dashboard development). It is never shipped as real market data.
"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from category_radar.config import load_config
from category_radar.models import RawListing

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def cfg():
    return load_config(ROOT / "config" / "airfryer.yaml")


MODELS = [
    ("Ninja", "Ninja AF400EU Foodi MAX Dual Zone", 175, 9.5, "Doppel-Heißluftfritteuse"),
    ("Ninja", "Ninja AF180EU Max Pro", 110, 6.2, "Heißluftfritteuse"),
    ("Cosori", "Cosori Turbo Blaze CAF-DC602", 120, 6.0, "Heißluftfritteuse"),
    ("Cosori", "Cosori Dual Blaze Twin Fry CAF-TF101S", 160, 10.0, "Doppel-Heißluftfritteuse"),
    ("Philips", "Philips NA352/00 Dual Basket 3000 Series", 125, 9.0, "Doppel-Heißluftfritteuse"),
    ("Philips", "Philips NA555/00 Steam 5000 Series", 185, 9.0, "Doppel-Heißluftfritteuse"),
    ("Tefal", "Tefal EY905D Dual Easy Fry & Grill", 95, 8.3, "Doppel-Heißluftfritteuse"),
    ("Tefal", "Tefal EY1308 Easy Fry Essential", 45, 3.5, "Heißluftfritteuse"),
    ("Severin", "Severin FR 2462 Black Line Single XXL", 40, 7.0, "Heißluftfritteuse"),
    ("Xiaomi", "Xiaomi Air Fryer Essential MAF13 6l", 48, 6.0, "Heißluftfritteuse"),
]
FX = {"EUR": 1.0, "CHF": 0.94, "PLN": 4.27, "CZK": 24.4, "HUF": 395.0}
CHANNEL = {"DE": "geizhals_de", "AT": "geizhals_at", "CH": "toppreise_ch", "PL": "ceneo_pl", "CZ": "alza_cz", "HU": "arukereso_hu"}


def synthetic_raw(market: str, seed: int = 0, price_shift: float = 1.0) -> list[RawListing]:
    rnd = random.Random(f"{market}-{seed}")
    order = MODELS[:]
    rnd.shuffle(order)
    cur = {"DE": "EUR", "AT": "EUR", "CH": "CHF", "PL": "PLN", "CZ": "CZK", "HU": "HUF"}[market]
    out = []
    for i, (brand, title, eur, cap, typ) in enumerate(order, start=1):
        price = round(eur * FX[cur] * rnd.uniform(0.9, 1.15) * price_shift, 2)
        out.append(RawListing(
            channel=CHANNEL[market], market=market, rank=i, title=title, url=f"https://example.test/{market}/{i}",
            price=price, currency=cur, offers=rnd.randint(1, 30), rating=round(rnd.uniform(3.8, 5), 2),
            rating_count=rnd.randint(0, 400), sponsored=(i == 1 and market in ("PL", "CZ")),
            specs_text=f"Typ: {typ} | Fassungsvermögen: {cap}l", capacity_text=f"{cap}l", power_text="1800W",
            type_text=typ, extra={"recent_purchases_90d": rnd.randint(5, 300)} if market == "PL" else {},
        ))
    return out
