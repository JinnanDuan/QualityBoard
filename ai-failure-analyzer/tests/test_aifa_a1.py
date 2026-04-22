"""A1 验收用例（不依赖外网 LLM）。"""

import json
import uuid
from typing import Any, Dict, List, Tuple

import pytest
from httpx import ASGITransport, AsyncClient

from ai_failure_analyzer.main import app


def _parse_sse(body: str) -> List[Tuple[str, Dict[str, Any]]]:
    events: List[Tuple[str, Dict[str, Any]]] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = None
        data_payload = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                raw = line[len("data:") :].strip()
                data_payload = json.loads(raw)
        if event_name and data_payload is not None:
            events.append((event_name, data_payload))
    return events


@pytest.fixture
def any_session_id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_healthz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["checks"]["report_fetch"] == "skipped"
    assert data["checks"]["llm"] == "ok"


@pytest.mark.asyncio
async def test_healthz_llm_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIFA_LLM_MOCK", raising=False)
    monkeypatch.delenv("AIFA_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AIFA_LLM_API_KEY", raising=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["checks"]["llm"] == "not_configured"


@pytest.mark.asyncio
async def test_analyze_missing_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIFA_INTERNAL_TOKEN", "test-secret-token")
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/analyze",
            json={"session_id": str(uuid.uuid4()), "mode": "initial"},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_analyze_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIFA_INTERNAL_TOKEN", "test-secret-token")
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/analyze",
            headers={"Authorization": "Bearer wrong"},
            json={"session_id": str(uuid.uuid4()), "mode": "initial"},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_analyze_mock_sse_and_category_guard(
    monkeypatch: pytest.MonkeyPatch,
    any_session_id: str,
) -> None:
    monkeypatch.setenv("AIFA_INTERNAL_TOKEN", "test-secret-token")
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/analyze",
            headers={"Authorization": "Bearer test-secret-token"},
            json={
                "session_id": any_session_id,
                "mode": "initial",
                "case_context": {
                    "case_name": "demo",
                    "batch": "b1",
                    "platform": "Android",
                },
            },
        )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    events = _parse_sse(r.text)
    kinds = [e[0] for e in events]
    assert kinds.count("progress") >= 4
    assert "report" in kinds
    report_data = next(d for k, d in events if k == "report")
    assert report_data["session_id"] == any_session_id
    assert report_data["status"] == "partial"
    assert report_data["report"]["failure_category"] == "unknown"
    assert len(report_data["report"]["stage_timeline"]) >= 3
    assert any("plan" == item["stage"] for item in report_data["report"]["stage_timeline"])
    assert any("act" == item["stage"] for item in report_data["report"]["stage_timeline"])
    assert any("synthesis" == item["stage"] for item in report_data["report"]["stage_timeline"])
    assert any("截图" in g for g in report_data["report"]["data_gaps"])
    progress_stages = [d.get("stage") for k, d in events if k == "progress"]
    assert "plan_started" in progress_stages
    assert "plan_done" in progress_stages
    assert "act_started" in progress_stages
    assert "act_done" in progress_stages
    assert "synthesize_started" in progress_stages
    assert "synthesize_done" in progress_stages


@pytest.mark.asyncio
async def test_analyze_mock_keeps_spec_change_with_evidence(
    monkeypatch: pytest.MonkeyPatch,
    any_session_id: str,
) -> None:
    monkeypatch.setenv("AIFA_INTERNAL_TOKEN", "test-secret-token")
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/analyze",
            headers={"Authorization": "Bearer test-secret-token"},
            json={
                "session_id": any_session_id,
                "mode": "initial",
                "case_context": {
                    "case_name": "demo",
                    "success_screenshot_urls": ["http://example.com/a.png"],
                },
            },
        )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    report_data = next(d for k, d in events if k == "report")
    assert report_data["report"]["failure_category"] == "规格变更，用例需适配"


@pytest.mark.asyncio
async def test_follow_up_with_existing_session(
    monkeypatch: pytest.MonkeyPatch,
    any_session_id: str,
) -> None:
    monkeypatch.setenv("AIFA_INTERNAL_TOKEN", "test-secret-token")
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/v1/analyze",
            headers={"Authorization": "Bearer test-secret-token"},
            json={
                "session_id": any_session_id,
                "mode": "initial",
                "case_context": {"case_name": "demo"},
            },
        )
        assert first.status_code == 200
        follow = await client.post(
            "/v1/analyze",
            headers={"Authorization": "Bearer test-secret-token"},
            json={
                "session_id": any_session_id,
                "mode": "follow_up",
                "follow_up_message": "再解释一下结论",
            },
        )
    assert follow.status_code == 200
    events = _parse_sse(follow.text)
    report_data = next(d for k, d in events if k == "report")
    assert report_data["session_id"] == any_session_id
    assert report_data["trace"]["skills_invoked"] == ["synthesis_skill"]


@pytest.mark.asyncio
async def test_follow_up_without_session_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIFA_INTERNAL_TOKEN", "test-secret-token")
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/analyze",
            headers={"Authorization": "Bearer test-secret-token"},
            json={
                "session_id": str(uuid.uuid4()),
                "mode": "follow_up",
                "follow_up_message": "是否是环境问题",
            },
        )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    kinds = [k for k, _ in events]
    assert "error" in kinds
    err = next(d for k, d in events if k == "error")
    assert err["error_code"] == "session_not_found"


@pytest.mark.asyncio
async def test_analyze_missing_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIFA_INTERNAL_TOKEN", "test-secret-token")
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/analyze",
            headers={"Authorization": "Bearer test-secret-token"},
            json={"mode": "initial"},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_analyze_body_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIFA_INTERNAL_TOKEN", "test-secret-token")
    monkeypatch.setenv("AIFA_LLM_MOCK", "1")
    transport = ASGITransport(app=app)
    huge = "x" * (600 * 1024)
    payload = {"session_id": str(uuid.uuid4()), "mode": "initial", "case_context": {"case_name": huge}}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/analyze",
            headers={"Authorization": "Bearer test-secret-token"},
            json=payload,
        )
    assert r.status_code == 400
