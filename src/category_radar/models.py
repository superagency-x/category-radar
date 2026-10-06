"""Core data contracts.

Every channel adapter emits `RawListing` objects. Everything downstream
(normalisation, storage, analytics) depends only on these contracts, never on
a specific website. That is what makes a new channel a ~60-line plug-in.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class RawListing:
    """One product as it appears on one channel's category shelf, as scraped."""

    channel: str
    market: str
    rank: int                       # position on the popularity-sorted shelf (1 = top)
    title: str
    url: str
    price: Optional[float]          # in local currency
    currency: str
    external_id: Optional[str] = None
    brand_hint: Optional[str] = None
    offers: Optional[int] = None    # number of shops / offers (distribution breadth)
    rating: Optional[float] = None  # 0..5
    rating_count: Optional[int] = None
    sponsored: bool = False         # paid placement on the shelf
    specs_text: str = ""            # free-text spec line / description used for claim detection
    capacity_text: Optional[str] = None
    power_text: Optional[str] = None
    type_text: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)  # channel-specific signals

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Listing:
    """A normalised, enriched listing ready for storage and analysis."""

    run_id: str
    snapshot_date: str
    channel: str
    channel_type: str
    market: str
    rank: int
    title: str
    url: str
    external_id: Optional[str]
    brand: str
    model_key: str                  # cross-market product key (brand + model code)
    price_local: Optional[float]
    currency: str
    price_eur: Optional[float]
    offers: Optional[int]
    rating: Optional[float]
    rating_count: Optional[int]
    sponsored: bool
    capacity_l: Optional[float]
    power_w: Optional[int]
    dual_zone: bool
    claims: list[str]
    extra: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Review:
    channel: str
    market: str
    model_key: str
    brand: str
    rating: Optional[float]
    text: str
    language: str
