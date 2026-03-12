from __future__ import annotations

from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient
from firefly_mcp.models import CompactRule, RuleActionInput, RuleTriggerInput

# Valid trigger and action keywords for reference / validation
TRIGGER_KEYWORDS = {
    "from_account_starts", "from_account_ends", "from_account_is", "from_account_contains",
    "to_account_starts", "to_account_ends", "to_account_is", "to_account_contains",
    "amount_less", "amount_exactly", "amount_more",
    "description_starts", "description_ends", "description_contains", "description_is",
    "transaction_type",
    "category_is", "budget_is", "tag_is", "currency_is",
    "has_attachments", "has_no_category", "has_any_category",
    "has_no_budget", "has_any_budget", "has_no_tag", "has_any_tag",
    "notes_contains", "notes_start", "notes_end", "notes_are", "no_notes", "any_notes",
}

ACTION_KEYWORDS = {
    "set_category", "clear_category", "set_budget", "clear_budget",
    "add_tag", "remove_tag", "remove_all_tags", "link_to_bill",
    "set_description", "append_description", "prepend_description",
    "set_source_account", "set_destination_account",
    "set_notes", "append_notes", "prepend_notes", "clear_notes",
    "convert_withdrawal", "convert_deposit", "convert_transfer",
    "delete_transaction",
}


async def _find_or_create_rule_group(
    client: FireflyClient, group_title: str
) -> int:
    """Find a rule group by title, or create it if it doesn't exist."""
    data = await client.list_rule_groups()
    for g in data.get("data", []):
        if g["attributes"]["title"].lower() == group_title.lower():
            return int(g["id"])
    result = await client.create_rule_group({"title": group_title})
    return int(result["data"]["id"])


async def manage_automations(
    action: Annotated[
        str,
        Field(description="Action: 'list', 'get', 'create', 'update', 'delete', 'enable', 'disable'"),
    ],
    rule_id: Annotated[int | None, Field(description="Rule ID (for get/update/delete/enable/disable)")] = None,
    title: Annotated[str | None, Field(description="Rule title (for create/update)")] = None,
    rule_group: Annotated[str | None, Field(description="Rule group name (auto-creates if needed)")] = None,
    trigger_on: Annotated[
        str | None,
        Field(description="When to fire: 'store-journal' (on create) or 'update-journal' (on edit)"),
    ] = None,
    strict: Annotated[bool | None, Field(description="True = ALL triggers must match, False = ANY")] = None,
    triggers: Annotated[
        list[RuleTriggerInput] | None,
        Field(description="List of trigger conditions"),
    ] = None,
    actions: Annotated[
        list[RuleActionInput] | None,
        Field(description="List of actions to perform when triggered"),
    ] = None,
    stop_processing: Annotated[bool | None, Field(description="Stop processing subsequent rules")] = None,
    *,
    client: FireflyClient,
) -> dict:
    """Manage automation rules: list, create, update, delete, enable/disable."""
    if action == "list":
        all_rules: list[dict] = []
        page = 1
        while True:
            data = await client.list_rules(page=page)
            for item in data.get("data", []):
                all_rules.append(CompactRule.from_api(item).model_dump())
            total_pages = data.get("meta", {}).get("pagination", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        return {"rules": all_rules, "total": len(all_rules)}

    elif action == "get":
        if rule_id is None:
            return {"error": "rule_id is required for 'get'"}
        data = await client.get_rule(rule_id)
        return CompactRule.from_api(data["data"]).model_dump()

    elif action == "create":
        if not title:
            return {"error": "title is required for 'create'"}
        if not triggers or not actions:
            return {"error": "triggers and actions are required for 'create'"}

        group_name = rule_group or "Default"
        group_id = await _find_or_create_rule_group(client, group_name)

        payload: dict = {
            "title": title,
            "rule_group_id": str(group_id),
            "trigger": trigger_on or "store-journal",
            "active": True,
            "strict": strict if strict is not None else True,
            "stop_processing": stop_processing or False,
            "triggers": [
                {
                    "type": t.type,
                    "value": t.value,
                    "active": True,
                    "prohibited": t.prohibited,
                }
                for t in triggers
            ],
            "actions": [
                {"type": a.type, "value": a.value, "active": True}
                for a in actions
            ],
        }

        data = await client.create_rule(payload)
        rule = CompactRule.from_api(data["data"])
        return {"created": "rule", **rule.model_dump()}

    elif action == "update":
        if rule_id is None:
            return {"error": "rule_id is required for 'update'"}

        payload = {}
        if title is not None:
            payload["title"] = title
        if trigger_on is not None:
            payload["trigger"] = trigger_on
        if strict is not None:
            payload["strict"] = strict
        if stop_processing is not None:
            payload["stop_processing"] = stop_processing
        if rule_group is not None:
            group_id = await _find_or_create_rule_group(client, rule_group)
            payload["rule_group_id"] = str(group_id)
        if triggers is not None:
            payload["triggers"] = [
                {"type": t.type, "value": t.value, "active": True, "prohibited": t.prohibited}
                for t in triggers
            ]
        if actions is not None:
            payload["actions"] = [
                {"type": a.type, "value": a.value, "active": True}
                for a in actions
            ]

        if not payload:
            return {"error": "No fields provided to update"}

        data = await client.update_rule(rule_id, payload)
        rule = CompactRule.from_api(data["data"])
        return {"updated": "rule", **rule.model_dump()}

    elif action == "delete":
        if rule_id is None:
            return {"error": "rule_id is required for 'delete'"}
        await client.delete_rule(rule_id)
        return {"deleted": "rule", "rule_id": rule_id}

    elif action == "enable":
        if rule_id is None:
            return {"error": "rule_id is required for 'enable'"}
        data = await client.update_rule(rule_id, {"active": True})
        return {"enabled": "rule", "rule_id": rule_id}

    elif action == "disable":
        if rule_id is None:
            return {"error": "rule_id is required for 'disable'"}
        data = await client.update_rule(rule_id, {"active": False})
        return {"disabled": "rule", "rule_id": rule_id}

    return {"error": f"Unknown action '{action}'"}


async def test_automation(
    rule_id: Annotated[int | None, Field(description="Rule ID to test/trigger")] = None,
    rule_group_id: Annotated[int | None, Field(description="Rule group ID to test/trigger")] = None,
    execute: Annotated[
        bool,
        Field(description="False = dry run (show matches), True = actually fire the rule"),
    ] = False,
    *,
    client: FireflyClient,
) -> dict:
    """Test or fire an automation rule against existing transactions."""
    if rule_id is None and rule_group_id is None:
        return {"error": "Provide either rule_id or rule_group_id"}

    if rule_id is not None:
        if execute:
            await client.trigger_rule(rule_id)
            return {"triggered": "rule", "rule_id": rule_id}
        else:
            data = await client.test_rule(rule_id)
            matched = [
                {
                    "id": int(t["id"]),
                    "description": t["attributes"]["transactions"][0]["description"],
                    "amount": float(t["attributes"]["transactions"][0]["amount"]),
                    "date": t["attributes"]["transactions"][0]["date"][:10],
                }
                for t in data.get("data", [])
            ]
            return {"rule_id": rule_id, "matched_transactions": matched, "count": len(matched)}

    if rule_group_id is not None:
        if execute:
            await client.trigger_rule_group(rule_group_id)
            return {"triggered": "rule_group", "rule_group_id": rule_group_id}
        else:
            data = await client.test_rule_group(rule_group_id)
            matched = [
                {
                    "id": int(t["id"]),
                    "description": t["attributes"]["transactions"][0]["description"],
                    "amount": float(t["attributes"]["transactions"][0]["amount"]),
                    "date": t["attributes"]["transactions"][0]["date"][:10],
                }
                for t in data.get("data", [])
            ]
            return {"rule_group_id": rule_group_id, "matched_transactions": matched, "count": len(matched)}

    return {"error": "Unreachable"}


async def get_automation_context(*, client: FireflyClient) -> dict:
    """Get available trigger keywords, action keywords, and existing rule groups."""
    data = await client.list_rule_groups()
    groups = [
        {"id": int(g["id"]), "title": g["attributes"]["title"]}
        for g in data.get("data", [])
    ]

    return {
        "trigger_keywords": sorted(TRIGGER_KEYWORDS),
        "action_keywords": sorted(ACTION_KEYWORDS),
        "trigger_types": ["store-journal", "update-journal"],
        "rule_groups": groups,
    }
