"""与架构 §4.1 对齐的请求体（无 log_url）。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CaseContext(BaseModel):
    model_config = {"extra": "ignore"}

    history_id: Optional[int] = None
    batch: Optional[str] = None
    case_name: Optional[str] = None
    platform: Optional[str] = None
    main_module: Optional[str] = None
    module: Optional[str] = None
    subtask: Optional[str] = None
    start_time: Optional[str] = None
    case_result: Optional[str] = None
    code_branch: Optional[str] = None
    screenshot_index_url: Optional[str] = None
    screenshot_urls: Optional[List[str]] = None
    pipeline_url: Optional[str] = None
    reports_url: Optional[str] = None
    case_level: Optional[str] = None
    last_success_batch: Optional[str] = None
    success_screenshot_index_url: Optional[str] = None
    success_screenshot_urls: Optional[List[str]] = None


class RecentExecution(BaseModel):
    model_config = {"extra": "ignore"}

    start_time: Optional[str] = None
    case_result: Optional[str] = None
    code_branch: Optional[str] = None


class RepoHint(BaseModel):
    model_config = {"extra": "ignore"}

    repo_url: Optional[str] = None
    default_branch: Optional[str] = None
    path_hints: Optional[List[str]] = None


class AnalyzeRequest(BaseModel):
    session_id: str = Field(..., description="会话 UUID")
    mode: Literal["initial", "follow_up"] = "initial"
    follow_up_message: Optional[str] = None
    case_context: Optional[CaseContext] = None
    recent_executions: Optional[List[RecentExecution]] = None
    repo_hint: Optional[RepoHint] = None

    model_config = {"extra": "forbid"}
