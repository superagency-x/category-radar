"""Write the dashboard data bundle and analyst-friendly CSVs."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import __version__
from .analytics import analyse
from .config import CategoryConfig
from .store import Store


def build_bundle(cfg: CategoryConfig, store: Store, run_id: Optional[str] = None) -> dict[str, Any]:
    run_id = run_id or store.latest_run_id()
    if not run_id:
        raise RuntimeError("No completed run in the database yet. Run `radar run` first.")
    runs = store.runs()
    run = next(r for r in runs if r["run_id"] == run_id)
    latest = store.listings(run_id)
    history = store.listings()
    reviews = store.reviews(run_id) or store.reviews()
    insights = analyse(latest, history, reviews, cfg)
    return {
        "meta": {
            "category": {"id": cfg.id, "name": cfg.name},
            "run_id": run_id,
            "snapshot_date": run["snapshot_date"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": __version__,
            "fx_source": run["fx_source"],
            "fx": store.fx(run_id),
            "markets": cfg.markets,
            "channels": {
                cid: {"market": c.market, "type": c.type, "url": c.start_url,
                      **run["channel_status"].get(cid, {"status": "not run"})}
                for cid, c in cfg.channels.items()
            },
            "history": [{"run_id": r["run_id"], "date": r["snapshot_date"],
                         "listings": sum(s.get("listings", 0) for s in r["channel_status"].values())}
                        for r in runs if r["finished_at"]],
            "counts": {"listings": len(latest), "reviews": len(reviews),
                       "brands": len({l["brand"] for l in latest}), "snapshots": len({h["snapshot_date"] for h in history})},
        },
        "insights": insights,
        "listings": [
            {k: l[k] for k in ("market", "channel", "rank", "brand", "title", "url", "price_local", "currency",
                               "price_eur", "offers", "rating", "rating_count", "sponsored", "capacity_l",
                               "power_w", "dual_zone", "claims", "model_key")}
            for l in latest
        ],
    }


def write_site_data(bundle: dict[str, Any], site_dir: Path) -> Path:
    out = site_dir / "data"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "radar.json"
    path.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path


def write_csvs(bundle: dict[str, Any], export_dir: Path) -> list[Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    listings = bundle["listings"]
    if listings:
        p = export_dir / f"listings_{bundle['meta']['snapshot_date']}.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(listings[0].keys()))
            w.writeheader()
            for row in listings:
                w.writerow({**row, "claims": ";".join(row["claims"])})
        paths.append(p)
    p = export_dir / f"brands_{bundle['meta']['snapshot_date']}.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["market", "brand", "listings", "top20", "visibility_share", "review_share", "avg_rating",
                    "avg_offers", "median_price_eur", "sponsored_listings"])
        for m, d in bundle["insights"]["landscape"]["markets"].items():
            for b in d["brands"]:
                w.writerow([m, b["brand"], b["listings"], b["top20"], b["visibility_share"], b["review_share"],
                            b["avg_rating"], b["avg_offers"], b["median_price_eur"], b["sponsored_listings"]])
    paths.append(p)
    return paths
