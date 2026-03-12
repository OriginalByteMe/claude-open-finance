from __future__ import annotations

import calendar
import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.server.lifespan import lifespan
from fastmcp.dependencies import CurrentContext

from firefly_mcp.client import FireflyClient
from firefly_mcp.models import TransactionUpdate, RuleTriggerInput, RuleActionInput
from firefly_mcp.tools.import_tool import import_bank_statement as _import_bank_statement
from firefly_mcp.tools.review import get_review_queue as _get_review_queue
from firefly_mcp.tools.review import categorize_transactions as _categorize_transactions
from firefly_mcp.tools.search import search_transactions as _search_transactions
from firefly_mcp.tools.insights import get_spending_summary as _get_spending_summary
from firefly_mcp.tools.metadata import get_financial_context as _get_financial_context
from firefly_mcp.tools.metadata import manage_metadata as _manage_metadata
from firefly_mcp.tools.automations import manage_automations as _manage_automations
from firefly_mcp.tools.automations import test_automation as _test_automation
from firefly_mcp.tools.automations import get_automation_context as _get_automation_context
from firefly_mcp.prompts import REVIEW_IMPORTS_TEMPLATE, MONTHLY_REVIEW_TEMPLATE, SETUP_AUTOMATION_TEMPLATE
from firefly_mcp.resources import get_bank_config

load_dotenv()


@lifespan
async def app_lifespan(server):
    client = FireflyClient(
        firefly_url=os.environ["FIREFLY_URL"],
        token=os.environ["FIREFLY_TOKEN"],
        importer_url=os.environ["FIREFLY_IMPORTER_URL"],
        importer_secret=os.environ["FIREFLY_IMPORTER_SECRET"],
    )
    try:
        yield {"client": client}
    finally:
        await client.close()


mcp = FastMCP(
    name="firefly",
    instructions=(
        "Firefly III MCP server for personal finance management. "
        "Use get_financial_context to learn available categories, tags, and budgets "
        "before categorizing transactions. Use get_review_queue after imports to "
        "find transactions needing review. Use manage_metadata to create, update, or "
        "delete categories, tags, budgets, accounts, and bills. Use manage_automations "
        "to create and manage automation rules that automatically categorize transactions. "
        "Always test automations with test_automation before firing them."
    ),
    lifespan=app_lifespan,
)


# -- Tools --


@mcp.tool
async def import_bank_statement(
    csv_path: str,
    bank: str = "auto",
    dry_run: bool = False,
    ctx: Context = CurrentContext(),
) -> str:
    """Import a CSV bank statement into Firefly III via the Data Importer.

    Reads the CSV file, pairs it with the appropriate bank configuration,
    and uploads both to the Data Importer. Returns a summary of the import results.
    """
    client = ctx.lifespan_context["client"]
    return await _import_bank_statement(csv_path, bank, dry_run, client=client)


@mcp.tool
async def get_review_queue(
    days_back: int = 30,
    filter: str = "all_unreviewed",
    ctx: Context = CurrentContext(),
) -> list[dict]:
    """Fetch transactions needing review — missing tags, categories, or budgets.

    Returns transactions within the date range that are missing tags, categories,
    or budgets. Use after importing to find transactions needing categorization.
    Filter options: 'untagged', 'uncategorized', 'unbudgeted', 'all_unreviewed'.
    """
    client = ctx.lifespan_context["client"]
    txns = await _get_review_queue(days_back, filter, client=client)
    return [t.model_dump() for t in txns]


@mcp.tool
async def categorize_transactions(
    updates: list[TransactionUpdate],
    ctx: Context = CurrentContext(),
) -> dict:
    """Batch-apply categories, tags, budgets, and notes to transactions.

    Each update needs a transaction_id and any combination of: category, tags
    (list of strings), budget, notes. Only provided fields are changed.
    """
    client = ctx.lifespan_context["client"]
    return await _categorize_transactions(updates, client=client)


@mcp.tool
async def search_transactions(
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    account: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    budget: str | None = None,
    type: str = "all",
    ctx: Context = CurrentContext(),
) -> list[dict]:
    """Search transactions with natural parameters.

    Combine any filters: query (description text), date range, amount range,
    account, category, tag, budget, type (withdrawal/deposit/transfer/all).
    """
    client = ctx.lifespan_context["client"]
    txns = await _search_transactions(
        query=query, date_from=date_from, date_to=date_to,
        amount_min=amount_min, amount_max=amount_max, account=account,
        category=category, tag=tag, budget=budget, type=type,
        client=client,
    )
    return [t.model_dump() for t in txns]


@mcp.tool
async def get_spending_summary(
    period: str = "this_month",
    group_by: str = "category",
    ctx: Context = CurrentContext(),
) -> dict:
    """Get aggregated spending summary grouped by category/tag/budget/account.

    Periods: 'this_month', 'last_month', 'this_year', or 'YYYY-MM-DD:YYYY-MM-DD'.
    Budget view includes limits and remaining amounts.
    """
    client = ctx.lifespan_context["client"]
    return await _get_spending_summary(period, group_by, client=client)


@mcp.tool
async def get_financial_context(
    what: str = "all",
    ctx: Context = CurrentContext(),
) -> dict:
    """Get reference data: available categories, tags, budgets, accounts, bills.

    Call with 'all' before reviewing transactions to know what categories,
    tags, and budgets are available. This helps make accurate categorization decisions.
    """
    client = ctx.lifespan_context["client"]
    return await _get_financial_context(what, client=client)


@mcp.tool
async def manage_metadata(
    action: str,
    name: str = "",
    entity_id: int | None = None,
    amount: float | None = None,
    period: str | None = None,
    account_type: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    repeat_freq: str | None = None,
    currency_code: str | None = None,
    ctx: Context = CurrentContext(),
) -> dict:
    """Create, update, or delete tags, categories, budgets, accounts, and bills.

    Actions: 'create_tag', 'update_tag', 'delete_tag', 'create_category',
    'update_category', 'delete_category', 'create_budget', 'update_budget_limit',
    'delete_budget', 'create_account', 'update_account', 'delete_account',
    'create_bill', 'update_bill', 'delete_bill'.
    For update/delete, provide entity_id. Use get_financial_context to find IDs.
    """
    client = ctx.lifespan_context["client"]
    return await _manage_metadata(
        action, name, entity_id=entity_id, amount=amount, period=period,
        account_type=account_type, amount_min=amount_min, amount_max=amount_max,
        repeat_freq=repeat_freq, currency_code=currency_code, client=client,
    )


@mcp.tool
async def manage_automations(
    action: str,
    rule_id: int | None = None,
    title: str | None = None,
    rule_group: str | None = None,
    trigger_on: str | None = None,
    strict: bool | None = None,
    triggers: list[RuleTriggerInput] | None = None,
    actions: list[RuleActionInput] | None = None,
    stop_processing: bool | None = None,
    ctx: Context = CurrentContext(),
) -> dict:
    """Manage automation rules that fire on transaction create/update.

    Actions: 'list', 'get', 'create', 'update', 'delete', 'enable', 'disable'.
    For create: provide title, triggers (conditions), and actions (effects).
    Triggers match on description, amount, accounts, etc. Actions set category,
    tags, budget, etc. Use get_automation_context for available keywords.
    """
    client = ctx.lifespan_context["client"]
    return await _manage_automations(
        action, rule_id=rule_id, title=title, rule_group=rule_group,
        trigger_on=trigger_on, strict=strict, triggers=triggers,
        actions=actions, stop_processing=stop_processing, client=client,
    )


@mcp.tool
async def test_automation(
    rule_id: int | None = None,
    rule_group_id: int | None = None,
    execute: bool = False,
    ctx: Context = CurrentContext(),
) -> dict:
    """Test or fire an automation rule against existing transactions.

    With execute=False (default): dry-run showing which transactions would match.
    With execute=True: actually fire the rule, applying its actions.
    Provide either rule_id or rule_group_id.
    """
    client = ctx.lifespan_context["client"]
    return await _test_automation(
        rule_id=rule_id, rule_group_id=rule_group_id, execute=execute, client=client,
    )


@mcp.tool
async def get_automation_context(
    ctx: Context = CurrentContext(),
) -> dict:
    """Get available trigger keywords, action keywords, and existing rule groups.

    Call this before creating automations to know what trigger conditions
    (e.g., description_contains, amount_more) and actions (e.g., set_category,
    add_tag) are available.
    """
    client = ctx.lifespan_context["client"]
    return await _get_automation_context(client=client)


# -- Prompts --


@mcp.prompt
def review_imports(days_back: int = 7) -> str:
    """Guide the LLM through reviewing and categorizing recently imported transactions."""
    return REVIEW_IMPORTS_TEMPLATE.format(days_back=days_back)


@mcp.prompt
def monthly_review(month: str = "") -> str:
    """Guide the LLM through a monthly spending review with budget comparisons."""
    if not month:
        from datetime import date
        today = date.today()
        month = today.strftime("%Y-%m")

    start = f"{month}-01"
    year, mon = int(month[:4]), int(month[5:7])
    last_day = calendar.monthrange(year, mon)[1]
    end = f"{month}-{last_day}"

    return MONTHLY_REVIEW_TEMPLATE.format(month=month, start=start, end=end)


@mcp.prompt
def setup_automation() -> str:
    """Guide the LLM through creating an automation rule in Firefly III."""
    return SETUP_AUTOMATION_TEMPLATE


# -- Resources --


@mcp.resource("firefly://config/{bank}")
def bank_config(bank: str) -> str:
    """Data Importer JSON configuration for a bank (hsbc, maybank)."""
    return get_bank_config(bank)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
