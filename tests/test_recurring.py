import pytest
from unittest.mock import AsyncMock

from firefly_mcp.tools.recurring import (
    _normalize_description,
    _detect_frequency,
    discover_recurring,
)
from datetime import date, timedelta


# -- Unit tests for helpers --


def test_normalize_description_strips_trailing_reference():
    assert _normalize_description("NETFLIX SUBSCRIPTION - 123456") == "netflix subscription"


def test_normalize_description_strips_trailing_hash():
    assert _normalize_description("SPOTIFY PREMIUM #987") == "spotify premium"


def test_normalize_description_strips_trailing_date():
    assert _normalize_description("GRAB FOOD 03/15") == "grab food"


def test_normalize_description_preserves_normal_text():
    assert _normalize_description("STARBUCKS KLCC") == "starbucks klcc"


def test_detect_frequency_monthly():
    dates = [date(2026, 1, 1) + timedelta(days=30 * i) for i in range(5)]
    result = _detect_frequency(dates)
    assert result is not None
    assert result["frequency"] == "monthly"


def test_detect_frequency_weekly():
    dates = [date(2026, 1, 5) + timedelta(days=7 * i) for i in range(6)]
    result = _detect_frequency(dates)
    assert result is not None
    assert result["frequency"] == "weekly"


def test_detect_frequency_yearly():
    dates = [date(2023, 3, 1), date(2024, 3, 1), date(2025, 3, 1)]
    result = _detect_frequency(dates)
    assert result is not None
    assert result["frequency"] == "yearly"


def test_detect_frequency_too_few_dates():
    result = _detect_frequency([date(2026, 1, 1)])
    assert result is None


def test_detect_frequency_irregular():
    # Random gaps that don't fit any pattern
    dates = [date(2026, 1, 1), date(2026, 1, 5), date(2026, 3, 20), date(2026, 4, 2)]
    result = _detect_frequency(dates)
    assert result is None


# -- Integration test for discover_recurring --


def _make_transaction(id: int, description: str, date_str: str, amount: str = "15.00"):
    return {
        "id": str(id),
        "attributes": {
            "transactions": [
                {
                    "transaction_journal_id": str(id),
                    "type": "withdrawal",
                    "date": f"{date_str}T00:00:00+00:00",
                    "amount": amount,
                    "description": description,
                    "source_name": "Checking",
                    "destination_name": description.split()[0],
                    "category_name": None,
                    "budget_name": None,
                    "tags": [],
                    "notes": None,
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_discover_recurring_finds_monthly_subscription():
    mock_client = AsyncMock()

    # Create 5 monthly Netflix transactions
    transactions = [
        _make_transaction(i + 1, "NETFLIX SUBSCRIPTION", f"2025-{10 + i:02d}-15" if 10 + i <= 12 else f"2026-{10 + i - 12:02d}-15")
        for i in range(5)
    ]

    mock_client.list_transactions.return_value = {
        "data": transactions,
        "meta": {"pagination": {"total_pages": 1}},
    }
    mock_client.list_bills.return_value = {"data": []}

    result = await discover_recurring(days_back=180, min_occurrences=3, client=mock_client)
    assert result["total_found"] >= 1
    found = result["recurring"][0]
    assert "netflix" in found["normalized_key"]
    assert found["frequency"] == "monthly"
    assert found["occurrences"] == 5


@pytest.mark.asyncio
async def test_discover_recurring_skips_infrequent():
    mock_client = AsyncMock()

    # Only 2 transactions — below min_occurrences=3
    transactions = [
        _make_transaction(1, "RARE PURCHASE", "2026-01-01"),
        _make_transaction(2, "RARE PURCHASE", "2026-02-01"),
    ]

    mock_client.list_transactions.return_value = {
        "data": transactions,
        "meta": {"pagination": {"total_pages": 1}},
    }
    mock_client.list_bills.return_value = {"data": []}

    result = await discover_recurring(days_back=180, min_occurrences=3, client=mock_client)
    assert result["total_found"] == 0


@pytest.mark.asyncio
async def test_discover_recurring_marks_existing_bills():
    mock_client = AsyncMock()

    transactions = [
        _make_transaction(i + 1, "SPOTIFY PREMIUM", f"2025-{10 + i:02d}-01" if 10 + i <= 12 else f"2026-{10 + i - 12:02d}-01")
        for i in range(4)
    ]

    mock_client.list_transactions.return_value = {
        "data": transactions,
        "meta": {"pagination": {"total_pages": 1}},
    }
    mock_client.list_bills.return_value = {
        "data": [
            {
                "id": "1",
                "attributes": {
                    "name": "spotify premium",
                    "amount_min": "15.00",
                    "amount_max": "15.00",
                    "repeat_freq": "monthly",
                },
            }
        ]
    }

    result = await discover_recurring(days_back=180, min_occurrences=3, client=mock_client)
    assert result["total_found"] >= 1
    spotify = [r for r in result["recurring"] if "spotify" in r["normalized_key"]]
    assert len(spotify) == 1
    assert spotify[0]["has_bill"] is True


@pytest.mark.asyncio
async def test_discover_recurring_empty_history():
    mock_client = AsyncMock()
    mock_client.list_transactions.return_value = {
        "data": [],
        "meta": {"pagination": {"total_pages": 1}},
    }
    mock_client.list_bills.return_value = {"data": []}

    result = await discover_recurring(days_back=180, min_occurrences=3, client=mock_client)
    assert result["total_found"] == 0
    assert result["total_transactions_scanned"] == 0
