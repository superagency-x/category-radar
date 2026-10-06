"""Loads and validates a category YAML file."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


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
    keep_keywords: Optional[str] = None
    exclude_keywords: Optional[str] = None


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
    path: Optional[Path] = None

    def currency_of(self, market: str) -> str:
        return self.markets[market]["currency"]

    def language_of(self, market: str) -> str:
        return self.markets[market]["language"]


def load_config(path: str | Path) -> CategoryConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    for key in ("category", "markets", "channels", "claims", "needs"):
        if key not in raw:
            raise ConfigError(f"{path}: missing top-level section '{key}'")

    markets = raw["markets"]
    channels: dict[str, ChannelConfig] = {}
    for cid, c in raw["channels"].items():
        if c.get("market") not in markets:
            raise ConfigError(f"channel {cid}: unknown market {c.get('market')!r}")
        if "start_url" not in c:
            raise ConfigError(f"channel {cid}: missing start_url")
        channels[cid] = ChannelConfig(
            id=cid,
            market=c["market"],
            adapter=c.get("adapter", cid.split("_")[0]),
            type=c.get("type", "price_comparison"),
            start_url=c["start_url"],
            max_pages=int(c.get("max_pages", 1)),
            keep_keywords=c.get("keep_keywords"),
            exclude_keywords=c.get("exclude_keywords"),
        )

    for section in ("claims", "needs"):
        for key, spec in raw[section].items():
            try:
                re.compile(spec["pattern"])
            except re.error as exc:  # fail fast on a broken regex in YAML
                raise ConfigError(f"{section}.{key}: invalid regex: {exc}") from exc

    cat = raw["category"]
    return CategoryConfig(
        id=cat["id"],
        name=cat["name"],
        base_currency=cat.get("base_currency", "EUR"),
        crawl=raw.get("crawl", {}),
        markets=markets,
        channels=channels,
        brands=raw.get("brands", {}),
        price_tiers=raw.get("price_tiers", []),
        claims=raw["claims"],
        needs=raw["needs"],
        reviews=raw.get("reviews", {}),
        path=path,
    )
