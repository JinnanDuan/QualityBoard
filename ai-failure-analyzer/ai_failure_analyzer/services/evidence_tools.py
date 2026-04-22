"""B1 工具：报告与截图证据拉取。"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Dict, List, Optional, Sequence
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from ai_failure_analyzer.core.config import Settings

logger = logging.getLogger(__name__)

_IMG_EXT_RE = re.compile(r"\.(png|jpe?g|webp|gif|bmp)$", re.IGNORECASE)


def _truncate_text(text: str, max_chars: int) -> Dict[str, object]:
    if max_chars <= 0:
        return {"text": "", "truncated": bool(text), "content_length": len(text)}
    if len(text) <= max_chars:
        return {"text": text, "truncated": False, "content_length": len(text)}
    return {"text": text[:max_chars], "truncated": True, "content_length": len(text)}


def _is_allowed_url(url: str, settings: Settings) -> Optional[str]:
    if len(url) > settings.aifa_fetch_url_max_length:
        return "url_too_long"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "url_scheme_not_allowed"
    host = (parsed.hostname or "").lower()
    if not host:
        return "url_host_missing"
    allowed = settings.aifa_fetch_allowed_hosts
    if allowed:
        allowed_hit = False
        for candidate in allowed:
            c = candidate.strip().lower()
            if not c:
                continue
            if host == c or host.endswith("." + c):
                allowed_hit = True
                break
        if not allowed_hit:
            return "url_host_not_allowed"
    return None


def _build_timeout(settings: Settings) -> httpx.Timeout:
    return httpx.Timeout(
        connect=settings.aifa_fetch_connect_timeout_seconds,
        read=settings.aifa_fetch_read_timeout_seconds,
        write=settings.aifa_fetch_read_timeout_seconds,
        pool=settings.aifa_fetch_connect_timeout_seconds,
    )


def _extract_image_urls_from_html(base_url: str, html_text: str) -> List[str]:
    parser = HTMLParser(html_text)
    urls: List[str] = []

    for node in parser.css("img"):
        src = (node.attributes.get("src") or "").strip()
        if src:
            urls.append(urljoin(base_url, src))

    for node in parser.css("a"):
        href = (node.attributes.get("href") or "").strip()
        if not href:
            continue
        if _IMG_EXT_RE.search(href):
            urls.append(urljoin(base_url, href))

    dedup: List[str] = []
    seen = set()
    for item in urls:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def _pick_urls_by_limit(urls: Sequence[str], max_images: int) -> List[str]:
    if max_images <= 0:
        return []
    if len(urls) <= max_images:
        return list(urls)
    if max_images == 1:
        return [urls[-1]]
    return list(urls[: max_images - 1]) + [urls[-1]]


def _safe_url_for_log(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    if len(path) > 64:
        path = path[:61] + "..."
    return "%s://%s%s" % (parsed.scheme or "?", parsed.netloc or "?", path)


async def _fetch_binary_image(
    client: httpx.AsyncClient,
    screenshot_url: str,
    max_bytes: int,
) -> Dict[str, object]:
    try:
        response = await client.get(screenshot_url)
    except httpx.HTTPError as exc:
        return {"error": "http_error", "detail": str(exc)}
    if response.status_code >= 400:
        return {"error": "http_status_error", "detail": "status=%s" % response.status_code}
    content_type = (response.headers.get("content-type") or "").lower()
    if not content_type.startswith("image/"):
        return {"error": "unsupported_content_type", "detail": content_type or "unknown"}
    content = response.content
    if len(content) > max_bytes:
        return {
            "error": "image_too_large",
            "detail": "size=%s exceeds max_bytes=%s" % (len(content), max_bytes),
        }
    import base64

    digest = hashlib.sha256(content).hexdigest()[:16]
    return {
        "base64": base64.b64encode(content).decode("ascii"),
        "mime": content_type.split(";")[0].strip(),
        "size_bytes": len(content),
        "content_sha256_prefix": digest,
        "source_url": screenshot_url,
    }


async def fetch_report_html(
    reports_url: str,
    settings: Settings,
    max_chars: Optional[int] = None,
) -> Dict[str, object]:
    """拉取报告 HTML 并提取可用文本。"""
    err = _is_allowed_url(reports_url, settings)
    if err:
        return {"error": err, "detail": _safe_url_for_log(reports_url)}

    limit = max_chars if max_chars is not None else settings.aifa_report_max_chars
    timeout = _build_timeout(settings)
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        try:
            response = await client.get(reports_url)
        except httpx.HTTPError as exc:
            return {"error": "http_error", "detail": str(exc)}
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    if response.status_code >= 400:
        return {"error": "http_status_error", "detail": "status=%s" % response.status_code}
    content_type = (response.headers.get("content-type") or "").lower()
    if "html" not in content_type:
        return {"error": "unsupported_content_type", "detail": content_type or "unknown"}

    raw = response.text
    parser = HTMLParser(raw)
    body_text = parser.body.text(separator="\n", strip=True) if parser.body else parser.text(separator="\n")
    result = _truncate_text(body_text, limit)
    logger.info(
        "B1 fetch_report_html ok url=%s elapsed_ms=%s raw_len=%s out_len=%s truncated=%s",
        _safe_url_for_log(reports_url),
        elapsed_ms,
        len(raw),
        len(str(result["text"])),
        result["truncated"],
    )
    return result


async def fetch_screenshot_b64(
    screenshot_url: str,
    settings: Settings,
    max_bytes: Optional[int] = None,
    max_images: Optional[int] = None,
) -> Dict[str, object]:
    """拉取截图：支持 image 直链或 HTML 索引页。"""
    err = _is_allowed_url(screenshot_url, settings)
    if err:
        return {"error": err, "detail": _safe_url_for_log(screenshot_url)}

    limit_bytes = max_bytes if max_bytes is not None else settings.aifa_screenshot_max_bytes
    limit_images = max_images if max_images is not None else settings.aifa_screenshot_max_images
    timeout = _build_timeout(settings)
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        try:
            response = await client.get(screenshot_url)
        except httpx.HTTPError as exc:
            return {"error": "http_error", "detail": str(exc)}
        if response.status_code >= 400:
            return {"error": "http_status_error", "detail": "status=%s" % response.status_code}

        content_type = (response.headers.get("content-type") or "").lower()
        if content_type.startswith("image/"):
            one = await _fetch_binary_image(client, screenshot_url, limit_bytes)
            if "error" in one:
                return one
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                "B1 fetch_screenshot_b64 image ok url=%s elapsed_ms=%s size_bytes=%s",
                _safe_url_for_log(screenshot_url),
                elapsed_ms,
                one.get("size_bytes"),
            )
            return one

        if "html" not in content_type:
            return {"error": "unsupported_content_type", "detail": content_type or "unknown"}

        urls = _extract_image_urls_from_html(screenshot_url, response.text)
        picked = _pick_urls_by_limit(urls, limit_images)
        images: List[Dict[str, object]] = []
        skipped_errors: List[str] = []
        for child_url in picked:
            child_err = _is_allowed_url(child_url, settings)
            if child_err:
                skipped_errors.append("%s:%s" % (child_err, _safe_url_for_log(child_url)))
                continue
            one = await _fetch_binary_image(client, child_url, limit_bytes)
            if "error" in one:
                skipped_errors.append("%s:%s" % (one.get("error"), _safe_url_for_log(child_url)))
                continue
            images.append(one)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "B1 fetch_screenshot_b64 index ok url=%s elapsed_ms=%s total_found=%s selected=%s ok=%s skipped=%s",
        _safe_url_for_log(screenshot_url),
        elapsed_ms,
        len(urls),
        len(picked),
        len(images),
        len(skipped_errors),
    )
    return {
        "images": images,
        "image_count": len(images),
        "selected_count": len(picked),
        "total_found": len(urls),
        "truncated_by_max_images": len(urls) > len(picked),
        "skipped_errors": skipped_errors,
    }

