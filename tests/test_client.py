import pytest
import respx
import httpx

from firefly_mcp.client import FireflyClient
from tests.conftest import SAMPLE_TRANSACTION


def test_client_init():
    client = FireflyClient(
        firefly_url="http://localhost:8080",
        token="test-token",
        importer_url="http://localhost:8081",
        importer_secret="test-secret-16chars",
    )
    assert client.firefly_url == "http://localhost:8080"
    assert client.importer_url == "http://localhost:8081"


@respx.mock
@pytest.mark.asyncio
async def test_list_transactions(client):
    respx.get("http://firefly.test/api/v1/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [SAMPLE_TRANSACTION],
                "meta": {"pagination": {"total": 1, "count": 1, "total_pages": 1}},
            },
        )
    )
    result = await client.list_transactions(start="2026-03-01", end="2026-03-31")
    assert len(result["data"]) == 1


@respx.mock
@pytest.mark.asyncio
async def test_search_transactions(client):
    respx.get("http://firefly.test/api/v1/search/transactions").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    result = await client.search_transactions("amount_more:100")
    assert result["data"] == []


@respx.mock
@pytest.mark.asyncio
async def test_upload_csv(client):
    respx.post("http://importer.test/autoupload").mock(
        return_value=httpx.Response(200, text="Import complete. 5 transactions imported.")
    )
    result = await client.upload_csv(b"date,amount\n2026-03-01,25.50", '{"version": 3}')
    assert "5 transactions" in result
