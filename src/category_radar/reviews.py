"""Review collection for market-needs mining.

Site-agnostic by design: product pages on most shops and comparison engines
publish reviews as schema.org structured data (JSON-LD or microdata) for
Google rich results. Reading that layer instead of the visual markup means
one extractor works across all channels and survives redesigns.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Optional

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


def _walk(node: Any) -> Iterable[dict]:
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _rating(r: dict) -> Optional[float]:
    rr = r.get("reviewRating") or {}
    val = rr.get("ratingValue") if isinstance(rr, dict) else None
    try:
        best = float(rr.get("bestRating", 5)) if isinstance(rr, dict) else 5.0
        return round(float(str(val).replace(",", ".")) * 5.0 / best, 2) if val is not None else None
    except (TypeError, ValueError):
        return None


def extract_reviews(html: str, limit: int = 50) -> list[tuple[Optional[float], str]]:
    """Return [(rating 0..5 or None, text)] found in structured data."""
    soup = BeautifulSoup(html, "lxml")
    found: list[tuple[Optional[float], str]] = []

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "null")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _walk(data):
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if "Review" in types:
                body = " ".join(
                    str(node.get(k, "")) for k in ("name", "reviewBody", "description", "positiveNotes", "negativeNotes")
                    if isinstance(node.get(k), str)
                ).strip()
                if len(body) > 15:
                    found.append((_rating(node), body))

    if not found:  # microdata fallback
        for el in soup.select('[itemprop="review"]'):
            body_el = el.select_one('[itemprop="reviewBody"], [itemprop="description"]')
            if body_el:
                txt = body_el.get_text(" ", strip=True)
                rv = el.select_one('[itemprop="ratingValue"]')
                rating = None
                if rv is not None:
                    try:
                        rating = float((rv.get("content") or rv.get_text()).replace(",", "."))
                    except ValueError:
                        rating = None
                if len(txt) > 15:
                    found.append((rating, txt))

    seen, unique = set(), []
    for rating, txt in found:
        key = txt[:120]
        if key not in seen:
            seen.add(key)
            unique.append((rating, txt))
    return unique[:limit]
