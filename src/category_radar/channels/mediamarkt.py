"""mediamarkt.de: Germany's leading consumer electronics omnichannel retailer (EUR).

Shelf signals: shelf rank, retail price, UVP (strikethrough / RRP), discount depth %,
customer rating (Bazaarvoice verified stars + count), stock and delivery flags.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawListing
from .base import ChannelAdapter, first_int, parse_price, register, text

BASE = "https://www.mediamarkt.de"


@register("mediamarkt")
class MediaMarktAdapter(ChannelAdapter):
    def parse(self, html: str, *, channel: str, market: str, currency: str, rank_offset: int = 0) -> list[RawListing]:
        soup = BeautifulSoup(html, "lxml")
        out: list[RawListing] = []
        rank = rank_offset

        for card in soup.select('[data-test="mms-product-card"]'):
            title_el = card.select_one(
                '[data-test="product-title"], [data-test="mms-router-link-product-list-item-link"]'
            )
            link_el = card.select_one('a[data-test*="product-list-item-link"], a[data-test*="product-image-wrapper"]')

            if not title_el or not link_el:
                continue

            title = text(title_el)
            if not title:
                continue

            # Price & UVP extraction
            uvp_el = card.select_one('[data-test*="strike-price-type-rrp"], [data-test*="strike-price"]')
            uvp = parse_price(text(uvp_el), decimal=",") if uvp_el else None

            # Current selling price
            price = None
            price_box = card.select_one('[data-test="cofr-price"], [data-test="mms-price"]')
            if price_box:
                for sp in price_box.find_all(["span", "div"]):
                    st = text(sp)
                    if "€" in st and "UVP" not in st and "Raten" not in st and "MwSt" not in st:
                        p_val = parse_price(st, decimal=",")
                        if p_val and p_val != uvp:
                            price = p_val
                            break

            if price is None:
                all_t = text(card)
                matches = re.findall(r"(\d{1,4}(?:,\d{2}|,–)?)\s*€", all_t)
                for m in matches:
                    p_val = parse_price(m, decimal=",")
                    if p_val and p_val != uvp:
                        price = p_val
                        break

            if price is None:
                continue

            # Rating stars and count
            rating_box = card.select_one('[data-test="mms-customer-rating-container"]')
            rating = None
            if rating_box:
                full_stars = len(rating_box.select('[data-test="mms-fully-rated-star"]'))
                half_stars = len(rating_box.select('[data-test="mms-partial-rated-star"]'))
                rating = round(full_stars + 0.5 * half_stars, 2) if (full_stars or half_stars) else None

            count_el = card.select_one('[data-test="mms-customer-rating-count"]')
            rating_count = first_int(text(count_el)) if count_el else None

            rank += 1
            out.append(
                RawListing(
                    channel=channel,
                    market=market,
                    rank=rank,
                    title=title,
                    url=urljoin(BASE, link_el["href"]),
                    price=price,
                    currency=currency,
                    rating=rating,
                    rating_count=rating_count,
                    specs_text=title,
                    extra={
                        "uvp_eur": uvp,
                        "discount_depth_pct": round(100 * (uvp - price) / uvp, 1)
                        if (uvp and price and uvp > price)
                        else None,
                        "retailer": "MediaMarkt",
                    },
                )
            )
        return out

    def next_page_url(self, html: str, current_url: str) -> str | None:
        m = re.search(r"[?&]page=(\d+)", current_url)
        page = int(m.group(1)) if m else 1
        next_page = page + 1
        if "page=" in current_url:
            return re.sub(r"page=\d+", f"page={next_page}", current_url)
        sep = "&" if "?" in current_url else "?"
        return f"{current_url}{sep}page={next_page}"
