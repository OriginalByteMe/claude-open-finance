import pytest
from unittest.mock import patch, AsyncMock
from datetime import date

from firefly_mcp.tools.insights import _resolve_period, get_spending_summary


@patch("firefly_mcp.tools.insights.date")
def test_resolve_period_this_month(mock_date):
    mock_date.today.return_value = date(2026, 3, 15)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    start, end = _resolve_period("this_month")
    assert start == "2026-03-01"
    assert end == "2026-03-31"


@patch("firefly_mcp.tools.insights.date")
def test_resolve_period_last_month(mock_date):
    mock_date.today.return_value = date(2026, 3, 15)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    start, end = _resolve_period("last_month")
    assert start == "2026-02-01"
    assert end == "2026-02-28"


def test_resolve_period_custom():
    start, end = _resolve_period("2026-01-01:2026-01-31")
    assert start == "2026-01-01"
    assert end == "2026-01-31"


@patch("firefly_mcp.tools.insights.date")
def test_resolve_period_this_year(mock_date):
    mock_date.today.return_value = date(2026, 3, 15)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    start, end = _resolve_period("this_year")
    assert start == "2026-01-01"
    assert end == "2026-12-31"


@pytest.mark.asyncio
async def test_get_spending_summary_by_category():
    mock_client = AsyncMock()
    mock_client.get_insight.return_value = [
        {"name": "Dining", "difference_float": -150.00, "currency_code": "MYR"},
        {"name": "Transport", "difference_float": -80.00, "currency_code": "MYR"},
    ]

    result = await get_spending_summary(
        period="this_month", group_by="category", client=mock_client
    )
    assert result["grand_total"] == 230.00
    assert result["groups"][0]["name"] == "Dining"
    assert result["groups"][1]["name"] == "Transport"


@pytest.mark.asyncio
async def test_get_spending_summary_by_budget_with_limits():
    mock_client = AsyncMock()
    mock_client.get_insight.return_value = [
        {"name": "Eating Out", "difference_float": -120.00, "currency_code": "MYR"},
    ]
    mock_client.list_budgets.return_value = {
        "data": [
            {
                "id": "1",
                "attributes": {
                    "name": "Eating Out",
                    "auto_budget_amount": "200.00",
                    "auto_budget_period": "monthly",
                },
            }
        ]
    }

    result = await get_spending_summary(
        period="2026-03-01:2026-03-31", group_by="budget", client=mock_client
    )
    assert result["groups"][0]["limit"] == 200.0
    assert result["groups"][0]["remaining"] == 80.0
