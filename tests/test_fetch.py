import httpx

from category_radar.fetch import BlockedError, Fetcher, looks_blocked


def test_looks_blocked():
    assert looks_blocked(403, "")
    assert looks_blocked(200, "<html><head><title>Just a moment...</title></head></html>")
    assert looks_blocked(200, "<html><head><title>x</title></head><body>cf-challenge</body></html>")
    big_page = "<html><head><title>Fritteusen</title><script src='recaptcha'></script></head>" + "x" * 50000
    assert not looks_blocked(200, big_page)


def _fetcher(tmp_path, handler, **kw):
    f = Fetcher(tmp_path, mode="http", delay_seconds=0, max_retries=0, **kw)
    f._client = httpx.Client(transport=httpx.MockTransport(handler))
    return f


def test_robots_disallow_is_respected(tmp_path):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, text="<html><title>ok</title>" + "x" * 50000 + "</html>")

    f = _fetcher(tmp_path, handler)
    assert f.allowed("https://shop.test/category")
    assert not f.allowed("https://shop.test/private/page")


def test_fetch_caches_html_and_reports_blocks(tmp_path):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/blocked":
            return httpx.Response(403, text="nope")
        return httpx.Response(200, text="<html><title>ok</title>" + "x" * 50000 + "</html>")

    f = _fetcher(tmp_path, handler)
    res = f.fetch("https://shop.test/list", cache_path=tmp_path / "c" / "page-1.html")
    assert res.via == "http" and (tmp_path / "c" / "page-1.html").exists()
    try:
        f.fetch("https://shop.test/blocked")
        raise AssertionError("expected BlockedError")
    except BlockedError:
        pass
