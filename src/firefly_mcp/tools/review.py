from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient
from firefly_mcp.models import BulkTransactionUpdate, CompactTransaction, TransactionUpdate


def _needs_review(txn: CompactTransaction, filter_type: str) -> bool:
    """Check if a transaction matches the review filter."""
    if filter_type == "untagged":
        return len(txn.tags) == 0
    if filter_type == "uncategorized":
        return txn.category is None
    if filter_type == "unbudgeted":
        return txn.budget is None
    # all_unreviewed: missing any of tags, category, or budget
    return len(txn.tags) == 0 or txn.category is None or txn.budget is None


async def get_review_queue(
    days_back: Annotated[int, Field(description="How many days back to look", ge=1)] = 30,
    filter: Annotated[
        str,
        Field(description="Filter: 'untagged', 'uncategorized', 'unbudgeted', or 'all_unreviewed'"),
    ] = "all_unreviewed",
    *,
    client: FireflyClient,
) -> list[CompactTransaction]:
    """Fetch transactions needing review -- missing tags, categories, or budgets."""
    end = date.today()
    start = end - timedelta(days=days_back)

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
            txn = CompactTransaction.from_api(item)
            if _needs_review(txn, filter):
                all_txns.append(txn)

        total_pages = data.get("meta", {}).get("pagination", {}).get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return all_txns


async def categorize_transactions(
    updates: Annotated[
        list[TransactionUpdate],
        Field(description="List of transaction updates to apply"),
    ],
    *,
    client: FireflyClient,
) -> dict:
    """Batch-apply categories, tags, budgets, and notes to multiple transactions."""
    succeeded = 0
    failed: list[dict] = []

    for update in updates:
        payload: dict = {"transactions": [{}]}
        txn_payload = payload["transactions"][0]

        if update.category is not None:
            txn_payload["category_name"] = update.category
        if update.tags is not None:
            txn_payload["tags"] = update.tags
        if update.budget is not None:
            txn_payload["budget_name"] = update.budget
        if update.notes is not None:
            txn_payload["notes"] = update.notes

        if not txn_payload:
            continue

        try:
            await client.update_transaction(update.transaction_id, payload)
            succeeded += 1
        except Exception as e:
            failed.append({"transaction_id": update.transaction_id, "error": str(e)})

    return {
        "succeeded": succeeded,
        "failed": len(failed),
        "errors": failed,
        "total": len(updates),
    }


async def update_transactions(
    updates: Annotated[
        list[BulkTransactionUpdate],
        Field(description="List of transaction updates to apply"),
    ],
    *,
    client: FireflyClient,
) -> dict:
    """Bulk-update transactions: change type, destination, description, amount, and metadata.

    Use this to convert withdrawals to transfers, set destination accounts,
    or make any other changes to transaction fields in bulk.
    For type conversion to 'transfer', provide destination_id (account ID) or
    destination_name (account name) along with type='transfer'.
    """
    succeeded = 0
    failed: list[dict] = []

    field_map = {
        "type": "type",
        "source_id": "source_id",
        "destination_id": "destination_id",
        "destination_name": "destination_name",
        "category": "category_name",
        "tags": "tags",
        "budget": "budget_name",
        "notes": "notes",
        "description": "description",
        "amount": "amount",
    }

    for update in updates:
        payload: dict = {"transactions": [{}]}
        txn_payload = payload["transactions"][0]

        for attr, api_field in field_map.items():
            value = getattr(update, attr)
            if value is not None:
                txn_payload[api_field] = value

        if not txn_payload:
            continue

        try:
            await client.update_transaction(update.transaction_id, payload)
            succeeded += 1
        except Exception as e:
            failed.append({"transaction_id": update.transaction_id, "error": str(e)})

    return {
        "succeeded": succeeded,
        "failed": len(failed),
        "errors": failed,
        "total": len(updates),
    }
