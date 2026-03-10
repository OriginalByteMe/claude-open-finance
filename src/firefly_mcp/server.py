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
