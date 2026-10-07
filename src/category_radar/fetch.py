"""Polite page fetching with a raw-HTML cache.

Design points:
* Every fetched page is written to data/raw/<date>/<channel>/page-<n>.html
  before parsing. Parsers can then be fixed and re-run offline
  (`radar reparse`) without hitting the sites again.
* robots.txt is honoured by default and requests to one host are rate-limited.
* `auto` mode tries plain HTTP first and falls back to a real headless browser
  (Playwright) if a page is blocked or rendered client-side. Interactive bot
  challenges (CAPTCHA / "verify you are human") are NOT bypassed: the channel
  is reported as blocked and skipped.
"""

from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .logging_config import get_logger
from .settings import settings

log = get_logger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)

ACCEPT_LANGUAGE = {
    "de": "de-DE,de;q=0.9,en;q=0.6",
    "pl": "pl-PL,pl;q=0.9,en;q=0.6",
    "cs": "cs-CZ,cs;q=0.9,en;q=0.6",
    "hu": "hu-HU,hu;q=0.9,en;q=0.6",
}

CHALLENGE_TITLES = ("just a moment", "attention required", "kontrola zabezpečení", "access denied")
CHALLENGE_MARKERS = (
    "cf-challenge",
    "challenge-platform",
    "verify you are human",
    "captcha-delivery",
    "js_f-container",
    "fdetection",
    "przejdź do ceneo",
)


class FetchError(RuntimeError):
    pass


class BlockedError(FetchError):
    """The site answered with a bot wall / challenge."""


class RobotsDisallowed(FetchError):
    pass


@dataclass
class FetchResult:
    url: str
    html: str
    status: int
    via: str  # "http" | "browser" | "cache"
    cache_path: Path | None = None


def looks_blocked(status: int, html: str) -> bool:
    if status in (403, 429, 503):
        return True
    low = html[:50000].lower()
    start = low.find("<title")
    title = low[start : low.find("</title>", start)] if start >= 0 else ""
    if any(t in title for t in CHALLENGE_TITLES):
        return True
    # Real category pages are large; challenge interstitials are small.
    return len(html) < 60000 and any(m in low for m in CHALLENGE_MARKERS)


class Fetcher:
    def __init__(
        self,
        raw_dir: Path,
        *,
        mode: str = "auto",
        delay_seconds: float = 4.0,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        respect_robots: bool = True,
        user_agent: str | None = None,
    ) -> None:
        self.raw_dir = raw_dir
        self.mode = mode
        self.delay = delay_seconds
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self.respect_robots = respect_robots
        self.user_agent = user_agent or settings.user_agent or DEFAULT_UA
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        self._browser: Any = None  # lazily started Playwright browser
        self._pw: Any = None

    # -- politeness -------------------------------------------------------
    def _throttle(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            wait = self.delay - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_hit[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self._client.get(base + "/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])  # unreachable robots.txt -> treat as allow-all
            self._robots[base] = rp
        return rp.can_fetch(self.user_agent, url)

    # -- fetching ---------------------------------------------------------
    def fetch(self, url: str, *, language: str = "de", cache_path: Path | None = None) -> FetchResult:
        if not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        host = urlparse(url).netloc
        result: FetchResult | None = None

        if self.mode in ("auto", "http"):
            try:
                result = self._fetch_http(url, host, language)
            except BlockedError:
                if self.mode == "http":
                    raise
                log.info("http_blocked_retry", host=host)

        if result is None:
            result = self._fetch_browser(url, host, language)

        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(result.html, encoding="utf-8")
            result.cache_path = cache_path
        return result

    def _fetch_http(self, url: str, host: str, language: str) -> FetchResult:
        headers = {"Accept-Language": ACCEPT_LANGUAGE.get(language, "en")}
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle(host)
            log.info("http_fetch_attempt", url=url, attempt=attempt + 1, host=host)
            try:
                r = self._client.get(url, headers=headers)
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(2**attempt)
                continue
            if looks_blocked(r.status_code, r.text):
                log.warning("fetch_blocked", host=host, status=r.status_code, page_size=len(r.text))
                raise BlockedError(f"{host} answered {r.status_code} / challenge page")
            if r.status_code >= 500:
                last_exc = FetchError(f"{url} -> HTTP {r.status_code}")
                time.sleep(2**attempt)
                continue
            if r.status_code >= 400:
                raise FetchError(f"{url} -> HTTP {r.status_code}")
            return FetchResult(url=str(r.url), html=r.text, status=r.status_code, via="http")
        raise FetchError(f"{url}: giving up after retries ({last_exc})")

    def _fetch_browser(self, url: str, host: str, language: str) -> FetchResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise FetchError(
                "Page needs a real browser but Playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            ) from exc
        if self._browser is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
        self._throttle(host)
        ctx = self._browser.new_context(
            user_agent=self.user_agent,
            locale=ACCEPT_LANGUAGE.get(language, "en").split(",")[0],
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            page.wait_for_timeout(2500)  # let client-side lists render
            # scroll once so lazy-loaded product cards are in the DOM
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(1500)
            html = page.content()
            status = resp.status if resp else 200
        finally:
            ctx.close()
        if looks_blocked(status, html):
            raise BlockedError(f"{host}: bot challenge in browser too, skipping (not bypassed by design)")
        return FetchResult(url=url, html=html, status=status, via="browser")

    def close(self) -> None:
        self._client.close()
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
