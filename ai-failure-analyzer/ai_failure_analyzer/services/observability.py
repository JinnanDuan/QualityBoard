"""C4 观测与成本：trace 持久化与进程内 metrics 聚合。"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_METRICS_LOCK = threading.Lock()
_REQUESTS_TOTAL = 0
_REQUESTS_OK = 0
_REQUESTS_PARTIAL = 0
_REQUESTS_ERROR = 0
_TOKENS_INPUT_TOTAL = 0
_TOKENS_OUTPUT_TOTAL = 0
_ESTIMATED_COST_TOTAL = 0.0
_CIRCUIT_BREAKER_TRIGGERED_TOTAL = 0
_EXTERNAL_DEPENDENCY_ERROR_TOTAL = 0
_LATENCIES_MS: List[int] = []
_MAX_LATENCY_SAMPLES = 2000


def _percentile(sorted_values: List[int], q: float) -> int:
    if not sorted_values:
        return 0
    if q <= 0:
        return sorted_values[0]
    if q >= 1:
        return sorted_values[-1]
    idx = int((len(sorted_values) - 1) * q)
    return sorted_values[idx]


def record_analyze_outcome(
    *,
    status: str,
    elapsed_ms: int,
    llm_input_tokens: int,
    llm_output_tokens: int,
    estimated_cost: float,
    circuit_breaker_triggered: bool,
    external_dependency_error: bool,
) -> None:
    global _REQUESTS_TOTAL
    global _REQUESTS_OK
    global _REQUESTS_PARTIAL
    global _REQUESTS_ERROR
    global _TOKENS_INPUT_TOTAL
    global _TOKENS_OUTPUT_TOTAL
    global _ESTIMATED_COST_TOTAL
    global _CIRCUIT_BREAKER_TRIGGERED_TOTAL
    global _EXTERNAL_DEPENDENCY_ERROR_TOTAL

    with _METRICS_LOCK:
        _REQUESTS_TOTAL += 1
        normalized = (status or "error").strip().lower()
        if normalized == "ok":
            _REQUESTS_OK += 1
        elif normalized == "partial":
            _REQUESTS_PARTIAL += 1
        else:
            _REQUESTS_ERROR += 1
        _TOKENS_INPUT_TOTAL += max(0, int(llm_input_tokens))
        _TOKENS_OUTPUT_TOTAL += max(0, int(llm_output_tokens))
        _ESTIMATED_COST_TOTAL += max(0.0, float(estimated_cost))
        if circuit_breaker_triggered:
            _CIRCUIT_BREAKER_TRIGGERED_TOTAL += 1
        if external_dependency_error:
            _EXTERNAL_DEPENDENCY_ERROR_TOTAL += 1
        _LATENCIES_MS.append(max(0, int(elapsed_ms)))
        if len(_LATENCIES_MS) > _MAX_LATENCY_SAMPLES:
            overflow = len(_LATENCIES_MS) - _MAX_LATENCY_SAMPLES
            if overflow > 0:
                del _LATENCIES_MS[:overflow]


def get_metrics_snapshot() -> Dict[str, Any]:
    with _METRICS_LOCK:
        ordered = sorted(_LATENCIES_MS)
        p50 = _percentile(ordered, 0.50)
        p95 = _percentile(ordered, 0.95)
        tokens_total = _TOKENS_INPUT_TOTAL + _TOKENS_OUTPUT_TOTAL
        return {
            "requests_total": _REQUESTS_TOTAL,
            "requests_ok": _REQUESTS_OK,
            "requests_partial": _REQUESTS_PARTIAL,
            "requests_error": _REQUESTS_ERROR,
            "request_latency_p50_ms": p50,
            "request_latency_p95_ms": p95,
            "tokens_input_total": _TOKENS_INPUT_TOTAL,
            "tokens_output_total": _TOKENS_OUTPUT_TOTAL,
            "tokens_total": tokens_total,
            "estimated_cost_total": round(_ESTIMATED_COST_TOTAL, 6),
            "circuit_breaker_triggered_total": _CIRCUIT_BREAKER_TRIGGERED_TOTAL,
            "external_dependency_error_total": _EXTERNAL_DEPENDENCY_ERROR_TOTAL,
        }


def append_trace_line(trace_log_path: str, payload: Dict[str, Any]) -> None:
    safe_path = (trace_log_path or "trace.log").strip() or "trace.log"
    line = json.dumps(payload, ensure_ascii=False)
    try:
        parent = os.path.dirname(safe_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(safe_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001
        logger.exception("写入 trace 失败 path=%s", safe_path)


def build_trace_payload(
    *,
    request_id: str,
    session_id: str,
    history_id: int,
    status: str,
    elapsed_ms: int,
    trace_obj: Dict[str, Any],
    error_code: str = "",
    error_message: str = "",
    data_gaps: List[str] = None,
) -> Dict[str, Any]:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "timestamp": ts,
        "request_id": request_id,
        "session_id": session_id,
        "history_id": history_id,
        "status": status,
        "elapsed_ms": int(elapsed_ms),
        "error_code": error_code,
        "error_message": error_message,
        "skills_invoked": trace_obj.get("skills_invoked", []),
        "tool_calls": trace_obj.get("tool_calls", 0),
        "llm_input_tokens": trace_obj.get("llm_input_tokens", 0),
        "llm_output_tokens": trace_obj.get("llm_output_tokens", 0),
        "estimated_cost": trace_obj.get("estimated_cost", 0.0),
        "token_budget_triggered": bool(trace_obj.get("token_budget_triggered", False)),
        "degrade_reasons": trace_obj.get("degrade_reasons", []),
        "data_gaps": list(data_gaps or []),
    }
