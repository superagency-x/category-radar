from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from .logging_config import get_logger
from .store import Store

log = get_logger(__name__)
app = FastAPI(title="Category Radar Health", version="1.0.0")


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    last_run: str | None
    last_run_status: str
    channels_status: dict[str, Any]
    database_size_mb: float
    disk_space_gb: float
    logs_path: str


@app.get("/health", response_model=HealthResponse)
async def health_check(data_dir: str = "data") -> HealthResponse:
    """Return system health status."""
    data_path = Path(data_dir)
    db_path = data_path / "radar.sqlite"

    # Database status
    last_run = None
    last_run_status = "no_runs"
    channels_status = {}

    if db_path.exists():
        try:
            store = Store(db_path)
            runs = store.runs()
            if runs:
                latest = runs[-1]
                last_run = latest["started_at"]
                last_run_status = "success" if latest["finished_at"] else "incomplete"
                channels_status = latest.get("channel_status", {})
            store.close()
            db_size_mb = db_path.stat().st_size / (1024 * 1024)
        except Exception as e:
            log.error("health_check_db_error", error=str(e))
            db_size_mb = 0
    else:
        db_size_mb = 0

    # Disk space
    disk_usage = data_path.stat().st_size if data_path.exists() else 0
    disk_space_gb = disk_usage / (1024**3)

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        last_run=last_run,
        last_run_status=last_run_status,
        channels_status=channels_status,
        database_size_mb=round(db_size_mb, 2),
        disk_space_gb=round(disk_space_gb, 2),
        logs_path=str(data_path / "logs"),
    )


@app.get("/health/ready")
async def readiness_check(data_dir: str = "data") -> dict[str, str]:
    """Kubernetes-style readiness probe."""
    data_path = Path(data_dir)
    db_path = data_path / "radar.sqlite"

    if not db_path.exists():
        return {"status": "not_ready", "reason": "database_not_found"}

    try:
        store = Store(db_path)
        latest_run_id = store.latest_run_id()
        store.close()

        if not latest_run_id:
            return {"status": "not_ready", "reason": "no_completed_runs"}

        return {"status": "ready", "last_run_id": latest_run_id}
    except Exception as e:
        return {"status": "not_ready", "reason": str(e)}
