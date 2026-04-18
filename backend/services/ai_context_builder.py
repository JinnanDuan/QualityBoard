# ============================================================
# AI 分析上下文 — 仅只读拼装发往 AIFA 的 JSON（无 LLM、无 log_url）
# 规格：docs/superpowers/specs/dt-report-phase-a2-ai-context-builder-spec.md
# ============================================================

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.pipeline_history import PipelineHistory
from backend.services.history_service import list_recent_executions_by_case_platform

logger = logging.getLogger(__name__)

# A2：与规格默认 N=20 一致；单字段截断防止 token 膨胀
RECENT_EXECUTIONS_LIMIT = 20
MAX_STRING_CHARS = 2000
MAX_PATH_HINTS = 50
MAX_PATH_HINT_LEN = 500


class AIContextHistoryNotFoundError(Exception):
    """pipeline_history 不存在时由 API 层转换为 404。"""

    def __init__(self, history_id: int) -> None:
        self.history_id = history_id
        super().__init__(f"执行记录不存在: history_id={history_id}")


def _truncate(value: Optional[str], max_chars: int = MAX_STRING_CHARS) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 3] + "..."


@lru_cache(maxsize=8)
def _parse_module_repo_mapping_file(resolved_path: str) -> Tuple[Dict[str, Any], ...]:
    """
    解析 config/module_repo_mapping.yaml（或部署路径）。
    路径为空或文件不存在时返回空元组；解析失败时 WARNING 并返回空。
    """
    if not resolved_path:
        return ()
    p = Path(resolved_path)
    if not p.is_file():
        return ()
    try:
        raw = p.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except Exception:
        logger.warning("module_repo_mapping 文件无法解析: path=%s", resolved_path, exc_info=True)
        return ()
    if not data or not isinstance(data, dict):
        return ()
    mappings = data.get("mappings")
    if not isinstance(mappings, list):
        return ()
    out: List[Dict[str, Any]] = []
    for m in mappings:
        if isinstance(m, dict):
            out.append(m)
    return tuple(out)


def _repo_hint_for_main_module(main_module: Optional[str]) -> Dict[str, Any]:
    mm = (main_module or "").strip()
    if not mm:
        return {}
    path = (settings.AI_MODULE_REPO_MAPPING_PATH or "").strip()
    if not path:
        return {}
    try:
        resolved = str(Path(path).resolve())
    except Exception:
        resolved = path
    for m in _parse_module_repo_mapping_file(resolved):
        if str(m.get("main_module", "")).strip() != mm:
            continue
        rh: Dict[str, Any] = {}
        ru = m.get("repo_url")
        if ru is not None and str(ru).strip():
            rh["repo_url"] = _truncate(str(ru), MAX_STRING_CHARS)
        db = m.get("default_branch")
        if db is not None and str(db).strip():
            rh["default_branch"] = _truncate(str(db), 512)
        ph = m.get("path_hints")
        if isinstance(ph, list):
            hints: List[str] = []
            for h in ph[:MAX_PATH_HINTS]:
                if h is None:
                    continue
                t = _truncate(str(h), MAX_PATH_HINT_LEN)
                if t:
                    hints.append(t)
            if hints:
                rh["path_hints"] = hints
        return rh
    return {}


def _case_context_from_row(row: PipelineHistory) -> Dict[str, Any]:
    """构造 case_context；禁止包含 log_url。"""
    ctx: Dict[str, Any] = {
        "history_id": row.id,
        "batch": _truncate(row.start_time),
        "case_name": _truncate(row.case_name),
        "platform": _truncate(row.platform),
        "main_module": _truncate(row.main_module) or "",
        "module": _truncate(row.module),
        "subtask": _truncate(row.subtask),
        # 与 batch 同源（轮次）；便于与旧字段名兼容
        "start_time": _truncate(row.start_time),
        "case_result": _truncate(row.case_result),
        "code_branch": _truncate(row.code_branch),
        "pipeline_url": _truncate(row.pipeline_url),
        "reports_url": _truncate(row.reports_url),
        "case_level": _truncate(row.case_level) or "",
    }
    su = _truncate(row.screenshot_url, MAX_STRING_CHARS)
    if su:
        ctx["screenshot_index_url"] = su
        ctx["screenshot_urls"] = [su]
    # A2：成功侧 batch/URL 替换见 Phase B4；此处不伪造
    return {k: v for k, v in ctx.items() if v is not None and v != ""}


async def build_analyze_payload(db: AsyncSession, history_id: int) -> Dict[str, Any]:
    """
    拼装发往 AIFA 的 JSON 片段（不含 session_id/mode；由 ai_proxy 合并）。
    禁止包含日志 HTML URL。
    """
    stmt = select(PipelineHistory).where(PipelineHistory.id == history_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise AIContextHistoryNotFoundError(history_id)

    case_context = _case_context_from_row(row)
    recent = await list_recent_executions_by_case_platform(
        db,
        row.case_name,
        row.platform,
        RECENT_EXECUTIONS_LIMIT,
    )
    recent_executions: List[Dict[str, Optional[str]]] = []
    for item in recent:
        recent_executions.append(
            {
                "start_time": _truncate(item.get("start_time")),
                "case_result": _truncate(item.get("case_result")),
                "code_branch": _truncate(item.get("code_branch")),
            }
        )

    repo_hint = _repo_hint_for_main_module(row.main_module)

    payload: Dict[str, Any] = {
        "case_context": case_context,
        "recent_executions": recent_executions,
        "repo_hint": repo_hint,
    }
    return payload
