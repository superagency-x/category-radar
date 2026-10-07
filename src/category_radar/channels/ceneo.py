"""ceneo.pl: Poland's leading price-comparison engine (PLN).

Ceneo exposes an unusually strong demand signal: "N kupionych ostatnio"
(units bought via Ceneo in the last 90 days), stored as
data-productrecentlypurchased. Promoted listings carry a "Polecany" label.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawListing
from .base import ChannelAdapter, first_float, first_int, parse_price, register, text

BASE = "https://www.ceneo.pl"


@register("ceneo")
class CeneoAdapter(ChannelAdapter):
    def parse(self, html, *, channel, market, currency, rank_offset=0):
        soup = BeautifulSoup(html, "lxml")
        out: list[RawListing] = []
        for i, row in enumerate(soup.select("div.cat-prod-row"), start=1):
            pid = row.get("data-pid") or row.get("data-productid")
            name_el = row.select_one(".cat-prod-row__name .font-bold") or row.select_one(".cat-prod-row__name a")
            if not pid or not name_el:
                continue
            params = {}
            for li in row.select("ul.prod-params li"):
                t = text(li)
                if ":" in t:
                    k, v = t.split(":", 1)
                    params[k.strip()] = v.strip()
            price = None
            if row.get("data-price"):
                try:
                    price = float(row["data-price"])
                except ValueError:
                    price = None
            if price is None:
                price = parse_price(text(row.select_one(".cat-prod-row__price .price")), decimal=",")
            bought = row.get("data-productrecentlypurchased")
            out.append(
                RawListing(
                    channel=channel,
                    market=market,
                    rank=rank_offset + i,
                    title=text(name_el),
                    url=urljoin(BASE, "/" + pid),
                    price=price,
                    currency=currency,
                    external_id=pid,
                    brand_hint=row.get("data-brand") or None,
                    offers=first_int(text(row.select_one(".shop-numb"))),
                    rating=first_float(text(row.select_one(".product-score"))),
                    rating_count=first_int(text(row.select_one(".prod-review__qo"))),
                    sponsored=bool(row.select_one(".cat-prod-row__name .recommended-label")),
                    specs_text=" | ".join(f"{k}: {v}" for k, v in params.items()),
                    capacity_text=params.get("Pojemność"),
                    power_text=params.get("Moc"),
                    type_text=params.get("Typ"),
                    extra={
                        "recent_purchases_90d": int(bought) if bought and bought.isdigit() else None,
                        "variants": first_int(text(row.select_one(".cat-prod-row__variants"))),
                    },
                )
            )
        return out

    def next_page_url(self, html, current_url):
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one("a.pagination__next") or soup.find("a", string=re.compile(r"Więcej produktów|Następna"))
        if link and link.get("href"):
            return urljoin(BASE, link["href"])
        return None
