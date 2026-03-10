# Firefly III MCP Server Design

## Overview

A FastMCP-based MCP server that provides workflow-oriented tools for managing personal finances through Firefly III. Two primary workflows: importing bank statements (CSV via Data Importer) and reviewing/categorizing transactions. Runs via STDIO transport from Claude Code on a Windows desktop, connecting to self-hosted Firefly III and Data Importer on Unraid.

## Architecture

```
Claude Code (STDIO) --> firefly-mcp (FastMCP, Python)
                            |---> Firefly III API (Unraid, PAT auth)
                            |---> Data Importer API (Unraid, PAT + secret)
```

### Configuration

Environment variables:
- `FIREFLY_URL` — Firefly III base URL (e.g., `http://unraid:8080`)
- `FIREFLY_TOKEN` — Personal Access Token
- `FIREFLY_IMPORTER_URL` — Data Importer base URL
- `FIREFLY_IMPORTER_SECRET` — Auto-import secret (min 16 chars)

### Server Lifespan

A shared `httpx.AsyncClient` initialized at startup with auth headers pre-configured. Cleaned up on shutdown. Accessible via `ctx.lifespan_context["firefly_client"]` and `ctx.lifespan_context["importer_client"]`.

## Tools

### 1. `import_bank_statement`

Imports a CSV bank statement into Firefly III via the Data Importer.

**Input:**
- `csv_path: str` — absolute path to the CSV file on local machine
- `bank: str = "auto"` — "hsbc", "maybank", or "auto" (detects from CSV headers)
- `dry_run: bool = False` — if true, validates the CSV against the config but doesn't import

**Behavior:**
1. Reads the CSV file from disk
2. Selects the matching JSON config (hsbc.json or maybank.json from configs/)
3. POSTs both to Data Importer's `/autoupload?secret=...` endpoint
4. Parses the import log response

**Returns:** Count of transactions created, duplicates skipped, and any errors/warnings.

### 2. `get_review_queue`

Fetches transactions that need human/LLM review — missing tags, categories, or budgets.

**Input:**
- `days_back: int = 30` — how far back to look
- `filter: str = "all_unreviewed"` — one of: "untagged", "uncategorized", "unbudgeted", "all_unreviewed"

**Behavior:**
1. Queries `GET /v1/transactions` with date range filter, type=withdrawal
2. Filters results for transactions missing the requested metadata
3. Formats into a compact representation

**Returns:** List of transactions with: id, date, amount, description, source_account, destination_name, current tags/category/budget.

### 3. `categorize_transactions`

Batch-applies categories, tags, budgets, and notes to multiple transactions.

**Input:**
- `updates: list[dict]` — each dict contains:
  - `transaction_id: int` (required)
  - `category: str | None`
  - `tags: list[str] | None`
  - `budget: str | None`
  - `notes: str | None`

**Behavior:**
1. For each update, PUTs to `/v1/transactions/{id}` with the specified fields
2. Collects results, continues on individual failures
3. Reports success/failure summary

**Returns:** Count of successful updates, list of any failures with error messages.

### 4. `search_transactions`

Flexible transaction search with natural parameters translated to Firefly's query language.

**Input:**
- `query: str | None` — free-text description search
- `date_from: str | None` — ISO date
- `date_to: str | None` — ISO date
- `amount_min: float | None`
- `amount_max: float | None`
- `account: str | None` — account name
- `category: str | None`
- `tag: str | None`
- `budget: str | None`
- `type: str = "all"` — "withdrawal", "deposit", "transfer", "all"

**Behavior:**
1. Builds Firefly search query string from provided parameters
2. Queries `GET /v1/search/transactions`
3. Formats results in the same compact format as review queue

**Returns:** Matching transactions in compact format.

### 5. `get_spending_summary`

Aggregated spending insights for a period.

**Input:**
- `period: str = "this_month"` — "this_month", "last_month", "this_year", or "YYYY-MM-DD:YYYY-MM-DD"
- `group_by: str = "category"` — "category", "tag", "budget", "account"

**Behavior:**
1. Resolves period to start/end dates
2. Queries the appropriate `/v1/insight/expense/*` endpoint
3. When grouped by budget, also fetches budget limits for comparison

**Returns:** Totals per group, sorted by amount. Budget view includes limit and remaining.

### 6. `get_financial_context`

Returns reference data the LLM needs for making categorization decisions.

**Input:**
- `what: str = "all"` — "accounts", "budgets", "categories", "tags", "bills", "all"

**Behavior:**
1. Fetches the requested entities from Firefly API
2. Returns compact summaries (not full API objects)

**Returns:** Names and relevant details (e.g., budget limits, account types, tag usage counts).

### 7. `manage_metadata`

Creates or updates tags, categories, and budgets when existing ones don't fit.

**Input:**
- `action: str` — "create_tag", "create_category", "create_budget", "update_budget_limit"
- `name: str` — name of the entity
- `amount: float | None` — for budget limit operations
- `period: str | None` — for budget limits ("monthly", "weekly", "yearly")

**Behavior:** Dispatches to the appropriate Firefly API endpoint based on action.

**Returns:** Confirmation with the created/updated entity details.

## Prompts

### 1. `review_imports`

Parameters: `days_back: int = 7`

Template guides the LLM through:
1. Call `get_financial_context("all")` to learn available categories/tags/budgets
2. Call `get_review_queue(days_back=days_back)`
3. Analyze merchant names and amounts to propose categorizations
4. Present proposed changes to the user for approval
5. Call `categorize_transactions` with approved changes

### 2. `monthly_review`

Parameters: `month: str` (e.g., "2026-03")

Template guides the LLM through:
1. Call `get_spending_summary` for the month, grouped by budget and category
2. Compare spending to budget limits, flag overages
3. Call `get_review_queue` to check for any uncategorized transactions
4. Present a summary with actionable insights

## Resources

### `firefly://config/{bank}`

Returns the Data Importer JSON configuration for a given bank (hsbc, maybank). Allows the LLM to inspect and understand the import mapping.

## Project Structure

```
firefly-tools/
  pyproject.toml
  .env.example
  src/
    firefly_mcp/
      __init__.py
      server.py              # FastMCP app, lifespan, env config
      tools/
        __init__.py
        import_tool.py       # import_bank_statement
        review.py            # get_review_queue, categorize_transactions
        search.py            # search_transactions
        insights.py          # get_spending_summary
        metadata.py          # get_financial_context, manage_metadata
      prompts.py             # review_imports, monthly_review
      resources.py           # firefly://config/{bank}
      client.py              # httpx wrapper for Firefly + Importer APIs
      configs/
        hsbc.json            # Data Importer config for HSBC
        maybank.json         # Data Importer config for Maybank
```

## Dependencies

- `fastmcp` — MCP server framework
- `httpx` — async HTTP client for Firefly/Importer APIs
- `pydantic` — input validation (comes with fastmcp)
- `python-dotenv` — .env file loading

## Out of Scope

- Individual CRUD tools per entity (anti-pattern: API wrapping)
- Rule management (better in Firefly UI)
- Attachments, piggy banks, recurring transactions
- Chart/visualization endpoints
- OAuth authentication (PAT only)
