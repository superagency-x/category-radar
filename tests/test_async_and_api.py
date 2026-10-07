"""Tests for async scraping and API endpoints."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from category_radar import api
from category_radar.config import load_config
from category_radar.fetch_async import AsyncFetcher
from category_radar.models import Listing
from category_radar.pipeline import run_pipeline_async
from category_radar.store import Store


def test_api_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", str(tmp_path))
    store = Store(tmp_path / "radar.sqlite")
    run_id = "api-test-run"
    snapshot_date = datetime.now(timezone.utc).date().isoformat()
    store.start_run(run_id, snapshot_date, datetime.now(timezone.utc).isoformat(), "airfryer")
    store.replace_listings(
        run_id,
        "geizhals_de",
        [
            Listing(
                run_id=run_id,
                snapshot_date=snapshot_date,
                channel="geizhals_de",
                channel_type="price_comparison",
                market="DE",
                rank=1,
                title="Ninja AF400 Air Fryer",
                url="https://example.test/ninja-af400",
                external_id=None,
                brand="Ninja",
                model_key="ninja:AF400",
                price_local=149.0,
                currency="EUR",
                price_eur=149.0,
                offers=2,
                rating=4.8,
                rating_count=50,
                sponsored=False,
                capacity_l=9.5,
                power_w=2470,
                dual_zone=True,
                claims=["dual_zone"],
                extra={},
            )
        ],
    )
    store.save_fx(run_id, snapshot_date, {"EUR": 1.0})
    store.finish_run(run_id, datetime.now(timezone.utc).isoformat(), "test", {"geizhals_de": {"status": "ok"}})
    store.close()

    with TestClient(api.app) as client:
        # Root
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["name"] == "Category Radar API"

        # Listings
        r = client.get("/api/v1/listings?limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        # Filtered listings
        r = client.get("/api/v1/listings?market=DE&limit=5")
        assert r.status_code == 200
        for item in r.json():
            assert item["market"] == "DE"

        # Price insights
        r = client.get("/api/v1/insights/price")
        assert r.status_code == 200
        assert "markets" in r.json()

        # Landscape insights
        r = client.get("/api/v1/insights/landscape")
        assert r.status_code == 200
        assert "markets" in r.json()

        # Brands
        r = client.get("/api/v1/brands?market=DE")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        # Health & Ready
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

        r = client.get("/health/ready")
        assert r.status_code == 200
        assert r.json()["status"] in ("ready", "not_ready")

        # Battlecards
        r = client.get("/api/v1/battlecards?brand=Ninja&market=DE")
        assert r.status_code == 200
        assert r.json()["brand"] == "Ninja"

        # Alerts
        r = client.get("/api/v1/alerts")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


def test_async_fetcher_cached(tmp_path):
    async def _test():
        cache_file = tmp_path / "page-1.html"
        cache_file.write_text("<html>Cached content</html>", encoding="utf-8")

        fetcher = AsyncFetcher(tmp_path, delay_seconds=0.01, respect_robots=False)
        result = await fetcher.fetch("https://example.com", cache_path=cache_file)

        assert result.status == 200
        assert result.via == "cache"
        assert "Cached content" in result.html

    asyncio.run(_test())


def test_async_fetcher_throttle(tmp_path):
    async def _test():
        fetcher = AsyncFetcher(tmp_path, delay_seconds=0.05, respect_robots=False)
        await fetcher._throttle("test.host")
        assert "test.host" in fetcher._last_hit

    asyncio.run(_test())


def test_run_pipeline_async(tmp_path):
    async def _test():
        cfg = load_config("config/airfryer.yaml")

        # Seed cached file for geizhals_de
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).date().isoformat()
        raw_dir = tmp_path / "raw" / today / "geizhals_de"
        raw_dir.mkdir(parents=True, exist_ok=True)
        fx_path = Path(__file__).parent / "fixtures" / "geizhals.html"
        (raw_dir / "page-1.html").write_text(fx_path.read_text(encoding="utf-8"), encoding="utf-8")

        report = await run_pipeline_async(
            cfg,
            tmp_path,
            channels=["geizhals_de"],
            offline_raw_dir=tmp_path / "raw" / today,
        )
        assert report.total_listings > 0
        assert "geizhals_de" in report.channel_status

        store = Store(tmp_path / "radar.sqlite")
        listings = store.listings(report.run_id)
        assert len(listings) > 0
        store.close()

    asyncio.run(_test())
