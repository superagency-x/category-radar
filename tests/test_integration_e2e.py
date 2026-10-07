"""End-to-end integration tests."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from category_radar.config import load_config
from category_radar.pipeline import run_pipeline
from category_radar.store import Store


@pytest.mark.integration
def test_full_pipeline_integration(tmp_path):
    """Test complete pipeline from config to export."""
    cfg = load_config("config/airfryer.yaml")

    # Pre-populate raw html cache for geizhals_de to guarantee determinism
    today = datetime.now(timezone.utc).date().isoformat()
    date_dir = tmp_path / "raw" / today
    ch_dir = date_dir / "geizhals_de"
    ch_dir.mkdir(parents=True, exist_ok=True)
    fx_path = Path(__file__).parent / "fixtures" / "geizhals.html"
    (ch_dir / "page-1.html").write_text(fx_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Run pipeline with a single channel using cached fixture
    report = run_pipeline(
        cfg,
        tmp_path,
        channels=["geizhals_de"],
        with_reviews=False,
        offline_raw_dir=date_dir,
        progress=lambda x: None,
    )

    assert report.total_listings > 0
    assert report.channel_status["geizhals_de"]["status"] in ["ok", "empty", "blocked"]

    # Verify database
    store = Store(tmp_path / "radar.sqlite")
    rows = store.listings(report.run_id)
    assert len(rows) > 0
    store.close()
