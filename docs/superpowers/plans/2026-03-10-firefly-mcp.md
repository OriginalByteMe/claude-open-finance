# Firefly III MCP Server Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a workflow-oriented FastMCP server that imports CSV bank statements into Firefly III and provides batch + conversational transaction review/categorization.

**Architecture:** FastMCP server running via STDIO. Two async HTTP clients (Firefly API + Data Importer) managed via lifespan. Tools organized by workflow: import, review, search, insights, metadata. Prompts guide multi-step workflows.

**Tech Stack:** Python 3.12+, FastMCP, httpx, pydantic, python-dotenv

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Package config, dependencies, entry point |
| `.env.example` | Template for required env vars |
| `src/firefly_mcp/__init__.py` | Package init, version |
| `src/firefly_mcp/server.py` | FastMCP app creation, lifespan, tool registration |
| `src/firefly_mcp/client.py` | `FireflyClient` class — all HTTP calls to Firefly III and Data Importer |
| `src/firefly_mcp/models.py` | Pydantic models for tool inputs/outputs and API response parsing |
| `src/firefly_mcp/tools/__init__.py` | Tool module init |
| `src/firefly_mcp/tools/import_tool.py` | `import_bank_statement` tool |
| `src/firefly_mcp/tools/review.py` | `get_review_queue` + `categorize_transactions` tools |
| `src/firefly_mcp/tools/search.py` | `search_transactions` tool |
| `src/firefly_mcp/tools/insights.py` | `get_spending_summary` tool |
| `src/firefly_mcp/tools/metadata.py` | `get_financial_context` + `manage_metadata` tools |
| `src/firefly_mcp/prompts.py` | `review_imports` + `monthly_review` prompt templates |
| `src/firefly_mcp/resources.py` | `firefly://config/{bank}` resource |
| `src/firefly_mcp/configs/hsbc.json` | Data Importer config for HSBC |
| `src/firefly_mcp/configs/maybank.json` | Data Importer config for Maybank |
| `tests/conftest.py` | Shared fixtures: mock clients, sample data |
| `tests/test_client.py` | Tests for FireflyClient |
| `tests/test_models.py` | Tests for Pydantic models |
| `tests/test_import_tool.py` | Tests for import_bank_statement |
| `tests/test_review.py` | Tests for review queue + categorize |
| `tests/test_search.py` | Tests for search_transactions |
| `tests/test_insights.py` | Tests for get_spending_summary |
| `tests/test_metadata.py` | Tests for get_financial_context + manage_metadata |
| `tests/test_prompts.py` | Tests for prompt templates and date logic |
| `tests/test_resources.py` | Tests for bank config resources |
| `tests/test_server.py` | Integration test: server starts, tools/prompts/resources registered |

---

## Chunk 1: Project Scaffolding + Client Foundation

### Task 1: Initialize project with pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/firefly_mcp/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "firefly-mcp"
version = "0.1.0"
description = "Workflow-oriented MCP server for Firefly III personal finance management"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.22.0",
]

[project.scripts]
firefly-mcp = "firefly_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create .env.example**

```bash
FIREFLY_URL=http://your-unraid-ip:8080
FIREFLY_TOKEN=your-personal-access-token
FIREFLY_IMPORTER_URL=http://your-unraid-ip:8081
FIREFLY_IMPORTER_SECRET=your-auto-import-secret-min-16-chars
```

- [ ] **Step 3: Create package init**

```python
# src/firefly_mcp/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 4: Create tools/__init__.py**

Empty file: `src/firefly_mcp/tools/__init__.py`

- [ ] **Step 5: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.egg-info/
dist/
build/
.pytest_cache/
.venv/
```

- [ ] **Step 6: Install the project in dev mode**

Run: `pip install -e ".[dev]"`
Expected: Installs successfully with all dependencies.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/firefly_mcp/__init__.py src/firefly_mcp/tools/__init__.py
git commit -m "chore: scaffold project with pyproject.toml and package structure"
```

---

### Task 2: Build the Firefly API client

**Files:**
- Create: `src/firefly_mcp/client.py`
- Create: `tests/conftest.py`
- Create: `tests/test_client.py`

This is the HTTP layer that all tools depend on. It wraps httpx and provides typed methods for each Firefly API interaction we need.

- [ ] **Step 1: Write failing test for client initialization**

```python
# tests/test_client.py
import pytest
from firefly_mcp.client import FireflyClient


def test_client_init():
    client = FireflyClient(
        firefly_url="http://localhost:8080",
        token="test-token",
        importer_url="http://localhost:8081",
        importer_secret="test-secret-16chars",
    )
    assert client.firefly_url == "http://localhost:8080"
    assert client.importer_url == "http://localhost:8081"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_client.py::test_client_init -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'firefly_mcp.client'`

- [ ] **Step 3: Write the FireflyClient class with init and context manager**

```python
# src/firefly_mcp/client.py
from __future__ import annotations

import httpx


class FireflyClient:
    """HTTP client for Firefly III and Data Importer APIs."""

    def __init__(
        self,
        firefly_url: str,
        token: str,
        importer_url: str,
        importer_secret: str,
    ) -> None:
        self.firefly_url = firefly_url.rstrip("/")
        self.importer_url = importer_url.rstrip("/")
        self.importer_secret = importer_secret

        self._firefly = httpx.AsyncClient(
            base_url=f"{self.firefly_url}/api/v1",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._importer = httpx.AsyncClient(
            base_url=self.importer_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=120.0,
        )

    async def close(self) -> None:
        await self._firefly.aclose()
        await self._importer.aclose()

    # -- Transactions --

    async def list_transactions(
        self,
        start: str | None = None,
        end: str | None = None,
        type: str = "withdrawal",
        page: int = 1,
    ) -> dict:
        params: dict = {"type": type, "page": page}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self._firefly.get("/transactions", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_transaction(self, transaction_id: int) -> dict:
        resp = await self._firefly.get(f"/transactions/{transaction_id}")
        resp.raise_for_status()
        return resp.json()

    async def update_transaction(self, transaction_id: int, payload: dict) -> dict:
        resp = await self._firefly.put(
            f"/transactions/{transaction_id}", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    async def search_transactions(self, query: str, page: int = 1) -> dict:
        resp = await self._firefly.get(
            "/search/transactions", params={"query": query, "page": page}
        )
        resp.raise_for_status()
        return resp.json()

    # -- Accounts --

    async def list_accounts(self, account_type: str = "asset") -> dict:
        resp = await self._firefly.get(
            "/accounts", params={"type": account_type}
        )
        resp.raise_for_status()
        return resp.json()

    # -- Tags --

    async def list_tags(self) -> dict:
        resp = await self._firefly.get("/tags")
        resp.raise_for_status()
        return resp.json()

    async def create_tag(self, name: str) -> dict:
        resp = await self._firefly.post("/tags", json={"tag": name})
        resp.raise_for_status()
        return resp.json()

    # -- Categories --

    async def list_categories(self) -> dict:
        resp = await self._firefly.get("/categories")
        resp.raise_for_status()
        return resp.json()

    async def create_category(self, name: str) -> dict:
        resp = await self._firefly.post("/categories", json={"name": name})
        resp.raise_for_status()
        return resp.json()

    # -- Budgets --

    async def list_budgets(self) -> dict:
        resp = await self._firefly.get("/budgets")
        resp.raise_for_status()
        return resp.json()

    async def create_budget(self, name: str) -> dict:
        resp = await self._firefly.post("/budgets", json={"name": name})
        resp.raise_for_status()
        return resp.json()

    async def create_budget_limit(
        self, budget_id: int, amount: float, start: str, end: str, currency_code: str = "MYR"
    ) -> dict:
        resp = await self._firefly.post(
            f"/budgets/{budget_id}/limits",
            json={
                "amount": str(amount),
                "start": start,
                "end": end,
                "currency_code": currency_code,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # -- Bills --

    async def list_bills(self) -> dict:
        resp = await self._firefly.get("/bills")
        resp.raise_for_status()
        return resp.json()

    # -- Insights --

    async def get_insight(
        self, insight_type: str, group: str, start: str, end: str
    ) -> list:
        resp = await self._firefly.get(
            f"/insight/{insight_type}/{group}",
            params={"start": start, "end": end},
        )
        resp.raise_for_status()
        return resp.json()

    # -- Summary --

    async def get_summary(self, start: str, end: str) -> dict:
        resp = await self._firefly.get(
            "/summary/basic", params={"start": start, "end": end}
        )
        resp.raise_for_status()
        return resp.json()

    # -- Data Importer --

    async def upload_csv(self, csv_bytes: bytes, config_json: str) -> str:
        resp = await self._importer.post(
            "/autoupload",
            params={"secret": self.importer_secret},
            files={
                "importable": ("import.csv", csv_bytes, "text/csv"),
                "json": ("config.json", config_json.encode(), "application/json"),
            },
            headers={"Content-Type": None},  # let httpx set multipart boundary
        )
        resp.raise_for_status()
        return resp.text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_client.py::test_client_init -v`
Expected: PASS

- [ ] **Step 5: Write tests for API methods using respx**

```python
# tests/conftest.py
import pytest
from firefly_mcp.client import FireflyClient


@pytest.fixture
def client():
    return FireflyClient(
        firefly_url="http://firefly.test",
        token="test-token",
        importer_url="http://importer.test",
        importer_secret="test-secret-16chars",
    )


SAMPLE_TRANSACTION = {
    "id": "1",
    "attributes": {
        "transactions": [
            {
                "transaction_journal_id": "1",
                "type": "withdrawal",
                "date": "2026-03-01T00:00:00+00:00",
                "amount": "25.50",
                "description": "GRAB FOOD",
                "source_name": "HSBC Checking",
                "destination_name": "Grab Food",
                "category_name": None,
                "budget_name": None,
                "tags": [],
                "notes": None,
            }
        ]
    },
}
```

```python
# tests/test_client.py (append to existing)
import respx
import httpx


@respx.mock
@pytest.mark.asyncio
async def test_list_transactions(client):
    respx.get("http://firefly.test/api/v1/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [SAMPLE_TRANSACTION],
                "meta": {"pagination": {"total": 1, "count": 1, "total_pages": 1}},
            },
        )
    )
    result = await client.list_transactions(start="2026-03-01", end="2026-03-31")
    assert len(result["data"]) == 1


@respx.mock
@pytest.mark.asyncio
async def test_search_transactions(client):
    respx.get("http://firefly.test/api/v1/search/transactions").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    result = await client.search_transactions("amount_more:100")
    assert result["data"] == []


@respx.mock
@pytest.mark.asyncio
async def test_upload_csv(client):
    respx.post("http://importer.test/autoupload").mock(
        return_value=httpx.Response(200, text="Import complete. 5 transactions imported.")
    )
    result = await client.upload_csv(b"date,amount\n2026-03-01,25.50", '{"version": 3}')
    assert "5 transactions" in result
```

- [ ] **Step 6: Run all client tests**

Run: `pytest tests/test_client.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/firefly_mcp/client.py tests/conftest.py tests/test_client.py
git commit -m "feat: add FireflyClient with typed methods for Firefly III and Data Importer APIs"
```

---

### Task 3: Define Pydantic models

**Files:**
- Create: `src/firefly_mcp/models.py`
- Create: `tests/test_models.py`

Models for tool inputs (what the LLM sends) and compact transaction representations (what tools return).

- [ ] **Step 1: Write failing test for TransactionUpdate model**

```python
# tests/test_models.py
import pytest
from firefly_mcp.models import TransactionUpdate, CompactTransaction


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the models**

```python
# src/firefly_mcp/models.py
from __future__ import annotations

from pydantic import BaseModel


class TransactionUpdate(BaseModel):
    """Input model for categorize_transactions tool."""

    transaction_id: int
    category: str | None = None
    tags: list[str] | None = None
    budget: str | None = None
    notes: str | None = None


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
```

- [ ] **Step 4: Write test for from_api parsing**

```python
# tests/test_models.py (append)
from tests.conftest import SAMPLE_TRANSACTION


def test_compact_transaction_from_api():
    txn = CompactTransaction.from_api(SAMPLE_TRANSACTION)
    assert txn.id == 1
    assert txn.description == "GRAB FOOD"
    assert txn.amount == 25.50
    assert txn.category is None
    assert txn.tags == []
```

- [ ] **Step 5: Run all model tests**

Run: `pytest tests/test_models.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/firefly_mcp/models.py tests/test_models.py
git commit -m "feat: add Pydantic models for transaction updates and compact representations"
```

---

### Task 4: Create the FastMCP server with lifespan

**Files:**
- Create: `src/firefly_mcp/server.py`
- Create: `tests/test_server.py`

The server entry point: creates the FastMCP app, initializes clients via lifespan, and will register all tools.

- [ ] **Step 1: Write failing test for server creation**

```python
# tests/test_server.py
import pytest


def test_server_exists():
    from firefly_mcp.server import mcp
    assert mcp.name == "firefly"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py::test_server_exists -v`
Expected: FAIL

- [ ] **Step 3: Write the server module**

```python
# src/firefly_mcp/server.py
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from firefly_mcp.client import FireflyClient

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
        "find transactions needing review."
    ),
    lifespan=app_lifespan,
)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server.py::test_server_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/firefly_mcp/server.py tests/test_server.py
git commit -m "feat: add FastMCP server with lifespan-managed FireflyClient"
```

---

## Chunk 2: Core Tools — Import + Review

### Task 5: Build import_bank_statement tool

**Files:**
- Create: `src/firefly_mcp/tools/import_tool.py`
- Create: `src/firefly_mcp/configs/hsbc.json`
- Create: `src/firefly_mcp/configs/maybank.json`
- Create: `tests/test_import_tool.py`
- Modify: `src/firefly_mcp/server.py` — register tool

The import tool reads a local CSV, pairs it with the right bank config, and sends both to the Data Importer.

- [ ] **Step 1: Create placeholder bank configs**

```json
// src/firefly_mcp/configs/hsbc.json
{
    "version": 3,
    "date_format": "Ymd",
    "default_account": 1,
    "delimiter": "comma",
    "headers": true,
    "rules": true,
    "skip_form": false,
    "add_import_tag": true,
    "roles": [],
    "do_mapping": {},
    "mapping": {},
    "duplicate_detection_method": "classic",
    "unique_column_index": 0,
    "unique_column_type": "internal_reference",
    "flow": "file",
    "content_type": "csv",
    "specifics": []
}
```

```json
// src/firefly_mcp/configs/maybank.json
{
    "version": 3,
    "date_format": "Ymd",
    "default_account": 2,
    "delimiter": "comma",
    "headers": true,
    "rules": true,
    "skip_form": false,
    "add_import_tag": true,
    "roles": [],
    "do_mapping": {},
    "mapping": {},
    "duplicate_detection_method": "classic",
    "unique_column_index": 0,
    "unique_column_type": "internal_reference",
    "flow": "file",
    "content_type": "csv",
    "specifics": []
}
```

- [ ] **Step 2: Write failing test for import tool**

```python
# tests/test_import_tool.py
import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch
from pathlib import Path

from firefly_mcp.tools.import_tool import import_bank_statement


@pytest.mark.asyncio
async def test_import_bank_statement_hsbc(tmp_path):
    csv_file = tmp_path / "statement.csv"
    csv_file.write_text("date,description,amount\n2026-03-01,GRAB FOOD,-25.50\n")

    mock_client = AsyncMock()
    mock_client.upload_csv.return_value = (
        "Import complete. 1 transaction(s) imported. 0 duplicate(s) skipped."
    )

    result = await import_bank_statement(
        csv_path=str(csv_file),
        bank="hsbc",
        dry_run=False,
        client=mock_client,
    )
    assert "1 transaction" in result
    mock_client.upload_csv.assert_called_once()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_import_tool.py -v`
Expected: FAIL

- [ ] **Step 4: Write the import tool**

```python
# src/firefly_mcp/tools/import_tool.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient

CONFIGS_DIR = Path(__file__).parent.parent / "configs"

BANK_CONFIGS = {
    "hsbc": CONFIGS_DIR / "hsbc.json",
    "maybank": CONFIGS_DIR / "maybank.json",
}


def _detect_bank(csv_text: str) -> str:
    """Auto-detect bank from CSV content. Falls back to hsbc."""
    lower = csv_text[:500].lower()
    if "maybank" in lower:
        return "maybank"
    return "hsbc"


async def import_bank_statement(
    csv_path: Annotated[str, Field(description="Absolute path to the CSV file to import")],
    bank: Annotated[str, Field(description="Bank name: 'hsbc', 'maybank', or 'auto' to detect")] = "auto",
    dry_run: Annotated[bool, Field(description="If true, validate only without importing")] = False,
    *,
    client: FireflyClient,
) -> str:
    """Import a CSV bank statement into Firefly III via the Data Importer.

    Reads the CSV file, pairs it with the appropriate bank configuration,
    and uploads both to the Data Importer. Returns a summary of the import results.
    """
    path = Path(csv_path)
    if not path.exists():
        return f"Error: File not found: {csv_path}"

    csv_bytes = path.read_bytes()
    csv_text = csv_bytes.decode("utf-8", errors="replace")

    if bank == "auto":
        bank = _detect_bank(csv_text)

    config_path = BANK_CONFIGS.get(bank)
    if config_path is None:
        return f"Error: Unknown bank '{bank}'. Available: {', '.join(BANK_CONFIGS)}"

    if not config_path.exists():
        return f"Error: Config file not found: {config_path}"

    config_json = config_path.read_text()

    if dry_run:
        line_count = len(csv_text.strip().splitlines()) - 1
        return (
            f"Dry run: Would import {line_count} row(s) from '{path.name}' "
            f"using {bank} config. No data sent."
        )

    result = await client.upload_csv(csv_bytes, config_json)
    return f"Import result ({bank}, {path.name}):\n{result}"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_import_tool.py -v`
Expected: PASS

- [ ] **Step 6: Register tool in server.py**

Add to `src/firefly_mcp/server.py` after the `mcp` definition:

```python
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

from firefly_mcp.tools.import_tool import import_bank_statement as _import_bank_statement


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
```

- [ ] **Step 7: Commit**

```bash
git add src/firefly_mcp/tools/import_tool.py src/firefly_mcp/configs/ tests/test_import_tool.py src/firefly_mcp/server.py
git commit -m "feat: add import_bank_statement tool with bank config auto-detection"
```

---

### Task 6: Build get_review_queue tool

**Files:**
- Create: `src/firefly_mcp/tools/review.py`
- Create: `tests/test_review.py`
- Modify: `src/firefly_mcp/server.py` — register tools

- [ ] **Step 1: Write failing test for get_review_queue**

```python
# tests/test_review.py
import pytest
from unittest.mock import AsyncMock
from datetime import date

from firefly_mcp.tools.review import get_review_queue
from tests.conftest import SAMPLE_TRANSACTION


@pytest.mark.asyncio
async def test_get_review_queue_returns_untagged():
    mock_client = AsyncMock()
    mock_client.list_transactions.return_value = {
        "data": [SAMPLE_TRANSACTION],
        "meta": {"pagination": {"total_pages": 1}},
    }

    result = await get_review_queue(
        days_back=30,
        filter="all_unreviewed",
        client=mock_client,
    )
    assert len(result) == 1
    assert result[0].description == "GRAB FOOD"
    assert result[0].category is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_review.py::test_get_review_queue_returns_untagged -v`
Expected: FAIL

- [ ] **Step 3: Write get_review_queue**

```python
# src/firefly_mcp/tools/review.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient
from firefly_mcp.models import CompactTransaction, TransactionUpdate


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
    """Fetch transactions needing review — missing tags, categories, or budgets.

    Returns a compact list of transactions that match the filter criteria
    within the specified date range. Use this after importing to find
    transactions that need categorization.
    """
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
    """Batch-apply categories, tags, budgets, and notes to multiple transactions.

    Each update specifies a transaction_id and the fields to set.
    Only provided fields are updated — omitted fields are left unchanged.
    Returns a summary of successes and failures.
    """
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
```

- [ ] **Step 4: Write test for categorize_transactions**

```python
# tests/test_review.py (append)


@pytest.mark.asyncio
async def test_categorize_transactions_batch():
    mock_client = AsyncMock()
    mock_client.update_transaction.return_value = {"data": {}}

    updates = [
        TransactionUpdate(transaction_id=1, category="Dining", tags=["restaurant"]),
        TransactionUpdate(transaction_id=2, budget="Transport", notes="Grab ride"),
    ]

    result = await categorize_transactions(updates, client=mock_client)
    assert result["succeeded"] == 2
    assert result["failed"] == 0
    assert mock_client.update_transaction.call_count == 2


@pytest.mark.asyncio
async def test_categorize_transactions_partial_failure():
    mock_client = AsyncMock()
    mock_client.update_transaction.side_effect = [
        {"data": {}},
        Exception("API error"),
    ]

    updates = [
        TransactionUpdate(transaction_id=1, category="Dining"),
        TransactionUpdate(transaction_id=2, category="Transport"),
    ]

    result = await categorize_transactions(updates, client=mock_client)
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["errors"][0]["transaction_id"] == 2
```

- [ ] **Step 5: Run all review tests**

Run: `pytest tests/test_review.py -v`
Expected: All PASS

- [ ] **Step 6: Register tools in server.py**

Add to `src/firefly_mcp/server.py`:

```python
from firefly_mcp.tools.review import get_review_queue as _get_review_queue
from firefly_mcp.tools.review import categorize_transactions as _categorize_transactions
from firefly_mcp.models import TransactionUpdate


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
```

- [ ] **Step 7: Commit**

```bash
git add src/firefly_mcp/tools/review.py tests/test_review.py src/firefly_mcp/server.py
git commit -m "feat: add get_review_queue and categorize_transactions tools"
```

---

## Chunk 3: Search + Insights + Metadata Tools

### Task 7: Build search_transactions tool

**Files:**
- Create: `src/firefly_mcp/tools/search.py`
- Create: `tests/test_search.py`
- Modify: `src/firefly_mcp/server.py` — register tool

- [ ] **Step 1: Write failing test for query building**

```python
# tests/test_search.py
import pytest
from firefly_mcp.tools.search import _build_search_query


def test_build_query_description_only():
    q = _build_search_query(query="grab food")
    assert q == "grab food"


def test_build_query_with_filters():
    q = _build_search_query(
        query="food",
        date_from="2026-03-01",
        date_to="2026-03-31",
        amount_min=10.0,
        category="Dining",
        type="withdrawal",
    )
    assert "food" in q
    assert "date_after:2026-03-01" in q
    assert "date_before:2026-03-31" in q
    assert "amount_more:10.0" in q
    assert 'category_is:"Dining"' in q
    assert "type:withdrawal" in q


def test_build_query_no_params():
    q = _build_search_query()
    assert q == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search.py -v`
Expected: FAIL

- [ ] **Step 3: Write search tool**

```python
# src/firefly_mcp/tools/search.py
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient
from firefly_mcp.models import CompactTransaction


def _build_search_query(
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
) -> str:
    """Build Firefly III search query string from natural parameters."""
    parts: list[str] = []

    if query:
        parts.append(query)
    if date_from:
        parts.append(f"date_after:{date_from}")
    if date_to:
        parts.append(f"date_before:{date_to}")
    if amount_min is not None:
        parts.append(f"amount_more:{amount_min}")
    if amount_max is not None:
        parts.append(f"amount_less:{amount_max}")
    if account:
        parts.append(f'source_account_is:"{account}"')
    if category:
        parts.append(f'category_is:"{category}"')
    if tag:
        parts.append(f'tag_is:"{tag}"')
    if budget:
        parts.append(f'budget_is:"{budget}"')
    if type != "all":
        parts.append(f"type:{type}")

    return " ".join(parts)


async def search_transactions(
    query: Annotated[str | None, Field(description="Free-text description search")] = None,
    date_from: Annotated[str | None, Field(description="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, Field(description="End date (YYYY-MM-DD)")] = None,
    amount_min: Annotated[float | None, Field(description="Minimum amount")] = None,
    amount_max: Annotated[float | None, Field(description="Maximum amount")] = None,
    account: Annotated[str | None, Field(description="Account name")] = None,
    category: Annotated[str | None, Field(description="Category name")] = None,
    tag: Annotated[str | None, Field(description="Tag name")] = None,
    budget: Annotated[str | None, Field(description="Budget name")] = None,
    type: Annotated[str, Field(description="Transaction type: 'withdrawal', 'deposit', 'transfer', 'all'")] = "all",
    *,
    client: FireflyClient,
) -> list[CompactTransaction]:
    """Search transactions with natural parameters.

    Translates friendly parameters into Firefly III's search query language.
    Combine any parameters to narrow results. Returns compact transaction list.
    """
    search_query = _build_search_query(
        query=query,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        account=account,
        category=category,
        tag=tag,
        budget=budget,
        type=type,
    )

    if not search_query:
        return []

    results: list[CompactTransaction] = []
    page = 1

    while True:
        data = await client.search_transactions(search_query, page=page)
        for item in data.get("data", []):
            results.append(CompactTransaction.from_api(item))

        total_pages = data.get("meta", {}).get("pagination", {}).get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return results
```

- [ ] **Step 4: Write test for full search with mock client**

```python
# tests/test_search.py (append)
from unittest.mock import AsyncMock
from tests.conftest import SAMPLE_TRANSACTION
from firefly_mcp.tools.search import search_transactions


@pytest.mark.asyncio
async def test_search_transactions_with_results():
    mock_client = AsyncMock()
    mock_client.search_transactions.return_value = {
        "data": [SAMPLE_TRANSACTION],
        "meta": {"pagination": {"total_pages": 1}},
    }

    result = await search_transactions(
        query="grab", type="withdrawal", client=mock_client
    )
    assert len(result) == 1
    assert result[0].description == "GRAB FOOD"


@pytest.mark.asyncio
async def test_search_transactions_empty_params():
    mock_client = AsyncMock()
    result = await search_transactions(client=mock_client)
    assert result == []
    mock_client.search_transactions.assert_not_called()
```

- [ ] **Step 5: Run all search tests**

Run: `pytest tests/test_search.py -v`
Expected: All PASS

- [ ] **Step 6: Register tool in server.py**

Add to `src/firefly_mcp/server.py`:

```python
from firefly_mcp.tools.search import search_transactions as _search_transactions


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
```

- [ ] **Step 7: Commit**

```bash
git add src/firefly_mcp/tools/search.py tests/test_search.py src/firefly_mcp/server.py
git commit -m "feat: add search_transactions tool with query builder"
```

---

### Task 8: Build get_spending_summary tool

**Files:**
- Create: `src/firefly_mcp/tools/insights.py`
- Create: `tests/test_insights.py`
- Modify: `src/firefly_mcp/server.py` — register tool

- [ ] **Step 1: Write failing test for period resolution**

```python
# tests/test_insights.py
import pytest
from unittest.mock import patch
from datetime import date

from firefly_mcp.tools.insights import _resolve_period


@patch("firefly_mcp.tools.insights.date")
def test_resolve_period_this_month(mock_date):
    mock_date.today.return_value = date(2026, 3, 15)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    start, end = _resolve_period("this_month")
    assert start == "2026-03-01"
    assert end == "2026-03-31"


@patch("firefly_mcp.tools.insights.date")
def test_resolve_period_last_month(mock_date):
    mock_date.today.return_value = date(2026, 3, 15)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    start, end = _resolve_period("last_month")
    assert start == "2026-02-01"
    assert end == "2026-02-28"


def test_resolve_period_custom():
    start, end = _resolve_period("2026-01-01:2026-01-31")
    assert start == "2026-01-01"
    assert end == "2026-01-31"


@patch("firefly_mcp.tools.insights.date")
def test_resolve_period_this_year(mock_date):
    mock_date.today.return_value = date(2026, 3, 15)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    start, end = _resolve_period("this_year")
    assert start == "2026-01-01"
    assert end == "2026-12-31"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_insights.py -v`
Expected: FAIL

- [ ] **Step 3: Write insights tool**

```python
# src/firefly_mcp/tools/insights.py
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
    """Get aggregated spending summary for a period, grouped by category/tag/budget/account.

    Shows totals per group sorted by amount. When grouped by budget,
    includes budget limits and remaining amounts for comparison.
    """
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
```

- [ ] **Step 4: Write test for full summary with mock**

```python
# tests/test_insights.py (append)
from unittest.mock import AsyncMock
from firefly_mcp.tools.insights import get_spending_summary


@pytest.mark.asyncio
async def test_get_spending_summary_by_category():
    mock_client = AsyncMock()
    mock_client.get_insight.return_value = [
        {"name": "Dining", "difference_float": -150.00, "currency_code": "MYR"},
        {"name": "Transport", "difference_float": -80.00, "currency_code": "MYR"},
    ]

    result = await get_spending_summary(
        period="this_month", group_by="category", client=mock_client
    )
    assert result["grand_total"] == 230.00
    assert result["groups"][0]["name"] == "Dining"
    assert result["groups"][1]["name"] == "Transport"


@pytest.mark.asyncio
async def test_get_spending_summary_by_budget_with_limits():
    mock_client = AsyncMock()
    mock_client.get_insight.return_value = [
        {"name": "Eating Out", "difference_float": -120.00, "currency_code": "MYR"},
    ]
    mock_client.list_budgets.return_value = {
        "data": [
            {
                "id": "1",
                "attributes": {
                    "name": "Eating Out",
                    "auto_budget_amount": "200.00",
                    "auto_budget_period": "monthly",
                },
            }
        ]
    }

    result = await get_spending_summary(
        period="2026-03-01:2026-03-31", group_by="budget", client=mock_client
    )
    assert result["groups"][0]["limit"] == 200.0
    assert result["groups"][0]["remaining"] == 80.0
```

- [ ] **Step 5: Run all insight tests**

Run: `pytest tests/test_insights.py -v`
Expected: All PASS

- [ ] **Step 6: Register tool in server.py**

Add to `src/firefly_mcp/server.py`:

```python
from firefly_mcp.tools.insights import get_spending_summary as _get_spending_summary


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
```

- [ ] **Step 7: Commit**

```bash
git add src/firefly_mcp/tools/insights.py tests/test_insights.py src/firefly_mcp/server.py
git commit -m "feat: add get_spending_summary tool with period resolution and budget comparison"
```

---

### Task 9: Build get_financial_context and manage_metadata tools

**Files:**
- Create: `src/firefly_mcp/tools/metadata.py`
- Create: `tests/test_metadata.py`
- Modify: `src/firefly_mcp/server.py` — register tools

- [ ] **Step 1: Write failing test for get_financial_context**

```python
# tests/test_metadata.py
import pytest
from unittest.mock import AsyncMock

from firefly_mcp.tools.metadata import get_financial_context, manage_metadata


@pytest.mark.asyncio
async def test_get_financial_context_tags():
    mock_client = AsyncMock()
    mock_client.list_tags.return_value = {
        "data": [
            {"id": "1", "attributes": {"tag": "restaurant", "date": None}},
            {"id": "2", "attributes": {"tag": "transport", "date": None}},
        ]
    }

    result = await get_financial_context(what="tags", client=mock_client)
    assert "tags" in result
    assert len(result["tags"]) == 2
    assert result["tags"][0]["name"] == "restaurant"


@pytest.mark.asyncio
async def test_get_financial_context_all():
    mock_client = AsyncMock()
    mock_client.list_tags.return_value = {"data": []}
    mock_client.list_categories.return_value = {"data": []}
    mock_client.list_budgets.return_value = {"data": []}
    mock_client.list_accounts.return_value = {"data": []}
    mock_client.list_bills.return_value = {"data": []}

    result = await get_financial_context(what="all", client=mock_client)
    assert "tags" in result
    assert "categories" in result
    assert "budgets" in result
    assert "accounts" in result
    assert "bills" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metadata.py -v`
Expected: FAIL

- [ ] **Step 3: Write metadata tools**

```python
# src/firefly_mcp/tools/metadata.py
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient


async def _fetch_tags(client: FireflyClient) -> list[dict]:
    data = await client.list_tags()
    return [{"name": t["attributes"]["tag"]} for t in data.get("data", [])]


async def _fetch_categories(client: FireflyClient) -> list[dict]:
    data = await client.list_categories()
    return [{"name": c["attributes"]["name"]} for c in data.get("data", [])]


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
    """Get reference data for making categorization decisions.

    Returns available categories, tags, budgets, accounts, and/or bills.
    Call with 'all' before categorizing transactions to know what's available.
    """
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
        Field(description="Action: 'create_tag', 'create_category', 'create_budget', 'update_budget_limit'"),
    ],
    name: Annotated[str, Field(description="Name of the tag, category, or budget")],
    amount: Annotated[float | None, Field(description="Budget limit amount (for budget operations)")] = None,
    period: Annotated[str | None, Field(description="Budget period: 'monthly', 'weekly', 'yearly'")] = None,
    *,
    client: FireflyClient,
) -> dict:
    """Create or update tags, categories, and budgets.

    Use when existing metadata doesn't fit a transaction.
    For budgets, provide amount and period to set a spending limit.
    """
    if action == "create_tag":
        data = await client.create_tag(name)
        return {"created": "tag", "name": name, "id": data["data"]["id"]}

    elif action == "create_category":
        data = await client.create_category(name)
        return {"created": "category", "name": name, "id": data["data"]["id"]}

    elif action == "create_budget":
        data = await client.create_budget(name)
        return {"created": "budget", "name": name, "id": data["data"]["id"]}

    elif action == "update_budget_limit":
        if amount is None:
            return {"error": "amount is required for update_budget_limit"}

        # Find budget ID by name
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
            # Start from Monday of current week
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

    return {"error": f"Unknown action '{action}'"}
```

- [ ] **Step 4: Write test for manage_metadata**

```python
# tests/test_metadata.py (append)


@pytest.mark.asyncio
async def test_manage_metadata_create_tag():
    mock_client = AsyncMock()
    mock_client.create_tag.return_value = {"data": {"id": "5"}}

    result = await manage_metadata(action="create_tag", name="gaming", client=mock_client)
    assert result["created"] == "tag"
    assert result["name"] == "gaming"


@pytest.mark.asyncio
async def test_manage_metadata_create_category():
    mock_client = AsyncMock()
    mock_client.create_category.return_value = {"data": {"id": "3"}}

    result = await manage_metadata(action="create_category", name="Dining", client=mock_client)
    assert result["created"] == "category"
    mock_client.create_category.assert_called_once_with("Dining")


@pytest.mark.asyncio
async def test_manage_metadata_create_budget():
    mock_client = AsyncMock()
    mock_client.create_budget.return_value = {"data": {"id": "2"}}

    result = await manage_metadata(action="create_budget", name="Transport", client=mock_client)
    assert result["created"] == "budget"


@pytest.mark.asyncio
async def test_manage_metadata_update_budget_limit():
    mock_client = AsyncMock()
    mock_client.list_budgets.return_value = {
        "data": [{"id": "1", "attributes": {"name": "Eating Out"}}]
    }
    mock_client.create_budget_limit.return_value = {"data": {"id": "10"}}

    result = await manage_metadata(
        action="update_budget_limit",
        name="Eating Out",
        amount=500.0,
        period="monthly",
        client=mock_client,
    )
    assert result["updated"] == "budget_limit"
    assert result["amount"] == 500.0
    assert result["period"] == "monthly"
    mock_client.create_budget_limit.assert_called_once()


@pytest.mark.asyncio
async def test_manage_metadata_update_budget_limit_not_found():
    mock_client = AsyncMock()
    mock_client.list_budgets.return_value = {"data": []}

    result = await manage_metadata(
        action="update_budget_limit", name="Nonexistent", amount=100.0, client=mock_client
    )
    assert "error" in result
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_manage_metadata_unknown_action():
    mock_client = AsyncMock()
    result = await manage_metadata(action="delete_everything", name="x", client=mock_client)
    assert "error" in result
```

- [ ] **Step 5: Run all metadata tests**

Run: `pytest tests/test_metadata.py -v`
Expected: All PASS

- [ ] **Step 6: Register tools in server.py**

Add to `src/firefly_mcp/server.py`:

```python
from firefly_mcp.tools.metadata import get_financial_context as _get_financial_context
from firefly_mcp.tools.metadata import manage_metadata as _manage_metadata


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
    name: str,
    amount: float | None = None,
    period: str | None = None,
    ctx: Context = CurrentContext(),
) -> dict:
    """Create tags, categories, or budgets. Update budget limits.

    Actions: 'create_tag', 'create_category', 'create_budget', 'update_budget_limit'.
    For budget limits, provide amount and period ('monthly'/'weekly'/'yearly').
    """
    client = ctx.lifespan_context["client"]
    return await _manage_metadata(action, name, amount=amount, period=period, client=client)
```

- [ ] **Step 7: Commit**

```bash
git add src/firefly_mcp/tools/metadata.py tests/test_metadata.py src/firefly_mcp/server.py
git commit -m "feat: add get_financial_context and manage_metadata tools"
```

---

## Chunk 4: Prompts, Resources, and Final Integration

### Task 10: Add prompts

**Files:**
- Create: `src/firefly_mcp/prompts.py`
- Modify: `src/firefly_mcp/server.py` — register prompts

- [ ] **Step 1: Write prompts module**

```python
# src/firefly_mcp/prompts.py
from __future__ import annotations

REVIEW_IMPORTS_TEMPLATE = """You are reviewing recently imported bank transactions in Firefly III.

Follow these steps:

1. First, call get_financial_context("all") to learn what categories, tags, and budgets exist.

2. Then call get_review_queue(days_back={days_back}) to see transactions needing review.

3. For each transaction, analyze the description and amount to determine:
   - Category (e.g., Dining, Transport, Shopping, Subscriptions, Groceries)
   - Tags (e.g., restaurant, grab, subscription, online-shopping)
   - Budget (e.g., Eating Out, Transport, Personal Spending, Tech)
   - Notes (optional, for additional context)

4. Present your proposed categorizations to the user in a clear table format.
   Group similar transactions together. Ask the user to confirm or adjust.

5. Once confirmed, call categorize_transactions with all the updates.

6. Report the results: how many succeeded, any failures.

Tips for categorization:
- Look for merchant keywords: GRAB = transport/food delivery, SHOPEE/LAZADA = online shopping
- Recurring similar amounts = likely subscriptions
- If unsure, ask the user rather than guessing
- Create new tags/categories via manage_metadata if needed
"""


MONTHLY_REVIEW_TEMPLATE = """You are conducting a monthly financial review for {month}.

Follow these steps:

1. Call get_spending_summary(period="{start}:{end}", group_by="budget") to see budget performance.

2. Call get_spending_summary(period="{start}:{end}", group_by="category") for category breakdown.

3. Check for uncategorized transactions: get_review_queue(days_back=31, filter="all_unreviewed")

4. Present a summary to the user:
   - Budget performance: which budgets are over/under, remaining amounts
   - Top spending categories
   - Any uncategorized transactions that need attention
   - Notable patterns or anomalies (unusually large transactions, new merchants)

5. Ask if they want to:
   - Categorize remaining transactions
   - Adjust any budget limits for next month
   - Tag specific transactions for tracking
"""
```

- [ ] **Step 2: Register prompts in server.py**

Add to `src/firefly_mcp/server.py`:

```python
from firefly_mcp.prompts import REVIEW_IMPORTS_TEMPLATE, MONTHLY_REVIEW_TEMPLATE


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
    # Calculate last day of month
    year, mon = int(month[:4]), int(month[5:7])
    import calendar
    last_day = calendar.monthrange(year, mon)[1]
    end = f"{month}-{last_day}"

    return MONTHLY_REVIEW_TEMPLATE.format(month=month, start=start, end=end)
```

- [ ] **Step 3: Write tests for prompts**

```python
# tests/test_prompts.py
from firefly_mcp.prompts import REVIEW_IMPORTS_TEMPLATE, MONTHLY_REVIEW_TEMPLATE


def test_review_imports_template_formats():
    result = REVIEW_IMPORTS_TEMPLATE.format(days_back=14)
    assert "days_back=14" in result
    assert "get_financial_context" in result
    assert "categorize_transactions" in result


def test_monthly_review_template_formats():
    result = MONTHLY_REVIEW_TEMPLATE.format(month="2026-03", start="2026-03-01", end="2026-03-31")
    assert "2026-03-01" in result
    assert "2026-03-31" in result
    assert "get_spending_summary" in result


def test_monthly_review_server_prompt():
    """Test the server-level prompt function handles month parsing."""
    from firefly_mcp.server import monthly_review
    result = monthly_review(month="2026-02")
    assert "2026-02-01" in result
    assert "2026-02-28" in result


def test_monthly_review_server_prompt_default():
    """Test that default month uses current month."""
    from firefly_mcp.server import monthly_review
    result = monthly_review()
    assert "get_spending_summary" in result
```

- [ ] **Step 4: Run prompt tests**

Run: `pytest tests/test_prompts.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/firefly_mcp/prompts.py src/firefly_mcp/server.py tests/test_prompts.py
git commit -m "feat: add review_imports and monthly_review prompt templates"
```

---

### Task 11: Add resources

**Files:**
- Create: `src/firefly_mcp/resources.py`
- Modify: `src/firefly_mcp/server.py` — register resources

- [ ] **Step 1: Write resources module**

```python
# src/firefly_mcp/resources.py
from __future__ import annotations

import json
from pathlib import Path

CONFIGS_DIR = Path(__file__).parent / "configs"


def get_bank_config(bank: str) -> str:
    """Read and return the Data Importer config for a bank."""
    config_path = CONFIGS_DIR / f"{bank}.json"
    if not config_path.exists():
        available = [p.stem for p in CONFIGS_DIR.glob("*.json")]
        return json.dumps({"error": f"Unknown bank '{bank}'", "available": available})
    return config_path.read_text()
```

- [ ] **Step 2: Register resource in server.py**

Add to `src/firefly_mcp/server.py`:

```python
from firefly_mcp.resources import get_bank_config


@mcp.resource("firefly://config/{bank}")
def bank_config(bank: str) -> str:
    """Data Importer JSON configuration for a bank (hsbc, maybank)."""
    return get_bank_config(bank)
```

- [ ] **Step 3: Write tests for resources**

```python
# tests/test_resources.py
import json
from firefly_mcp.resources import get_bank_config


def test_get_bank_config_hsbc():
    result = get_bank_config("hsbc")
    data = json.loads(result)
    assert data["version"] == 3
    assert data["content_type"] == "csv"


def test_get_bank_config_maybank():
    result = get_bank_config("maybank")
    data = json.loads(result)
    assert data["version"] == 3


def test_get_bank_config_unknown():
    result = get_bank_config("unknown_bank")
    data = json.loads(result)
    assert "error" in data
    assert "available" in data
    assert "hsbc" in data["available"]
```

- [ ] **Step 4: Run resource tests**

Run: `pytest tests/test_resources.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/firefly_mcp/resources.py src/firefly_mcp/server.py tests/test_resources.py
git commit -m "feat: add firefly://config/{bank} resource for import configs"
```

---

### Task 12: Final server.py cleanup and integration test

**Files:**
- Modify: `src/firefly_mcp/server.py` — add entry point to pyproject.toml
- Create: `tests/test_server.py` — full integration test
- Modify: `pyproject.toml` — add script entry point

- [ ] **Step 1: Write integration test**

```python
# tests/test_server.py
import pytest


def test_server_has_correct_name():
    from firefly_mcp.server import mcp
    assert mcp.name == "firefly"


def test_server_has_all_tools():
    from firefly_mcp.server import mcp

    tool_names = {t.name for t in mcp._tool_manager.tools.values()}
    expected_tools = {
        "import_bank_statement",
        "get_review_queue",
        "categorize_transactions",
        "search_transactions",
        "get_spending_summary",
        "get_financial_context",
        "manage_metadata",
    }
    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"


def test_server_has_prompts():
    from firefly_mcp.server import mcp

    prompt_names = {p.name for p in mcp._prompt_manager.prompts.values()}
    expected_prompts = {"review_imports", "monthly_review"}
    assert expected_prompts.issubset(prompt_names), f"Missing prompts: {expected_prompts - prompt_names}"


def test_server_has_resources():
    from firefly_mcp.server import mcp

    # Verify resource templates are registered (firefly://config/{bank})
    templates = {t.uri_template for t in mcp._resource_manager.templates.values()}
    assert any("config" in str(t) for t in templates), f"Missing config resource template. Found: {templates}"


def test_server_has_instructions():
    from firefly_mcp.server import mcp
    assert "Firefly III" in mcp.instructions
    assert "get_financial_context" in mcp.instructions
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_server.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_server.py
git commit -m "feat: add comprehensive integration tests — server complete"
```

---

## Summary

| Task | What | Key Files |
|------|------|-----------|
| 1 | Project scaffold + .gitignore | pyproject.toml, .env.example, .gitignore |
| 2 | FireflyClient | client.py, test_client.py |
| 3 | Pydantic models | models.py, test_models.py |
| 4 | FastMCP server + lifespan | server.py, test_server.py |
| 5 | import_bank_statement | import_tool.py, configs/*.json |
| 6 | review queue + categorize | review.py, test_review.py |
| 7 | search_transactions | search.py, test_search.py |
| 8 | get_spending_summary | insights.py, test_insights.py |
| 9 | metadata tools | metadata.py, test_metadata.py |
| 10 | Prompts | prompts.py, test_prompts.py |
| 11 | Resources | resources.py, test_resources.py |
| 12 | Integration tests | test_server.py |
