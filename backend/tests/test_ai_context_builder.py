import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.pipeline_history import PipelineHistory
from backend.services.ai_context_builder import (
    AIContextHistoryNotFoundError,
    RECENT_EXECUTIONS_LIMIT,
    _parse_module_repo_mapping_file,
    _repo_hint_for_main_module,
    _truncate,
    build_analyze_payload,
)
from backend.services.history_service import list_recent_executions_by_case_platform


def test_truncate_short_unchanged() -> None:
    assert _truncate("abc") == "abc"
    assert _truncate(None) is None
    assert _truncate("  ") is None


def test_truncate_long() -> None:
    s = "x" * 5000
    out = _truncate(s, max_chars=100)
    assert out is not None
    assert len(out) == 100
    assert out.endswith("...")


def test_parse_module_repo_mapping_missing_file(tmp_path) -> None:
    p = str(tmp_path / "nope.yaml")
    _parse_module_repo_mapping_file.cache_clear()
    assert _parse_module_repo_mapping_file(p) == ()


def test_parse_module_repo_mapping_valid(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    y = tmp_path / "m.yaml"
    y.write_text(
        "mappings:\n  - main_module: \"auth\"\n    repo_url: \"https://h.example/r\"\n    default_branch: \"main\"\n    path_hints: [\"a/\"]\n",
        encoding="utf-8",
    )
    _parse_module_repo_mapping_file.cache_clear()
    t = _parse_module_repo_mapping_file(str(y.resolve()))
    assert len(t) == 1
    assert t[0].get("main_module") == "auth"


def test_repo_hint_for_main_module(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    y = tmp_path / "m.yaml"
    y.write_text(
        "mappings:\n  - main_module: \"pay\"\n    repo_url: \"https://h.example/pay\"\n    default_branch: \"dev\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.services.ai_context_builder.settings.AI_MODULE_REPO_MAPPING_PATH",
        str(y.resolve()),
    )
    _parse_module_repo_mapping_file.cache_clear()
    h = _repo_hint_for_main_module("pay")
    assert h.get("repo_url") == "https://h.example/pay"
    assert h.get("default_branch") == "dev"
    _parse_module_repo_mapping_file.cache_clear()


@pytest.mark.asyncio
async def test_build_analyze_payload_history_not_found() -> None:
    r1 = MagicMock()
    r1.scalar_one_or_none.return_value = None
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=r1)
    with pytest.raises(AIContextHistoryNotFoundError) as ei:
        await build_analyze_payload(mock_db, 999)
    assert ei.value.history_id == 999


@pytest.mark.asyncio
async def test_build_analyze_payload_no_log_url(monkeypatch: pytest.MonkeyPatch) -> None:
    row = MagicMock(spec=PipelineHistory)
    row.id = 42
    row.start_time = "202604011200"
    row.case_name = "case_login_fail"
    row.platform = "Android"
    row.main_module = "auth"
    row.module = "auth"
    row.subtask = "g1"
    row.case_result = "failed"
    row.code_branch = "master"
    row.pipeline_url = "http://jenkins/p/1"
    row.reports_url = "http://reports/batch/report/"
    row.case_level = "P0"
    row.screenshot_url = "http://img/s.png"
    row.log_url = "http://logs/SECRET.html"  # 不得进入 payload

    r1 = MagicMock()
    r1.scalar_one_or_none.return_value = row
    r2 = MagicMock()
    r2.all.return_value = [
        ("202604011200", "failed", "master"),
        ("202603011200", "passed", "master"),
    ]
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=[r1, r2])

    payload = await build_analyze_payload(mock_db, 42)
    raw = json.dumps(payload, ensure_ascii=False)
    assert "log_url" not in raw
    assert "SECRET" not in raw

    assert payload["case_context"]["history_id"] == 42
    assert payload["case_context"]["batch"] == "202604011200"
    assert payload["case_context"]["case_name"] == "case_login_fail"
    assert payload["case_context"]["platform"] == "Android"
    assert payload["case_context"]["screenshot_index_url"] == "http://img/s.png"

    assert isinstance(payload["recent_executions"], list)
    assert len(payload["recent_executions"]) <= RECENT_EXECUTIONS_LIMIT
    assert payload["repo_hint"] == {}


@pytest.mark.asyncio
async def test_list_recent_executions_empty_when_missing_names() -> None:
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    out = await list_recent_executions_by_case_platform(mock_db, None, "Android", 20)
    assert out == []
    mock_db.execute.assert_not_called()
