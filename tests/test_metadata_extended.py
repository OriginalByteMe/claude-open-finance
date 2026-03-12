import pytest
from unittest.mock import AsyncMock

from firefly_mcp.tools.metadata import get_financial_context, manage_metadata


@pytest.mark.asyncio
async def test_manage_metadata_update_tag():
    mock_client = AsyncMock()
    mock_client.update_tag.return_value = {"data": {"id": "5"}}

    result = await manage_metadata(
        action="update_tag", name="new-name", entity_id=5, client=mock_client
    )
    assert result["updated"] == "tag"
    assert result["id"] == 5
    mock_client.update_tag.assert_called_once_with(5, {"tag": "new-name"})


@pytest.mark.asyncio
async def test_manage_metadata_update_tag_requires_id():
    mock_client = AsyncMock()
    result = await manage_metadata(action="update_tag", name="x", client=mock_client)
    assert "error" in result


@pytest.mark.asyncio
async def test_manage_metadata_delete_tag():
    mock_client = AsyncMock()
    result = await manage_metadata(action="delete_tag", entity_id=3, client=mock_client)
    assert result["deleted"] == "tag"
    mock_client.delete_tag.assert_called_once_with(3)


@pytest.mark.asyncio
async def test_manage_metadata_update_category():
    mock_client = AsyncMock()
    mock_client.update_category.return_value = {"data": {"id": "2"}}

    result = await manage_metadata(
        action="update_category", name="Dining Out", entity_id=2, client=mock_client
    )
    assert result["updated"] == "category"
    mock_client.update_category.assert_called_once_with(2, {"name": "Dining Out"})


@pytest.mark.asyncio
async def test_manage_metadata_delete_category():
    mock_client = AsyncMock()
    result = await manage_metadata(action="delete_category", entity_id=7, client=mock_client)
    assert result["deleted"] == "category"


@pytest.mark.asyncio
async def test_manage_metadata_delete_budget():
    mock_client = AsyncMock()
    result = await manage_metadata(action="delete_budget", entity_id=4, client=mock_client)
    assert result["deleted"] == "budget"
    mock_client.delete_budget.assert_called_once_with(4)


@pytest.mark.asyncio
async def test_manage_metadata_create_account():
    mock_client = AsyncMock()
    mock_client.create_account.return_value = {"data": {"id": "10"}}

    result = await manage_metadata(
        action="create_account", name="Savings", account_type="asset",
        currency_code="MYR", client=mock_client,
    )
    assert result["created"] == "account"
    assert result["name"] == "Savings"
    call_payload = mock_client.create_account.call_args[0][0]
    assert call_payload["name"] == "Savings"
    assert call_payload["type"] == "asset"
    assert call_payload["currency_code"] == "MYR"


@pytest.mark.asyncio
async def test_manage_metadata_create_account_defaults():
    mock_client = AsyncMock()
    mock_client.create_account.return_value = {"data": {"id": "11"}}

    result = await manage_metadata(
        action="create_account", name="Checking", client=mock_client
    )
    assert result["created"] == "account"
    call_payload = mock_client.create_account.call_args[0][0]
    assert call_payload["type"] == "asset"


@pytest.mark.asyncio
async def test_manage_metadata_update_account():
    mock_client = AsyncMock()
    mock_client.update_account.return_value = {"data": {"id": "10"}}

    result = await manage_metadata(
        action="update_account", name="New Name", entity_id=10, client=mock_client,
    )
    assert result["updated"] == "account"
    mock_client.update_account.assert_called_once_with(10, {"name": "New Name"})


@pytest.mark.asyncio
async def test_manage_metadata_delete_account():
    mock_client = AsyncMock()
    result = await manage_metadata(action="delete_account", entity_id=10, client=mock_client)
    assert result["deleted"] == "account"


@pytest.mark.asyncio
async def test_manage_metadata_create_bill():
    mock_client = AsyncMock()
    mock_client.create_bill.return_value = {"data": {"id": "20"}}

    result = await manage_metadata(
        action="create_bill", name="Netflix", amount_min=15.99, amount_max=15.99,
        repeat_freq="monthly", client=mock_client,
    )
    assert result["created"] == "bill"
    assert result["name"] == "Netflix"
    call_payload = mock_client.create_bill.call_args[0][0]
    assert call_payload["name"] == "Netflix"
    assert call_payload["repeat_freq"] == "monthly"


@pytest.mark.asyncio
async def test_manage_metadata_create_bill_requires_amounts():
    mock_client = AsyncMock()
    result = await manage_metadata(
        action="create_bill", name="Netflix", client=mock_client
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_manage_metadata_update_bill():
    mock_client = AsyncMock()
    mock_client.update_bill.return_value = {"data": {"id": "20"}}

    result = await manage_metadata(
        action="update_bill", entity_id=20, name="Netflix Premium",
        amount_min=22.99, amount_max=22.99, client=mock_client,
    )
    assert result["updated"] == "bill"


@pytest.mark.asyncio
async def test_manage_metadata_delete_bill():
    mock_client = AsyncMock()
    result = await manage_metadata(action="delete_bill", entity_id=20, client=mock_client)
    assert result["deleted"] == "bill"


@pytest.mark.asyncio
async def test_fetch_tags_includes_ids():
    mock_client = AsyncMock()
    mock_client.list_tags.return_value = {
        "data": [
            {"id": "1", "attributes": {"tag": "restaurant", "date": None}},
        ]
    }
    result = await get_financial_context(what="tags", client=mock_client)
    assert result["tags"][0]["id"] == 1
    assert result["tags"][0]["name"] == "restaurant"


@pytest.mark.asyncio
async def test_fetch_accounts_includes_ids():
    mock_client = AsyncMock()
    mock_client.list_accounts.return_value = {
        "data": [
            {
                "id": "5",
                "attributes": {
                    "name": "Checking",
                    "type": "asset",
                    "current_balance": "1000.00",
                    "currency_code": "MYR",
                },
            }
        ]
    }
    result = await get_financial_context(what="accounts", client=mock_client)
    assert result["accounts"][0]["id"] == 5


@pytest.mark.asyncio
async def test_fetch_bills_includes_ids():
    mock_client = AsyncMock()
    mock_client.list_bills.return_value = {
        "data": [
            {
                "id": "3",
                "attributes": {
                    "name": "Netflix",
                    "amount_min": "15.99",
                    "amount_max": "15.99",
                    "repeat_freq": "monthly",
                },
            }
        ]
    }
    result = await get_financial_context(what="bills", client=mock_client)
    assert result["bills"][0]["id"] == 3
