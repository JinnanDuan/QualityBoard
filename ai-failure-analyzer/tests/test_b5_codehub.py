"""B5 CodeHub 工具测试。"""

import httpx
import pytest

from ai_failure_analyzer.core.config import Settings
from ai_failure_analyzer.services.evidence_tools import (
    CodeHubAuthError,
    codehub_get_commit_diff,
    codehub_list_commits,
)


def _settings() -> Settings:
    return Settings(
        AIFA_CODEHUB_BASE_URL="https://codehub.example.com",
        AIFA_CODEHUB_TOKEN="token",
        AIFA_CODEHUB_CONNECT_TIMEOUT_SECONDS=1,
        AIFA_CODEHUB_READ_TIMEOUT_SECONDS=1,
    )


@pytest.mark.asyncio
async def test_codehub_list_commits_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(
        self: httpx.AsyncClient,
        url: str,
        params: object = None,
        headers: object = None,
    ) -> httpx.Response:
        request = httpx.Request("GET", url)
        assert "commits" in url
        payload = {
            "commits": [
                {
                    "sha": "abc123",
                    "author_name": "alice",
                    "committed_at": "2026-04-22T21:10:01",
                    "message": "fix auth bug",
                    "files": ["src/auth/login.py"],
                }
            ]
        }
        return httpx.Response(200, json=payload, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await codehub_list_commits(
        settings=_settings(),
        repo_url="https://codehub.example.com/group/proj",
        branch="master",
        since="2026-04-21T21:10:01",
        until="2026-04-22T21:10:01",
        path_filters=["src/auth/"],
        limit=30,
    )
    assert "error" not in result
    commits = result["commits"]
    assert isinstance(commits, list)
    assert commits[0]["sha"] == "abc123"
    assert commits[0]["author"] == "alice"


@pytest.mark.asyncio
async def test_codehub_list_commits_401_fail_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(
        self: httpx.AsyncClient,
        url: str,
        params: object = None,
        headers: object = None,
    ) -> httpx.Response:
        request = httpx.Request("GET", url)
        return httpx.Response(401, json={"message": "unauthorized"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with pytest.raises(CodeHubAuthError):
        await codehub_list_commits(
            settings=_settings(),
            repo_url="https://codehub.example.com/group/proj",
            branch="master",
            since="2026-04-21T21:10:01",
            until="2026-04-22T21:10:01",
            path_filters=[],
            limit=30,
        )


@pytest.mark.asyncio
async def test_codehub_get_commit_diff_truncate(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(
        self: httpx.AsyncClient,
        url: str,
        params: object = None,
        headers: object = None,
    ) -> httpx.Response:
        request = httpx.Request("GET", url)
        payload = {
            "diff": "a\nb\nc\nd\ne",
            "files_changed": ["src/a.py"],
        }
        return httpx.Response(200, json=payload, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await codehub_get_commit_diff(
        settings=_settings(),
        repo_url="https://codehub.example.com/group/proj",
        sha="abc123",
        max_lines=3,
    )
    assert "error" not in result
    assert result["truncated"] is True
    assert str(result["diff"]).splitlines() == ["a", "b", "c"]
    assert result["files_changed"] == ["src/a.py"]
