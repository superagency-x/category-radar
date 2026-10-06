"""End-to-end: synthetic shelves -> store -> analytics -> export bundle."""
from pathlib import Path

from category_radar import pipeline
from category_radar.analytics import analyse, visibility_weight
from category_radar.export import build_bundle, write_site_data
from category_radar.models import Review
from category_radar.normalize import Normalizer
from category_radar.reviews import extract_reviews
from category_radar.store import Store

from .conftest import FX, synthetic_raw


def _populate(tmp: Path, cfg, days=("2026-10-05", "2026-10-06")):
    store = Store(tmp / "radar.sqlite")
    norm = Normalizer(cfg, FX)
    for n, day in enumerate(days):
        run_id = f"{day.replace('-', '')}-090000"
        store.start_run(run_id, day, f"{day}T09:00:00+02:00", cfg.id)
        status = {}
        for m in cfg.markets:
            raws = synthetic_raw(m, seed=0, price_shift=1.0 if n == 0 else 0.9)
            ls = norm.normalize(raws, run_id=run_id, snapshot_date=day)
            ch = raws[0].channel
            status[ch] = {"status": "ok", "listings": store.replace_listings(run_id, ch, ls), "market": m}
        store.replace_reviews(run_id, [
            Review(channel="geizhals_de", market="DE", model_key="ninja:AF400", brand="Ninja", rating=5,
                   text="Sehr leise und leicht zu reinigen, Korb passt in die Spülmaschine", language="de"),
            Review(channel="ceneo_pl", market="PL", model_key="tefal:EY905", brand="Tefal", rating=2,
                   text="Głośna i trudno się czyści, zapach plastiku", language="pl"),
        ])
        store.save_fx(run_id, day, FX)
        store.finish_run(run_id, f"{day}T09:10:00+02:00", "ecb", status)
    return store


def test_visibility_weight_is_dcg_like():
    assert visibility_weight(1) == 1.0
    assert round(visibility_weight(3), 2) == 0.5


def test_full_bundle(tmp_path, cfg):
    store = _populate(tmp_path, cfg)
    bundle = build_bundle(cfg, store)
    ins = bundle["insights"]
    assert set(ins["price"]["markets"]) == set(cfg.markets)
    # visibility shares sum to ~100 per market
    for m, d in ins["landscape"]["markets"].items():
        assert abs(sum(b["visibility_share"] for b in d["brands"]) - 100) < 1
        assert 0 < d["hhi"] <= 10000
    # identical models are matched across all six markets
    assert any(len(c["prices_eur"]) == 6 for c in ins["price"]["cross_market"])
    # two snapshots -> trend has two points and a 10% price cut is detected
    assert len(ins["price"]["trend"]["DE"]) == 2
    assert ins["price"]["movers"] and all(m["change_pct"] < 0 for m in ins["price"]["movers"])
    # needs: review salience picks up noise + cleaning in both languages
    de = {x["need"]: x for x in ins["needs"]["review_salience"]["DE"]}
    pl = {x["need"]: x for x in ins["needs"]["review_salience"]["PL"]}
    assert de["noise"]["mentions"] == 1 and de["cleaning"]["mentions"] == 1
    assert pl["noise"]["mentions"] == 1 and pl["smell"]["mentions"] == 1
    assert ins["needs"]["demand_signals"][0]["market"] == "PL"
    # positioning: tiers assigned, maps built
    assert ins["positioning"]["maps"]["DE"]
    assert ins["insights"]
    path = write_site_data(bundle, tmp_path / "site")
    assert path.exists() and path.stat().st_size > 1000
    store.close()


def test_pipeline_offline_reparse(tmp_path, cfg, monkeypatch):
    """`radar reparse` path: saved HTML -> listings without network."""
    fx_dir = Path(__file__).parent / "fixtures"
    raw = tmp_path / "raw" / "2026-10-06"
    for ch, fx in {"geizhals_de": "geizhals.html", "ceneo_pl": "ceneo.html", "alza_cz": "alza.html"}.items():
        (raw / ch).mkdir(parents=True)
        (raw / ch / "page-1.html").write_text((fx_dir / fx).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(pipeline, "fetch_ecb_rates", lambda: (FX, "2026-10-06", "test"))
    report = pipeline.run_pipeline(cfg, tmp_path, offline_raw_dir=raw, with_reviews=False)
    assert report.channel_status["geizhals_de"]["listings"] == 3
    assert report.channel_status["ceneo_pl"]["listings"] == 2
    assert report.channel_status["alza_cz"]["listings"] == 2
    assert report.channel_status["toppreise_ch"]["status"] == "missing"
    store = Store(tmp_path / "radar.sqlite")
    rows = store.listings(report.run_id)
    cz = [r for r in rows if r["market"] == "CZ"][0]
    assert cz["price_eur"] == round(3998 / 24.4, 2)
    store.close()


def test_extract_reviews_jsonld():
    html = """<html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"X",
     "review":[{"@type":"Review","reviewRating":{"@type":"Rating","ratingValue":"4","bestRating":"5"},
                "reviewBody":"Bardzo cicha, łatwo się czyści i jest duża dla rodziny."},
               {"@type":"Review","reviewRating":{"ratingValue":2},"reviewBody":"Laut und riecht nach Plastik am Anfang."}]}
    </script></head><body></body></html>"""
    revs = extract_reviews(html)
    assert len(revs) == 2 and revs[0][0] == 4.0 and "cicha" in revs[0][1]
