"""Test fetch resilience and error handling."""
import time
import httpx
import pytest

from category_radar.fetch import BlockedError, FetchError, Fetcher, looks_blocked


def test_looks_blocked_detects_challenges():
    assert looks_blocked(403, "<title>Just a moment</title>")
    assert looks_blocked(429, "")
    assert looks_blocked(200, "cf-challenge-platform")
    assert not looks_blocked(200, "<html>Valid content</html>" * 1000)


def test_fetcher_respects_rate_limit(tmp_path):
    fetcher = Fetcher(tmp_path, delay_seconds=0.1, respect_robots=False)

    start = time.monotonic()
    fetcher._throttle("example.com")
    fetcher._throttle("example.com")
    elapsed = time.monotonic() - start

    assert elapsed >= 0.1  # Should have waited at least delay_seconds
    fetcher.close()


def test_fetcher_retries_on_failure(tmp_path, monkeypatch):
    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("Temporary failure")
        return httpx.Response(200, text="<html>OK</html>", request=httpx.Request("GET", "http://example.com"))

    monkeypatch.setattr("httpx.Client.get", mock_get)

    fetcher = Fetcher(tmp_path, max_retries=3, respect_robots=False)
    result = fetcher._fetch_http("http://example.com", "example.com", "de")

    assert call_count == 3  # Should have retried twice then succeeded
    assert result.html == "<html>OK</html>"
    fetcher.close()
