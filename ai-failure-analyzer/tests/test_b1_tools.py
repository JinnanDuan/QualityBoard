"""B1 证据拉取工具测试。"""

import httpx
import pytest

from ai_failure_analyzer.core.config import Settings
from ai_failure_analyzer.services.evidence_tools import (
    build_success_urls_by_batch_replace,
    fetch_report_html,
    fetch_screenshot_b64,
    resolve_evidence_urls,
)


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


@pytest.mark.asyncio
async def test_resolve_evidence_urls_prefilled_urls_have_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        called["count"] += 1
        request = httpx.Request("GET", url)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html></html>", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await resolve_evidence_urls(
        settings=_settings(),
        reports_url="https://example.com/r.html",
        screenshot_urls=["https://example.com/a.png", "https://example.com/a.png#dup"],
        screenshot_index_url="https://example.com/index.html",
    )
    assert result["report_url"] == "https://example.com/r.html"
    assert result["screenshot_urls"] == ["https://example.com/a.png"]
    meta = result["url_resolution_meta"]
    assert meta["source"] == "prefilled_urls"
    assert called["count"] == 0


@pytest.mark.asyncio
async def test_resolve_evidence_urls_extracts_relative_paths_from_index(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html><body>
      <img src="../images/1.png" />
      <img src="./2.jpg" />
      <a href="/3.webp">x</a>
      <a href="/not-image.html">skip</a>
    </body></html>
    """

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        request = httpx.Request("GET", url)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=html, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await resolve_evidence_urls(
        settings=_settings(),
        reports_url=None,
        screenshot_urls=[],
        screenshot_index_url="https://example.com/a/b/index.html",
        max_screenshot_candidates=2,
    )
    assert result["screenshot_urls"] == [
        "https://example.com/a/images/1.png",
        "https://example.com/3.webp",
    ]
    meta = result["url_resolution_meta"]
    assert meta["source"] == "index_page"
    assert meta["truncated"] is True


@pytest.mark.asyncio
async def test_resolve_evidence_urls_rejects_unallowed_index_host() -> None:
    result = await resolve_evidence_urls(
        settings=_settings(),
        reports_url=None,
        screenshot_urls=[],
        screenshot_index_url="https://evil.com/index.html",
    )
    assert result["screenshot_urls"] == []
    errors = result["errors"]
    assert isinstance(errors, list)
    assert any(item["code"] == "url_host_not_allowed" for item in errors)


def test_build_success_urls_by_batch_replace_success() -> None:
    result = build_success_urls_by_batch_replace(
        settings=_settings(),
        failed_urls=[
            "https://example.com/reports/batch_20260401/case/screenshots/1.png",
            "https://example.com/reports/batch_20260401/case/screenshots/2.png",
        ],
        failed_batch="20260401",
        success_batch="20260331",
    )
    assert result["success_urls"] == [
        "https://example.com/reports/batch_20260331/case/screenshots/1.png",
        "https://example.com/reports/batch_20260331/case/screenshots/2.png",
    ]
    assert result["errors"] == []


def test_build_success_urls_by_batch_replace_not_applicable() -> None:
    result = build_success_urls_by_batch_replace(
        settings=_settings(),
        failed_urls=["https://example.com/reports/no_batch_marker/1.png"],
        failed_batch="20260401",
        success_batch="20260331",
    )
    assert result["success_urls"] == []
    assert any(item["code"] == "batch_replace_not_applicable" for item in result["errors"])

