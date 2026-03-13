from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient
from firefly_mcp.models import CompactTransaction


def _normalize_description(desc: str) -> str:
    """Normalize a transaction description for grouping.

    Strips trailing digits/reference numbers and lowercases for comparison.
    """
    import re
    # Remove trailing reference numbers, dates, and IDs
    cleaned = re.sub(r"\s*[-/]\s*\d{6,}$", "", desc)
    cleaned = re.sub(r"\s*#\d+$", "", cleaned)
    cleaned = re.sub(r"\s+\d{2,4}[/-]\d{2,4}([/-]\d{2,4})?$", "", cleaned)
    return cleaned.strip().lower()


def _detect_frequency(dates: list[date]) -> dict | None:
    """Detect the most likely frequency from a list of transaction dates.

    Returns frequency info or None if no pattern is detected.
    """
    if len(dates) < 2:
        return None

    sorted_dates = sorted(dates)
    gaps = [(sorted_dates[i + 1] - sorted_dates[i]).days for i in range(len(sorted_dates) - 1)]

    if not gaps:
        return None

    avg_gap = sum(gaps) / len(gaps)
    median_gap = sorted(gaps)[len(gaps) // 2]

    # Classify frequency based on median gap
    if 5 <= median_gap <= 10:
        freq = "weekly"
        expected_gap = 7
    elif 12 <= median_gap <= 18:
        freq = "biweekly"
        expected_gap = 14
    elif 25 <= median_gap <= 35:
        freq = "monthly"
        expected_gap = 30
    elif 55 <= median_gap <= 70:
        freq = "bimonthly"
        expected_gap = 60
    elif 80 <= median_gap <= 100:
        freq = "quarterly"
        expected_gap = 91
    elif 170 <= median_gap <= 195:
        freq = "half-yearly"
        expected_gap = 182
    elif 350 <= median_gap <= 380:
        freq = "yearly"
        expected_gap = 365
    else:
        return None

    # Check consistency — at least half the gaps should be close to expected
    close_gaps = sum(1 for g in gaps if abs(g - expected_gap) <= expected_gap * 0.35)
    if close_gaps < len(gaps) * 0.5:
        return None

    return {
        "frequency": freq,
        "avg_gap_days": round(avg_gap, 1),
        "median_gap_days": median_gap,
        "consistency": round(close_gaps / len(gaps), 2),
    }


async def discover_recurring(
    days_back: Annotated[int, Field(description="How many days of history to analyze", ge=30)] = 180,
    min_occurrences: Annotated[int, Field(description="Minimum times a transaction must repeat", ge=2)] = 3,
    *,
    client: FireflyClient,
) -> dict:
    """Analyze transaction history to discover recurring patterns (subscriptions, bills, regular payments).

    Scans withdrawals over the specified period, groups by similar descriptions,
    and detects frequency patterns. Returns groups that appear to be recurring.
    """
    end = date.today()
    start = end - timedelta(days=days_back)

    # Fetch all withdrawals in the period
    all_txns: list[CompactTransaction] = []
    page = 1
    while True:
        data = await client.list_transactions(
            start=start.isoformat(),
            end=end.isoformat(),
            type="withdrawal",
            page=page,
        )
        for item in data.get("data", []):
            all_txns.append(CompactTransaction.from_api(item))

        total_pages = data.get("meta", {}).get("pagination", {}).get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    # Group by normalized description
    groups: dict[str, list[CompactTransaction]] = defaultdict(list)
    for txn in all_txns:
        key = _normalize_description(txn.description)
        groups[key].append(txn)

    # Filter to groups with enough occurrences and detect frequency
    recurring: list[dict] = []
    for key, txns in groups.items():
        if len(txns) < min_occurrences:
            continue

        dates = [date.fromisoformat(t.date) for t in txns]
        freq_info = _detect_frequency(dates)

        if freq_info is None:
            continue

        amounts = [t.amount for t in txns]
        avg_amount = sum(amounts) / len(amounts)
        amount_variance = max(amounts) - min(amounts)
        is_fixed_amount = amount_variance <= avg_amount * 0.1

        # Use the most recent transaction as the representative
        latest = max(txns, key=lambda t: t.date)

        recurring.append({
            "description": latest.description,
            "normalized_key": key,
            "occurrences": len(txns),
            "frequency": freq_info["frequency"],
            "avg_amount": round(avg_amount, 2),
            "amount_range": {"min": min(amounts), "max": max(amounts)},
            "fixed_amount": is_fixed_amount,
            "consistency": freq_info["consistency"],
            "avg_gap_days": freq_info["avg_gap_days"],
            "first_seen": min(t.date for t in txns),
            "last_seen": max(t.date for t in txns),
            "destination": latest.destination,
            "has_bill": False,  # Could be enriched if bills are linked
            "sample_transaction_ids": [t.id for t in sorted(txns, key=lambda t: t.date)[-3:]],
        })

    # Sort by occurrence count descending
    recurring.sort(key=lambda r: r["occurrences"], reverse=True)

    # Check which recurring items already have bills linked
    bills_data = await client.list_bills()
    bill_names = {b["attributes"]["name"].lower() for b in bills_data.get("data", [])}
    for item in recurring:
        if item["normalized_key"] in bill_names or item["destination"].lower() in bill_names:
            item["has_bill"] = True

    return {
        "recurring": recurring,
        "total_found": len(recurring),
        "period_analyzed": {"start": start.isoformat(), "end": end.isoformat()},
        "total_transactions_scanned": len(all_txns),
    }
