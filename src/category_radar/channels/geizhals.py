"""geizhals.de / geizhals.at: DACH's dominant price-comparison engine.

Shelf signals: lowest offer price, number of offers (distribution breadth),
user rating + count, editorial test score, 30-day price change badge,
structured specs (type, power, capacity).
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..models import RawListing
from .base import ChannelAdapter, first_float, first_int, parse_price, register, text


@register("geizhals")
class GeizhalsAdapter(ChannelAdapter):
    def parse(self, html, *, channel, market, currency, rank_offset=0):
        soup = BeautifulSoup(html, "lxml")
        base = "https://geizhals.at/" if market == "AT" else "https://geizhals.de/"
        out: list[RawListing] = []
        for i, card in enumerate(soup.select(".galleryview__item"), start=1):
            name_el = card.select_one(".galleryview__name-link")
            if not name_el:
                continue
            href = (name_el.get("href") or "").split("?")[0]
            specs = {
                text(dt): text(dt.find_next_sibling("dd"))
                for dt in card.select("dl dt")
            }
            stars = card.select_one(".stars-rating")
            rating: Optional[float] = None
            if stars and stars.get("style"):
                m = re.search(r"--stars-rating:\s*([\d.]+)", stars["style"])
                rating = round(float(m.group(1)), 2) if m else None
            discount = text(card.select_one(".badge--discount"))
            ext = re.search(r"-a(\d+)\.html", href)
            out.append(RawListing(
                channel=channel,
                market=market,
                rank=rank_offset + i,
                title=text(name_el),
                url=urljoin(base, href),
                price=parse_price(text(card.select_one(".price")), decimal=","),
                currency=currency,
                external_id=ext.group(1) if ext else None,
                offers=first_int(text(card.select_one(".galleryview__offercount-link"))),
                rating=rating,
                rating_count=first_int(text(card.select_one(".stars-rating-label-bottom"))),
                specs_text=" | ".join(f"{k}: {v}" for k, v in specs.items()),
                capacity_text=specs.get("Fassungsvermögen"),
                power_text=specs.get("Leistung"),
                type_text=specs.get("Typ"),
                extra={
                    "mpn": text(card.select_one(".galleryview__mpn")) or None,
                    "test_score": first_int(text(card.select_one(".metascore-badge"))),
                    "price_change_30d_pct": first_float(discount) * (-1 if "-" in discount else 1) if discount else None,
                },
            ))
        return out

    def next_page_url(self, html, current_url):
        nxt = super().next_page_url(html, current_url)
        if nxt:
            return nxt
        soup = BeautifulSoup(html, "lxml")
        m = re.search(r"[?&]pg=(\d+)", current_url)
        page = int(m.group(1)) if m else 1
        link = soup.find("a", href=re.compile(rf"[?&]pg={page + 1}\b"))
        if link:
            host = f"{urlparse(current_url).scheme}://{urlparse(current_url).netloc}/"
            return urljoin(host, link["href"])
        return None
