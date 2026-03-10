import pytest
from unittest.mock import AsyncMock

from firefly_mcp.tools.review import get_review_queue, categorize_transactions
from firefly_mcp.models import TransactionUpdate
from tests.conftest import SAMPLE_TRANSACTION


@pytest.mark.asyncio
async def test_get_review_queue_returns_untagged():
    mock_client = AsyncMock()
    mock_client.list_transactions.return_value = {
        "data": [SAMPLE_TRANSACTION],
        "meta": {"pagination": {"total_pages": 1}},
    }

    result = await get_review_queue(
        days_back=30,
        filter="all_unreviewed",
        client=mock_client,
    )
    assert len(result) == 1
    assert result[0].description == "GRAB FOOD"
    assert result[0].category is None


@pytest.mark.asyncio
async def test_categorize_transactions_batch():
    mock_client = AsyncMock()
    mock_client.update_transaction.return_value = {"data": {}}

    updates = [
        TransactionUpdate(transaction_id=1, category="Dining", tags=["restaurant"]),
        TransactionUpdate(transaction_id=2, budget="Transport", notes="Grab ride"),
    ]

    result = await categorize_transactions(updates, client=mock_client)
    assert result["succeeded"] == 2
    assert result["failed"] == 0
    assert mock_client.update_transaction.call_count == 2


@pytest.mark.asyncio
async def test_categorize_transactions_partial_failure():
    mock_client = AsyncMock()
    mock_client.update_transaction.side_effect = [
        {"data": {}},
        Exception("API error"),
    ]

    updates = [
        TransactionUpdate(transaction_id=1, category="Dining"),
        TransactionUpdate(transaction_id=2, category="Transport"),
    ]

    result = await categorize_transactions(updates, client=mock_client)
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["errors"][0]["transaction_id"] == 2
