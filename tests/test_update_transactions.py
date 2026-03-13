import pytest
from unittest.mock import AsyncMock

from firefly_mcp.models import BulkTransactionUpdate
from firefly_mcp.tools.review import update_transactions


@pytest.mark.asyncio
async def test_update_transactions_convert_to_transfer():
    mock_client = AsyncMock()
    mock_client.update_transaction.return_value = {"data": {}}

    updates = [
        BulkTransactionUpdate(
            transaction_id=1,
            type="transfer",
            destination_id=5,
        ),
        BulkTransactionUpdate(
            transaction_id=2,
            type="transfer",
            destination_name="Investment Account",
        ),
    ]

    result = await update_transactions(updates, client=mock_client)
    assert result["succeeded"] == 2
    assert result["failed"] == 0
    assert mock_client.update_transaction.call_count == 2

    # Verify first call payload
    first_call = mock_client.update_transaction.call_args_list[0]
    assert first_call[0][0] == 1
    payload = first_call[0][1]
    assert payload["transactions"][0]["type"] == "transfer"
    assert payload["transactions"][0]["destination_id"] == 5

    # Verify second call payload
    second_call = mock_client.update_transaction.call_args_list[1]
    payload = second_call[0][1]
    assert payload["transactions"][0]["type"] == "transfer"
    assert payload["transactions"][0]["destination_name"] == "Investment Account"


@pytest.mark.asyncio
async def test_update_transactions_mixed_fields():
    mock_client = AsyncMock()
    mock_client.update_transaction.return_value = {"data": {}}

    updates = [
        BulkTransactionUpdate(
            transaction_id=10,
            category="Investments",
            tags=["stocks"],
            description="Stock Purchase",
        ),
    ]

    result = await update_transactions(updates, client=mock_client)
    assert result["succeeded"] == 1

    payload = mock_client.update_transaction.call_args[0][1]
    txn = payload["transactions"][0]
    assert txn["category_name"] == "Investments"
    assert txn["tags"] == ["stocks"]
    assert txn["description"] == "Stock Purchase"


@pytest.mark.asyncio
async def test_update_transactions_partial_failure():
    mock_client = AsyncMock()
    mock_client.update_transaction.side_effect = [
        {"data": {}},
        Exception("API error"),
        {"data": {}},
    ]

    updates = [
        BulkTransactionUpdate(transaction_id=1, type="transfer", destination_id=5),
        BulkTransactionUpdate(transaction_id=2, type="transfer", destination_id=5),
        BulkTransactionUpdate(transaction_id=3, type="transfer", destination_id=5),
    ]

    result = await update_transactions(updates, client=mock_client)
    assert result["succeeded"] == 2
    assert result["failed"] == 1
    assert result["errors"][0]["transaction_id"] == 2


@pytest.mark.asyncio
async def test_update_transactions_empty_update_skipped():
    mock_client = AsyncMock()

    updates = [
        BulkTransactionUpdate(transaction_id=1),  # No fields set
    ]

    result = await update_transactions(updates, client=mock_client)
    assert result["succeeded"] == 0
    assert result["failed"] == 0
    mock_client.update_transaction.assert_not_called()
