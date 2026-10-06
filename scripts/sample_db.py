"""Build a SYNTHETIC sample database for dashboard development / CI screenshots.

    python scripts/sample_db.py --out /tmp/radar-sample && \
    radar export --data-dir /tmp/radar-sample --site-dir /tmp/radar-sample/site

The dashboard shows a red "synthetic sample data" banner when it renders this
data. Real data only ever comes from `radar run`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from category_radar.config import load_config  # noqa: E402
from category_radar.models import Review  # noqa: E402
from category_radar.normalize import Normalizer  # noqa: E402
from category_radar.store import Store  # noqa: E402
from tests.conftest import FX, synthetic_raw  # noqa: E402

REVIEWS = {
    "DE": ["Sehr leise und leicht zu reinigen", "Zu laut, riecht anfangs nach Plastik", "Groß genug für die ganze Familie",
           "Pommes werden richtig knusprig", "Nimmt viel Platz weg", "Beschichtung löst sich nach 6 Monaten"],
    "PL": ["Głośna i trudno się czyści", "Duża pojemność, idealna dla rodziny", "Chrupiące frytki, szybko",
           "Zapach plastiku na początku", "Prosta obsługa, dobra cena"],
    "CZ": ["Velký objem, křupavé hranolky", "Hlučná, ale snadné čištění v myčce", "Zabírá hodně místa", "Rychlá a levná"],
    "HU": ["Nagy kosár, családnak ideális", "Hangos, de könnyen tisztítható", "Ropogós krumpli, gyors", "Műanyag szag az elején"],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/radar-sample")
    args = ap.parse_args()
    cfg = load_config(ROOT / "config" / "airfryer.yaml")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "radar.sqlite").unlink(missing_ok=True)
    store = Store(out / "radar.sqlite")
    norm = Normalizer(cfg, FX)
    days = ["2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06"]
    for n, day in enumerate(days):
        run_id = f"{day.replace('-', '')}-090000"
        store.start_run(run_id, day, f"{day}T09:00:00+02:00", cfg.id)
        status = {}
        for m in cfg.markets:
            raws = synthetic_raw(m, seed=n % 2, price_shift=1 - 0.02 * n)
            ls = norm.normalize(raws, run_id=run_id, snapshot_date=day)
            ch = raws[0].channel
            status[ch] = {"status": "ok", "listings": store.replace_listings(run_id, ch, ls), "pages": 1, "via": "sample", "market": m}
        store.replace_reviews(run_id, [
            Review(channel="x", market=m, model_key="x", brand="x", rating=(5 if i % 2 == 0 else 2), text=t, language=cfg.language_of(m))
            for m, texts in REVIEWS.items() for i, t in enumerate(texts)
        ])
        store.save_fx(run_id, day, FX)
        store.finish_run(run_id, f"{day}T09:10:00+02:00", "sample", status)
    store.close()
    print(f"Synthetic sample DB written to {out / 'radar.sqlite'}")


if __name__ == "__main__":
    main()
