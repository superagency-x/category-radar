"""alza.cz: Czechia's largest e-commerce retailer (CZK).

Used for CZ because heureka.cz serves an interactive bot challenge, which this
tool deliberately does not bypass. The listing URL is Alza's own
"best-sellers" ordering, so rank = bestseller rank. The long description
line is the brand's own positioning copy, which is ideal for claim analysis.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawListing
from .base import ChannelAdapter, first_float, first_int, parse_price, register, text

BASE = "https://www.alza.cz"


@register("alza")
class AlzaAdapter(ChannelAdapter):
    def parse(self, html, *, channel, market, currency, rank_offset=0):
        soup = BeautifulSoup(html, "lxml")
        out: list[RawListing] = []
        for i, box in enumerate(soup.select("div.browsingitem"), start=1):
            name_el = box.select_one("a.name")
            if not name_el:
                continue
            desc = text(box.select_one(".Description"))
            rating_label = (
                (box.select_one(".star-rating-wrapper") or {}).get("aria-label", "")
                if box.select_one(".star-rating-wrapper")
                else ""
            )
            cap = re.search(r"objem\s*(\d+(?:[.,]\d+)?)\s*l", desc, re.IGNORECASE) or re.search(
                r"(\d+(?:[.,]\d+)?)\s*l\b", text(name_el), re.IGNORECASE
            )
            power = re.search(r"příkon\s*(\d{3,4})\s*W", desc, re.IGNORECASE) or re.search(r"(\d{3,4})\s*W\b", desc)
            sponsored = bool(box.select_one(".sponsoredcommodity")) or "Sponzorováno" in text(
                box.select_one(".box-recommendation")
            )
            price_el = (
                box.select_one(".js-price-box__primary-price__value")
                or box.select_one(".price-box__price")
                or box.select_one(".price")
            )
            coupon = text(box.select_one(".coupon-block__price"))
            out.append(
                RawListing(
                    channel=channel,
                    market=market,
                    rank=rank_offset + i,
                    title=text(name_el),
                    url=urljoin(BASE, name_el.get("href", "")),
                    price=parse_price(text(price_el), decimal=","),
                    currency=currency,
                    external_id=box.get("data-id"),
                    rating=first_float(text(box.select_one(".star-rating-block__value"))) or first_float(rating_label),
                    rating_count=first_int(text(box.select_one(".star-rating-block__count"))),
                    sponsored=sponsored,
                    specs_text=desc,
                    capacity_text=f"{cap.group(1)}l" if cap else None,
                    power_text=f"{power.group(1)}W" if power else None,
                    type_text=desc.split(" - ")[0] if " - " in desc else None,
                    extra={
                        "order_code": box.get("data-code"),
                        "coupon_price": parse_price(coupon, decimal=",") if coupon else None,
                        "in_stock": "Skladem" in text(box.select_one(".avl")),
                    },
                )
            )
        return out

    def next_page_url(self, html, current_url):
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one('a.next, a[rel="next"], link[rel="next"]')
        if link and link.get("href"):
            return urljoin(BASE, link["href"])
        m = re.search(r"-p(\d+)\.htm", current_url)
        page = int(m.group(1)) if m else 1
        link = soup.find("a", href=re.compile(rf"-p{page + 1}\.htm"))
        return urljoin(BASE, link["href"]) if link else None
