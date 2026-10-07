"""REST API for programmatic access to Category Radar data."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .config import load_config
from .export import build_bundle
from .logging_config import get_logger
from .store import Store

log = get_logger(__name__)

DATA_DIR = "data"
CONFIG_PATH = "config/airfryer.yaml"


class MarketStats(BaseModel):
    market: str
    median_eur: float
    median_local: float
    p10_eur: float
    p90_eur: float
    listings: int


class BrandStats(BaseModel):
    brand: str
    market: str
    listings: int
    visibility_share: float
    review_share: float | None = None
    avg_rating: float | None = None
    median_price_eur: float | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global CONFIG, DATA_DIR
    CONFIG = load_config(CONFIG_PATH)
    DATA_DIR = "data"
    yield


app = FastAPI(
    title="Category Radar API",
    description="Central European category intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """API root with documentation links."""
    return {
        "name": "Category Radar API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/api/v1/listings")
async def get_listings(
    market: str | None = None,
    brand: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict]:
    """Get listings with optional filters."""
    store = Store(f"{DATA_DIR}/radar.sqlite")
    try:
        run_id = store.latest_run_id()
        if not run_id:
            raise HTTPException(status_code=404, detail="No data available")

        listings = store.listings(run_id)

        # Apply filters
        if market:
            listings = [listing for listing in listings if listing["market"] == market]
        if brand:
            listings = [listing for listing in listings if listing["brand"] == brand]

        return listings[:limit]
    finally:
        store.close()


@app.get("/api/v1/insights/price")
async def get_price_insights(market: str | None = None) -> dict:
    """Get price analysis by market."""
    store = Store(f"{DATA_DIR}/radar.sqlite")
    try:
        run_id = store.latest_run_id()
        if not run_id:
            raise HTTPException(status_code=404, detail="No data available")

        cfg = load_config(CONFIG_PATH)
        bundle = build_bundle(cfg, store, run_id)

        price_data = bundle["insights"]["price"]

        if market:
            return {"markets": {market: price_data["markets"].get(market)}}

        return price_data
    finally:
        store.close()


@app.get("/api/v1/insights/landscape")
async def get_landscape_insights(market: str | None = None) -> dict:
    """Get competitive landscape by market."""
    store = Store(f"{DATA_DIR}/radar.sqlite")
    try:
        run_id = store.latest_run_id()
        if not run_id:
            raise HTTPException(status_code=404, detail="No data available")

        cfg = load_config(CONFIG_PATH)
        bundle = build_bundle(cfg, store, run_id)

        landscape = bundle["insights"]["landscape"]

        if market:
            return {"markets": {market: landscape["markets"].get(market)}}

        return landscape
    finally:
        store.close()


@app.get("/api/v1/brands")
async def get_brands(market: str | None = None) -> list[BrandStats]:
    """Get brand statistics."""
    store = Store(f"{DATA_DIR}/radar.sqlite")
    try:
        run_id = store.latest_run_id()
        if not run_id:
            raise HTTPException(status_code=404, detail="No data available")

        cfg = load_config(CONFIG_PATH)
        bundle = build_bundle(cfg, store, run_id)

        brands = []
        for m, data in bundle["insights"]["landscape"]["markets"].items():
            if market and m != market:
                continue
            for b in data["brands"]:
                brands.append(
                    BrandStats(
                        brand=b["brand"],
                        market=m,
                        listings=b["listings"],
                        visibility_share=b["visibility_share"],
                        review_share=b.get("review_share"),
                        avg_rating=b.get("avg_rating"),
                        median_price_eur=b.get("median_price_eur"),
                    )
                )

        return brands
    finally:
        store.close()
