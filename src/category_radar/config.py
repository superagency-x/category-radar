"""Loads and validates a category YAML file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass
class ChannelConfig:
    id: str
    market: str
    adapter: str
    type: str
    start_url: str
    max_pages: int = 1
    keep_keywords: str | None = None
    exclude_keywords: str | None = None


@dataclass
class CategoryConfig:
    id: str
    name: str
    base_currency: str
    crawl: dict[str, Any]
    markets: dict[str, dict[str, str]]
    channels: dict[str, ChannelConfig]
    brands: dict[str, list[str]]
    price_tiers: list[dict[str, Any]]
    claims: dict[str, dict[str, str]]
    needs: dict[str, dict[str, str]]
    reviews: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    def currency_of(self, market: str) -> str:
        return self.markets[market]["currency"]

    def language_of(self, market: str) -> str:
        return self.markets[market]["language"]


def load_config(path: str | Path) -> CategoryConfig:
    """Load config with Pydantic validation first, then convert to legacy format."""
    from .config_schema import load_config_schema

    # Validate with Pydantic schema
    try:
        schema = load_config_schema(path)
    except (ValueError, FileNotFoundError) as e:
        raise ConfigError(str(e)) from e

    # Convert to legacy dataclass format for backward compatibility
    path = Path(path)

    markets = {k: {"name": v.name, "currency": v.currency, "language": v.language} for k, v in schema.markets.items()}

    channels = {}
    for cid, ch in schema.channels.items():
        channels[cid] = ChannelConfig(
            id=cid,
            market=ch.market,
            adapter=ch.adapter,
            type=ch.type.value,
            start_url=str(ch.start_url),
            max_pages=ch.max_pages,
            keep_keywords=ch.keep_keywords,
            exclude_keywords=ch.exclude_keywords,
        )

    claims = {k: {"label": v.label, "pattern": v.pattern} for k, v in schema.claims.items()}
    needs = {k: {"label": v.label, "pattern": v.pattern} for k, v in schema.needs.items()}
    price_tiers = [{"name": t.name, "max_pct": t.max_pct} for t in schema.price_tiers]

    return CategoryConfig(
        id=schema.id,
        name=schema.name,
        base_currency=schema.base_currency,
        crawl=schema.crawl.model_dump(),
        markets=markets,
        channels=channels,
        brands=schema.brands,
        price_tiers=price_tiers,
        claims=claims,
        needs=needs,
        reviews=schema.reviews.model_dump(),
        path=path,
    )
