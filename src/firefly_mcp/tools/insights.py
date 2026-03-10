from __future__ import annotations

import calendar
from datetime import date as _date_type
from datetime import timedelta
from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient

# Module-level reference so tests can mock it
date = _date_type


def _resolve_period(period: str) -> tuple[str, str]:
    """Convert a period string to (start_date, end_date) ISO strings."""
    today = date.today()

    if period == "this_month":
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
    elif period == "last_month":
        first_of_this = today.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        start = last_of_prev.replace(day=1)
        end = last_of_prev
    elif period == "this_year":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
    elif ":" in period:
        parts = period.split(":", 1)
        return parts[0], parts[1]
    else:
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)

    return start.isoformat(), end.isoformat()


INSIGHT_GROUPS = {
    "category": "category",
    "tag": "tag",
    "budget": "budget",
    "account": "asset",
}


async def get_spending_summary(
    period: Annotated[
        str,
        Field(description="Period: 'this_month', 'last_month', 'this_year', or 'YYYY-MM-DD:YYYY-MM-DD'"),
    ] = "this_month",
    group_by: Annotated[
        str,
        Field(description="Group by: 'category', 'tag', 'budget', or 'account'"),
    ] = "category",
    *,
    client: FireflyClient,
) -> dict:
    """Get aggregated spending summary for a period, grouped by category/tag/budget/account."""
    start, end = _resolve_period(period)
    insight_group = INSIGHT_GROUPS.get(group_by, "category")

    data = await client.get_insight("expense", insight_group, start, end)

    groups: list[dict] = []
    for item in data:
        entry = {
            "name": item.get("name", "Unknown"),
            "total": abs(float(item.get("difference_float", 0))),
            "currency": item.get("currency_code", ""),
        }
        groups.append(entry)

    groups.sort(key=lambda x: x["total"], reverse=True)

    result: dict = {
        "period": f"{start} to {end}",
        "group_by": group_by,
        "groups": groups,
        "grand_total": sum(g["total"] for g in groups),
    }

    if group_by == "budget":
        budgets_data = await client.list_budgets()
        budget_limits: dict[str, float] = {}
        for b in budgets_data.get("data", []):
            name = b["attributes"]["name"]
            auto_amount = b["attributes"].get("auto_budget_amount")
            if auto_amount:
                budget_limits[name] = float(auto_amount)

        for group in result["groups"]:
            limit = budget_limits.get(group["name"])
            if limit:
                group["limit"] = limit
                group["remaining"] = limit - group["total"]

    return result
