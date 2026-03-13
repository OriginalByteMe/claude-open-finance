from __future__ import annotations

from pydantic import BaseModel


class TransactionUpdate(BaseModel):
    """Input model for categorize_transactions tool."""

    transaction_id: int
    category: str | None = None
    tags: list[str] | None = None
    budget: str | None = None
    notes: str | None = None


class BulkTransactionUpdate(BaseModel):
    """Input model for update_transactions tool — supports all transaction fields."""

    transaction_id: int
    type: str | None = None  # "withdrawal", "deposit", "transfer"
    source_id: int | None = None
    destination_id: int | None = None
    destination_name: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    budget: str | None = None
    notes: str | None = None
    description: str | None = None
    amount: str | None = None


class RuleTriggerInput(BaseModel):
    """Input model for a rule trigger condition."""

    type: str
    value: str = ""
    prohibited: bool = False


class RuleActionInput(BaseModel):
    """Input model for a rule action."""

    type: str
    value: str = ""


class CompactRule(BaseModel):
    """Compact representation of a rule for LLM consumption."""

    id: int
    title: str
    active: bool
    trigger_on: str
    strict: bool
    group: str
    triggers: list[dict]
    actions: list[dict]

    @classmethod
    def from_api(cls, data: dict) -> CompactRule:
        """Parse a Firefly API rule response into compact form."""
        attrs = data["attributes"]
        triggers = [
            {
                "type": t["type"],
                "value": t.get("value", ""),
                "prohibited": t.get("prohibited", False),
            }
            for t in attrs.get("triggers", [])
            if t.get("active", True)
        ]
        actions = [
            {"type": a["type"], "value": a.get("value", "")}
            for a in attrs.get("actions", [])
            if a.get("active", True)
        ]
        return cls(
            id=int(data["id"]),
            title=attrs["title"],
            active=attrs.get("active", True),
            trigger_on=attrs.get("trigger", "store-journal"),
            strict=attrs.get("strict", True),
            group=attrs.get("rule_group_title", ""),
            triggers=triggers,
            actions=actions,
        )


class CompactTransaction(BaseModel):
    """Compact representation of a transaction for LLM consumption."""

    id: int
    date: str
    amount: float
    description: str
    source_account: str
    destination: str
    category: str | None = None
    budget: str | None = None
    tags: list[str] = []
    notes: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> CompactTransaction:
        """Parse a Firefly API transaction response into compact form."""
        attrs = data["attributes"]["transactions"][0]
        return cls(
            id=int(data["id"]),
            date=attrs["date"][:10],
            amount=float(attrs["amount"]),
            description=attrs["description"],
            source_account=attrs.get("source_name", ""),
            destination=attrs.get("destination_name", ""),
            category=attrs.get("category_name"),
            budget=attrs.get("budget_name"),
            tags=attrs.get("tags", []),
            notes=attrs.get("notes"),
        )
