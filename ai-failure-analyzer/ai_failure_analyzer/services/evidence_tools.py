"""B1 工具：报告与截图证据拉取。"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Dict, List, Optional, Sequence
from urllib.parse import urljoin, urlparse

import httpx
try:
    from selectolax.parser import HTMLParser
except ImportError:  # pragma: no cover - fallback for minimal environments
    HTMLParser = None  # type: ignore[assignment]

from ai_failure_analyzer.core.config import Settings

logger = logging.getLogger(__name__)

_IMG_EXT_RE = re.compile(r"\.(png|jpe?g|webp|gif|bmp)$", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"[ \t]+")


def _extract_attr_values(html_text: str, tag: str, attr: str) -> List[str]:
    pattern = re.compile(
        r"<%s\b[^>]*\b%s\s*=\s*['\"]([^'\"]+)['\"]" % (re.escape(tag), re.escape(attr)),
        re.IGNORECASE,
    )
    values: List[str] = []
    for match in pattern.finditer(html_text):
        value = (match.group(1) or "").strip()
        if value:
            values.append(value)
    return values


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
    if HTMLParser is None:
        urls = [_normalize_candidate_url(item, base_url) for item in _extract_attr_values(html_text, "img", "src")]
        href_candidates = _extract_attr_values(html_text, "a", "href")
        for item in href_candidates:
            if _IMG_EXT_RE.search(item):
                urls.append(_normalize_candidate_url(item, base_url))
        return _dedup_keep_order([item for item in urls if item])

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

    return _dedup_keep_order(urls)


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


def _extract_text_from_html(html_text: str) -> str:
    if HTMLParser is not None:
        parser = HTMLParser(html_text)
        if parser.body:
            return parser.body.text(separator="\n", strip=True)
        return parser.text(separator="\n")

    no_tags = _TAG_RE.sub(" ", html_text)
    normalized = _SPACE_RE.sub(" ", no_tags)
    lines = [item.strip() for item in normalized.splitlines() if item.strip()]
    return "\n".join(lines)


def _normalize_candidate_url(url: str, base_url: Optional[str] = None) -> Optional[str]:
    raw = (url or "").strip()
    if not raw:
        return None
    if base_url:
        raw = urljoin(base_url, raw)
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return parsed._replace(fragment="").geturl()


def _looks_like_image_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path or ""
    return bool(_IMG_EXT_RE.search(path))


def _dedup_keep_order(urls: Sequence[str]) -> List[str]:
    dedup: List[str] = []
    seen = set()
    for item in urls:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def _replace_batch_segment(url: str, failed_batch: str, success_batch: str) -> Optional[str]:
    """B4：仅在路径段中替换批次子串，保持 scheme/host 不变。"""
    if not failed_batch or not success_batch or failed_batch == success_batch:
        return None
    parsed = urlparse(url)
    path = parsed.path or ""
    segments = path.split("/")
    changed = False
    new_segments: List[str] = []
    for seg in segments:
        if failed_batch in seg:
            new_segments.append(seg.replace(failed_batch, success_batch))
            changed = True
        else:
            new_segments.append(seg)
    if not changed:
        return None
    new_path = "/".join(new_segments)
    return parsed._replace(path=new_path, fragment="").geturl()


def build_success_urls_by_batch_replace(
    settings: Settings,
    failed_urls: Sequence[str],
    failed_batch: Optional[str],
    success_batch: Optional[str],
    max_screenshot_candidates: Optional[int] = None,
) -> Dict[str, object]:
    """B4：按 batch 替换规则从失败侧 URL 生成成功侧截图候选。"""
    limit = (
        max_screenshot_candidates
        if max_screenshot_candidates is not None
        else settings.aifa_screenshot_max_images
    )
    src_failed_batch = (failed_batch or "").strip()
    dst_success_batch = (success_batch or "").strip()
    if not src_failed_batch or not dst_success_batch:
        return {
            "success_urls": [],
            "meta": {"source": "batch_replace", "truncated": False},
            "errors": [{"code": "batch_replace_not_applicable", "field": "batch", "message": "批次信息缺失"}],
        }

    generated: List[str] = []
    for raw in failed_urls:
        normalized = _normalize_candidate_url(str(raw))
        if not normalized:
            continue
        replaced = _replace_batch_segment(normalized, src_failed_batch, dst_success_batch)
        if not replaced:
            continue
        err = _is_allowed_url(replaced, settings)
        if err:
            continue
        generated.append(replaced)
    generated = _dedup_keep_order(generated)
    selected = _pick_urls_by_limit(generated, limit)

    errors: List[Dict[str, str]] = []
    if not selected:
        errors.append(
            {
                "code": "batch_replace_not_applicable",
                "field": "success_screenshot_urls",
                "message": "未找到可替换的批次段或替换结果不可用",
            }
        )
    return {
        "success_urls": selected,
        "meta": {
            "source": "batch_replace",
            "input_count": len(failed_urls),
            "output_count": len(selected),
            "truncated": len(generated) > len(selected),
        },
        "errors": errors,
    }


async def resolve_evidence_urls(
    settings: Settings,
    reports_url: Optional[str],
    screenshot_urls: Optional[Sequence[str]],
    screenshot_index_url: Optional[str],
    max_screenshot_candidates: Optional[int] = None,
) -> Dict[str, object]:
    """B3：解析并归一化报告/截图 URL，输出稳定候选集合。"""
    limit = (
        max_screenshot_candidates
        if max_screenshot_candidates is not None
        else settings.aifa_screenshot_max_images
    )
    errors: List[Dict[str, str]] = []
    warnings: List[str] = []
    source = "none"

    normalized_report_url: Optional[str] = None
    if (reports_url or "").strip():
        candidate = _normalize_candidate_url(str(reports_url))
        if not candidate:
            errors.append(
                {"code": "invalid_reports_url", "field": "reports_url", "message": "reports_url 非法"}
            )
        else:
            report_err = _is_allowed_url(candidate, settings)
            if report_err:
                errors.append(
                    {
                        "code": report_err,
                        "field": "reports_url",
                        "message": "reports_url 不满足白名单或安全规则",
                    }
                )
            else:
                normalized_report_url = candidate

    normalized_screenshot_urls: List[str] = []
    prefilled = screenshot_urls or []
    prefilled_candidates: List[str] = []
    prefilled_rejected = 0
    for item in prefilled:
        normalized = _normalize_candidate_url(str(item))
        if not normalized:
            prefilled_rejected += 1
            continue
        if _is_allowed_url(normalized, settings):
            prefilled_rejected += 1
            continue
        prefilled_candidates.append(normalized)
    prefilled_candidates = _dedup_keep_order(prefilled_candidates)

    if prefilled_candidates:
        source = "prefilled_urls"
        normalized_screenshot_urls = prefilled_candidates
    elif (screenshot_index_url or "").strip():
        source = "index_page"
        index_url = _normalize_candidate_url(str(screenshot_index_url))
        if not index_url:
            errors.append(
                {
                    "code": "invalid_screenshot_index_url",
                    "field": "screenshot_index_url",
                    "message": "screenshot_index_url 非法",
                }
            )
        else:
            index_err = _is_allowed_url(index_url, settings)
            if index_err:
                errors.append(
                    {
                        "code": index_err,
                        "field": "screenshot_index_url",
                        "message": "screenshot_index_url 不满足白名单或安全规则",
                    }
                )
            else:
                timeout = _build_timeout(settings)
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                    try:
                        response = await client.get(index_url)
                    except httpx.HTTPError as exc:
                        errors.append(
                            {
                                "code": "screenshot_index_http_error",
                                "field": "screenshot_index_url",
                                "message": str(exc),
                            }
                        )
                    else:
                        if response.status_code >= 400:
                            errors.append(
                                {
                                    "code": "screenshot_index_http_status_error",
                                    "field": "screenshot_index_url",
                                    "message": "status=%s" % response.status_code,
                                }
                            )
                        else:
                            content_type = (response.headers.get("content-type") or "").lower()
                            if "html" not in content_type:
                                errors.append(
                                    {
                                        "code": "screenshot_index_unsupported_content_type",
                                        "field": "screenshot_index_url",
                                        "message": content_type or "unknown",
                                    }
                                )
                            else:
                                extracted = _extract_image_urls_from_html(index_url, response.text)
                                valid_candidates: List[str] = []
                                for item in extracted:
                                    normalized = _normalize_candidate_url(item)
                                    if not normalized:
                                        continue
                                    if not _looks_like_image_url(normalized):
                                        continue
                                    if _is_allowed_url(normalized, settings):
                                        continue
                                    valid_candidates.append(normalized)
                                normalized_screenshot_urls = _dedup_keep_order(valid_candidates)

    if prefilled_rejected > 0:
        warnings.append("prefilled_screenshot_urls_rejected=%s" % prefilled_rejected)

    selected = _pick_urls_by_limit(normalized_screenshot_urls, limit)
    if len(normalized_screenshot_urls) > len(selected):
        warnings.append("screenshot_candidates_truncated")

    if source == "none" and not selected:
        errors.append(
            {
                "code": "missing_screenshot_urls",
                "field": "screenshot_urls",
                "message": "缺少可用截图 URL",
            }
        )

    return {
        "report_url": normalized_report_url,
        "screenshot_urls": selected,
        "url_resolution_meta": {
            "source": source,
            "input_count": len(prefilled),
            "output_count": len(selected),
            "truncated": len(normalized_screenshot_urls) > len(selected),
            "warnings": warnings,
        },
        "errors": errors,
    }


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
    body_text = _extract_text_from_html(raw)
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

