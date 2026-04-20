"""SSE ``report`` 事件与 trace 结构（A1 最小集）。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


FailureCategory = Literal[
    "bug",
    "环境问题",
    "规格变更，用例需适配",
    "用例不稳定，需加固",
    "unknown",
]
ReportStatus = Literal["ok", "partial", "error"]


class EvidenceItem(BaseModel):
    id: str = "e0"
    type: str = "history_pattern"
    source: str = "payload"
    snippet: str = ""
    reference: str = ""


class StageTimelineItem(BaseModel):
    stage: str
    message: str
    elapsed_ms: int = 0


class ReportInner(BaseModel):
    failure_category: FailureCategory = "unknown"
    verdict: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    detailed_reason: str = ""
    rationale_summary: Optional[str] = None
    stage_timeline: List[StageTimelineItem] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    suspect_patches: Optional[list] = None
    suggested_next_steps: Optional[List[str]] = None
    data_gaps: List[str] = Field(default_factory=list)


class TracePayload(BaseModel):
    skills_invoked: List[str] = Field(default_factory=lambda: ["llm_single"])
    tool_calls: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    elapsed_ms: int = 0


class AnalyzeReportEnvelope(BaseModel):
    """``event: report`` 的 data JSON 顶层。"""

    session_id: str
    status: ReportStatus
    report: ReportInner
    trace: TracePayload
