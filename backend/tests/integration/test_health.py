"""Integration tests for GET /api/v1/health.

TDD RED phase: written before the controller exists.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_health_returns_200_with_ok_checks(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert body["data"]["checks"]["db"] == "ok"


@pytest.mark.integration
async def test_health_includes_correlation_id_header(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert "X-Correlation-Id" in response.headers
    assert len(response.headers["X-Correlation-Id"]) == 36  # UUID4


@pytest.mark.integration
async def test_health_propagates_provided_correlation_id(client: AsyncClient) -> None:
    custom_id = "test-correlation-id-12345"
    response = await client.get("/api/v1/health", headers={"X-Correlation-Id": custom_id})

    assert response.headers["X-Correlation-Id"] == custom_id
