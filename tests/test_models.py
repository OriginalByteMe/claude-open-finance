import pytest
from firefly_mcp.models import (
    TransactionUpdate, CompactTransaction, CompactRule,
    RuleTriggerInput, RuleActionInput,
)
from tests.conftest import SAMPLE_TRANSACTION


def test_transaction_update_valid():
    update = TransactionUpdate(
        transaction_id=1,
        category="Dining",
        tags=["restaurant", "grab"],
        budget="Eating Out",
        notes="Grab Food order",
    )
    assert update.transaction_id == 1
    assert update.tags == ["restaurant", "grab"]


def test_transaction_update_minimal():
    update = TransactionUpdate(transaction_id=42)
    assert update.category is None
    assert update.tags is None


def test_compact_transaction():
    txn = CompactTransaction(
        id=1,
        date="2026-03-01",
        amount=-25.50,
        description="GRAB FOOD",
        source_account="HSBC Checking",
        destination="Grab Food",
        category=None,
        budget=None,
        tags=[],
        notes=None,
    )
    assert txn.id == 1
    assert txn.amount == -25.50


def test_compact_transaction_from_api():
    txn = CompactTransaction.from_api(SAMPLE_TRANSACTION)
    assert txn.id == 1
    assert txn.description == "GRAB FOOD"
    assert txn.amount == 25.50
    assert txn.category is None
    assert txn.tags == []


def test_rule_trigger_input():
    t = RuleTriggerInput(type="description_contains", value="STARBUCKS")
    assert t.type == "description_contains"
    assert t.prohibited is False


def test_rule_trigger_input_prohibited():
    t = RuleTriggerInput(type="description_contains", value="REFUND", prohibited=True)
    assert t.prohibited is True


def test_rule_action_input():
    a = RuleActionInput(type="set_category", value="Dining")
    assert a.type == "set_category"
    assert a.value == "Dining"


def test_compact_rule_from_api():
    data = {
        "id": "7",
        "attributes": {
            "title": "Test Rule",
            "active": True,
            "trigger": "store-journal",
            "strict": True,
            "rule_group_title": "My Group",
            "triggers": [
                {"type": "description_contains", "value": "TEST", "active": True, "prohibited": False},
                {"type": "amount_more", "value": "10", "active": False, "prohibited": False},
            ],
            "actions": [
                {"type": "set_category", "value": "Testing", "active": True},
                {"type": "add_tag", "value": "test", "active": True},
            ],
        },
    }
    rule = CompactRule.from_api(data)
    assert rule.id == 7
    assert rule.title == "Test Rule"
    assert rule.group == "My Group"
    assert rule.strict is True
    assert rule.trigger_on == "store-journal"
    # Inactive trigger should be filtered out
    assert len(rule.triggers) == 1
    assert rule.triggers[0]["type"] == "description_contains"
    assert len(rule.actions) == 2
