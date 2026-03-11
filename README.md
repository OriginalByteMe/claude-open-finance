# 🔥 Firefly Tools

**Stop manually categorizing bank transactions. Life's too short.**

A Claude Code plugin + MCP server that turns your messy bank statements into a clean, categorized ledger in [Firefly III](https://www.firefly-iii.org/) — the open-source personal finance manager.

---

## Why This Exists

I use Firefly III to track every ringgit I spend. I love that it's open-source, self-hosted, and my financial data stays on my own server — not in some bank's "insights" dashboard I didn't ask for.

But here's the problem: **Malaysian banks are painful.**

No open banking APIs. No CSV exports that just work. You get a PDF statement (if you're lucky), and then you're staring at 200 transactions trying to remember if "POS DEBIT 29481 KL" was groceries or that birthday dinner. Every month. For every account.

This tool fixes that. Drop in a PDF or CSV bank statement, and Claude will:

1. **Parse it** — Claude is surprisingly good at extracting transaction data from PDFs
2. **Import it** — straight into Firefly III via the Data Importer
3. **Categorize everything** — batch-classifying merchants with high confidence, then asking you about the ambiguous ones
4. **Build your ledger** — clean, consistent, tagged, budgeted

What used to take an evening now takes a few minutes of confirming suggestions.

---

## What's Inside

This repo has two parts that work together:

### MCP Server (`src/firefly_mcp/`)

A [Model Context Protocol](https://modelcontextprotocol.io) server that gives Claude direct access to your Firefly III instance. Seven tools covering the full workflow:

| Tool | What it does |
|------|-------------|
| `import_bank_statement` | Upload a CSV + bank config to the Data Importer |
| `get_review_queue` | Find transactions missing categories, tags, or budgets |
| `categorize_transactions` | Batch-apply classifications to transactions |
| `search_transactions` | Query transactions with natural filters |
| `get_spending_summary` | Spending breakdown by category, tag, budget, or account |
| `get_financial_context` | List your existing categories, tags, budgets, and accounts |
| `manage_metadata` | Create new tags, categories, budgets, or adjust budget limits |

The MCP server works standalone with any MCP-compatible client — Claude Code, Claude Desktop, or others.

### Claude Code Plugin (`skills/`, `agents/`, `hooks/`)

Workflow automation built on top of the MCP server. This is where the magic happens.

**Skills (slash commands):**

| Command | What it does |
|---------|-------------|
| `/firefly-tools:setup` | Guided first-time setup — creates your config file safely |
| `/firefly-tools:import-and-review` | Full pipeline: parse statement → import → categorize |
| `/firefly-tools:classify-unknowns` | Review and classify uncategorized transactions |
| `/firefly-tools:monthly-review` | End-of-month spending analysis with budget comparison |

**Agents (the workers):**

| Agent | Model | Role |
|-------|-------|------|
| `csv-parser` | Sonnet | Extracts transactions from PDF statements → CSV |
| `merchant-classifier` | Haiku | Batch-identifies merchants and suggests categories |

---

## Quick Start

### Prerequisites

- [Firefly III](https://www.firefly-iii.org/) running somewhere (Docker, Unraid, bare metal, etc.)
- [Firefly III Data Importer](https://docs.firefly-iii.org/how-to/data-importer/installation/docker/) running alongside it
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- [uv](https://docs.astral.sh/uv/) installed (for running the Python MCP server)

### 1. Install the Plugin

```bash
claude plugin install OriginalByteMe/firefly-tools
```

### 2. Run Setup

Start Claude Code and run:

```
/firefly-tools:setup
```

This creates a `.env` file in the plugin directory with placeholder values and tells you exactly where it is. Open that file in your text editor and fill in your credentials:

```env
FIREFLY_URL=http://your-server:8080
FIREFLY_TOKEN=your-personal-access-token
FIREFLY_IMPORTER_URL=http://your-server:8081
FIREFLY_IMPORTER_SECRET=your-auto-import-secret
```

> **Your credentials never enter the chat.** The setup skill creates the file, you edit it externally, then Claude verifies the connection works. The `.env` file stays local and is gitignored.

**Where to find each value:**

| Value | Where to get it |
|-------|----------------|
| `FIREFLY_URL` | The URL you use to open Firefly III in your browser |
| `FIREFLY_TOKEN` | Firefly III → Options → Profile → Personal Access Tokens → Create |
| `FIREFLY_IMPORTER_URL` | The URL of your Data Importer instance |
| `FIREFLY_IMPORTER_SECRET` | The `AUTO_IMPORT_SECRET` in your Data Importer's config (min 16 chars) |

### 3. Import a Statement

```
/firefly-tools:import-and-review ~/Downloads/march-2026-statement.pdf
```

That's it. Claude will parse the PDF, import the transactions, classify them, and ask you about the ambiguous ones.

---

## Usage Examples

### Import and categorize a bank statement

```
/firefly-tools:import-and-review ~/Downloads/hsbc-march.csv
```

Works with both CSV and PDF files. PDFs are parsed by the `csv-parser` agent, which handles multi-page statements and extracts transaction data into a clean CSV before importing.

### Clean up uncategorized transactions

```
/firefly-tools:classify-unknowns 14
```

Finds all transactions from the last 14 days that are missing categories, tags, or budgets. Groups similar transactions together, suggests classifications, and asks you about the ambiguous ones in batches — not one-by-one.

### Monthly spending review

```
/firefly-tools:monthly-review 2026-02
```

Pulls your spending data, compares against budgets, shows month-over-month trends, and has a conversation with you about what to adjust. Suggests concrete actions like raising a budget limit or creating a new tracking tag.

---

## Using the MCP Server Standalone

If you're not using Claude Code, you can still use the MCP server directly with any MCP-compatible client.

### Claude Desktop

Add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "firefly": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/OriginalByteMe/firefly-tools", "firefly-mcp"]
    }
  }
}
```

You'll need to set the environment variables (`FIREFLY_URL`, `FIREFLY_TOKEN`, `FIREFLY_IMPORTER_URL`, `FIREFLY_IMPORTER_SECRET`) in a `.env` file in your working directory or in your shell environment for this to work.

### Other MCP Clients

The MCP server uses stdio transport and should work with any MCP client. The command to start it is:

```bash
uvx --from git+https://github.com/OriginalByteMe/firefly-tools firefly-mcp
```

Or if you've cloned the repo locally:

```bash
uv run firefly-mcp
```

---

## Supported Banks

The import tool auto-detects your bank from the CSV content. Currently ships with configs for:

- **HSBC** (Malaysia)
- **Maybank**

But there's no hard lock to these banks. The PDF parser agent uses Claude's understanding of document structure, so it can handle most bank statement formats. For CSVs, the Firefly III Data Importer is flexible about column formats — as long as your CSV has dates, descriptions, and amounts, it should work.

Want to add your bank? Drop a Data Importer config JSON in `src/firefly_mcp/configs/` and update the detection logic in `src/firefly_mcp/tools/import_tool.py`.

---

## Project Structure

```
firefly-tools/
├── .claude-plugin/plugin.json    # Plugin manifest
├── .mcp.json                     # MCP server registration
├── skills/                       # Slash command workflows
│   ├── setup/                    # /firefly-tools:setup
│   ├── import-and-review/        # /firefly-tools:import-and-review
│   ├── classify-unknowns/        # /firefly-tools:classify-unknowns
│   └── monthly-review/           # /firefly-tools:monthly-review
├── agents/                       # Subagent definitions
│   ├── csv-parser.md             # PDF → CSV extraction
│   └── merchant-classifier.md    # Merchant identification
├── hooks/                        # Lifecycle hooks
│   ├── hooks.json                # Hook configuration
│   └── check-setup.sh            # Nudges setup on session start
├── src/firefly_mcp/              # MCP server (Python)
│   ├── server.py                 # FastMCP server + tool registration
│   ├── client.py                 # Firefly III API client
│   ├── models.py                 # Pydantic models
│   ├── tools/                    # Tool implementations
│   └── configs/                  # Bank-specific import configs
└── tests/                        # Test suite
```

---

## Development

```bash
# Clone and install dependencies
git clone https://github.com/OriginalByteMe/firefly-tools.git
cd firefly-tools
uv sync --dev

# Copy and configure environment
cp .env.example .env
# Edit .env with your Firefly III credentials

# Run the MCP server directly
uv run firefly-mcp

# Run tests
uv run pytest

# Test the plugin locally
claude --plugin-dir .
```

---

## License

MIT
