from __future__ import annotations

from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient


async def _fetch_tags(client: FireflyClient) -> list[dict]:
    data = await client.list_tags()
    return [{"id": int(t["id"]), "name": t["attributes"]["tag"]} for t in data.get("data", [])]


async def _fetch_categories(client: FireflyClient) -> list[dict]:
    data = await client.list_categories()
    return [{"id": int(c["id"]), "name": c["attributes"]["name"]} for c in data.get("data", [])]


async def _fetch_budgets(client: FireflyClient) -> list[dict]:
    data = await client.list_budgets()
    results = []
    for b in data.get("data", []):
        attrs = b["attributes"]
        entry = {"id": int(b["id"]), "name": attrs["name"]}
        if attrs.get("auto_budget_amount"):
            entry["auto_budget_amount"] = attrs["auto_budget_amount"]
            entry["auto_budget_period"] = attrs.get("auto_budget_period", "monthly")
        results.append(entry)
    return results


async def _fetch_accounts(client: FireflyClient) -> list[dict]:
    data = await client.list_accounts()
    return [
        {
            "id": int(a["id"]),
            "name": a["attributes"]["name"],
            "type": a["attributes"]["type"],
            "balance": a["attributes"].get("current_balance"),
            "currency": a["attributes"].get("currency_code"),
        }
        for a in data.get("data", [])
    ]


async def _fetch_bills(client: FireflyClient) -> list[dict]:
    data = await client.list_bills()
    return [
        {
            "id": int(b["id"]),
            "name": b["attributes"]["name"],
            "amount_min": b["attributes"].get("amount_min"),
            "amount_max": b["attributes"].get("amount_max"),
            "repeat_freq": b["attributes"].get("repeat_freq"),
        }
        for b in data.get("data", [])
    ]


FETCHERS = {
    "tags": _fetch_tags,
    "categories": _fetch_categories,
    "budgets": _fetch_budgets,
    "accounts": _fetch_accounts,
    "bills": _fetch_bills,
}


async def get_financial_context(
    what: Annotated[
        str,
        Field(description="What to fetch: 'accounts', 'budgets', 'categories', 'tags', 'bills', or 'all'"),
    ] = "all",
    *,
    client: FireflyClient,
) -> dict:
    """Get reference data for making categorization decisions."""
    result: dict = {}

    if what == "all":
        for key, fetcher in FETCHERS.items():
            result[key] = await fetcher(client)
    elif what in FETCHERS:
        result[what] = await FETCHERS[what](client)
    else:
        return {"error": f"Unknown type '{what}'. Available: {', '.join(FETCHERS)}, all"}

    return result


async def manage_metadata(
    action: Annotated[
        str,
        Field(description=(
            "Action: 'create_tag', 'create_category', 'create_budget', 'update_budget_limit', "
            "'update_tag', 'update_category', 'delete_tag', 'delete_category', 'delete_budget', "
            "'create_account', 'update_account', 'delete_account', "
            "'create_bill', 'update_bill', 'delete_bill'"
        )),
    ],
    name: Annotated[str, Field(description="Name of the entity")] = "",
    entity_id: Annotated[int | None, Field(description="Entity ID (for update/delete operations)")] = None,
    amount: Annotated[float | None, Field(description="Budget limit amount or bill amount")] = None,
    period: Annotated[str | None, Field(description="Budget period: 'monthly', 'weekly', 'yearly'")] = None,
    account_type: Annotated[
        str | None,
        Field(description="Account type: 'asset', 'expense', 'revenue', 'liability'"),
    ] = None,
    amount_min: Annotated[float | None, Field(description="Bill minimum amount")] = None,
    amount_max: Annotated[float | None, Field(description="Bill maximum amount")] = None,
    repeat_freq: Annotated[
        str | None,
        Field(description="Bill repeat frequency: 'weekly', 'monthly', 'quarterly', 'half-year', 'yearly'"),
    ] = None,
    currency_code: Annotated[str | None, Field(description="Currency code (e.g. 'MYR', 'USD')")] = None,
    *,
    client: FireflyClient,
) -> dict:
    """Create, update, or delete tags, categories, budgets, accounts, and bills."""
    # -- Tags --
    if action == "create_tag":
        data = await client.create_tag(name)
        return {"created": "tag", "name": name, "id": data["data"]["id"]}

    elif action == "update_tag":
        if entity_id is None:
            return {"error": "entity_id is required for update_tag"}
        data = await client.update_tag(entity_id, {"tag": name})
        return {"updated": "tag", "id": entity_id, "name": name}

    elif action == "delete_tag":
        if entity_id is None:
            return {"error": "entity_id is required for delete_tag"}
        await client.delete_tag(entity_id)
        return {"deleted": "tag", "id": entity_id}

    # -- Categories --
    elif action == "create_category":
        data = await client.create_category(name)
        return {"created": "category", "name": name, "id": data["data"]["id"]}

    elif action == "update_category":
        if entity_id is None:
            return {"error": "entity_id is required for update_category"}
        data = await client.update_category(entity_id, {"name": name})
        return {"updated": "category", "id": entity_id, "name": name}

    elif action == "delete_category":
        if entity_id is None:
            return {"error": "entity_id is required for delete_category"}
        await client.delete_category(entity_id)
        return {"deleted": "category", "id": entity_id}

    # -- Budgets --
    elif action == "create_budget":
        data = await client.create_budget(name)
        return {"created": "budget", "name": name, "id": data["data"]["id"]}

    elif action == "update_budget_limit":
        if amount is None:
            return {"error": "amount is required for update_budget_limit"}

        budgets = await client.list_budgets()
        budget_id = None
        for b in budgets.get("data", []):
            if b["attributes"]["name"].lower() == name.lower():
                budget_id = int(b["id"])
                break

        if budget_id is None:
            return {"error": f"Budget '{name}' not found"}

        from datetime import date, timedelta
        import calendar

        today = date.today()
        start = today.replace(day=1)

        effective_period = period or "monthly"
        if effective_period == "weekly":
            start = today - timedelta(days=today.weekday())
            end_date = start + timedelta(days=6)
        elif effective_period == "yearly":
            start = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        else:  # monthly
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = today.replace(day=last_day)

        data = await client.create_budget_limit(
            budget_id, amount, start.isoformat(), end_date.isoformat()
        )
        return {
            "updated": "budget_limit",
            "name": name,
            "amount": amount,
            "period": effective_period,
            "id": data["data"]["id"],
        }

    elif action == "delete_budget":
        if entity_id is None:
            return {"error": "entity_id is required for delete_budget"}
        await client.delete_budget(entity_id)
        return {"deleted": "budget", "id": entity_id}

    # -- Accounts --
    elif action == "create_account":
        if not name:
            return {"error": "name is required for create_account"}
        payload: dict = {
            "name": name,
            "type": account_type or "asset",
        }
        if currency_code:
            payload["currency_code"] = currency_code
        data = await client.create_account(payload)
        return {"created": "account", "name": name, "id": data["data"]["id"]}

    elif action == "update_account":
        if entity_id is None:
            return {"error": "entity_id is required for update_account"}
        payload = {}
        if name:
            payload["name"] = name
        if account_type:
            payload["type"] = account_type
        if currency_code:
            payload["currency_code"] = currency_code
        if not payload:
            return {"error": "No fields provided to update"}
        data = await client.update_account(entity_id, payload)
        return {"updated": "account", "id": entity_id}

    elif action == "delete_account":
        if entity_id is None:
            return {"error": "entity_id is required for delete_account"}
        await client.delete_account(entity_id)
        return {"deleted": "account", "id": entity_id}

    # -- Bills --
    elif action == "create_bill":
        if not name:
            return {"error": "name is required for create_bill"}
        if amount_min is None or amount_max is None:
            return {"error": "amount_min and amount_max are required for create_bill"}
        from datetime import date
        payload = {
            "name": name,
            "amount_min": str(amount_min),
            "amount_max": str(amount_max),
            "date": date.today().isoformat(),
            "repeat_freq": repeat_freq or "monthly",
        }
        if currency_code:
            payload["currency_code"] = currency_code
        data = await client.create_bill(payload)
        return {"created": "bill", "name": name, "id": data["data"]["id"]}

    elif action == "update_bill":
        if entity_id is None:
            return {"error": "entity_id is required for update_bill"}
        payload = {}
        if name:
            payload["name"] = name
        if amount_min is not None:
            payload["amount_min"] = str(amount_min)
        if amount_max is not None:
            payload["amount_max"] = str(amount_max)
        if repeat_freq:
            payload["repeat_freq"] = repeat_freq
        if currency_code:
            payload["currency_code"] = currency_code
        if not payload:
            return {"error": "No fields provided to update"}
        data = await client.update_bill(entity_id, payload)
        return {"updated": "bill", "id": entity_id}

    elif action == "delete_bill":
        if entity_id is None:
            return {"error": "entity_id is required for delete_bill"}
        await client.delete_bill(entity_id)
        return {"deleted": "bill", "id": entity_id}

    return {"error": f"Unknown action '{action}'"}
