"""Async fetcher for concurrent channel scraping."""

import asyncio
import time
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .fetch import ACCEPT_LANGUAGE, DEFAULT_UA, looks_blocked
from .logging_config import get_logger
from .settings import settings

log = get_logger(__name__)


@dataclass
class FetchResult:
    url: str
    html: str
    status: int
    via: str
    cache_path: Path | None = None


class AsyncFetcher:
    """Concurrent fetcher using asyncio and httpx."""

    def __init__(
        self,
        raw_dir: Path,
        *,
        delay_seconds: float = 4.0,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        respect_robots: bool = True,
        user_agent: str | None = None,
        max_concurrent: int = 3,
    ) -> None:
        self.raw_dir = raw_dir
        self.delay = delay_seconds
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self.respect_robots = respect_robots
        self.user_agent = user_agent or settings.user_agent or DEFAULT_UA
        self.max_concurrent = max_concurrent
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._robots_lock = asyncio.Lock()
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def _throttle(self, host: str) -> None:
        """Async rate limiting."""
        last = self._last_hit.get(host)
        if last is not None:
            wait = self.delay - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_hit[host] = time.monotonic()

    async def fetch(self, url: str, *, language: str = "de", cache_path: Path | None = None) -> FetchResult:
        """Fetch a single URL with caching, robots check, and throttling."""
        if cache_path is not None and cache_path.exists():
            return FetchResult(
                url=url,
                html=cache_path.read_text(encoding="utf-8"),
                status=200,
                via="cache",
                cache_path=cache_path,
            )

        async with self._semaphore:
            if self.respect_robots and not await self._allowed(url):
                from .fetch import RobotsDisallowed

                raise RobotsDisallowed(f"robots.txt disallows {url}")

            host = urlparse(url).netloc
            host_lock = self._host_locks.setdefault(host, asyncio.Lock())

            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": ACCEPT_LANGUAGE.get(language, "en"),
            }

            async with host_lock:
                await self._throttle(host)
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    for attempt in range(self.max_retries + 1):
                        try:
                            response = await client.get(url, headers=headers, follow_redirects=True)

                            if looks_blocked(response.status_code, response.text):
                                from .fetch import BlockedError

                                raise BlockedError(f"{host} answered {response.status_code} / challenge page")

                            if response.status_code >= 500:
                                if attempt == self.max_retries:
                                    from .fetch import FetchError

                                    raise FetchError(f"{url} -> HTTP {response.status_code} after retries")
                                await asyncio.sleep(2**attempt)
                                continue

                            if response.status_code >= 400:
                                from .fetch import FetchError

                                raise FetchError(f"{url} -> HTTP {response.status_code}")

                            result = FetchResult(
                                url=str(response.url),
                                html=response.text,
                                status=response.status_code,
                                via="http",
                            )

                            if cache_path:
                                cache_path.parent.mkdir(parents=True, exist_ok=True)
                                cache_path.write_text(result.html, encoding="utf-8")
                                result.cache_path = cache_path

                            return result

                        except httpx.HTTPError as exc:
                            if attempt == self.max_retries:
                                from .fetch import FetchError

                                raise FetchError(f"{url}: giving up after retries ({exc})") from exc
                            await asyncio.sleep(2**attempt)
        raise RuntimeError("fetch failed without returning or raising")

    async def _allowed(self, url: str) -> bool:
        """Check robots.txt without blocking the event loop; deny on policy-fetch errors."""
        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(base)
        if rp is None:
            async with self._robots_lock:
                rp = self._robots.get(base)
                if rp is None:
                    rp = urllib.robotparser.RobotFileParser()
                    robots_url = base + "/robots.txt"
                    rp.set_url(robots_url)
                    try:
                        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                            response = await client.get(robots_url, headers={"User-Agent": self.user_agent})
                    except httpx.HTTPError as exc:
                        from .fetch import FetchError

                        raise FetchError(f"Could not check robots.txt for {base}: {exc}") from exc

                    if response.status_code == 404:
                        # No robots file is published; there are no crawl restrictions to apply.
                        rp.parse([])
                    elif response.status_code in (401, 403):
                        from .fetch import RobotsDisallowed

                        raise RobotsDisallowed(
                            f"Cannot confirm crawl permission for {base}: robots.txt returned {response.status_code}"
                        )
                    elif response.status_code >= 400:
                        from .fetch import FetchError

                        raise FetchError(f"Could not check robots.txt for {base}: HTTP {response.status_code}")
                    else:
                        rp.parse(response.text.splitlines())
                    self._robots[base] = rp
        return rp.can_fetch(self.user_agent, url)

    async def fetch_all(self, urls: list[tuple[str, str]]) -> list[FetchResult]:
        """Fetch multiple URLs concurrently."""
        tasks = [self.fetch(url, language=lang) for url, lang in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, FetchResult)]
