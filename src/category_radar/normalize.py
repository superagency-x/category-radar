"""Turn RawListings into comparable, enriched Listings.

* brand resolution (dictionary + fallback)
* cross-market model key (Ninja AF400EU / AF400EUWH / AF400EUCP -> ninja:AF400)
* capacity (litres) and power (watts) extraction
* claim tagging from a multilingual regex taxonomy defined in the YAML
* currency conversion to EUR
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

from .config import CategoryConfig
from .models import Listing, RawListing

MODEL_CODE = re.compile(r"\b([A-Z]{1,4}-?[A-Z]{0,4}\d{2,5}[A-Z0-9]*(?:[/-][A-Z0-9]+)*)\b")
MODEL_CORE = re.compile(r"^([A-Z]{1,4})([A-Z]{0,4})(\d{2,5})")
STOPWORDS = {
    "heißluftfritteuse", "heissluftfritteuse", "doppel", "airfryer", "air", "fryer", "frytkownica",
    "beztłuszczowa", "horkovzdušná", "fritéza", "forrólevegős", "sütő", "schwarz", "black", "weiß",
    "weiss", "white", "grau", "grey", "gray", "silber", "silver", "edelstahl", "gold", "kupfer",
    "bronze", "czarny", "černá", "fekete", "fehér", "inox", "l", "the", "mit", "und", "with",
}


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class Normalizer:
    def __init__(self, cfg: CategoryConfig, fx_to_eur: dict[str, float]):
        self.cfg = cfg
        self.fx = fx_to_eur  # units of currency per 1 EUR (ECB convention)
        self._brand_patterns = [
            (canon, re.compile(r"\b(" + "|".join(re.escape(a) for a in aliases) + r")\b", re.I))
            for canon, aliases in sorted(cfg.brands.items(), key=lambda kv: -max(len(a) for a in kv[1]))
        ]
        self._claims = {k: re.compile(v["pattern"], re.I) for k, v in cfg.claims.items()}

    # -- fields ------------------------------------------------------------
    def brand(self, title: str, hint: Optional[str]) -> str:
        for candidate in (title, hint or ""):
            for canon, pat in self._brand_patterns:
                if pat.search(candidate):
                    return canon
        if hint:
            return hint.strip().title()
        first = re.split(r"\s+", title.strip())[0] if title.strip() else "Unknown"
        return first.capitalize()

    @staticmethod
    def model_key(brand: str, title: str, extra_code: Optional[str] = None) -> str:
        candidates = []
        for src in (extra_code or "", title):
            candidates += MODEL_CODE.findall(src.upper())
        for code in candidates:
            m = MODEL_CORE.match(code.replace("-", ""))
            if not m:
                continue
            letters = m.group(1) + m.group(2)
            if letters in {"L", "W", "XL", "XXL", "KG", "V", "IN"}:
                continue
            core = f"{letters}{m.group(3)}"
            if len(core) >= 4:
                return f"{slug(brand)}:{core}"
        words = [w for w in re.findall(r"[\wäöüßąćęłńóśźżčďěňřšťůžáéíóúýőű]+", title.lower())
                 if w not in STOPWORDS and w != brand.lower() and not re.fullmatch(r"\d+([.,]\d+)?l?", w)]
        return f"{slug(brand)}:{slug(' '.join(words[:3]))}"

    @staticmethod
    def capacity_l(*texts: Optional[str]) -> Optional[float]:
        for t in texts:
            if not t:
                continue
            m = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:l|L|litr|liter|litrů|literes)\b", t)
            if m:
                val = float(m.group(1).replace(",", "."))
                if 0.5 <= val <= 40:
                    return val
        return None

    @staticmethod
    def power_w(*texts: Optional[str]) -> Optional[int]:
        for t in texts:
            if not t:
                continue
            m = re.search(r"(\d{3,4})\s*W\b", t)
            if m and 500 <= int(m.group(1)) <= 4000:
                return int(m.group(1))
        return None

    def claims_of(self, raw: RawListing) -> list[str]:
        blob = " ".join(filter(None, [raw.title, raw.specs_text, raw.type_text, raw.capacity_text]))
        return [k for k, pat in self._claims.items() if pat.search(blob)]

    def to_eur(self, amount: Optional[float], currency: str) -> Optional[float]:
        if amount is None:
            return None
        if currency == "EUR":
            return round(amount, 2)
        rate = self.fx.get(currency)
        return round(amount / rate, 2) if rate else None

    @staticmethod
    def in_category(ch, r: RawListing) -> bool:
        """Mixed categories: keep explicit matches, drop explicit non-matches, keep the rest."""
        blob = f"{r.title} {r.specs_text}"
        if ch.keep_keywords and re.search(ch.keep_keywords, blob, re.I):
            return True
        if ch.exclude_keywords and re.search(ch.exclude_keywords, blob, re.I):
            return False
        return True

    # -- main --------------------------------------------------------------
    def normalize(self, raws: Iterable[RawListing], *, run_id: str, snapshot_date: str) -> list[Listing]:
        out: list[Listing] = []
        for r in raws:
            ch = self.cfg.channels[r.channel]
            if not self.in_category(ch, r):
                continue
            brand = self.brand(r.title, r.brand_hint)
            claims = self.claims_of(r)
            capacity = self.capacity_l(r.capacity_text, r.title, r.specs_text)
            dual = (
                "dual_zone" in claims
                or bool(r.capacity_text and re.search(r"2\s*x|1x .*1x", r.capacity_text))
                or bool(r.type_text and re.search(r"doppel|dual", r.type_text, re.I))
            )
            if dual and "dual_zone" not in claims:
                claims.append("dual_zone")
            out.append(Listing(
                run_id=run_id,
                snapshot_date=snapshot_date,
                channel=r.channel,
                channel_type=ch.type,
                market=r.market,
                rank=r.rank,
                title=r.title,
                url=r.url,
                external_id=r.external_id,
                brand=brand,
                model_key=self.model_key(brand, r.title, (r.extra or {}).get("mpn")),
                price_local=r.price,
                currency=r.currency,
                price_eur=self.to_eur(r.price, r.currency),
                offers=r.offers,
                rating=r.rating,
                rating_count=r.rating_count,
                sponsored=r.sponsored,
                capacity_l=capacity,
                power_w=self.power_w(r.power_text, r.specs_text, r.title),
                dual_zone=dual,
                claims=sorted(set(claims)),
                extra=r.extra or {},
            ))
        return out
