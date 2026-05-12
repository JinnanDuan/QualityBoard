import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_openapi_json_available():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body.get("openapi") is not None
    assert "paths" in body
    assert "/api/v1/ut-gate-runs" in body["paths"]
    assert "post" in body["paths"]["/api/v1/ut-gate-runs"]
