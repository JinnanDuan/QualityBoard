"""
WeLink 卡片消息：Playwright 登录取 Cookie + POST share_url。

配置见 config/welink_card.ini.example；路径由 WELINK_CARD_INI_PATH 指定。
"""

from __future__ import annotations

import configparser
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

# 进程内缓存 Cookie 串；发送失败会清空并重新登录
_cached_cookie_header: Optional[str] = None

MAX_SEND_ATTEMPTS = 3

# 与常见桌面 Chrome 接近，降低无头特征（仍可能被站点风控）
_DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _cookies_to_header(cookies: List[Dict[str, Any]]) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name"))


def _parse_ini_bool(value: Optional[str], default: bool) -> bool:
    """解析 ini 中的布尔：缺省或空则 default。"""
    if value is None:
        return default
    v = value.strip().lower()
    if not v:
        return default
    if v in ("0", "false", "no", "off", "n"):
        return False
    if v in ("1", "true", "yes", "on", "y"):
        return True
    return default


def _parse_ini_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(s)
    except ValueError:
        return default


def _safe_page_url(page: Any) -> str:
    try:
        return (page.url or "").strip()
    except Exception:
        return ""


_T = TypeVar("_T")


def _playwright_step(page: Any, phase: str, action: Callable[[], _T]) -> _T:
    """执行一步 Playwright 操作，失败时打当前页诊断后原样抛出。"""
    try:
        return action()
    except Exception:
        _log_page_state_after_stall(page, _safe_page_url(page), phase)
        raise


def _page_text_snippet(page: Any, max_len: int = 500) -> str:
    """短超时抓取 body 可见文本。"""
    try:
        raw = page.inner_text("body", timeout=2000)
        s = (raw or "").replace("\n", " ").strip()
        return s[:max_len] if s else ""
    except Exception:
        return ""


def _log_page_state_after_stall(
    page: Any,
    last_url: str,
    phase: str,
) -> str:
    """超时/失败时打 ERROR（含页面文本摘要），并返回短说明供异常信息使用（摘要不重复进异常）。"""
    url_disp = last_url if last_url else "(page.url 为空或无法读取)"
    logger.error("welink 登录阶段失败 [%s] 当前地址: %s", phase, url_disp[:500])
    snippet = _page_text_snippet(page, max_len=600)
    if snippet:
        logger.error("welink 页面文本摘要: %s", snippet)
    low = (last_url or "").lower()
    if "login.huawei.com" in low and "login" in low:
        return (
            " 说明：若仍停在华为登录域，多为风控/验证码/密码等。"
        )
    if not last_url:
        return " 说明：page.url 为空时可能未成功打开页面。"
    return " 说明：请核对登录是否完成或增大 login_wait_timeout_ms。"


def _fetch_cookies_playwright(
    login_page_url: str,
    username: str,
    password: str,
    ignore_https_errors: bool,
    login_wait_timeout_ms: int,
    browser_user_agent: Optional[str],
) -> str:
    from playwright.sync_api import sync_playwright

    # SSH 开启 X11 转发时 DISPLAY 可能指向本机，Chromium 会尝试连 X11，Xshell 会弹 Xmanager。
    # 启动浏览器子进程时去掉 DISPLAY，强制纯 headless，不经过 X11。
    _launch_env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
    _chromium_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        # 减弱自动化特征（部分站点仍可能拦截无头环境）
        "--disable-blink-features=AutomationControlled",
    ]
    if ignore_https_errors:
        _chromium_args.append("--ignore-certificate-errors")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=_chromium_args,
            env=_launch_env,
        )
        try:
            ua = (browser_user_agent or "").strip() or _DEFAULT_BROWSER_USER_AGENT
            context = browser.new_context(
                ignore_https_errors=ignore_https_errors,
                user_agent=ua,
                locale="zh-CN",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            _playwright_step(
                page,
                "打开 login_page_url",
                lambda: page.goto(
                    login_page_url, wait_until="domcontentloaded", timeout=60000
                ),
            )
            _playwright_step(
                page,
                "等待登录页 #username 出现",
                lambda: page.wait_for_selector(
                    "#username", state="visible", timeout=30000
                ),
            )
            page.fill("#username", username)
            page.fill("#password", password)
            page.click("#w3-login-button")
            try:
                page.wait_for_load_state("networkidle", timeout=login_wait_timeout_ms)
            except Exception as e:
                extra = _log_page_state_after_stall(
                    page,
                    _safe_page_url(page),
                    "登录提交后等待 networkidle",
                )
                raise RuntimeError(
                    f"登录后等待 networkidle 超时（{login_wait_timeout_ms}ms）。{extra}"
                ) from e
            cookies = context.cookies()
            header = _cookies_to_header(cookies)
            if not header:
                raise RuntimeError("登录后未获取到任何 Cookie")
            logger.info("welink playwright 登录成功，cookie 条数=%d", len(cookies))
            return header
        finally:
            browser.close()


def _welink_share_response_ok(body: Any) -> bool:
    """黄区样例：外层 code=200，data 为 JSON 字符串，内层 data.is_success=1。"""
    if not isinstance(body, dict):
        return False
    if body.get("code") != 200:
        return False
    data = body.get("data")
    if isinstance(data, str):
        try:
            inner = json.loads(data)
        except json.JSONDecodeError:
            return False
        if isinstance(inner, dict) and inner.get("code") != 200:
            return False
        if isinstance(inner, dict):
            inner_data = inner.get("data")
            if isinstance(inner_data, dict) and inner_data.get("is_success") == 1:
                return True
    if isinstance(data, dict):
        inner_data = data.get("data")
        if isinstance(inner_data, dict) and inner_data.get("is_success") == 1:
            return True
    return False


class WelinkCardShare:
    """读取 welink_card.ini，Playwright 登录取 Cookie 后 POST 分享接口。"""

    def __init__(self, ini_path: str) -> None:
        self._ini_path = Path(ini_path).expanduser()
        self._config = configparser.ConfigParser()
        self._config.optionxform = lambda option: option

    def _read_config(self) -> None:
        if not self._ini_path.is_file():
            raise FileNotFoundError(f"WeLink 配置文件不存在: {self._ini_path}")
        read_ok = self._config.read(self._ini_path, encoding="utf-8")
        if not read_ok:
            raise ValueError(f"无法读取 WeLink 配置文件: {self._ini_path}")

    def _get_section(self, section: str) -> Dict[str, str]:
        if section not in self._config.sections():
            raise ValueError(f"配置缺少 section [{section}]: {self._ini_path}")
        return dict(self._config.items(section))

    def send_card(self, ids: str, content: str, remark: str, url: str) -> Any:
        global _cached_cookie_header

        self._read_config()
        bl = self._get_section("browser_login")
        login_page_url = (bl.get("login_page_url") or "").strip()
        username = (bl.get("username") or "").strip()
        password = (bl.get("password") or "").strip()
        browser_user_agent = (bl.get("browser_user_agent") or "").strip() or None
        login_wait_timeout_ms = _parse_ini_int(
            bl.get("login_wait_timeout_ms"), default=120000
        )
        if login_wait_timeout_ms < 5000:
            login_wait_timeout_ms = 5000
        # 内网/自签证书：设为 false 时，Playwright 与 httpx 均跳过证书校验
        ssl_verify = _parse_ini_bool(bl.get("ssl_verify"), default=True)
        if not ssl_verify:
            logger.warning(
                "welink 已关闭 HTTPS 证书校验（ssl_verify=false），仅建议在受信内网使用"
            )
        if not login_page_url or not username or not password:
            raise ValueError(
                "WeLink 配置 [browser_login] 须包含 login_page_url、username、password"
            )

        share_header = self._get_section("share_header")
        share_data: Dict[str, Any] = dict(self._get_section("share_data"))
        # modelType 等保持与 ini 一致；若为纯数字字符串可转为 int 便于 JSON
        if "modelType" in share_data and str(share_data["modelType"]).isdigit():
            share_data["modelType"] = int(str(share_data["modelType"]))
        share_data.update(
            {"ids": ids, "content": content, "remark": remark, "url": url}
        )
        share_url = self._get_section("share_url")["url"].strip()

        logger.info(
            "welink send_card: ids=%s, content=%s, link_url=%s",
            ids,
            content,
            url,
        )
        logger.info(
            "welink share POST share_url=%s body=%s",
            share_url,
            json.dumps(share_data, ensure_ascii=False),
        )

        last_err: Optional[Exception] = None
        with httpx.Client(timeout=120.0, verify=ssl_verify) as client:
            for attempt in range(MAX_SEND_ATTEMPTS):
                # 首次且已有缓存：先带缓存 Cookie 发；否则或重试时重新 Playwright 登录
                if attempt == 0 and _cached_cookie_header is not None:
                    cookie_header = _cached_cookie_header
                else:
                    cookie_header = _fetch_cookies_playwright(
                        login_page_url,
                        username,
                        password,
                        ignore_https_errors=not ssl_verify,
                        login_wait_timeout_ms=login_wait_timeout_ms,
                        browser_user_agent=browser_user_agent,
                    )
                    _cached_cookie_header = cookie_header

                req_headers = dict(share_header)
                req_headers["Cookie"] = cookie_header
                resp = client.post(share_url, json=share_data, headers=req_headers)
                text_preview = (resp.text or "")[:800]
                if resp.status_code != 200:
                    last_err = RuntimeError(
                        f"WeLink 分享 HTTP {resp.status_code}: {text_preview}"
                    )
                    logger.warning(
                        "welink 分享失败 attempt=%s http=%s",
                        attempt + 1,
                        resp.status_code,
                    )
                    _cached_cookie_header = None
                    continue
                try:
                    body = resp.json()
                except json.JSONDecodeError as e:
                    last_err = RuntimeError(f"WeLink 响应非 JSON: {text_preview}")
                    logger.warning("welink 响应解析失败 attempt=%s", attempt + 1)
                    _cached_cookie_header = None
                    continue
                if _welink_share_response_ok(body):
                    logger.info("welink 分享业务成功 attempt=%s", attempt + 1)
                    return body
                last_err = RuntimeError(
                    f"WeLink 业务未成功: {json.dumps(body, ensure_ascii=False)[:800]}"
                )
                logger.warning(
                    "welink 业务 is_success 非 1 attempt=%s body=%s",
                    attempt + 1,
                    json.dumps(body, ensure_ascii=False)[:500],
                )
                _cached_cookie_header = None

        _cached_cookie_header = None
        if last_err:
            raise last_err
        raise RuntimeError("WeLink 分享失败")


def rolling_welink_share(
    user: str,
    content: str,
    remark: str,
    url: str,
) -> Tuple[bool, str]:
    """
    向指定域账号发送 WeLink 卡片（与 spec/13 约定一致）。

    :param user: ums_email.domain_account（首字母+工号）
    :return: (是否成功, 中文说明)
    """
    ini_path = (settings.WELINK_CARD_INI_PATH or "").strip()
    if not ini_path:
        return False, "WeLink 未配置：请设置环境变量 WELINK_CARD_INI_PATH 为卡片配置文件路径"
    if not user:
        return False, "接收人为空，无法发送"

    try:
        WelinkCardShare(ini_path).send_card(user, content, remark, url)
        return True, "发送成功"
    except Exception:
        logger.exception("welink send_card failed user=%s", user)
        return False, "发送失败，详见服务日志"


def rolling_welink_alert(
    user: str,
    content: str,
    remark: str,
    url: str,
) -> Tuple[bool, str]:
    """兼容黄区命名。"""
    return rolling_welink_share(user, content, remark, url)
