"""Channel adapter contract + shared parsing helpers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..models import RawListing

_REGISTRY: dict[str, type[ChannelAdapter]] = {}


def register(name: str) -> Callable[[type[ChannelAdapter]], type[ChannelAdapter]]:
    def deco(cls: type[ChannelAdapter]) -> type[ChannelAdapter]:
        cls.name = name
        _REGISTRY[name] = cls
        return cls

    return deco


def get_adapter(name: str) -> ChannelAdapter:
    if name not in _REGISTRY:
        raise KeyError(f"No adapter called {name!r}. Known: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)


class ChannelAdapter(ABC):
    """Turns one listing page of HTML into RawListings.

    Adapters are pure functions of HTML: no network, no state. That keeps them
    unit-testable against saved fixtures.
    """

    name: str = "base"
    base_url: str = ""

    @abstractmethod
    def parse(
        self, html: str, *, channel: str, market: str, currency: str, rank_offset: int = 0
    ) -> list[RawListing]: ...

    def next_page_url(self, html: str, current_url: str) -> str | None:
        """Default: <link rel=next> or <a rel=next>."""
        soup = BeautifulSoup(html, "lxml")
        el = soup.select_one('link[rel="next"], a[rel="next"]')
        if el and el.get("href"):
            href = el["href"]
            if isinstance(href, str):
                return urljoin(current_url, href)
        return None


# ---------------------------------------------------------------- helpers
def text(el: Tag | None) -> str:
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


def parse_price(raw: str | None, decimal: str = ",") -> float | None:
    """Parse '€ 1.159,00', 'CHF 1'299.90', '3 998,-', '29 200 Ft-tól' into a float."""
    if not raw:
        return None
    s = raw.replace("\xa0", " ").replace(" ", " ")
    s = re.sub(r",-|\.-", "", s)
    m = re.search(r"\d[\d\s.,']*", s)
    if not m:
        return None
    num = m.group(0).strip().replace(" ", "").replace("'", "")
    if decimal == ",":
        num = num.replace(".", "").replace(",", ".")
    else:
        num = num.replace(",", "")
    try:
        return round(float(num), 2)
    except ValueError:
        return None


def first_int(raw: str | None) -> int | None:
    if not raw:
        return None
    m = re.search(r"\d[\d\s\xa0]*", raw)
    return int(re.sub(r"\D", "", m.group(0))) if m else None


def first_float(raw: str | None) -> float | None:
    if not raw:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", raw)
    return float(m.group(0).replace(",", ".")) if m else None
