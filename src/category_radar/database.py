"""Database abstraction layer."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from .models import Listing, Review


class Database(ABC):
    """Abstract database interface."""

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def start_run(self, run_id: str, snapshot_date: str, started_at: str, category: str) -> None: ...

    @abstractmethod
    def finish_run(self, run_id: str, finished_at: str, fx_source: str, channel_status: dict[str, Any]) -> None: ...

    @abstractmethod
    def save_fx(self, run_id: str, rate_date: str, rates: dict[str, float]) -> None: ...

    @abstractmethod
    def replace_listings(self, run_id: str, channel: str, listings: Iterable[Listing]) -> int: ...

    @abstractmethod
    def replace_reviews(self, run_id: str, reviews: Iterable[Review]) -> int: ...

    @abstractmethod
    def latest_run_id(self) -> str | None: ...

    @abstractmethod
    def runs(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def listings(self, run_id: str | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def reviews(self, run_id: str | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def fx(self, run_id: str) -> dict[str, float]: ...
