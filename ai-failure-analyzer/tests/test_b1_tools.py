"""B1 证据拉取工具测试。"""

import httpx
import pytest

from ai_failure_analyzer.core.config import Settings
from ai_failure_analyzer.services.evidence_tools import fetch_report_html, fetch_screenshot_b64


def _settings() -> Settings:
    return Settings(
        AIFA_FETCH_ALLOWED_HOSTS="example.com",
        AIFA_FETCH_CONNECT_TIMEOUT_SECONDS=1,
        AIFA_FETCH_READ_TIMEOUT_SECONDS=1,
        AIFA_REPORT_MAX_CHARS=20,
        AIFA_SCREENSHOT_MAX_BYTES=1024,
        AIFA_SCREENSHOT_MAX_IMAGES=3,
    )


@pytest.mark.asyncio
async def test_fetch_report_html_success_and_truncate(monkeypatch: pytest.MonkeyPatch) -> None:
    html = "<html><body><h1>Title</h1><p>abcdefg0123456789ZZZZ</p></body></html>"

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        request = httpx.Request("GET", url)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=html, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_report_html("https://example.com/report.html", settings=_settings())
    assert "error" not in result
    assert result["truncated"] is True
    assert len(str(result["text"])) == 20


@pytest.mark.asyncio
async def test_fetch_report_html_non_html(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            text='{"ok":true}',
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_report_html("https://example.com/report.json", settings=_settings())
    assert result["error"] == "unsupported_content_type"


@pytest.mark.asyncio
async def test_fetch_screenshot_b64_direct_image(monkeypatch: pytest.MonkeyPatch) -> None:
    binary = b"\x89PNG\r\n\x1a\nxxxx"

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        request = httpx.Request("GET", url)
        return httpx.Response(200, headers={"content-type": "image/png"}, content=binary, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_screenshot_b64("https://example.com/a.png", settings=_settings())
    assert "error" not in result
    assert result["mime"] == "image/png"
    assert result["size_bytes"] == len(binary)


@pytest.mark.asyncio
async def test_fetch_screenshot_b64_index_html(monkeypatch: pytest.MonkeyPatch) -> None:
    index_html = """
    <html><body>
      <img src=\"/1.png\" />
      <img src=\"/2.png\" />
      <a href=\"/3.jpg\">pic</a>
      <img src=\"/4.png\" />
    </body></html>
    """

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        request = httpx.Request("GET", url)
        if url.endswith(".png") or url.endswith(".jpg"):
            return httpx.Response(
                200,
                headers={"content-type": "image/png"},
                content=b"img",
                request=request,
            )
        return httpx.Response(200, headers={"content-type": "text/html"}, text=index_html, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_screenshot_b64("https://example.com/index.html", settings=_settings())
    assert "error" not in result
    assert result["total_found"] == 4
    assert result["selected_count"] == 3
    assert result["image_count"] == 3
    assert result["truncated_by_max_images"] is True


@pytest.mark.asyncio
async def test_fetch_screenshot_rejects_unallowed_host() -> None:
    result = await fetch_screenshot_b64("https://evil.com/a.png", settings=_settings())
    assert result["error"] == "url_host_not_allowed"

