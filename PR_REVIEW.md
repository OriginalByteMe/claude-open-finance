# PR Review: Firefly III MCP Server — Claude Open Finance

**Reviewed by:** Agent Team (5 specialized reviewers)
**Date:** 2026-03-13
**Scope:** Full codebase review — 56 files, ~8,700 lines

---

## Overall Assessment

The project has a **clean, well-structured architecture** with proper separation of concerns: `server.py` (MCP tool definitions) → `tools/*.py` (business logic) → `client.py` (HTTP transport) → `models.py` (data shapes). The test suite is solid for a project this size, with both unit and integration tests. The plugin/skill system is thoughtfully designed.

That said, there are several **critical issues** around error handling, security, and API consistency that should be addressed before merging.

---

## Critical Issues (Must Fix)

### 1. Arbitrary File System Read via `csv_path` — Security
**File:** `src/firefly_mcp/tools/import_tool.py:35-39`

The `csv_path` parameter accepts any absolute path with no restrictions. An MCP client could supply paths like `/etc/passwd` or `~/.ssh/id_rsa`. There is no allowlist, no directory restriction, no file extension check, and no file size limit.

**Suggestion:** Restrict to an allowed directory (configurable via env var), validate `.csv` extension, and add a file size limit.

```python
ALLOWED_DIR = Path(os.environ.get("FIREFLY_IMPORT_DIR", "/tmp/firefly-imports"))

def _validate_path(csv_path: str) -> Path:
    path = Path(csv_path).resolve()
    if not path.is_relative_to(ALLOWED_DIR):
        raise ValueError(f"Path must be within {ALLOWED_DIR}")
    if path.suffix.lower() != ".csv":
        raise ValueError("Only .csv files are allowed")
    return path
```

---

### 2. Unhandled httpx Exceptions in Most Tool Paths
**File:** `src/firefly_mcp/client.py` (throughout) + `src/firefly_mcp/server.py`

Every client method calls `raise_for_status()` but almost no tool function catches the resulting `httpx.HTTPStatusError`. Only `review.py` wraps calls in try/except. A single 404 or 422 from Firefly III will crash the tool invocation with an inscrutable httpx traceback.

**Suggestion:** Add centralized error handling — either a wrapper method in `FireflyClient` or a decorator for tool functions:

```python
async def _api_call(self, method, url, **kwargs):
    resp = await self._firefly.request(method, url, **kwargs)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise FireflyAPIError(resp.status_code, body) from e
    return resp
```

---

### 3. Inconsistent Error Reporting Pattern Across All Tools
Three different error strategies are used:
- Return `{"error": "message"}` dict — `automations.py`, `metadata.py`, `insights.py`
- Return plain string `"Error: ..."` — `import_tool.py`
- Let exceptions propagate unhandled — everything else

**Suggestion:** Pick one pattern. Returning `{"error": "..."}` dicts is the most common pattern in this codebase — apply it consistently. Make `import_bank_statement` return `dict` like all other tools.

---

### 4. Missing Environment Variable Validation at Startup
**File:** `src/firefly_mcp/server.py:35-38`

The lifespan reads `FIREFLY_URL`, `FIREFLY_TOKEN`, `FIREFLY_IMPORTER_URL`, `FIREFLY_IMPORTER_SECRET` via `os.environ[...]` with no error handling. A missing variable crashes with a raw `KeyError`.

**Suggestion:**
```python
required = ["FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_IMPORTER_URL", "FIREFLY_IMPORTER_SECRET"]
missing = [k for k in required if k not in os.environ]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
```

---

### 5. Importer Secret Passed as URL Query Parameter
**File:** `src/firefly_mcp/client.py:288-289`

```python
params={"secret": self.importer_secret},
```

Query parameters are logged by web servers, proxies, and load balancers. If `raise_for_status()` throws, the exception message includes the full URL with `?secret=...`.

**Suggestion:** Move to a request header instead.

---

### 6. Path Traversal in Bank Config Resource
**File:** `src/firefly_mcp/resources.py:9-15`

The `bank` parameter is taken from the URI and used directly in `CONFIGS_DIR / f"{bank}.json"`. A value like `../../etc/passwd` would escape the configs directory.

**Suggestion:**
```python
if ".." in bank or "/" in bank:
    raise ValueError("Invalid bank name")
```

---

### 7. Silent Skip Accounting Bug in `review.py`
**File:** `src/firefly_mcp/tools/review.py:85`

When `txn_payload` is empty, `continue` skips the update without incrementing `succeeded` or `failed`. The returned `total` is `len(updates)`, making `succeeded + failed != total` possible. Same issue in `update_transactions` at line 142.

**Suggestion:** Add a `skipped` counter, or count these as succeeded (no-op updates).

---

### 8. Empty Name Validation Missing for Tag/Category Creation
**File:** `src/firefly_mcp/tools/metadata.py:102`

The `name` parameter defaults to `""`. For `create_tag` (line 123) and `create_category` (line 140), there is no check that `name` is non-empty. `create_account` and `create_bill` do validate this. An LLM could create a tag named `""`.

---

## High Priority Suggestions

### 9. Duplicated Pagination Pattern — Extract a Helper
The same `while True` / fetch page / check `total_pages` / break or increment loop appears in 4 files:
- `automations.py:73-82`
- `recurring.py:97-111`
- `review.py:40-55`
- `search.py:77-85`

None have an upper-bound safety limit. A caller requesting `days_back=100000` could trigger hundreds of sequential API calls.

**Suggestion:** Extract `async def paginate(client_method, **kwargs, max_pages=100)` into the client or a utility module.

---

### 10. `manage_metadata` God Function — 195-Line Dispatch
**File:** `src/firefly_mcp/tools/metadata.py:92-286`

A single function with 15 action branches handling 5 entity types. This makes it hard to test individual actions and easy to miss cases.

**Suggestion:** Split into per-entity functions or use a dispatch table pattern (similar to `FETCHERS` in `get_financial_context`).

---

### 11. `_resolve_period` Silently Defaults Invalid Input
**File:** `src/firefly_mcp/tools/insights.py:35-38`

Unrecognized period strings (e.g., typo `"this_mnoth"`) silently default to `this_month`. Custom date ranges with malformed format also fall through silently.

**Suggestion:** Return an error for unrecognized period values.

---

### 12. `_detect_bank` Silently Defaults to HSBC
**File:** `src/firefly_mcp/tools/import_tool.py:21`

If CSV content doesn't match any known bank pattern, it defaults to HSBC config without warning, which could produce corrupted imports.

---

### 13. `close()` Method Not Exception-Safe
**File:** `src/firefly_mcp/client.py:38-40`

If the first `aclose()` fails, the second is never called.

```python
async def close(self) -> None:
    try:
        await self._firefly.aclose()
    finally:
        await self._importer.aclose()
```

---

### 14. Hardcoded Currency Default `"MYR"`
**File:** `src/firefly_mcp/client.py:168`

The `currency_code` parameter defaults to `"MYR"` (Malaysian Ringgit), which will surprise any non-Malaysian user.

---

### 15. Placeholder Inconsistency Between `.env.example` and Hook
**Files:** `plugins/firefly-tools/.env.example` vs `plugins/firefly-tools/hooks/check-setup.sh:13`

`.env.example` uses `your-personal-access-token` but the hook checks for `REPLACE_WITH`. Users who copy `.env.example` to `.env` will bypass the setup check.

---

## Infrastructure & CI

### 16. Unpinned Docker Images and Dependencies
- `docker-compose.yml` uses `fireflyiii/core:latest` and `fireflyiii/data-importer:latest`
- `pyproject.toml` uses `>=` version pins with no upper bounds
- CI uses `version: "latest"` for uv
- `.mcp.json` installs from git HEAD with no tag

**Suggestion:** Pin versions for reproducibility. Add `pip-audit` to CI.

### 17. CI Could Be Improved
- No linting (`ruff`) or type-checking (`mypy`) step
- No JUnit/XML test report upload
- Integration tests depend on unit tests (`needs: unit-tests`) — if independent, run in parallel to cut CI time

### 18. Plugin Repository URL Mismatch
**File:** `plugins/firefly-tools/.claude-plugin/plugin.json:8`

Points to `firefly-tools` repo, not `claude-open-finance`.

---

## Test Coverage Gaps

### 19. Client Layer — Only 3 of ~30 Methods Tested
`test_client.py` covers `list_transactions`, `search_transactions`, and `upload_csv`. The entire accounts, tags, categories, budgets, bills, rules, and insights surface is untested.

### 20. Pagination Never Tested with Multi-Page Responses
Every paginating function is tested with single-page mocks only.

### 21. `_needs_review` Has 4 Filter Branches, Only 1 Tested
The `untagged`, `uncategorized`, and `unbudgeted` filters are never exercised in tests.

### 22. Import Tool — Only Happy Path Tested
Missing: file not found, unknown bank, config not found, dry run, auto-detection.

### 23. `_resolve_period` January Edge Case
When `today` is January, `last_month` should return December of the previous year. Not tested.

---

## Nits

- `server.py:86,141` — Parameters named `filter` and `type` shadow Python builtins. Use `filter_type`, `txn_type`.
- `import_tool.py:3` — `json` imported but never used.
- `recurring.py:18` — `re` imported inside function body; move to top-level.
- `client.py:79,88` — Duplicate `# -- Accounts --` section header.
- `models.py:29` — `amount` typed as `str` when semantically numeric; leaks API detail.
- `models.py:106` — `from_api` silently discards split transactions (only reads `transactions[0]`).
- `test_review.py:10` — Test name `test_get_review_queue_returns_untagged` is misleading (uses `all_unreviewed`).
- `insights.py:93` — `if auto_budget_amount:` treats `0` as falsy; use `is not None`.
- Bank configs hardcode `default_account: 1` and `2` — will fail for users with different account IDs.

---

## Summary

| Category | Critical | High | Medium | Low/Nit |
|----------|----------|------|--------|---------|
| Security | 2 | 1 | 4 | 2 |
| Error Handling | 3 | 1 | — | — |
| Code Quality | 1 | 3 | 2 | 9 |
| Test Coverage | — | — | 5 | 3 |
| Infrastructure | — | 1 | 3 | 2 |
| **Total** | **6** | **6** | **14** | **16** |

### Top 5 Actions Before Merge
1. **Restrict `csv_path`** to prevent arbitrary file reads (security)
2. **Add centralized error handling** for httpx exceptions (reliability)
3. **Unify error reporting** across all tools (API consistency)
4. **Validate env vars at startup** with clear error messages (UX)
5. **Move importer secret from query param to header** (security)
