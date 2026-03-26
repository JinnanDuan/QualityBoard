"""
WeLink 卡片消息（会话登录 + 发卡片），配置来自独立 INI 文件路径。

黄区逻辑参考：testvigil/tuil/welink_card（share.py / rolling_alert.py）。
仓库内仅保留模板：config/welink_card.ini.example；生产路径由 WELINK_CARD_INI_PATH 指定。
"""

from __future__ import annotations

import configparser
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)


class WelinkCardShare:
    """读取 welink_card.ini，先登录再调用分享接口。"""

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
        self._read_config()
        login_header = self._get_section("login_header")
        login_data = self._get_section("login_data")
        login_url = self._get_section("login_url")["url"]
        share_header = self._get_section("share_header")
        share_data = dict(self._get_section("share_data"))
        share_data.update({"ids": ids, "content": content, "remark": remark, "url": url})
        share_url = self._get_section("share_url")["url"]

        logger.info(
            "welink send_card: ids=%s, content=%s, url=%s",
            ids,
            content,
            url,
        )
        with httpx.Client(timeout=30.0) as client:
            login_resp = client.post(login_url, headers=login_header, data=login_data)
            login_resp.raise_for_status()
            resp = client.post(share_url, json=share_data, headers=share_header)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"WeLink 分享请求失败 HTTP {resp.status_code}: {resp.text[:500]}"
                )
            logger.info("welink send_card status_code=%s", resp.status_code)
            return resp.json()


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
