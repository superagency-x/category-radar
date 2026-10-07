"""otto.de: Germany's #2 e-commerce platform and home appliance leader (EUR).

Shelf signals: retail price, UVP (strikethrough / was-price) for discount depth,
rating count, popularity badges ("Sehr beliebt", "Fast ausverkauft"),
structured spec description.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawListing
from .base import ChannelAdapter, first_int, parse_price, register, text

BASE = "https://www.otto.de"


@register("otto")
class OttoAdapter(ChannelAdapter):
    def parse(self, html: str, *, channel: str, market: str, currency: str, rank_offset: int = 0) -> list[RawListing]:
        soup = BeautifulSoup(html, "lxml")
        out: list[RawListing] = []
        rank = rank_offset

        for art in soup.select("article"):
            link_el = art.select_one('a[href*="/p/"]')
            if not link_el:
                continue

            brand_el = art.select_one('[class*="product-brand"], [data-qa*="brand"]')
            title_el = art.select_one('[class*="product-title"], [data-qa*="title"], h2, h3')
            rating_el = art.select_one('[class*="rating__amount"], [class*="rating"]')

            brand = text(brand_el)
            product_title = text(title_el)
            full_title = f"{brand} {product_title}".strip() if brand else product_title
            if not full_title:
                continue

            price = None
            uvp = None
            pricing_el = art.select_one("ofc-pricing-item-v1")
            if pricing_el and pricing_el.get("retail-price"):
                try:
                    price = round(int(str(pricing_el["retail-price"])) / 100.0, 2)
                    if pricing_el.get("suggested-retail-price"):
                        uvp = round(int(str(pricing_el["suggested-retail-price"])) / 100.0, 2)
                except (ValueError, TypeError):
                    pass

            if price is None:
                price_el = art.select_one('[class*="retailPrice"], [data-qa*="retailPrice"]')
                price = parse_price(text(price_el), decimal=",") if price_el else None
                uvp_el = art.select_one('[class*="wasPrice"], [class*="strikethrough"]')
                uvp = parse_price(text(uvp_el), decimal=",") if uvp_el else None

            if price is None:
                price_m = re.search(r"(\d+(?:,\d{2})?)\s*€", text(art))
                if price_m:
                    price = parse_price(price_m.group(1), decimal=",")

            if price is None:
                continue

            rating_count = first_int(text(rating_el)) if rating_el else None

            # Look for ratings stars or badges
            stars_el = art.select_one('[class*="rating__stars"], [aria-label*="Sterne"]')
            rating = None
            if stars_el and stars_el.get("aria-label"):
                aria_val = stars_el.get("aria-label")
                if isinstance(aria_val, str):
                    m = re.search(r"(\d+(?:[.,]\d+)?)\s*von\s*5", aria_val)
                    if m:
                        rating = float(m.group(1).replace(",", "."))

            all_txt = text(art)
            is_popular = "Sehr beliebt" in all_txt
            is_selling_fast = "Fast ausverkauft" in all_txt

            rank += 1
            out.append(
                RawListing(
                    channel=channel,
                    market=market,
                    rank=rank,
                    title=full_title,
                    url=urljoin(BASE, str(link_el["href"])),
                    price=price,
                    currency=currency,
                    brand_hint=brand or None,
                    rating=rating,
                    rating_count=rating_count,
                    specs_text=product_title,
                    extra={
                        "uvp_eur": uvp,
                        "discount_depth_pct": round(100 * (uvp - price) / uvp, 1)
                        if (uvp and price and uvp > price)
                        else None,
                        "badge_popular": is_popular,
                        "badge_low_stock": is_selling_fast,
                    },
                )
            )
        return out

    def next_page_url(self, html: str, current_url: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one('a[rel="next"], [data-qa="san_pagination_next"]')
        if link and link.get("href"):
            href = link["href"]
            if isinstance(href, str):
                return urljoin(BASE, href)
        return super().next_page_url(html, current_url)
