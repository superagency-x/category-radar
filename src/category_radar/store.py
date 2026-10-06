"""SQLite storage: one file, zero setup, full history.

Tables
  runs       one row per pipeline run (when, which channels, status per channel)
  listings   one row per product per channel per run (the time series)
  reviews    review texts used for market-needs mining
  fx_rates   the exchange rates used by each run (reproducibility)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import Listing, Review

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    snapshot_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    category TEXT NOT NULL,
    fx_source TEXT,
    channel_status TEXT           -- JSON {channel: {status, listings, pages, via, error}}
);
CREATE TABLE IF NOT EXISTS listings (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    snapshot_date TEXT NOT NULL,
    channel TEXT NOT NULL,
    channel_type TEXT NOT NULL,
    market TEXT NOT NULL,
    rank INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    external_id TEXT,
    brand TEXT NOT NULL,
    model_key TEXT NOT NULL,
    price_local REAL,
    currency TEXT NOT NULL,
    price_eur REAL,
    offers INTEGER,
    rating REAL,
    rating_count INTEGER,
    sponsored INTEGER NOT NULL DEFAULT 0,
    capacity_l REAL,
    power_w INTEGER,
    dual_zone INTEGER NOT NULL DEFAULT 0,
    claims TEXT NOT NULL DEFAULT '[]',
    extra TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, channel, rank)
);
CREATE INDEX IF NOT EXISTS ix_listings_model ON listings(model_key, market, snapshot_date);
CREATE INDEX IF NOT EXISTS ix_listings_date ON listings(snapshot_date, market);
CREATE TABLE IF NOT EXISTS reviews (
    run_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    market TEXT NOT NULL,
    model_key TEXT NOT NULL,
    brand TEXT NOT NULL,
    rating REAL,
    language TEXT,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fx_rates (
    run_id TEXT NOT NULL,
    rate_date TEXT,
    currency TEXT NOT NULL,
    per_eur REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # -- writes ------------------------------------------------------------
    def start_run(self, run_id: str, snapshot_date: str, started_at: str, category: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs(run_id, snapshot_date, started_at, category) VALUES (?,?,?,?)",
            (run_id, snapshot_date, started_at, category),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, finished_at: str, fx_source: str, channel_status: dict[str, Any]) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at=?, fx_source=?, channel_status=? WHERE run_id=?",
            (finished_at, fx_source, json.dumps(channel_status), run_id),
        )
        self.conn.commit()

    def save_fx(self, run_id: str, rate_date: str, rates: dict[str, float]) -> None:
        self.conn.execute("DELETE FROM fx_rates WHERE run_id=?", (run_id,))
        self.conn.executemany(
            "INSERT INTO fx_rates VALUES (?,?,?,?)",
            [(run_id, rate_date, cur, val) for cur, val in rates.items()],
        )
        self.conn.commit()

    def replace_listings(self, run_id: str, channel: str, listings: Iterable[Listing]) -> int:
        self.conn.execute("DELETE FROM listings WHERE run_id=? AND channel=?", (run_id, channel))
        rows = [
            (
                l.run_id, l.snapshot_date, l.channel, l.channel_type, l.market, l.rank, l.title, l.url,
                l.external_id, l.brand, l.model_key, l.price_local, l.currency, l.price_eur, l.offers,
                l.rating, l.rating_count, int(l.sponsored), l.capacity_l, l.power_w, int(l.dual_zone),
                json.dumps(l.claims), json.dumps(l.extra, ensure_ascii=False),
            )
            for l in listings
        ]
        self.conn.executemany(f"INSERT OR REPLACE INTO listings VALUES ({','.join('?' * 23)})", rows)
        self.conn.commit()
        return len(rows)

    def replace_reviews(self, run_id: str, reviews: Iterable[Review]) -> int:
        self.conn.execute("DELETE FROM reviews WHERE run_id=?", (run_id,))
        rows = [(run_id, r.channel, r.market, r.model_key, r.brand, r.rating, r.language, r.text) for r in reviews]
        self.conn.executemany("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()
        return len(rows)

    # -- reads -------------------------------------------------------------
    def latest_run_id(self) -> Optional[str]:
        row = self.conn.execute(
            "SELECT run_id FROM runs WHERE finished_at IS NOT NULL ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return row["run_id"] if row else None

    def runs(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM runs ORDER BY started_at").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["channel_status"] = json.loads(d["channel_status"] or "{}")
            out.append(d)
        return out

    def listings(self, run_id: Optional[str] = None) -> list[dict[str, Any]]:
        if run_id:
            rows = self.conn.execute("SELECT * FROM listings WHERE run_id=? ORDER BY market, rank", (run_id,))
        else:
            rows = self.conn.execute("SELECT * FROM listings ORDER BY snapshot_date, market, rank")
        out = []
        for r in rows.fetchall():
            d = dict(r)
            d["claims"] = json.loads(d["claims"])
            d["extra"] = json.loads(d["extra"])
            d["sponsored"] = bool(d["sponsored"])
            d["dual_zone"] = bool(d["dual_zone"])
            out.append(d)
        return out

    def reviews(self, run_id: Optional[str] = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM reviews" + (" WHERE run_id=?" if run_id else "")
        return [dict(r) for r in self.conn.execute(q, (run_id,) if run_id else ()).fetchall()]

    def fx(self, run_id: str) -> dict[str, float]:
        rows = self.conn.execute("SELECT currency, per_eur FROM fx_rates WHERE run_id=?", (run_id,)).fetchall()
        return {r["currency"]: r["per_eur"] for r in rows}
