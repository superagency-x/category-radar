"""toppreise.ch: Switzerland's leading price-comparison engine (CHF)."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawListing
from .base import ChannelAdapter, first_int, parse_price, register, text

BASE = "https://www.toppreise.ch"


@register("toppreise")
class ToppreiseAdapter(ChannelAdapter):
    def parse(self, html, *, channel, market, currency, rank_offset=0):
        soup = BeautifulSoup(html, "lxml")
        out: list[RawListing] = []
        rank = rank_offset
        for card in soup.select(".Plugin_Product.mixedBrowsingList"):
            name_el = card.select_one(".product-name a.bold") or card.select_one("a.bold")
            if not name_el:
                continue
            rank += 1
            href = (name_el.get("href") or "").split("?")[0]
            price_el = card.select_one(".productPrice .Plugin_Price") or card.select_one(".Plugin_Price")
            features = text(card.select_one("a.product-features"))
            brand_img = card.select_one(".manufacturer-image img")
            ext = re.search(r"-p(\d+)$", href)
            cap = re.search(r"(\d+(?:\.\d+)?)\s*L\b", features)
            power = re.search(r"(\d{3,4})\s*W\b", features)
            out.append(RawListing(
                channel=channel,
                market=market,
                rank=rank,
                title=text(name_el),
                url=urljoin(BASE, href),
                price=parse_price(text(price_el), decimal="."),
                currency=currency,
                external_id=ext.group(1) if ext else None,
                brand_hint=brand_img.get("alt") if brand_img else None,
                offers=first_int(text(card.select_one(".offers"))),
                specs_text=features,
                capacity_text=f"{cap.group(1)}l" if cap else None,
                power_text=f"{power.group(1)}W" if power else None,
                type_text=features.split(",")[0] if features else None,
                extra={"is_variant": "f_collection" in (card.get("class") or [])},
            ))
        return out

    def next_page_url(self, html, current_url):
        m = re.search(r"[?&]p=(\d+)", current_url)
        nxt = (int(m.group(1)) + 1) if m else 1
        soup = BeautifulSoup(html, "lxml")
        link = soup.find("a", class_="f_pagination", href=re.compile(rf"[?&]p={nxt}\b"))
        return urljoin(BASE, link["href"]) if link else None
