"""EUR reference rates from the European Central Bank (free, no key)."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import httpx

log = logging.getLogger(__name__)

ECB_DAILY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

# Used only if the ECB feed is unreachable; the run is flagged as "fallback".
FALLBACK_RATES = {"EUR": 1.0, "CHF": 0.94, "PLN": 4.27, "CZK": 24.4, "HUF": 395.0}


def fetch_ecb_rates(timeout: float = 15.0) -> tuple[dict[str, float], str, str]:
    """Return (rates per 1 EUR, rate date, source)."""
    try:
        r = httpx.get(ECB_DAILY, timeout=timeout)
        r.raise_for_status()
        return parse_ecb_xml(r.text) + ("ecb",)
    except Exception as exc:  # network down, proxy, format change...
        log.warning("ECB rates unavailable (%s); using fallback rates", exc)
        return dict(FALLBACK_RATES), "fallback", "fallback"


def parse_ecb_xml(xml_text: str) -> tuple[dict[str, float], str]:
    root = ET.fromstring(xml_text)
    rates = {"EUR": 1.0}
    rate_date = ""
    for el in root.iter():
        if el.tag.endswith("Cube") and "time" in el.attrib:
            rate_date = el.attrib["time"]
        if el.tag.endswith("Cube") and "currency" in el.attrib:
            rates[el.attrib["currency"]] = float(el.attrib["rate"])
    return rates, rate_date
