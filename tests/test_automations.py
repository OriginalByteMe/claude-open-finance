import pytest
from unittest.mock import AsyncMock

from firefly_mcp.models import RuleTriggerInput, RuleActionInput
from firefly_mcp.tools.automations import (
    manage_automations,
    test_automation,
    get_automation_context,
)


SAMPLE_RULE = {
    "id": "1",
    "attributes": {
        "title": "Starbucks → Coffee",
        "active": True,
        "trigger": "store-journal",
        "strict": True,
        "rule_group_title": "Auto-categorize",
        "triggers": [
            {"type": "description_contains", "value": "STARBUCKS", "active": True, "prohibited": False},
        ],
        "actions": [
            {"type": "set_category", "value": "Food & Dining", "active": True},
            {"type": "add_tag", "value": "coffee", "active": True},
        ],
    },
}

SAMPLE_RULE_GROUP = {
    "id": "1",
    "attributes": {"title": "Auto-categorize"},
}


@pytest.mark.asyncio
async def test_manage_automations_list():
    mock_client = AsyncMock()
    mock_client.list_rules.return_value = {
        "data": [SAMPLE_RULE],
        "meta": {"pagination": {"total_pages": 1}},
    }

    result = await manage_automations(action="list", client=mock_client)
    assert result["total"] == 1
    assert result["rules"][0]["title"] == "Starbucks → Coffee"
    assert result["rules"][0]["triggers"][0]["type"] == "description_contains"


@pytest.mark.asyncio
async def test_manage_automations_get():
    mock_client = AsyncMock()
    mock_client.get_rule.return_value = {"data": SAMPLE_RULE}

    result = await manage_automations(action="get", rule_id=1, client=mock_client)
    assert result["title"] == "Starbucks → Coffee"
    assert result["id"] == 1


@pytest.mark.asyncio
async def test_manage_automations_get_requires_id():
    mock_client = AsyncMock()
    result = await manage_automations(action="get", client=mock_client)
    assert "error" in result


@pytest.mark.asyncio
async def test_manage_automations_create():
    mock_client = AsyncMock()
    mock_client.list_rule_groups.return_value = {
        "data": [SAMPLE_RULE_GROUP],
    }
    mock_client.create_rule.return_value = {"data": SAMPLE_RULE}

    triggers = [RuleTriggerInput(type="description_contains", value="STARBUCKS")]
    actions = [
        RuleActionInput(type="set_category", value="Food & Dining"),
        RuleActionInput(type="add_tag", value="coffee"),
    ]

    result = await manage_automations(
        action="create",
        title="Starbucks → Coffee",
        rule_group="Auto-categorize",
        triggers=triggers,
        actions=actions,
        client=mock_client,
    )
    assert result["created"] == "rule"
    assert result["title"] == "Starbucks → Coffee"
    mock_client.create_rule.assert_called_once()

    call_payload = mock_client.create_rule.call_args[0][0]
    assert call_payload["title"] == "Starbucks → Coffee"
    assert call_payload["trigger"] == "store-journal"
    assert call_payload["strict"] is True
    assert len(call_payload["triggers"]) == 1
    assert len(call_payload["actions"]) == 2


@pytest.mark.asyncio
async def test_manage_automations_create_new_group():
    mock_client = AsyncMock()
    mock_client.list_rule_groups.return_value = {"data": []}
    mock_client.create_rule_group.return_value = {"data": {"id": "5"}}
    mock_client.create_rule.return_value = {"data": SAMPLE_RULE}

    triggers = [RuleTriggerInput(type="description_contains", value="GRAB")]
    actions = [RuleActionInput(type="set_category", value="Transport")]

    result = await manage_automations(
        action="create",
        title="Grab → Transport",
        rule_group="New Group",
        triggers=triggers,
        actions=actions,
        client=mock_client,
    )
    assert result["created"] == "rule"
    mock_client.create_rule_group.assert_called_once_with({"title": "New Group"})


@pytest.mark.asyncio
async def test_manage_automations_create_requires_fields():
    mock_client = AsyncMock()

    result = await manage_automations(action="create", client=mock_client)
    assert "error" in result

    result = await manage_automations(
        action="create", title="Test", client=mock_client
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_manage_automations_update():
    mock_client = AsyncMock()
    mock_client.update_rule.return_value = {"data": SAMPLE_RULE}

    result = await manage_automations(
        action="update", rule_id=1, title="Updated Rule", client=mock_client
    )
    assert result["updated"] == "rule"
    mock_client.update_rule.assert_called_once_with(1, {"title": "Updated Rule"})


@pytest.mark.asyncio
async def test_manage_automations_delete():
    mock_client = AsyncMock()
    result = await manage_automations(action="delete", rule_id=1, client=mock_client)
    assert result["deleted"] == "rule"
    assert result["rule_id"] == 1
    mock_client.delete_rule.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_manage_automations_enable():
    mock_client = AsyncMock()
    mock_client.update_rule.return_value = {"data": SAMPLE_RULE}
    result = await manage_automations(action="enable", rule_id=1, client=mock_client)
    assert result["enabled"] == "rule"
    mock_client.update_rule.assert_called_once_with(1, {"active": True})


@pytest.mark.asyncio
async def test_manage_automations_disable():
    mock_client = AsyncMock()
    mock_client.update_rule.return_value = {"data": SAMPLE_RULE}
    result = await manage_automations(action="disable", rule_id=1, client=mock_client)
    assert result["disabled"] == "rule"
    mock_client.update_rule.assert_called_once_with(1, {"active": False})


@pytest.mark.asyncio
async def test_manage_automations_unknown_action():
    mock_client = AsyncMock()
    result = await manage_automations(action="explode", client=mock_client)
    assert "error" in result


@pytest.mark.asyncio
async def test_test_automation_dry_run():
    mock_client = AsyncMock()
    mock_client.test_rule.return_value = {
        "data": [
            {
                "id": "10",
                "attributes": {
                    "transactions": [
                        {
                            "description": "STARBUCKS KLCC",
                            "amount": "12.50",
                            "date": "2026-03-01T00:00:00+00:00",
                        }
                    ]
                },
            }
        ]
    }

    result = await test_automation(rule_id=1, execute=False, client=mock_client)
    assert result["rule_id"] == 1
    assert result["count"] == 1
    assert result["matched_transactions"][0]["description"] == "STARBUCKS KLCC"
    mock_client.test_rule.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_test_automation_execute():
    mock_client = AsyncMock()
    result = await test_automation(rule_id=1, execute=True, client=mock_client)
    assert result["triggered"] == "rule"
    mock_client.trigger_rule.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_test_automation_group_dry_run():
    mock_client = AsyncMock()
    mock_client.test_rule_group.return_value = {"data": []}

    result = await test_automation(rule_group_id=2, execute=False, client=mock_client)
    assert result["rule_group_id"] == 2
    assert result["count"] == 0
    mock_client.test_rule_group.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_test_automation_group_execute():
    mock_client = AsyncMock()
    result = await test_automation(rule_group_id=2, execute=True, client=mock_client)
    assert result["triggered"] == "rule_group"
    mock_client.trigger_rule_group.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_test_automation_requires_id():
    mock_client = AsyncMock()
    result = await test_automation(client=mock_client)
    assert "error" in result


@pytest.mark.asyncio
async def test_get_automation_context():
    mock_client = AsyncMock()
    mock_client.list_rule_groups.return_value = {
        "data": [SAMPLE_RULE_GROUP],
    }

    result = await get_automation_context(client=mock_client)
    assert "trigger_keywords" in result
    assert "action_keywords" in result
    assert "trigger_types" in result
    assert "rule_groups" in result
    assert "known_quirks" in result
    assert "description_contains" in result["trigger_keywords"]
    assert "set_category" in result["action_keywords"]
    assert result["rule_groups"][0]["title"] == "Auto-categorize"
    # Verify convert_transfer quirk is documented
    quirk_actions = [q["action"] for q in result["known_quirks"]]
    assert "convert_transfer" in quirk_actions
