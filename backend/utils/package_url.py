# ============================================================
# 取包地址拼接（占位符：code_branch、start_time、package_name）
# ============================================================

from typing import Optional, Tuple


def resolve_package_url(
    init_url: str,
    package_name_mac: str,
    package_name_oh: str,
    code_branch: Optional[str],
    start_time: Optional[str],
    platform: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """
  生成取包链接。

  :return: (url, hint)。hint 为 ``unknown_platform`` 时表示平台不支持；其余失败为 (None, None)。
  """
    template = (init_url or "").strip()
    if not template:
        return None, None

    branch = (code_branch or "").strip()
    batch = (start_time or "").strip().replace("_", "")
    if not branch or not batch:
        return None, None

    plat = (platform or "").strip().lower()
    if plat == "mac":
        package_name = (package_name_mac or "").strip()
    elif plat == "oh":
        package_name = (package_name_oh or "").strip()
    else:
        return None, "unknown_platform"

    if not package_name:
        return None, None

    url = (
        template.replace("code_branch", branch)
        .replace("start_time", batch)
        .replace("package_name", package_name)
    )
    return url, None
