# ============================================================
# 首页看板 — 代码内默认策略（非环境变量）
# ============================================================
# 后续若需按环境区分，可将同名逻辑迁移至 Settings / .env，由 dashboard_service
# 统一读取解析后的结果即可，SQL 结构可保持不变。
# ============================================================

from typing import Tuple

# 是否仅统计 batch（pipeline_overview.batch，与明细表 start_time 同口径的轮次串）
# 以任一「前缀」开头的行
DASHBOARD_BATCH_PREFIX_FILTER_ENABLED: bool = True

# 轮次字符串前缀白名单；任一前缀匹配则保留（LIKE prefix%）
DASHBOARD_BATCH_PREFIXES: Tuple[str, ...] = ("20",)
