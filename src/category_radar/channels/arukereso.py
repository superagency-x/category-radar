"""arukereso.hu: Hungary's leading price-comparison engine (HUF).

The category mixes classic oil fryers and hot-air fryers; the channel config
filters titles with `include_if_title_matches`. "brandbox" cards are paid
brand placements and are flagged as sponsored.

Selectors are anchored on the product link pattern (/<category>-c<id>/<brand>/
<slug>-p<id>) plus text patterns ("... Ft-tól", "... ajánlat"), which is
robust to layout changes.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawListing
from .base import ChannelAdapter, first_float, first_int, parse_price, register, text

BASE = "https://www.arukereso.hu"
PRODUCT_HREF = re.compile(r"arukereso\.hu/[^/]+-c\d+/([^/]+)/[^/?#]+-p(\d+)")


@register("arukereso")
class ArukeresoAdapter(ChannelAdapter):
    def parse(self, html, *, channel, market, currency, rank_offset=0):
        soup = BeautifulSoup(html, "lxml")
        out: list[RawListing] = []
        rank = rank_offset
        for box in soup.select(".product-box"):
            name_el = box.select_one(".name h2 a") or box.select_one("h2 a")
            if not name_el:
                continue
            if "buyingguide" in name_el.get("href", "").lower():
                continue
            title = text(name_el)
            all_text = text(box)
            # product URL: prefer a direct product link over ad-redirect links
            href = None
            brand_slug = pid = None
            for a in box.find_all("a", href=True):
                m = PRODUCT_HREF.search(urljoin(BASE, a["href"]))
                if m:
                    href, brand_slug, pid = urljoin(BASE, a["href"]).split("#")[0], m.group(1), m.group(2)
                    break
            akpid = box.get("data-akpid", "")
            if not pid:
                m = re.search(r"p(\d+)", akpid)
                pid = m.group(1) if m else None
            price_m = re.search(r"(\d{1,3}(?:[ \xa0]\d{3})+|\d+)\s*Ft-tól", all_text) or re.search(
                r"(\d{1,3}(?:[ \xa0]\d{3})+|\d+)\s*Ft\b", all_text)
            offers_m = re.search(r"(\d+)\s*ajánlat", all_text)
            rating_el = box.select_one("[class*=rating] [class*=value], .rating-value")
            rank += 1
            out.append(RawListing(
                channel=channel,
                market=market,
                rank=rank,
                title=title,
                url=href or urljoin(BASE, name_el.get("href", "")),
                price=parse_price(price_m.group(1), decimal=",") if price_m else None,
                currency=currency,
                external_id=pid,
                brand_hint=brand_slug.replace("-", " ") if brand_slug else None,
                offers=int(offers_m.group(1)) if offers_m else (1 if price_m else None),
                rating=first_float(text(rating_el)) if rating_el else None,
                sponsored="brandbox" in (box.get("class") or []) or "PADS" in akpid,
                specs_text=text(box.select_one(".description, .short-description, .properties")),
            ))
        return out

    def next_page_url(self, html, current_url):
        soup = BeautifulSoup(html, "lxml")
        link = soup.find("a", string=re.compile(r"Következő"))
        if link and link.get("href"):
            return urljoin(BASE, link["href"])
        return super().next_page_url(html, current_url)
