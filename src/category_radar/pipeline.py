"""Orchestration: scrape -> normalise -> store -> (reviews) -> analyse -> export.

Each channel runs in isolation: one broken or blocked site never stops the
others. Its status (ok / empty / blocked / disallowed / error) is recorded on
the run and shown on the dashboard, so data gaps are visible and never silent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .channels import get_adapter
from .config import CategoryConfig
from .fetch import BlockedError, Fetcher, FetchError, RobotsDisallowed
from .fx import fetch_ecb_rates
from .models import RawListing, Review
from .normalize import Normalizer
from .reviews import extract_reviews
from .store import Store

log = logging.getLogger(__name__)


@dataclass
class RunReport:
    run_id: str
    snapshot_date: str
    channel_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    reviews: int = 0

    @property
    def total_listings(self) -> int:
        return sum(s.get("listings", 0) for s in self.channel_status.values())


def _now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def new_run_id(ts: Optional[datetime] = None) -> str:
    return (ts or _now()).strftime("%Y%m%d-%H%M%S")


def scrape_channel(cfg: CategoryConfig, channel_id: str, fetcher: Fetcher, raw_dir: Path) -> tuple[list[RawListing], dict[str, Any]]:
    ch = cfg.channels[channel_id]
    adapter = get_adapter(ch.adapter)
    currency, language = cfg.currency_of(ch.market), cfg.language_of(ch.market)
    url: Optional[str] = ch.start_url
    listings: list[RawListing] = []
    status: dict[str, Any] = {"status": "ok", "pages": 0, "listings": 0, "via": None, "market": ch.market}
    seen_urls: set[str] = set()
    try:
        for page_no in range(1, ch.max_pages + 1):
            if not url or url in seen_urls:
                break
            seen_urls.add(url)
            res = fetcher.fetch(url, language=language, cache_path=raw_dir / channel_id / f"page-{page_no}.html")
            page_items = adapter.parse(res.html, channel=channel_id, market=ch.market, currency=currency,
                                       rank_offset=len(listings))
            log.info("%s page %d: %d listings (via %s)", channel_id, page_no, len(page_items), res.via)
            status["pages"] += 1
            status["via"] = res.via
            if not page_items:
                break
            listings += page_items
            url = adapter.next_page_url(res.html, url)
    except BlockedError as exc:
        status.update(status="blocked", error=str(exc))
    except RobotsDisallowed as exc:
        status.update(status="disallowed", error=str(exc))
    except FetchError as exc:
        status.update(status="error", error=str(exc))
    except Exception as exc:  # parser bug etc. must not kill the run
        log.exception("unexpected failure in %s", channel_id)
        status.update(status="error", error=f"{type(exc).__name__}: {exc}")
    if status["status"] == "ok" and not listings:
        status.update(status="empty", error="page fetched but no products parsed - selectors may have changed")
    status["listings"] = len(listings)
    return listings, status


def parse_cached(cfg: CategoryConfig, channel_id: str, raw_dir: Path) -> tuple[list[RawListing], dict[str, Any]]:
    """Re-parse previously saved HTML (no network)."""
    ch = cfg.channels[channel_id]
    adapter = get_adapter(ch.adapter)
    pages = sorted((raw_dir / channel_id).glob("page-*.html"), key=lambda p: int(p.stem.split("-")[1]))
    listings: list[RawListing] = []
    for p in pages:
        listings += adapter.parse(p.read_text(encoding="utf-8"), channel=channel_id, market=ch.market,
                                  currency=cfg.currency_of(ch.market), rank_offset=len(listings))
    status = {"status": "ok" if listings else ("empty" if pages else "missing"), "pages": len(pages),
              "listings": len(listings), "via": "cache", "market": ch.market}
    return listings, status


def collect_reviews(cfg: CategoryConfig, store_rows: list[dict], fetcher: Fetcher, raw_dir: Path) -> list[Review]:
    top_n = int(cfg.reviews.get("top_n_products", 0))
    if top_n <= 0:
        return []
    out: list[Review] = []
    by_channel: dict[str, list[dict]] = {}
    for r in store_rows:
        by_channel.setdefault(r["channel"], []).append(r)
    for channel, rows in by_channel.items():
        seen: set[str] = set()
        picked = []
        for r in sorted(rows, key=lambda r: r["rank"]):
            if r["model_key"] not in seen and r["url"]:
                seen.add(r["model_key"])
                picked.append(r)
            if len(picked) >= top_n:
                break
        lang = cfg.language_of(cfg.channels[channel].market)
        for i, r in enumerate(picked, start=1):
            try:
                res = fetcher.fetch(r["url"], language=lang, cache_path=raw_dir / channel / "products" / f"{i:02d}.html")
            except FetchError as exc:
                log.info("reviews: skip %s (%s)", r["url"], exc)
                if isinstance(exc, (BlockedError, RobotsDisallowed)):
                    break
                continue
            for rating, txt in extract_reviews(res.html):
                out.append(Review(channel=channel, market=r["market"], model_key=r["model_key"], brand=r["brand"],
                                  rating=rating, text=txt, language=lang))
    return out


def run_pipeline(
    cfg: CategoryConfig,
    data_dir: Path,
    *,
    channels: Optional[list[str]] = None,
    with_reviews: bool = True,
    offline_raw_dir: Optional[Path] = None,
    fetcher_factory: Optional[Callable[[Path], Fetcher]] = None,
    progress: Callable[[str], None] = lambda s: None,
) -> RunReport:
    started = _now()
    run_id = new_run_id(started)
    snapshot_date = started.date().isoformat()
    raw_dir = offline_raw_dir or (data_dir / "raw" / snapshot_date)
    store = Store(data_dir / "radar.sqlite")
    store.start_run(run_id, snapshot_date, started.isoformat(), cfg.id)
    report = RunReport(run_id=run_id, snapshot_date=snapshot_date)

    rates, rate_date, fx_source = fetch_ecb_rates()
    store.save_fx(run_id, rate_date, rates)
    normalizer = Normalizer(cfg, rates)
    progress(f"FX {fx_source} ({rate_date}): " + ", ".join(f"{c} {rates.get(c)}" for c in ("CHF", "PLN", "CZK", "HUF")))

    crawl = cfg.crawl
    fetcher = (fetcher_factory or (lambda rd: Fetcher(
        rd,
        mode=crawl.get("fetcher", "auto"),
        delay_seconds=float(crawl.get("delay_seconds", 4)),
        timeout_seconds=float(crawl.get("timeout_seconds", 30)),
        max_retries=int(crawl.get("max_retries", 2)),
        respect_robots=bool(crawl.get("respect_robots_txt", True)),
        user_agent=crawl.get("user_agent"),
    )))(raw_dir)

    try:
        for cid in channels or list(cfg.channels):
            progress(f"→ {cid}")
            if offline_raw_dir:
                raws, status = parse_cached(cfg, cid, raw_dir)
            else:
                raws, status = scrape_channel(cfg, cid, fetcher, raw_dir)
            listings = normalizer.normalize(raws, run_id=run_id, snapshot_date=snapshot_date)
            status["listings"] = store.replace_listings(run_id, cid, listings)
            report.channel_status[cid] = status
            progress(f"  {status['status']}: {status['listings']} listings"
                     + (f" ({status.get('error')})" if status.get("error") else ""))

        if with_reviews and not offline_raw_dir:
            progress("→ reviews (top products per channel)")
            reviews = collect_reviews(cfg, store.listings(run_id), fetcher, raw_dir)
            report.reviews = store.replace_reviews(run_id, reviews)
            progress(f"  {report.reviews} reviews")
    finally:
        fetcher.close()
        store.finish_run(run_id, _now().isoformat(), fx_source, report.channel_status)
        store.close()
    return report
